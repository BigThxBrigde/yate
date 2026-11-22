# Plan a — LSP request layer (wave 1)

Parent: [../lsp-navigation-plan.md](../lsp-navigation-plan.md).

## Input / output

Input: issue brief AC1-AC7, code facts in parent plan §2.
Output: L0 request+parsing module, canonical URI mapping, thin manager wrappers,
unit tests. No UI and no key changes in this plan.

## Exclusive files

- `yate/editor_lsp/navigation.py` (new)
- `yate/editor_lsp/protocol.py`
- `yate/editor_lsp/manager.py`
- `tests/test_lsp_navigation.py` (new)

Do not touch `tests/test_architecture.py` or any rule file here; line-count
sync belongs to plan e.

## Concrete changes

### 1. `editor_lsp/protocol.py`

Add `canonical_uri(uri: str) -> str` (public): convert via `uri_to_path(uri)`
then `path_to_uri(...)`; when the source is not a `file:` URI, return the input
unchanged. Replace manager's raw diagnostic key and outgoing URI generation
with this function so pyright's drive-escaped echoes and locally built URIs
compare equal. Keep `uri_to_path` / `path_to_uri` signatures unchanged.

### 2. New `editor_lsp/navigation.py` (L0, stdlib + local imports only)

- `class LspFeatureUnavailable(Exception)` — raised when the server capability
  is missing/false; flows turn it into a message (AC1/AC4/AC6).
- Frozen dataclasses: `LspLocation(uri, row, col, end_row, end_col)`,
  `LspSymbol(name, kind, detail, uri, row, col, end_row, end_col, depth)`,
  `LspTextEdit(start_row, start_col, end_row, end_col, text)`,
  `WorkspaceEdit(changes: dict[str, tuple[LspTextEdit, ...]], unsupported: bool)`,
  `LspCodeAction(title, kind, edit: WorkspaceEdit | None, command: str | None,
  arguments: tuple[object, ...])`,
  `LspSignature(text: str, active_parameter: int)`.
- `supports_feature(caps: dict[str, object], feature: str) -> bool`: missing,
  `False` or `None` => False; `True` or any dict/list => True. Handles the
  object-form `renameProvider` / `codeActionProvider`.
- `request(client, method: str, params: dict[str, object]) -> object`:
  `start_request` + `asyncio.wait_for(future, NAV_TIMEOUT_S=3.0)`; on timeout
  call `send_cancel(req_id)`; always `settle_request(req_id)`. Re-raise
  `asyncio.CancelledError`; wrap `LspError`/`OSError`/`TimeoutError` into
  `LspFeatureFailed` (new exception) with the method name.
- Pure parsers (all defensive: wrong shapes return empty values, no exception):
  `parse_locations(raw)`, `parse_symbols(raw)`, `parse_workspace_edit(raw)`,
  `parse_code_actions(raw)`, `parse_signature_help(raw)`.
  - `parse_locations`: accept `Location`, `LocationLink` (`targetUri` +
    `targetRange`), and `null`; clamp rows/cols like `parsing._range_to_buffer_cols`.
  - `parse_symbols`: accept both `DocumentSymbol[]` (recursive, flatten with
    increasing `depth`, use `selectionRange` for jump) and `SymbolInformation[]`
    (`location.uri` + `location.range`).
  - `parse_workspace_edit`: support `changes: dict[uri, TextEdit[]]` and
    `documentChanges` items with `edits`; set `unsupported=True` when any
    `CreateFile` / `DeleteFile` / `RenameFile` appears and return no partial
    changes.
  - `parse_code_actions`: accept `Command` and `CodeAction` shapes; keep title,
    kind, edit, command name and arguments.
  - `parse_signature_help`: pick active signature/parameter, format a markdown
    card with the label and the active parameter marked in bold.

### 3. `editor_lsp/manager.py`

Keep existing behavior unchanged. Add imports from `navigation` and
`protocol.canonical_uri`. Add thin methods after `request_hover`:

```python
def supports_feature(self, doc: Document, feature: str) -> bool
async def request_definition(self, doc: Document, row: int, col: int) -> list[LspLocation]
async def request_references(self, doc: Document, row: int, col: int) -> list[LspLocation]
async def request_document_symbols(self, doc: Document) -> list[LspSymbol]
async def request_rename(self, doc: Document, row: int, col: int, new_name: str) -> WorkspaceEdit
async def request_code_actions(self, doc: Document, row: int, col: int, diagnostics: list[Diagnostic]) -> list[LspCodeAction]
async def request_signature_help(self, doc: Document, row: int, col: int) -> LspSignature | None
async def execute_command(self, client: LspClient, name: str, arguments: list[object]) -> None
```

Each request method: `_ready_client_for(doc)` → `supports_feature(...)` (raise
`LspFeatureUnavailable` on false) → build LSP params with UTF-16 columns via
existing `_to_utf16` → `navigation.request(...)` → parser. `request_references`
passes `{"includeDeclaration": True}`. `request_code_actions` passes the
diagnostics range and `only: ["quickfix", "refactor", "source"]` filtered to
what the server declares when possible. `execute_command` sends
`workspace/executeCommand` through the client and ignores the result.

Modify `_uri()` and `handle_notification()` to use `canonical_uri` as described.

## Tests (`tests/test_lsp_navigation.py`)

Use the `_FakeClient` / `_Harness` pattern from `tests/test_lsp_hover.py:36-121`
(read that file; do not modify it). Required cases:

- `test_canonical_uri_maps_drive_escaped_and_plain_forms_to_one`: `canonical_uri("file:///d%3A/x.py") == canonical_uri("file:///D:/x.py")`.
- `test_parse_locations_accepts_location_link_and_null`: one `LocationLink` with `targetUri`/`targetRange` and one `None` -> one `LspLocation` with expected row/col.
- `test_parse_symbols_flattens_nested_document_symbols`: parent + child -> two `LspSymbol`s with depths 0/1 and child's `selectionRange` position.
- `test_parse_workspace_edit_rejects_file_operations`: edit with one valid text edit plus one `CreateFile` -> `unsupported is True` and `changes == {}`.
- `test_parse_code_actions_keeps_command_and_edit`: one command action and one edit action -> fields preserved.
- `test_parse_signature_help_marks_active_parameter`: two signatures, active 1/1 -> card text contains bold marker for second parameter.
- `test_manager_request_definition_without_provider_raises_unavailable`: fake client capabilities without `definitionProvider` -> `pytest.raises(LspFeatureUnavailable)`.
- `test_manager_request_definition_returns_locations`: fake response with two locations -> two `LspLocation`s, request method `textDocument/definition` recorded.
- `test_manager_request_references_timeout_sends_cancel`: fake future never settles, monkeypatch `navigation.NAV_TIMEOUT_S=0.001` -> `LspFeatureFailed`, `send_cancel` called, `settle_request` called.
- `test_manager_notification_uses_canonical_diagnostic_uri`: publish diagnostics with drive-escaped URI -> `manager` diagnostic key equals `canonical_uri` form.

## Acceptance commands (run from the task worktree root)

```powershell
.venv\Scripts\python.exe -m pytest tests/test_lsp_navigation.py -q
.venv\Scripts\python.exe -m pyright yate/editor_lsp tests/test_lsp_navigation.py
```

Exit 0 required for both. Do not run the full suite here.

## Risk / rollback

Risk: fake client harness may need `OpenDocState` fields; copy from
`tests/test_lsp_hover.py` exactly. Risk: `manager.py` grows past 893 lines —
expected and acceptable (already exempt); plan e syncs counts. Rollback: revert
this plan's commits; no other wave depends on its runtime behavior until wave 3.
