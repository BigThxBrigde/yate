# IKSFS7 plan-e — review round-1 major/minor fixes (wave-3, serial)

Main plan: [`../iksfs7-plan.md`](../iksfs7-plan.md) · wave table:
[`overview.md`](overview.md). Run from the `../yate-iksfs7` worktree root.
Triggered by step 5 review round 1: **0 blocker / 2 major / 4 minor**, so step 6
returns to step 2 for this design before any further code change.

## 1. Input

- Review round-1 findings (major#1 retarget onto a URI owned by another tab;
  major#2 path spelling vs URI equivalence; minor#3 close-during-open ghost
  entry; minor#4 three uncovered lines; minor#5 783/800 line budget;
  minor#6 missing multi-argument `:enew` case).
- Main plan §3 decision C (especially rejected alternative C4: "an unchanged
  path keeps didSave, restarting the server-side document on an identical
  path discards diagnostics for no reason") and §6 risk table.
- [`iksfs7-lsp-state-plan-b.md`](iksfs7-lsp-state-plan-b.md) §3.4/§3.5 for the
  current `on_document_shown` / `_close_uri` / `on_document_retargeted` shape.
- Rules: `.trae/rules/architecture-boundaries.md` §三.7 (>800 lines needs
  exemption or split), R4/R2/R6, `.trae/rules/python-coding-style.md`,
  `.trae/rules/misc-rules.md` §四 (English comments/docstrings).

### Design rulings (step-2 additions, must be implemented as written)

1. **URI, not `Path`, is the identity of an open document.** `previous_path`
   and `doc.path` are compared by `protocol.path_to_uri(...)` (which resolves
   the path, `../../yate/editor_lsp/protocol.py:156-158`). A spelling like
   `sub/../a.py` therefore counts as *the same* document, keeps the existing
   didOpen and sends only didSave. The old spelling's `_uri_cache` key is
   dropped so equivalent paths do not accumulate duplicate keys.
2. **A retarget may steal a URI from another tab.** If `_open[new_uri]` exists
   and `state.doc is not doc`, close that entry first (best-effort didClose),
   then let `on_document_shown` open the retargeted document. Without this,
   `on_document_shown` short-circuits on `uri in self._open` and the server
   never sees the new owner's content.
3. **Close wins over an in-flight open.** `_close_uri` discards the URI from
   `_opening`; `on_document_shown` re-checks membership after `await
   ensure_client` and after `await client.notify("didOpen")`, and aborts
   without writing `_open` when a close happened in between.
4. **No new module / no new public method.** `manager.py` is at 783 lines
   (17 below the §三.7 threshold). All fixes are in-place rewrites of the
   three existing methods; docstrings/comments are shortened where needed.
   The executor must assert `< 800` lines at acceptance time.
5. **No `resolve()`/`normpath` in `DocumentFlows`.** Rejected: `resolve()`
   follows symlinks and would change the file a save targets, while
   `normpath` changes the lexical meaning of `link/../file` on some platforms.
   URI comparison fixes the LSP behavior without touching the save path or
   `workspace.set_root(path.parent)`.

## 2. Exclusive files

- `yate/editor_lsp/manager.py` (write — only `_close_uri`,
  `on_document_shown`, `on_document_retargeted`)
- `tests/test_lsp.py` (append new cases only)
- `tests/test_cmd_enew.py` (append one case only)

Everything else is read-only, including `yate/flows/document_flows.py`,
`yate/commands.py`, manuals, smoke files, `tests/test_architecture.py` and all
`.trae/**` documents (backfill belongs to the main agent).

## 3. Concrete changes in `yate/editor_lsp/manager.py`

### 3.1 `_close_uri` (`:405-425`) — one line + one comment

Immediately after `state = self._open.pop(uri, None)` add:

```python
# A close during an in-flight didOpen wins: the opener checks this set
# after each await and must not resurrect the URI.
self._opening.discard(uri)
```

All other statements, the `R3 N5` comment and the
`log.debug("didClose failed for %s: %s", uri, exc)` message stay verbatim.

### 3.2 `on_document_shown` (`:361-403`) — two membership re-checks

Keep the existing structure. Replace:

```python
client = await self.ensure_client(doc)
if client is None:
    return
```

with:

```python
client = await self.ensure_client(doc)
# _close_uri drops the uri from _opening, so a close during the handshake
# aborts this open instead of writing a ghost entry back into _open.
if client is None or uri not in self._opening:
    return
```

And immediately after the `except (LspError, OSError): return` block for the
`didOpen` notify (i.e. before `self._open[uri] = OpenDocState(...)`) add:

```python
if uri not in self._opening:
    return
```

`finally: self._opening.discard(uri)` stays exactly where it is.

### 3.3 `on_document_retargeted` (`:433-451`) — replace the whole method body

```python
async def on_document_retargeted(
    self, doc: Document, previous_path: Path | None
) -> None:
    """Rebind a saved-as document on its server.

    *previous_path* is the path before the successful write (``None`` for a
    buffer that was unnamed).  Paths are compared by URI, not spelling: an
    unchanged URI keeps didSave, a changed one closes the old URI before
    didOpen.  A first path is treated as a document-shown event.  When another
    tab owns the target URI, its entry is closed so this document can own it.
    """
    if doc.path is None:
        return
    new_uri = self._uri(doc)
    if previous_path is not None:
        previous_uri = protocol.path_to_uri(previous_path)
        if previous_uri == new_uri:
            self._uri_cache.pop(previous_path, None)
            await self.notify_saved(doc)
            return
        await self._close_uri(previous_uri)
    owner = self._open.get(new_uri)
    if owner is not None and owner.doc is not doc:
        await self._close_uri(new_uri)
    await self.on_document_shown(doc)
```

Do not change `state_for_doc`, `supports`, `states`, `ensure_client`,
`notify_saved`, `notify_edit`, `shutdown_all`, or any wire payload. No new
imports (`Path`, `protocol` are already present). Do not introduce a new
`ServerState`, callback or context type (R2/R8, §三.1).

## 4. Tests

### 4.1 `tests/test_lsp.py` — append 7 cases

Reuse the module's existing fake-client fixtures and `asyncio.run(scenario())`
pattern. Every assertion below is a concrete observable value.

| # | Test name | Arrange / Act | Assert |
|---|---|---|---|
| 1 | `test_on_document_retargeted_same_uri_with_different_spelling_only_sends_did_save` | fake client session; `doc.path = tmp_path/"a.py"`; `await mgr.on_document_shown(doc)`; set `doc.path = tmp_path/"sub"/".."/"a.py"` (no file I/O needed); `await mgr.on_document_retargeted(doc, tmp_path/"a.py")` | `didClose` count == 0; `didOpen` count == 1 (only the initial one); exactly 1 `didSave`; `mgr.is_open(doc) is True`; `len(cast(Any, mgr)._uri_cache) == 1` |
| 2 | `test_on_document_retargeted_to_uri_owned_by_another_document_reopens_for_new_owner` | fake client session; `a = Document(Path("x.py"))` with text `"a\n"`, `b = Document(Path("y.py"))` with text `"b\n"`; `await mgr.on_document_shown(a)`; `await mgr.on_document_shown(b)`; set `a.path = Path(b.path)`; `await mgr.on_document_retargeted(a, Path("x.py"))` | old `x.py` URI got `didClose`; `y.py` URI got `didClose`; exactly 1 `didOpen` carrying `uri == protocol.path_to_uri(y.py)` and `text == "a\n"` (filter by new URI); `cast(Any, mgr)._open[new_uri].doc is a`; `mgr.is_open(a) is True` |
| 3 | `test_on_document_retargeted_without_path_is_noop` | `doc = Document(None)`; `await mgr.on_document_retargeted(doc, None)` | no client created; `_open` empty; `_opening` empty; no notification |
| 4 | `test_on_document_shown_without_path_is_noop` | `doc = Document(None)` with `filetype_override = "py"`; `await mgr.on_document_shown(doc)` | no client created; `_open` empty; `_opening` empty |
| 5 | `test_on_document_shown_notify_failure_leaves_no_open_state` | fake client whose `notify` raises `LspError` for `didOpen`; `await mgr.on_document_shown(doc)` | `_open` empty; `_opening` empty; no exception escapes |
| 6 | `test_on_document_closed_during_open_handshake_leaves_no_ghost_state` | fake client whose `start()` awaits `asyncio.sleep(0)`; `task = asyncio.create_task(mgr.on_document_shown(doc))`; `await asyncio.sleep(0)`; `await mgr.on_document_closed(doc)`; `await task` | no `didOpen` notification (or, if the notify already started, `_open` has no URI afterwards); `_opening == set()`; `mgr.is_open(doc) is False` |
| 7 | `test_on_document_retargeted_same_uri_does_not_leave_duplicate_cache_keys` | same setup as #1 but assert cache keys explicitly | `protocol.path_to_uri(a.py)` appears exactly once among `_uri_cache.values()`; the old-spelling key `tmp_path/"a.py"` is absent when it differs from `doc.path` |

Negative drills (record in §6): before the product edit, cases #1 and #2 must
fail (#1 currently sends didClose+didOpen because `Path(sub/../a.py) !=
Path(a.py)`; #2 currently leaves `_open[new_uri].doc is b` and sends no
didOpen for `a`). After the edit both must be green. Do not weaken assertions.

### 4.2 `tests/test_cmd_enew.py` — append 1 case

| # | Test name | Arrange / Act | Assert |
|---|---|---|---|
| 8 | `test_enew_with_multiple_arguments_warns_and_creates_no_buffer` | fresh fixture; `fx.entry.func("a.py b.py")` | `new_buffer_calls == []`; `notes == [(_USAGE_MESSAGE, "warn")]` |

## 5. Acceptance commands (copy-paste, from worktree root)

```powershell
.venv\Scripts\python.exe -m pytest tests/test_lsp.py tests/test_cmd_enew.py -q -n auto
.venv\Scripts\python.exe -m pytest tests/test_lsp.py tests/test_cmd_enew.py -q -n 1
.venv\Scripts\python.exe -m pytest tests/test_document_flows_saveas.py tests/test_app_lsp.py -q -n auto
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/ pack/
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
.venv\Scripts\python.exe -m pytest tests/test_lsp.py tests/test_cmd_enew.py --cov=yate.editor_lsp.manager --cov=yate.commands --cov-branch --cov-report=term-missing --cov-fail-under=0 -q
.venv\Scripts\python.exe -c "from pathlib import Path; n=len(Path('yate/editor_lsp/manager.py').read_text(encoding='utf-8').splitlines()); print('manager.py lines:', n); assert n < 800"
```

Pass criteria: every command exits 0; `-n auto` and `-n 1` agree; pyright 0
errors; architecture 37 passed; coverage report no longer lists
`manager.py:364`, `:387-388`, `:445` as uncovered (line numbers may shift);
line count `< 800`. A parallel-only failure must be re-checked with `-n 1` and
fixed, not recorded as a flake.

## 6. Execution record (fill in with real numbers)

| Command | Result | Exit code |
|---|---|---|
| negative drills (#1, #2 before edit) | pending | — |
| `pytest tests/test_lsp.py tests/test_cmd_enew.py -q -n auto` | pending | — |
| `pytest ... -n 1` | pending | — |
| `pytest tests/test_document_flows_saveas.py tests/test_app_lsp.py -q -n auto` | pending | — |
| `pyright ...` | pending | — |
| `pytest tests/test_architecture.py -q` | pending | — |
| local coverage `--cov-fail-under=0` | pending | — |
| line count `manager.py` | pending | — |

Deviations: none recorded yet.

## 7. Risks and rollback

- Risk: closing another tab's URI makes that tab's later edits share the new
  owner's `OpenDocState`. This is inherent to two tabs bound to one path (a
  pre-existing `EditorSession` model limitation, reachable through `:saveas`);
  the LSP wire protocol has one document per URI. It is registered as a
  follow-up backlog item, not fixed here (out of IKSFS7 scope).
- Risk: `_opening` membership checks make a legitimate open abort if some
  unrelated code discards the URI. Only `_close_uri` discards (plus the
  opener's own `finally`), so this is intentional: close wins.
- Risk: line-count guard. All changes are in-place; the executor asserts
  `< 800` and must shorten prose, never add a module, if the limit is hit.
- Rollback: revert this wave's commit; wave-1/2 behavior stays intact but the
  two majors return, so step 5 review must be repeated after any rollback.
