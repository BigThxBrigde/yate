# 全量文档 review（doc-review-sweep）— 2026-10-05

> **范围**：仓库内受版本控制的全部 Markdown（**221 篇**），**排除** `.trae/rules/`
> 与 `.trae/agents/`（用户显式排除），实际纳入 **207 篇**。
> **方法**：机械体检（命名 / 相对链接 / 绝对路径 / 双语配对）+ 对 12 篇用户可见
> 文档做语义深度核对（3 名只读子代理分文件并行）+ 147 篇计划文档实施状态逐篇取证。
> **对照基准**：worktree `ref/doc-review-sweep` 的实际代码，非文档自身叙述。
> 方案与逐条处置见 [`../documents/doc-review-sweep-plan.md`](../documents/doc-review-sweep-plan.md)；
> 计划状态汇总入口见 [`../documents/overview.md`](../documents/overview.md)。
>
> 本文是**只读事实记录**（`doc-conventions` §二.1），只记录发现与核对结论。

---

## 一、机械体检结果

| 检查项 | 治理前 | 治理后 | 判定 |
|---|---|---|---|
| 命名违规（`doc-conventions` §一/§二） | **26 文件** | **0** | ✅ 归零 |
| 失效相对链接 | **22 文件** | **6 文件** | 🟡 仅剩真正失效目标（见 §四） |
| 真实机器本地路径（§五） | **51 文件** | **0** | ✅ 归零 |
| 已脱敏占位示例（按 §五 保留） | — | 12 文件 | ✅ 口径内 |
| `yate/docs` 双语配对 | 4 组全成对 | 4 组全成对 | ✅ 始终合规 |

### 1.1 命名违规（26 文件 → 0）

| 违规 | 文件数 | 处置 |
|---|---|---|
| `code-review-fix-plans/P1-subplans/`、`P2-subplans/` 嵌套子计划目录（规范只定义一层 `<task>-plans/`） | 17 | 消除嵌套：先改名为 `code-review-fix-p1-plans/` / `code-review-fix-p2-plans/`，再上提为 `.trae/documents/` 直属子计划目录；16 篇文档的相对引用回退一层 |
| `keybinding-fix-wt/` 目录名非 `<task>-plans/` 形态 | 9 | → `keybinding-fix-wt-plans/` |
| `keybinding-fix-wt/issue_reply_IKH1RA.md`（下划线 + 大写 + 非 `*-plan-<a>.md`） | 1 | → `keybinding-fix-wt-issue-reply-plan-h.md`（字母位续排在 plan-h） |
| `fix-folder-deletion-does-not-notify-LSP-plan.md`（文件名含大写） | 1 | → `fix-folder-deletion-lsp-notify-plan.md` |

改名均**保持目录深度**（除上提的两个目录），入链经脚本全量同步并复跑探针校验。

### 1.2 相对链接（22 → 6 文件）

已修复 **约 290 处**，按三类可机械判定的形态：

1. **写成仓库根相对**（如 `.trae/documents/` 下的 `[x](yate/cli.py#L95)`）→ 改写为文档相对；
2. **少写一层 `../`**（如 `../../yate/diagnostics.py` 落在 `.trae/yate/`）→ 补一层；
3. **跨目录同号文件 / 改名前旧名**（`code-review-fix-suggestions-plan-b.md`、
   `plan_A_assembly.md` → `editor-refactoring-assembly-plan-a.md`）→ 指向真实路径。

**残留 6 文件为真正失效目标**，按 `doc-conventions` §五「存量文档随下次修改逐步
迁移，**不做专项清扫**」保留原样，登记为待办（见 §四）。

---

## 二、语义偏离（用户可见文档，12 文件）

三名词**只读**子代理按互不重叠文件切分并行核对，主代理逐条复核证据。

### 2.1 根文档（`README.md` / `README.zh.md`；`CHANGELOG.*` 核验**无偏离**）

