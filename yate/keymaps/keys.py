"""Key notation for keymaps (L0 leaf, no upward dependencies).

``KEY_ALIASES`` / ``SPECIAL_KEYS`` plus the two codecs :func:`parse_key` and
:func:`key_name` are the whole of this module: pure string logic that any
layer may import, including the L0 key codecs in :mod:`yate.keyproto`.
``keymaps/base.py`` (L1) re-exports them for the historical import surface;
**L0 code must import them from here** -- the layer guard in
``tests/test_architecture.py`` rejects an L0 module reaching into ``base``.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Key notation
#
# Human readable key specs (used by binding tables and extension scripts):
#   "<ctrl-x>" "<alt-x>" "<shift-x>" "<f1>" "<enter>" "<esc>" "<tab>"
#   "<backspace>" "<up>" "<down>" "<left>" "<right>" "<home>" "<end>"
#   "<pageup>" "<pagedown>" "<delete>" "<space>"
# Plain characters are written literally:  "a", "1", ":", "/".
# ---------------------------------------------------------------------------

SPECIAL_KEYS: dict[str, str] = {
    "enter": "\r",
    "return": "\r",
    "esc": "\x1b",
    "escape": "\x1b",
    "tab": "\t",
    "space": " ",
    "backspace": "\x7f",
    "delete": "\x1b[3~",
    "insert": "\x1b[2~",
    "up": "\x1b[A",
    "down": "\x1b[B",
    "right": "\x1b[C",
    "left": "\x1b[D",
    "home": "\x1b[H",
    "end": "\x1b[F",
    "pageup": "\x1b[5~",
    "pagedown": "\x1b[6~",
    "f1": "\x1bOP",
    "f2": "\x1bOQ",
    "f3": "\x1bOR",
    "f4": "\x1bOS",
    "f5": "\x1b[15~",
    "f6": "\x1b[17~",
    "f7": "\x1b[18~",
    "f8": "\x1b[19~",
    "f9": "\x1b[20~",
    "f10": "\x1b[21~",
    "f11": "\x1b[23~",
    "f12": "\x1b[24~",
}

# Common terminal variants not covered by the canonical names.
KEY_ALIASES: dict[str, str] = {
    "\x1b[1~": "home",
    "\x1b[4~": "end",
    "\x1b[1;5D": "ctrl-left",
    "\x1b[1;5C": "ctrl-right",
    "\x1b[1;2D": "shift-left",
    "\x1b[1;2C": "shift-right",
    "\x1b[1;2A": "shift-up",
    "\x1b[1;2B": "shift-down",
    "\x1b[1;6D": "ctrl-shift-left",
    "\x1b[1;6C": "ctrl-shift-right",
    "\x1b[1;5H": "ctrl-home",
    "\x1b[1;5F": "ctrl-end",
    "\x1b[1;2H": "shift-home",
    "\x1b[1;2F": "shift-end",
    "\x1b[5;5~": "ctrl-pageup",
    "\x1b[6;5~": "ctrl-pagedown",
    "\x1b[1;3A": "alt-up",
    "\x1b[1;3B": "alt-down",
    "\x1b[1;3C": "alt-right",
    "\x1b[1;3D": "alt-left",
    "\x1b[Z": "shift-tab",
    # Both ctrl-/ and ctrl-_ physically send US (0x1f) on most terminals;
    # key_name() therefore displays <ctrl-_> bindings as <ctrl-/>.
    "\x1f": "ctrl-/",
}

#: Inverse of :data:`KEY_ALIASES` (canonical name -> raw sequence).
#: :func:`parse_key` uses it for shift+special specs, whose real sequences
#: differ from the unmodified key instead of deriving from it.
_KEY_ALIASES_INV: dict[str, str] = {
    name: raw for raw, name in KEY_ALIASES.items()
}


def parse_key(spec: str) -> str:
    """Parse a human key spec (``"<ctrl-s>"``) into a raw key string."""
    if not (spec.startswith("<") and spec.endswith(">")):
        return spec
    body = spec[1:-1].lower()
    tokens = body.split("-")
    modifiers = set(tokens[:-1])
    unknown = modifiers - {"shift", "alt", "ctrl"}
    if unknown:
        # A typo like "<ctr-s>" must not silently bind the unmodified key.
        raise ValueError(f"unknown modifier(s) in spec: {spec!r}")
    name = tokens[-1]

    if name in SPECIAL_KEYS:
        base = SPECIAL_KEYS[name]
    elif len(name) == 1:
        base = name
    else:
        raise ValueError(f"unknown key name in spec: {spec!r}")

    if "shift" in modifiers:
        if name == "tab":
            # shift-tab is a real sequence (``\x1b[Z``), not "T" -- uppercasing
            # the single-character base would silently alias plain tab.
            base = "\x1b[Z"
        elif len(base) == 1:
            base = base.upper()
        else:
            # Real terminals encode shift+special with modified CSI
            # parameters; silently dropping the modifier would alias the
            # plain key (``<shift-up>`` would bind exactly like ``<up>``).
            # Resolve through the alias table when the combination is
            # known, reject it otherwise (mirrors the ctrl handling).
            shifted = _KEY_ALIASES_INV.get(f"shift-{name}")
            if shifted is None:
                raise ValueError(f"unsupported shift key: {spec!r}")
            base = shifted
    if "alt" in modifiers:
        base = "\x1b" + base
    if "ctrl" in modifiers:
        if len(base) != 1:
            raise ValueError(f"ctrl requires a single character: {spec!r}")
        ch = base.upper()
        if ch == " ":
            base = "\x00"
        elif ch == "/":
            # ``/`` (0x2f) has no C0 letter mapping; terminals send ASCII US
            # (0x1f) for ctrl-/, matching KEY_ALIASES["\x1f"] = "ctrl-/".
            base = "\x1f"
        elif "@" <= ch <= "_":
            # ctrl-@ .. ctrl-_ map to codes 0x00 .. 0x1f (covers letters,
            # brackets etc. the same way a real terminal encodes them).
            base = chr(ord(ch) - 64)
        elif "0" <= ch <= "9":
            # ctrl+digits have no C0 code; encode as the kitty keyboard
            # protocol CSI-u sequence modern terminals send
            base = f"\x1b[{ord(ch)};5u"
        else:
            raise ValueError(f"unsupported ctrl key: {spec!r}")
    return base


def key_name(key: str) -> str:
    """Inverse of :func:`parse_key`, used by the help overlay."""
    if key in KEY_ALIASES:
        return "<" + KEY_ALIASES[key] + ">"
    for name, raw in SPECIAL_KEYS.items():
        if raw == key and name not in ("return", "escape"):
            return "<" + name + ">"
    if len(key) == 1:
        code = ord(key)
        if code == 0:
            return "<ctrl-space>"
        if 1 <= code <= 26:
            return f"<ctrl-{chr(code + ord('a') - 1)}>"
        if key == " ":
            return "<space>"
        return key
    if key.startswith("\x1b") and len(key) == 2:
        return f"<alt-{key[1]}>"
    m = re.fullmatch(r"\x1b\[(\d+);(\d+)u", key)
    if m:
        # kitty encodes the modifier field as 1 + bitmask (shift=1 alt=2 ctrl=4)
        code, mod = int(m.group(1)), int(m.group(2)) - 1
        if not mod:
            return chr(code)
        mods: list[str] = []
        if mod & 1:
            mods.append("shift")
        if mod & 2:
            mods.append("alt")
        if mod & 4:
            mods.append("ctrl")
        mods.append(chr(code))
        return "<" + "-".join(mods) + ">"
    return repr(key)
