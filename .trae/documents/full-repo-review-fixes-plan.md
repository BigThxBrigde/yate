# 2026-11-26 全仓库评审修复方案

- 基线：worktree `yate-full-repo-review`、分支 `feature/enh-full-repo-review`，起点
  `master` `b97a695c`；评审产物为 4 笔提交（`8c805463`…`0918b4fd`）。
- 规范来源：[评审记录](../reviews/2026-11-26-full-repo-review.md)（findings 编号与
  `文件:行号` 为唯一事实来源）、[评审方案](full-repo-review-plan.md) §八、
  [规则总纲](../rules/task-orchestration.md)、[Python 风格](../rules/python-coding-style.md)、
  [架构边界](../rules/architecture-boundaries.md)。
- 批准状态：用户于 2026-11-26 以「按计划执行」批准上一轮汇报中的修复请求
  （「另出 `full-repo-review-fixes-plan.md` 并修复这些发现」）。本方案是该批准的落实；
  遇到新的设计裁决点（不在已批准的 33 条 findings 内）停下上报，不自行扩大范围。
- 规划产出：`plan-architect-designer` 的 `qwen-3.8-plus` 在本会话已两次报未注册，按
  `task-orchestration.md` §三由主代理亲自按剧本代笔，如实标注「规划子代理零产出」。

## 一、目标与非目标

**目标**：修复评审记录中全部 **5 MAJOR + 28 MINOR = 33 条 findings**，每条附回归用例；
S5/S6 独立审核的裁定为修复设计的边界（不得重开已驳回的提议）。

**非目标**：

- 6 条 SUSPECT 与 25 条 SUGGESTION 保持登记状态，不在本轮修复（其中 mdlint 围栏取舍、
  `error_for` UI 缺口、`_render_parent` 缓存绕过等需实测或产品裁决）。
- 不合并、不推送；产品代码修复只在当前分支逐波提交。
- 不改 CI 配置、依赖版本与 Textual 内部实现。

## 二、备选方案与否决理由（按 finding 归并）

| 主题 | 采用 | 否决的路线与理由 |
|---|---|---|
| M1 补全并集 | buffer 级聚合词集随 `content_version` 增量更新；top-k 用 `heapq.nsmallest` | ① 全局缓存跨 buffer 共享：文档身份与版本失效难界定，历史上 per-view 缓存因缺身份出过 bug；② 只调 debounce：请求次数不变，单次仍 O(文档) |
| M2 `diff_words` | 行长超过阈值退回整行高亮；保留字符级 `SequenceMatcher` 用于短行 | ① 一律词级 diff：短行结果质量下降且改变既有展示语义；② 只提高 `MAX_DIFF_LINES`：缺陷是行长不是行数 |
| M3 vim count | `min(int(count), 上限)` 且按边界预计算终点（`x` 到行尾、motion 到文件边界） | ① 只加暂停检查：UI 线程不可中断，检查点仍可能过疏；② 禁止长数字：vi 兼容行为退化 |
| M4 release 回滚 | `except (RuntimeError, OSError, KeyboardInterrupt)` 统一回滚后原样 `raise` | `except BaseException`：会捕获 `SystemExit` 等非用户错误，吞掉正常退出路径 |
| M5 分派异常边界 | L1 `ActionContext` 注入错误报告回调；三处分派点 `log.exception` + 用户可见错误，会话保留 | ① App 层统一兜底：L1 registry 不能 import L3（R1/R5 架构违例）；② 保持 panic：编辑器会话与未保存内容丢失 |
| m4 锁表误摘 | 锁对象随 `OpenDocState` 生命周期管理，避免在途摘除引用 | ① 仅判断 `lock.locked()`：等待者已持有旧引用时仍会并发；② 删除 close 淘汰：锁表无界增长 |
| m6 诊断行索引 | 按 start/end 排序 + `bisect` 的区间索引 | ① 提高 `_ROW_INDEX_SPAN_MAX`：只缓解常数，不改复杂度类；② 取消行索引：`diagnostic_at` 回退全表扫描（#77 已修问题） |
| m1 分数解析 | `int(denominator)` 移入同一 `try`，错误文案带选项名 | 放宽 `isdecimal()` 校验：会让更多非法值进入转换，掩盖真实错误 |
| m11 changelog 重复 heading | 解析期检测到重复即报明确错误 | 保留最后一个：`check` 会放过已漂移的段落（finding 本身） |

## 三、波次与独占文件清单

```mermaid
flowchart LR
    A["波次 A<br/>性能热路径<br/>yate/ 核心"] --> B["波次 B<br/>LSP / 配置 / 分派边界<br/>yate/ 上层"]
    B --> C["波次 C<br/>工具链<br/>tools/"]
    C --> D["波次 D<br/>测试与文档<br/>tests/ + .trae/ + docs"]
    D --> E["审核迭代 + 全量门禁 + 回填"]
```

