# doc-review-sweep 方案（全量文档 review 整理）

> 任务来源：用户「新任务」——基于当前项目实现，对所有文档做 review 整理，
> **排除 `.trae/rules/` 与 `.trae/agents/`**；要求完整性、正确性、
> 修正偏离不符合之处、**未实施的计划需标注**。
> 无人值守执行：权限申请与步骤确认一律 bypass，不向用户发起询问。
>
> 工作区：`D:/Programming/yate-doc-review-sweep`（分支 `ref/doc-review-sweep`，
> 复用既有 worktree 及其 `.venv`，不新建沙箱）。

---

## 一、目标与非目标

### 目标

1. **完整性**：每篇文档在"事实、状态、引用"三个维度自洽无缺；
   建立 `.trae/documents/` 集中状态索引，让 147 篇计划的实施状态可一眼查全。
2. **正确性**：文档断言与当前代码/配置事实一致（行号、符号、数量、命令、默认值）。
3. **修正偏离**：命名、相对路径、绝对路径泄漏、失效链接、双语同步等
   `doc-conventions` 违规项全部修正。
4. **未实施计划标注**：4 类状态（已实施 / 部分实施 / 未实施 / 已被取代）
   在每篇计划文档头部显式标注，并汇总进索引。

### 非目标

- **不改 `.trae/rules/` 与 `.trae/agents/`**（用户显式排除）。
  规则文档本身被查出的偏离只登记在评审记录中，留作后续独立任务。
- 不改产品源码 `yate/`（本任务零代码行为变更）。
- 不重写历史计划正文；只修引用与状态头，保留原始记录。
- 不做 `git push`（闭环流程内禁止）。

---

## 二、事实基线（调研取证，2026-10-05）

受版本控制 Markdown 共 **221 篇**，排除 rules/agents 后 **207 篇**纳入本轮。

| 面 | 数量 | 取证方式 |
|---|---|---|
| 命名违规 | **26 文件** | 探针 `tools/_probe_docs.py` 逐路径比对 `doc-conventions` §一/§二 |
| 失效相对链接 | **22 文件**（含 1 篇 160 处量级） | 探针按"以文档自身位置为基准"解析 |
| 机器本地绝对路径 | **51 文件** | 探针正则 + 人工甄别占位符 |
| 计划文档 | **147 篇**（根级 65 + 子计划目录 82） | 3 只读子代理逐篇核对产物存在性 |
| 双语配对（`yate/docs`） | 4 组全部成对 ✅ | 探针 |

### 2.1 命名违规（26 文件，真实违规）

| 违规对象 | 文件数 | 实测 |
|---|---|---|
| `code-review-fix-plans/P1-subplans/`、`P2-subplans/` 嵌套子计划目录 | 17 | `doc-conventions` §一只定义 `<task>-plans/` 一层子计划目录，无嵌套形态 |
| `keybinding-fix-wt/` 目录名非 `<task>-plans/` 形态 | 9 | 实为子计划目录（内含 `overview.md` + plan-a…g） |
| `keybinding-fix-wt/issue_reply_IKH1RA.md` | 1 | 含下划线 + 大写 + 非 `*-plan-<a>.md` |
| `fix-folder-deletion-does-not-notify-LSP-plan.md` | 1 | 文件名含大写 `LSP`，违反"文件名一律 ASCII 小写" |

**改名前置核查**：`P1-subplans` / `P2-subplans` / `keybinding-fix-wt` /
`issue_reply_IKH1RA` 在全仓 Markdown 中的入链数为 **0**（仅 `tests/test_keyproto.py`
注释引用 worktree 路径），改名风险极低。

### 2.2 误报纠正（子代理错误，主代理复核后否决）

子代理报告「`P2-subplans` 下 `plan-f` 字母位重复」——**不成立**。
实测 `P2-subplans/` 为 a–g 七个唯一字母位（`services-logs` 为 `-plan-g`），
无重复。此项不得据以改动。

### 2.3 计划文档实施状态（147 篇逐篇核对）

