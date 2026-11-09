# Plan g — `HoverFlows` orchestration (wave-3, L3)

Parent: [overview.md](overview.md) · Main plan: [../lsp-hover-docs-plan.md](../lsp-hover-docs-plan.md), decisions D4/D5/D6
Depends on: plan d (`LspManager.request_hover`), plan e (`HoverPopup.show/close`),
plan a (normalization).

## Input

- `yate/flows/completion_flows.py:87-113`, `:145-184`, `:186-281`
  (debounce with `call_later`, `SpawnFn` worker, `_stale()` token-ish logic,
  `_show_items()` geometry: `theme.char_to_cell`, `editor.size`, `gutter_width`,
  `origin_y=2`).
- `yate/flows/__init__.py:31-33` (`SpawnFn = Callable[..., Worker[object]]`).
- `yate/editor_lsp/manager.py:216-218` (`supports(doc)`).
- `architecture-boundaries.md` §三.8 (new L3 flow module checklist), R11
  (registration done by plan h), R12 (tracing), R10 (no swallowed keys —
  handled in plan h).

## Exclusive files

- `yate/flows/hover_flows.py` (new)
- `tests/test_hover_flows.py` (new)

## Concrete changes (`yate/flows/hover_flows.py`)

Module docstring (ASCII English), `from __future__ import annotations`,
imports grouped stdlib / third-party / `yate`, no `yate.editor` / `yate.app`,
no `Any` / `TYPE_CHECKING` / relative imports.

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

This exact signature is the contract consumed by plan h; do not change it
without writing back to the overview first.

Fields: `_timer: asyncio.TimerHandle | None = None`, `_token: int = 0`,
`_source: str = ""`, `_target: Pos | None = None`,
`_doc_path: str | None = None`.

Public API:

1. `request_at_cursor() -> None` — keyboard path. Snapshot
   `doc = self.session.doc`, `pos = (buf.row, buf.col)`; call `_schedule(doc,
   pos, "key")` immediately (no debounce).
2. `on_mouse_move(pos: Pos | None) -> None` — callback injected into
   `MouseFlows` by plan h.
   - `None` (pointer left the text area / gate off / drag started) →
     `self.dismiss()`.
   - a different position than `_target` → `self.popup.close()` immediately
     (no stale card while the new debounce runs), then cancel the previous
     timer and schedule `loop.call_later(HOVER_DEBOUNCE_S,
     self._schedule_mouse, pos)`.
   - the same position while a card is visible → do nothing (no flicker).
3. `dismiss() -> None` — cancel timer, `_token += 1` (invalidates in-flight
   results), `self.popup.close()`. Idempotent; never writes to the message or
   status bar.
4. `_schedule(doc: Document, pos: Pos, source: str) -> None` — guard
   `self._has_modal_screen()` and `not self.lsp.supports(doc)` → `self.dismiss()`
   for the latter is **not** allowed (would close a card without feedback on a
   mere guard); instead `return` silently for modal, and for no-server simply
   `return` after `popup.close()` only when a card is visible. Record
   `_doc_path = str(doc.path) if doc.path is not None else None`, `_source`,
   `_target`, increment `_token`, and spawn:
   `self._spawn(partial(self._worker, doc, pos, token), group="lsp-hover",
   exclusive=True, exit_on_error=False)` (coroutine *function*, not an eager
   coroutine).
5. `async def _worker(self, doc: Document, pos: tuple[int, int], token: int) -> None`:
   - `text = await self.lsp.request_hover(doc, pos[0], pos[1])` wrapped in
     `try/except Exception:  # noqa: BLE001 - a failed request must be silent`
     → `text = ""` + `log.debug(..., exc_info=False)` (lazy `%`).
   - `if self._stale(doc, pos, token): return` (drop, no UI change).
   - `if not text.strip(): self.popup.close(); return` — **zero UI feedback**,
     including the "card was visible then the new result is empty" case.
   - `view = self.panes.active_view`; `None` → return.
   - `buf = doc.buffer`; `line = buf.lines[pos[0]] if pos[0] < buf.line_count else ""`;
     `cell = theme.char_to_cell(line, pos[1], buf.tab_width) - view.scroll_col`;
     `rel_row = pos[0] - view.scroll_offset.y`;
     `self.popup.show(text, (cell, rel_row),
     (view.size.width or 80, view.size.height or 20),
     view.gutter_width(), origin_y=2)`.
   - No prompt/message/report/status calls anywhere in this module.
