"""Unit tests for the split-pane tree model (no Textual runtime).

PaneManager is driven with a real :class:`EditorSession` plus host-less
callbacks: structure ops run host-less (``host is None``), exactly like the
model would behave before the first widget mounts, so every tree/state rule
is testable without a screen.

One exception: the S17 scroll-restore regression test drives a real app
under pilot, because the restore paths it guards live in the widget layer
(``PaneHost.reconcile`` for inactive leaves, ``apply_doc`` for the focus
leaf).
"""

from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional

import pytest

# The S17 regression test launches the real app; make sure the bundled
# Python LSP extension never probes PATH or spawns a server in tests.
os.environ["YATE_PYTHON_LSP"] = "off"

from yate.app import YateApp
from yate.config import YateConfig
from yate.editor_core.buffer import TextBuffer
from yate.editor_core.document import Document
from yate.editor_view.editor import EditorView
from yate.editor_view.panes import PaneManager
from yate.session import (
    MIN_FRACTION,
    EditorSession,
    Leaf,
    Split,
    find_axis_split,
    leaves,
    remove_node,
)


def make_doc(text: str = "") -> Document:
    return Document(None, TextBuffer(text))


def _manager(session: EditorSession, doc: Document) -> PaneManager:
    """Host-less manager: panes never reach the (absent) widget host."""
    return PaneManager(
        session,
        doc,
        is_mounted=lambda: False,
        after_pane_focus=lambda: None,
        focus_explorer=lambda: None,
    )


def _env() -> tuple[EditorSession, PaneManager, Document, Document]:
    """Fresh host-less manager over two documents."""
    doc1 = make_doc("one\ntwo\nthree\n")
    doc2 = make_doc("alpha\nbeta\n")
    session = EditorSession(YateConfig())
    session.docs.extend([doc1, doc2])
    session.index = 0
    return session, _manager(session, doc1), doc1, doc2


# --- initial state ----------------------------------------------------------


def test_initial_state() -> None:
    async def _scenario() -> None:
        _session, mgr, doc1, _doc2 = _env()
        root = mgr.root
        assert isinstance(root, Leaf)
        assert root.doc is doc1
        assert mgr.leaf_count == 1
        assert mgr.active is root

    asyncio.run(_scenario())


# --- splitting --------------------------------------------------------------


def test_split_clones_view_state_and_cursor() -> None:
    async def _scenario() -> None:
        _session, mgr, doc1, _doc2 = _env()
        # move the (single) active pane's cursor first
        doc1.buffer.set_cursor((2, 1))
        await mgr.split_active("horizontal")

        root = mgr.root
        assert isinstance(root, Split)
        assert root.axis == "horizontal"
        assert len(leaves(root)) == 2
        assert root.sizes == [0.5, 0.5]

        source, new = root.children
        assert isinstance(source, Leaf) and isinstance(new, Leaf)
        assert mgr.active is new
        assert source.doc is doc1
        assert new.doc is doc1
        # vim :split opens at the same cursor position
        assert new.state_for(doc1).cursor == (2, 1)
        # editing the new pane's state must not touch the source pane
        new.state_for(doc1).cursor = (0, 0)
        assert source.state_for(doc1).cursor == (2, 1)

    asyncio.run(_scenario())


def test_split_with_other_document() -> None:
    async def _scenario() -> None:
        session, mgr, doc1, doc2 = _env()
        await mgr.split_active("vertical", doc2)
        root = mgr.root
        assert isinstance(root, Split)
        source, new = root.children
        assert isinstance(source, Leaf) and isinstance(new, Leaf)
        assert root.axis == "vertical"
        assert source.doc is doc1
        assert new.doc is doc2
        assert mgr.active is new
        assert session.index == 1

    asyncio.run(_scenario())


# --- focus / cursor restoration --------------------------------------------


