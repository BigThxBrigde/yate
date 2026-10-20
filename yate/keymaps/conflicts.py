"""Conflict scanning for keymap binding tables (L1, zero UI imports).

Walks one :class:`~yate.keymaps.base.Keymap` binding table and reports the
two shapes of conflict that make a binding unreachable:

``duplicate``
    The same raw key appears more than once in ``bindings`` -- in
    :attr:`Keymap._index` the later entry shadows the earlier one, so the
    earlier binding never dispatches.  Normal registration goes through
    :meth:`Keymap.add_binding`, which replaces in place, so a duplicate
    only survives from a hand-built table or a stale twin.
``reserved``
    The raw key is consumed before the table is consulted (e.g. vim's
    hard-coded branches), so the bound action can never run.  The reserved
    set is injected by the caller instead of imported from a concrete
    keymap: the scan stays reusable and the module never couples to vim.

The report consumer is the ``:check-keys`` command (L3 wiring lands in a
later wave); :func:`format_conflicts` renders plain text with no UI
imports, matching architecture rule R4 (``keymaps/*`` stays UI-free).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Literal

from yate.keymaps.base import KeyBinding, Keymap
from yate.keymaps.keys import key_name


@dataclass(frozen=True)
class KeyConflict:
    """One detected keymap conflict and the bindings that collide."""

    raw: str  # the colliding raw key
    reason: Literal["duplicate", "reserved"]
    bindings: tuple[KeyBinding, ...]  # every table entry involved


def find_key_conflicts(
    keymap: Keymap,
    reserved: frozenset[str] = frozenset(),
) -> list[KeyConflict]:
    """Scan *keymap*'s binding table; sorted by ``key_name(raw)``.

    ``duplicate``: the same raw key appears twice in ``bindings`` -- the
    later entry shadows the earlier one in ``_index``.  ``reserved``: the
    raw key is consumed before the table is consulted (e.g. vim's
    RESERVED_KEYS), so the binding can never dispatch.  Bindings
    registered through ``add_binding`` replace in place and are reported
    only if the table still holds a stale twin.

    A raw key that hits both shapes yields two conflicts, ``duplicate``
    ahead of ``reserved``; across keys the list is ordered by the human
    key label so the report reads like the keyboard.
    """
    counts = Counter(b.key for b in keymap.bindings)
    conflicts: list[KeyConflict] = []
    visited: set[str] = set()
    for binding in keymap.bindings:
        raw = binding.key
        if raw in visited:
            continue
        visited.add(raw)
        entries = tuple(b for b in keymap.bindings if b.key == raw)
        if counts[raw] > 1:
            conflicts.append(KeyConflict(raw, "duplicate", entries))
        if raw in reserved:
            conflicts.append(KeyConflict(raw, "reserved", entries))
    # reason breaks the tie for one raw key: "duplicate" < "reserved".
    conflicts.sort(key=lambda c: (key_name(c.raw), c.reason))
    return conflicts


def format_conflicts(keymap_name: str, conflicts: list[KeyConflict]) -> str:
    """Render the ``:check-keys`` report body (human text, no UI imports).

    With conflicts the text opens with the class counts
    (``keymap: <name> -- N conflict(s) (D duplicate, R reserved)``) and
    follows with one ``<key>  <reason>  action1 -> action2`` line per
    conflict (a direct callable action shows its description); an empty
    scan renders the ``keymap: <name> -- no conflicts`` one-liner.  The
    reserved class gets a closing note: those keys are claimed by the
    built-in dispatch branch first, so their table row never dispatches --
    for the built-in rows that is deliberate (they are help mirrors of the
    branch), while for an extension binding it is a silent dead binding.
    """
    if not conflicts:
        return f"keymap: {keymap_name} -- no conflicts"
    duplicates = sum(1 for c in conflicts if c.reason == "duplicate")
    reserved = len(conflicts) - duplicates
    lines = [
        f"keymap: {keymap_name} -- {len(conflicts)} conflict(s) "
        f"({duplicates} duplicate, {reserved} reserved)"
    ]
    for conflict in conflicts:
        actions = " -> ".join(
            b.action if isinstance(b.action, str) else (b.description or "<callable>")
            for b in conflict.bindings
        )
        lines.append(f"{key_name(conflict.raw)}  {conflict.reason}  {actions}")
    if reserved:
        lines.append(
            f"note: reserved rows sit on keys the built-in {keymap_name} "
            "branch handles first, so the row itself never dispatches."
        )
    return "\n".join(lines)