6. `_stale(doc, pos, token) -> bool`:
   - `token != self._token`, `self.session.doc is not doc`,
     `doc.path` string != `_doc_path`, `not self.popup.is_mounted`;
   - for `_source == "key"`: `session.doc.buffer.row/col != pos`;
   - for `_source == "mouse"`: `self._target != pos`.
   - Return `True` on any mismatch; stale responses are discarded, never
     displayed and never close an unrelated newer card.

Widget imports (`HoverPopup`, `PaneManager`, `EditorView`, `theme`) are L3→L2
and must be registered in `UI_FROZEN_FILES` by plan h (R11). Keep the module
under 800 lines (expected ~170).

## Tests (`tests/test_hover_flows.py`)

Fakes (no Textual App): `_FakeLsp` with `supports()` and
`async request_hover()` returning a preset string (or raising),
`_FakePopup` recording `show`/`close`/`is_mounted`,
`_FakeView` with `size`, `scroll_col`, `scroll_offset.y`, `gutter_width()`,
`_FakePanes.active_view`, a `spawn` shim that runs the coroutine function with
`asyncio.get_running_loop().create_task` (cast to `SpawnFn` in the test only),
and `session` with a real `EditorSession`/`Document` from the project fixtures.
Use `wait_until`-style polling; monkeypatch `HOVER_DEBOUNCE_S` to `0` and never
assert on a fixed sleep duration (`python-coding-style.md` §4.7).

| Test | Arrange / Act | Assert |
| --- | --- | --- |
| `test_request_at_cursor_shows_normalized_docs` | lsp returns `"**f()** docs"` | `popup.show` called once with that text and `(cell, rel_row)`, inner size, gutter, `origin_y=2` |
| `test_empty_result_produces_zero_ui_output` | lsp returns `""` | `popup.show` never called; `popup.close` called; no message/status hook exists in the constructor (assert by inspecting the instance `__dict__` for prompt/message attributes is forbidden — instead assert the only observable calls are `close`) |
| `test_empty_result_clears_a_previously_visible_card` | first show docs, then lsp returns `""` | second run calls `close` and not `show` |
| `test_whitespace_only_result_is_silent` | lsp returns `"  \n "` | no `show`, one `close` |
| `test_request_failure_is_silent` | `request_hover` raises `TimeoutError` | no `show`, one `close`, no exception out of the worker |
| `test_no_server_guard_does_not_show_card` | `supports(doc) is False` | no worker spawned (`request_hover` not called), no `show` |
| `test_modal_screen_blocks_request` | `has_modal_screen` returns `True` | no `request_hover`, no `show` |
| `test_stale_result_after_tab_switch_is_dropped` | start a worker, replace `session.doc`, resolve | no `show`, no `close` on the newer state |
| `test_stale_result_after_cursor_move_is_dropped` | key path, move `buf` cursor before resolving | no `show` |
| `test_newer_request_supersedes_older_result` | two overlapping requests | only the newer token can call `show` |
| `test_mouse_move_debounces_to_one_request` | 5 rapid `on_mouse_move` calls with the same pos, debounce 0 | `request_hover` called once via polling |
| `test_mouse_move_to_different_position_closes_old_card` | visible card + new pos | `close` called immediately, new request scheduled |
| `test_mouse_move_to_none_dismisses_and_cancels_timer` | visible card + `on_mouse_move(None)` | `close` called, token advanced, no later request fires |
| `test_stale_mouse_result_after_pointer_move_is_dropped` | resolve after `_target` changed | no `show` |
| `test_card_geometry_falls_back_when_view_size_is_zero` | `view.size.width = 0`, `height = 0` | `show` receives `(80, 20)` |

## Acceptance commands

```powershell
cd D:/Programming/yate-lsp-hover-docs
.venv\Scripts\python.exe -m pytest tests/test_hover_flows.py -q -n 1
.venv\Scripts\python.exe -m pytest tests/test_lsp_hover.py tests/test_hover_popup.py -q -n 1
```

Both exit codes 0. Main-agent wave-3 gate adds full pyright.

## Risks and rollback

- Risk: `asyncio.get_running_loop()` is unavailable when the callback is called
  outside a running loop (unit tests). `on_mouse_move` must use
  `asyncio.get_running_loop()` only inside the App event loop; in tests drive it
  through `asyncio.run` or set the debounce to 0 and call the scheduled
  callback explicitly. Do not add a `try/except RuntimeError` fallback that
  silently swallows missing-loop errors — report it instead.
- Risk: `exclusive=True` cancels the previous worker, so `CancelledError` must
  propagate (manager re-raises it) and must not be logged as a failure.
- Risk: an over-eager `close()` on a guard could flash. Guards return before
  touching the popup unless a card is genuinely visible; covered by
  `test_no_server_guard_does_not_show_card`.
- Rollback: revert this commit; plan h is the only consumer (wave 4).
