"""The open documents session: tabs, the active document and search state.

:class:`EditorSession` is the single owner of the *document model* of a
running editor.  It is deliberately UI free -- it knows nothing about panes,
prompts, themes or Textual -- so every layer (widgets, keymaps, actions,
commands, extensions, diagnostics) can share the same concrete object instead
of routing ``doc`` / ``buffer`` / ``docs`` / ``doc_index`` through the
application with one protocol per consumer.

Pane binding and the visual side effects (LSP notifications, repaints) stay
with the callers: the session only reports which documents changed.

The module also carries the UI-free *window* model (``Leaf`` / ``Split`` /
``ViewState`` and the tree operations from the deleted ``pane_types`` module):
one ``Leaf`` is a document slot plus its per-document viewport state.  It lives
here because it is L1 state with L0-only dependencies, shared by ``EditorView``
and ``PaneManager`` without an intermediate type-only module.  ``EditorSession``
itself stays pane-agnostic: the window layout is owned by ``PaneManager`` (L2)
and composed by ``Editor`` (L3).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Literal, Optional, Union

from yate.config import YateConfig
from yate.editor_core import Document, SearchEngine
from yate.editor_core.buffer import Pos, TextBuffer
from yate.services.workspace import Workspace

#: Called with the documents a close operation removed (LSP didClose hook).
ClosedHook = Callable[[list[Document]], None]


class EditorSession:
    """Tabs, the active document and the search state of a running editor."""

    def __init__(
        self,
        config: YateConfig,
        *,
        on_closed: Optional[ClosedHook] = None,
    ) -> None:
        self.config = config
        self.docs: list[Document] = []
        self.index = -1
        self.search = SearchEngine()
        #: The welcome page shows on a pristine startup buffer until a user
        #: requested buffer (:enew) dismisses it; :welcome turns it back on.
        self.welcome_visible = True
        self._on_closed = on_closed

    # ------------------------------------------------------------- documents

    @property
    def doc(self) -> Document:
        """The active document."""
        return self.docs[self.index]

    @property
    def buffer(self) -> TextBuffer:
        """The buffer of the active document."""
        return self.doc.buffer

    def make_buffer(self, text: str = "") -> TextBuffer:
        """Create a buffer honoring the yaterc indentation options."""
        return TextBuffer(
            text,
            tab_width=self.config.tab_width,
            use_spaces=self.config.use_spaces,
        )

    def apply_buffer_options(self, buf: TextBuffer) -> None:
        """Propagate the yaterc indentation options onto an existing buffer."""
        buf.tab_width = self.config.tab_width
        buf.use_spaces = self.config.use_spaces

    def is_open(self, path: Path) -> Optional[Document]:
        """The document already showing *path*, or ``None``."""
        resolved = path.resolve()
        for doc in self.docs:
            if doc.path is not None and doc.path.resolve() == resolved:
                return doc
        return None

    def activate(self, doc: Document) -> None:
        """Make *doc* the active document."""
        self.index = self.docs.index(doc)

    def open(self, path: Path) -> Optional[Document]:
        """Open (or reuse) *path* and make it active.

        Returns ``None`` for a binary file; the caller reports that.
        """
        existing = self.is_open(path)
        if existing is not None:
            self.activate(existing)
            return existing
        if path.exists() and not Workspace.is_text_file(path):
            return None
        if path.exists():
            doc = Document.open(path)
        else:
            doc = Document(path, self.make_buffer())
        self.apply_buffer_options(doc.buffer)
        self.docs.append(doc)
        self.activate(doc)
        return doc

    async def open_async(self, path: Path) -> Optional[Document]:
        """Like :meth:`open`, but the disk read runs off the event loop."""
        existing = self.is_open(path)
        if existing is not None:
            self.activate(existing)
            return existing

        def _inspect() -> tuple[bool, bool]:
            return path.exists(), Workspace.is_text_file(path)

        exists, is_text = await asyncio.to_thread(_inspect)
        if exists and not is_text:
            return None
        if exists:
            doc = await Document.open_async(path)
        else:
            doc = Document(path, self.make_buffer())
        self.apply_buffer_options(doc.buffer)
        self.docs.append(doc)
        self.activate(doc)
        return doc

    def new_buffer(self) -> Document:
        """Append an empty unnamed buffer and make it active."""
        doc = Document(None, self.make_buffer())
        self.docs.append(doc)
        self.activate(doc)
        return doc

    def reset_search(self) -> None:
        """Drop the live search state (tab switches / opens clear matches)."""
        self.search = SearchEngine()

    def cycle(self, delta: int) -> Optional[Document]:
        """Activate the tab *delta* positions away (wrapping)."""
        if len(self.docs) < 2:
            return None
        index = (self.index + delta) % len(self.docs)
        self.activate(self.docs[index])
        return self.doc

    # -------------------------------------------------------------- closing

    def close_active(self) -> tuple[Document, Document]:
        """Remove the active tab; returns ``(closed, fallback)``.

        A fresh scratch buffer is appended when the last tab closes so the
        session always has an active document.
        """
        closed = self.doc
        self.docs.pop(self.index)
        if self.docs:
            fallback = self.docs[min(self.index, len(self.docs) - 1)]
        else:
            fallback = Document(None, self.make_buffer())
            self.docs.append(fallback)
        self.index = self.docs.index(fallback)
        self._notify_closed([closed])
        return closed, fallback

    def close_under(self, path: Path) -> list[Document]:
        """Close every tab whose file lives under *path* (the delete flow)."""
        target = path.resolve()
        closed = [
            doc for doc in self.docs
            if doc.path is not None and doc.path.resolve().is_relative_to(target)
        ]
        if not closed:
            return []
        self.docs = [doc for doc in self.docs if doc not in closed]
        if not self.docs:
            self.docs.append(Document(None, self.make_buffer()))
        self.index = max(0, min(self.index, len(self.docs) - 1))
        self._notify_closed(closed)
        return closed

    def retarget(self, old: Path, new: Path) -> list[Document]:
        """Keep tabs pointing at a document that was renamed on disk."""
        moved: list[Document] = []
        for doc in self.docs:
            if doc.path is not None and doc.path.resolve() == old.resolve():
                doc.path = new
                moved.append(doc)
        return moved

    def _notify_closed(self, closed: list[Document]) -> None:
        if self._on_closed is not None and closed:
            self._on_closed(closed)


# ========================================================== pane tree model
# UI-free window layout model: a Leaf is an editor window slot bound to a
# Document, a Split arranges several of them horizontally/vertically.  It
# lives here next to EditorSession (both L1, editor_core-only dependencies),
# so the L2 modules editor_view/editor.py and editor_view/panes.py can import
# it directly and no intermediate type-only module (the deleted
# editor_view/pane_types.py) is needed.  The window layout itself is still
# composed by Editor (L3) and owned by PaneManager (L2): EditorSession stays
# pane-agnostic.

#: Split axis: ``horizontal`` stacks top/bottom (:split), ``vertical`` puts
#: windows side by side (:vsplit).
Axis = Literal["horizontal", "vertical"]

#: Smallest share of a split any one pane may hold while resizing.
MIN_FRACTION = 0.12

#: Fraction transferred per ``ctrl+w +/-/< />`` keypress.
RESIZE_STEP = 0.08


@dataclass
class ViewState:
    """Per-(leaf, document) view: independent cursor, anchor and scroll."""

    cursor: Pos = (0, 0)
    anchor: Optional[Pos] = None
    scroll_col: int = 0
    scroll_row: int = 0


@dataclass
class Leaf:
    """One editor window bound to a document."""

    id: int
    doc: Document
    #: View states keyed by ``Document.uid`` so a leaf remembers the cursor
    #: position of every document it has shown.  Using a stable monotonically
    #: increasing id avoids ``id(document)`` instability when documents are
    #: recreated (e.g.  reopening after a crash).
    states: dict[int, ViewState] = field(
        default_factory=lambda: dict[int, ViewState]()
    )

    def state_for(self, doc: Document) -> ViewState:
        state = self.states.get(doc.uid)
        if state is None:
            state = ViewState(
                cursor=doc.buffer.cursor, anchor=doc.buffer.anchor
            )
            self.states[doc.uid] = state
        return state


@dataclass
class Split:
    """A horizontal/vertical arrangement; ``sizes`` sum to 1.0."""

    axis: Axis
    children: list["Node"]
    sizes: list[float]


Node = Union[Leaf, Split]


# ----------------------------------------------------------------- tree ops


def leaves(node: Node) -> list[Leaf]:
    """All leaves in screen (left-to-right, top-to-bottom) order."""
    if isinstance(node, Leaf):
        return [node]
    out: list[Leaf] = []
    for child in node.children:
        out.extend(leaves(child))
    return out


def find_leaf(node: Node, leaf_id: int) -> Optional[Leaf]:
    if isinstance(node, Leaf):
        return node if node.id == leaf_id else None
    for child in node.children:
        found = find_leaf(child, leaf_id)
        if found is not None:
            return found
    return None


def replace_node(node: Node, target: Leaf, replacement: Node) -> Node:
    """Return *node* with the *target* leaf swapped for *replacement*."""
    if isinstance(node, Leaf):
        return replacement if node is target else node
    node.children = [
        replace_node(child, target, replacement) for child in node.children
    ]
    return node


def remove_node(node: Node, target: Leaf) -> Optional[Node]:
    """Return *node* without *target*; ``None`` when *target* was the root.

    A split left with a single child collapses (the child is hoisted).
    """
    if isinstance(node, Leaf):
        return None if node is target else node
    # ``children`` and ``sizes`` are parallel lists: keep the pairs together so
    # the survivors retain *their own* fractions (slicing the first N sizes
    # would shift every fraction after the removed slot).
    kept: list[tuple[Node, float]] = []
    for child, size in zip(node.children, node.sizes):
        result = remove_node(child, target)
        if result is None:
            # the target leaf lived directly in this split: drop it
            continue
        kept.append((result, size))
    if len(kept) == 1:
        return kept[0][0]
    node.children = [child for child, _size in kept]
    node.sizes = _normalized([size for _child, size in kept])
    return node


def find_axis_split(
    node: Node, target: Leaf, axis: Axis
) -> Optional[tuple[Split, int]]:
    """Deepest *axis* split on the path to *target* + the child index whose
    subtree contains the target (the slot to resize)."""
    if isinstance(node, Leaf):
        return None
    target_index = -1
    for i, child in enumerate(node.children):
        if find_leaf(child, target.id) is not None:
            target_index = i
            break
    if target_index < 0:
        return None
    # Prefer a deeper matching split (resize the tightest enclosing group).
    deeper = find_axis_split(node.children[target_index], target, axis)
    if deeper is not None:
        return deeper
    return (node, target_index) if node.axis == axis else None


def _normalized(sizes: list[float]) -> list[float]:
    total = sum(sizes) or 1.0
    return [s / total for s in sizes]