def test_focus_switch_restores_independent_cursors() -> None:
    async def _scenario() -> None:
        session, mgr, doc1, _doc2 = _env()
        doc1.buffer.set_cursor((2, 0))
        await mgr.split_active("horizontal")
        root = mgr.root
        assert isinstance(root, Split)
        source, new = root.children
        assert isinstance(source, Leaf) and isinstance(new, Leaf)

        # the active (new) pane diverges to row 1
        doc1.buffer.set_cursor((1, 0))
        mgr.capture_active()
        # switching to the source restores its cursor (row 2)
        mgr.apply_doc(source)
        assert doc1.buffer.cursor == (2, 0)
        # switching back replays the new pane's cursor (row 1)
        mgr.apply_doc(new)
        assert doc1.buffer.cursor == (1, 0)
        assert session.index == 0

    asyncio.run(_scenario())


def test_show_doc_remembers_per_leaf_state() -> None:
    async def _scenario() -> None:
        session, mgr, doc1, doc2 = _env()
        await mgr.split_active("horizontal")
        root = mgr.root
        assert isinstance(root, Split)
        first, second = root.children
        assert isinstance(first, Leaf) and isinstance(second, Leaf)

        # "focus" pane 1 on doc2, move to row 1 there
        mgr.show_doc(first, doc2)
        mgr.apply_doc(first)
        assert session.index == 1
        doc2.buffer.set_cursor((1, 0))
        mgr.capture_active()
        # "focus" pane 2 on doc1 (its state is the initial row 0)
        mgr.show_doc(second, doc1)
        mgr.apply_doc(second)
        assert session.index == 0
        assert doc1.buffer.cursor == (0, 0)
        # back to pane 1: doc2 and its own cursor are restored
        mgr.apply_doc(first)
        assert doc2.buffer.cursor == (1, 0)
        assert session.index == 1

    asyncio.run(_scenario())


# --- closing ----------------------------------------------------------------


def test_close_active_collapses_split() -> None:
    async def _scenario() -> None:
        _session, mgr, _doc1, _doc2 = _env()
        await mgr.split_active("horizontal")
        closed = mgr.active
        assert await mgr.close_active()

        root = mgr.root
        assert isinstance(root, Leaf)
        assert root is not closed
        assert mgr.leaf_count == 1

    asyncio.run(_scenario())


def test_close_hoists_sibling_split() -> None:
    async def _scenario() -> None:
        _session, mgr, _doc1, _doc2 = _env()
        # outer horizontal split: [a | b]
        await mgr.split_active("horizontal")
        root = mgr.root
        assert isinstance(root, Split)
        a, b = root.children
        assert isinstance(a, Leaf) and isinstance(b, Leaf)
        # split the top leaf vertically: [ [a | c] | b ]
        mgr.active = a
        mgr.apply_doc(a)
        await mgr.split_active("vertical")
        root = mgr.root
        assert isinstance(root, Split)
        inner, still_b = root.children
        assert isinstance(inner, Split) and isinstance(still_b, Leaf)
        assert inner.axis == "vertical"
        a2, c = inner.children
        assert isinstance(a2, Leaf) and isinstance(c, Leaf)

        # close c -> the vertical split collapses, its survivor hoisted
        mgr.active = c
        assert await mgr.close_active()
        root = mgr.root
        assert isinstance(root, Split)
        assert root.axis == "horizontal"
        survivor, b3 = root.children
        assert survivor is a2
        assert b3 is still_b

        # close the last sibling -> single leaf tree
        assert isinstance(b3, Leaf)
        mgr.active = b3
        assert await mgr.close_active()
        assert mgr.root is a2
        assert mgr.leaf_count == 1

        # the very last leaf cannot be closed
        assert not await mgr.close_active()

    asyncio.run(_scenario())


def test_only_keeps_active_and_its_state() -> None:
    async def _scenario() -> None:
        _session, mgr, _doc1, doc2 = _env()
        await mgr.split_active("horizontal", doc2)
        active = mgr.active
        doc2.buffer.set_cursor((1, 0))
        mgr.capture_active()
        await mgr.only_active()

        assert mgr.root is active
        assert mgr.leaf_count == 1
        assert active.state_for(doc2).cursor == (1, 0)

    asyncio.run(_scenario())


