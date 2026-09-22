# Plan D — 外壳瘦身与接线

> 状态：✅ **已完成**（2026-09-22）· 前置：[Plan A](plan_A_leaf_models.md)–[C](plan_C_functional_tables.md) · 后置：[Plan E](plan_E_tests_tools.md)
> 门禁（实际执行结果）：`python -c "import yate.app"` 成功；`python -m pyright yate/` → **0 errors, 0 warnings**；
> `python -m yate --diag` 正常输出。（测试迁移属于 Plan E。）
> 实施结果见 §D.6。

---

## D.0 背景（执行前的状态，历史记录）

1. `yate/app.py` 仍是 2005 行的"业务 + 外壳"混合体：文档 / 窗格 / 提示 / shell / LSP / 主题 /
   覆盖层 / 扩展全部堆在 `YateApp`；`TabBar` 甚至定义在 `app.py` 里并持有 `YateApp`。
2. 工作区已有 `yate/editor.py`（`Editor` 调度层）但**尚未接线**，且存在真实导入环：
   `yate/editor.py` import `yate.actions`，而 `yate/actions.py` import `yate.editor`。
   验证命令 `python -c "import yate.editor"` 当前直接 `ImportError`。
3. `yate/app_features/`（6 个文件）是当初从 `YateApp` 拆出的薄委托；现在它们的功能已分别落到
   `Editor` / `ExplorerTree` / `TerminalPanel` / `CompletionController` /
   `load_startup_extensions` / `Editor._open_doc`，目录应整体删除。

**目标**：`YateApp` 瘦到约 150 行，只做「主题桥 + CSS + 生命周期 + 事件转发 + 装载内置表」；
功能调度全部落在 `Editor` 及其协作者。改动性质 = 代码搬运 + 删除，不改行为。

---

## D.1 解环：`editor.py` 不再 import 内置表模块

| 文件 | 动作 |
|---|---|
| `yate/editor.py` | 删除 `from yate.actions import populate` 与 `from yate.commands import register_commands` 两行，并删除 `__init__` 中的 `populate(self.actions, self)` / `register_commands(self.commands, self)` 调用。保留 `from yate.registries import ActionRegistry, CommandRegistry`，`self.actions = ActionRegistry()` / `self.commands = CommandRegistry()` 仍在 `Editor.__init__` 中创建（空表） |
| `yate/app.py` | 由外壳装载：`populate(self.editor.actions, self.editor)`、`register_commands(self.editor.commands, self.editor)` |

规则：R5（表模块 → `editor.py` 单向）、R7（装载权归外壳）。

---

## D.2 `yate/app.py` 重写（本 Plan 唯一允许的大改文件）

保留（且只保留）以下成员：

| 成员 | 说明 |
|---|---|
| `ENABLE_COMMAND_PALETTE = False` | 关闭 Textual 自带命令面板 |
| `CSS` | 布局 CSS（`#body #sidebar #sidebar-head #explorer #editor-col #tabbar #breadcrumbs #bottom-dock #terminal-dock #bottom`），原样保留 |
| `__init__` | ① `self.title` ② `self.config` ③ 主题引导 ④ 构造 `Editor` ⑤ 装载内置表 |
| `editor: Editor` | 唯一的业务入口 |
| `compose()` | `yield from self.editor.compose()` |
| `on_mount()` | `await self.editor.on_mount()` |
| `on_unmount()` | `await self.editor.on_unmount()` |
| `on_key(event)` | `if self.editor.handle_key(event): event.stop(); event.prevent_default()` |
| `get_theme_variable_defaults()` | 手册 / changelog 的 CSS 变量默认值，原样保留 |
| `action_quit()` | `self.editor.quit()` |

主题引导（`__init__` 内，**必须在构造 `Editor` 之前**，逐字搬运 `app.py:167-200`）：
`theme.set_theme(wanted)` → 逐个 `register_theme(theme.to_textual_theme(yt))` →
`self.theme = theme.textual_theme_name(...)`（桥不可用时回落 `mocha`）；错误信息照样写入
`config.errors`。

构造函数签名保持不变（`cli.py` 依赖）：
`YateApp(target=None, *, keymap=None, theme_name=None, config=None, ext_files=None, ext_dirs=None)`。

删除：`TabBar` 类（已在 `editor_view/chrome.py`）、`docs` / `doc_index` / `search` / `doc` /
`buffer` / `focus_target` / `_message_owner` / `_replace_pending` / `welcome_visible` 等状态，
以及上表之外的全部方法（含 `register_command` / `command_entries` / `action_entries` /
`mode_label` / `apply_terminal_height` / `terminal_height` / `shell_command` / `terminal_cwd` /
`spawn` / `terminal_factory` / `build_tabbar` / `render_breadcrumbs` / `_sync_explorer_visibility`
等）。

`__all__` 相应收缩（不再导出 `CommandRegistry`；`textual_key_to_raw` 的再导出若无人使用也删除，
先 grep 确认 `tests/` 与 `tools/` 的用法）。

---

## D.3 `yate/editor.py` 补漏（从 `app.py` 搬运）