| 状态 | 篇数 | 篇目 |
|---|---|---|
| ❌ 未实施 | 2 | `dap-support-plan.md`（`yate/editor_dap*` 实测 0 文件、`config.py` 无 `debug_options`、`diagnostics.py` 无 `dap` 节）；`highlight-comment-flicker-plan.md` |
| 🟡 部分实施 | 4 | `win-keybinding-protocol-plan.md`（keyproto 落地 5/7，`kitty.py`/`negotiate.py`/`--key-protocol`/`:keys`/探针未落地）；`wt-keybinding-fix-plan.md`（SP1–SP3 已执行，后续被 steps-plan-g 取代）；`keybinding-fix-wt/overview.md`（SP5 真机矩阵人工遗留）；`keybinding-fix-wt-gates-matrix-plan-e.md` |
| ↩️ 已被取代 | 5 | `remove-type-checking-refactor.md`、`split-app-protocol-plan.md`、`logs-impl-plan.md`、`unify-crash-tracing-plan.md`（后两者归属迁至 `yate/logs.py`）、`keybinding-fix-wt-key-reachability-plan-f.md` |
| 📌 指针化 | 1 | `theme-ownership-plan.md`（明示"本文件不再维护"） |
| ✅ 已实施 | 135 | 其余全部，产物存在性与文档自述一致 |

**状态头滞后 2 篇**（自述与产物矛盾，方向为低报）：

- `input-assist-plan.md:5` 仍写"待用户批准（尚未写任何产品代码）"，
  但 `yate/editor_core/indentation.py`、`tests/test_input_assist.py`、
  手册 §3.5 均已落地；
- `code-review-fix-suggestions-plan-b.md:5` 仍写"本文档仅为计划，未实施"，
  同文 `:15-19` 已记"全部实施完成…清零"，自相矛盾。

### 2.4 权威文档内容偏离（子代理实证，逐条带 `文件:行号`）

**根文档**：`README.md` / `README.zh.md` 共 8 类偏离——扩展自动加载漏
`:trust` 前置（`README.md:176` / `README.zh.md:198`）、冒烟标签清单与
`tools/smoke_test/harness.py:87-99` 合法标签几乎不匹配（`README.md:336-337`）、
覆盖率阈值（`:344`）、`--report` 实为 HTML（`:366`）、依赖漏 `pyperclip`
（`:52`）、结构树漏 `keyproto/`+`editor_sprites/`（`:217-253`）、Usage 缺
`--diff/--2way/--3way/--readonly/--version`（`:74-90`）、en/zh 不同步
（`README.zh.md:382-383` 独有段落）。

**`yate/docs`** 5 组偏离：`yaterc.*` "九个选项"与代码 15 个不符且漏
`show_hidden`/`key_protocol`、`_make_buffer`/`_apply_buffer_options` 符号
不存在、`logs.py:568` 日志名带 `-<pid>`；`themes.*` 方式 A 注入 `Theme`
与 `config.py:267-271` 不符；`lsp.*` 漏 venv scripts 目录一步发现
（`extensions/python_lsp.py:86-94`）；`extensions.*` 加载顺序编号与
`services/extensions.py:615-637` 实际顺序不符。

**`.trae/wikis`**：`yate-architecture.md` 架构用例写 20（实为 22）、
测试文件写 47（实为 58）、`CompletionController`（实为 `CompletionFlows`）、
`_load_app_css()`（实为 `paths.load_tcss`）、`load_startup_services` 不存在、
漏 `editor_view/diffview.py`、事件流顺序缺 prompt 短路；
`textual-framework-hooks.md` 6 处 `app.py` 行号全部失效、
`manual.py` CSS 变量实为 `resources/markdown-doc-screen.tcss`。

**`.trae/reviews/README.md`**：漏登记 2 篇（`2026-10-03-pr51-path-space-ai-review.md`、
`2026-10-03-wiki-translate-progress.md`）；速览 #1 与总表 2026-09-16 行
声称 ctrl+digit 已由 Phase B 覆盖并标 ✅，但源文档
`2026-09-16-full-review.md:274-276` 仍为 `- [ ]` + ⏸ 暂缓且全文无
`2026-10-01`/`PB6`；速览 #24「5 WARNING / 9 SUGGESTION」口径混用
（源文档 `:12` 原文为"计划核对阶段 G1–G5" + "若干 SUGGESTION"）；
总表 `2026-10-04` 行「最终 24 提交 / 61 文件」为索引独家数字，源文档零命中。

