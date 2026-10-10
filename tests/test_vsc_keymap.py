"""``VscKeymap`` regression pins: binding-table integrity.

Guards the modeless vscode keymap against the two silent-failure shapes a
binding table can have: a raw key bound twice (the later entry overwrites
the earlier one in ``Keymap._index`` without a word -- issue IKJ2V1) and an
action name the built-in table never registered (the key falls through
with an "unknown action" notice at dispatch time).
"""

from __future__ import annotations

from collections import Counter
from typing import cast

from yate.actions import populate
from yate.editor import Editor
from yate.keymaps.base import parse_key
from yate.keymaps.vsc import SEL, VscKeymap
from yate.registries import ActionRegistry

from conftest import make_action_context


def test_vsc_has_no_duplicate_raw_keys() -> None:
    """Every raw key appears once: ``_index`` must never silently override."""
    vsc = VscKeymap()
    counts = Counter(b.key for b in vsc.bindings)
    dupes = [k for k, c in counts.items() if c > 1]
    assert not dupes, f"duplicate raw keys found: {dupes}"


def test_vsc_bindings_use_registered_actions() -> None:
    """Every vsc action name resolves through the built-in action table.

    ``populate`` only builds lambdas at registration time -- the editor is
    referenced lazily inside them -- so the ``cast(Editor, None)`` stand-in
    is never touched and the check needs no running editor.
    """
    registry = ActionRegistry()
    populate(registry, cast(Editor, None))
    vsc = VscKeymap()
    unknown = [
        b.action
        for b in vsc.bindings
        if isinstance(b.action, str) and b.action not in registry.names()
    ]
    assert unknown == []


def test_ctrl_w_in_vsc_closes_tab() -> None:
    """ctrl+w keeps its vscode meaning in vsc mode: close the current tab."""
    vsc = VscKeymap()
    binding = vsc.lookup("\x17")
    assert binding is not None
    assert binding.action == "close_tab"


def test_alt_c_binding_resolves_add_cursor_below() -> None:
    """<alt-c> is bound to the multi-cursor add-cursor-below action (SEL)."""
    vsc = VscKeymap()
    binding = vsc.lookup(parse_key("<alt-c>"))
    assert binding is not None
    assert binding.action == "add_cursor_below"
    assert binding.category == SEL


def test_handle_unbound_printable_multi_cursor_inserts_at_points() -> None:
    """A printable key inserts at every extra point; single-cursor keeps
    the type_char affordances (bracket auto-completion).

    The multi-cursor half drives the unbound fallback directly against a
    real buffer, so it does not depend on the action table: the extra
    points come from the buffer API itself, not from a registered action.
    """
    ctx = make_action_context("alpha beta\ngamma delta")
    ctx.buffer.set_cursor((0, 2))
    assert ctx.buffer.add_cursor_at((1, 2)) is True

    assert VscKeymap().handle_key(ctx, "X") is True
    assert ctx.buffer.lines[0][:3] == "alX"  # "alXpha beta"
    assert ctx.buffer.lines[1][:3] == "gaX"  # "gaXmma delta"

    # single-cursor contrast: the printable key goes through type_char
    # again, so its bracket auto-completion keeps working
    ctx.buffer.clear_extra_cursors()
    ctx.buffer.set_cursor((0, 0))
    assert VscKeymap().handle_key(ctx, "(") is True
    assert "()" in ctx.buffer.lines[0]
