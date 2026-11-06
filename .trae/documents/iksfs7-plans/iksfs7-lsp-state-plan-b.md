# IKSFS7 plan-b — L0 manager: path gate, URI retarget, single didOpen (wave-1)

Main plan: [`../iksfs7-plan.md`](../iksfs7-plan.md) · wave table:
[`overview.md`](overview.md). Run from the `../yate-iksfs7` worktree root.

## 1. Input

- Issue notes [`../iksfs7-issue-notes.md`](../iksfs7-issue-notes.md) §1 problems 2/3, §5 LSP locations, §6 directions 2/3.
- Main plan §2 facts F4-F11, F18, §3 decisions B/C, §4 sequence diagram.
- Rules: `.trae/rules/architecture-boundaries.md` (R4: `editor_lsp` is a UI-free
  L0 leaf; R2/R6/§三.3), `.trae/rules/python-coding-style.md` (full annotations,
  docstrings, lazy `%` logging), `.trae/rules/misc-rules.md` §四 (English
  comments/docstrings).

## 2. Exclusive files

- `yate/editor_lsp/manager.py` (write)
- `tests/test_lsp.py` (write, append new cases only; do not rewrite the file)

Everything else is read-only. In particular do not touch
`yate/flows/document_flows.py` (plan-c) or `tests/test_architecture.py`.

## 3. Concrete changes (all in `yate/editor_lsp/manager.py`)

### 3.1 Module docstring (`:3-9`)

Add a fifth lifecycle bullet next to `on_document_closed`:

```
* :meth:`on_document_retargeted` -- a save-as gave the document a new URI
  (didClose of the old URI, didOpen of the new one)
```

Keep the surrounding prose and ASCII punctuation.

### 3.2 `__init__` (near `:113`, next to `_uri_cache`)

Add:

```python
#: URIs with an in-flight ``on_document_shown`` handshake.  The check in
#: ``is_open`` happens before ``await ensure_client``, so without this set two
#: overlapping refresh workers could both send didOpen for the same uri.
self._opening: set[str] = set()
```

No new imports (`set[str]` is builtin). `shutdown_all` (`:682+`) may call
`self._opening.clear()` after cancelling tasks — only if it does not change the
existing teardown order; the in-flight coroutines also clear their own entries
in `finally`.

### 3.3 `state_for_doc` (`:235-238`) — unify the gate with `supports`

Replace with:

```python
def state_for_doc(self, doc: Document) -> ServerState | None:
    """Aggregated server state relevant to *doc*, for the status bar.

    An unnamed document has no URI, so no server can ever serve it: return
    ``None`` instead of advertising a configured/ready server.  This mirrors
    the ``path is not None`` gate in :meth:`supports` and
    :meth:`ensure_client`.
    """
    if doc.path is None:
        return None
    cfg = self.config_for(doc.filetype)
    return self.states().get(cfg.name) if cfg is not None else None
```

`states()` / `configs()` (used by `diagnostics.py` and the extension bridge)
must remain unchanged: they describe *registered servers*, not a document.

### 3.4 `on_document_shown` (`:347-383`) — single didOpen under concurrency

Restructure to the following (preserve the existing `didOpen` payload,
`OpenDocState` fields, `_forget_diagnostics(uri)` call and the
`(LspError, OSError)` best-effort return):

```python
async def on_document_shown(self, doc: Document) -> None:
    """Open *doc* on its server when it becomes the active document."""
    if doc.path is None:
        return
    uri = self._uri(doc)
    if uri in self._open or uri in self._opening:
        return
    config = self.config_for(doc.filetype)
    if config is None:
        return
    self._opening.add(uri)
    try:
        client = await self.ensure_client(doc)
        if client is None:
            return
        root = self.root_for(config, doc)
        text = doc.buffer.get_text()
        try:
            await client.notify("textDocument/didOpen", {
                "textDocument": {
                    "uri": uri,
                    "languageId": config.language_id(doc.filetype),
                    "version": 1,
                    "text": text,
                },
            })
        except (LspError, OSError):
            return
        self._open[uri] = OpenDocState(
            uri=uri,
            config_name=config.name,
            client_key=(config.name, str(root)),
            language_id=config.language_id(doc.filetype),
            version=1,
            last_synced_lines=tuple(doc.buffer.lines),
            last_synced_version=doc.buffer.content_version,
            doc=doc,
        )
        # Pending diagnostics may already be stale relative to buffer content;
        # the server republishes after didOpen.
        self._forget_diagnostics(uri)
    finally:
        self._opening.discard(uri)
```

The `finally` must cover every early return inside the `try` (client start
failure, notify failure) so a URI is never stuck in `_opening`.

### 3.5 Extract `_close_uri` and add `on_document_retargeted` (`:385-408`)