**`CHANGELOG.md` / `CHANGELOG.zh.md`**：无偏离 ✅（版本 `0.2.8` 与
`yate/__init__.py:15` 一致，11 个版本段对齐，随包副本一致）。

### 2.5 范围外发现（登记不改）

`architecture-boundaries.md` 三处偏离：R4 与 §六 UI-free 守卫面漏列
`editor_core`（`tests/test_architecture.py:102-108` 已纳入）、三处
`test_architecture.py:88` 行号应为 `:102`、§五自检清单「除 `PaneRegistry`」
应为「除 4 类冻结白名单」。**属 rules 文件，本轮不动**，登记备查。

---

## 三、备选方案与否决理由

| 方案 | 结论 | 否决理由 |
|---|---|---|
| A. 全量逐篇人工精读 207 篇 | 否决 | 单轮上下文无法承载；且 135 篇已实施计划无内容偏离，人工精读性价比极低 |
| B. **机械体检 + 分层深度核对**（选中） | 采纳 | 机械项（命名/链接/绝对路径/状态标注）用脚本确定性处理；语义偏离只对 12 篇用户可见文档做深审；子代理 3 个并行 |
| C. 派 6 个子代理各管 1/6 文档 | 否决 | 状态判定需读产品代码，交叉重叠必然产生冲突；且 `subagent-workflow` §五.5 批大小实践为 2~3 |
| D. 只标注未实施计划，不修链接/命名 | 否决 | 用户明确要求"修正偏离不符合的地方"，`doc-conventions` 是本仓文档的成文规范 |
| E. 扁平化合并 P1+P2 子计划为一个目录 | 否决 | 14 篇字母位会冲突（两套 a–g），重排字母会破坏可追溯性；改为 `code-review-fix-p1-plans/` + `code-review-fix-p2-plans/` 两个合规目录 |

---

## 四、分步实施计划

文件独占原则：每一步只改自己名下文件，跨组引用由主代理统一收口。

### Step 1 — 语义偏离修正（3 个子代理并行，wave-1）

唯一规范来源：本方案 §2.4；核对基准为 worktree 内实际代码。
**只改各自名下文件，不得改 `yate/` 产品源码，不得改其它文档。**

| 成员 | 独占文件清单 | 任务 |
|---|---|---|
| A | `README.md`、`README.zh.md`、`CHANGELOG.md`、`CHANGELOG.zh.md` | 按 §2.4「根文档」8 类偏离逐条修正；CHANGELOG 仅核验不修 |
| B | `yate/docs/{yaterc,themes,lsp,extensions}.{en,zh}.md` | 按 §2.4「`yate/docs`」5 组偏离逐条修正，**en/zh 必须同步成对修改** |
| C | `.trae/wikis/yate-architecture.md`、`.trae/wikis/textual-framework-hooks.md` | 按 §2.4「`.trae/wikis`」逐条修正；行号须实测复核 |

验收：`.venv\Scripts\python.exe tools\_probe_docs.py` 中该组文件不再出现
失效链接与绝对路径；en/zh 仍成对。

### Step 2 — 机械合规（主代理，脚本驱动，wave-2）

1. **改名**（`git mv`）：`P1-subplans/` → `code-review-fix-p1-plans/`、
   `P2-subplans/` → `code-review-fix-p2-plans/`、
   `keybinding-fix-wt/` → `keybinding-fix-wt-plans/`、
   `issue_reply_IKH1RA.md` → `keybinding-fix-wt-issue-reply.md`、
   `fix-folder-deletion-does-not-notify-LSP-plan.md` →
   `fix-folder-deletion-lsp-notify-plan.md`；同步修全部入链。
2. **相对链接**：22 文件。按"能解析则改写为文档相对路径、
   目标已删除则降级为行内代码"两条规则批处理。
3. **绝对路径脱敏**：51 文件。仅脱敏真实机器路径
   （`D:\Programming\yate*`、`E:\Jermaine\*`、`C:\Users\i77\*`）；
   **保留**已脱敏占位示例（`C:\Users\xxx`、`C:\...`、`C:\my`、`D:\tmp\...`）。
4. **`tests/test_keyproto.py:116`** 注释中的真实 worktree 路径 → 仓库相对表述。

