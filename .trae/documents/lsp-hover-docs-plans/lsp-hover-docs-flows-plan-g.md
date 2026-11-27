# 计划 g — `HoverFlows` 编排（波次 3，L3）

父计划：[overview.md](overview.md) · 主计划：[../lsp-hover-docs-plan.md](../lsp-hover-docs-plan.md)，决策 D4/D5/D6
依赖：计划 d（`LspManager.request_hover`）、计划 e（`HoverPopup.show/close`）、计划 a（归一化）。

## 输入

- `yate/flows/completion_flows.py:87-113`、`:145-184`、`:186-281`（用 `call_later` 实现防抖、`SpawnFn` worker、`_stale()` 类似 token 的逻辑、`_show_items()` 几何计算：`theme.char_to_cell`、`editor.size`、`gutter_width`、`origin_y=2`）。
- `yate/flows/__init__.py:31-33`（`SpawnFn = Callable[..., Worker[object]]`）。
- `yate/editor_lsp/manager.py:216-218`（`supports(doc)`）。
- `architecture-boundaries.md` §三.8（新增 L3 流程模块检查清单）、R11（由计划 h 完成注册）、R12（tracing）、R10（不吞键 —— 由计划 h 处理）。

## 独占文件

- `yate/flows/hover_flows.py`（新建）
- `tests/test_hover_flows.py`（新建）
- `tests/test_architecture.py` —— 对 `UI_FROZEN_FILES`（`:198`）**只**做一处添加，登记 `hover_flows.py` 实际导入的 L2 模块（R11）。已登记对原始波次顺序的偏离：计划 h（波次 4）将按顺序把新的漂移守卫用例添加到同一文件。
  **原因：**一旦新的 L3 流程导入 `editor_components`，`:830` 处的 R11 守卫就会失败，因此白名单必须与该流程在同一波次落地。

## 具体改动（`yate/flows/hover_flows.py`）

模块 docstring（ASCII 英文），`from __future__ import annotations`，按 stdlib / 第三方 / `yate` 分组导入，不使用 `yate.editor` / `yate.app`，不使用 `Any` / `TYPE_CHECKING` / 相对导入。

```python
#: Delay before a non-drag MouseMove starts a hover request.
HOVER_DEBOUNCE_S: float = 0.35

class HoverFlows:
    """Own hover requests, debounce, staleness tokens and card dismissal."""

    def __init__(
        self,
        *,
        spawn: SpawnFn,
        lsp: LspManager,
        session: EditorSession,
        panes: PaneManager,
        popup: HoverPopup,
        has_modal_screen: Callable[[], bool],
    ) -> None: ...
```

这个确切的签名是计划 h 所依赖的契约；未经先回写 overview 不得改动它。

字段：`_timer: asyncio.TimerHandle | None = None`、`_token: int = 0`、`_source: str = ""`、`_target: Pos | None = None`、`_doc_path: str | None = None`。

公开 API：

1. `request_at_cursor() -> None` —— 键盘路径。快照
   `doc = self.session.doc`、`pos = (buf.row, buf.col)`；立即调用 `_schedule(doc,
   pos, "key")`（不防抖）。
2. `on_mouse_move(pos: Pos | None) -> None` —— 由计划 h 注入 `MouseFlows`
   的回调。
   - `None`（指针离开文本区域 / 门控关闭 / 开始拖拽）→
     `self.dismiss()`。
   - 与 `_target` 不同的位置 → 立即 `self.popup.close()`
     （新防抖运行期间不留旧卡片），然后取消上一个定时器并安排
     `loop.call_later(HOVER_DEBOUNCE_S,
     self._schedule_mouse, pos)`。
   - 卡片可见时位置相同 → 不做事（不闪烁）。
3. `dismiss() -> None` —— 取消定时器，`_token += 1`（使在途结果失效），`self.popup.close()`。幂等；绝不写入消息栏或状态栏。
4. `_schedule(doc: Document, pos: Pos, source: str) -> None` —— 对
   `self._has_modal_screen()` 与 `not self.lsp.supports(doc)` 做门控；后者
   **不得**调用 `self.dismiss()`（仅因门控就关闭卡片而不给出反馈是不允许的）；
   对模态屏直接静默 `return`；对无服务器的情况，仅在卡片可见时先 `popup.close()`
   再 `return`。记录
   `_doc_path = str(doc.path) if doc.path is not None else None`、`_source`、
   `_target`，递增 `_token`，然后 spawn：
   `self._spawn(partial(self._worker, doc, pos, token), group="lsp-hover",
   exclusive=True, exit_on_error=False)`（传协程*函数*，不是预先创建的协程对象）。
5. `async def _worker(self, doc: Document, pos: tuple[int, int], token: int) -> None`：
   - `text = await self.lsp.request_hover(doc, pos[0], pos[1])` 包在
     `try/except Exception:  # noqa: BLE001 - a failed request must be silent`
     中 → `text = ""` + `log.debug(..., exc_info=False)`（延迟 `%`）。
   - `if self._stale(doc, pos, token): return`（丢弃，不改变 UI）。
   - `if not text.strip(): self.popup.close(); return` —— **零 UI 反馈**，
     包括"卡片原本可见、但新结果为空"的情况。
   - `view = self.panes.active_view`；`None` → 返回。
   - `buf = doc.buffer`；`line = buf.lines[pos[0]] if pos[0] < buf.line_count else ""`；
     `cell = theme.char_to_cell(line, pos[1], buf.tab_width) - view.scroll_col`；
     `rel_row = pos[0] - view.scroll_offset.y`；
     `self.popup.show(text, (cell, rel_row),
     (view.size.width or 80, view.size.height or 20),
     view.gutter_width(), origin_y=2)`。
   - 本模块中任何地方都不调用 prompt/message/report/status。
