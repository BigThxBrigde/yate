"""The shared hover-documentation key: one constant, two built-in tables.

Guards plan c (lsp-hover-docs wave-1): ``HOVER_DOC_KEY`` is a single L0
constant referenced by both keymap tables, it maps to a free function key
(``<f7>``), and neither table hard-codes the literal.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import cast

import pytest

from yate.keymaps.base import HOVER_DOC_KEY, parse_key
from yate.keymaps.conflicts import find_key_conflicts
from yate.keymaps.keys import SPECIAL_KEYS, key_name
from yate.keymaps.registry import KeymapSet
from yate.keymaps import vim as vim_keymaps
from yate.keymaps.vim import RESERVED_KEYS, VimKeymap, VimMode
from yate.keymaps.vsc import VscKeymap
from conftest import make_action_context, make_key_ui

_RAW: str = parse_key(HOVER_DOC_KEY)


def test_hover_key_constant_is_f7_and_maps_to_f7_raw() -> None:
    """The constant is the ``<f7>`` notation and resolves to its raw code."""
    assert HOVER_DOC_KEY == "<f7>"
    assert _RAW == SPECIAL_KEYS["f7"] == "\x1b[18~"


def test_vsc_and_vim_bind_the_same_raw_key_to_hover_action() -> None:
    """Both built-in tables expose ``show_hover_docs`` on the same raw key."""
    vsc_binding = VscKeymap().lookup(_RAW)
    vim_binding = VimKeymap().lookup(_RAW)
    assert vsc_binding is not None
    assert vim_binding is not None
    assert vsc_binding.action == "show_hover_docs"
    assert vim_binding.action == "show_hover_docs"
    assert vsc_binding.key == vim_binding.key == _RAW


def test_hover_key_is_not_a_conflict_in_either_keymap() -> None:
    """No conflict class claims the hover raw key; ctrl+shift+k stays intact."""
    raw = _RAW
    vsc_conflicts = find_key_conflicts(VscKeymap())
    vim_conflicts = find_key_conflicts(VimKeymap(), reserved=RESERVED_KEYS)
    for conflicts in (vsc_conflicts, vim_conflicts):
        assert not [c for c in conflicts if c.raw == raw]
    ctrl_shift_k = parse_key("<ctrl-shift-k>")
    binding = VscKeymap().lookup(ctrl_shift_k)
    assert binding is not None
    assert binding.action == "delete_line"


def test_hover_key_is_not_a_vim_motion_or_reserved_key() -> None:
    """The hover raw key is free of vim hard-coded dispatch claims."""
    raw = _RAW
    motion_codes = cast(
        frozenset[str], getattr(vim_keymaps, "_MOTION_CODES")
    )
    assert raw not in RESERVED_KEYS
    assert raw not in motion_codes
    occupied = ("<f1>", "<f2>", "<f8>", "<f9>", "<ctrl-shift-k>")
    assert HOVER_DOC_KEY not in occupied


def test_both_tables_reference_the_shared_constant() -> None:
    """Each ``build_bindings`` mentions the constant once; no literal <f7>."""
    base = Path(__file__).resolve().parent.parent / "yate" / "keymaps"
    for module in ("vsc.py", "vim.py"):
        source = (base / module).read_text(encoding="utf-8")
        tree = ast.parse(source)
        names = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Name) and node.id == "HOVER_DOC_KEY"
        ]
        assert len(names) == 1, module
        literals = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and node.value == "<f7>"
        ]
        assert literals == [], module


@pytest.mark.parametrize("mode", list(VimMode))
def test_vim_dispatches_hover_key_in_normal_insert_and_visual_modes(
    mode: VimMode,
) -> None:
    """Every vim mode dispatches the hover key to ``show_hover_docs``."""
    dispatched: list[str] = []

    def recorder(action: str) -> bool:
        dispatched.append(action)
        return True

    vim = VimKeymap()
    vim.mode = mode
    ctx = make_action_context(ui=make_key_ui(execute=recorder))
    assert vim.handle_key(ctx, _RAW) is True
    assert dispatched == ["show_hover_docs"]


def test_toggle_keymap_preserves_hover_binding() -> None:
    """The binding survives ``KeymapSet.toggle()`` in both directions."""
    keymaps = KeymapSet({"vsc": VscKeymap(), "vim": VimKeymap()}, "vsc")
    for _ in range(3):
        binding = keymaps.active.lookup(_RAW)
        assert binding is not None
        assert binding.action == "show_hover_docs"
        keymaps.toggle()


def test_key_name_round_trip_displays_the_hover_key() -> None:
    """The human label of the raw key keeps the ``f7`` name visible."""
    assert "f7" in key_name(_RAW)
