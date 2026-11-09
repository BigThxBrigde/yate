# Plan d — `LspManager.request_hover` (wave-2, L0)

Parent: [overview.md](overview.md) · Main plan: [../lsp-hover-docs-plan.md](../lsp-hover-docs-plan.md), decision D3
Depends on: plan a (`parsing.parse_hover_contents`).

## Input

- `yate/editor_lsp/manager.py:45-46` (re-exported UTF-16 helpers),
  `:50` (constants), `:212-239` (`config_for` / `supports` / `states`),
  `:300-329` (`ensure_client` **starts** a client), `:361-408`
  (`on_document_shown` emits `didOpen`), `:467-516` (`didChange`),
  `:541-618` (`request_completion` template), `:785` (`_uri`).
- `yate/editor_lsp/client.py:62` (`ServerState.READY`), `:394-429`
  (`request` / `start_request` / `settle_request`).
- `yate/editor_lsp/parsing.py` after plan a: `parse_hover_contents`.

## Exclusive files

- `yate/editor_lsp/manager.py`
- `tests/test_lsp_hover.py` (new)

## Concrete changes

1. `yate/editor_lsp/manager.py:50` — add
   `HOVER_TIMEOUT_S: float = 2.0` with a `#:` comment (a bounded wait is
   mandatory: `LspClient.request()` has no timeout).
2. Add a private lookup near `state_for_doc` (`manager.py:241`):

   ```python
   def _ready_client_for(self, doc: Document) -> LspClient | None:
       """Return an already-READY client with *doc* open; never start one."""
   ```

   Steps: `doc.path is None` → `None`; `config = self.config_for(doc.filetype)`
   → `None` guard; `root = self.root_for(config, doc)`;
   `key = (config.name, str(root))`; `client = self._clients.get(key)`;
   return it **only** when `client.state is ServerState.READY` **and** the
   document URI is already open (use `self.is_open(...)` at `manager.py:220`,
   matching its actual signature; otherwise check `uri in self._open`).
   Never call `ensure_client`, `_start_client`, `_make_client`,
   `on_document_shown` or `notify`.
3. Add the public method after `request_completion` (`manager.py:618`):

   ```python
   async def request_hover(self, doc: Document, row: int, col: int) -> str:
       """Fetch normalized hover Markdown; "" when unavailable or empty."""
   ```

   - `client = self._ready_client_for(doc)`; `None` → `""` (log at debug only).
   - `uri = self._uri(doc)`;
     `cursor_line = doc.buffer.lines[row] if row < doc.buffer.line_count else ""`;
     `params = {"textDocument": {"uri": uri}, "position": {"line": row,
     "character": _to_utf16(cursor_line, col)}}`.
   - Mirror `request_completion:584-600`: `request_id, future = await
     client.start_request("textDocument/hover", params)`, then
     `raw = await asyncio.wait_for(future, HOVER_TIMEOUT_S)` inside a nested
     `try/finally: client.settle_request(request_id)`; re-raise
     `asyncio.CancelledError`; `except (LspError, OSError, TimeoutError)`
     → `""`; no `dispatch_change`, no `on_document_shown`.
   - Parse with `parsing.parse_hover_contents(raw)` inside
     `try/except Exception:  # noqa: BLE001 - hostile server payload` →
     `log.debug(...)` and `""` (never raise, never surface to the UI).
   - Docstring must contrast with `request_completion`: no `didOpen`, no
     `didChange`, no server startup.
4. No changes to `request_completion`, `ensure_client`, `notify_edit`,
   `on_document_shown`, `states` or the diagnostics path (AC6).

## Tests (`tests/test_lsp_hover.py`)

Fixture: a `_FakeClient` with `state = ServerState.READY`,
`async def start_request(method, params)` recording the call and returning
`(id, future)`, `settle_request(id)` recording cleanup; register a
`ServerConfig` via `manager.register_server(...)` and inject the fake into
`manager._clients` (pattern from `tests/test_lsp.py:37-70` and
`tests/test_app_lsp.py`). Monkeypatch `manager.ensure_client` and
`manager.on_document_shown` to fail the test if called. Use the async style
already used in `tests/test_lsp.py` (`asyncio.run` or the project's async
fixture — follow that file, do not add a new dependency).

| Test | Arrange / Act | Assert |
| --- | --- | --- |
| `test_request_hover_sends_hover_method_and_uri` | ready + open doc, `await manager.request_hover(doc, 3, 2)` | recorded method `== "textDocument/hover"` and `params["textDocument"]["uri"]` matches `manager._uri(doc)` |
| `test_request_hover_encodes_position_in_utf16_units` | line `"aé中x"`, cursor `col=3` | `params["position"] == {"line": row, "character": _to_utf16(line, 3)}` and equals 3 (é=1 unit, 中=1 unit) — assert against `_to_utf16`, not a hard-coded guess |
| `test_request_hover_without_ready_server_returns_empty_without_starting_one` | empty `_clients` | `== ""`; `ensure_client` / `on_document_shown` never called; no `start_request` |
| `test_request_hover_with_failed_server_state_returns_empty` | fake `state = ServerState.FAILED` | `== ""` |
| `test_request_hover_with_unopened_document_returns_empty` | ready client, `is_open` false | `== ""`, no `start_request` |
| `test_request_hover_does_not_flush_didChange` | monkeypatch `dispatch_change` to raise | call returns normally and the spy was not called |
| `test_request_hover_with_null_result_returns_empty` | `future.set_result(None)` | `== ""` |
| `test_request_hover_with_error_response_returns_empty` | `future.set_exception(LspResponseError(...))` | `== ""` and `settle_request` was called |
| `test_request_hover_with_timeout_returns_empty` | never settle the future, monkeypatch `HOVER_TIMEOUT_S` to a tiny value | `== ""` and `settle_request` was called (no fixed-sleep assertion) |
| `test_request_hover_with_malformed_payload_returns_empty` | `future.set_result(object())` | `== ""`, no exception |
| `test_request_hover_returns_normalized_markdown_from_markup_array` | `{"contents": [{"language":"python","value":"def f():"}, {"kind":"markdown","value":"docs"}]}` | result contains the fenced signature and `docs` |
| `test_request_hover_settles_pending_request_on_success` | normal result | `settle_request` called exactly once with the issued id |
| `test_request_hover_with_cancelled_worker_reraises_cancellation` | cancel the awaiting task | `pytest.raises(asyncio.CancelledError)` |

## Acceptance commands

```powershell
cd D:/Programming/yate-lsp-hover-docs
.venv\Scripts\python.exe -m pytest tests/test_lsp_hover.py -q -n 1
.venv\Scripts\python.exe -m pytest tests/test_lsp.py tests/test_lsp_parsing.py tests/test_app_lsp.py -q -n 1
```

Both exit codes 0; the second proves completion/diagnostics are untouched.

## Risks and rollback

- Risk: `is_open()` signature differs from the assumption — read
  `manager.py:220` first; if it takes a `Document`, pass `doc`; never call a
  method that opens the document.
- Risk: `asyncio.wait_for` cancels the underlying future; `settle_request`
  must still run in `finally`. Covered by the timeout test.
- Risk: `parsing.parse_hover_contents` is not yet importable if plan a failed —
  wave 2 must not start until wave 1 passes.
- Rollback: revert this commit; plan g is the only consumer, in wave 3.
