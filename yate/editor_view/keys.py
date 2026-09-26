"""Translation from Textual key names to the raw byte sequences yate keymaps
use (control codes / ANSI escape sequences)."""

from __future__ import annotations

from yate.keymaps.base import SPECIAL_KEYS

# Textual canonical key names share their raw sequences with the keymap's
# SPECIAL_KEYS table (minus the "esc" alias -- Textual always reports "escape").
_NAMED_KEYS = {name: raw for name, raw in SPECIAL_KEYS.items() if name != "esc"}

# Ctrl+punctuation raw bytes. Ctrl+/ is 0x1F (the vsc keymap's keymap
# toggle); without these entries it could never reach it -- terminals and
# Textual drivers spell the same byte several ways: legacy/xterm delivers
# \x1f as "ctrl+underscore", kitty CSI-u as "ctrl+slash", and some win32
# driver paths use "ctrl+slash" for the bare name too, so every spelling
# must map to the same byte.
_CTRL_PUNCT = {
    "[": 0x1B,
    "\\": 0x1C,
    "]": 0x1D,
    "/": 0x1F,
    "underscore": 0x1F,
    "slash": 0x1F,
}

_MOD_ARROWS: dict[tuple[str, ...], dict[str, str]] = {
    ("ctrl",): {"up": "\x1b[1;5A", "down": "\x1b[1;5B", "right": "\x1b[1;5C", "left": "\x1b[1;5D"},
    ("shift",): {"up": "\x1b[1;2A", "down": "\x1b[1;2B", "right": "\x1b[1;2C", "left": "\x1b[1;2D"},
    ("ctrl", "shift"): {"right": "\x1b[1;6C", "left": "\x1b[1;6D"},
    ("alt",): {"up": "\x1b[1;3A", "down": "\x1b[1;3B", "right": "\x1b[1;3C", "left": "\x1b[1;3D"},
}

_MOD_SPECIAL: dict[tuple[str, ...], dict[str, str]] = {
    ("ctrl",): {"home": "\x1b[1;5H", "end": "\x1b[1;5F",
                "pageup": "\x1b[5;5~", "pagedown": "\x1b[6;5~"},
    ("shift",): {"home": "\x1b[1;2H", "end": "\x1b[1;2F", "tab": "\x1b[Z"},
}


def event_to_raw(key: str, character: str | None = None) -> str | None:
    """Map a Textual Key event to a raw key string.

    Textual reports shifted punctuation as long names (``"exclamation_mark"``)
    with the actual glyph in ``event.character``; prefer that for plain keys
    without modifiers.  For ctrl-chords the table lookup is tried first, then
    a C0 fallback: real-terminal drivers (observed on Windows Terminal's
    win32 driver) spell ctrl+punctuation with long names the table does not
    know (``ctrl+right_square_bracket``, ``ctrl+circumflex_accent``) while
    ``event.character`` still carries the true C0 byte (``\\x1d``, ``\\x1e``)
    -- the byte is by definition what the keymap tables dispatch on, so it
    wins over an unknown name.  Printable characters never satisfy the
    fallback, which keeps physically-unmappable chords (``ctrl+1`` on legacy
    terminals) returning ``None``.
    """
    if (
        "+" not in key
        and character
        and len(character) == 1
        and character.isprintable()
    ):
        return character
    raw = textual_key_to_raw(key)
    if raw is not None:
        return raw
    if (
        key.startswith("ctrl+")
        and character
        and len(character) == 1
        and ord(character) < 0x20
    ):
        return character
    return None


def textual_key_to_raw(key: str) -> str | None:
    """Translate a Textual ``event.key`` string to the raw escape/ctrl byte
    sequence that :mod:`yate.keymaps` understand.

    Printable characters pass through unchanged; unknown keys return ``None``.
    """
    if not key:
        return None
    if len(key) == 1:
        return key
    if key in _NAMED_KEYS:
        return _NAMED_KEYS[key]

    parts = key.split("+")
    if len(parts) == 1:
        return None
    mods, last = tuple(sorted(parts[:-1])), parts[-1]

    if mods in _MOD_ARROWS and last in _MOD_ARROWS[mods]:
        return _MOD_ARROWS[mods][last]
    if mods in _MOD_SPECIAL and last in _MOD_SPECIAL[mods]:
        return _MOD_SPECIAL[mods][last]

    if mods == ("ctrl",):
        if last in _CTRL_PUNCT:
            return chr(_CTRL_PUNCT[last])
        if last == "space":
            return "\x00"
        if len(last) == 1 and last.isalpha():
            return chr(ord(last.lower()) - ord("a") + 1)
        return None
    if mods == ("alt",):
        if last == "backspace":
            return "\x1b\x7f"
        if len(last) == 1:
            return "\x1b" + last
        return None
    return None
