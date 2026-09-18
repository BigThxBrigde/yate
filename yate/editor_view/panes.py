"""Split panes (vim ``:split`` / ``:vsplit``): window tree manager + host.

The pane system mirrors vim's window/buffer split:

* a :class:`Leaf` is one editor window bound to one :class:`Document`;
* a :class:`Split` is a horizontal (top/bottom, ``:split``) or vertical
  (left/right, ``:vsplit``) arrangement of child nodes with fractional sizes;
* the same Document may be bound to several leaves, each keeping its own
  :class:`ViewState` (cursor, selection anchor and scroll position), which is
  what makes the two windows' cursors independent;
* text/undo/LSP state stays shared in the Document/Buffer. While a leaf is
  active its view state is mirrored onto the buffer (all edit code keeps
  working unchanged); focus switches capture/restore through
  :meth:`PaneManager.capture_active` / :meth:`PaneManager.apply_doc`.

:class:`PaneHost` is the thin Textual side: it builds one widget subtree per
model tree (``Horizontal``/``Vertical`` boxes containing :class:`EditorView`
leaves) and fully reconciles it after structural changes. Editor views are
deliberately cheap and disposable -- every durable state lives in the model.

The pure data model (:class:`Leaf`, :class:`Split`, :class:`Node`,
:class:`ViewState`, and the tree utility functions) lives in
:mod:`yate.editor_view.pane_types` to avoid a type-level cycle with
:mod:`yate.editor_view.editor`.
"""

from __future__ import annotations

from itertools import count
from typing import Optional

from textual.containers import Horizontal, Vertical
from textual.widget import Widget

from yate.editor_core.document import Document
from yate.editor_view.editor import EditorView
from yate.interfaces import AppProtocol

from yate.editor_view.pane_types import (
    MIN_FRACTION,
    RESIZE_STEP,
    Axis,
    Leaf,
    Node,
    Split,
    ViewState,
    find_axis_split,
    find_leaf,
    leaves,
    remove_node,
    replace_node,
)

# Re-export for backward compatibility -- external code imports from panes.
# DEPRECATED: prefer ``from yate.editor_view.pane_types import Axis, Leaf, ...``
# These re-exports may be removed in a future version.
__all__ = [
    "Axis",
    "Leaf",
    "Node",
    "Split",
    "ViewState",
    "PaneManager",
    "PaneHost",
]


# ================================================================ manager