| # | 偏离 | 证据 | 处置 |
|---|---|---|---|
| 1 | 扩展自动加载漏 `:trust` 前置 | `extensions.py:621-633` 对未信任工作区跳过并提示 | 双语补注 |
| 2 | 冒烟标签清单与合法标签几乎不匹配（写 `--tag misc` 会 SystemExit） | `tools/smoke_test/harness.py:87-99` 合法 11 个；`:514-520` 未知标签退出 | 双语改为代码真值 + 说明 `misc` 是 primary tag 兜底、`slow` 是布尔开关 |
| 3 | 覆盖率阈值 "actions >=50%" 不存在 | `report.py:332` 两者共用 60% | 双语改为同用 60% |
| 4 | `--report` 被描述为机器可读 | `tools/smoke_test/cli.py:66-69` 是独立 HTML | 双语区分 `--json` / `--report` |
| 5 | 依赖清单漏 `pyperclip` | `pyproject.toml:12-15` | 双语补齐 |
| 6 | 结构树漏 `keyproto/` `editor_sprites/` `*_flows.py`、`resources/` 说明不全 | 目录实测 | 双语补入 |
| 7 | Usage 缺 `--diff` `--2way` `--3way` `--readonly` `--version`、`:diff` | `cli.py:64,72-77,161-163,180-200`；`commands.py:365` | 双语补齐 |
| 8 | en/zh 不同步（中文侧多一段 changelog 缺资源回退说明） | `editor_view/manual.py:47-59` | **英文侧补齐**（保留中文侧） |
| 9 | `cd d:\Programming\yate-pack-wiki` 真实路径 | §五违规 | → `cd <checkout>` |

### 2.2 `yate/docs` 双语手册（8 文件）

| # | 偏离 | 证据 | 处置 |
|---|---|---|---|
| 1 | yaterc 称"只有九个选项"，实为 15 个 | `config.py:60-64` + 5 个表项 | 改为无硬编码数字表述 |
| 2 | yaterc 缺 `show_hidden` / `key_protocol` | `config.py:631-638` / `:70,151,577-584` | 双语补两行 |
| 3 | yaterc 指向 `_make_buffer` / `_apply_buffer_options`（全仓不存在） | 实际是 `session.py:72-83` 的 `make_buffer` / `apply_buffer_options` | 双语改指 `yate/session.py` |
| 4 | yaterc 日志名缺 `-<pid>` | `logs.py:568-571` | 双语修正 |
| 5 | themes 称方式 A 注入 `Theme` + `register_theme` | `config.py:267-271` 只注入 `register_theme` | 双语改口径，与 `yaterc.*` 对齐 |
| 6 | lsp 的 Python 服务器发现顺序漏 venv scripts 目录一步 | `extensions/python_lsp.py:37-50,86-94` | 双语补第 3 步（3 步 → 4 步） |
| 7 | extensions 称"加载顺序即编号顺序"，`--ext-dir` 实为最先 | `services/extensions.py:615-637` | 双语改为真实序列 |
| 8 | extensions `:trust` 未提符号链接工作区被拒 | `extension_flows.py:79-88` | 双语补一句 |

**连带修正（子代理主动上报、主代理裁定）**：`yate/resources/manual.{en,zh}.md`
的 Python LSP 发现顺序同样是 3 步，与 §2.2-6 同一处偏离，已同步为 4 步；
`yate/yaterc.example` 未覆盖 `show_hidden` / `key_protocol`，且示例内的日志名
同样缺 `-<pid>`，三处一并补齐。

### 2.3 `.trae/wikis`（2 文件）