### Step 3 — 状态标注体系（主代理，脚本驱动，wave-3）

1. 147 篇计划文档统一在 H1 之后注入幂等状态块
   `> **实施状态**：<符号> <状态>（2026-10-05 全量核对：<依据>）`；
   非「已实施」者加 ⚠️ 说明缺口。
2. 新建 `.trae/documents/overview.md`：147 篇状态索引 + 未实施/部分实施
   专题清单 + 命名规范摘要。
   **偏离记录（实测裁定）**：初稿命名为 `README.md`，但 `tools/pack/wiki.py`
   的 `_collect_trae_dir` 把每个 `.trae` 子目录下的 `*.md` 映射到
   `<name>.zh.md` 根目标，`_assert_unique` 会在出现第二个 depth-1
   `README.md` 时抛 `wiki target collision`——`.trae/reviews/README.md` 已占用
   该目标（实测 `tests/test_pack_wiki.py::test_keyboard_interrupt_maps_to_exit_130`
   失败，移走即通过）。**不为此改产品代码**，改用本仓库既有的
   `doc-conventions` §一「子计划目录总纲 `overview.md`」命名，既消除冲突又
   符合成文规范。

### Step 4 — reviews 索引修正（主代理，wave-4）

按 §2.4「`.trae/reviews/README.md`」：补登记 2 篇、修正速览 #1 与总表
2026-09-16 行的 ✅ 表述（回填源文档而非改索引）、统一 #24 严重度口径、
删除或标注索引独家数字。

### Step 5 — 门禁与收尾（主代理，wave-5）

- `.venv\Scripts\python.exe -m pyright yate/ tests/ tools/`
- `.venv\Scripts\python.exe -m pytest tests/ -q`
- `.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q`
- 复跑探针确认 4 类违规归零（双语配对除外，本就合规）
- 落盘评审记录 `.trae/reviews/2026-10-05-doc-review-sweep.md`
- 删除一次性探针 `tools/_probe_docs.py` 与临时输出 `.probe-out.txt`
- 按 `git-commit-message.md` 分步提交（只提交不推送）

---

## 五、风险清单与回滚路径

| 风险 | 等级 | 缓解 | 回滚 |
|---|---|---|---|
| 改名断掉外部入链 | 低 | 已实测入链为 0；改名前后各跑一次探针对比 | `git mv` 反向 |
| 147 篇状态块注入误伤正文 | 中 | 幂等标记 + 只在 H1 后插入 + 抽检 10 篇 | 单文件 `git checkout` |
| 失效链接批量降级为行内代码丢失可导航性 | 中 | 规则是"目标存在才改写、不存在才降级"，存在的不降级 | 探针复跑核对残留 |
| en/zh 双语改单边 | 中 | 成员 B 独占 8 篇并在验收时校验配对 | 探针配对检查 |
| 探针正则误伤 URL | 低 | 已修正为 `(?<![\w:/])` 负向断言，实测不再误报 | 已验证 |

---

## 六、执行结果回填（2026-10-05 实测）

### 6.1 各步产出

| 步 | 状态 | 实测产出 |
|---|---|---|
| Step 1 语义偏离（3 子代理并行） | ✅ 完成 | 12 文件：`README.md` / `README.zh.md`（8 类 + 1 处真实路径）、`yate/docs/` 8 篇（8 类）、`.trae/wikis/` 2 篇（12 类）。三名词下文件互不重叠，无越界 |
| Step 2 机械合规（主代理脚本） | ✅ 完成 | 命名 26→0；相对链接修复约 290 处（22→6 文件，残留为真正失效目标）；真实机器路径 51→0（41 文件脱敏）；`yaterc.example` 补 2 选项 + 日志名 |
| Step 3 状态标注（主代理脚本） | ✅ 完成 | 147 篇注入幂等状态块（连跑 3 次验证 0 变更）；`overview.md` 索引（147 行清单 + 未实施/部分实施/已被取代专题） |
| Step 4 reviews 索引 | ✅ 完成 | 补登记 2 篇 + 新增本轮 1 篇；回填源文档 ctrl+digit 销账；修正 #24 严重度口径；删除索引独家不可核实数字；计数 27→28 条 |
| Step 5 门禁与收尾 | ✅ 完成 | 见 §六.2 |

