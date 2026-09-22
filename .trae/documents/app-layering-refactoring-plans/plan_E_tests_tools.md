# Plan E — 测试与冒烟脚本迁移

> 状态：🔄 **执行中**（2026-09-22，5 个子任务并行）· 前置：[Plan D](plan_D_shell_wiring.md) · 后置：[Plan F](plan_F_gate_docs.md)
> 门禁：`python -m pytest tests/ -q` 全绿 · `python -m pyright tests/ tools/` 0 诊断
> 子任务划分见 §E.2，落地记录见 §E.5。

---

## E.0 背景

Plan D 之后 `YateApp` 不再持有业务状态，测试与冒烟脚本里所有 `app.<业务属性>` 都要改走
`app.editor.*`。这是**机械替换**（属性路径搬家），除少数构造点需要语义改写外不改断言语义。

## E.1 属性映射表（唯一权威）

### 会话（L1）

| 旧 | 新 |
|---|---|
| `app.doc` | `app.editor.session.doc` |
| `app.buffer` | `app.editor.session.buffer` |
| `app.docs` | `app.editor.session.docs` |
| `app.doc_index` | `app.editor.session.index` |
| `app.search` | `app.editor.session.search` |
| `app.welcome_visible` | `app.editor.session.welcome_visible` |
| `app.close_documents_under(p)` | `app.editor.session.close_under(p)` |
| `app.activate_doc(doc)` | `app.editor.activate_doc(doc)` |
| `app.new_buffer()` | `app.editor.new_buffer()` |

### 服务 / 注册表（L0）

| 旧 | 新 |
|---|---|
| `app.workspace` | `app.editor.workspace` |
| `app.lsp` | `app.editor.lsp` |
| `app.config` | `app.editor.config` |
| `app.extension_loader` / `app.extension_api` | `app.editor.extension_loader` / `app.editor.extension_api` |
| `app.actions` / `app.commands` | `app.editor.actions` / `app.editor.commands` |
| `app.keymaps`（dict） | `app.editor.keymaps`（`KeymapSet`，取单个用 `.get(name)`） |
| `app.keymap_name` | `app.editor.keymaps.name` |
| `app.active_keymap` | `app.editor.keymaps.active` |
| `app.select_keymap(n)` | `app.editor.select_keymap(n)` |

### 组件（L2）

| 旧 | 新 |
|---|---|
| `app.prompt_bar` | `app.editor.prompt_bar` |
| `app.explorer_tree` | `app.editor.explorer_tree` |
| `app.panes` | `app.editor.panes` |
| `app.terminal_panel` | `app.editor.terminal_panel` |
| `app.status_bar` | `app.editor.status_bar` |
| `app.completion_popup` | `app.editor.completion_popup` |
| `app.tabbar` / `app.breadcrumbs` / `app.sidebar` | `app.editor.tabbar` / `app.editor.breadcrumbs` / `app.editor.sidebar` |
| `app.sidebar_head` | `app.editor.sidebar_head`（`Static`，文本用 `editor_view.chrome.sidebar_head_text()` 构造） |
| `app.editor_view` | `app.editor.panes.active_view`（`PaneManager.active_view`，`Optional[EditorView]`） |
| `app.pane_host` | `app.editor.pane_host` |
| `app.key_ui` | `app.editor.key_ui`（`KeyUi` 记录；旧测试若构造 `ActionContext(session, ui)` 需按其字段补齐：`execute_action` / `message` / `command_prompt` / `find_prompt` / `goto_prompt` / `toggle_keymap`） |
| `app._terminal_factory` | `app.editor.terminal_panel.view_factory` |
| `app.build_tabbar(w)` | `app.editor.tabbar.build(w)` |
| `app.render_breadcrumbs(w)` | `app.editor.breadcrumbs.build(w)` |

### 操作（L3）

| 旧 | 新 |
|---|---|
| `app.ui_refresh()` | `app.editor.refresh_ui()` |
| `app.message(...)` | `app.editor.message(...)` |
| `app.run_command(t)` | `app.editor.run_command(t)` |
| `app.insert_char(c)` | `app.editor.insert_char(c)` |
| `app.open_path(p)` | `app.editor.open_path(p)` |
| `app.execute_action(n)` | `app.editor.execute_action(n)` |
| `app.mode_label()` | `app.editor.mode_label()` |
| `app.set_theme(n)` / `app.goto_prompt()` / `app.open_command_palette()` / `app.open_file_palette()` / `app.show_manual()` / `app.show_changelog()` / `app.prompt_completions()` / `app.load_startup_services()` / `app.quit()` | `app.editor.<同名>` |
| `app.explorer_visible` / `app.window_pending` | `app.editor.explorer_visible` / `app.editor.window_pending`（**属性，不加括号**：`yate/editor.py` 的 `@property`） |
| `app.has_modal_screen()` | `app.editor.has_modal_screen()` |

