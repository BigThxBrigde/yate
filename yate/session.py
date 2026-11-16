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

Macro registers are session-level, in-memory, and never persisted.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from yate.config import YateConfig
from yate.editor_core import Document, SearchEngine
from yate.editor_core.buffer import Pos, TextBuffer
from yate.editor_core.chunked import ChunkedFallback
from yate.logs import tracing
from yate.services.workspace import Workspace

#: Called with the documents a close operation removed (LSP didClose hook).
type ClosedHook = Callable[[list[Document]], None]

#: Called with each document freshly opened from disk (chunked-attach hook).
type OpenedHook = Callable[[Document], None]


@dataclass
class MacroState:
    """Session-level macro registers and the recording / replay state (L1)."""

    registers: dict[str, tuple[str, ...]] = field(
        default_factory=dict[str, tuple[str, ...]]
    )
    recording: str | None = None
    buffer: list[str] = field(default_factory=list[str])
    awaiting: Literal["record", "play"] | None = None
    last_played: tuple[str, int] | None = None
    playing: bool = False
    play_depth: int = 0
    pending_count: int = 1

    def recording_label(self) -> str | None:
        """Return the ``rec @<reg>`` status-bar label, or ``None``."""
        return f"rec @{self.recording}" if self.recording is not None else None

    def get(self, reg: str) -> tuple[str, ...]:
        """Return the recorded raw keys for *reg*, or ``()`` when unrecorded."""
        return self.registers.get(reg, ())


#: Legal single-character mark names (v1: lowercase letters only). Lives
#: here (L1) instead of keymaps/keys.py so the L3 command table can import
#: it downward without a cross-L3 module dependency.
MARK_NAME_CHARS: str = "abcdefghijklmnopqrstuvwxyz"

#: Capacity of each jump-list stack (issue IKUOCI: 100).
JUMP_LIST_LIMIT: int = 100


@dataclass(frozen=True)
class Mark:
    """One buffer-local named mark: an exact buffer position (row, col)."""

    row: int
    col: int


class MarkBook:
    """Per-buffer named marks keyed by ``Document.uid`` (L1, UI-free)."""

    def __init__(self) -> None:
        self._by_doc: dict[int, dict[str, Mark]] = {}

    def set(self, uid: int, name: str, row: int, col: int) -> None:
        """Set (or overwrite) mark *name* on document *uid* at (row, col)."""
        if len(name) != 1 or name not in MARK_NAME_CHARS:
            raise ValueError(f"mark name must be one of a-z: {name!r}")
        self._by_doc.setdefault(uid, {})[name] = Mark(row, col)

    def get(self, uid: int, name: str) -> Mark | None:
        """The mark *name* on *uid*, or ``None``."""
        return self._by_doc.get(uid, {}).get(name)

    def delete(self, uid: int, name: str) -> bool:
        """Delete mark *name* on *uid*; ``False`` when it was not set."""
        marks = self._by_doc.get(uid)
        if marks is None or name not in marks:
            return False
        del marks[name]
        return True

    def drop_doc(self, uid: int) -> None:
        """Drop every mark of document *uid* (buffer close cleanup)."""
        self._by_doc.pop(uid, None)

    def all_marks(self) -> list[tuple[int, str, Mark]]:
        """Every mark as ``(uid, name, mark)`` rows: docs in insertion
        order, names sorted within each doc."""
        rows: list[tuple[int, str, Mark]] = []
        for uid in self._by_doc:
            for name in sorted(self._by_doc[uid]):
                rows.append((uid, name, self._by_doc[uid][name]))
        return rows


@dataclass(frozen=True)
class JumpEntry:
    """One jump-list entry: where a jump started (resolved via uid)."""

    uid: int
    path: str  # display string ("[no name]" for scratch buffers)
    row: int
    col: int