### 6.2 门禁实测（主代理亲自跑，worktree `.venv`）

| 命令 | 退出码 | 结果 |
|---|---|---|
| `python -m pyright yate/ tests/ tools/` | **0** | `0 errors, 0 warnings, 0 informations` |
| `python -m pytest tests/ -q` | **0** | **1818 tests / 0 failures / 0 errors / 8 skipped** |
| `python -m pytest tests/test_architecture.py -q` | **0** | **22 passed / 0 failures** |
| `python -m pytest tests/ -q --cov=yate --cov-fail-under=75` | **0** | 覆盖率 **91.27%** ≥ 75% |

### 6.3 偏离计划记录（附实测依据）

1. **索引文件名由 `README.md` 改为 `overview.md`**（Step 3）。
   依据：`tools/pack/wiki.py` 的 `_collect_trae_dir` 把每个 `.trae` 子目录下的
   `*.md` 映射到 `<name>.zh.md` 根目标，`_assert_unique` 遇第二个 depth-1
   `README.md` 即抛 `wiki target collision`——`.trae/reviews/README.md` 已占用该
   目标。实测 `tests/test_pack_wiki.py::test_keyboard_interrupt_maps_to_exit_130`
   失败、移走即通过。**不为此改产品代码**，改用 `doc-conventions` §一
   「子计划目录总纲 `overview.md`」的既有命名。
2. **`keybinding-fix-wt/issue_reply_IKH1RA.md` 定名 `…-issue-reply-plan-h.md`**（Step 2）。
   依据：规范无"非计划类附件"形态，字母位续排在 plan-h 以保持 §一 形态合规。
3. **worktree `.venv` 补装依赖**（Step 5 前置）。
   依据：复用既有 worktree 时其 `.venv` 缺 `textual` / `rich` 且未装 yate 本体，
   子代理实测 pytest 直接 `ModuleNotFoundError` 退出码 4；按
   `task-orchestration` §二.1 补装 `-e ".[dev]"`。
4. **失效链接不做专项清扫**（Step 2）。
   依据：`doc-conventions` §五明文"存量文档随下次修改逐步迁移，不做专项清扫"；
   残留 6 文件 24 处已登记为待办。
5. **子代理"plan-f 字母位重复"结论未被采纳**。
   依据：实测 `code-review-fix-p2-plans/` 为 a–g 七个唯一字母位，误报。
6. **不推送**：闭环流程内禁止 `git push`。

### 6.4 子代理存活与产出（`subagent-workflow` §五.7 如实报告）

3 名成员全部存活、全部有落盘产出、均未越界：

| 成员 | 独占文件 | 产出 | 越界 |
|---|---|---|---|
| `fix-readme` | 4（README×2 改，CHANGELOG×2 只核验） | ✅ 8 类 + 1 处真实路径 | 无 |
| `fix-docs` | 8（`yate/docs/**`） | ✅ 8 类 | 无 |
| `fix-wikis` | 2（`.trae/wikis/**`） | ✅ 12 类 | 无 |

**成员上报的两项范围外发现由主代理裁定并处置**：`yate/resources/manual.*.md`
的 Python LSP 发现顺序未同步、`yate/yaterc.example` 未覆盖两个新选项——
两项均属实且属同一偏离族，已在主代理侧一并修正。
`fix-wikis` 正确地否决了任务书中两个不准确的佐证行号
（`extension_flows.py:60`→`:49`、`cli.py:380`→`:379-380`）与一条错误佐证
（`UI_FROZEN_FILES` 与 `diffview.py` 无关），并按实测写入——**未照抄任务书**。

---

## 七、边界条款触发汇总

- **R6/§五**：本任务零产品代码改动，`tests/test_keyproto.py` 仅改注释，
  仍需跑 pyright + pytest 确认零诊断。
- **`doc-conventions` §五**：相对路径与真实路径脱敏是本任务核心约束之一，
  改完后必须以探针复跑为准，不以"已改"自述为准。
- **`doc-conventions` §二.1**：评审记录落盘命名 `YYYY-MM-DD-<topic>.md`。
- **`task-orchestration` §二**：每步产物单独提交，禁止 `git push`。