def test_document_closed_rebinds_every_leaf() -> None:
    async def _scenario() -> None:
        _session, mgr, doc1, doc2 = _env()
        await mgr.split_active("horizontal", doc2)
        mgr.document_closed(doc2, doc1)
        for leaf in leaves(mgr.root):
            assert leaf.doc is doc1

    asyncio.run(_scenario())


# --- resizing ---------------------------------------------------------------


def test_resize_conserves_fractions_and_clamps() -> None:
    async def _scenario() -> None:
        _session, mgr, _doc1, _doc2 = _env()
        await mgr.split_active("horizontal")
        root = mgr.root
        assert isinstance(root, Split)
        # the freshly created pane (child 1) is active: grow it
        for _ in range(20):
            if not mgr.resize("horizontal", 1):
                break
        assert sum(root.sizes) == pytest.approx(1.0)
        assert root.sizes[0] >= MIN_FRACTION - 1e-9
        assert root.sizes[1] > 0.5
        # already at the ceiling
        assert not mgr.resize("horizontal", 1)

        mgr.equalize()
        assert root.sizes == [0.5, 0.5]

        # shrinking the active pane really transfers space to the neighbour
        assert mgr.resize("horizontal", -1)
        assert root.sizes[1] < 0.5
        assert root.sizes[0] > 0.5
        for _ in range(20):
            if not mgr.resize("horizontal", -1):
                break
        assert root.sizes[1] >= MIN_FRACTION - 1e-9
        assert not mgr.resize("horizontal", -1)

    asyncio.run(_scenario())


def test_resize_uses_enclosing_axis_split() -> None:
    async def _scenario() -> None:
        _session, mgr, _doc1, doc2 = _env()
        await mgr.split_active("horizontal")
        root = mgr.root
        assert isinstance(root, Split)
        top, _bottom = root.children
        assert isinstance(top, Leaf)
        mgr.active = top
        await mgr.split_active("vertical", doc2)
        # the active leaf sits in a vertical split inside the horizontal one:
        # vertical resize targets the inner split ...
        found_v = find_axis_split(mgr.root, mgr.active, "vertical")
        assert found_v is not None
        split_v, slot = found_v
        assert split_v.axis == "vertical"
        assert slot == 1  # the doc2 leaf is the right child
        # ... while horizontal resize walks out to the outer split
        found_h = find_axis_split(mgr.root, mgr.active, "horizontal")
        assert found_h is not None
        assert found_h[0].axis == "horizontal"
        assert found_h[1] == 0  # whole inner split is child 0

    asyncio.run(_scenario())


def test_close_renormalizes_sizes() -> None:
    async def _scenario() -> None:
        session, mgr, doc1, doc2 = _env()
        await mgr.split_active("vertical")
        root = mgr.root
        assert isinstance(root, Split)
        root.sizes[:] = [0.7, 0.3]
        await mgr.close_active()
        # collapsed to a leaf; nothing to normalize -- check a 3-pane case:
        doc3 = make_doc("gamma\n")
        session.docs.append(doc3)
        mgr = _manager(session, doc1)
        await mgr.split_active("vertical", doc2)
        top = mgr.root
        assert isinstance(top, Split)
        nested = top.children[0]
        assert isinstance(nested, Leaf)
        mgr.active = nested
        await mgr.split_active("vertical", doc3)
        # closing one pane inside a split keeps normalized sibling fractions
        await mgr.close_active()
        outer = mgr.root
        assert isinstance(outer, Split)
        assert sum(outer.sizes) == pytest.approx(1.0)

    asyncio.run(_scenario())


# --- tree ops: remove_node (M2 regression) ----------------------------------