class PaneManager:
    """Owns the pane tree and mediates between app and widgets."""

    def __init__(self, app: AppProtocol, doc: Document) -> None:
        self.app = app
        self._ids = count(1)
        first = Leaf(next(self._ids), doc)
        self.root: Node = first
        self.active: Leaf = first
        self.host: Optional[PaneHost] = None
        #: Mounted views keyed by leaf id; rebuilt on every reconcile.
        self.views: dict[int, EditorView] = {}

    # ------------------------------------------------------------- lookups

    def attach(self, host: PaneHost) -> None:
        self.host = host

    @property
    def leaf_count(self) -> int:
        return len(leaves(self.root))

    @property
    def active_view(self) -> Optional[EditorView]:
        return self.views.get(self.active.id)

    def all_views(self) -> list[EditorView]:
        return [view for leaf in leaves(self.root)
                if (view := self.views.get(leaf.id)) is not None]

    def views_for(self, doc: Document) -> list[EditorView]:
        return [view for leaf in leaves(self.root)
                if leaf.doc is doc
                and (view := self.views.get(leaf.id)) is not None]

    def leaf_for(self, leaf_id: int) -> Optional[Leaf]:
        """Non-asserting leaf lookup for render paths that must tolerate a
        leaf already dropped from the tree (a structural reconcile such as
        ``:only`` while a framework timer still paints the removed widget).
        :meth:`leaf_by_id` stays strict for code owning the live-view
        invariant (focus, keypress, active-view logic)."""
        return find_leaf(self.root, leaf_id)

    def leaf_by_id(self, leaf_id: int) -> Leaf:
        leaf = find_leaf(self.root, leaf_id)
        # the id always comes from a live EditorView built from this tree
        assert leaf is not None, f"pane leaf {leaf_id} not found"
        return leaf

    def make_leaf(
        self, doc: Document, *, inherit: Optional[Leaf] = None
    ) -> Leaf:
        """Create a leaf; optionally clone one document's view state
        (``:split`` without arguments opens at the same cursor position)."""
        leaf = Leaf(next(self._ids), doc)
        if inherit is not None:
            state = inherit.states.get(doc.uid)
            if state is not None:
                leaf.states[doc.uid] = ViewState(
                    cursor=state.cursor,
                    anchor=state.anchor,
                    scroll_col=state.scroll_col,
                    scroll_row=state.scroll_row,
                )
        return leaf

    # ------------------------------------------------- active/state syncing

    def _clamp(self, doc: Document, pos: tuple[int, int]) -> tuple[int, int]:
        buf = doc.buffer
        row = max(0, min(pos[0], buf.line_count - 1))
        col = max(0, min(pos[1], len(buf.lines[row])))
        return (row, col)

    def capture_active(self) -> None:
        """Persist the buffer cursor/anchor and the widget scroll into the
        active leaf's view state (call before changing active document)."""
        leaf = self.active
        buf = leaf.doc.buffer
        state = leaf.state_for(leaf.doc)
        state.cursor = buf.cursor
        state.anchor = buf.anchor
        view = self.views.get(leaf.id)
        if view is not None:
            state.scroll_col = view.scroll_col
            state.scroll_row = view.scroll_offset.y

    def apply_doc(self, leaf: Leaf) -> None:
        """Make *leaf*'s document the active one: index, buffer cursor and
        scroll all follow the leaf's stored view state."""
        doc = leaf.doc
        self.active = leaf
        state = leaf.state_for(doc)
        buf = doc.buffer
        buf.cursor = self._clamp(doc, state.cursor)
        state.cursor = buf.cursor
        buf.anchor = (
            self._clamp(doc, state.anchor) if state.anchor is not None else None
        )
        state.anchor = buf.anchor
        try:
            self.app.doc_index = self.app.docs.index(doc)
        except ValueError:
            pass
        view = self.views.get(leaf.id)
        if view is not None:
            view.scroll_col = state.scroll_col
            view.scroll_to(y=state.scroll_row, animate=False)

    def notify_focus(self, leaf_id: int) -> None:
        """EditorView.on_focus hook: switch the active pane."""
        if not self.app.mounted:
            return
        leaf = self.leaf_by_id(leaf_id)
        if leaf is self.active:
            return
        self.capture_active()
        self.apply_doc(leaf)
        self.app.after_pane_focus()

    def show_doc(self, leaf: Leaf, doc: Document) -> None:
        """Bind *doc* into *leaf* (file open / tab cycle), restoring the
        per-(leaf, doc) view state."""
        if leaf.doc is not doc:
            if leaf is self.active:
                self.capture_active()
            leaf.doc = doc
        if leaf is self.active:
            self.apply_doc(leaf)

    def document_closed(self, closed: Document, fallback: Document) -> None:
        """Rebind every leaf showing *closed* to *fallback* (``:bd``)."""
        for leaf in leaves(self.root):
            if leaf.doc is closed:
                leaf.doc = fallback
        if self.active.doc is fallback:
            self.apply_doc(self.active)

    # -------------------------------------------------------- structure ops

    async def split_active(
        self, axis: Axis, doc: Optional[Document] = None
    ) -> Leaf:
        """Split the active leaf; focus moves to the new leaf (vim)."""
        self.capture_active()
        source = self.active
        if doc is None or doc is source.doc:
            new_leaf = self.make_leaf(source.doc, inherit=source)
        else:
            new_leaf = self.make_leaf(doc)
        split = Split(axis, [source, new_leaf], [0.5, 0.5])
        self.root = replace_node(self.root, source, split)
        self.active = new_leaf
        if self.host is not None:
            await self.host.reconcile(new_leaf)
        # Same document: cloned cursor state keeps the new pane at the same
        # position; another document: its stored (or fresh) state is applied.
        self.apply_doc(new_leaf)
        if self.host is not None:
            self.app.after_pane_focus()
        return new_leaf

    async def close_active(self) -> bool:
        """Close the active leaf. ``False`` when it is the only one (the
        caller then handles app quit / tab close)."""
        ordered = leaves(self.root)
        if len(ordered) == 1:
            return False
        index = ordered.index(self.active)
        following = (
            ordered[index + 1]
            if index + 1 < len(ordered)
            else ordered[index - 1]
        )
        new_root = remove_node(self.root, self.active)
        # not the last leaf (guarded above), so the tree still exists
        assert new_root is not None
        self.root = new_root
        self.active = following
        if self.host is not None:
            await self.host.reconcile(following)
        self.apply_doc(following)
        self.app.after_pane_focus()
        return True

    async def only_active(self) -> None:
        """Close every other leaf (``:only``); documents stay open."""
        if self.leaf_count == 1:
            return
        keep = self.active
        self.capture_active()
        self.root = keep
        if self.host is not None:
            await self.host.reconcile(keep)
        self.apply_doc(keep)
        self.app.after_pane_focus()

    # ------------------------------------------------------------ movement

    def focus_direction(self, direction: str) -> bool:
        """Focus the geometrically nearest pane in h/j/k/l direction.

        ``False`` when no editor pane lies that way (the caller may focus
        the explorer for ``h``).
        """
        view = self.active_view
        if view is None:
            return False
        ordered = leaves(self.root)
        if len(ordered) == 1:
            return False
        ax_f, ay_f = view.region.center
        ax, ay = int(ax_f), int(ay_f)
        best: Optional[Leaf] = None
        best_score: Optional[tuple[int, int]] = None
        for leaf in ordered:
            if leaf is self.active:
                continue
            other = self.views.get(leaf.id)
            if other is None or not other.display:
                continue
            cx_f, cy_f = other.region.center
            cx, cy = int(cx_f), int(cy_f)
            along: int
            cross: int
            if direction == "h" and cx < ax:
                along, cross = ax - cx, abs(cy - ay)
            elif direction == "l" and cx > ax:
                along, cross = cx - ax, abs(cy - ay)
            elif direction == "j" and cy > ay:
                along, cross = cy - ay, abs(cx - ax)
            elif direction == "k" and cy < ay:
                along, cross = ay - cy, abs(cx - ax)
            else:
                continue
            score = (cross, along)
            if best_score is None or score < best_score:
                best_score, best = score, leaf
        if best is None:
            return False
        target = self.views.get(best.id)
        if target is None:
            return False
        target.focus()
        return True

    def cycle_focus(self, *, explorer_focused: bool) -> None:
        """``ctrl+w ctrl+w``: explorer -> active editor -> next pane -> ... ->
        explorer round-robin."""
        if explorer_focused:
            view = self.active_view
            if view is not None:
                view.focus()
            return
        ordered = leaves(self.root)
        index = ordered.index(self.active)
        if index + 1 < len(ordered):
            next_view = self.views.get(ordered[index + 1].id)
            if next_view is not None:
                next_view.focus()
                return
        self.app.focus_explorer()

    # -------------------------------------------------------------- sizing

    def resize(self, axis: Axis, sign: int) -> bool:
        """Grow (sign=1) / shrink (sign=-1) the active pane along *axis*."""
        found = find_axis_split(self.root, self.active, axis)
        if found is None:
            return False
        split, index = found
        neighbor = index + 1 if index + 1 < len(split.children) else index - 1
        if sign > 0:
            room = split.sizes[neighbor] - MIN_FRACTION
            if room <= 0:
                return False
            step = min(RESIZE_STEP, room)
            split.sizes[index] += step
            split.sizes[neighbor] -= step
        else:
            room = split.sizes[index] - MIN_FRACTION
            if room <= 0:
                return False
            step = min(RESIZE_STEP, room)
            split.sizes[index] -= step
            split.sizes[neighbor] += step
        if self.host is not None:
            self.host.apply_sizes()
        return True

    def equalize(self) -> None:
        """Reset every split to equal fractions (``ctrl+w =``)."""
        def _even(node: Node) -> None:
            if isinstance(node, Split):
                node.sizes = [1.0 / len(node.children)] * len(node.children)
                for child in node.children:
                    _even(child)

        _even(self.root)
        if self.host is not None:
            self.host.apply_sizes()