> 上表路径已在 `yate/editor.py` 中逐条核对（2026-09-22）：`session` / `workspace` / `lsp` / `config` /
> `keymaps` / `actions` / `commands` / `completion` / `completion_popup` / `panes` / `pane_host` / `prompt_bar` /
> `explorer_tree` / `terminal_panel` / `status_bar` / `tabbar` / `breadcrumbs` / `sidebar` / `sidebar_head` /
> `key_ui` / `explorer_visible` / `_ext_messages` 均为 `Editor` 上的真实成员。

### 消失的东西

| 旧 | 处理 |
|---|---|
| `app.explorer_feature` / `app.terminal_feature` / `app.docs_feature` | 删除：能力已归 `ExplorerTree` / `TerminalPanel` / `Editor` |
| `app.completion_ctl` | `app.editor.completion` |
| `app.focus_target` | 删除（无消费者） |
| `app._ext_messages` | `app.editor._ext_messages`（尽量改用公开行为断言） |

### **不要动**（Textual 原生）

`run_test` / `screen` / `screen_stack` / `focused` / `is_running` / `return_code` /
`run_worker` / `query_one` / `save_screenshot` / `pushed` / `exit` / `theme`（指 Textual 主题时）。

---

## E.2 子任务划分（可并行）

| 子任务 | 文件 | 重点 |
|---|---|---|
| **E1** | `tests/test_app_textual.py` | 体量最大（`app.buffer` 124 处、`app.doc` 112 处、`app.run_command` 65 处）。按 E.1 表机械替换；`patch("yate.app.run_shell")` 改为 `patch("yate.editor.run_shell")`；`app.docs_feature` / `app.terminal_feature` 相关用例改为直接驱动 `app.editor.terminal_panel` / `Editor._open_doc` |
| **E2** | `tests/test_explorer.py`、`tests/test_changelog_view.py`、`tests/test_diagnostics.py` | `test_explorer.py` 不再 import `app_features`，改用 `EditorSession.close_under` + `ExplorerTree` 自带的创建/重命名/删除提示流（构造注入 fake `PromptBar` / `EditorSession`）；`test_changelog_view.py` 的 `DocsFeature` 用例改为 `Editor.push_overlay` / `_open_doc`；`test_diagnostics.py` 改为构造 `Editor` 或 `app.editor` |
| **E3** | `tests/test_cli.py`、`tests/test_config.py`、`tests/test_panes.py`、`tests/test_editor_core.py`、`tests/test_extensions.py`、`tests/test_highlight.py` | 构造点同步：`ExtensionAPI(ExtensionContext(...))`、`PaneManager(session, doc, is_mounted=..., after_pane_focus=..., focus_explorer=...)`、`populate(registry, editor)`、`ActionContext(session, KeyUi(...))`、`YateApp` 替身补 `.editor`。**注**：`test_terminal.py` 只测 `editor_term` 的 PTY，无需迁移（原表误列） |
| **E4** | `tools/smoke_test/**` | 按 E.1 表替换（`app.doc` → `app.editor.session.doc` 等）；`YateApp.execute_action` 的猴子补丁改为 `Editor.execute_action`；`app.mode_label()` → `app.editor.mode_label()` |
| **E5** | `tests/test_architecture.py` | 见 E.3 规则更新 |

> 并行前提：E1–E4 改的是互不相交的文件，可同时开工；E5 独立。
> 每个子任务完成后单独跑 `python -m pytest <自己的文件> -q`。
> **本轮并行执行**（team `layering-plan-e`）：E1 `e1-app-textual`、E2 `e2-explorer-docs`、
> E3 `e3-unit-tests`、E4 `e4-smoke-tools`、E5 `e5-architecture`。

## E.3 架构守护规则更新（`tests/test_architecture.py`）

