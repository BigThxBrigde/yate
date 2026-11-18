"""Headless tests for the soft-wrap key surface: alt+z and vim gj/gk.

The alt+z bindings in both built-in keymaps resolve the shared L0 constant
(:func:`yate.keymaps.keys.parse_key` of ``SOFT_WRAP_KEY``) to the
``toggle_soft_wrap`` action; the vim ``gj`` / ``gk`` chords drive the
injected :attr:`KeyUi.move_display_line` callback and degenerate to the
logical-row motion when the callback is ``None`` (headless / wrap-off).
"""

from __future__ import annotations

from collections.abc import Callable

from yate.config import YateConfig
from yate.keymaps.base import ActionContext, KeyUi, parse_key
from yate.keymaps.keys import SOFT_WRAP_KEY
from yate.keymaps.vim import RESERVED_KEYS, VimKeymap, VimMode
from yate.keymaps.vsc import VscKeymap
from yate.session import EditorSession


def _recorder(calls: list[tuple[int, int, bool]]) -> Callable[[int, int, bool], None]:
    """A ``move_display_line`` stub recording ``(direction, count, select)``."""
    def move(direction: int, count: int, select: bool) -> None:
        calls.append((direction, count, select))
    return move


def _make_context(
    text: str,
    move_display_line: Callable[[int, int, bool], None] | None,
) -> ActionContext:
    """A real :class:`ActionContext` over a buffer seeded with *text*."""
    ui = KeyUi(
        execute_action=lambda _name: True,
        message=lambda _text: None,
        command_prompt=lambda: None,
        find_prompt=lambda _forward: None,
        goto_prompt=lambda: None,
        toggle_keymap=lambda: None,
        move_display_line=move_display_line,
    )
    session = EditorSession(YateConfig())
    session.new_buffer().buffer.set_text(text)
    return ActionContext(session, ui)


def test_counted_gj_moves_display_rows_down() -> None:
    """``3gj`` calls the display-line callback once with direction +1, count 3."""
    calls: list[tuple[int, int, bool]] = []
    ctx = _make_context("ab\ncd\nef", _recorder(calls))
    keymap = VimKeymap()
    for key in "3gj":
        keymap.handle_key(ctx, key)
    assert calls == [(1, 3, False)]
    assert keymap.prefix is None
    assert keymap.count_str == ""


def test_gk_moves_display_rows_up_with_default_count() -> None:
    """``gk`` calls the display-line callback with direction -1, count 1."""
    calls: list[tuple[int, int, bool]] = []
    ctx = _make_context("ab\ncd\nef", _recorder(calls))
    keymap = VimKeymap()
    keymap.handle_key(ctx, "g")
    keymap.handle_key(ctx, "k")
    assert calls == [(-1, 1, False)]


def test_visual_gj_moves_display_rows_over_the_selection() -> None:
    """Visual-mode ``gj`` passes ``select=True`` so the anchor is kept."""
    calls: list[tuple[int, int, bool]] = []
    ctx = _make_context("ab\ncd\nef", _recorder(calls))
    keymap = VimKeymap()
    keymap.handle_key(ctx, "v")
    assert keymap.mode is VimMode.VISUAL
    keymap.handle_key(ctx, "g")
    keymap.handle_key(ctx, "j")
    assert calls == [(1, 1, True)]
    assert keymap.mode is VimMode.VISUAL
    assert keymap.prefix is None


def test_gj_without_callback_degenerates_to_logical_motion() -> None:
    """With ``move_display_line`` unset, ``gj`` falls back to logical rows."""
    ctx = _make_context("ab\ncd\nef", None)
    keymap = VimKeymap()
    keymap.handle_key(ctx, "g")
    keymap.handle_key(ctx, "j")
    assert ctx.buffer.cursor[0] == 1


def test_gg_still_jumps_to_first_line_next_to_gj() -> None:
    """``gg`` keeps its jump semantics; a count still targets line N."""
    calls: list[tuple[int, int, bool]] = []
    ctx = _make_context("ab\ncd\nef", _recorder(calls))
    keymap = VimKeymap()
    for key in "2gg":
        keymap.handle_key(ctx, key)
    assert ctx.buffer.cursor[0] == 1
    assert calls == []


def test_unknown_g_follower_is_still_dropped() -> None:
    """``gq`` claims nothing: the prefix drops and the key is swallowed."""
    calls: list[tuple[int, int, bool]] = []
    ctx = _make_context("ab\ncd", _recorder(calls))
    keymap = VimKeymap()
    keymap.handle_key(ctx, "g")
    assert keymap.handle_key(ctx, "q") is True
    assert keymap.prefix is None
    assert ctx.buffer.cursor == (0, 0)
    assert calls == []


def test_alt_z_resolves_toggle_soft_wrap_in_both_keymaps() -> None:
    """alt+z resolves to ``toggle_soft_wrap`` in vim and vsc alike."""
    raw = parse_key(SOFT_WRAP_KEY)
    assert raw == "\x1bz"
    vsc_binding = VscKeymap().lookup(raw)
    assert vsc_binding is not None
    assert vsc_binding.action == "toggle_soft_wrap"
    vim_binding = VimKeymap().lookup(raw)
    assert vim_binding is not None
    assert vim_binding.action == "toggle_soft_wrap"


def test_soft_wrap_key_is_not_reserved_in_either_keymap() -> None:
    """alt+z is a table binding: it sits in no keymap's reserved-key set."""
    raw = parse_key(SOFT_WRAP_KEY)
    assert raw not in RESERVED_KEYS
    assert raw not in VscKeymap().reserved_keys
