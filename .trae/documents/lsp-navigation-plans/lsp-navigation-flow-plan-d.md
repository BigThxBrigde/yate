# 计划 d — L3 流程与编辑器接线（波次 3）

父计划：[../lsp-navigation-plan.md](../lsp-navigation-plan.md)。

## 输入 / 输出

输入：波次 a 的 manager 方法、波次 b 的动作名、波次 c 的选择器行类型。
输出：一个实现所有用户可见行为并完成接线的 L3 流程对象。

## 独占文件

- `yate/flows/lsp_navigation_flows.py`（新增）
- `yate/editor_compose.py`
- `yate/editor.py`
- `tests/test_lsp_navigation_flows.py`（新增）

此处不要编辑 keymap、动作、manager、选择器、架构测试或文档。

## 具体改动

### 1. `flows/lsp_navigation_flows.py`

参照 `HoverFlows` 的形态（`hover_flows.py:33-59`）新建 L3 流程模块：

```python
class LspNavigationFlows:
    def __init__(self, *, spawn: SpawnFn, lsp: LspManager,
                 session: EditorSession, panes: PaneManager,
                 popup: HoverPopup,
                 open_path: Callable[[Path], Document | None],
                 push_overlay: Callable[[Screen[None]], None],
                 message: Callable[[str, str], None],
                 refresh: Callable[[], None],
                 prompt: PromptBar,
                 has_modal_screen: Callable[[], bool]) -> None
```

只注入具体对象/回调；不持有 App 句柄（`test_flow_modules_hold_no_app_handle`）。
`PromptBar` 来自 `yate.editor_components.commandline`（波次 d 更正：
`PromptFlows` 没有 `prompt_text` 方法；该栏在 `commandline.py:315-325` 的
`activate(mode, *, placeholder, on_submit, ...)` API 才是提示的接缝）。
模块级 `NAV_JUMP_KIND = "info"`、`NAV_TIMEOUT_MESSAGE = "LSP request timed out"`。

公开方法（名称必须与波次 b 的动作一致）：
`goto_definition()`、`find_references()`、`show_outline()`、`rename_symbol()`、
`show_code_actions()`、`show_signature_help()`。

公共机制：
- `_snapshot()` 捕获 `doc`、`(row, col)`、`str(doc.path)`，并递增 `self._token`。
- `_stale(doc, pos, token)` 参照 `HoverFlows._stale`（`:190-209`）：token、
  会话文档身份、路径，以及键盘请求的光标。过期结果会被丢弃，不给出消息、
  也不改动 UI（AC7）。
- `_spawn(partial(self._worker_* , ...), group="lsp-navigation", exclusive=True,
  exit_on_error=False)`；worker 捕获 `LspFeatureUnavailable`、`LspFeatureFailed`、
  `TimeoutError` 和 `Exception`（带 `noqa: BLE001` + `log.debug`）并调用
  `message(explicit_text, "warning")`，绝不静默。
- `_chooser(rows, title)` 推送 `LspChooserScreen(rows, title, self._jump_to_row)`。
- `_jump_to_row(row: LspRow)`：通过 `uri_to_path(row.uri)` 解析路径；
  `open_path(path)`（波次 d 更正：`DocumentFlows.open_path` 返回 `None`）；
  然后 `doc = session.is_open(path)`（`session.py:243-249`），若为 `None` ->
  给出消息并返回；把光标设到 `(row.row, row.col)`，清除锚点，通过
  `panes.views_for(doc)` 在所有视图上调用 `reveal_cursor()`；`open_path` 会激活
  该文档；调用 `refresh()` 与 `message(f"jumped to {file}:{line+1}", "info")`。

各方法行为：
- `goto_definition`：请求定义；0 -> `"No definition found"`；1 ->
  直接跳转；>1 -> 标题为 `Definitions` 的选择器。
- `find_references`：请求引用；0 -> `"No references found"`；否则使用标题为
  `References`、`detail = "line N"` 的选择器。
- `show_outline`：请求文档符号；0 -> "No symbols available"；否则使用标题为
  `Outline` 的选择器，`label` 以 `"  "*depth` 作为前缀。
- `rename_symbol`：通过注入的 `PromptBar` 提示（`prompt.activate(
  "lsp_rename", placeholder="New symbol name", on_submit=self._on_rename))`；
  用 ESC 取消不会调用 `on_submit`，且为空操作。提交回调会快照 doc/pos/token，
  派生重命名 worker；若 `unsupported` -> 给出警告消息；否则 `_apply_workspace_edit(edit)`。
- `_apply_workspace_edit(edit)`：预先把每个 URI 解析为路径；若任何路径缺失/不可读 ->
  给出消息，不做改动。为每个受影响的文档快照 `buffer.get_text()` 和光标。
  按 `(start_row, start_col)` 降序对每个文档自底向上用 `buffer.replace_range`
  应用文本编辑；发生任何异常时用 `replace_range` 在完整旧范围上恢复每个快照。
  调用 `refresh()`；给出消息 `Renamed N occurrence(s)` 或失败文案。不写磁盘；
  未打开的目标通过 `open_path` 打开。
