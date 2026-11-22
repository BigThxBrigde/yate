# Plan c — generic LSP chooser component (wave 2)

Parent: [../lsp-navigation-plan.md](../lsp-navigation-plan.md).

## Input / output

Input: `editor_components/marks_palette.py:59-119` overlay pattern, issue AC1/AC3/AC4/AC6.
Output: one reusable L2 chooser screen driven by pure data + callbacks.

## Exclusive files

- `yate/editor_components/lsp_chooser.py` (new)
- `tests/test_lsp_chooser.py` (new)

Do not modify `marks_palette.py`, `modals.py`, or any flow module.

## Concrete changes

### `editor_components/lsp_chooser.py`

- Module docstring: explains this is a read-only L2 chooser for LSP results,
  driven by injected rows/callbacks; no App handle, no LSP state (R3/R13).
- `from __future__ import annotations`, absolute imports only.
- `@dataclass(frozen=True) class LspRow` with fields:
  `label: str`, `detail: str`, `uri: str`, `row: int`, `col: int`,
  `end_row: int`, `end_col: int`, `kind: str`. Positions are 0-based.
- `class LspChooserScreen(OverlayScreen)` (from `yate.editor_components.modals`):
  - `__init__(self, rows: list[LspRow], title: str, on_pick: Callable[[LspRow], None]) -> None`.
  - `BINDINGS = [("enter", "pick", "select row")]`.
  - `compose()` yields `Static(id="overlay-body")` plus a `.hint` Static
    inside `OverlayScroll(id="overlay")` (same ids as `marks_palette.py:85-89`;
    component-owned, no shell CSS change, R9 precedent).
  - `on_mount()` paints once and calls `theme.attach(self, self._paint)`;
    `on_unmount()` calls `theme.detach(self)` (R13). The shared
    `OverlayScreen` base already wires slim scrollbars (R15) — do not add a
    second class-level patch.
  - `on_key(event: Key)`: consume up/down only, `event.stop()` +
    `event.prevent_default()` after consumption (R10); wrap selection.
  - `_body_text() -> Text`: header with *title*, then rows formatted as
    ` > {label:<32} {detail:<20} {file}:{line+1}` with theme styles; empty
    rows render `"  (no results)"`. Use `uri_file_name(uri)` for the file name.
  - `action_pick()`: call `self._on_pick(rows[self._selected])` and `dismiss()`.
  - Expose `selected_row` property for tests.

No new `.tcss` file: `OverlayScreen` owns the frozen `#overlay` ids and styles.

## Tests (`tests/test_lsp_chooser.py`)

- `test_lsp_chooser_renders_label_detail_and_location`: two `LspRow`s; after
  mount, `#overlay-body` text contains both labels, `a.py:3` and `b.py:7`.
- `test_lsp_chooser_enter_calls_on_pick_with_selected_row`: move down, press
  enter, assert callback received the second row and screen dismissed.
- `test_lsp_chooser_up_down_wraps_and_stops_event`: from row 0 press up -> last
  row selected; assert `event.stop` / `prevent_default` called (stub Key).
- `test_lsp_chooser_empty_rows_show_placeholder_and_ignore_enter`: no rows ->
  "(no results)" visible, callback not called.
- `test_lsp_chooser_uses_theme_attach_detach`: monkeypatch `theme.attach/detach`,
  mount/unmount, assert one call each.

Use the Textual pilot pattern from `tests/test_marks_palette.py` (find the
actual filename under `tests/`; do not modify it).

## Acceptance commands

```powershell
.venv\Scripts\python.exe -m pytest tests/test_lsp_chooser.py -q
.venv\Scripts\python.exe -m pyright yate/editor_components/lsp_chooser.py tests/test_lsp_chooser.py
```

Exit 0 required.

## Risk / rollback

Risk: `OverlayScreen` may require a mounted App for `theme.attach`; reuse the
exact pilot fixture from the marks tests. Risk: R15 guard scans all L2 modules
defining scrollable subclasses — this screen defines none (it only instantiates
`OverlayScroll`), so no guard registration is needed. Rollback: delete the two
new files; no other wave imports them until wave 3.
