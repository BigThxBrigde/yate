# lsp-uri-canonical-fix-plan

## 目标与非目标

**目标**：修复 !146（ce6d079a）合入 master 后 CI 暴露的两类测试失败：

1. **Ubuntu CI pytest 2 例**（`tests/test_lsp_navigation.py`）：
   - `test_canonical_uri_maps_drive_escaped_and_plain_forms_to_one`
   - `test_manager_notification_uses_canonical_diagnostic_uri`
2. **Windows CI 冒烟 3 个检查**（`tools/smoke_test`）：
   - `lsp_navigation_gd_jumps_across_files_in_both_keymaps`: `jump_vsc` / `jump_vim`
   - `lsp_navigation_gr_chooser_lists_both_files_and_enter_navigates`: `enter_navigates`

**非目标**：不改 LSP 请求层行为语义；不改 pytest fixture/tmp 体系；不动 `uri_to_path`
对 nt 平台外的盘符剥离行为（仅 `canonical_uri` 归一）。

## 根因（已实证）

### 根因 A：`canonical_uri` 盘符大小写归一依赖平台（Ubuntu 失败）

- 位置：`yate/editor_lsp/protocol.py` `_url_path_to_pathname`（L144-152）
  仅当 `os.name == "nt"` 才把 `/d:/x.py` 剥成 `d:/x.py`，且 `resolve()` 在
  Windows 上才顺带归一大小写。
- Linux 上 `canonical_uri("file:///d%3A/x.py")` → `Path("/d:/x.py")` →
  `file:///d%3A/x.py`；`canonical_uri("file:///D:/x.py")` →
  `file:///D%3A/x.py`。盘符大小写不归一 → 两个用例失败（CI 日志原文：
  `assert 'file:///d%3A/x.py' == 'file:///D%3A/x.py'`）。
- manager 用例同理：`publishDiagnostics` 的 drive-escaped URI（小写盘符）
  经 canonical 后仍与 `_uri(doc)`（大写）不等 → `_diagnostics` 以
  escaped 形式为键 → 断言 `escaped_uri not in _diagnostics` 失败。

### 根因 B：冒烟 harness tmp 根路径未 resolve（Windows 失败，已本地复现）

- GitHub Windows runner 的 TEMP 是 8.3 短路径（用户目录的 `RUNNER~1`
  缩写形态）。
- 场景断言 `app.editor.session.doc.path == def_path`，其中 `def_path = tmp /
  "mathutil.txt"`（harness `TemporaryDirectory()` 原样返回的短路径形式）。
- 跳转链路 `_jump_to_row` → `uri_to_path(canonical_uri(path_to_uri(def_path)))`，
  `path_to_uri` 内部 `Path.resolve()` 把短路径展开为长路径 →
  `session.doc.path`（长）≠ `def_path`（短）→ 谓词 5s 内恒假。
- 旁证与 CI 日志完全吻合：`jump_message_vsc` / `jump_message_vim` /
  `enter_message` 均通过（消息在 open+set_cursor 之后发出），仅路径恒等
  谓词失败；gd 场景耗时 10360ms ≈ 两次 5s `wait_until` 超时。
- **本地复现**：TEMP 指向 junction（等价于短路径的 resolve 改写机制）时
  精确复现 CI 同款失败（20/23，`jump_vsc`/`jump_vim`/`enter_navigates`）；
  TEMP 为长路径时 43/43 全过（本地无 8.3 短名，`Administrator` 无短名别名）。

## 备选方案与否决理由

### Bug A 备选

- **A1（采纳）**：`canonical_uri` 内平台无关地归一化盘符段大小写——
  对 `uri_to_path` 结果的字符串形式匹配可选前导 `/` + 单个 ASCII 字母 +
  `:` 的盘符段，大写后重建 URI。
- **A2（否决）**：改 `_url_path_to_pathname` 在 POSIX 上也剥盘符——
  改变了 `uri_to_path` 的公开语义（POSIX 上 `/d:` 是普通目录名），
  影响面大于本缺陷所需。
- **A3（否决）**：仅在 nt 分支处理、POSIX 跳过——正是当前缺陷的成因，
  与测试要求的平台无关恒等矛盾。

### Bug B 备选

- **B1（采纳）**：harness CLI 侧一次性 `Path(td).resolve()`——单点根修，
  所有现存与未来场景的 tmp 根都是 resolved 长路径，与 `path_to_uri`
  round trip 一致。
- **B2（否决）**：逐场景改断言为 `resolved_path` 比较——治标，新增场景
  仍会踩同一坑，且要改多处断言。

## 分步实施

### 步骤 1：修 `canonical_uri`（Bug A）

- 输入：根因 A。
- 改动文件：`yate/editor_lsp/protocol.py`（`canonical_uri` 函数体）。
- 输出：`file:///d%3A/x.py` 与 `file:///D:/x.py` 归一为同一 canonical 形式
  （POSIX 上 `file:///D%3A/x.py`；nt 上 `file:///D:/x.py`，与现状一致）。