文件独占规则：同一波内文件不重叠；跨波可再次触碰同一文件（波次串行），但每波提交独立。
`yate/` 产品源码一律由**主代理**修改（subagent-workflow §一.3 禁止子代理改产品源码）；
波次 C / D 的 `tools/`、`tests/`、`.trae/` 部分可派 `plan-executor` 并行，任务书以本方案为
唯一规范来源并列出独占文件。

### 波次 A — 性能热路径（finding M1 / M2 / M3 / m6 / m7 / m9）

| finding | 改动文件 | 回归用例 |
|---|---|---|
| M1 | `yate/editor_components/completion.py` | `tests/test_completion.py`（大缓冲请求只做增量并入；items 上限仍 64；旧 buffer 不串味） |
| M2 | `yate/editor_core/diff.py`、`yate/editor_components/diff/screen.py` | `tests/test_diff_words.py`（长行退化路径 + 短行词级结果不变 + 超长行不触发 `SequenceMatcher`） |
| M3 | `yate/keymaps/vim.py` | `tests/test_keymaps_vim.py`（超大 count 即时返回；`x` 到行尾不空转；`p` 粘贴次数受上限） |
| m6 | `yate/editor_lsp/manager.py` | `tests/test_lsp.py`（区间索引与线性扫描结果一致；超宽 span 走 overflow；`diagnostic_at` 语义不变） |
| m7 | `yate/editor_components/manual.py` | `tests/test_manual.py`（连续 resize 只保留最后一个 timer；卸载后无悬挂 timer） |
| m9 | `yate/actions.py`、`yate/editor_core/commenting.py` | `tests/test_toggle_comment.py`（大文档选区操作只拷贝选区；整行/块注释可逆性不变） |

验收命令（逐条，失败即停）：

```powershell
.venv\Scripts\python.exe -m pytest tests/test_completion.py tests/test_diff_words.py tests/test_keymaps_vim.py tests/test_lsp.py tests/test_manual.py tests/test_toggle_comment.py -q -p no:cacheprovider
.venv\Scripts\python.exe -m pyright yate/editor_components/completion.py yate/editor_core/diff.py yate/editor_components/diff/screen.py yate/keymaps/vim.py yate/editor_lsp/manager.py yate/editor_components/manual.py yate/actions.py yate/editor_core/commenting.py
```

### 波次 B — LSP / 配置 / 分派边界（finding m1 / m2 / m3 / m4 / m5 / m8 / m22 / M5）

| finding | 改动文件 | 回归用例 |
|---|---|---|
| m1 | `yate/yaterc_options.py` | `tests/test_yaterc_options.py`（`"1/--5"` 的友好文案 + 后续 extractor 仍执行） |
| m2 | `yate/editor_lsp/manager.py`、`sync.py`、`client.py`，`yate/services/trust.py`、`extensions/api.py`，`yate/editor_components/terminal.py` | `tests/test_lsp.py`、`tests/test_trust.py`、`tests/test_terminal.py`（失败路径有 `caplog` 记录） |
| m3 | `yate/editor_lsp/client.py` | `tests/test_lsp.py`（`workspace/configuration` 多项请求按项回填） |
| m4 | `yate/editor_lsp/sync.py` | `tests/test_lsp_sync.py`（文档重开 + 在途 notify 下不产生重复 version） |
| m5 | `yate/editor_lsp/navigation.py` | `tests/test_lsp_navigation.py`（活动参数是重复子串时高亮 `start:end`） |
| m8 | `yate/logs.py` | `tests/test_logs.py`（不可写目录时 stderr 有 warning 且 editor 仍启动） |
| m22 | `yate/services/workspace.py` | `tests/test_workspace.py`（Windows 保留名/尾随点给出明确错误） |
| M5 | `yate/editor.py`、`yate/registries.py`、`yate/keymaps/base.py` | `tests/test_app_commands.py`、`tests/test_registries.py`（处理器抛异常应用不退出、有日志与用户提示；扩展回调同样隔离） |

验收命令：

```powershell
.venv\Scripts\python.exe -m pytest tests/test_yaterc_options.py tests/test_lsp.py tests/test_lsp_sync.py tests/test_lsp_navigation.py tests/test_logs.py tests/test_workspace.py tests/test_app_commands.py tests/test_registries.py -q -p no:cacheprovider
.venv\Scripts\python.exe -m pyright yate/
```

### 波次 C — 工具链（finding M4 / m10 / m11 / m12 / m13 / m14 / m15 / m16 / m18 / m19 / m20 / m21 / m28）

独占文件（仅 `tools/**` 与对应 `tests/test_*`）：

- `tools/release/cli.py`（M4）；`tools/pack/zip_dist.py`（m14）；`tools/translate/cli.py`（m15）；
  `tools/pack/icon.py`（m16）；`tools/pack/wiki/publish.py`（m18）；
  `tools/probes/pb6_real_input_harness.py`（m19）；`tools/probes/win32im_probe.py`（m20）；
  `tools/screenshots/driver.py`、`tools/screenshots/__main__.py`（m21）；
  `tools/changelog/render.py`（m11）；`tools/lint_lua.py`（m10）；
  `tools/smoke_test/harness.py`、`tools/smoke_test/cli.py`（m12）；
  `tools/smoke_test/harness.py`、`tools/smoke_test/testsuite.py`（m13 / m28）。

