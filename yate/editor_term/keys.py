"""Translate Textual ``event.key`` names to the byte sequences a PTY expects.

The terminal dock feeds these sequences to the PTY writer.  Modified special
keys resolve through :func:`yate.keyproto.legacy.modified_key_sequence` so
this table cannot drift from the driver-side codec (the former local copy
missed ctrl+shift arrows and modified home/end, silently dropping those keys
in the integrated terminal).
"""

from __future__ import annotations

from yate.keyproto.legacy import modified_key_sequence

#: Byte sequences for the named (non-printable) keys, keyed by
#: ``event.key`` name.
_NAMED: dict[str, str] = {
    "enter": "\r", "return": "\r",
    "tab": "\t",
    "space": " ",
    "backspace": "\x7f",
    "escape": "\x1b", "esc": "\x1b",
    "delete": "\x1b[3~", "insert": "\x1b[2~",
    "home": "\x1b[H", "end": "\x1b[F",
    "pageup": "\x1b[5~", "pagedown": "\x1b[6~",
    "up": "\x1b[A", "down": "\x1b[B", "right": "\x1b[C", "left": "\x1b[D",
    "f1": "\x1bOP", "f2": "\x1bOQ", "f3": "\x1bOR", "f4": "\x1bOS",
    "f5": "\x1b[15~", "f6": "\x1b[17~", "f7": "\x1b[18~", "f8": "\x1b[19~",
    "f9": "\x1b[20~", "f10": "\x1b[21~", "f11": "\x1b[23~", "f12": "\x1b[24~",
}


def key_to_terminal(key: str, character: str | None = None) -> str | None:
    """Translate a Textual ``event.key`` to the byte sequence a PTY expects."""
    if "+" not in key and character and len(character) == 1:
        return character
    if len(key) == 1:
        return key
    if key in _NAMED:
        return _NAMED[key]

    parts = key.split("+")
    if len(parts) == 1:
        return None
    mods = frozenset(parts[:-1])
    base = parts[-1]

    shared = modified_key_sequence(mods, base)
    if shared is not None:
        return shared

    if mods == frozenset({"ctrl"}):
        if base in ("space", "@"):
            return "\x00"
        mapping = {"[": 0x1B, "\\": 0x1C, "]": 0x1D,
                   "^": 0x1E, "_": 0x1F, "?": 0x7F}
        if base in mapping:
            return chr(mapping[base])
        if len(base) == 1 and base.isalpha():
            return chr(ord(base.lower()) - ord("a") + 1)
        return None

    if mods == frozenset({"alt"}):
        inner = _NAMED.get(base)
        if inner is None and len(base) == 1:
            inner = base
        return ("\x1b" + inner) if inner is not None else None

    if mods == frozenset({"ctrl", "shift"}):
        if base in ("space", "@"):
            return "\x00"
        if len(base) == 1 and base.isalpha():
            return chr(ord(base.lower()) - ord("a") + 1)
        return None
    return None
