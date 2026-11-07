# Unnamed-buffer LSP attach plan-c — `:saveas` attaches LSP on first path (wave-2)

Main plan: [`../enew-args-lsp-attach-plan.md`](../enew-args-lsp-attach-plan.md) · wave table:
[`overview.md`](overview.md). Run from the `../yate-enew-args-lsp-attach` worktree root.
**Depends on plan-b**: `LspManager.on_document_retargeted` must exist and be
green before this plan starts.

## 1. Input

- Issue notes [`../enew-args-lsp-attach-issue-notes.md`](../enew-args-lsp-attach-issue-notes.md) §3 expected behavior, §6 direction 3.
- Main plan §2 facts F11-F15, §3 decision C, §4 sequence diagram.
- [`enew-args-lsp-attach-state-plan-b.md`](enew-args-lsp-attach-state-plan-b.md) §3.5 for the exact
  coroutine signature: `async def on_document_retargeted(self, doc: Document, previous_path: Path | None) -> None`.
- Rules: `.trae/rules/architecture-boundaries.md` (R11: `flows/*` may use the
  injected L0 manager; no upward import; §三.8 no new context type),
  `.trae/rules/python-coding-style.md` (full annotations, docstrings, logging),
  `.trae/rules/misc-rules.md` §四 (English comments/docstrings).

## 2. Exclusive files

- `yate/flows/document_flows.py` (write — only `_submit_save_as`)
- `tests/test_document_flows_saveas.py` (new file)

`yate/commands.py`, `yate/editor_lsp/manager.py`, `yate/flows/lsp_sync.py`,
manuals, smoke files and all `.trae/**` documents are read-only here.

## 3. Concrete change — `yate/flows/document_flows.py:457-509`

Current body (abridged, preserve it verbatim except for the listed edits):

```python
def _submit_save_as(self, text: str) -> None:
    ...
    doc = self.session.doc
    if doc.chunked is not None: ... return
    buf = doc.buffer
    locked = buf.read_only
    if locked: buf.read_only = False
    path = self.resolve_input_path(Path(text))
    saved = False
    try:
        self.session.doc.save(path)
        saved = True
        ...
        self.workspace.set_root(path.parent)
        self.explorer_tree.refresh_tree()
        self._message(f"saved {path}", "ok")
        self._events.emit(EditorEvent.DOCUMENT_SAVED, DocumentSaved(self.session.doc))
    except (OSError, UnicodeError) as exc:
        self._message(f"save failed: {exc}", "error")
    finally:
        if locked and not saved:
            buf.read_only = True
```

Edits, in order:

1. Immediately after `doc = self.session.doc` add:

   ```python
   previous_path = doc.path
   ```

   This is the path *before* the write; `Document.save` only retargets the
   document after a successful `os.replace` (F11).

2. In the `try` block replace `self.session.doc.save(path)` with
   `doc.save(path)` (same object, clearer and consistent with the new
   `previous_path` local). Keep `saved = True` on the next line.

3. At the **end of the successful `try` branch**, after the existing
   `self._events.emit(...)` call, add:

   ```python
   self._spawn(
       partial(self.lsp.on_document_retargeted, doc, previous_path),
       group="lsp-sync", exclusive=False, exit_on_error=False,
   )
   ```

   `partial` and the `lsp-sync` worker group are already used at `:426-429`
   for `notify_saved`; no new import, no new constructor parameter, no new
   event name. The spawn must stay inside the `try`, after `saved = True`, so
   a failed write or failed bookkeeping never schedules a retarget.

4. After the `finally` block, at method scope, add:

   ```python
   self._refresh_ui()
   ```

   This mirrors `save_document`'s tail (`:436`). It repaints the tab bar
   (`[no name]` → file name) and the status bar, and through
   `Editor.refresh_ui → _refresh_lsp → LspSync.doc_shown_later` provides the
   normal shown-event path; plan-b's `_opening` guard makes the extra
   `doc_shown_later` idempotent with the retarget worker. It runs on failure
   too (same as `save_document`), so the message line is repainted after an
   error.

5. Update `_submit_save_as`'s docstring with one sentence: "On a successful
   write the LSP manager is asked to rebind the document, which sends didOpen
   for the newly acquired URI (and didClose for a replaced one)."

Do **not** change `save_document` (`:402-436`), `save_as` (`:445-455`),
`prompt_save_as` (`:438-443`), the read-only lift/`finally` restoration, the
message texts, or the `DOCUMENT_SAVED` payload. Do not import `lsp_sync` into
this module (it is not a constructor collaborator).

## 4. Tests — new `tests/test_document_flows_saveas.py`

Headless construction pattern: `tests/test_overlay_flows_hex.py:395-419`
(DocumentFlows with `cast(Any, ...)` stand-ins) and
`tests/test_cmd_cd.py:82-115`. Use a real `EditorSession(YateConfig())` with
`session.new_buffer()` so `Document.name`, `Document.save` and buffer state are
genuine; use `tmp_path` for real disk writes. Every test must have full
annotations, English docstrings, `from __future__ import annotations`, absolute
imports, and no `TYPE_CHECKING`.

Recording stand-ins (names are advisory, behavior is fixed):

- `spawn`: appends `(work, kwargs)` and returns `None`; `work` is a
  `functools.partial`, so assertions can inspect `work.func.__name__`,
  `work.args[0]` (the `Document`) and `work.args[1]` (the previous path).
- `lsp`: exposes an async `on_document_retargeted(doc, previous_path)` and an
  async `notify_saved(doc)` that append to a call list; a `MagicMock` is also
  acceptable if pyright stays at zero diagnostics with `cast(Any, ...)`.
