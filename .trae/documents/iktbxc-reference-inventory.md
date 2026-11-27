# IKTBXC 引用面清单（仅事实，无设计）

由只读 `code-explorer` 对 worktree `yate-naming-hygiene`（master `3e92532`）扫描收集，另加协调者抽查。用作方案设计者的唯一事实输入。无分析、无提议设计。

## A. 含各旧路径字符串的行数

| 旧路径字符串 | yate 代码 | 测试 | 工具 | 规则 | wiki | 评审 | 文档 | README | tcss | 合计 |
|---|---|---|---|---|---|---|---|---|---|---|
| `keyproto.legacy` / `keyproto/legacy` / `legacy.py` | 6 | 3 | 0 | 1 | 3 | 4 | 101 | 0 | 0 | 118 |
| `editor_components.editor` / `editor_components/editor` | 14 | 9 | 1 | 2 | 0 | 1 | 8 | 0 | 1 | 36 |
| `flows.cmdline_completions` / `flows/cmdline_completions` / 裸 `cmdline_completions` | 6 | 11 | 1 | 6 | 3 | 0 | 62 | 2 | 0 | 91 |

- 裸 import 形式 `from yate.editor_components import editor`、`from yate.keyproto import legacy`、`from yate.flows import cmdline_completions` 出现 **0 次**。
- `CHANGELOG*.md`、`yate/resources/changelog.*.md`、`tools/changelog/zh_overrides.json`：**0** 处旧路径命中。
- `.trae/documents/**` 历史计划：101 + 8 + 62 = 171 行。issue §六 明确将其豁免于残余 grep。
- 依据 `doc-conventions.md` §2.1，`.trae/reviews/**` 是只读事实记录。
- `pack/`（7 个文件，含两个 `.spec`）、`pyproject.toml`、`yate/` + `tools/` 下所有 `*.json`、所有 `*.scm`、所有 `yate/docs/**`、`yate/resources/manual*.md`：**0** 处旧路径命中。

## B. 旧路径 1 —— `yate.keyproto.legacy`

产品代码（6）：`yate/app.py:30`、`yate/editor_dispatch.py:23`、`yate/editor_dispatch.py:123`（注释）、`yate/editor_term/keys.py:4`（docstring）、`yate/editor_term/keys.py:12`、`yate/keyproto/__init__.py:13`。
测试（3）：`tests/test_app_textual.py:23`、`tests/test_term_keys.py:12`、`tests/test_keyproto.py:30`。
规则文本（1）：`.trae/rules/architecture-boundaries.md:47`。
Wiki（3）：`.trae/wikis/yate-architecture.md:156`、`:184`、`:194`（Mermaid participant）。
评审（4）/ 历史计划（101）：豁免回改。

`yate/keyproto/legacy.py:1-7` 的 docstring 字面以 "Legacy key codec: translation from Textual key names to the raw byte sequences..." 开头，并继续 "Formerly ``yate.editor_components.keys``; moved into the L0 leaf package..."。
该模块仅 import `from yate.keymaps.keys import SPECIAL_KEYS`（`:11`）。
`yate/keyproto/` 中不存在 `key_codec.py`（目录：`__init__.py`、`aliases.py`、`chords.py`、`driver_windows.py`、`frames.py`、`legacy.py`、`textual_internals.py`）。

## C. 旧路径 2 —— `yate.editor_components.editor`

产品代码（14）：`yate/editor.py:61`、`yate/editor_dispatch.py:19`、`yate/session.py:272`（注释）、`yate/editor_components/__init__.py:5` 与 `:26`、`yate/editor_components/welcome.py:3`、`highlighting.py:3`、`panes.py:24` 与 `:40`、`terminal.py:40`、`completion.py:4`、`yate/flows/mouse_flows.py:3` 与 `:19`、`yate/flows/completion_flows.py:24`。
样式资源（1）：`yate/resources/editor-view.tcss:2`（CSS 注释）。
测试（9）：`tests/test_app_mouse.py:22`、`test_app_panes.py:16`、`test_dispatch_guards.py:19`、`test_panes.py:26`、`test_support_mouse.py:31`、`tests/test_architecture.py:130`（`ALLOWED_PROTOCOLS` **键**）、`:213` 与 `:225`（`UI_FROZEN_FILES` **允许集值**，非键）、`:329`（docstring）。
工具（1）：`tools/smoke_test/scenarios/multi_cursor.py:18`。
规则（2）：`.trae/rules/architecture-boundaries.md:113`、`:347`。
评审（1）/ 历史计划（8）：豁免回改。