回归用例落在既有测试中或新增 `tests/test_<tool>.py`；验收命令：

```powershell
.venv\Scripts\python.exe -m pytest tests/test_release_cli.py tests/test_zip_dist.py tests/test_changelog_tool.py tests/test_smoke_cli.py tests/test_lua_lint.py -q -p no:cacheprovider
.venv\Scripts\python.exe -m pyright tools/
.venv\Scripts\python.exe -m tools.smoke_test run --jobs 4
```

### 波次 D — 测试与文档（finding m23 / m24 / m25 / m26 / m27 / m29）

- `tests/test_architecture.py`（m23：守卫改为 AST 比较 `on_event` 内闸门语句与转发语句行号，
  并保留负向演练）；`tests/test_theme_reset_fixture.py`（m24：合并不依赖 worker 顺序）；
  `tests/test_lsp_real_server.py`（m25：仅「未安装」skip，启动失败改 fail）；
  `tests/test_explorer.py` 或新增用例（m26：建/改/删错误分支）；
  `tests/conftest.py`、`test_architecture.py`、`test_lua_lint.py`、`test_pack_zip.py`（m27：行宽）。
- 文档漂移（m29）：`.trae/skills/{multi-dim-review,pr-review,textual-pilot-smoke}/SKILL.md`、
  `.trae/agents/{code-review-expert,coder,plan-architect-designer}.md`、
  `.trae/rules/{python-coding-style,architecture-boundaries}.md`、
  `yate/docs/lsp.{en,zh}.md`（标题数对齐）。只做文本更正，不改行数结构；架构守卫与
  `test_architecture.py` 的规则表锚点须同步复测。
- 验收命令：

```powershell
.venv\Scripts\python.exe -m pytest tests/ -q -n auto
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
.venv\Scripts\python.exe -m tools.mdlint --auto-lang --check .trae/ yate/docs/
```

## 四、风险清单与回滚路径

| # | 风险 | 应对 |
|---|---|---|
| R1 | M5 错误报告回调跨 L1/L3 触架构边界 | 回调定义在 L1 `ActionContext`（`Callable[[str], None]` 内联），由 L3 `Editor` 注入；不新增 Protocol / TYPE_CHECKING；波次 B 后立刻跑 `test_architecture.py` |
| R2 | M1 聚合缓存与 buffer 版本失效错位导致补全串味 | 缓存以 `id(buf)` + `content_version` 双键失效，并补「两 buffer 交替请求」回归；波次 A 首项先提交 |
| R3 | m6 区间索引与旧线性语义不一致（行号/列号边界） | 以旧算法作 oracle 做差分测试，超宽 span 保持 overflow 分支 |
| R4 | 波次 C 的子代理改漏 / 改错 tools 文件 | 只认落盘 diff；主代理逐文件回读并重跑该模块测试；零产出则主代理亲自实现 |
| R5 | safe-delete 钩子在 pytest 收尾杀进程 | 门禁一律用全新 `--basetemp`（`%TEMP%` 下），出现 `[safe-delete]` 行判环境伪影并重跑；不清理积压 |
| R6 | 文档行数变化触发规则表的行数/守卫数断言 | m29 只做等行替换；`test_architecture.py` 失败即还原并改用行内措辞 |
| R7 | 并行波次互相干扰（`--jobs 4` / `-n auto`） | 波次串行、单波内最多 2~3 个成员；flake 用 `-n 1` / `--jobs 1` 复核，禁止改断言掩盖 |

**回滚路径**：每波单独提交、只提交不推送；任一条修复无法在波次内转绿即
`git revert <该波提交>` 后停下上报；全部放弃时由用户显式要求才删除 worktree / 分支。

## 五、全量门禁（主代理亲跑，统一并行口径）

```powershell
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/ pack/
.venv\Scripts\python.exe -m pytest tests/ -q -n auto
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
.venv\Scripts\python.exe -m pytest tests/ --cov=yate --cov-branch -n auto
.venv\Scripts\python.exe -m tools.smoke_test run --jobs 4
.venv\Scripts\python.exe -m tools.changelog check
git --no-pager diff --check
```

## 六、执行日志（回填）

| 波次 | 提交 | 结果 | 门禁数字 |
|---|---|---|---|
| 方案 | 待回填 | 用户「按计划执行」批准；规划角色零产出由主代理代笔 | — |
| A | 待回填 | — | — |
| B | 待回填 | — | — |
| C | 待回填 | — | — |
| D | 待回填 | — | — |
| 门禁 / 审核 | 待回填 | — | — |

## 七、偏离记录（回填）

| # | 偏离 | 依据与处置 |
|---|---|---|
| — | 暂无 | — |
