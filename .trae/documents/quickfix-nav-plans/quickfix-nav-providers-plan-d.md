# Plan d — Diagnostics, project search and references providers

Parent: [`../quickfix-nav-plan.md`](../quickfix-nav-plan.md). Rules: [`../../rules/architecture-boundaries.md`](../../rules/architecture-boundaries.md).

## Input / output

Input: wave c wired flow and actions. Output: all three AC providers publish into the same list; AC4-AC7 behaviors covered.

## Exclusive files

- `yate/flows/lsp_sync.py`
- `yate/flows/overlay_flows.py`
- `yate/editor_components/find_replace.py`
- `yate/flows/lsp_navigation_flows.py`
- `yate/editor_compose.py` (late provider callback injection only)
- `tests/test_quickfix_providers.py` (new)

## Concrete changes

1. `yate/flows/lsp_sync.py`: add injected `set_quickfix: Callable[[str, tuple[QuickFixEntry, ...], str], None]` (default `None` is not acceptable — all call sites pass it; use a required keyword). In `show_diagnostics()` keep `lsp.diagnostics_for(doc)` and `counts_for(doc)`; build entries with `path=doc.path or Path(doc.name)` (the existing API already returns empty for unsaved docs), `row=d.start_row`, `col=d.start_col`, `label=d.message`, `detail=f"[{d.source}]"` when present, `severity=labels.get(...)`; call `set_quickfix("diagnostics", tuple(entries), title)`. On empty, call `set_quickfix("diagnostics", (), "no diagnostics")` and keep the existing `"no diagnostics"` message. Remove the `OutputScreen` overlay path for `:diagnostics` (retained class remains used elsewhere).
2. `yate/editor_components/find_replace.py`: add keyword `on_results: Callable[[list[FileMatch]], None] | None = None` to `__init__`; after `_search_worker` attaches and assigns `_results/_flat`, call `on_results(list(self._results))`; after `_clear_results`, call `on_results([])`. In `_open_current()` call `self._session.push_jump()` immediately before `self._reveal(path, match.row, match.start)` (T3 closure); do not change `r`/`a` branches or up/down clamping.
3. `yate/flows/overlay_flows.py`: add `on_search_results: Callable[[list[FileMatch]], None] | None = None` to `__init__`; pass it as `on_results=` in the `FindReplaceScreen(...)` construction at lines 310-318. Import `FileMatch` from `yate.editor_core.project_search` (L0 → L3 legal).
4. `yate/flows/lsp_navigation_flows.py`: add keyword `set_quickfix` with the same signature as LspSync. In `_worker_references` after `_stale` check: map each `LspLocation` through `_location_row`, publish `set_quickfix("references", tuple(rows_as_entries), "references")`, and still call `_chooser(...)` for the immediate selection path. Empty references call `set_quickfix("references", (), "no references")` and keep the existing explicit message. Add `session.push_jump()` at the start of `_jump_to_row` (before `_open_path`/cursor write) so chooser and `gd` jumps join the jump list. Panel jumps use `QuickFixFlows.jump_to` and do not call `_jump_to_row`, so no double push.
5. `yate/editor_compose.py`: build adapters that convert `FileMatch`/`LspRow` to `QuickFixEntry` (module-level private helpers or small local functions) and inject `set_quickfix=ed.quickfix_flows.set_results` into `LspSync` and `LspNavigationFlows`, `on_search_results=...` into `OverlayFlows`. Keep all conversions concrete; no `Protocol`, `Any` or new data layer.

## Tests (`tests/test_quickfix_providers.py`)

- `test_diagnostics_publish_entries_including_severity_and_position`: real `LspManager` with `diagnostics_for` monkeypatched to two `Diagnostic`s; call `show_diagnostics()`; assert provider name, `(row,col)` values, severity labels, source detail, and no `OutputScreen` push.
- `test_diagnostics_empty_publishes_empty_set_and_message`: no diagnostics; assert empty tuple published and message `no diagnostics`.
- `test_project_search_publishes_flat_entries_and_records_jump`: real `EditorSession`, `FileMatch` fixture with two rows; call the screen's `_search_worker` path or direct `_on_results` hook; assert two entries with path/row/col/snippet; invoke `_open_current()` with a recording `reveal`; assert `push_jump` grew the back stack by one before reveal.
- `test_references_publish_then_chooser_still_opens`: `_Harness` from `tests/test_lsp_navigation_flows.py`; fake LSP references two locations; run `find_references()`; assert `set_quickfix` received two entries and one chooser was pushed; dismiss chooser; assert quickfix list survives.
- `test_references_empty_publishes_empty_and_warns`: fake empty references; assert empty set and message `No references found`.
- `test_chooser_jump_records_jump_once`: call `_jump_to_row` with a known row; assert back stack grows exactly one and cursor lands at the row.

## Acceptance commands

```powershell
.venv\Scripts\python.exe -m pytest tests/test_quickfix_providers.py tests/test_app_find_replace.py tests/test_lsp_navigation_flows.py tests/test_lsp_navigation.py -q
.venv\Scripts\python.exe -m pyright yate/flows/lsp_sync.py yate/flows/overlay_flows.py yate/editor_components/find_replace.py yate/flows/lsp_navigation_flows.py yate/editor_compose.py tests/test_quickfix_providers.py
```

## Risks / rollback

- Risk: `doc.path is None` for unsaved buffers; diagnostics API already returns `[]`, so the empty state is deterministic.
- Risk: stale async reference response after document change; existing `_snapshot/_stale` guard runs before publish, so no stale entry is written.
- Risk: double jump push from chooser then quickfix next; tests assert exact stack growth per path.
- Rollback: revert this wave; panel/flow remain usable but empty until providers are restored.