`yate/editor_components/editor.py` 在 `:50` 持有 `PaneRegistry(Protocol)`、在 `:74` 持有 `EditorView`；`:90` 处为 `DEFAULT_CSS = load_tcss("editor-view.tcss")`。
`yate/editor_components/` 中不存在 `view.py` / `text_view.py`（目录列举已确认）。`yate/editor_compose.py` **不含** `editor_components.editor` 引用（issue 的 "22 sites" 列表在此已过时）。

`tests/test_architecture.py` 中的守卫事实：
- `ALLOWED_PROTOCOLS:129-133` 映射 `"editor_components/editor.py": {"PaneRegistry"}`，由 `test_no_new_protocols:592-598` 经 `ALLOWED_PROTOCOLS.get(key, set())` 使用，其中 `key` 是相对 `yate/` 的路径。
- `UI_FROZEN_FILES:195-257` 有 10 个 `flows/*.py` 键；`:213` 与 `:225` 分别是 `flows/completion_flows.py` 与 `flows/mouse_flows.py` 允许集中的元素。`test_collaborators_keep_widget_coupling_frozen:827-837` 断言每个 `yate.editor_components*` import 都在该文件的允许集中。
- `SIZE_EXEMPT_FILES:357-362` 不含 `editor_components/editor.py`。
- `_python_files():480-486` 扫描 `yate/` + `tests/` + `tools/` 的 rglob `*.py`；`_yate_files():499-504` 扫描 `yate/` 的 rglob `*.py`；两者都跳过 `__pycache__`。

## D. 旧路径 3 —— `yate.flows.cmdline_completions`

产品代码（6）：`yate/editor_compose.py:33`（import）、`:129`（调用）、`yate/flows/cmdline_completions.py:17`（函数名，非路径）、`yate/config.py:12`（模块 docstring）、`:290`（`#:` 注释）、`yate/services/extensions/api.py:411`（注释）。
测试（11）：`tests/test_app_find.py:18`、`:337`、`:475`；`tests/test_cmdline_completions.py:3`、`:28`、`:72`、`:142`、`:153`；`tests/test_architecture.py:25`（模块 docstring）、`tests/test_set_options.py:45`（测试名）、`tests/test_workspace_filter.py:887`（注释）。
工具（1）：`tools/smoke_test/scenarios/guards.py:200`（docstring 路径字符串）。
根文档（2）：`README.md:272`、`README.zh.md:290` —— 两者都已在根 `yate/` 树中列出裸文件名 `cmdline_completions.py`（无 `flows/` 前缀）。
规则（6）：`.trae/rules/architecture-boundaries.md:25`、`:133`、`:139`、`:268`、`:297`、`:457`。
Wiki（3）：`.trae/wikis/yate-architecture.md:23`、`:151`、`:159`。
评审（0）/ 历史计划（62）：豁免回改。

`yate/flows/cmdline_completions.py`（53 行）恰好 import：
- `:12 from yate.registries import CommandRegistry`
- `:13 from yate.services.workspace import Workspace, path_matches`
- `:14 from yate.session import EditorSession`