| 旧规则 | 新规则 |
|---|---|
| `test_features_import_only_allowed_view_modules`（针对 `app_features`） | **删除**（目录已不存在），替换为：`editor_view/*` 不得 import `yate.editor` / `yate.app`（R3） |
| — | 新增：`yate/editor.py` 不得 import `yate.actions` / `yate.commands`（R5，防导入环回归） |
| — | 新增：源码中不得出现 `*Feature` / `*Ops` / `*Delegate` / `AppProtocol` 命名；`*Host` 仅白名单 `PaneHost`（Textual 容器 widget）。该守卫**不带 R 编号**（R7 是"外壳装载内置表"，目前无自动守护） |
| `test_only_cli_imports_app`（R1） | 保留 |
| `test_keymaps_services_and_models_stay_ui_free`（R4） | 保留（**已改名**，原 `test_keymaps_and_services_stay_ui_free`），并把 `session.py` / `registries.py` 纳入同一检查 |
| `test_no_type_checking`（R6） | 保留 |
| `test_collaborators_keep_widget_coupling_frozen` | 按 **R11** 标注（原文误标 R4；R4 由上面的 UI-free 用例守护） |

## E.4 完成检查

- [ ] `python -m pytest tests/ -q` 全绿
- [ ] `python -m pyright tests/ tools/` 0 诊断
- [ ] `grep -rn "app_features" tests/ tools/` 为空
- [ ] `grep -rn "\.explorer_feature\|\.terminal_feature\|\.docs_feature" tests/ tools/` 为空

> 2026-09-23 实测：`pytest tests/ -q` 在**收集阶段**被 `test_explorer.py` / `test_changelog_view.py`
> 中断（`ModuleNotFoundError: yate.app_features.*`），`test_editor_core.py` 的 `SessionOps` 导入亦未修复；
> 逐文件待办见 §E.6 末尾。

---

## E.5 实施记录

| 子任务 | 文件 | 结果（2026-09-23 审计实测） |
|---|---|---|
| **E5** | `tests/test_architecture.py` | ✅ 重写为 **11 个用例**：`python -m pytest tests/test_architecture.py -q` → **11 passed**。删除旧的 `test_features_import_only_allowed_view_modules` 与 `ALLOWED_FEATURE_VIEW_IMPORTS`；新增 helper `_yate_files()` / `_imports_upward()` / `_protocol_classes()` / `_identifiers()`；规则映射见 §E.3 与 [rules §六](../../rules/architecture-boundaries.md) |
| E1 | `tests/test_app_textual.py` | ⏳ **未开始**：`app.editor.` 命中 0 处，旧属性路径约 250 处 |
| E2 | `tests/test_explorer.py` / `test_changelog_view.py` / `test_diagnostics.py` | ⏳ **未开始**：前两者仍在**收集阶段** `ModuleNotFoundError: yate.app_features.*`；`test_diagnostics.py` 仍走 `YateApp` + `app.load_startup_services()` |
| E3 | `tests/test_cli.py` / `test_config.py` / `test_panes.py` / `test_editor_core.py` / `test_extensions.py` / `test_highlight.py` | ⏳ **未开始**：`test_editor_core.py` 仍 `from yate.actions import SessionOps`（已删 → 收集期 `ImportError`）；`test_panes.py` 旧 `PaneManager` 签名；`test_config.py` 仍用 `app.keymap_name` |
| E4 | `tools/smoke_test/**` | 🔄 **部分完成**：`harness.py` / `_base.py` / `aliases.py` / `core.py` / `edit.py` 已迁移；其余 8 个场景（`explorer` `files` `integration` `panes` `regression` `search` `stress` `view`）仍走 `app.<业务属性>` |

### E.5.1 E5 阶段的两项裁决（已同步到 README 与规则文档）

1. **Protocol 白名单冻结为 4 个类**：`PaneRegistry`（本轮唯一新增）、`SyntaxBackend`、
   `editor_syntax/ts_backend/backend.py::_TsPoint` / `_TsNode`（后者为可选依赖 py-tree-sitter 的私有
   结构化类型，先于本轮存在）。不为"只留 2 个"去改动叶包源码。
2. **`completion.py` / `prompt_completion.py` 采用"冻结 UI 耦合"**：两者允许 import `editor_view`
   （L3 流程模块天然驱动 L2 组件），但禁止向上 import `yate.editor` / `yate.app`，且新增 `editor_view`
   导入必须登记；已固化为 R11。
   （未来可选清理：把 `theme` 的纯计算工具下沉到叶子模块，让 `prompt_completion.py` 彻底无 UI —— 非本轮目标。）

> 收尾时补录 E1–E4：每个文件最终的迁移方式、`python -m pytest <file> -q` 结果、剩余失败项与原因
> （迁移前的完整待办见 §E.6）。
> 迁移完成后，本 Plan 状态改为 ✅，并把总纲 §1.1 / §5 与 [Plan F](plan_F_gate_docs.md) 的前置同步更新。

