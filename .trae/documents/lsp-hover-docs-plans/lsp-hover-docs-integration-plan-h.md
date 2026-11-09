# Plan h — wiring, architecture guards, integration (wave-4)

Parent: [overview.md](overview.md) · Main plan: [../lsp-hover-docs-plan.md](../lsp-hover-docs-plan.md), §6
Depends on: all wave 1-3 plans, especially plan g's `HoverFlows.__init__`
signature and `HoverPopup(id=...)`.

## Input (exact baseline locations)

- `yate/editor.py:101-139` (class attributes), `:164-175` (assembly order),
  `:327-336` (`on_mount` popup mount), `:484-488` (`_refresh_lsp`), `:500-506`.
- `yate/editor_compose.py:125-142` (`_build_widgets`, `CompletionPopup()`),
  `:213-241` (`_build_pane_stack`, `MouseFlows(...)`), `:295-330`
  (`LspSync` / `CompletionFlows` construction).
- `yate/editor_dispatch.py:40-51` (`_handle_key` entry), `:189-197`
  (`_cancel_mouse_state`).
- `yate/flows/mouse_flows.py:28-58`, `:60-67`, `:69-134`.
- `yate/actions.py:26-32`, `:209-238` (view group).
- `tests/test_architecture.py:141` (`_LAYER_RANKS`), `:198` (`UI_FROZEN_FILES`),
  `:360` (`SIZE_EXEMPT_FILES`), `:436` (`SCROLLABLE_BASES`), `:1556-1597`
  (R15 guard).
- `tests/conftest.py:311-331` (`wait_until`), `:334-344`
  (`plain_text` / `message_text`), `:347-377` (`make_key_ui` /
  `make_action_context`).
- `tests/test_action_table.py:20-135` (`_StubEditor` hook list).

## Exclusive files

- `yate/editor.py`
- `yate/editor_compose.py`
- `yate/editor_dispatch.py`
- `yate/flows/mouse_flows.py`
- `yate/actions.py`
- `tests/test_architecture.py`
- `tests/test_hover_integration.py` (new)
- `tests/test_app_mouse.py`
- `tests/test_action_table.py`
- `tests/test_editor_dispatch.py`
- `tests/test_dispatch_guards.py`

`.trae/rules/architecture-boundaries.md` is **not** touched by this plan: after
the new guard case is added (37 → 38 architecture cases), the main agent
updates the rule's §六 count/table during step 7 (document write-back), with
the real measured number.

## Concrete changes

### 1. `yate/editor.py`

- `:101-139`: add `hover_popup: HoverPopup` and `hover: HoverFlows` next to
  `completion_popup` / `completion`; add the two imports at the top with the
  existing grouped absolute imports (no new upward edge: Editor is L3).
- `:164-175`: extend the assembly-order comment with "hover flows are built
  after `panes` and before `mouse_flows`, which receives its `on_mouse_move`
  callback".
- `:336`: after `await self.editor_col.mount(self.completion_popup)`, add
  `await self.editor_col.mount(self.hover_popup)`. Two separate awaits keep the
  existing mount semantics.
- Do **not** add any `def apply_theme` / `.styles.background` painting (T2),
  and do not call `lsp.notify_edit` from the hover path (AC6).

### 2. `yate/editor_compose.py`

- `_build_widgets` (`:138`): `ed.hover_popup = HoverPopup(id="hover-docs")`
  (R9: id supplied by the dispatch layer; frozen in `hover-popup.tcss`).
- `_build_pane_stack`: after `ed.panes = PaneManager(...)` (`:225-231`) and
  before `ed.mouse_flows = MouseFlows(...)` (`:233`), construct

  ```python
  ed.hover = HoverFlows(
      spawn=ed.app.run_worker,
      lsp=ed.lsp,
      session=ed.session,
      panes=ed.panes,
      popup=ed.hover_popup,
      has_modal_screen=ed.has_modal_screen,
  )
  ```

  then pass `on_hover_move=ed.hover.on_mouse_move` into `MouseFlows(...)`.
  Update the factory docstring (`:213-222`) to list `HoverFlows`.
- No App handle is stored in any flow (guard
  `test_flow_modules_hold_no_app_handle`).

