"""Wave-1 plan-b pins: LSP navigation key constants, chords and actions.

Covers the five shared key constants in :mod:`yate.keymaps.keys`, the vim
``gd``/``gr``/``K`` dispatch, the vsc ``<alt-g>``/``<alt-r>``/``K`` bindings
and the six new action names registered in :mod:`yate.actions`.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast

from yate.actions import populate
from yate.editor import Editor
from yate.keymaps.base import parse_key
from yate.keymaps.keys import (
    FIND_REFS_KEY,
    FIND_REFS_VSC_KEY,
    GOTO_DEF_KEY,
    GOTO_DEF_VSC_KEY,
    HOVER_POPUP_KEY,
)
from yate.keymaps.vim import VimKeymap
from yate.keymaps.vsc import VscKeymap
from yate.registries import ActionRegistry

from conftest import make_action_context, make_key_ui


def test_lsp_navigation_keys_are_distinct_and_defined_once() -> None:
    """All five constants are pairwise distinct; <shift-k> normalizes to K."""
    keys = {
        GOTO_DEF_KEY,
        FIND_REFS_KEY,
        GOTO_DEF_VSC_KEY,
        FIND_REFS_VSC_KEY,
        HOVER_POPUP_KEY,
    }
    assert len(keys) == 5
    assert parse_key(HOVER_POPUP_KEY) == "K"


def test_vsc_lsp_shortcuts_resolve_to_actions() -> None:
    """The vsc table binds alt-g / alt-r / K to the navigation actions."""
    vsc = VscKeymap()
    goto = vsc.lookup(parse_key(GOTO_DEF_VSC_KEY))
    assert goto is not None
    assert goto.action == "goto_definition"
    refs = vsc.lookup(parse_key(FIND_REFS_VSC_KEY))
    assert refs is not None
    assert refs.action == "find_references"
    hover = vsc.lookup(parse_key(HOVER_POPUP_KEY))
    assert hover is not None
    assert hover.action == "show_hover_docs"


def test_vim_k_resolves_to_hover_action() -> None:
    """<shift-k> parses to ``K`` and the vim table dispatches show_hover_docs."""
    vim = VimKeymap()
    binding = vim.lookup(parse_key(HOVER_POPUP_KEY))
    assert binding is not None
    assert binding.action == "show_hover_docs"


def test_vim_g_chords_call_navigation_actions() -> None:
    """``gd`` / ``gr`` fire goto_definition / find_references and clear
    the ``g`` prefix (the chord is a complete command)."""
    for chord, action in (("d", "goto_definition"), ("r", "find_references")):
        executed: list[str] = []
        ctx = make_action_context(
            "alpha beta\ngamma delta",
            make_key_ui(execute=lambda name, _l=executed: _l.append(name) or True),
        )
        vim = VimKeymap()
        assert vim.handle_key(ctx, "g") is True
        assert vim.handle_key(ctx, chord) is True
        assert executed == [action]
        assert vim.prefix is None


def test_vim_gd_does_not_break_existing_g_chords() -> None:
    """``gg`` / ``gj`` / ``gc`` keep their prior paths: no navigation action
    is recorded and the prior state transitions still occur."""
    executed: list[str] = []
    ctx = make_action_context(
        "alpha beta\ngamma delta",
        make_key_ui(execute=lambda name: executed.append(name) or True),
    )
    vim = VimKeymap()

    # gg: document start -- cursor jumps from row 1 back to row 0
    ctx.buffer.set_cursor((1, 0))
    assert vim.handle_key(ctx, "g") is True
    assert vim.handle_key(ctx, "g") is True
    assert ctx.buffer.cursor == (0, 0)
    assert executed == []

    # gj: display-line motion -- cursor moves one row down
    ctx2 = make_action_context(
        "alpha beta\ngamma delta",
        make_key_ui(execute=lambda name: executed.append(name) or True),
    )
    vim2 = VimKeymap()
    ctx2.buffer.set_cursor((0, 0))
    assert vim2.handle_key(ctx2, "g") is True
    assert vim2.handle_key(ctx2, "j") is True
    assert ctx2.buffer.cursor == (1, 0)
    assert executed == []

    # gc: the comment operator arms (gcc pending), prefix stays visible
    ctx3 = make_action_context(
        "alpha beta\ngamma delta",
        make_key_ui(execute=lambda name: executed.append(name) or True),
    )
    vim3 = VimKeymap()
    assert vim3.handle_key(ctx3, "g") is True
    assert vim3.handle_key(ctx3, "c") is True
    assert vim3.comment_pending is True
    assert vim3.pending_prefix() == "c"
    assert executed == []


def test_builtin_actions_include_lsp_navigation_names() -> None:
    """The six new action names resolve through populate() against a stub
    editor exposing ``lsp_navigation`` (wave d supplies the real flows)."""
    recorded: list[str] = []
    lsp = SimpleNamespace(
        goto_definition=lambda: recorded.append("goto_definition"),
        find_references=lambda: recorded.append("find_references"),
        show_outline=lambda: recorded.append("show_outline"),
        rename_symbol=lambda: recorded.append("rename_symbol"),
        show_code_actions=lambda: recorded.append("show_code_actions"),
        show_signature_help=lambda: recorded.append("show_signature_help"),
    )
    editor_stub = cast(Editor, SimpleNamespace(lsp_navigation=lsp))
    registry = ActionRegistry()
    populate(registry, editor_stub)

    ctx = make_action_context("")
    for name in (
        "goto_definition",
        "find_references",
        "show_outline",
        "rename_symbol",
        "show_code_actions",
        "show_signature_help",
    ):
        assert registry.execute(name, ctx) is True
    assert recorded == [
        "goto_definition",
        "find_references",
        "show_outline",
        "rename_symbol",
        "show_code_actions",
        "show_signature_help",
    ]