Move the exact body of `on_document_closed` after its `if doc.path is None:
return` guard into a new private coroutine:

```python
async def _close_uri(self, uri: str) -> None:
    """Forget one open URI and best-effort notify its server with didClose."""
    state = self._open.pop(uri, None)
    self._change_timers.pop(uri, None)
    # Queued senders for this uri hold their own lock reference and
    # bail out on the pre-notify state check; dropping the entry here
    # keeps a reopened document from reusing the stale lock (R3 N5).
    self._change_locks.pop(uri, None)
    self._drop_uri_cache(uri)
    if state is None:
        return
    client = self._clients.get(state.client_key)
    if client is not None and client.state is ServerState.READY:
        try:
            await client.notify("textDocument/didClose",
                               {"textDocument": {"uri": uri}})
        except (LspError, OSError) as exc:
            # The document already left the session, so a lost didClose
            # only leaves the server's view stale -- logged (never
            # raised) to keep the close path total and traceable.
            log.debug("didClose failed for %s: %s", uri, exc)

async def on_document_closed(self, doc: Document) -> None:
    """Forget *doc*'s didOpen state and notify didClose (best effort)."""
    if doc.path is None:
        return
    await self._close_uri(self._uri(doc))
```

Then add the retarget entry point immediately after `on_document_closed`:

```python
async def on_document_retargeted(
    self, doc: Document, previous_path: Path | None
) -> None:
    """Rebind a saved-as document on its server.

    *previous_path* is the path the document had *before* the successful
    write (``None`` for a buffer that was unnamed).  An unchanged path keeps
    the ordinary didSave; a changed one drops the old URI (with didClose)
    before the new document is opened.  A first path is treated exactly like
    a document-shown event, so ``:saveas test.py`` really attaches the server.
    """
    if doc.path is None:
        return
    if previous_path is not None and Path(previous_path) == doc.path:
        await self.notify_saved(doc)
        return
    if previous_path is not None:
        await self._close_uri(protocol.path_to_uri(previous_path))
    await self.on_document_shown(doc)
```

`Path` and `protocol` are already imported (`:28`, `:34`). Keep the
`previous_path` comparison positional and path-object based (no string
normalization surprises); `doc.path` is absolute after
`resolve_input_path` in the save flow, and `previous_path` comes from the same
`Document.path` attribute.

### 3.6 Explicitly unchanged

`supports`, `is_open`, `states`, `ensure_client`, `notify_saved`,
`notify_edit`, `request_completion`, `shutdown_all`'s interruption order and
all wire payloads. No new public API other than `on_document_retargeted`;
`__all__` of `yate/editor_lsp/` is not modified.

## 4. Tests (append to `tests/test_lsp.py`)

Reuse the module's existing fixtures/helpers (`PY_CONFIG`, `make_python_doc`,
the fake-client `session` fixture and `asyncio.run(scenario())` pattern — read
`tests/test_lsp.py:640-810` and `:1060-1085` before writing). No new conftest,
no mocks of the manager internals beyond the existing `cast(Any, mgr)` seams.

| # | Test name | Arrange / Act | Assert (concrete values) |
|---|---|---|---|
| 1 | `test_state_for_doc_is_none_for_unnamed_buffer_with_filetype_override` | `mgr = LspManager(); mgr.register_server(PY_CONFIG); doc = Document(None); doc.filetype_override = "py"`; `state_for_doc(doc)`, `supports(doc)`, `ensure_client(doc)` | `state_for_doc(doc) is None`; `supports(doc) is False`; `await mgr.ensure_client(doc) is None`; no client in `mgr._clients` |
| 2 | `test_state_for_doc_reports_configured_for_named_buffer` | same manager; `doc = Document(Path("a.py"))` | `state_for_doc(doc) is ServerState.CONFIGURED`; `supports(doc) is True` |
| 3 | `test_on_document_retargeted_from_unnamed_sends_did_open` | fake client session; `doc = Document(None)` with `filetype_override = "py"` and text `"x = 1\n"`; `doc.path = tmp_path / "new.py"`; `await mgr.on_document_retargeted(doc, None)` | exactly one `textDocument/didOpen` notification; its `uri == protocol.path_to_uri(doc.path)`, `languageId == PY_CONFIG.language_id("py")`, `text == "x = 1\n"`; `mgr.is_open(doc) is True`; `client.started is True` |
| 4 | `test_on_document_retargeted_from_named_path_closes_old_uri_and_opens_new` | fake client session; `old = tmp_path/"old.py"`, `new = tmp_path/"new.py"`; `await mgr.on_document_shown(doc)` with `doc.path = old`; then `doc.path = new`; `await mgr.on_document_retargeted(doc, old)` | `didClose` sent with `protocol.path_to_uri(old)`; `didOpen` sent with `protocol.path_to_uri(new)`; `mgr.is_open(doc) is True`; `protocol.path_to_uri(old) not in cast(Any, mgr)._open`; `uri_to_path`-based cache check: `protocol.path_to_uri(old) not in cast(Any, mgr)._uri_cache.values()` |
| 5 | `test_on_document_retargeted_same_path_only_sends_did_save` | fake client session; `await mgr.on_document_shown(doc)`; `await mgr.on_document_retargeted(doc, doc.path)` | exactly one `didSave`; `didOpen` count stays 1; `didClose` count is 0 |
| 6 | `test_on_document_retargeted_without_matching_server_is_noop` | `mgr.register_server(PY_CONFIG)`; `doc = Document(None)`, `doc.path = tmp_path/"note.txt"` (no override); `await mgr.on_document_retargeted(doc, None)` | no client started; `mgr.is_open(doc) is False`; `_open` empty |
| 7 | `test_concurrent_document_shown_sends_single_did_open` | fake client whose `start()` awaits `asyncio.sleep(0)` (reuse the existing slow-start fake if available); create two tasks `asyncio.create_task(mgr.on_document_shown(doc))`; `await asyncio.gather(*tasks)` | exactly one `didOpen`; `len(mgr._open) == 1`; `cast(Any, mgr)._opening == set()` |
| 8 | `test_on_document_closed_still_clears_state_after_uri_extraction` | fake client session; `await mgr.on_document_shown(doc)`; arm a pending change with `doc.buffer.insert_text("x"); mgr.notify_edit(doc)`; `await mgr.on_document_closed(doc)` | `mgr.is_open(doc) is False`; one `didClose`; `cast(Any, mgr)._change_timers` no longer holds `uri`; `uri not in cast(Any, mgr)._uri_cache.values()` |