- `show_code_actions`：请求动作；0 -> 消息；否则使用带标题的选择器；
  选中时若有 `action.edit` 则应用它，否则若有命令名则 `execute_command(...)`，
  否则给出消息 "action cannot be applied"。
- `show_signature_help`：请求签名；`None`/空 -> 消息；否则通过
  `panes.active_view.screen_anchor(row, col)` 计算锚点，并调用
  `popup.show(text, anchor, size, gutter, origin_y=2)`（与 hover 相同的 API）。
  显示前使用 token 过期检查；过期时关闭弹窗。

### 2. `editor_compose.py`

在 `HoverFlows`（`:250-257`）附近构造该流程，需在 `ed.overlays` 和
`ed.document_flows` 存在之后（现有的 `NavigationFlows` 块 `:304-311` 是范本）。
注入 `spawn=ed.app.run_worker`、`lsp=ed.lsp`、session、panes、
`popup=ed.hover_popup`、`open_path=ed.document_flows.open_path`、
`push_overlay=ed.overlays.push`、`message=ed.message`、`refresh=ed.refresh_ui`、
`has_modal_screen=ed.has_modal_screen`、`prompt=ed.prompt_bar`。
无需改动 `PromptFlows`：更正后的提示接缝是 `PromptBar.activate`。

### 3. `editor.py`

在 `hover`（`:103-148`）附近的类属性表中加入 `lsp_navigation: LspNavigationFlows`，
并更新装配顺序注释。无其他改动。

## 测试（`tests/test_lsp_navigation_flows.py`）

使用返回预设结果的假 manager，并桩掉注入的回调：
- `test_goto_definition_single_location_jumps_cross_file`：另一文件中有一个位置 ->
  以该路径调用 `open_path`，缓冲区光标等于目标行/列，并发出消息。
- `test_goto_definition_multiple_locations_open_chooser`：两个位置 -> 推送一次含两行的 `LspChooserScreen`。
- `test_goto_definition_without_provider_reports_message`：`LspFeatureUnavailable` -> 警告消息包含 `definition`，无选择器，无异常。
- `test_find_references_empty_reports_message`：空列表 -> "No references found"。
- `test_find_references_rows_are_navigable`：两行 -> 选中第二行时以其 URI 路径和正确行号调用 `open_path`。
- `test_show_outline_uses_selection_range_and_depth`：嵌套符号 -> 选择器标签带缩进，跳转目标取自 `selectionRange`。
- `test_rename_applies_workspace_edit_bottom_up`：一个缓冲区中的两处编辑 -> 均被应用，刷新一次，成功消息。
- `test_rename_rolls_back_all_buffers_on_failure`：第二处编辑无效 -> 所有缓冲区恢复为原始文本，给出警告消息。
- `test_rename_unsupported_edit_reports_message`：`unsupported=True` -> 警告，无改动。
- `test_show_code_actions_executes_command_without_edit`：只有命令的动作 -> 以名称/参数调用 `execute_command`。
- `test_show_signature_help_uses_hover_popup`：签名文本 -> 以预期锚点调用 `popup.show`。
- `test_stale_result_is_discarded`：在 worker 完成前递增 token / 切换文档 -> 无选择器、无消息、无弹窗。

## 验收命令

```powershell
.venv\Scripts\python.exe -m pytest tests/test_lsp_navigation_flows.py -q
.venv\Scripts\python.exe -m pyright yate/flows/lsp_navigation_flows.py yate/editor.py yate/editor_compose.py tests/test_lsp_navigation_flows.py
```

要求以 0 退出。此处不要跑完整测试套件或冒烟测试。

## 风险 / 回滚

风险：`editor.py` 和 `keymaps/vim.py` 的行数会变化；由计划 e 同步。
风险：若 `PromptFlows` 缺少 `prompt_text`，在做任何范围外改动之前先报告主代理。
风险：`open_path` 实际上可能是异步的；接线前核验签名，相应调整注入的回调类型，
并记录该偏离。回滚：回退本计划的提交；波次 a/b/c 的产物仍可独立测试。

## 执行偏离记录（2026-11-22）

实测：`PromptBar.MESSAGE_COLORS`（`commandline.py:54-56`）接受 `warn`，
而非 `warning`；计划中的 `"warning"` 类型被静默渲染为 `fg_bright`。
主代理在波次 d 后把全部 14 处流程消息类型及对应的测试断言改为 `"warn"`，
重新运行流程测试（12 passed）和 pyright（0 诊断），然后随该波次提交了更正。
除消息颜色外，没有其他行为改变。
计划 e 实测的最终行数：`editor.py` 848、`keymaps/vim.py` 1704、
`editor_lsp/manager.py` 1168（`splitlines()`）。