# ============================================================== Textual host


class PaneHost(Widget):
    """Renders the :class:`PaneManager` tree and reconciles on changes."""

    DEFAULT_CSS = """
    PaneHost {
        width: 100%;
        height: 1fr;
    }
    .pane-box {
        width: 100%;
        height: 100%;
    }
    PaneHost EditorView {
        width: 100%;
        height: 100%;
    }
    /* divider between two panes of a split; only the first side gets it */
    .pane-sep-h {
        border-bottom: heavy $primary 60%;
    }
    .pane-sep-v {
        border-right: heavy $primary 60%;
    }
    """

    def __init__(self, manager: PaneManager) -> None:
        super().__init__()
        self.manager = manager
        manager.attach(self)

    def on_mount(self) -> None:
        # compose() built the tree before mount; fractional sizes only
        # resolve correctly against a mounted parent, so re-apply them.
        self.apply_sizes()

    def compose(self):
        yield self._build(self.manager.root)

    def _build(self, node: Node) -> Widget:
        if isinstance(node, Leaf):
            view = EditorView(self.manager.app, leaf_id=node.id)
            self.manager.views[node.id] = view
            return view
        box_cls = Vertical if node.axis == "horizontal" else Horizontal
        children = [self._build(child) for child in node.children]
        sep = "pane-sep-h" if node.axis == "horizontal" else "pane-sep-v"
        for child in children[:-1]:
            child.add_class(sep)
        box = box_cls(*children, classes="pane-box")
        self._style_split(box, node)
        return box

    def _style_split(self, box: Widget, split: Split) -> None:
        """Apply fractional sizes to the immediate children of a split."""
        horizontal_box = split.axis == "horizontal"
        children = list(box.children)
        for child, fraction in zip(children, split.sizes):
            pct = f"{fraction * 100:.3f}%"
            if horizontal_box:
                child.styles.height = pct
            else:
                child.styles.width = pct

    async def reconcile(self, focus: Leaf) -> None:
        """Rebuild the whole widget subtree from the model tree.

        # TODO(perf): full rebuild destroys and recreates every widget on
        # structural changes (split/close/only).  A diff-based approach that
        # reuses unchanged :class:`EditorView` instances would avoid the
        # layout thrash for large pane trees.  Currently acceptable because
        # split operations are infrequent and EditorView construction is
        # cheap -- revisit once pane counts exceed ~8.
        """
        self.manager.views.clear()
        for child in list(self.children):
            await child.remove()
        await self.mount(self._build(self.manager.root))
        # Fractional sizes assigned before mount resolve against an unknown
        # parent and come out wrong (panes end up off-screen), so re-apply
        # them now that the widgets are mounted.
        self.apply_sizes()
        # restore each pane's saved scroll before handing focus over
        for leaf in leaves(self.manager.root):
            view = self.manager.views.get(leaf.id)
            state = leaf.states.get(leaf.doc.uid)
            if view is not None and state is not None:
                view.scroll_col = state.scroll_col
                view.scroll_to(y=state.scroll_row, animate=False)
        target = self.manager.views.get(focus.id)
        if target is not None:
            target.focus()

    def apply_sizes(self) -> None:
        """Re-apply fractional sizes without a structural rebuild."""
        root_child = next(iter(self.children), None)
        if root_child is not None:
            self._apply_sizes(self.manager.root, root_child)

    def _apply_sizes(self, node: Node, widget: Widget) -> None:
        if isinstance(node, Leaf):
            return
        for child, child_widget, fraction in zip(
            node.children, widget.children, node.sizes
        ):
            pct = f"{fraction * 100:.3f}%"
            if node.axis == "horizontal":
                child_widget.styles.height = pct
            else:
                child_widget.styles.width = pct
            self._apply_sizes(child, child_widget)
