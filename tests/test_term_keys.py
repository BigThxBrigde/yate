"""Unit tests for yate.editor_term.keys: event.key -> PTY byte sequences.

Covers the full branch set of :func:`key_to_terminal` (the emulator-side
tests do not reach these): printable keys, the named-key table, ctrl /
alt / ctrl+shift chords, the ctrl-symbol special codes and the shared
keyproto codec path for modified special keys.
"""

from __future__ import annotations

from yate.editor_term.keys import key_to_terminal
from yate.keyproto.legacy import modified_key_sequence


def test_key_to_terminal_printable_with_character_returns_character() -> None:
    assert key_to_terminal("a", "a") == "a"


def test_key_to_terminal_printable_without_character_returns_key() -> None:
    assert key_to_terminal("a", None) == "a"


def test_key_to_terminal_combo_ignores_character_argument() -> None:
    """A chord must not take the single-character fast path."""
    assert key_to_terminal("ctrl+a", "a") == "\x01"


def test_key_to_terminal_named_keys_resolve_table() -> None:
    """Plain named keys resolve through the built-in table."""
    assert key_to_terminal("enter", None) == "\r"
    assert key_to_terminal("escape", None) == "\x1b"
    assert key_to_terminal("f5", None) == "\x1b[15~"
    assert key_to_terminal("up", None) == "\x1b[A"
    assert key_to_terminal("backspace", None) == "\x7f"


def test_key_to_terminal_ctrl_letter_maps_control_code() -> None:
    assert key_to_terminal("ctrl+c", None) == "\x03"


def test_key_to_terminal_ctrl_symbol_maps_special_code() -> None:
    """Ctrl punctuation maps to its historic C0 special code."""
    assert key_to_terminal("ctrl+space", None) == "\x00"
    assert key_to_terminal("ctrl+[", None) == "\x1b"
    assert key_to_terminal("ctrl+?", None) == "\x7f"


def test_key_to_terminal_alt_prefixes_named_and_plain_keys() -> None:
    """alt + plain letter gets an ESC prefix; alt + arrow resolves through
    the shared keyproto codec (CSI 1;3A), not a doubled ESC."""
    assert key_to_terminal("alt+b", None) == "\x1bb"
    assert key_to_terminal("alt+up", None) == "\x1b[1;3A"


def test_key_to_terminal_ctrl_shift_letter_matches_ctrl_code() -> None:
    assert key_to_terminal("ctrl+shift+a", None) == "\x01"


def test_key_to_terminal_modified_arrows_match_keyproto_codec() -> None:
    """Modified arrows resolve through the shared driver codec so the PTY
    writer cannot drift from the keymap side (no exact bytes pinned)."""
    expected = modified_key_sequence(frozenset({"ctrl"}), "left")
    assert expected is not None and expected.startswith("\x1b")
    assert key_to_terminal("ctrl+left", None) == expected


def test_key_to_terminal_unmapped_modifier_combo_returns_none() -> None:
    assert key_to_terminal("meta+x", None) is None


def test_key_to_terminal_unknown_named_key_returns_none() -> None:
    assert key_to_terminal("capslock", None) is None
