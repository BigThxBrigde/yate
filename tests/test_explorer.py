"""Tests for yate.app_features.explorer (ExplorerFeature) and the app-side
document cleanup behind it (YateApp.close_documents_under)."""

from __future__ import annotations

import asyncio
import inspect
from pathlib import Path
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock

from yate.app import YateApp
from yate.app_features.explorer import ExplorerFeature
from yate.editor_core.buffer import TextBuffer
from yate.editor_core.document import Document


async def _drain(works: list[object]) -> None:
    """Run every worker payload the way Textual's Worker would."""
    for work in works:
        # Textual only accepts coroutine functions (or awaitables) here; a plain
        # sync callable is rejected with WorkerError.
        assert inspect.iscoroutinefunction(work)
        await work()


def _bare_app() -> Any:
    """A YateApp instance without __init__/mount: only the close-docs path."""
    app = cast(Any, object.__new__(YateApp))
    app.run_worker = MagicMock()
    app.new_buffer = MagicMock()
    app.message = MagicMock()
    app.lsp = MagicMock()
    app.lsp.on_document_closed = AsyncMock()
    return app


# --- ExplorerFeature.submit_delete -----------------------------------------


def test_submit_delete_confirmed_mutates_and_closes(tmp_path: Path) -> None:
    """A confirmed delete removes the entry and closes affected tabs."""
    host = MagicMock()
    host.activate_prompt.return_value = True
    workspace = MagicMock()
    feature = ExplorerFeature(host, workspace)
    victim = tmp_path / "folder"

    feature.prompt_delete(victim)
    feature.submit_delete("y")

    workspace.remove_entry.assert_called_once_with(victim)
    host.close_documents_under.assert_called_once_with(victim)
    host.refresh_explorer.assert_called_once()
    host.message.assert_called()


def test_submit_delete_cancelled_does_nothing(tmp_path: Path) -> None:
    """Cancellation (non-'y' confirm) should not mutate anything."""
    host = MagicMock()
    host.activate_prompt.return_value = True
    workspace = MagicMock()
    feature = ExplorerFeature(host, workspace)

    feature.prompt_delete(tmp_path / "folder")
    feature.submit_delete("n")

    workspace.remove_entry.assert_not_called()
    host.close_documents_under.assert_not_called()
    host.refresh_explorer.assert_not_called()


# --- YateApp.close_documents_under -----------------------------------------


def test_close_documents_under_notifies_lsp_did_close(tmp_path: Path) -> None:
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

    app = _bare_app()
    app.docs = [doc_a, doc_b, scratch]
    app.doc_index = 0

    app.close_documents_under(folder)

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


def test_close_documents_under_no_open_tabs_is_noop(tmp_path: Path) -> None:
    """A folder with no open tabs under it should not crash."""
    folder = tmp_path / "folder"
    folder.mkdir()
    (folder / "orphan.py").write_text("pass\n")

    scratch = Document(None, TextBuffer("scratch\n"))

    app = _bare_app()
    app.docs = [scratch]
    app.doc_index = 0

    app.close_documents_under(folder)

    # No run_worker calls when no file-backed docs match
    assert app.run_worker.call_count == 0
    app.lsp.on_document_closed.assert_not_called()
    # docs list unchanged
    assert app.docs == [scratch]