Negative drills (record in §6): before the edit, case #1 must fail
(`state_for_doc` currently returns `CONFIGURED`) and case #7 must fail
(two `didOpen`s). After the edit both must be green. Do not weaken assertions
to make a drill pass.

## 5. Acceptance commands (copy-paste, from worktree root)

```powershell
.venv\Scripts\python.exe -m pytest tests/test_lsp.py -q -n auto
.venv\Scripts\python.exe -m pytest tests/test_lsp.py -q -n 1
.venv\Scripts\python.exe -m pytest tests/test_app_lsp.py tests/test_lsp_diff.py -q -n auto
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/ pack/
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
.venv\Scripts\python.exe -c "from pathlib import Path; print(len(Path('yate/editor_lsp/manager.py').read_text(encoding='utf-8').splitlines()))"
```

Pass criteria: all pytest/pyright commands exit 0; `-n auto` and `-n 1` agree;
architecture suite 37 passed; `manager.py` stays below 800 lines.

## 6. Execution record (fill in with real numbers)

| Command | Result | Exit code |
|---|---|---|
| negative drill (case #1, #7 before edit) | `state_for_doc` returned `CONFIGURED` on an unnamed doc; two overlapping `on_document_shown` workers sent two didOpen — both assertions FAILED as expected | 1 (negative drill) |
| `pytest tests/test_lsp.py -q -n auto` | 64 passed (plan-b wave); 72+ after wave-3 additions | 0 |
| `pytest tests/test_lsp.py -q -n 1` | agrees with `-n auto`, no flake | 0 |
| `pytest tests/test_app_lsp.py tests/test_lsp_diff.py -q -n auto` | all passed | 0 |
| `pyright ...` | `0 errors, 0 warnings, 0 informations` | 0 |
| `pytest tests/test_architecture.py -q` | 37 passed | 0 |
| line count `manager.py` | 783 after plan-b; 797 after wave-3 (still `< 800`) | 0 |

Deviations: none at wave-1. Step-5 review round 1 later found two major design
gaps in §3.5's `Path`-based comparison; they were redesigned in
[`iksfs7-review-fixes-plan-e.md`](iksfs7-review-fixes-plan-e.md) and fixed in
wave-3, with 4/4 negative drills failing on the old implementation. The
current code follows plan-e, not the original §3.5 snippet above.

## 7. Risks and rollback

- Risk: `_opening` leaks if a task is cancelled before `finally`. Mitigated by
  `try/finally`; case #7 asserts the set is empty. `shutdown_all` cancellation
  also reaches `finally` on the next loop turn.
- Risk: `_close_uri` extraction changes `didClose` bookkeeping. Mitigated by
  copying the exact statement order and pinning case #8 plus the full
  `tests/test_lsp.py` regression.
- Risk: a stale `_open` entry for the old URI after `:saveas`. Case #4 asserts
  the old URI is dropped from `_open` and the URI cache.
- Rollback: revert this wave's commit; plan-c depends on
  `on_document_retargeted`, so wave-2 must not start if this plan is rolled
  back.
