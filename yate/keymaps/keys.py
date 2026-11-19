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

#: Shared default for the "show API documentation" action. Both built-in
#: keymaps import this single L0 constant (AC2); <ctrl-k> is NOT usable
#: because it aliases <ctrl-shift-k> (delete_line) at raw byte \x0b.
HOVER_DOC_KEY: str = "<f7>"
#: Shared key for toggling macro recording in both built-in keymaps (AC3).
MACRO_RECORD_KEY: str = "<f10>"
#: Shared key for playing a recorded macro in both built-in keymaps (AC3).
MACRO_PLAY_KEY: str = "<f11>"
#: Shared key for repeating the last macro replay in both keymaps (AC3).
MACRO_REPLAY_LAST_KEY: str = "<f12>"
#: Shared key for toggling soft-wrap display in both built-in keymaps
#: (IKVRXT); alt+z parses to ESC+z and collides with no existing binding.
SOFT_WRAP_KEY: str = "<alt-z>"
#: Shared key for toggling comments in both built-in keymaps (IKWNOG).
#: Ctrl+/ and Ctrl+Shift+/ both parse to raw ``\x1f``, so the comment action
#: owns that raw key; the keymap toggle is intercepted by event.key name in
#: :mod:`yate.editor_dispatch` before raw conversion.
TOGGLE_COMMENT_KEY: str = "<ctrl-/>"
#: Textual event.key name of the keymap toggle chord, NOT a keymap spec:
#: ``parse_key("<ctrl-shift-/>")`` collapses to ``"\x1f"`` just like
#: :data:`TOGGLE_COMMENT_KEY`, so a second raw row could never distinguish it.
TOGGLE_KEYMAP_KEY: str = "ctrl+shift+/"
#: Legal single-character macro register names (a-z0-9), shared by the
#: dispatch register guard, the L3 flows layer and the ``:macro-*`` commands
#: (pure L0 data; keeping it here avoids an L3 -> L3 cross-module import).
MACRO_REGISTER_CHARS: str = "abcdefghijklmnopqrstuvwxyz0123456789"

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


#: Raw forms of the three macro control keys; dispatch uses this set to keep
#: the control keys themselves out of a recorded sequence and to reject a
#: replay-triggering key while a replay is in flight (AC4).
MACRO_CONTROL_KEYS: frozenset[str] = frozenset(
    parse_key(key)
    for key in (MACRO_RECORD_KEY, MACRO_PLAY_KEY, MACRO_REPLAY_LAST_KEY)
)

#: Shared jump-list / marks keys for both built-in keymaps (issue IKUOCI).
#: alt+arrow reaches the keymap as modified-CSI bytes -- keyproto.key_codec
#: maps Textual's "alt+left"/"alt+right" event names to exactly these
#: sequences (vsc move_line_up precedent) -- so the constants hold the raw
#: CSI form; parse_key would produce the meta-prefix form ("\x1b\x1b[D")
#: which no terminal sends.  key_name() renders both via KEY_ALIASES as
#: "<alt-left>" / "<alt-right>" in help and which-key surfaces.
JUMPLIST_BACK_KEY: str = "\x1b[1;3D"
JUMPLIST_FORWARD_KEY: str = "\x1b[1;3C"
#: Marks overlay key (alt+m); parse_key's meta-prefix form IS the bytes a
#: terminal sends for alt plus a letter (MACRO_CONTROL_KEYS precedent).
MARKS_OVERLAY_KEY: str = parse_key("<alt-m>")


def key_name(key: str) -> str:
    """Inverse of :func:`parse_key`, used by the help overlay."""
    if key == TOGGLE_KEYMAP_KEY:
        # Help-only name-level chord; not a raw byte, so render it literally.
        return "<ctrl-shift-/>"
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
        if 28 <= code <= 30:
            # FS/GS/RS (0x1c..0x1e) are the C0 images of ctrl-\, ctrl-] and
            # ctrl-^ -- the tail of parse_key's "@".."_" ctrl range that the
            # letter branch above and the alias (0x1f -> ctrl-/) leave
            # uncovered; without this the raw byte leaks into the help
            # overlay and the which-key sheet.
            return f"<ctrl-{chr(code + 64)}>"
        if key == " ":
            return "<space>"
        return key
    if key.startswith("\x1b") and len(key) == 2:
        # Name the byte after the modifier through the single-char path so
        # <alt-backspace> reads as such instead of leaking the raw DEL byte
        # (same leak class as the FS/GS/RS branch above).
        named = key_name(key[1])
        body = (
            named[1:-1]
            if named.startswith("<") and named.endswith(">") and len(named) > 2
            else named
        )
        return f"<alt-{body}>"
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
