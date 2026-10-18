"""Conflict scans: duplicate twins, reserved keys, report rendering.

Pure-logic checks for :mod:`yate.keymaps.conflicts` -- no Textual, no
editor, and the reserved sets are built from literals so this file stays
independent of the concrete keymaps (it must stay green while sibling
waves touch ``vim.py``).
"""

from __future__ import annotations

from typing import override

from yate.keymaps.base import KeyBinding, Keymap
from yate.keymaps.conflicts import find_key_conflicts, format_conflicts
from yate.keymaps.keys import key_name
from yate.keymaps.vsc import VscKeymap


class _TwinKeymap(Keymap):
    """Hand-built table: two rows for raw ``x`` plus one for raw ``1``."""

    name = "twin"
    label = "Twin"

    @override
    def build_bindings(self) -> list[KeyBinding]:
        """A stale twin on ``x`` and a reserved-candidate digit binding."""
        return [
            KeyBinding("x", "a1", "first twin", "general"),
            KeyBinding("x", "a2", "second twin", "general"),
            KeyBinding("1", "x", "digit one", "general"),
        ]


class _LabelKeymap(Keymap):
    """Table whose rows sit in reverse label order (``z`` before ESC)."""

    name = "labels"
    label = "Labels"

    @override
    def build_bindings(self) -> list[KeyBinding]:
        """Two reserved candidates: plain ``z`` first, raw ESC second."""
        return [
            KeyBinding("z", "to_z", "plain z", "general"),
            KeyBinding("\x1b", "to_esc", "escape", "general"),
        ]


def test_duplicate_raw_key_is_reported() -> None:
    """The twin ``x`` rows surface as exactly one duplicate conflict."""
    conflicts = find_key_conflicts(_TwinKeymap())
    assert len(conflicts) == 1
    conflict = conflicts[0]
    assert conflict.raw == "x"
    assert conflict.reason == "duplicate"
    assert [b.action for b in conflict.bindings] == ["a1", "a2"]


def test_reserved_key_binding_is_reported() -> None:
    """A binding on a reserved raw key can never dispatch, so flag it."""
    km = _TwinKeymap()
    conflicts = find_key_conflicts(km, reserved=frozenset({"1"}))
    reserved_hits = [c for c in conflicts if c.reason == "reserved"]
    assert len(reserved_hits) == 1
    conflict = reserved_hits[0]
    assert conflict.raw == "1"
    entry = next(b for b in km.bindings if b.key == "1")
    assert entry in conflict.bindings


def test_clean_table_reports_nothing() -> None:
    """The live VscKeymap table scans clean: no false positives."""
    assert find_key_conflicts(VscKeymap()) == []


def test_conflicts_sorted_by_key_label() -> None:
    """Label order drives the report: ``<esc>`` ahead of the plain ``z``."""
    conflicts = find_key_conflicts(
        _LabelKeymap(), reserved=frozenset({"\x1b", "z"})
    )
    assert len(conflicts) == 2
    labels = [key_name(c.raw) for c in conflicts]
    assert labels[0] == "<esc>"
    assert labels[0] < "z"


def test_format_conflicts_lists_actions() -> None:
    """The report body names the keymap and every colliding action."""
    conflicts = find_key_conflicts(_TwinKeymap())
    text = format_conflicts("vim", conflicts)
    assert "keymap: vim" in text
    # <key>  <reason>  action1 -> action2, per the format spec.
    assert "x  duplicate  a1 -> a2" in text
    assert "no conflicts" in format_conflicts("vim", [])