### 3. `yate/flows/mouse_flows.py`

- `__init__` (`:28-41`): add
  `on_hover_move: Callable[[Pos | None], None] | None = None` as the **last**
  parameter with a default so every existing direct construction keeps
  working; store it. Import `Pos` from `yate.editor_core.buffer` (L0).
- Add `_notify_hover(self, pos: Pos | None) -> None` calling the callback when
  present (plain `Callable`, no protocol).
- `handle_view_mouse` gate branch (`:45-49`): call `_notify_hover(None)`
  before returning `False`, so turning `support_mouse` off removes a visible
  card.
- `_on_move` (`:96-106`): when **not dragging** (`not self._dragging or
  event.button != LEFT_BUTTON`), compute
  `pos = view.buffer_pos_from_mouse(event)`, call `_notify_hover(pos)`, and
  `return False` — the event stays unconsumed (AC3 / "不改变既有鼠标行为").
  At the top of the drag branch call `_notify_hover(None)`.
- `_on_down`, `_on_up`, `_on_click` and `cancel_drag`: call
  `_notify_hover(None)` before their existing logic (editing interaction
  dismisses the card). Keep all existing return values and refresh calls
  unchanged.

### 4. `yate/editor_dispatch.py`

- `_handle_key` (`:40-52`): after the modal-screen guard, add one idempotent
  line `ed.hover.dismiss()`. It must **not** `return` and must not consume the
  key: every key keeps its existing dispatch path (R10, AC6, "卡片不吞键").
  This covers cursor moves, editing keys and `Esc` in one place.
- If `tests/test_editor_dispatch.py` / `tests/test_dispatch_guards.py` build a
  stub editor, add a `hover` object with a no-op `dismiss()` to that stub —
  do not introduce `getattr` fallbacks in production code.

### 5. `yate/actions.py`

- In the view group (`:209-236`) add
  `reg("show_hover_docs", lambda ctx: editor.hover.request_at_cursor(),
  "Show API documentation at cursor")`.
- `tests/test_action_table.py`: extend `_StubEditor`'s recorded hook list with
  `hover` (a recording stand-in with `request_at_cursor`) and add a test
  `test_show_hover_docs_action_forwards_to_hover_flows` asserting
  `registry.execute("show_hover_docs", ctx) is True` and the call count is 1.

### 6. `tests/test_architecture.py`

- `UI_FROZEN_FILES` (`:198`): add the exact set of L2 modules imported by
  `yate/flows/hover_flows.py`, e.g.
  `"flows/hover_flows.py": {"yate.editor_components",
  "yate.editor_components.hover_popup", "yate.editor_components.view",
  "yate.editor_components.theme", "yate.editor_components.panes"}` — reduce
  the set to the actual imports; R11 forbids a wider whitelist.
- Add `test_hover_key_is_shared_and_identical`: AST-assert that
  `yate/keymaps/vsc.py` and `yate/keymaps/vim.py` each reference
  `HOVER_DOC_KEY` inside `build_bindings` and contain no literal `"<f7>"`;
  runtime-assert `VscKeymap().lookup(parse_key(HOVER_DOC_KEY))` and
  `VimKeymap().lookup(...)` both resolve to `show_hover_docs`. This makes a
  one-sided key edit fail the architecture gate (AC2).
- Do not change `_LAYER_RANKS`, `SIZE_EXEMPT_FILES`, `UPWARD_EDGES_FROZEN` or
  `SCROLLBAR_EXEMPT`. Expected architecture result: **38 passed** (37 + 1).

### 7. `tests/test_hover_integration.py` (new)

Use Textual pilots (`app.run_test()`), a fake READY LSP client injected the way
`tests/test_app_lsp.py` does, `wait_until` for async workers, and
`plain_text`/`message_text` helpers for UI-output assertions. No real server
(`tests/conftest.py:41` forces `YATE_PYTHON_LSP=off`).