def test_remove_node_keeps_each_survivor_fraction() -> None:
    """Dropping a leaf keeps every *other* pane's own fraction.

    ``children`` / ``sizes`` are parallel lists, so removing the first pane of
    ``[0.5, 0.25, 0.25]`` must leave the remaining two sharing ``[0.5, 0.5]``
    (the old first-N slice wrongly produced ``[0.6667, 0.3333]``).
    """
    doc1 = make_doc("one\n")
    doc2 = make_doc("two\n")
    doc3 = make_doc("three\n")

    def _tree() -> tuple[Split, Leaf, Leaf, Leaf]:
        a = Leaf(1, doc1)
        b = Leaf(2, doc2)
        c = Leaf(3, doc3)
        return Split("vertical", [a, b, c], [0.5, 0.25, 0.25]), a, b, c

    # close the first pane -> the survivors keep their own equal shares
    root, a, b, c = _tree()
    after = remove_node(root, a)
    assert isinstance(after, Split)
    assert after.sizes == pytest.approx([0.5, 0.5])
    assert after.children[0] is b
    assert after.children[1] is c
    assert leaves(after)[0] is b
    assert leaves(after)[1] is c

    # close the middle pane -> 0.5 and 0.25 renormalize to 2/3 and 1/3
    # (assert the exact fractions: a padded literal would need a loose
    # tolerance and could hide a real off-by-a-slot regression)
    root, a, b, c = _tree()
    after = remove_node(root, b)
    assert isinstance(after, Split)
    assert after.sizes == pytest.approx([2 / 3, 1 / 3])
    assert after.children[0] is a
    assert after.children[1] is c
    assert leaves(after)[0] is a
    assert leaves(after)[1] is c


def test_remove_node_renormalizes_nested_survivors() -> None:
    """A nested split renormalizes its own survivors, not a prefix slice.

    Removing ``a`` from the inner ``[0.2, 0.3, 0.5]`` vertical split keeps the
    ``b`` / ``c`` pair and renormalizes *their* sizes to ``[0.375, 0.625]``
    (the old code sliced ``[0.2, 0.3]`` and produced ``[0.4, 0.6]``), while the
    enclosing horizontal split keeps its own slot fractions and ordering.
    """
    a = Leaf(1, make_doc("a\n"))
    b = Leaf(2, make_doc("b\n"))
    c = Leaf(3, make_doc("c\n"))
    sibling = Leaf(4, make_doc("d\n"))
    inner = Split("vertical", [a, b, c], [0.2, 0.3, 0.5])
    outer = Split("horizontal", [inner, sibling], [0.7, 0.3])

    after = remove_node(outer, a)
    assert isinstance(after, Split) and after is outer
    nested = after.children[0]
    assert isinstance(nested, Split) and nested is inner
    assert nested.children[0] is b
    assert nested.children[1] is c
    assert nested.sizes == pytest.approx([0.375, 0.625])
    # the outer slots (their order and fractions) are untouched
    assert after.children[1] is sibling
    assert after.sizes == pytest.approx([0.7, 0.3])


# --- S17 regression: scroll survives split/close -----------------------------
# Widget-level test (see the module docstring): the restore paths it guards
# live in PaneHost.reconcile (inactive leaves) and PaneManager.apply_doc
# (focus leaf), so a real app under pilot is required.