| 偏离 | 证据 | 处置 |
|---|---|---|
| 架构用例写 20（实为 22） | `tests/test_architecture.py` 实测 22 个 `def test_*` | 改 22，核对日期改 2026-10-05 |
| 测试文件写 47（实为 58） | `tests/` 实测 58 个 `test_*.py` | 改 58 |
| `CompletionController`（全仓无此符号） | `completion.py:51 class CompletionFlows`；`editor.py:342` | 改 `CompletionFlows` |
| `_load_app_css()`（全仓无此函数） | `app.py:32,82-83` 用 `paths.load_tcss("app.tcss")` | 改为 `yate.paths.load_tcss` |
| `editor.py::load_startup_services`（不存在） | 实际 `editor.py:433-434` → `extension_flows.py:49,104`；headless `cli.py:379-380` | 替换并补 headless |
| `extensions/` 行把 C# 高亮算作扩展 | `yate/extensions/` 仅 `python_lsp.py` + 6 个 `*.py.example`；C# 属内置语法层 | 改准确表述 |
| §3 `editor_view/` 表缺 `diffview.py` | `editor_view/diffview.py:233,520,528` | 补行 |
| §4 事件流顺序与代码不符且漏 prompt 短路 | `editor.py:553-645` 实际分派顺序 | 按实测顺序改写 + 补 9 行分派顺序表 |
| 模块清单漏 `keyproto/frames.py`、`services/clipboard.py`、`editor_core/{diff,indentation,textobjects}.py`、`dist_meta.py`、`tools/translate/`、R6 流程模块族 | 目录实测 | 补入 |
| `textual-framework-hooks.md` **6 处 `app.py` 行号全部失效** | 逐条实测：`ENABLE_COMMAND_PALETTE` 46、`get_driver_class` 65、`on_event` 224、`get_theme_variable_defaults` 282、`action_quit` 298、`execute_action("quit")` 306 | 全部更新，核对日期改 2026-10-05 |
| `$doc-hit-*` 变量归因错误 | 实际在 `resources/markdown-doc-screen.tcss:51,54`，由 `manual.py:183` 装载 | 改指资源文件 |
| 主题桥变量行号 `theme.py:618-619` | 实测 `:645-646` | 修正 |

---

## 三、`.trae/reviews/` 索引核对

| 发现 | 处置 |
|---|---|
| **漏登记 2 篇**：`2026-10-03-pr51-path-space-ai-review.md`、`2026-10-03-wiki-translate-progress.md` | 速览表补 #26 / #27，轮次总表补 2 行，计数由「11 项未关闭」更新为「27 条：未闭环 12 / 已闭环 14 / 部分闭环 1」 |
| 速览 #1 与总表 2026-09-16 行称 ctrl+digit 已 ✅，但源文档 `2026-09-16-full-review.md:274-276` 仍 `- [ ]` + ⏸ 暂缓，全文无 `2026-10-01`/`PB6` | **回填源文档**（评审记录是只读事实文档，销账依据必须落在源文档）：补 ✅ 闭环注记，写明 win32-input-mode 落地、PB6 真机帧 `[49;2;0;1;40;1_` 12/12 PASS、legacy 限制已由 PB4 标注、残留并入速览 #10 |
| 速览 #24 严重度口径混用（"5 WARNING" 来自源文档"计划核对阶段"限定语，"9 SUGGESTION" 为索引自行加总） | 改为与源文档一致：`0 CRITICAL / 5 WARNING（计划核对阶段 G1–G5）/ 若干 SUGGESTION（逐条共 18 条：G1–G8 + H1–H10）` |
| 总表 2026-10-04 行的"最终 24 提交 / 61 文件 / +3597 −257"为**索引独家数字**（源文档与修复方案均零命中） | 删除不可核实的数字，保留源文档记载的评审时点值 |

**误报纠正**：子代理报告「`P2-subplans` 下 `plan-f` 字母位重复」——**不成立**。
实测该目录为 a–g 七个唯一字母位（`services-logs` 为 `-plan-g`），无重复，
未据此做任何改动（`subagent-workflow` §五.6：只认落盘结果与复核证据）。

---

## 四、计划文档实施状态（147 篇逐篇取证）

| 状态 | 篇数 | 篇目与依据 |
|---|---|---|
| ❌ **未实施** | **2** | `dap-support-plan.md`（`yate/editor_dap*` 实测零文件、`extensions/python_dap.py` 与 `yate/docs/dap.*.md` 不存在、`config.py` 无 `debug_options`）、`highlight-comment-flicker-plan.md`（无专属产物） |
| 🟡 **部分实施** | **4** | `win-keybinding-protocol-plan.md`（`keyproto/` 落地 5 模块；`kitty.py` / `negotiate.py` / `--key-protocol` / `keys` 命令 / `tools/probe_keys.py` 未落地）、`wt-keybinding-fix-plan.md`（SP1–SP3 已执行，后续由 steps-plan-g 承接）、`keybinding-fix-wt-plans/overview.md` 与 `keybinding-fix-wt-gates-matrix-plan-e.md`（SP5 三终端真机人工矩阵未执行，即速览 #10） |
| ↩️ **已被取代** | **7** | `remove-type-checking-refactor.md`、`split-app-protocol-plan.md`、`logs-impl-plan.md`、`unify-crash-tracing-plan.md`（后两者实现迁至 `yate/logs.py`）、`keybinding-fix-wt-plans/keybinding-fix-wt-key-reachability-plan-f.md`（根因假设被探针证伪）、`theme-ownership-plan.md`（明示"不再维护"）、`editor-refactoring-plans/overview.md` |
| ✅ **已实施** | **134** | 文档自述与代码产物一致 |