class JumpList:
    """Session-level jump history: a back stack and a forward stack (L1).

    Producers call :meth:`push` with the position a jump *leaves*;
    navigation pops one stack while pushing the current position onto the
    other, so alt-left/alt-right round-trip and boundaries are empty stacks
    (no looping, no pointer arithmetic).
    """

    def __init__(self) -> None:
        self._back: list[JumpEntry] = []
        self._forward: list[JumpEntry] = []

    def push(self, origin: JumpEntry) -> None:
        """Record *origin* as the position a new jump leaves behind.

        A new jump discards the forward branch; pushing the same position
        consecutively dedups (the forward branch still clears).
        """
        self._forward.clear()
        if self._back and self._back[-1] == origin:
            return
        self._back.append(origin)
        if len(self._back) > JUMP_LIST_LIMIT:
            del self._back[0]

    def take_back(self, current: JumpEntry) -> JumpEntry | None:
        """Pop the newest back entry; *current* becomes forward-reachable."""
        if not self._back:
            return None
        target = self._back.pop()
        self._forward.append(current)
        if len(self._forward) > JUMP_LIST_LIMIT:
            del self._forward[0]
        return target

    def take_forward(self, current: JumpEntry) -> JumpEntry | None:
        """Pop the newest forward entry; *current* becomes back-reachable."""
        if not self._forward:
            return None
        target = self._forward.pop()
        self._back.append(current)
        if len(self._back) > JUMP_LIST_LIMIT:
            del self._back[0]
        return target

    def drop_docs(self, uids: set[int]) -> None:
        """Prune entries whose document closed (buffer close cleanup)."""
        self._back = [e for e in self._back if e.uid not in uids]
        self._forward = [e for e in self._forward if e.uid not in uids]

    def stacks(self) -> tuple[list[JumpEntry], list[JumpEntry]]:
        """``(back, forward)`` snapshots for the :jumps view (back is
        oldest-to-newest; the current position sits between the stacks)."""
        return (list(self._back), list(self._forward))


log = tracing.get_logger(__name__)


