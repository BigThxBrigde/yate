# Plan d — L3 flow and editor wiring (wave 3)

Parent: [../lsp-navigation-plan.md](../lsp-navigation-plan.md).

## Input / output

Input: wave a manager methods, wave b action names, wave c chooser row type.
Output: one L3 flow object implementing all user-visible behaviors plus wiring.

## Exclusive files

- `yate/flows/lsp_navigation_flows.py` (new)
- `yate/editor_compose.py`
- `yate/editor.py`
- `tests/test_lsp_navigation_flows.py` (new)

Do not edit keymaps, actions, manager, chooser, architecture tests or docs here.

## Concrete changes

### 1. `flows/lsp_navigation_flows.py`

New L3 flow module following the `HoverFlows` shape (`hover_flows.py:33-59`):

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

Only injected concrete objects/callbacks; no App handle (`test_flow_modules_hold_no_app_handle`).
`PromptBar` comes from `yate.editor_components.commandline` (wave-d correction:
`PromptFlows` has no `prompt_text` method; the bar's `activate(mode, *,
placeholder, on_submit, ...)` API at `commandline.py:315-325` is the prompt
seam). Module-level `NAV_JUMP_KIND = "info"`,
`NAV_TIMEOUT_MESSAGE = "LSP request timed out"`.

Public methods (names must match wave b actions):
`goto_definition()`, `find_references()`, `show_outline()`, `rename_symbol()`,
`show_code_actions()`, `show_signature_help()`.

Common machinery:
- `_snapshot()` captures `doc`, `(row, col)`, `str(doc.path)`, bumps `self._token`.
- `_stale(doc, pos, token)` mirrors `HoverFlows._stale` (`:190-209`): token,
  session doc identity, path, and cursor for keyboard requests. Stale results
  are discarded without messages or UI changes (AC7).
- `_spawn(partial(self._worker_* , ...), group="lsp-navigation", exclusive=True,
  exit_on_error=False)`; workers catch `LspFeatureUnavailable`, `LspFeatureFailed`,
  `TimeoutError` and `Exception` (with `noqa: BLE001` + `log.debug`) and call
  `message(explicit_text, "warning")`, never silent.
- `_chooser(rows, title)` pushes `LspChooserScreen(rows, title, self._jump_to_row)`.
- `_jump_to_row(row: LspRow)`: resolve path via `uri_to_path(row.uri)`;
  `open_path(path)` (wave-d correction: `DocumentFlows.open_path` returns
  `None`); then `doc = session.is_open(path)` (`session.py:243-249`) and if
  `None` -> message and return; set cursor at `(row.row, row.col)`, clear
  anchor, `reveal_cursor()` on all views via `panes.views_for(doc)`;
  `open_path` activates the document; call `refresh()` and
  `message(f"jumped to {file}:{line+1}", "info")`.

Per-method behavior:
- `goto_definition`: request definitions; 0 -> `"No definition found"`; 1 ->
  jump directly; >1 -> chooser titled `Definitions`.
- `find_references`: request references; 0 -> `"No references found"`; otherwise
  chooser titled `References` with `detail = "line N"`.
- `show_outline`: request document symbols; 0 -> "No symbols available"; else
  chooser titled `Outline`, `label` prefixed by `"  "*depth`.
- `rename_symbol`: prompt via the injected `PromptBar` (`prompt.activate(
  "lsp_rename", placeholder="New symbol name", on_submit=self._on_rename))`;
  cancelling with ESC never calls `on_submit` and is a no-op. The submit
  callback snapshots doc/pos/token, spawns the rename worker; if
  `unsupported` -> warning message; else `_apply_workspace_edit(edit)`.
- `_apply_workspace_edit(edit)`: pre-resolve every URI to a path; if any path is
  missing/unreadable -> message, no changes. Snapshot `buffer.get_text()` and
  cursor for each affected document. Apply text edits per document bottom-up
  by `(start_row, start_col)` descending with `buffer.replace_range`; on any
  exception restore each snapshot with `replace_range` over the full old range.
  Call `refresh()`; message `Renamed N occurrence(s)` or the failure text. No
  disk writes; unopened targets are opened through `open_path`.
- `show_code_actions`: request actions; 0 -> message; else chooser with titles;
  on pick, apply `action.edit` when present, else `execute_command(...)` when a
  command name exists, else message "action cannot be applied".
- `show_signature_help`: request signature; `None`/empty -> message; else
  compute anchor via `panes.active_view.screen_anchor(row, col)` and call
  `popup.show(text, anchor, size, gutter, origin_y=2)` (same API as hover).
  Use token staleness before showing; close popup when stale.

### 2. `editor_compose.py`

Construct the flow near `HoverFlows` (`:250-257`), after `ed.overlays` and
`ed.document_flows` exist (the existing `NavigationFlows` block at `:304-311`
is the model). Inject `spawn=ed.app.run_worker`, `lsp=ed.lsp`, session, panes,
`popup=ed.hover_popup`, `open_path=ed.document_flows.open_path`,
`push_overlay=ed.overlays.push`, `message=ed.message`, `refresh=ed.refresh_ui`,
`has_modal_screen=ed.has_modal_screen`, `prompt=ed.prompt_bar`.
No `PromptFlows` change is needed: the corrected prompt seam is `PromptBar.activate`.

### 3. `editor.py`

Add `lsp_navigation: LspNavigationFlows` to the class attribute table near
`hover` (`:103-148`) and update the assembly-order comment. No other changes.

## Tests (`tests/test_lsp_navigation_flows.py`)

Use fake manager returning pre-baked results and stub injected callbacks:
- `test_goto_definition_single_location_jumps_cross_file`: one location in other file -> `open_path` called with that path, buffer cursor equals target row/col, message emitted.
- `test_goto_definition_multiple_locations_open_chooser`: two locations -> one `LspChooserScreen` push with two rows.
- `test_goto_definition_without_provider_reports_message`: `LspFeatureUnavailable` -> warning message contains `definition`, no chooser, no exception.
- `test_find_references_empty_reports_message`: empty list -> "No references found".
- `test_find_references_rows_are_navigable`: two rows -> picking second calls `open_path` with its URI path and correct line.
- `test_show_outline_uses_selection_range_and_depth`: nested symbols -> chooser labels indented and jump target from `selectionRange`.
- `test_rename_applies_workspace_edit_bottom_up`: two edits in one buffer -> both applied, one refresh, success message.
- `test_rename_rolls_back_all_buffers_on_failure`: second edit invalid -> all buffers restored to original text, warning message.
- `test_rename_unsupported_edit_reports_message`: `unsupported=True` -> warning, no mutation.
- `test_show_code_actions_executes_command_without_edit`: action with command only -> `execute_command` called with name/args.
- `test_show_signature_help_uses_hover_popup`: signature text -> `popup.show` called with expected anchor.
- `test_stale_result_is_discarded`: bump token / switch doc before worker settles -> no chooser, no message, no popup.

## Acceptance commands

```powershell
.venv\Scripts\python.exe -m pytest tests/test_lsp_navigation_flows.py -q
.venv\Scripts\python.exe -m pyright yate/flows/lsp_navigation_flows.py yate/editor.py yate/editor_compose.py tests/test_lsp_navigation_flows.py
```

Exit 0 required. Do not run full suite or smoke here.

## Risk / rollback

Risk: `editor.py` and `keymaps/vim.py` line counts change; plan e syncs them.
Risk: if `PromptFlows` lacks `prompt_text`, report to main agent before any
out-of-scope edit. Risk: `open_path` may be async in practice; verify signature
before wiring and adapt the injected callback type accordingly, recording the
deviation. Rollback: revert this plan's commits; wave a/b/c artifacts remain
independently testable.
