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
from yate.keymaps.base import ActionContext
from yate.keymaps.vsc import VscKeymap
from yate.registries import ActionRegistry

from conftest import make_action_context, make_key_ui


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


# --- block (column) selection -------------------------------------------------


def test_vsc_binds_alt_shift_arrows_to_block_select_actions() -> None:
    """Alt+Shift+arrows resolve to the four column-selection actions."""
    vsc = VscKeymap()
    expected = {
        "\x1b[1;4A": "select_block_up",
        "\x1b[1;4B": "select_block_down",
        "\x1b[1;4C": "select_block_right",
        "\x1b[1;4D": "select_block_left",
    }
    for raw, action in expected.items():
        binding = vsc.lookup(raw)
        assert binding is not None, raw
        assert binding.action == action, raw


def test_vsc_ctrl_v_still_binds_paste() -> None:
    """ctrl+v keeps its paste binding (no vim VISUAL_BLOCK cross-talk)."""
    vsc = VscKeymap()
    binding = vsc.lookup("\x16")
    assert binding is not None
    assert binding.action == "paste"


def test_vsc_esc_clears_block_flag() -> None:
    """<esc> drops the block flag along with the anchor (block hygiene)."""
    registry = ActionRegistry()
    populate(registry, cast(Editor, None))
    holder: list[ActionContext] = []
    ctx = make_action_context(
        "abcd\nefgh\nijkl",
        ui=make_key_ui(execute=lambda name: registry.execute(name, holder[0])),
    )
    holder.append(ctx)
    buf = ctx.buffer
    buf.set_cursor((1, 1))
    buf.begin_block_selection()
    buf.move_down(select=True)
    assert buf.has_block_selection() is True

    assert VscKeymap().handle_key(ctx, "\x1b") is True
    assert buf.block is False
    assert buf.anchor is None