层级 rank 事实（`tests/test_architecture.py`）：
- `_LAYER_RANKS:141-158` 列出 `("flows/", 3)`、`("services/extensions/", 3)`、`("editor_components/", 2)`、`("session.py", 1)`、`("registries.py", 1)`、`("keymaps/keys.py", 0)`、`("keymaps/", 1)`；未列出的路径默认取 **0**（`_layer_rank:520-525`，`:135-140` 的 docstring 写着 "anything unlisted ranks as L0, which makes a new leaf module reaching upward fail the guard"）。
- `test_no_unregistered_upward_imports:765-793` 每当 `_layer_rank(target) > source_rank` 时收集 `f"{source} -> {module}"`，然后断言 `sorted(set(offenders) - UPWARD_EDGES_FROZEN)` 为空。
- `UPWARD_EDGES_FROZEN:165` = `frozenset()`（自 2026-10-20 起为空）。
- `_ranked_target:528-538` 将 `yate.x.y` 解析为 `x/y.py` 或 `x/y/__init__.py`。

作为事实记录（非设计）：迁移后的模块若其相对 `yate/` 的路径未在 `_LAYER_RANKS` 中注册，则 rank 为 0，而 `yate.registries` / `yate.session` 为 rank 1；于是这两处既有 import 会被 `test_no_unregistered_upward_imports` 报告为未注册的向上边。当前 `flows/` 前缀使该模块 rank 为 3，因此这些 import 目前是向下的。

其他守卫事实：
- `test_flow_modules_hold_no_app_handle` 在 `:1315` 扫描 `(YATE / "flows").glob("*.py")`（外加 `yate/*.py` 顶层 AST 扫描）；`test_flow_modules...` 属能力注入配对的一部分。
- `test_source_files_within_size_threshold:896-918` 使用 `SIZE_EXEMPT_FILES` 与 `_source_files()`（yate + tools，不含测试）；没有任何豁免提及三条旧路径。
- `test_no_banned_identifier_names:869-878` 才是真名；**不存在** `test_banned_identifier_names`（issue 文本在此已过时）。
- `NON_ASCII_COMMENT_EXEMPT:388-405`、`PRINT_EXEMPT_SITES:471-475`、`SCROLLABLE_BASES:433-441` 均未引用三条旧路径中的任何一条。

## E. 包 `__init__.py` 事实

- `yate/editor_components/__init__.py`：无再导出；`:5` 与 `:26` 提及 `yate.editor_components.editor.EditorView` / import 示例。
- `yate/keyproto/__init__.py`：无再导出；`:13` 将 `:mod:yate.keyproto.legacy` 列为三种编解码器之一。
- `yate/flows/__init__.py`：仅 5 个 PEP 695 `type` 别名，无再导出，0 处 `cmdline_completions` 引用。
- `yate/services/__init__.py`：无再导出，0 处旧路径引用。

## F. 冒烟基线

`tools/smoke_test/scenarios/` 有 26 个 `.py` 文件（24 个场景模块 + `_base.py` + `__init__.py`）；`Scenario(` 计数 = **121**，与 issue 的 "121 scenarios" 吻合。仅 2 个文件引用旧路径（一处真实 import，一处 docstring）。

## G. issue 主张与仓库事实的差异

| issue 主张 | 已核实事实 |
|---|---|
| `tests/test_architecture.py:213/225` 是 `UI_FROZEN_FILES` 的**键** | 它们是**允许集值**；键位于 `:208` / `:223` |
| P0-2 有 22 处引用点（含 `editor_compose.py`） | 共 36 行；`editor_compose.py` 有 0 处此类引用 |
| P0-1 "9 处活跃引用" | 9 行产品/测试正确；`.trae` 中另有 109 行（豁免的历史文档 / 评审 / wiki / 规则） |
| P1-3 称 `yate/docs` 手册引用该路径 | `yate/docs/**` 与 `yate/resources/manual*.md` 中 0 命中 |
| `tests/test_architecture.py` 有 "flows enumeration constants" | 不存在 `FLOWS` 常量；枚举在 docstring `:24-28`、`UI_FROZEN_FILES` 键、`_LAYER_RANKS:151`、`glob:1315` 中 |
| `test_banned_identifier_names` | 实际名称：`test_no_banned_identifier_names` |
| `editor_compose.py:127-133` 的 partial 接线 | `PromptBar(` 起于 `:127`、`partial(` 在 `:128`、`cmdline_completions` 在 `:129`、调用结束于 `:137`；import 在 `:33` |
