"""Tests for yate.editor_view.explorer (ExplorerTree) and the session-side
document cleanup behind it (EditorSession.close_under / Editor._lsp_documents_closed)."""

# pyright: reportPrivateUsage=false

from __future__ import annotations

import asyncio
import inspect
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import MagicMock

from yate.config import YateConfig
from yate.editor import Editor
from yate.editor_core.buffer import TextBuffer
from yate.editor_core.document import Document
from yate.editor_view.explorer import ExplorerTree
from yate.session import EditorSession


async def _drain(works: list[object]) -> None:
    """Run every worker payload the way Textual's Worker would."""
    for work in works:
        # Textual only accepts coroutine functions (or awaitables) here; a plain
        # sync callable is rejected with WorkerError.
        assert inspect.iscoroutinefunction(work)
        await work()


class _FakePrompt:
    """Minimal PromptBar stand-in: records writes, accepts prompts on demand."""

    def __init__(self, *, allows: bool = True) -> None:
        self.allows = allows
        self.modes: list[str] = []
        self.writes: list[tuple[str, str]] = []

    def activate(
        self,
        mode: str,
        *,
        placeholder: str = "",
        initial: str = "",
        on_submit: object = None,
        refocus: object = None,
    ) -> bool:
        self.modes.append(mode)
        return self.allows

    def write(self, text: str, kind: str = "info") -> None:
        self.writes.append((text, kind))


def _make_tree(
    session: EditorSession, prompt: _FakePrompt
) -> tuple[ExplorerTree, MagicMock]:
    """Build an ExplorerTree off-app with a stub workspace (no root open)."""
    workspace = MagicMock()
    workspace.root = None
    tree = ExplorerTree(
        session,
        workspace,
        cast(Any, prompt),
        open_path=lambda path: None,
        focus_editor=lambda: None,
        window_prefix=lambda event: False,
    )
    return tree, workspace


# --- ExplorerTree.submit_delete --------------------------------------------


def test_submit_delete_confirmed_mutates_and_closes(tmp_path: Path) -> None:
    """A confirmed delete removes the entry and closes affected tabs."""
    victim = tmp_path / "folder"
    session = EditorSession(YateConfig())
    opened = Document(victim / "child.py", TextBuffer("x = 1\n"))
    session.docs = [opened]
    session.index = 0
    prompt = _FakePrompt()
    tree, workspace = _make_tree(session, prompt)

    tree.prompt_delete(victim)
    tree.submit_delete("y")

    workspace.remove_entry.assert_called_once_with(victim)
    # the open tab under the folder was closed by the session
    assert opened not in session.docs
    # the delete is reported, including the closed-tab count
    assert any("deleted" in text for text, _kind in prompt.writes)
    assert any("closed 1 open tab" in text for text, _kind in prompt.writes)


def test_submit_delete_cancelled_does_nothing(tmp_path: Path) -> None:
    """Cancellation (non-'y' confirm) should not mutate anything."""
    victim = tmp_path / "folder"
    session = EditorSession(YateConfig())
    opened = Document(victim / "child.py", TextBuffer("x = 1\n"))
    session.docs = [opened]
    session.index = 0
    prompt = _FakePrompt()
    tree, workspace = _make_tree(session, prompt)

    tree.prompt_delete(victim)
    tree.submit_delete("n")

    workspace.remove_entry.assert_not_called()
    assert session.docs == [opened]
    assert prompt.writes == [("delete cancelled", "info")]


# --- EditorSession.close_under / Editor._lsp_documents_closed --------------


class _LspRecorder:
    """Minimal LspManager stand-in recording the didClose notifications."""

    def __init__(self) -> None:
        self.closed: list[Document] = []

    async def on_document_closed(self, doc: Document) -> None:
        self.closed.append(doc)


def _session_with_hook(lsp: _LspRecorder) -> tuple[EditorSession, MagicMock]:
    app = MagicMock()
    host = SimpleNamespace(app=app, lsp=lsp)
    notify = cast(Any, Editor._lsp_documents_closed)
    session = EditorSession(
        YateConfig(), on_closed=lambda closed: notify(host, closed)
    )
    return session, app


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

    lsp = _LspRecorder()
    session, app = _session_with_hook(lsp)
    session.docs = [doc_a, doc_b, scratch]
    session.index = 0

    session.close_under(folder)

    # run_worker was called twice (once per file-backed doc under folder)
    assert app.run_worker.call_count == 2

    # Nothing has run yet: the work handed to the worker must be a coroutine
    # factory, not an already-built coroutine (which would be created eagerly
    # and leak "never awaited" if the worker is cancelled before it starts).
    works = [c.args[0] for c in app.run_worker.call_args_list]
    assert not any(inspect.isawaitable(w) for w in works)
    assert lsp.closed == []

    # Draining the workers notifies LSP once per doc -- each payload carries its
    # own doc (no loop late-binding) and never the scratch buffer.
    asyncio.run(_drain(works))
    assert {d.path for d in lsp.closed} == {file_a, file_b}
    assert scratch not in lsp.closed

    # run_worker kwargs should match close_tab() convention
    for call in app.run_worker.call_args_list:
        assert call.kwargs.get("group") == "lsp-sync"
        assert call.kwargs.get("exclusive") is False
        assert call.kwargs.get("exit_on_error") is False

    # Verify the session no longer contains deleted-path documents
    remaining_paths = {d.path for d in session.docs}
    assert file_a not in remaining_paths
    assert file_b not in remaining_paths
    assert None in remaining_paths  # scratch buffer survived


def test_close_documents_under_no_open_tabs_is_noop(tmp_path: Path) -> None:
    """A folder with no open tabs under it should not crash."""
    folder = tmp_path / "folder"
    folder.mkdir()
    (folder / "orphan.py").write_text("pass\n")

    scratch = Document(None, TextBuffer("scratch\n"))

    lsp = _LspRecorder()
    session, app = _session_with_hook(lsp)
    session.docs = [scratch]
    session.index = 0

    closed = session.close_under(folder)

    # No run_worker calls when no file-backed docs match
    assert closed == []
    assert app.run_worker.call_count == 0
    assert lsp.closed == []
    # docs list unchanged
    assert session.docs == [scratch]
