"""Tests for yate.app_features.explorer file operations (apply_delete, etc.)."""

from __future__ import annotations

import asyncio
import inspect
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock


from yate.editor_core.buffer import TextBuffer
from yate.editor_core.document import Document
from yate.app_features.explorer import apply_delete


async def _drain(works: list[object]) -> None:
    """Run every worker payload the way Textual's Worker would."""
    for work in works:
        # Textual only accepts coroutine functions (or awaitables) here; a plain
        # sync callable is rejected with WorkerError.
        assert inspect.iscoroutinefunction(work)
        await work()


def test_apply_delete_notifies_lsp_did_close(tmp_path: Path) -> None:
    """Deleting a folder with open tabs calls on_document_closed for each."""
    folder = tmp_path / "folder"
    folder.mkdir()
    file_a = folder / "a.py"
    file_b = folder / "b.py"
    file_a.write_text("x = 1\n")
    file_b.write_text("y = 2\n")

    doc_a = Document(file_a, TextBuffer("x = 1\n"))
    doc_b = Document(file_b, TextBuffer("y = 2\n"))
    scratch = Document(None, TextBuffer("scratch\n"))  # no path -> unaffected

    app = MagicMock()
    app.docs = [doc_a, doc_b, scratch]
    app.doc_index = 0
    app.lsp.on_document_closed = AsyncMock()

    apply_delete(app, folder, "y")

    # run_worker was called twice (once per file-backed doc under folder)
    assert app.run_worker.call_count == 2

    # Nothing has run yet: the work handed to the worker must be a coroutine
    # factory, not an already-built coroutine (which would be created eagerly
    # and leak "never awaited" if the worker is cancelled before it starts).
    works = [c.args[0] for c in app.run_worker.call_args_list]
    assert not any(inspect.isawaitable(w) for w in works)
    app.lsp.on_document_closed.assert_not_called()

    # Draining the workers notifies LSP once per doc -- each payload carries its
    # own doc (no loop late-binding) and never the scratch buffer.
    asyncio.run(_drain(works))
    lsp_closed_docs = [
        c.args[0] for c in app.lsp.on_document_closed.call_args_list
    ]
    assert sorted(d.path for d in lsp_closed_docs) == [file_a, file_b]
    assert scratch not in lsp_closed_docs

    # run_worker kwargs should match close_tab() convention
    for call in app.run_worker.call_args_list:
        assert call.kwargs.get("group") == "lsp-sync"
        assert call.kwargs.get("exclusive") is False
        assert call.kwargs.get("exit_on_error") is False

    # Verify app.docs no longer contains deleted-path documents
    remaining_paths = {d.path for d in app.docs}
    assert file_a not in remaining_paths
    assert file_b not in remaining_paths
    assert None in remaining_paths  # scratch buffer survived


def test_apply_delete_no_open_tabs_still_works(tmp_path: Path) -> None:
    """Deleting a folder with no open tabs under it should not crash."""
    folder = tmp_path / "folder"
    folder.mkdir()
    (folder / "orphan.py").write_text("pass\n")

    scratch = Document(None, TextBuffer("scratch\n"))

    app = MagicMock()
    app.docs = [scratch]
    app.doc_index = 0

    apply_delete(app, folder, "y")

    # No run_worker calls when no file-backed docs match
    assert app.run_worker.call_count == 0
    app.lsp.on_document_closed.assert_not_called()
    # docs list unchanged
    assert app.docs == [scratch]


def test_apply_delete_cancelled_does_nothing(tmp_path: Path) -> None:
    """Cancellation (non-'y' confirm) should not mutate anything."""
    folder = tmp_path / "folder"
    folder.mkdir()
    file_a = folder / "a.py"
    file_a.write_text("x = 1\n")

    doc_a = Document(file_a, TextBuffer("x = 1\n"))

    app = MagicMock()
    app.docs = [doc_a]
    app.doc_index = 0

    apply_delete(app, folder, "n")

    # Nothing should have happened
    app.workspace.remove_entry.assert_not_called()
    app.run_worker.assert_not_called()
    app.lsp.on_document_closed.assert_not_called()
    assert app.docs == [doc_a]
