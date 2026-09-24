# yate 架构总览

> 基于当前代码梳理（`yate/` 包，Textual 终端编辑器）。
> 相关文档：`textual-framework-hooks.md`（框架钩子细节）。

## 1. 分层结构与持有关系

依赖方向严格单向：**cli → app → editor → 各子模块**，UI 无关的内核
（editor_core、editor_lsp、session、registries）位于依赖链末端。

```
__main__.py ──► cli.py::main() ──► YateApp (app.py) ──► Editor (editor.py)
                                                        │
        ┌───────────────┬───────────────┬───────────────┼─────────────┐
   editor_core/    editor_view/     keymaps/       editor_lsp/  editor_term/
  (编辑内核,无UI)  (Textual widgets) (可插拔键位)    (LSP,无UI)   (PTY+模拟器)
```

- **入口** `yate/__main__.py` → `yate/cli.py::main()`：解析参数、安装
  crash/trace 日志、加载 `yaterc` 与主题目录，惰性导入 TUI 后构造
  `YateApp.run()`；`--diag` 走无头诊断路径（`yate/diagnostics.py`）。
- **外壳** `yate/app.py::YateApp`（Textual `App` 子类）：刻意单薄，只负责
  主题桥、CSS、生命周期（compose/on_mount/on_unmount）与按键兜底转发。
  构造时创建 `Editor` 并执行 `actions.populate()` /
  `commands.register_commands()` 灌入内置表（R7 规则：表模块导入 editor，
  editor 不得反向导入它们）。
- **核心枢纽** `yate/editor.py::Editor`：持有 `EditorSession`、
  `Workspace`、`LspManager`、`KeymapSet`、`PaneManager`、
  `CompletionController` 及两个注册表；反向引用 `self.app`。
- **架构守护**：`tests/test_architecture.py` 在测试层强制约束上述分层。

## 2. 顶层模块职责

| 模块 | 职责 | 关键类/函数 |
| --- | --- | --- |
| `editor_core/` | UI 无关编辑内核 | `buffer.py::TextBuffer`、`document.py::Document`、`search.py::SearchEngine` |
| `session.py` | 文档会话模型（tabs/活动文档/搜索），含窗口模型 `Leaf/Split`，不依赖 UI | `EditorSession` |
| `registries.py` | 叶子模块，两个纯容器注册表 | `ActionRegistry`、`CommandRegistry` |
| `actions.py` | 内置动作表 | `populate()`（闭包绑定具体 Editor 实例） |
| `commands.py` | 内置 ex 命令表 | `register_commands()` |
| `config.py` | yaterc（Python 脚本式配置）加载 | `YateConfig`，支持 `register_theme` 注入、`language_servers` 声明 |
| `completion.py` / `prompt_completion.py` | 补全控制器与 prompt 补全 | `CompletionController` |
| `keymaps/` | 可插拔键位方案 | `base.py::Keymap/ActionContext`、`registry.py::KeymapSet`、`vsc.py`、`vim.py` |
| `editor_term/` | 内置终端：VT100/xterm 模拟器 + 跨平台 PTY | `emulator.py`、`pty_proc.py`、`shells.py` |
| `editor_lsp/` | UI 无关 LSP 客户端与管理器 | `client.py::LspClient`、`manager.py::LspManager`（didOpen/didChange/didSave/didClose、补全、诊断） |
| `editor_syntax/` | 语法高亮，按文件类型路由 | `engine.py` → tree-sitter 后端（`ts_backend/`）或正则后端（`regex_backend.py`），`.scm` 查询文件 |
| `services/` | 平台服务 | `extensions.py::ExtensionAPI`（扩展脚本 `setup(api)`）、`workspace.py`、`fonts.py`、`user_setup.py`、`trust.py`（工作区信任门控）、`shell.py` |
| `extensions/` | 内置扩展示例 | C# 高亮、Python LSP 扩展 |
| 其他 | `logs.py`（crash/tracing）、`paths.py`、`diagnostics.py`、`resources/`（字体、文档资源） | |

