"""Jump-list / marks key wiring (plan-b, issue IKUOCI).

Pure keymap-dispatch tests: no Textual, no editor widgets.  The context
comes from ``conftest`` -- a real :class:`EditorSession` plus a
:class:`KeyUi` stub whose ``execute_action`` records the action name, the
same shape the other keymap tests use.
"""

from __future__ import annotations

from conftest import make_action_context, make_key_ui

from yate.keymaps.base import ActionContext
from yate.keymaps.keys import (
    JUMPLIST_BACK_KEY,
    JUMPLIST_FORWARD_KEY,
    MARKS_OVERLAY_KEY,
)
from yate.keymaps.vim import VimKeymap, VimMode
from yate.keymaps.vsc import VscKeymap

#: The three shared raw keys, in table-row order.
_RAW_KEYS: tuple[str, ...] = (
    JUMPLIST_BACK_KEY,
    JUMPLIST_FORWARD_KEY,
    MARKS_OVERLAY_KEY,
)

#: Raw key -> action name both tables must agree on.
_ACTIONS: dict[str, str] = {
    JUMPLIST_BACK_KEY: "jump_back",
    JUMPLIST_FORWARD_KEY: "jump_forward",
    MARKS_OVERLAY_KEY: "marks_overlay",
}

#: Raw key -> rendered label (help / which-key surfaces, AC7).
_LABELS: dict[str, str] = {
    JUMPLIST_BACK_KEY: "<alt-left>",
    JUMPLIST_FORWARD_KEY: "<alt-right>",
    MARKS_OVERLAY_KEY: "<alt-m>",
}


def _context(seen: list[str], text: str = "") -> ActionContext:
    """An action context whose ``execute_action`` records action names."""
    def record(name: str) -> bool:
        seen.append(name)
        return True

    return make_action_context(text=text, ui=make_key_ui(execute=record))


def test_vim_alt_keys_consumed_in_all_three_modes() -> None:
    """Each alt key dispatches its action in NORMAL, INSERT and VISUAL."""
    km = VimKeymap()
    for mode in (VimMode.NORMAL, VimMode.INSERT, VimMode.VISUAL):
        km.mode = mode
        for key in _RAW_KEYS:
            seen: list[str] = []
            consumed = km.handle_key(_context(seen), key)
            assert consumed is True, (mode, key)
            assert seen == [_ACTIONS[key]], (mode, key, seen)


def test_vim_alt_key_clears_pending_chord() -> None:
    """A half-typed operator is dropped before the alt key dispatches."""
    km = VimKeymap()
    seen: list[str] = []
    ctx = _context(seen)
    km.handle_key(ctx, "d")
    assert km.op == "d"
    consumed = km.handle_key(ctx, JUMPLIST_BACK_KEY)
    assert consumed is True
    assert seen == ["jump_back"]
    assert km.op is None
    assert km.pending_prefix() == ""


def test_vim_unrelated_keys_unaffected() -> None:
    """The pre-dispatch branch eats only the three alt keys.

    ``x`` keeps its NORMAL-mode path (the hardcoded delete-forward branch,
    not the binding table, so ``ui`` records nothing) and never lands in
    the new navigation branch: no jump/marks action name is recorded and
    the buffer advances by one character.
    """
    km = VimKeymap()
    seen: list[str] = []
    ctx = _context(seen, text="abc")
    consumed = km.handle_key(ctx, "x")
    assert consumed is True
    assert seen == []
    assert ctx.buffer.get_text() == "bc"


def test_vsc_and_vim_resolve_same_actions_for_same_raw_keys() -> None:
    """Both tables map each raw key to the same action name."""
    vsc = VscKeymap()
    vim = VimKeymap()
    for key in _RAW_KEYS:
        vsc_binding = vsc.lookup(key)
        assert vsc_binding is not None, key
        vim_binding = vim.lookup(key)
        assert vim_binding is not None, key
        assert vsc_binding.action == _ACTIONS[key], (key, "vsc")
        assert vim_binding.action == _ACTIONS[key], (key, "vim")


def test_key_labels_render_alt_notation() -> None:
    """The three rows render <alt-left> / <alt-right> / <alt-m> labels."""
    vsc = VscKeymap()
    vim = VimKeymap()
    for key, label in _LABELS.items():
        vsc_binding = vsc.lookup(key)
        assert vsc_binding is not None, key
        assert vsc_binding.key_label == label, (key, "vsc", vsc_binding.key_label)
        vim_binding = vim.lookup(key)
        assert vim_binding is not None, key
        assert vim_binding.key_label == label, (key, "vim", vim_binding.key_label)
