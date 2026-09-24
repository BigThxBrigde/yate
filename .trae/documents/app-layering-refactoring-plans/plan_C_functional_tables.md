# Plan C — 函数化的表与流程：`populate` / `register_commands` / 补全 / 扩展

> 状态：✅ **已完成**（工作区）· 前置：[Plan B](plan_B_widget_selfhold.md) · 后置：[Plan D](plan_D_shell_wiring.md)
> 门禁：`python -m pyright yate/` 0 诊断；内置表可由外部装载（不产生导入环）

---

## C.1 背景（重构前）

1. 内置动作/命令表写在 `app_features/commands.py` 的 Feature 类里，由宿主转发调用；
2. 补全流程（缓冲补全、LSP 补全、弹窗状态、接受/取消）混在 Feature 与 widget 之间；
3. 扩展系统需要"宿主"对象才能注册动作/命令，`api.app` 暴露的是 `YateApp`，扩展与外壳强耦合；
4. `Editor`（调度层）不存在 —— "操作"分散在 `YateApp` 的 1875 行里。

## C.2 交付物

| 文件 | 形态 | 内容 |
|---|---|---|
| `yate/actions.py` | `def populate(registry: ActionRegistry, editor: Editor) -> None` | 内置动作表：编辑动作走 `ctx.buffer`，会话/视图动作走 `editor.*`（save / open_prompt / find / palette / keymap 切换…） |
| `yate/commands.py` | `def register_commands(registry: CommandRegistry, editor: Editor) -> None` | 内置 `:` 命令表（save / quit / set / theme / files / diagnostics / explorer / 扩展信息…） |
| `yate/prompt_completion.py` | `def prompt_completions(...)`、`_command_completions()`、`_path_matches()` + 模块级常量 | 提示条补全候选（命令名 / 路径）——**无状态模块**，允许 import `editor_view.theme`（存量耦合，见 R11） |
| `yate/completion.py` | `class CompletionController` | 会话级补全流程：`request` / `schedule`（触发与防抖）、LSP/缓冲候选、弹窗状态、`accept`（接受）、`close`（取消）、私有 `_stale`（过期校验） |
| `yate/services/extensions.py` | `ExtensionContext`（dataclass）、`ExtensionAPI`、`ExtensionLoader`、`load_startup_extensions(loader, config, *, ext_dirs, ext_files)` | `api.app` 从此暴露 **`ExtensionContext`**（session / workspace / lsp / keymaps / actions / commands / message / run_shell / open_path / save），不再依赖外壳 |
| `yate/editor.py` | `class Editor` | 调度层：`compose` / `on_mount` / `on_unmount` / `handle_key` / `handle_raw_key` + 打开保存、窗格、提示、搜索替换、主题、shell、LSP、覆盖层、扩展装载 |
| `yate/diagnostics.py` | `version_lines()`、`format_report(editor)`、`print_report(editor)` + 12 个 `_section_*` 与 `_enable_windows_ansi` / `_colorize_line` / `_kv` / `_package_version` 纯函数 | 由"依赖 YateApp 的对象"改为**接收 `Editor` 的函数集合** |

## C.3 设计要点

1. **表 = 函数，不是类**：`populate()` / `register_commands()` 只做"往注册表登记"，天然可被外壳（或测试）
   任意调用；`actions.py` / `commands.py` **单向** import `yate.editor`，反向禁止，保证无环（R5）。
2. **流程外移**：补全这种"横跨 buffer / LSP / 弹窗 / 提示条"的会话级流程从 `Editor` 里拆到
   `yate/completion.py`，候选生成再拆成纯函数 `prompt_completions()` —— `Editor` 只调一行。
3. **扩展面向上下文而非外壳**：`ExtensionContext` 是 dataclass，扩展需要的每一样能力都是显式字段，
   扩展与 `YateApp` 解耦；`load_startup_extensions()` 也退化成纯函数式装载流程。
4. **诊断是函数**：`format_report(editor)` / `print_report(editor)` 无状态，cli 直接 `print_report(app.editor)`。

## C.4 旧 → 新 对照

| 旧 | 新 |
|---|---|
| `app_features/commands.py::CommandsFeature`（339 行） | `yate/commands.py::register_commands()`（203 行） |
| `app_features/completion.py::CompletionFeature`（307 行） | `yate/completion.py::CompletionController`（280 行）+ `yate/prompt_completion.py`（126 行） |
| `app_features/docs.py`（59 行） | `Editor._open_doc` / `EditorView` / `manual.py` |
| `app_features/explorer.py`（211 行） | `ExplorerTree`（Plan B） |
| `app_features/terminal.py`（146 行） | `TerminalPanel`（Plan B） |
| `app.register_command(...)` / `app.command_entries()` | `CommandRegistry.register/names/describe` |
| `api.app` → `YateApp` | `api.app` → `ExtensionContext`（用户可见变化） |
| `AppDiagnostics(app)` | `print_report(editor)` / `format_report(editor)` |

> 行数口径同总纲 §1：**非空行**（`commands.py` 总 251 / 非空 203，`completion.py` 总 310 / 非空 280，
> `prompt_completion.py` 总 139 / 非空 126；2026-09-23 复核）。

## C.5 验收证据

- `import yate.editor` 成功（Plan D 解环后）；`yate/editor.py` 不 import `actions` / `commands`。
- `load_startup_extensions` 的入参为 `(loader, config, *, ext_dirs, ext_files)`，不接收外壳。
- `python -m pyright yate/` → 0 诊断。
