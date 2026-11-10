# Plan b — declare hover client capabilities (wave-1, L0)

Parent: [overview.md](overview.md) · Main plan: [../lsp-hover-docs-plan.md](../lsp-hover-docs-plan.md)

## Input

- `yate/editor_lsp/client.py:591-633` (`_initialize_params`), `:598-631`
  (`capabilities`), `:224-268` (`start()` handshake parses only
  `completionProvider.triggerCharacters`).
- Main plan D2: a client declares `textDocument.hover.contentFormat`, **not**
  `hoverProvider` (a server-side capability). The issue's `documentationFormat`
  wording is satisfied by filling the existing completion field.

## Exclusive files

- `yate/editor_lsp/client.py`
- `tests/test_lsp_client_capabilities.py` (new)

## Concrete changes

1. `yate/editor_lsp/client.py:612-620` — in the `textDocument.completion`
   block, replace `"documentationFormat": []` with
   `"documentationFormat": ["markdown", "plaintext"]`.
2. `yate/editor_lsp/client.py:620` — add a sibling key inside `textDocument`:

   ```python
   "hover": {
       "dynamicRegistration": False,
       "contentFormat": ["markdown", "plaintext"],
   },
   ```

   Keep `synchronization`, `completion`, `publishDiagnostics`, `workspace`,
   `window` and `textDocumentSync` byte-for-byte unchanged (AC6: no sync
   protocol change). Add an ASCII comment above `hover` stating that
   `hoverProvider` is a server capability and is intentionally not declared.
3. Define the format list once as a module-level constant
   `DOCUMENTATION_FORMATS: tuple[str, ...] = ("markdown", "plaintext")` and
   convert with `list(DOCUMENTATION_FORMATS)` at both sites so the two
   declarations cannot drift. Place it next to `ERR_METHOD_NOT_FOUND`
   (`client.py:44`) with a `#:` comment. Do **not** change
   `ServerState`, `start()` or request dispatch.

## Tests (`tests/test_lsp_client_capabilities.py`)

Fixture: construct `LspClient` the same way `tests/test_lsp.py:37-43`
(`PY_CONFIG`) does, with `tmp_path` as root; no process started.

| Test | Arrange / Act | Assert |
| --- | --- | --- |
| `test_initialize_params_declares_hover_content_format` | `caps = client._initialize_params()["capabilities"]["textDocument"]` | `caps["hover"] == {"dynamicRegistration": False, "contentFormat": ["markdown", "plaintext"]}` |
| `test_initialize_params_declares_completion_documentation_format` | same payload | `caps["completion"]["completionItem"]["documentationFormat"] == ["markdown", "plaintext"]` |
| `test_initialize_params_does_not_declare_server_side_hover_provider` | same payload | `"hoverProvider" not in caps` and `"hoverProvider" not in payload["capabilities"]` |
| `test_initialize_params_keeps_existing_capabilities_unchanged` | compare the rest of the payload against a literal expected dict | `textDocumentSync`, `synchronization`, `completion` remaining keys, `publishDiagnostics`, `workspace`, `window` all equal the baseline values from `client.py:598-631` |
| `test_documentation_formats_constant_is_shared_by_both_declarations` | read the module constant, call `_initialize_params()` | both lists equal `list(DOCUMENTATION_FORMATS)` |
| `test_initialize_params_hover_declaration_has_no_dynamic_registration` | `caps["hover"]` | `dynamicRegistration is False` (no new server requests at runtime) |

Use `cast(dict[str, object], ...)`/`cast(list[object], ...)` when indexing the
`dict[str, Any]` payload so pyright strict stays satisfied without new `Any`
annotations in product code.

## Acceptance commands

```powershell
.venv\Scripts\python.exe -m pytest tests/test_lsp_client_capabilities.py -q -n 1
.venv\Scripts\python.exe -m pytest tests/test_lsp.py tests/test_lsp_real_server.py -q -n 1
```

Both exit codes 0. The second command proves the handshake path is unchanged.

## Risks and rollback

- Risk: a strict server rejects an unknown `hover` client field. LSP 3.17
  standardizes it; the existing handshake ignores unknown fields on both
  sides, and `tests/test_lsp_real_server.py` guards the real-server path.
- Risk: filling `documentationFormat` makes servers return richer completion
  documentation. Non-goal explicitly forbids surfacing it; no completion
  parsing changes are allowed in this plan.
- Rollback: revert this commit; plan d only reads the client's `state`, not the
  capability payload.
