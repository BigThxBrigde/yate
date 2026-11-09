# Plan i — smoke scenarios (wave-5)

Parent: [overview.md](overview.md) · Main plan: [../lsp-hover-docs-plan.md](../lsp-hover-docs-plan.md), §8
Depends on: plan h (the app owns `hover_popup` / `hover` / `MouseFlows` callback).

## Input

- `tools/smoke_test/scenarios/__init__.py:1-7` (each module exports
  `SCENARIOS: list[Scenario]`), `:13-36` (imports), `:51-76` (single
  aggregation point).
- `tools/smoke_test/scenarios/_base.py:3-11` (scenario signature
  `async def (tmp: Path) -> ScenarioResult`), `:31-37` (`_COMMAND_KEY="f5"`,
  `_DRAIN_TIMEOUT_S`), `:93-98` (`message_text`), `:111-128` (`wait_until`,
  the only allowed polling primitive).
- `tools/smoke_test/harness.py:191-211` (`Check(label, expected, actual)`),
  `:214-239` (`ScenarioResult`), `:242-255` (`Scenario(name, run, tags)`),
  `:361` (`new_app()`), `:539-706` (runner and selection).
- `tools/smoke_test/scenarios/core.py:65-79` (`_keymap_toggle` presses
  `ctrl+/`), `tools/smoke_test/scenarios/edit.py:48-52` (existing `ctrl+k`
  delete-line assertion — must stay green).

## Exclusive files

- `tools/smoke_test/scenarios/hover.py` (new)
- `tools/smoke_test/scenarios/__init__.py`

## Concrete changes

1. `tools/smoke_test/scenarios/hover.py` — module docstring (ASCII English),
   `from __future__ import annotations`, absolute imports, full annotations,
   `SCENARIOS: list[Scenario]` at the bottom. Two scenarios with tag
   `("hover",)`:
   - `"hover_docs_key_is_silent_without_a_server_in_both_keymaps"`:
     `app = new_app()` inside `app.run_test()` (follow `_base.py`); press
     `"f7"` in the default vsc keymap, then `pilot.press("ctrl+/")` and press
     `"f7"` again. Use `wait_until(pilot, predicate)` for the worker drain,
     never a fixed sleep. Checks:
     - `Check("keymap", "vim", app.editor.keymaps.active.name)`,
     - `Check("card", False, app.editor.hover_popup.is_open)`,
     - `Check("message", "", message_text(app))`,
     - `Check("lines", expected_lines, list(app.editor.session.doc.buffer.lines))`
       (no accidental edit by the new key),
     - `Check("no_placeholder", False, "no documentation" in plain_text(app).lower())`.
   - `"hover_docs_non_drag_mouse_move_is_not_consumed"`:
     with `support_mouse` on, post a non-drag `MouseMove` through the view's
     `handle_mouse` path (or via `pilot` mouse events following the pattern in
     `tests/test_app_mouse.py`); assert the event handler returns `False`,
     the cursor/buffer are unchanged, no card appears, and no message is
     written. Add a second phase with `support_mouse=False` asserting the
     hover callback is not invoked (monkeypatch
     `app.editor.hover.on_mouse_move` with a counter if the harness allows it;
     otherwise assert only the observable state: card closed, no message).
   - No real LSP server is started (the harness disables it); the scenarios
     deliberately exercise the **AC5 silent path** and the **AC2/AC3 key and
     mouse plumbing**, not a real hover payload.
2. `tools/smoke_test/scenarios/__init__.py`: add
   `from tools.smoke_test.scenarios.hover import SCENARIOS as _HOVER` to the
   import block (`:13-36`) and `_HOVER` to the `SCENARIOS` aggregation list
   (`:51-76`), preserving the existing order convention (insert near the
   `_COMPLETION` entry). Update `__all__` only if the module lists the aliases.
3. Do not change any existing scenario, the harness, `edit.py`'s `ctrl+k`
   assertion, or any product code.

## Acceptance commands

```powershell
cd D:/Programming/yate-lsp-hover-docs
.venv\Scripts\python.exe -m tools.smoke_test run --jobs 4
.venv\Scripts\python.exe -m pytest tests/test_hover_docs.py tests/test_hover_integration.py -q -n 1
```

Both exit codes 0; smoke must report all scenarios passing (the baseline count
plus 2). If a scenario fails under `--jobs 4`, re-run with `--jobs 1` before
concluding; a genuine timing assumption must be fixed in the scenario, not
recorded as a flake.

## Risks and rollback

- Risk: headless Textual may not synthesize `f7` as `\x1b[18~`. If the scenario
  shows the key was not dispatched, log the observed `event.key` / raw mapping
  from `keyproto.event_to_raw`, report the deviation, and use the same public
  key constant everywhere — never add a second hard-coded key string.
- Risk: `new_app()` may not expose `editor.hover_popup` if mounting is deferred.
  Use `wait_until(pilot, lambda: app.editor.hover_popup.is_mounted)` before the
  first assertion.
- Risk: the mouse phase may need a view reference; follow
  `tests/test_app_mouse.py::_mouse_app` for the geometry rather than inventing
  a new helper.
- Rollback: revert this commit; no other plan depends on smoke.
