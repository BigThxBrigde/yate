# plan_D — overlays 流程外移（Wave 4）

> **实施状态**：✅ 已实施 —— 2026-10-05 全量核对：文档自述与代码产物一致。
全屏覆盖层（help / manual / changelog / 双 palette / screensaver）外移到
`yate/overlays.py`，`push_overlay` 一并归属（shell_flow 已注入等价回调，不回头依赖）。

## 改动文件（独占）
- 新建 `yate/overlays.py`
- `yate/editor.py`
- `tests/test_architecture.py`（R11 登记）

## 输入（外移方法，editor.py 行号）
| 方法 | 行号 | 去向 |
|---|---|---|
| `push_overlay` | 1399-1412 | `OverlayController.push` |
| `show_help` | 1414-1417 | `OverlayController.show_help` |
| `show_manual` / `show_changelog` / `_open_doc` | 1419-1430 | 同名 / `_open_doc` |
| `open_file_palette` / `open_command_palette` / `_palette` | 1432-1453 | 同名 / `_palette` |
| `toggle_screensaver` | 1455-1490 | `OverlayController.toggle_screensaver` |

## 实施
1. `OverlayController` 构造参数：`app`、`config: YateConfig`、`keymaps: KeymapSet`、
   `commands: CommandRegistry`、`actions: ActionRegistry`、`workspace: Workspace`、
   `prompt: PromptBar`、`message`、`mounted`、`open_path: Callable[[Path], None]`、
   `focus_editor: Callable[[], None]`、`execute_action: Callable[[str], bool]`、
   `run_command: Callable[[str], None]`、`refresh: Callable[[], None]`。
   （14 个参数偏胖——palette/help 本就需要这些能力；与 CompletionController 的 9 参
   同构，可接受，登记为已知权衡。）
2. editor.py 薄委托（actions.py 6 处 + commands.py 7 处 + tests 可能直调）：
   `push_overlay` / `show_help` / `show_manual` / `show_changelog` /
   `open_file_palette` / `open_command_palette` / `toggle_screensaver`，各 3-4 行。
   `_open_doc` / `_palette` 内部化，不保留。
3. `shell_flow`（Wave 3）注入的 `push_overlay` 回调改绑 `self.overlays.push`——
   实施顺序上 Wave 3 先注入 `ed.push_overlay`（此时还是 Editor 方法），Wave 4 改绑
   回调目标即可，shell_flow.py 本体零 diff。
4. `toggle_screensaver` 需 `character_names`（editor_sprites，L0 叶子）与
   `ScreensaverScreen`（editor_view.screensaver）——前者无守卫，后者登记。
5. `UI_FROZEN_FILES["overlays.py"] = {"yate.editor_view", "yate.editor_view.commandline",
   "yate.editor_view.modals", "yate.editor_view.manual", "yate.editor_view.palette",
   "yate.editor_view.screensaver"}`。
6. screensaver 空闲轮询（app.py:278 经 `editor.execute_action`）走 execute_action →
   委托链不变，无二次派发问题（R10 不涉及）。

## 输出 / 验收
统一门禁全 0；smoke 的 help_modal / file_palette 场景绿；F1 / Ctrl+P /
Alt+Shift+P / :manual 行为不变（tests 零 diff）。

## 回滚
单提交 revert。