async def _wait_until(
    pilot: Any, predicate: Callable[[], bool], timeout: float = 5.0
) -> bool:
    """Poll *predicate* between pilot pauses; False on timeout."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result: Awaitable[None] = pilot.pause(0.05)
        await result
        if predicate():
            return True
    return predicate()


def test_split_close_restores_scroll_for_focus_and_inactive_leaves(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Scroll state survives split/close for every surviving pane.

    Guards the two restore paths behind the SP3 fix: the reconcile loop
    re-applies the saved scroll of *inactive* leaves, and the ``apply_doc``
    follow-up does it for the focus leaf (which the loop skips on purpose).
    A spy on ``EditorView.scroll_to`` pins both calls down; a second restore
    for the focus leaf would mean the loop stopped skipping it.

    The final widget ``scroll_offset`` is deliberately not asserted: every
    reconcile rebuild recreates the views, and Textual silently discards
    scroll requests that run before the first layout pass (the fresh views
    still report ``allow_vertical_scroll == False`` when the deferred
    ``_scroll_to`` finally runs), so rebuilt views always read 0 no matter
    what the restore paths do.  The preserved ``ViewState`` plus the
    observed restore calls are the observable contract here.
    """

    async def _scenario() -> None:
        target = tmp_path / "long.txt"
        target.write_text(
            "\n".join(f"row {i}" for i in range(120)) + "\n",
            encoding="utf-8",
        )
        app = YateApp(target=target)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            panes = app.editor.panes
            assert panes is not None
            buf = app.editor.session.buffer

            # park the cursor a few rows inside the visible window so
            # reveal_cursor never overrides the saved scroll afterwards
            buf.set_cursor((60, 0))
            app.editor.refresh_ui()
            await pilot.pause()
            root = panes.root
            assert isinstance(root, Leaf)
            saved = panes.views[root.id].scroll_offset.y
            assert saved > 0
            buf.set_cursor((saved + 2, 0))
            app.editor.refresh_ui()
            await pilot.pause()
            assert panes.views[root.id].scroll_offset.y == saved

            # split: the first leaf goes inactive with its scroll captured
            app.editor.run_command("split")
            assert await _wait_until(pilot, lambda: panes.leaf_count == 2)
            await pilot.pause()
            root = panes.root
            assert isinstance(root, Split)
            a_leaf = root.children[0]
            assert isinstance(a_leaf, Leaf)
            assert panes.active is not a_leaf
            assert a_leaf.state_for(a_leaf.doc).scroll_row == saved

            # The split's rebuild dropped its mount-time scroll restores (see
            # the docstring), so re-apply the saved scroll to the focused pane
            # now that layout settled -- otherwise the vsplit capture below
            # would overwrite its state with the discarded 0.
            active = panes.active
            assert isinstance(active, Leaf)
            panes.views[active.id].scroll_to(y=saved, animate=False)
            assert await _wait_until(
                pilot, lambda: panes.views[active.id].scroll_offset.y == saved
            )

            # split the active pane again: three leaves, C active
            app.editor.run_command("vsplit")
            assert await _wait_until(pilot, lambda: panes.leaf_count == 3)
            await pilot.pause()
            ordered = leaves(panes.root)
            assert ordered[0] is a_leaf
            b_leaf = ordered[1]
            c_leaf = ordered[2]
            assert panes.active is c_leaf
            assert b_leaf.state_for(b_leaf.doc).scroll_row == saved

            # close the active pane C: B becomes focus (apply_doc restores
            # it), A stays inactive (the reconcile restore loop restores it)
            real_scroll_to = EditorView.scroll_to
            scroll_calls: list[tuple[int, Optional[int]]] = []

            def _spy_scroll_to(
                view: EditorView,
                x: Optional[float] = None,
                y: Optional[float] = None,
                **kwargs: Any,  # forwards Textual's own scroll_to keywords
            ) -> None:
                scroll_calls.append((view.leaf_id, None if y is None else int(y)))
                real_scroll_to(view, x=x, y=y, **kwargs)

            monkeypatch.setattr(EditorView, "scroll_to", _spy_scroll_to)

            app.editor.run_command("close")
            assert await _wait_until(pilot, lambda: panes.leaf_count == 2)
            assert await _wait_until(
                pilot,
                lambda: scroll_calls.count((a_leaf.id, saved)) >= 1
                and scroll_calls.count((b_leaf.id, saved)) >= 1,
            )
            await pilot.pause()

            assert panes.active is b_leaf
            # both surviving leaves keep their saved view state
            assert a_leaf.state_for(a_leaf.doc).scroll_row == saved
            assert b_leaf.state_for(b_leaf.doc).scroll_row == saved
            # inactive leaf A: exactly one restore, from the reconcile loop
            assert scroll_calls.count((a_leaf.id, saved)) == 1
            # focus leaf B: exactly one restore, from the apply_doc follow-up
            # (a second hit would mean the reconcile loop stopped skipping it)
            assert scroll_calls.count((b_leaf.id, saved)) == 1

            # focusing the inactive pane re-applies its saved scroll through
            # the same apply_doc path -- post-layout the widget keeps it
            panes.views[a_leaf.id].focus()
            assert await _wait_until(
                pilot, lambda: panes.views[a_leaf.id].scroll_offset.y == saved
            )
            assert panes.active is a_leaf

    asyncio.run(_scenario())
