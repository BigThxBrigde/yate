# Plan B — 组件自持：`editor_view/*` 拥有自己的行为

> 状态：✅ **已完成**（工作区）· 前置：[Plan A](plan_A_leaf_models.md) · 后置：[Plan C](plan_C_functional_tables.md)
> 门禁：`python -m pyright yate/` 0 诊断；`grep -rn "yate.editor\|yate.app" yate/editor_view/` 为空（R3）

---

## B.1 背景（重构前）

重构前，widget 只负责"画"，行为（新建/重命名/删除文件流、终端启停、提示条提交、补全弹窗状态、
标签点击命中、面包屑截断）全部由 `YateApp` 或 `app_features/*` 的 Feature 代办，形成
`widget ← 宿主方法 ← Feature` 的三段式转发，任何行为改动都要穿过三层。

## B.2 交付物与"自持的行为"

| 模块 | 形态 | 自持的行为 | 构造注入的协作者 / 回调 |
|---|---|---|---|
| `chrome.py` | `TabBar(Static)` | 标签行渲染、鼠标命中测试（`_regions`）、`refresh_tabs()` | `EditorSession`、`on_activate: Callable[[Document], None]` |
| | `Breadcrumbs(Static)` | `crumb_parts()` / `build(width)` 截断 / `refresh_crumbs()` | `EditorSession`、`Workspace` |
| | `sidebar_head_text()` | 侧栏标题文本（纯函数） | — |
| `commandline.py` | `CommandInput(Input)` | 输入历史（`push_history` / 光标回溯）、bash 式 Tab 补全状态 | 所属 `PromptBar` |
| | `PromptBar(Horizontal)` | 提示模式状态机（`activate` / `idle` / `write`）、提交/取消分发、输入历史、Tab 补全状态 | `completer: PromptCompleter`（`Callable[[str, str], list[str]]`，非 Protocol）、`on_cancel`、`focus_editor`、`refresh`（内部存为 `refresh_ui`，避让 `Widget.refresh`） |
| `explorer.py` | `ExplorerTree(Tree)` | 新建文件 `a` / 新建目录 `A` / 重命名 `r` / 删除 `d` 的**完整流程**（含 `session.close_under`、`retarget`、刷新、隐藏文件开关） | `EditorSession`、`Workspace`、`PromptBar`；`open_path`、`focus_editor`、`window_prefix` |
| `terminal.py` | `TerminalPanel(Vertical)` | 显示/隐藏、`apply_height()`、启动并重启 shell、标题栏 | `YateConfig`、`Workspace`、`PromptBar`、`focus_editor`；**`view_factory` 为测试注入点**（生产为 `None`） |
| | `TerminalView(Widget)` | PTY 进程生命周期、VT 模拟器、滚动、按键/粘贴/滚轮 | 所属 `TerminalPanel` |
| `panes.py` | `PaneManager` | 窗格树操作（split / close / only / focus 方向 / resize / equalize）、`active_view` | `EditorSession`、`Document`；`is_mounted` / `after_pane_focus` / `focus_explorer` |
| | `PaneHost(Widget)` | 按 `PaneManager` 的树构建/协调子 widget、尺寸应用 | `PaneManager`、`make_view: Callable[[int], EditorView]` |
| `pane_types.py` | `ViewState` / `Leaf` / `Split` + 纯函数 | 窗格树数据结构与纯操作（`leaves` / `find_leaf` / `replace_node` / `remove_node` / `find_axis_split`） | — |
| `statusbar.py` | `StatusBar(Static)` | 状态行内容（模式、文件、行列、LSP 回显） | `EditorSession`、`LspManager`、`KeymapSet`、`PromptBar`、`ExtensionLoader` |
| | `mode_chip(prompt, keymaps)` | 模式标签（纯函数，供状态栏与冒烟脚本复用） | — |
| `modals.py` | `_OverlayScreen` / `HelpScreen` / `OutputScreen` | 覆盖层外壳、快捷键参考、shell 输出查看 | `KeymapSet`、`CommandRegistry`（help）；标题/输出/返回码（output） |
| `palette.py` | `PaletteScreen(ModalScreen)` | 文件/命令面板：模糊匹配、候选构建、执行 | `Workspace`、`CommandRegistry`、`ActionRegistry`；`open_path` / `focus_editor` / `execute_action` / `run_command` / `refresh` |
| | `fuzzy_match()` / `_walk()` | 纯函数工具 | — |
| `editor.py`（视图） | `EditorView(ScrollView)` | 文本渲染、光标/选区、按键转发给 `handle_key` | `leaf_id`、`PaneRegistry`（**唯一保留的 Protocol**）、`EditorSession`、`LspManager`、`KeymapSet`、`handle_key` |
| `theme.py` / `icons.py` / `keys.py` / `manual.py` | 主题、图标、键名转换、手册屏幕 | 自持纯逻辑 | — |

## B.3 设计要点

1. **行为跟着组件走**：`ExplorerTree` 自己完成"改名 → `session.retarget` → 刷新"，`TerminalPanel` 自己
   完成"启动 → 退出 → 按键重启"，不再有中间 Feature 转发。
2. **注入具体协作者或回调**：组件只拿 `EditorSession` / `Workspace` / `PromptBar` 这类**具体对象**，
   或 `Callable` 回调；需要向上触达编辑器时用回调（`open_path` / `focus_editor` / `execute_action`），
   因此 `editor_view/*` 完全不 import `yate.editor` / `yate.app`（R3）。
3. **测试注入点保留在组件上**：`TerminalPanel.view_factory` 供测试替换 PTY；`PromptBar.completer` 是
   函数别名而非协议，测试可直接传 lambda。
4. **`PaneRegistry` 是唯一例外**：`PaneHost` 与 `EditorView` 之间存在结构性环，用一个方法级的
   窄 Protocol 打断（R2 白名单）。

## B.4 旧 → 新 对照

| 旧 | 新 |
|---|---|
| `app.build_tabbar(widget)` / `app.tabbar`（`TabBar` 定义在 `app.py`） | `yate/editor_view/chrome.py::TabBar`，`Editor` 持有 `self.tabbar`（`id="tabbar"`） |
| `app.render_breadcrumbs(widget)` | `Breadcrumbs.build(width)` |
| `app.explorer_feature.*` | `ExplorerTree` 自持 |
| `app.terminal_feature.*` / `app.spawn()` / `app._terminal_factory` | `TerminalPanel.toggle/open/close/apply_height` + `view_factory` |
| `app.docs_feature.*` | `Editor._open_doc` / `EditorView` |
| `app.completion_ctl`（Feature） | `CompletionController`（Plan C）+ `CompletionPopup`（本 Plan） |
| Feature 里的提示条驱动 | `PromptBar` 自持提交/取消 |

## B.5 验收证据

- `yate/editor_view/*` 无 `import yate.editor` / `import yate.app`。
- 外壳 CSS 依赖的 id 全部由 `Editor` 构造时传入：`#sidebar` `#sidebar-head` `#explorer`
  `#editor-col` `#tabbar` `#breadcrumbs` `#terminal-dock` `#statusbar`，
  外加 `compose()` 里的容器 id `#body` / `#bottom-dock` / `#bottom`
  （见 [Plan D](plan_D_shell_wiring.md) §D.3 与总纲 §4 R9）。
- **2026-09-23 审计复核**：本表全部 widget 的构造签名与自持方法经代码逐条核对一致。
- `python -m pyright yate/` → 0 诊断。