class EditorSession:
    """Tabs, the active document and the search state of a running editor."""

    def __init__(
        self,
        config: YateConfig,
        *,
        on_closed: ClosedHook | None = None,
        on_opened: OpenedHook | None = None,
    ) -> None:
        self.config = config
        self.docs: list[Document] = []
        self.index = -1
        self.search = SearchEngine()
        #: The welcome page shows on a pristine startup buffer until a user
        #: requested buffer (:enew) dismisses it; :welcome turns it back on.
        self.welcome_visible = True
        self._on_closed = on_closed
        self._on_opened = on_opened
        self.macro = MacroState()
        self.marks = MarkBook()
        self.jumps = JumpList()

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

    def is_open(self, path: Path) -> Document | None:
        """The document already showing *path*, or ``None``."""
        resolved = path.resolve()
        for doc in self.docs:
            if doc.resolved_path == resolved:
                return doc
        return None

    def activate(self, doc: Document) -> None:
        """Make *doc* the active document."""
        self.index = self.docs.index(doc)

    def open(self, path: Path) -> Document | None:
        """Open (or reuse) *path* and make it active.

        Returns ``None`` for a binary file; the caller reports that.
        Files above ``config.large_file.threshold`` open as locked,
        progressively filled chunked documents.
        """
        existing = self.is_open(path)
        if existing is not None:
            self.activate(existing)
            return existing
        if path.exists() and not Workspace.is_text_file(path):
            return None
        if path.exists():
            doc = self._open_sized(path)
        else:
            doc = Document(path, self.make_buffer())
        self.apply_buffer_options(doc.buffer)
        self.docs.append(doc)
        self.activate(doc)
        self._notify_opened(doc)
        log.debug("session open: %s (%d docs)", path, len(self.docs))
        return doc

    async def open_async(self, path: Path) -> Document | None:
        """Like :meth:`open`, but the disk read runs off the event loop."""
        existing = self.is_open(path)
        if existing is not None:
            self.activate(existing)
            return existing

        def _inspect() -> tuple[bool, bool, int]:
            exists = path.exists()
            size = path.stat().st_size if exists else 0
            return exists, Workspace.is_text_file(path), size

        exists, is_text, size = await asyncio.to_thread(_inspect)
        if exists and not is_text:
            return None
        if exists:
            doc = await asyncio.to_thread(self._open_sized, path, size)
        else:
            doc = Document(path, self.make_buffer())
        self.apply_buffer_options(doc.buffer)
        self.docs.append(doc)
        self.activate(doc)
        self._notify_opened(doc)
        log.debug("session open (async): %s (%d docs)", path, len(self.docs))
        return doc

    def _open_sized(self, path: Path, size: int | None = None) -> Document:
        """Open *path*, chunked when it exceeds the large-file threshold.

        A size of ``None`` stats the file (sync path); the async open
        passes the size its inspect task already collected.  A file whose
        shape cannot be chunk-aligned (CR-only line endings,
        :class:`~yate.editor_core.chunked.ChunkedFallback`) falls back to
        the plain full read.
        """
        threshold = self.config.large_file.threshold
        if size is None:
            size = path.stat().st_size
        if threshold > 0 and size > threshold:
            try:
                doc = Document.open_chunked(path)
            except ChunkedFallback:
                log.info("chunked open fell back to full load: %s", path)
            else:
                log.info("opened chunked: %s (%d bytes)", path, size)
                return doc
        return Document.open(path)

    def _notify_opened(self, doc: Document) -> None:
        if self._on_opened is not None:
            self._on_opened(doc)

    def new_buffer(self) -> Document:
        """Append an empty unnamed buffer and make it active."""
        doc = Document(None, self.make_buffer())
        self.docs.append(doc)
        self.activate(doc)
        log.debug("session new buffer (%d docs)", len(self.docs))
        return doc

    def reset_search(self) -> None:
        """Drop the live search state (tab switches / opens clear matches)."""
        self.search = SearchEngine()

    def doc_by_uid(self, uid: int) -> Document | None:
        """The open document with *uid*, or ``None`` (closed buffers)."""
        for doc in self.docs:
            if doc.uid == uid:
                return doc
        return None

    def current_jump_entry(self) -> JumpEntry:
        """The active document's cursor as a jump-list entry."""
        doc = self.doc
        return JumpEntry(
            doc.uid, doc.display_path, doc.buffer.row, doc.buffer.col
        )

    def push_jump(
        self, doc: Document | None = None, *, row: int | None = None,
        col: int | None = None,
    ) -> None:
        """Record the position a jump leaves behind (the single push contract).

        Defaults capture the active document's cursor.  Jump producers --
        mark jumps, ``:42``/ctrl-g line jumps, and the future LSP
        goto-definition flow -- call only this; the stacks are L1-internal.
        """
        origin_doc = doc if doc is not None else self.doc
        r = origin_doc.buffer.row if row is None else row
        c = origin_doc.buffer.col if col is None else col
        self.jumps.push(
            JumpEntry(origin_doc.uid, origin_doc.display_path, r, c)
        )

    def jump_back(self) -> JumpEntry | None:
        """Step one entry back; ``None`` at the boundary (empty back stack)."""
        return self.jumps.take_back(self.current_jump_entry())

    def jump_forward(self) -> JumpEntry | None:
        """Step one entry forward; ``None`` at the boundary."""
        return self.jumps.take_forward(self.current_jump_entry())

    def cycle(self, delta: int) -> Document | None:
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
        # Detach the chunked source: the background scan loop checks it and
        # exits on its next turn instead of reading the whole file for a
        # document nobody displays anymore.
        closed.chunked = None
        self.marks.drop_doc(closed.uid)
        self.jumps.drop_docs({closed.uid})
        log.debug("session close: %s (%d docs left)", closed.path, len(self.docs))
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
            if doc.resolved_path is not None
            and doc.resolved_path.is_relative_to(target)
        ]
        if not closed:
            return []
        active = self.docs[self.index] if 0 <= self.index < len(self.docs) else None
        self.docs = [doc for doc in self.docs if doc not in closed]
        if not self.docs:
            self.docs.append(Document(None, self.make_buffer()))
        if active is not None and active not in closed:
            # The active tab survived: keep it active by identity, because
            # removing preceding tabs shifts its index downward.
            self.index = self.docs.index(active)
        else:
            # The active tab was among the closed ones (or absent): fall back
            # to a surviving neighbour, matching close_active's behaviour.
            self.index = min(max(self.index, 0), len(self.docs) - 1)
        log.debug("session close under %s: %d doc(s)", path, len(closed))
        for doc in closed:
            doc.chunked = None  # stop the background scans (see close_active)
            self.marks.drop_doc(doc.uid)
        self.jumps.drop_docs({doc.uid for doc in closed})
        self._notify_closed(closed)
        return closed

    def retarget(self, old: Path, new: Path) -> list[Document]:
        """Keep tabs pointing at a document that was renamed on disk."""
        moved: list[Document] = []
        target = old.resolve()
        for doc in self.docs:
            if doc.resolved_path == target:
                doc.path = new
                moved.append(doc)
        if moved:
            log.debug("session retarget: %s -> %s (%d doc(s))", old, new, len(moved))
        return moved

    def _notify_closed(self, closed: list[Document]) -> None:
        if self._on_closed is not None and closed:
            self._on_closed(closed)


