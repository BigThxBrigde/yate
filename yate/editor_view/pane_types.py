"""Pure pane data model -- zero imports from editor or panes.

Contains the tree node types (:class:`Leaf`, :class:`Split`, :class:`Node`),
per-document :class:`ViewState`, and the stateless tree utility functions
(:func:`leaves`, :func:`find_leaf`, :func:`replace_node`, ...).

This module exists solely to break the type-level cycle between
:mod:`yate.editor_view.editor` and :mod:`yate.editor_view.panes`.  Both
modules import from here; neither needs to import from the other for type
annotations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional, Union

from yate.editor_core.buffer import Pos
from yate.editor_core.document import Document

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
    #: View states keyed by ``id(document)`` so a leaf remembers the cursor
    #: position of every document it has shown.
    states: dict[int, ViewState] = field(
        default_factory=lambda: dict[int, ViewState]()
    )

    def state_for(self, doc: Document) -> ViewState:
        state = self.states.get(id(doc))
        if state is None:
            state = ViewState(
                cursor=doc.buffer.cursor, anchor=doc.buffer.anchor
            )
            self.states[id(doc)] = state
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
    new_children: list[Node] = []
    for child in node.children:
        result = remove_node(child, target)
        if result is None:
            # the target leaf lived directly in this split: drop it
            continue
        new_children.append(result)
    if len(new_children) == 1:
        return new_children[0]
    node.children = new_children
    node.sizes = _normalized(node.sizes[: len(new_children)])
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
