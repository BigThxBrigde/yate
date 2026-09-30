# plan_C — shell + font 流程外移（Wave 3）

## 目标
shell 命令执行（同步/异步/worker）与 `:font` 字体安装外移到 `yate/shell_flow.py`。

## 改动文件（独占）
- 新建 `yate/shell_flow.py`
- `yate/editor.py`
- `tests/test_architecture.py`（R11 登记）

## 输入（外移方法，editor.py 行号）
| 方法 | 行号 | 去向 |
|---|---|---|
| `run_shell_command` | 1187-1203 | `ShellFlow.run` |
| `run_shell_command_later` | 1205-1220 | `ShellFlow.run_later` |
| `run_shell_command_async` | 1222-1234 | `ShellFlow.run_async` |
| `_shell_cwd` | 1236-1242 | `ShellFlow._cwd` |
| `_show_shell_result` | 1244-1251 | `ShellFlow._show_result` |
| `install_font` + `_font_command_async` | 1276-1293 | `ShellFlow.install_font` / `._font_async` |

## 实施
1. `ShellFlow` 构造参数：`app`、`session`、`workspace`、`prompt: PromptBar`、
   `message: Callable[[str, str], None]`、`mounted: Callable[[], bool]`、
   `push_overlay: Callable[[Screen[Any], Callable[[Any], None] | None], None]`。
   （prompt_bar 的 active_mode/idle 交互随 `run_later` 原样搬运。）
2. editor.py：
   - `_build_pane_stack` 后（或 `_build_widgets` 尾部）创建 `self.shell = ShellFlow(...)`。
   - 薄委托（外部调用面不变）：`run_shell_command`（ExtensionContext
     `run_shell=self.run_shell_command`，editor.py:220）、`run_shell_command_later`
     （shell_prompt lambda / run_command `:!` 分支）、`install_font`（commands.py:287）。
   - `shell_prompt`（editor.py:951-957）保留在 Editor（prompt 入口），其 on_submit
     lambda 改调 `self.shell.run_later`。
   - `run_command`（editor.py:1253）保留在 Editor（ex 分发），`!` 分支改调
     `self.shell.run_later`。
3. `UI_FROZEN_FILES["shell_flow.py"] = {"yate.editor_view", "yate.editor_view.commandline",
   "yate.editor_view.modals"}`。
4. 自查：不 import editor/app/actions/commands；asyncio.to_thread / run_worker 语义
   逐行保持（worker 组名 "shell" / "font" 不变）。

## 输出 / 验收
统一门禁全 0；ExtensionContext.run_shell 与 commands.py `:!` / `:font` 行为不变
（tests 零 diff 全绿佐证）。

## 回滚
单提交 revert。