# ========================================================== pane tree model
# UI-free window layout model: a Leaf is an editor window slot bound to a
# Document, a Split arranges several of them horizontally/vertically.  It
# lives here next to EditorSession (both L1, editor_core-only dependencies),
# so the L2 modules editor_components/view.py and editor_components/panes.py can import
# it directly and no intermediate type-only module (the deleted
# editor_components/pane_types.py) is needed.  The window layout itself is still
# composed by Editor (L3) and owned by PaneManager (L2): EditorSession stays
# pane-agnostic.

#: Split axis: ``horizontal`` stacks top/bottom (:split), ``vertical`` puts
#: windows side by side (:vsplit).
Axis = Literal["horizontal", "vertical"]

#: Smallest share of a split any one pane may hold while resizing.
MIN_FRACTION: float = 0.12

#: Fraction transferred per ``ctrl+w +/-/< />`` keypress.
RESIZE_STEP: float = 0.08


@dataclass
class ViewState:
    """Per-(leaf, document) view: independent cursor, anchor and scroll."""

    cursor: Pos = (0, 0)
    anchor: Pos | None = None
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
        """The view state for *doc*, created from its cursor on first use."""
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
    children: list[Node]
    sizes: list[float]


Node = Leaf | Split


# ----------------------------------------------------------------- tree ops


def leaves(node: Node) -> list[Leaf]:
    """All leaves in screen (left-to-right, top-to-bottom) order."""
    if isinstance(node, Leaf):
        return [node]
    out: list[Leaf] = []
    for child in node.children:
        out.extend(leaves(child))
    return out


def find_leaf(node: Node, leaf_id: int) -> Leaf | None:
    """The leaf with *leaf_id*, or ``None`` when absent."""
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


def remove_node(node: Node, target: Leaf) -> Node | None:
    """Return *node* without *target*; ``None`` when *target* was the root.

    A split left with a single child collapses (the child is hoisted) --
    but only when something was actually removed: a call whose *target*
    never lived in the tree keeps the shape untouched instead of hoisting
    a lone child of the root.
    """
    if isinstance(node, Leaf):
        return None if node is target else node
    # ``children`` and ``sizes`` are parallel lists: keep the pairs together so
    # the survivors retain *their own* fractions (slicing the first N sizes
    # would shift every fraction after the removed slot).  A mismatch would
    # silently truncate the tree, so it is refused outright -- an explicit
    # raise (review 2026-10-03 #52.1): a bare ``assert`` vanishes under ``-O``.
    if len(node.children) != len(node.sizes):
        raise ValueError(
            "Split invariant broken: "
            f"{len(node.children)} children vs {len(node.sizes)} sizes"
        )
    kept: list[tuple[Node, float]] = []
    removed_here = False
    for child, size in zip(node.children, node.sizes):
        result = remove_node(child, target)
        if result is None:
            # the target leaf lived directly in this split: drop it
            removed_here = True
            continue
        kept.append((result, size))
    if not removed_here and all(
        result is child for (result, _size), child in zip(kept, node.children)
    ):
        # Nothing was removed anywhere in this subtree and every survivor is
        # the very child object we started with: the rebuild below would be
        # a no-op, and hoisting a lone child here would reshape the tree
        # without an actual removal.
        return node
    if len(kept) == 1:
        return kept[0][0]
    node.children = [child for child, _size in kept]
    node.sizes = _normalized([size for _child, size in kept])
    return node


def find_axis_split(
    node: Node, target: Leaf, axis: Axis
) -> tuple[Split, int] | None:
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