**状态头曾滞后 2 篇**（自述与产物矛盾，方向为低报）：`input-assist-plan.md`
（仍写"待用户批准、尚未写任何产品代码"，但 `editor_core/indentation.py`、
`tests/test_input_assist.py`、双语手册 §3.5 均已落地）；
`code-review-fix-plans/code-review-fix-suggestions-plan-b.md`
（仍写"仅为计划，未实施"，同文后续记录却已写"全部实施完成"）。

**处置**：147 篇统一注入可检索状态块（幂等，已连跑三次验证 0 变更），
汇总入口 `.trae/documents/overview.md`。

---

## 五、待办（本轮**未**处理，附原因）

1. **6 篇文档 24 处失效链接**：目标已删除或本就在仓库外——
   `yate/app_features/*`（分层重构删除，见 `dap-support-plan.md` 13 处、
   `changelog-plan.md` 3 处、`wq-safety-plan.md` 3 处、`typing-flicker-debounce-plan.md` 1 处）、
   `yate/crash.py`（`pytest-isolation-plan.md` / `setup-defaults-plan.md` 各 1 处）、
   `.venv/Lib/site-packages/textual/widget.py`（`typing-flicker-debounce-plan.md` 1 处）、
   `../changes.diff`（`wq-safety-plan.md` 1 处）。
   **原因**：`doc-conventions` §五 明文"存量文档随下次修改逐步迁移，不做专项清扫"；
   批量降级为行内代码会丢失"此处曾有产物"的历史线索。
2. **`keybinding-fix-wt-plans/` 内 3 个一次性脚本**（`win32im_probe.py`、
   `pb6_real_input_harness.py`、`verify_matrix.ps1`）：是计划证据附件而非文档，
   `doc-conventions` 无对应形态，保留原位。
3. **`.trae/rules/architecture-boundaries.md` 三处偏离**（用户本轮显式排除 rules）：
   ① R4 与 §六 UI-free 守卫面漏列 `editor_core`（`tests/test_architecture.py:102-108`
   已纳入）；② 三处 `test_architecture.py:88` 行号应为 `:102`；
   ③ §五自检清单"除 `PaneRegistry`"应为"除 4 类冻结白名单"。
   建议另开独立任务处理。
4. **`tests/test_app_textual.py::test_type_save_find_help_keymap` 计时类偶发**：
   带 `--cov` 运行时 1 次 `ScreenStackError`（`app.py:252 poll_idle` 屏保轮询与
   screen 拆除竞争）。单独连续重跑 3 次全绿，全量带覆盖率重跑亦全绿，
   判定为**覆盖率拖慢下的既有偶发**，非本轮引入（本轮零产品代码改动），
   按 `subagent-workflow` §三.3 不改断言。

---

## 六、实测门禁（主代理亲自跑，worktree `.venv`）

| 命令 | 退出码 | 结果 |
|---|---|---|
| `python -m pyright yate/ tests/ tools/` | **0** | `0 errors, 0 warnings, 0 informations` |
| `python -m pytest tests/ -q` | **0** | **1818 tests / 0 failures / 0 errors / 8 skipped**（JUnit XML 取数） |
| `python -m pytest tests/test_architecture.py -q` | **0** | **22 passed / 0 failures** |
| `python -m pytest tests/ -q --cov=yate --cov-fail-under=75` | **0** | 覆盖率 **91.27%** ≥ 75%（TOTAL 13126 语句 / 928 miss） |

**环境偏离记录**：复用既有 worktree `D:/Programming/yate-doc-review-sweep` 时发现
其 `.venv` **不完整**（缺 `textual` / `rich`，且未装 yate 本体），子代理实测
`.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q` 直接
`ModuleNotFoundError` 退出码 4。已按 `task-orchestration` §二.1 补装
`.venv\Scripts\python.exe -m pip install -e ".[dev]"`，自证
`yate.__file__` 指向本 worktree、`textual 8.2.8` 到位后门禁方可运行。
