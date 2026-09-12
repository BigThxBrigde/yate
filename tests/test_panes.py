"""Unit tests for the split-pane tree model (no Textual runtime).

PaneManager is driven with a tiny fake app: structure ops run host-less
(``host is None``), exactly like the model would behave before the first
widget mounts, so every tree/state rule is testable without a screen.
"""

from __future__ import annotations

import unittest

from yate.editor_core.buffer import TextBuffer
from yate.editor_core.document import Document
from yate.editor_view.panes import (
    MIN_FRACTION,
    Leaf,
    PaneManager,
    Split,
    find_axis_split,
    leaves,
)


class FakeApp:
    """Just enough YateApp surface for the host-less pane manager."""

    def __init__(self, docs: list[Document]) -> None:
        self.docs = docs
        self.doc_index = 0
        self.mounted = False

    # pane manager app hooks ------------------------------------------------

    def after_pane_focus(self) -> None:
        pass

    def focus_explorer(self) -> None:
        pass

    def close_completion(self) -> None:
        pass

    def ui_refresh(self) -> None:
        pass


def make_doc(text: str = "") -> Document:
    return Document(None, TextBuffer(text))


class SplitTreeModelTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.doc1 = make_doc("one\ntwo\nthree\n")
        self.doc2 = make_doc("alpha\nbeta\n")
        self.app = FakeApp([self.doc1, self.doc2])
        self.app.doc_index = 0
        self.mgr = PaneManager(self.app, self.doc1)  # type: ignore[arg-type]

    async def test_initial_state(self) -> None:
        root = self.mgr.root
        assert isinstance(root, Leaf)
        self.assertIs(root.doc, self.doc1)
        self.assertEqual(self.mgr.leaf_count, 1)
        self.assertIs(self.mgr.active, root)

    async def test_split_clones_view_state_and_cursor(self) -> None:
        # move the (single) active pane's cursor first
        self.doc1.buffer.set_cursor((2, 1))
        await self.mgr.split_active("horizontal")

        root = self.mgr.root
        self.assertIsInstance(root, Split)
        assert isinstance(root, Split)
        self.assertEqual(root.axis, "horizontal")
        self.assertEqual(len(leaves(root)), 2)
        self.assertEqual(root.sizes, [0.5, 0.5])

        source, new = root.children
        assert isinstance(source, Leaf) and isinstance(new, Leaf)
        self.assertIs(self.mgr.active, new)
        self.assertIs(source.doc, self.doc1)
        self.assertIs(new.doc, self.doc1)
        # vim :split opens at the same cursor position
        self.assertEqual(new.state_for(self.doc1).cursor, (2, 1))
        # editing the new pane's state must not touch the source pane
        new.state_for(self.doc1).cursor = (0, 0)
        self.assertEqual(source.state_for(self.doc1).cursor, (2, 1))

    async def test_focus_switch_restores_independent_cursors(self) -> None:
        self.doc1.buffer.set_cursor((2, 0))
        await self.mgr.split_active("horizontal")
        root = self.mgr.root
        assert isinstance(root, Split)
        source, new = root.children
        assert isinstance(source, Leaf) and isinstance(new, Leaf)

        # the active (new) pane diverges to row 1
        self.doc1.buffer.set_cursor((1, 0))
        self.mgr.capture_active()
        # switching to the source restores its cursor (row 2)
        self.mgr.apply_doc(source)
        self.assertEqual(self.doc1.buffer.cursor, (2, 0))
        # switching back replays the new pane's cursor (row 1)
        self.mgr.apply_doc(new)
        self.assertEqual(self.doc1.buffer.cursor, (1, 0))
        self.assertEqual(self.app.doc_index, 0)

    async def test_split_with_other_document(self) -> None:
        await self.mgr.split_active("vertical", self.doc2)
        root = self.mgr.root
        assert isinstance(root, Split)
        source, new = root.children
        assert isinstance(source, Leaf) and isinstance(new, Leaf)
        self.assertEqual(root.axis, "vertical")
        self.assertIs(source.doc, self.doc1)
        self.assertIs(new.doc, self.doc2)
        self.assertIs(self.mgr.active, new)
        self.assertEqual(self.app.doc_index, 1)

    async def test_close_active_collapses_split(self) -> None:
        await self.mgr.split_active("horizontal")
        closed = self.mgr.active
        self.assertTrue(await self.mgr.close_active())

        root = self.mgr.root
        self.assertIsInstance(root, Leaf)
        self.assertIsNot(root, closed)
        self.assertEqual(self.mgr.leaf_count, 1)

    async def test_close_hoists_sibling_split(self) -> None:
        # outer horizontal split: [a | b]
        await self.mgr.split_active("horizontal")
        root = self.mgr.root
        assert isinstance(root, Split)
        a, b = root.children
        assert isinstance(a, Leaf) and isinstance(b, Leaf)
        # split the top leaf vertically: [ [a | c] | b ]
        self.mgr.active = a
        self.mgr.apply_doc(a)
        await self.mgr.split_active("vertical")
        root = self.mgr.root
        assert isinstance(root, Split)
        inner, still_b = root.children
        assert isinstance(inner, Split) and isinstance(still_b, Leaf)
        self.assertEqual(inner.axis, "vertical")
        a2, c = inner.children
        assert isinstance(a2, Leaf) and isinstance(c, Leaf)

        # close c -> the vertical split collapses, its survivor hoisted
        self.mgr.active = c
        self.assertTrue(await self.mgr.close_active())
        root = self.mgr.root
        assert isinstance(root, Split)
        self.assertEqual(root.axis, "horizontal")
        survivor, b3 = root.children
        self.assertIs(survivor, a2)
        self.assertIs(b3, still_b)

        # close the last sibling -> single leaf tree
        assert isinstance(b3, Leaf)
        self.mgr.active = b3
        self.assertTrue(await self.mgr.close_active())
        self.assertIs(self.mgr.root, a2)
        self.assertEqual(self.mgr.leaf_count, 1)

        # the very last leaf cannot be closed
        self.assertFalse(await self.mgr.close_active())

    async def test_only_keeps_active_and_its_state(self) -> None:
        await self.mgr.split_active("horizontal", self.doc2)
        active = self.mgr.active
        self.doc2.buffer.set_cursor((1, 0))
        self.mgr.capture_active()
        await self.mgr.only_active()

        self.assertIs(self.mgr.root, active)
        self.assertEqual(self.mgr.leaf_count, 1)
        self.assertEqual(active.state_for(self.doc2).cursor, (1, 0))

    async def test_show_doc_remembers_per_leaf_state(self) -> None:
        await self.mgr.split_active("horizontal")
        root = self.mgr.root
        assert isinstance(root, Split)
        first, second = root.children
        assert isinstance(first, Leaf) and isinstance(second, Leaf)

        # "focus" pane 1 on doc2, move to row 1 there
        self.mgr.show_doc(first, self.doc2)
        self.mgr.apply_doc(first)
        self.assertEqual(self.app.doc_index, 1)
        self.doc2.buffer.set_cursor((1, 0))
        self.mgr.capture_active()
        # "focus" pane 2 on doc1 (its state is the initial row 0)
        self.mgr.show_doc(second, self.doc1)
        self.mgr.apply_doc(second)
        self.assertEqual(self.app.doc_index, 0)
        self.assertEqual(self.doc1.buffer.cursor, (0, 0))
        # back to pane 1: doc2 and its own cursor are restored
        self.mgr.apply_doc(first)
        self.assertEqual(self.doc2.buffer.cursor, (1, 0))
        self.assertEqual(self.app.doc_index, 1)

    async def test_document_closed_rebinds_every_leaf(self) -> None:
        await self.mgr.split_active("horizontal", self.doc2)
        self.mgr.document_closed(self.doc2, self.doc1)
        for leaf in leaves(self.mgr.root):
            self.assertIs(leaf.doc, self.doc1)

    async def test_resize_conserves_fractions_and_clamps(self) -> None:
        await self.mgr.split_active("horizontal")
        root = self.mgr.root
        assert isinstance(root, Split)
        # the freshly created pane (child 1) is active: grow it
        for _ in range(20):
            if not self.mgr.resize("horizontal", 1):
                break
        self.assertAlmostEqual(sum(root.sizes), 1.0)
        self.assertGreaterEqual(root.sizes[0], MIN_FRACTION - 1e-9)
        self.assertGreater(root.sizes[1], 0.5)
        # already at the ceiling
        self.assertFalse(self.mgr.resize("horizontal", 1))

        self.mgr.equalize()
        self.assertEqual(root.sizes, [0.5, 0.5])

        # shrinking the active pane really transfers space to the neighbour
        self.assertTrue(self.mgr.resize("horizontal", -1))
        self.assertLess(root.sizes[1], 0.5)
        self.assertGreater(root.sizes[0], 0.5)
        for _ in range(20):
            if not self.mgr.resize("horizontal", -1):
                break
        self.assertGreaterEqual(root.sizes[1], MIN_FRACTION - 1e-9)
        self.assertFalse(self.mgr.resize("horizontal", -1))

    async def test_resize_uses_enclosing_axis_split(self) -> None:
        await self.mgr.split_active("horizontal")
        root = self.mgr.root
        assert isinstance(root, Split)
        top, _bottom = root.children
        assert isinstance(top, Leaf)
        self.mgr.active = top
        await self.mgr.split_active("vertical", self.doc2)
        # the active leaf sits in a vertical split inside the horizontal one:
        # vertical resize targets the inner split ...
        found_v = find_axis_split(self.mgr.root, self.mgr.active, "vertical")
        self.assertIsNotNone(found_v)
        assert found_v is not None
        split_v, slot = found_v
        self.assertEqual(split_v.axis, "vertical")
        self.assertEqual(slot, 1)  # the doc2 leaf is the right child
        # ... while horizontal resize walks out to the outer split
        found_h = find_axis_split(self.mgr.root, self.mgr.active, "horizontal")
        self.assertIsNotNone(found_h)
        assert found_h is not None
        self.assertEqual(found_h[0].axis, "horizontal")
        self.assertEqual(found_h[1], 0)  # whole inner split is child 0

    async def test_close_renormalizes_sizes(self) -> None:
        await self.mgr.split_active("vertical")
        root = self.mgr.root
        assert isinstance(root, Split)
        root.sizes[:] = [0.7, 0.3]
        await self.mgr.close_active()
        # collapsed to a leaf; nothing to normalize -- check a 3-pane case:
        doc3 = make_doc("gamma\n")
        self.app.docs.append(doc3)
        mgr = PaneManager(self.app, self.doc1)  # type: ignore[arg-type]
        await mgr.split_active("vertical", self.doc2)
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
        self.assertAlmostEqual(sum(outer.sizes), 1.0)


if __name__ == "__main__":
    unittest.main()