## 3. editor_view/ 组成（Textual UI 层)

| 文件 | 职责 |
| --- | --- |
| `editor.py::EditorView` | 主编辑面：Rich 渲染、语法高亮、选择/搜索叠层 |
| `panes.py::PaneManager/PaneHost` | 编辑区窗格管理 |
| `chrome.py` | TabBar / Breadcrumbs |
| `statusbar.py::StatusBar` | 状态栏 |
| `commandline.py::PromptBar` | 底部命令行 / 提示条 |
| `explorer.py::ExplorerTree` | 侧边文件浏览器 |
| `palette.py::PaletteScreen` | quick-open / 命令面板 |
| `modals.py` | Help / Output 覆盖层 |
| `manual.py::MarkdownDocScreen` | 帮助手册 / changelog 查看器（引用 `$doc-hit-*` CSS 变量） |
| `terminal.py::TerminalPanel` | 内置终端面板 |
| `completion.py::CompletionPopup` | 补全弹出层 |
| `keys.py` | Textual 键名 → raw 字节翻译（`event_to_raw` / `textual_key_to_raw`） |
| `theme.py` | yate 主题定义 + `to_textual_theme()` 桥接 |
| `icons.py` | Nerd Font 字形 |

## 4. 事件流：按键 → 动作 → 命令

```
焦点 widget ──未消费──► YateApp.on_key ──► Editor.handle_key(event)
                                              │ 按序检查：模态框 / 补全弹出层 /
                                              │ terminal 切换 / vim ctrl+w 前缀 /
                                              │ 全局 chord（ctrl+p、alt+shift+p…）
                                              ▼
                              keys.py::event_to_raw()  (Textual 键 → raw 字节)
                                              ▼
                     keymaps.active.handle_key(ActionContext(...))
                                              ▼
              键位绑定动作名 → Editor.execute_action() 查 ActionRegistry
              ":命令"        → Editor.run_command()    查 CommandRegistry
```

- 两个注册表在 `YateApp.__init__` 中由 `populate` / `register_commands`
  一次性灌入；扩展可通过 `ExtensionAPI` 追加。
- 键位方案可插拔：`keymaps/` 下 `base`/`vsc`/`vim`，`KeymapSet` 管理激活态。

## 5. 主题桥接机制

- `editor_view/theme.py::Theme` 定义 chrome + 语法调色板（8 个内置主题）；
- `to_textual_theme()` 生成 Textual `Theme`（命名 `yate-<name>`）；
- `YateApp.__init__` 中把所有桥注册进 Textual，并把 `self.theme` 设为活动
  桥，使所有覆盖层（help/manual/palette…）零切换自动同主题；
- 自定义主题：`set_theme` 支持 yaterc / `--theme-dir` / `--theme`
  （`register_theme` + `validate_theme` 严格校验）；
- `$doc-hit-*` 等自定义 CSS 变量的兜底见 `app.py::get_theme_variable_defaults`
  （详见 `textual-framework-hooks.md`）。

## 6. 外部集成

- **LSP**：`LspManager` UI 无关；server 来自 yaterc `language_servers` 声明
  与扩展 `api.lsp.register`；editor 在四个文档生命周期点挂钩
  （`editor.py::load_startup_services` 启动），诊断经 `on_event` 回调驱动
  UI 重绘。
- **内置终端**：`pty_proc.py` 起 PTY → `emulator.py` 把字节流驱动成单元格
  网格 → `TerminalPanel` 渲染。
- **扩展系统**：`services/extensions.py::ExtensionLoader` 加载 `setup(api)`
  脚本，受 `trust.py` 工作区信任门控。

## 7. 测试与工具链

- **`tests/`**：pytest，35+ 文件按模块一一对应，含
  `test_architecture.py` 守护分层约束；另有主题断言（如
  `test_theme_palettes.py`）。
- **`tools/`**：独立 CLI 工具集——`changelog/`（git + Gitee 生成双语
  changelog）、`pack/`（图标打包）、`release/`、`smoke_test/`（分场景
  端到端冒烟测试）。