6. `_stale(doc, pos, token) -> bool`：
   - `token != self._token`、`self.session.doc is not doc`、
     `doc.path` 字符串 != `_doc_path`、`not self.popup.is_mounted`；
   - `_source == "key"` 时：`session.doc.buffer.row/col != pos`；
   - `_source == "mouse"` 时：`self._target != pos`。
   - 任一不匹配即返回 `True`；过期响应被丢弃，绝不显示，也绝不关闭无关的新卡片。

Widget 导入（`HoverPopup`、`PaneManager`、`EditorView`、`theme`）属于 L3→L2，
必须由计划 h 登记到 `UI_FROZEN_FILES`（R11）。模块保持在 800 行以内（预计约 170 行）。

## 测试（`tests/test_hover_flows.py`）

假对象（无 Textual App）：`_FakeLsp` 带 `supports()` 和
`async request_hover()`，返回预设字符串（或抛错）；
`_FakePopup` 记录 `show`/`close`/`is_mounted`；
`_FakeView` 带 `size`、`scroll_col`、`scroll_offset.y`、`gutter_width()`；
`_FakePanes.active_view`；一个 `spawn` 桩，用
`asyncio.get_running_loop().create_task` 运行协程函数（仅在测试中转换为 `SpawnFn`）；
以及来自项目 fixture 的真实 `EditorSession`/`Document` 构成的 `session`。
使用 `wait_until` 风格的轮询；将 `HOVER_DEBOUNCE_S` monkeypatch 为 `0`，绝不对固定 sleep 时长断言（`python-coding-style.md` §4.7）。

| 测试 | 安排 / 执行 | 断言 |
| --- | --- | --- |
| `test_request_at_cursor_shows_normalized_docs` | lsp 返回 `"**f()** docs"` | `popup.show` 以该文本及 `(cell, rel_row)`、内部尺寸、gutter、`origin_y=2` 调用一次 |
| `test_empty_result_produces_zero_ui_output` | lsp 返回 `""` | `popup.show` 从未被调用；`popup.close` 被调用；构造函数中不存在 message/status 钩子（禁止通过检查实例 `__dict__` 中是否有 prompt/message 属性来断言 —— 改为断言唯一可观察到的调用是 `close`） |
| `test_empty_result_clears_a_previously_visible_card` | 先显示文档，再让 lsp 返回 `""` | 第二次运行调用 `close` 而不是 `show` |
| `test_whitespace_only_result_is_silent` | lsp 返回 `"  \n "` | 没有 `show`，有一次 `close` |
| `test_request_failure_is_silent` | `request_hover` 抛出 `TimeoutError` | 没有 `show`，有一次 `close`，worker 没有向外抛异常 |
| `test_no_server_guard_does_not_show_card` | `supports(doc) is False` | 没有 spawn worker（未调用 `request_hover`），没有 `show` |
| `test_modal_screen_blocks_request` | `has_modal_screen` 返回 `True` | 没有 `request_hover`，没有 `show` |
| `test_stale_result_after_tab_switch_is_dropped` | 启动 worker，替换 `session.doc`，再解析结果 | 没有 `show`，对新状态也没有 `close` |
| `test_stale_result_after_cursor_move_is_dropped` | 键盘路径，解析前移动 `buf` 光标 | 没有 `show` |
| `test_newer_request_supersedes_older_result` | 两个重叠的请求 | 只有较新 token 能调用 `show` |
| `test_mouse_move_debounces_to_one_request` | 对同一位置快速调用 5 次 `on_mouse_move`，防抖为 0 | 通过轮询确认 `request_hover` 只被调用一次 |
| `test_mouse_move_to_different_position_closes_old_card` | 卡片可见 + 新位置 | 立即调用 `close`，并安排新请求 |
| `test_mouse_move_to_none_dismisses_and_cancels_timer` | 卡片可见 + `on_mouse_move(None)` | 调用 `close`，token 递增，之后没有请求触发 |
| `test_stale_mouse_result_after_pointer_move_is_dropped` | `_target` 改变后再解析 | 没有 `show` |
| `test_card_geometry_falls_back_when_view_size_is_zero` | `view.size.width = 0`、`height = 0` | `show` 收到 `(80, 20)` |

## 验收命令

```powershell
.venv\Scripts\python.exe -m pytest tests/test_hover_flows.py -q -n 1
.venv\Scripts\python.exe -m pytest tests/test_lsp_hover.py tests/test_hover_popup.py -q -n 1
```

两条命令的退出码均为 0。主代理的波次 3 门禁额外运行完整 pyright。

## 风险与回滚

- 风险：当回调在运行中的事件循环之外被调用时（单元测试），`asyncio.get_running_loop()` 不可用。`on_mouse_move` 只能在 App 事件循环内使用 `asyncio.get_running_loop()`；测试中应通过 `asyncio.run` 驱动它，或将防抖设为 0 并显式调用被安排的回调。不要添加静默吞掉缺失循环错误的 `try/except RuntimeError` 回退 —— 应上报该错误。
- 风险：`exclusive=True` 会取消上一个 worker，因此 `CancelledError` 必须传播（manager 会重新抛出它），且不得被记录为失败。
- 风险：门控中过早调用 `close()` 可能造成闪烁。除非卡片确实可见，门控应在触碰 popup 之前返回；`test_no_server_guard_does_not_show_card` 已覆盖这一点。
- 回滚：回退此提交；计划 h 是唯一的消费方（波次 4）。