| Test | Arrange / Act | Assert |
| --- | --- | --- |
| `test_f7_shows_hover_docs_in_vsc_keymap` | fake hover payload with signature + docstring, `pilot.press("f7")` | `app.editor.hover_popup.is_open is True` and body holds the Markdown text |
| `test_f7_shows_hover_docs_in_vim_keymap_after_ctrl_slash_toggle` | `pilot.press("ctrl+/")`, then `pilot.press("f7")` | same card; `app.editor.keymaps.active.name == "vim"` |
| `test_null_hover_result_has_zero_ui_output` | fake returns `None` | card closed, `message_text(app) == ""`, status-bar text snapshot unchanged, `plain_text(app)` unchanged |
| `test_empty_whitespace_and_empty_array_results_have_zero_ui_output` | parametrized payloads `{}`, `"  "`, `[]` | same three assertions |
| `test_failed_and_timed_out_requests_are_silent` | fake raises / never resolves (tiny patched timeout) | same three assertions |
| `test_card_is_cleared_when_a_later_result_is_empty` | first payload has docs, second is `None` | after the second `f7`, `is_open is False`, no message/status change |
| `test_typing_dismisses_card_without_swallowing_key` | card visible, `pilot.press("x")` | card closed **and** `x` inserted into the buffer (vsc) |
| `test_escape_dismisses_card_and_keeps_existing_behavior` | card visible, `pilot.press("escape")` | card closed; existing clear_selection/keymap behavior unchanged |
| `test_hover_does_not_start_server_or_open_document` | no READY client, monkeypatch `ensure_client` / `on_document_shown` to fail | `pilot.press("f7")` shows nothing and neither method is called |
| `test_switching_buffer_drops_stale_hover_response` | delayed response, switch tab before it resolves | no card appears for the old document |
| `test_cursor_move_drops_stale_keyboard_response` | delayed response, move cursor before it resolves | no card appears |
| `test_support_mouse_off_disables_hover_and_keeps_mouse_behavior` | `:set support_mouse off` (or construct config with it off), post a non-drag `MouseMove` | `request_hover` call count 0, buffer unchanged, event not consumed |
| `test_support_mouse_on_non_drag_move_triggers_debounced_hover` | debounce patched to 0, `MouseMove` over a symbol | one request; card shows docs |
| `test_non_drag_mouse_move_is_not_consumed` | direct `MouseFlows.handle_view_mouse` with a move | returns `False` (existing behavior), `event.stop` not called |
| `test_bind_key_both_retargets_hover_action_in_both_keymaps` | `ExtensionAPI.bind_key(..., keymap="both")` with a new key (use the fixture from `tests/test_extensions.py`) | both `vsc` and `vim` resolve the new key to `show_hover_docs`; old key no longer does |

### 8. `tests/test_app_mouse.py`

Add `test_non_drag_mouse_move_keeps_existing_selection_and_cursor_behavior`
(no hover card, cursor unchanged, no refresh storm), guarding that the new
callback injection did not alter the existing mouse contract.

## Acceptance commands

```powershell
.venv\Scripts\python.exe -m pytest tests/test_hover_integration.py -q -n 1
.venv\Scripts\python.exe -m pytest tests/test_app_mouse.py tests/test_action_table.py tests/test_editor_dispatch.py tests/test_dispatch_guards.py tests/test_architecture.py -q -n 1
.venv\Scripts\python.exe -m pytest tests/test_hover_integration.py tests/test_architecture.py -q -n auto
```

All exit codes 0; the last command checks the parallel/CI-like path. Any flake
must be re-run with `-n 1` and the test fixed, not excused. Main-agent wave-4
gate also runs full pyright.

## Risks and rollback

- Risk: `ed.hover.dismiss()` on every key invalidates an in-flight request
  started by the same `f7` press? No — dismiss runs **before** the action
  executes; the action then increments a fresh token. Covered by
  `test_f7_shows_hover_docs_in_vsc_keymap`.
- Risk: `pilot.press("f7")` may not produce `\x1b[18~` in headless Textual.
  `key_codec._NAMED_KEYS` maps it; if the pilot uses a different spelling,
  assert via `event_to_raw` first and report the deviation with the actual
  event key before adapting the test.
- Risk: new `editor_components` imports in `hover_flows.py` fail R11 until the
  whitelist entry lands — both are in this same plan, so keep them in sync.
- Risk: architecture count changes to 38; the main agent must write the real
  number back into `architecture-boundaries.md` §六 at step 7.
- Rollback: revert this single wave commit; wave-5 smoke is the only consumer.