- 验收命令：
  - `.venv\Scripts\python.exe -m pytest tests/test_lsp_navigation.py -q`
  - POSIX 行为模拟探针（临时脚本，验证后删除）：patch
    `protocol.os.name = "posix"` 后断言两形式归一相等。

### 步骤 2：修冒烟 harness tmp 根（Bug B）

- 输入：根因 B。
- 改动文件：`tools/smoke_test/cli.py`（3 处 `TemporaryDirectory()` 使用点）。
- 输出：`tmp_root` 传入 harness 前已 resolve；并行路径 `str(tmp_root)`
  与 retry 子目录继承 resolved 根。
- 验收命令（复现条件）：
  - `$env:TMP` 指向 worktree 内预建的 junction 别名目录（模拟 CI 短路径）
    下 `.venv\Scripts\python.exe -m tools.smoke_test run --tag lsp-navigation --jobs 1`
    应 43/43 全过；
  - 正常 TEMP 下同命令回归。

### 步骤 3：全量门禁（主代理亲自）

- `.venv\Scripts\python.exe -m pyright yate/ tests/ tools/ pack/`
- `.venv\Scripts\python.exe -m pytest tests/ -q -n auto`
- `.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q`
- `.venv\Scripts\python.exe -m tools.smoke_test run --jobs 4`
- 冒烟报告 HTML 产物 `smoke-report.html` / json 属临时产物，不提交。

## 风险清单与回滚

- `canonical_uri` 收紧归一后，若有测试/调用方依赖小写盘符 canonical 形式
  → grep 全库确认（当前仅 manager 两处调用 + smoke 场景），风险低。
- harness resolve 后，SVG 基线含绝对路径（默认 off）不受影响；报告表宽
  不受影响（表内为场景名非路径）。
- 回滚路径：分支单笔 revert；master 未动。

## 涉及架构/流程

无需 Mermaid 图：修复为两个局部函数级改动，不跨模块交互（protocol.py 单
函数 + smoke cli 单点）。

## 流程偏离记录

- 无人值守模式：用户在任务指令中明确「进入无人值守纪律，按照闭环纪律执行
  修复」，视为对步骤【批准】的预授权，本计划落盘后直接进入执行，不再等待
  确认；批准记录以本节为准。

## 执行记录（回填区）

- **步骤 1（Bug A）**：提交 83895cb5。`canonical_uri` 平台无关大写盘符段
  （裸 `d:` 与前导 `/d:` 两种拼写）。验证：
  - POSIX 模拟探针（patch `_url_path_to_pathname` + `PurePosixPath.as_uri`，
    临时脚本已删除）：`file:///d%3A/x.py` 与 `file:///D:/x.py` 归一为
    `file:///D%3A/x.py` 相等；非盘符 POSIX 路径与非 file scheme 透传不变。
  - Windows 真机：`tests/test_lsp_navigation.py` 64 例全过。
- **步骤 2（Bug B）**：提交 ecc3ef1b。`tools/smoke_test/cli.py` 新增
  `_resolved_tmp`，run/snapshot/compare 三处 tmp 根先 `Path.resolve()`。
  验证：junction 别名 TEMP 下 4 场景 43/43（修复前同条件 20/23，同款
  `jump_vsc`/`jump_vim`/`enter_navigates` 失败）；正常 TEMP + jobs 4 +
  repeat 3 回归 43/43。
- **审核**：`code-review-expert` 评审（子代理，DeepSeek-V4.1-Flash）结论
  **无 blocker / major**，3 条 minor：
  1. 盘符判定谓词在 protocol.py 内 4 处重复（建议抽 `_is_ascii_drive_at`
     助手）→ **登记待办**，不在本闭环扩散重构；
  2. POSIX 根级 `/d:/` 真实路径会被误改写（固有取舍）→ **已采纳**：
     afb3603d 在 `canonical_uri` 注释显式登记该取舍；
  3. 建议补透传/空 URI 钉死用例 → **登记待办**。
- **门禁实测**：
  - pyright 全量（yate/ tests/ tools/ pack/）：0 errors, 0 warnings（exit 0）；
  - pytest 全量 `-q -n auto`：首轮 1 失败——架构守卫
    `test_no_machine_local_home_paths_in_sources` 命中 `_resolved_tmp`
    docstring 中的 RUNNER~1 家目录示例路径（属文档措辞违规，非代码
    缺陷）；afb3603d 改写 docstring 后 `tests/test_architecture.py` 47 例
    全过、目标模块全过、定向 pyright 0 诊断；最终全量复跑见下条；
  - 最终全量 pytest `-q -n auto`：exit 0 全过（仅既有 skip）；
  - 最终全量冒烟（CI 同口径 `--json smoke-report.json --report
    smoke-report.html --jobs 4`）：1554/1554 checks，128/128 scenarios，
    exit 0（报告产物为临时文件，未提交）。
- **偏离记录**：无方案偏离；评审 minor 1/3 未采纳为代码改动，已登记待办。
- **纪律修正**：复现探针（junction `yate-tmp-link`/`yate-tmp-real` 与临时
  脚本）曾散落在 worktree 外，收尾时已全部删除；后续闭环任务的一切临时
  产物一律放 worktree 内并用后即删。
