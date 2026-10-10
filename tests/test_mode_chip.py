"""Unit tests for the status-bar ``mode_chip`` pure function (issue IKKJHH)."""

from __future__ import annotations

from yate.editor_core.buffer import TextBuffer
from yate.editor_view import theme
from yate.editor_view.commandline import PromptBar
from yate.editor_view.statusbar import mode_chip
from yate.keymaps.registry import KeymapSet
from yate.keymaps.vim import VimKeymap, VimMode
from yate.keymaps.vsc import VscKeymap


def _prompt() -> PromptBar:
    """Minimal unmounted PromptBar whose ``active_mode`` is ``None``."""
    return PromptBar(
        lambda _text, _mode: [],
        cancel_hook=lambda: None,
        focus_editor=lambda: None,
        refresh=lambda: None,
    )


def _keymaps(name: str) -> KeymapSet:
    """A two-entry keymap set with *name* active."""
    return KeymapSet({"vsc": VscKeymap(), "vim": VimKeymap()}, name)


def test_mode_chip_multi_cursor_shows_v_column_in_vim_normal() -> None:
    """An extra cursor overrides the vim NORMAL chip with ``V-COLUMN``."""
    buf = TextBuffer("ab\ncd")
    assert buf.add_cursor_at((0, 1))
    label, bg = mode_chip(_prompt(), _keymaps("vim"), buf)
    assert (label, bg) == ("V-COLUMN", theme.active().mode_visual_bg)


def test_mode_chip_multi_cursor_shows_v_column_in_insert() -> None:
    """vim INSERT does not shadow the multi-cursor chip."""
    keymaps = _keymaps("vim")
    vim = keymaps.get("vim")
    assert isinstance(vim, VimKeymap)
    vim.mode = VimMode.INSERT
    buf = TextBuffer("ab\ncd")
    assert buf.add_cursor_at((0, 1))
    label, bg = mode_chip(_prompt(), keymaps, buf)
    assert (label, bg) == ("V-COLUMN", theme.active().mode_visual_bg)


def test_mode_chip_multi_cursor_shows_v_column_in_vsc() -> None:
    """The ``VSC`` fallback is overridden while multi-cursor is active."""
    buf = TextBuffer("ab\ncd")
    assert buf.add_cursor_at((0, 1))
    label, bg = mode_chip(_prompt(), _keymaps("vsc"), buf)
    assert (label, bg) == ("V-COLUMN", theme.active().mode_visual_bg)


def test_mode_chip_no_extra_cursors_keeps_vim_mapping() -> None:
    """Without extra cursors the vim NORMAL chip is unchanged."""
    label, bg = mode_chip(_prompt(), _keymaps("vim"), TextBuffer("ab\ncd"))
    assert (label, bg) == ("NORMAL", theme.active().mode_normal_bg)


def test_mode_chip_no_extra_cursors_vsc_fallback() -> None:
    """Without extra cursors the vsc fallback chip is unchanged."""
    label, bg = mode_chip(_prompt(), _keymaps("vsc"), TextBuffer("ab\ncd"))
    assert (label, bg) == ("VSC", theme.active().mode_normal_bg)


def test_mode_chip_prompt_active_beats_multi_cursor() -> None:
    """An active prompt outranks the multi-cursor chip (branch order)."""
    prompt = _prompt()
    prompt.active_mode = "command"
    buf = TextBuffer("ab\ncd")
    assert buf.add_cursor_at((0, 1))
    label, bg = mode_chip(prompt, _keymaps("vim"), buf)
    assert (label, bg) == ("COMMAND", theme.active().mode_command_bg)