| # | 动作 |
|---|---|
| 1 | **widget id**：`TabBar(..., id="tabbar")`、`Breadcrumbs(..., id="breadcrumbs")`、`ExplorerTree(..., id="explorer")`、`TerminalPanel(..., id="terminal-dock")`、`StatusBar(..., id="statusbar")`。外壳 CSS 依赖这些 id，缺一个布局就散 |
| 2 | `on_mount()` 内补终端初始状态（原 `app.py:1879-1880`）：`self.terminal_panel.styles.height = self.config.terminal_height`、`self.terminal_panel.display = False` |
| 3 | 新增 `mode_label() -> tuple[str, str]`：一行委托 `editor_view.statusbar.mode_chip(self.prompt_bar, self.keymaps)`（原 `YateApp.mode_label`，供状态栏与冒烟脚本复用） |
| 4 | 删除 `focus_target` 相关状态（已无消费者） |
| 5 | 逐个核对 `app.py` 的对外能力在 `Editor` 上都有落点；已确认存在：`has_modal_screen`、`install_font`、`quit`、`run_command`、`page`、`insert_char`、`execute_action`、`prompt_completions`、`load_startup_services`、`show_manual` / `show_changelog`（`_open_doc`）、`toggle_explorer` / `sync_explorer_visibility`、`refresh_explorer` / `set_show_hidden`、`select_keymap` / `toggle_keymap`、`set_theme` / `apply_theme`、`set_filetype`、`open_path` / `open_path_async` / `open_path_later`、`save_document` / `prompt_save_as`、`close_tab` / `cycle_tab` / `new_buffer`、`focus_explorer` / `focus_editor`、`handle_key` / `handle_raw_key`、`push_overlay` / `show_help` / 两个 palette、`show_diagnostics`。**缺失的按 `app.py` 原实现补进去，行为与文案保持一致** |
| 6 | 键事件不得被派发两次：`EditorView.on_key` 调用 `handle_key` 后若返回 `True` 会 `event.stop()`；返回 `False` 时事件会冒泡到 `YateApp.on_key` 再派发一次。修法（择一，推荐前者）：`EditorView.on_key` 无论返回值都 `event.stop()` + `event.prevent_default()`（编辑视图是输入终点，未消费的键不应再冒泡）；或 `YateApp.on_key` 先判断 `event.is_forwarded`/已处理标记。**必须保证一次按键只触发一次 `handle_raw_key`** |

---

## D.4 其余接线

| 文件 | 动作 |
|---|---|
| `yate/cli.py` | `--diag` 分支改为 `app.editor.load_startup_services()` 与 `diagnostics.print_report(app.editor)`（`diagnostics.py` 已按 `Editor` 改写） |
| `yate/app_features/` | **整个目录删除**（`__init__.py`、`commands.py`、`completion.py`、`docs.py`、`explorer.py`、`terminal.py`），含 `__pycache__` |
| `yate/__init__.py` | 模块文档串补一行 `:mod:yate.editor`（调度层）与 `:mod:yate.session`（会话模型） |

---

## D.5 完成检查（自检清单）

- [x] `python -c "import yate.editor"`、`python -c "import yate.app"` 均无错
- [x] `python -m pyright yate/` 0 诊断
- [x] `python -m yate --diag` 正常打印，`python -m yate --version` 正常
- [x] `grep -rn "app_features" yate/` 为空（tests/tools 留给 Plan E）
- [x] `wc -l yate/app.py` = **152** 行（≤ 170）
- [x] `yate/` 内除 `cli.py` 无 `import yate.app`

---

## D.6 实施结果（2026-09-22 实测）

| 项 | 结果 |
|---|---|
| `yate/app.py` | 2005 行 → **152 行**；仅剩 `ENABLE_COMMAND_PALETTE` / `CSS` / `__init__`（标题、config、主题引导、构造 `Editor`、装载内置表）/ `editor` / `compose` / `on_mount` / `on_unmount` / `on_key` / `get_theme_variable_defaults` / `action_quit` |
| `yate/app_features/` | 6 文件、1070 行**全部删除**（`__init__` / `commands` / `completion` / `docs` / `explorer` / `terminal`） |
| 解环（D.1） | `yate/editor.py` 不再 import `yate.actions` / `yate.commands`；改为 `YateApp.__init__` 装载（R7） |
| `yate/editor.py` | 新建 **1245 行**，承载原 `app.py` 的全部业务操作；`KeyUi` / `ActionContext(self.session, self.key_ui)` 在 `handle_key` / `execute_action` 处构建 |
| 接线（D.3） | 组件 id 全部带上：`#sidebar` `#sidebar-head` `#explorer` `#editor-col` `#tabbar` `#breadcrumbs` `#terminal-dock` `#statusbar`；`mode_label()` 委托 `statusbar.mode_chip()`；终端初始 `height = config.terminal_height` + `display = False` |
| cli（D.4） | `--diag` 走 `app.editor.load_startup_services()` 与 `diagnostics.print_report(app.editor)` |
| 综合门禁 | `pyright yate/` → 0 errors / 0 warnings；`python -m yate --diag`、`--version` 正常 |

**未完成项移交**：`tests/` 与 `tools/` 中 `app.<业务属性>` 的迁移、`tests/test_architecture.py` 规则更新
→ [Plan E](plan_E_tests_tools.md)；用户文档 / CHANGELOG / 架构规则文档同步 → [Plan F](plan_F_gate_docs.md)。
