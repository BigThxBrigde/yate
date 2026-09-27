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

from rich.style import Style
from rich.text import Text
from textual.widgets import Tree
from textual.widgets.tree import TreeNode

from yate.config import YateConfig
from yate.editor import Editor
from yate.editor_core.buffer import TextBuffer
from yate.editor_core.document import Document
from yate.editor_view.explorer import ExplorerTree
from yate.editor_view.icons import FOLDER, FOLDER_OPEN
from yate.services.workspace import Workspace
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

    # no run_worker calls when no file-backed docs match
    assert closed == []
    assert app.run_worker.call_count == 0
    assert lsp.closed == []
    # docs list unchanged
    assert session.docs == [scratch]


# --- S37 regression: a vanished selection is forgotten -----------------------


def test_restore_cursor_forgets_vanished_selection(tmp_path: Path) -> None:
    """Deleting the selected entry must clear ``_last_selected`` (S37).

    A deleted / renamed selection must not stay pinned: ``refresh_tree``
    defers cursor restoration via ``call_after_refresh`` -- without a
    running app the deferred callback is invoked manually after the
    rebuild, exactly as the next refresh pass would.
    """
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "a.txt").write_text("a\n", encoding="utf-8")
    victim = ws / "b.txt"
    victim.write_text("b\n", encoding="utf-8")
    tree = ExplorerTree(
        EditorSession(YateConfig()),
        Workspace(ws),
        cast(Any, _FakePrompt()),
        open_path=lambda path: None,
        focus_editor=lambda: None,
        window_prefix=lambda event: False,
    )

    tree.refresh_tree()
    # the user had selected (opened) the last entry ...
    tree._last_selected = victim
    # ... and it is deleted afterwards (explorer ``d`` flow / external)
    victim.unlink()
    tree.refresh_tree()
    tree._restore_cursor(victim)

    assert tree._last_selected is None


# --- icon-only toggle affordance (issue IKINF3) ------------------------------


def _tree_over(ws_root: Path) -> ExplorerTree:
    """Build an ExplorerTree over a real workspace root (no app)."""
    return ExplorerTree(
        EditorSession(YateConfig()),
        Workspace(ws_root),
        cast(Any, _FakePrompt()),
        open_path=lambda path: None,
        focus_editor=lambda: None,
        window_prefix=lambda event: False,
    )


def _label_text(node: TreeNode[Path | None]) -> str:
    """Plain text of a node label (``TreeNode.label`` is Text | str)."""
    label = node.label
    return label.plain if isinstance(label, Text) else label


def test_toggle_arrow_glyphs_are_suppressed(tmp_path: Path) -> None:
    """Rendered labels never contain Textual's default arrow glyphs."""
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "sub").mkdir()
    (ws / "file.py").write_text("x = 1\n", encoding="utf-8")
    tree = _tree_over(ws)

    assert ExplorerTree.ICON_NODE == ""
    assert ExplorerTree.ICON_NODE_EXPANDED == ""

    tree.refresh_tree()
    for node in [tree.root, *tree.root.children]:
        rendered = tree.render_label(node, Style(), Style()).plain
        assert "\u25b6" not in rendered  # Tree.ICON_NODE default "▶ "
        assert "\u25bc" not in rendered  # Tree.ICON_NODE_EXPANDED default "▼ "


def test_folder_glyph_flips_with_expansion(tmp_path: Path) -> None:
    """The folder glyph itself carries the open/closed state on toggle."""
    ws = tmp_path / "ws"
    ws.mkdir()
    sub = ws / "sub"
    sub.mkdir()
    (sub / "inner.py").write_text("x = 1\n", encoding="utf-8")
    tree = _tree_over(ws)
    tree.refresh_tree()

    node = tree._find_node(tree.root, sub)
    assert node is not None
    assert FOLDER in _label_text(node)
    assert FOLDER_OPEN not in _label_text(node)

    node.expand()
    tree.on_tree_node_expanded(Tree.NodeExpanded(node))
    assert FOLDER_OPEN in _label_text(node)

    node.collapse()
    tree.on_tree_node_collapsed(Tree.NodeCollapsed(node))
    assert FOLDER in _label_text(node)
    assert FOLDER_OPEN not in _label_text(node)


def test_refresh_tree_keeps_open_glyph_for_expanded_dirs(tmp_path: Path) -> None:
    """Rebuilding the tree renders the open glyph for expanded directories."""
    ws = tmp_path / "ws"
    ws.mkdir()
    sub = ws / "sub"
    sub.mkdir()
    (sub / "inner.py").write_text("x = 1\n", encoding="utf-8")
    tree = _tree_over(ws)
    tree.refresh_tree()

    node = tree._find_node(tree.root, sub)
    assert node is not None
    node.expand()
    tree.on_tree_node_expanded(Tree.NodeExpanded(node))
    assert FOLDER_OPEN in _label_text(node)

    tree.refresh_tree()
    rebuilt = tree._find_node(tree.root, sub)
    assert rebuilt is not None
    assert rebuilt.is_expanded
    assert FOLDER_OPEN in _label_text(rebuilt)


def test_indent_rails_align_under_parent_icon(tmp_path: Path) -> None:
    """Rails and terminators draw in the node's own slot (under the parent
    icon); non-last nodes keep a bare rail instead of the "├─" cross."""
    for lines in ExplorerTree.LINES.values():
        space, vertical, terminator, cross = lines
        assert len(space) == 2 and len(vertical) == 2, "slots stay 2 cells"
        assert terminator in ("\u2514 ", "\u2517 ", "\u255a "), "last child gets a terminator"
        assert cross.endswith(" "), "cross keeps a bare rail"
    # slot geometry: vertical/terminator sit in the node's own slot, exactly
    # one slot left of its icon == directly under the parent icon.
    assert ExplorerTree.LINES["default"] == ("  ", "\u2502 ", "\u2514 ", "\u2502 ")


def test_tree_h_scrollbar_stays_available_and_thin(tmp_path: Path) -> None:
    """Horizontal scrolling stays reachable with a one-cell scrollbar."""
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "file.py").write_text("x = 1\n", encoding="utf-8")
    _tree_over(ws)
    assert "scrollbar-size-horizontal: 1" in ExplorerTree.DEFAULT_CSS
    assert "overflow-x: hidden" not in ExplorerTree.DEFAULT_CSS


def test_guide_colors_constant_on_hover_and_selection() -> None:
    """Guides share the resting tint in every state: hover, selected,
    focused and light-mode variants must not repaint the rails mauve."""
    css = ExplorerTree.DEFAULT_CSS
    for variant in ("& > ", "&:focus > ", "&:light > "):
        for cls in ("tree--guides", "tree--guides-hover", "tree--guides-selected"):
            selector = f"{variant}.{cls}"
            assert selector in css, f"missing pinned selector {selector}"
            block = css.split(selector, 1)[1].split("}", 1)[0]
            assert "15%" in block, f"{selector} must pin the resting tint"