---

## E.6 逐文件待迁移清单（2026-09-23 审计实测）

> 由子代理对 `tests/` + `tools/` 全量 grep 得出；**行号会漂移**，以"当前引用形态 → 目标写法"为准。

### E.6.1 `tests/`

| 文件 | 现状 | 目标 |
|---|---|---|
| `test_explorer.py` | `import yate.app_features.explorer`；`YateApp.close_documents_under` / `app.docs` / `app.doc_index` / `app.lsp` | 改测 `ExplorerTree.prompt_delete` / `submit_delete`（注入 fake `PromptBar` / `EditorSession`）；`session.close_under` / `session.docs` / `session.index` / `editor.lsp` |
| `test_changelog_view.py` | `app_features.commands.CommandRegistry`、`app_features.docs.DocsFeature`、`app.docs_feature`、`register_commands(StubApp())` | `yate.registries.CommandRegistry`；`Editor.show_changelog` / `show_manual`（`_open_doc` + `push_overlay`）；`register_commands(registry, editor)` |
| `test_editor_core.py` | `from yate.actions import ActionRegistry, SessionOps, populate`；`ActionContext(cast(Any, app))` | `populate(registry, editor)`；`ActionContext(session, KeyUi(...))`（`SessionOps` 已删除） |
| `test_app_textual.py` | ≈250 处旧路径：`app.doc/buffer/docs/doc_index/search/lsp/panes/workspace/prompt_bar/explorer_tree/status_bar/editor_view`、`terminal_feature`、`_terminal_factory`、`keymap_name`、`active_keymap`、`ui_refresh()`、`build_tabbar` / `render_breadcrumbs`、`welcome_visible`；`PaletteScreen(app, "commands")`；`patch("yate.app.run_shell")` | 按 §E.1 统一加 `.editor`；`app.editor.panes.active_view`；`app.editor.terminal_panel.view_factory`；`app.editor.keymaps.name` / `.active`；`refresh_ui()`；`app.editor.tabbar.build(w)` / `breadcrumbs.build(w)`；`PaletteScreen("commands", workspace=..., commands=..., actions=..., open_path=..., focus_editor=..., execute_action=..., run_command=..., refresh=...)`；`patch("yate.editor.run_shell")` |
| `test_panes.py` | `PaneManager(app, doc1)`、`FakeApp(docs/doc_index)`、`ui_refresh()` | `PaneManager(session, doc, is_mounted=..., after_pane_focus=..., focus_explorer=...)`；`EditorSession`；`session.index`；`refresh_ui()` |
| `test_diagnostics.py` | `app.load_startup_services()` / `app.lsp` / `format_report(app)` | `app.editor.*`；`diagnostics.format_report(app.editor)` |
| `test_config.py` | `app.keymap_name` / `app.buffer` / `app.new_buffer(show=False)` | `app.editor.keymaps.name` / `app.editor.session.buffer` / `app.editor.new_buffer(show=False)` |
| `test_extensions.py`、`test_highlight.py` | `ExtensionAPI(cast(Any, _FakeApp()))`（靠 duck typing 暂不报错） | `ExtensionAPI(ExtensionContext(...))` |
| `test_cli.py` | `FakeApp` 无 `.editor`，而 `cli.py` 已走 `app.editor` | `FakeApp` 补 `editor`（或换轻量真 `Editor` 替身） |

### E.6.2 `tools/smoke_test/scenarios/`

| 状态 | 文件 |
|---|---|
| ✅ 已迁移 | `harness.py`、`_base.py`、`aliases.py`、`core.py`、`edit.py` |
| ⏳ 待迁移（8） | `explorer.py`、`files.py`、`integration.py`、`panes.py`、`regression.py`、`search.py`、`stress.py`、`view.py` —— 统一 `app.<业务属性>` → `app.editor.*`；`app.editor_view` → `app.editor.panes.active_view`；`build_tabbar` → `app.editor.tabbar.build`；`app.editor.window_pending` 是**属性**（不加括号） |

### E.6.3 当前 pytest 状态（迁移完成前）

- **收集中断（2）**：`test_explorer.py`、`test_changelog_view.py` —— `pytest` 直接 `Interrupted: 2 errors during collection`，其余用例不会执行。
- **运行期失败**：`test_editor_core.py`（`ImportError: SessionOps`）、`test_app_textual.py` / `test_panes.py` / `test_diagnostics.py` / `test_config.py`（`AttributeError`，旧属性路径）。