- `workspace`: `.root: Path | None = None` plus `set_root(path)` recorder
  (`resolve_input_path` reads `.root`, `yate/flows/document_flows.py:132-146`).
- `explorer_tree.refresh_tree()`, `events.emit(event, payload)`,
  `prompt_bar.activate(mode, initial=..., on_submit=...)`,
  `message(text, kind)`, `report(text, kind)`, `refresh_ui()`,
  `mounted() -> True`, `reveal_explorer()` recorders.

Exact test cases:

| # | Test name | Arrange / Act | Assert (concrete values) |
|---|---|---|---|
| 1 | `test_save_as_on_unnamed_buffer_spawns_retarget_with_none_previous_path` | `session.new_buffer()`; `session.doc.buffer.insert_text("print(1)\n")`; `flows.save_as(str(tmp_path / "new.py"))` | `dest.read_text(...) == "print(1)\n"`; `doc.path == dest`; `doc.name == "new.py"`; exactly 1 spawn with `work.func.__name__ == "on_document_retargeted"`, `work.args == (doc, None)`, `kwargs["group"] == "lsp-sync"`; `refresh_ui` calls == 1; message contains `"saved"` |
| 2 | `test_save_as_on_named_buffer_passes_previous_path` | create `source = tmp_path/"old.py"` with `"seed"`; `session.open(source)`; `flows.save_as(str(tmp_path/"renamed.py"))` | spawn args `(doc, source)`; `doc.path == renamed`; `source.read_text() == "seed"`; `renamed.read_text() == "seed"`; spawn count == 1 |
| 3 | `test_save_as_failure_spawns_no_retarget_and_keeps_previous_path` | unnamed doc; monkeypatch `Document.save` to raise `OSError("disk full")` (or make the target a directory so `os.replace` fails); `flows.save_as(str(dest))` | spawn count == 0; `doc.path is None`; `refresh_ui` calls == 1; a `"save failed"` error message is recorded; no exception escapes |
| 4 | `test_save_as_prompt_path_uses_the_same_retarget_path` | unnamed doc; `flows.save_as(None)` | `prompt_bar.activate` called once with `mode == "save"`; then `flows._submit_save_as(str(dest))` | exactly 1 retarget spawn with `(doc, None)`; `doc.path == dest` |
| 5 | `test_write_on_named_buffer_still_spawns_notify_saved` | `session.open(source)`; mark the buffer dirty with `insert_text("x")`; `flows.save_document()` | exactly 1 spawn whose `work.func.__name__ == "notify_saved"`; no retarget spawn; `source.read_text()` reflects the write; `refresh_ui` calls == 1 |

Negative drill (record in §6): before editing `_submit_save_as`, case #1 must
fail with `spawn count == 0` and `refresh_ui calls == 0`; after the edit it
must be green. Do not assert on a fake that auto-succeeds without the product
change.

## 5. Acceptance commands (copy-paste, from worktree root)

```powershell
.venv\Scripts\python.exe -m pytest tests/test_document_flows_saveas.py -q
.venv\Scripts\python.exe -m pytest tests/test_cmd_cd.py tests/test_shell_flows.py tests/test_overlay_flows_hex.py -q -n auto
.venv\Scripts\python.exe -m pytest tests/test_lsp.py -q -n auto
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/ pack/
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
.venv\Scripts\python.exe -c "from pathlib import Path; print(len(Path('yate/flows/document_flows.py').read_text(encoding='utf-8').splitlines()))"
```

Pass criteria: all commands exit 0; pyright 0 errors; architecture 37 passed;
`document_flows.py` stays below 800 lines. Note this plan's first command
requires plan-b's product change to be present (wave-1 gate).

## 6. Execution record (fill in with real numbers)

| Command | Result | Exit code |
|---|---|---|
| negative drill (case #1 before edit) | FAILED as expected: `spawn count == 0`, `refresh_ui calls == 0` | 1 (negative drill) |
| `pytest tests/test_document_flows_saveas.py -q` | 5 passed | 0 |
| `pytest ... -n auto` (cmd_cd / shell_flows / overlay_flows_hex) | all passed | 0 |
| `pytest tests/test_lsp.py -q -n auto` | all passed | 0 |
| `pyright ...` | `0 errors, 0 warnings, 0 informations` | 0 |
| `pytest tests/test_architecture.py -q` | 37 passed | 0 |
| line count `document_flows.py` | 533 | 0 |

Deviations (one, evidence-backed): case #4 calls
`cast(Any, fx.flows)._submit_save_as(...)` instead of the private method
directly, because pyright strict reports `reportPrivateUsage` on the direct
call; using `cast(Any, ...)` is the plan's documented seam. Verified in review
round 1 §4. No product behavior changed.

## 7. Risks and rollback

- Risk: two workers (`retarget` + `doc_shown_later`) both send didOpen.
  Mitigated by plan-b's `_opening` gate; plan-b case #7 and the full LSP suite
  are re-run in this plan's acceptance commands.
- Risk: a failed save still leaves the LSP manager bound to the old URI.
  Mitigated: the spawn is inside the successful branch only; `Document.save`
  leaves `path` unchanged on failure (F11); case #3 pins it.
- Risk: `_refresh_ui()` on the prompt path triggers an extra repaint. It is the
  same call `save_document` already makes; no new timer/worker group.
- Rollback: revert this wave's commit. plan-b remains independently useful
  (its manager API is unused but harmless); plan-d's manual wording about
  save-as attach must then be reverted too.
