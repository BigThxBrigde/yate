"""Decoder for Windows Terminal's win32-input-mode key frames.

With ``CSI ?9001h`` enabled, Windows Terminal encodes every key event as a
structured frame ``CSI Vk;Sc;Ucs;Kf;Ss;Rc_`` (decimal fields: virtual-key
code, scan code, UCS character, key-down flag, ``dwControlKeyState``,
repeat count) instead of lossy legacy bytes -- the probe of 2026-09-26
confirmed full fidelity for exactly the chords the legacy path loses
(``ctrl+shift+e`` arrives as ``[69;18;5;1;56;1_`` where the legacy record
carried a bare ``\\x05``).  ConPTY forwards the frames as plain text inside
the console records' character stream, so :class:`Win32FrameStream`
intercepts them before the legacy VT parser sees the bytes.

Terminals that do not implement win32-input-mode ignore ``?9001h`` and keep
feeding legacy bytes; the stream then simply never yields a frame and every
character passes through untouched.

Frame inputs are not authenticated: a pasted text containing a literal
``CSI <digits> _`` sequence decodes as a key.  That requires deliberately
typing an encoding nobody emits by hand, so it is accepted.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from yate.keyproto.aliases import chord_to_key_name
from yate.keyproto.chords import (
    ALT_BITS,
    CTRL_BITS,
    MODIFIER_VKS,
    SHIFT_BIT,
    KeyChord,
)

#: Complete win32-input-mode frame: ESC [ <digits/semicolons> _ .
_FRAME_RE: re.Pattern[str] = re.compile(r"\x1b\[([0-9;]+)_")

#: Trailing text that might still grow into a frame (ESC [ followed only by
#: digits/semicolons).  Held back across :meth:`Win32FrameStream.feed` calls
#: so a frame split between two read batches still decodes; anything else
#: (e.g. a legacy ``ESC [ A`` arrow sequence, whose char after ``[`` is not a
#: digit) is returned to the caller immediately.
_HOLD_RE: re.Pattern[str] = re.compile(r"\x1b\[[0-9;]*\Z")

#: Maximum bytes held back for a partial frame prefix; a longer match is
#: pathological input (legitimate frames carry at most a few digits) and is
#: dropped instead of buffering it forever across feeds.
_PENDING_MAX: int = 64

#: Virtual-key codes that arrive with a zero character and must be named
#: directly (the legacy parser has no bytes for them).  Covers navigation,
#: editing and the F-key row; letters/digits/Enter/Tab/Backspace/Escape ride
#: the character path instead.
NAV_VK_NAMES: dict[int, str] = {
    0x21: "pageup",
    0x22: "pagedown",
    0x23: "end",
    0x24: "home",
    0x25: "left",
    0x26: "up",
    0x27: "right",
    0x28: "down",
    0x2D: "insert",
    0x2E: "delete",
    **{0x70 + offset: f"f{offset + 1}" for offset in range(24)},
}


@dataclass(frozen=True, slots=True)
class Win32InputFrame:
    """One decoded win32-input-mode frame (decimal fields per the spec)."""

    vk: int
    scan: int
    char: int
    flags: int
    state: int
    count: int

    @property
    def is_key_down(self) -> bool:
        """Return whether the frame reports a key-down event.

        The fourth field is conhost's ``KEY_EVENT_RECORD.bKeyDown`` (BOOL):
        1 = down, 0 = up.  The live probe captured only downs (``...;1;...``)
        and the first real-input harness run proved the rest: every press
        produced a second, ~50 ms later, chord log line exactly when key-ups
        arrived, so 0 must be treated as up -- treating it as down makes the
        app see every key twice.
        """
        return self.flags == 1

    @property
    def char_text(self) -> str:
        """Return the frame's UCS character as text (``""`` when absent)."""
        return chr(self.char) if self.char else ""


def _decode_frame(fields: str) -> Win32InputFrame:
    """Build a :class:`Win32InputFrame` from the raw semicolon fields.

    Terminals may omit trailing fields; missing or empty fields default to
    zero, matching the "not reported" semantics of the encoding.  Empty
    fields must not raise: a malformed ``;;`` frame (the regex accepts any
    digit/semicolon run) would otherwise kill the input thread via the
    monitor's blanket except.
    """
    parts = fields.split(";")
    parts += ["0"] * (6 - len(parts))
    vk, scan, char, flags, state, count = (
        int(part) if part else 0 for part in parts[:6]
    )
    return Win32InputFrame(vk, scan, char, flags, state, count)


class Win32FrameStream:
    """Incremental decoder turning character text into key frames.

    The driver feeds the characters it read from the console records (after
    the record-level chord branch); the stream returns the frames it
    completed plus the residual text that is not frame material and must
    continue to the legacy VT parser.  A trailing partial frame is buffered
    until the next feed completes it.
    """

    def __init__(self) -> None:
        self._pending = ""

    def feed(self, text: str) -> tuple[list[Win32InputFrame], str]:
        """Consume *text*; return ``(frames, residual)``.

        *residual* is everything that is not (part of) a frame -- the caller
        must feed it to the legacy parser exactly as it would have fed the
        original characters.
        """
        stream = self._pending + text
        self._pending = ""
        frames: list[Win32InputFrame] = []
        parts: list[str] = []
        pos = 0
        for match in _FRAME_RE.finditer(stream):
            parts.append(stream[pos:match.start()])
            frames.append(_decode_frame(match.group(1)))
            pos = match.end()
        parts.append(stream[pos:])
        residual = "".join(parts)
        hold = _HOLD_RE.search(residual)
        if hold is not None:
            if len(hold.group(0)) <= _PENDING_MAX:
                self._pending = hold.group(0)
            # An overlong hold cannot be a legitimate frame prefix (frames
            # carry at most a few digits): drop it instead of buffering it
            # forever across feeds.
            residual = residual[: hold.start()]
        return frames, residual


def frame_to_key_name(frame: Win32InputFrame) -> str | None:
    """Return the canonical Textual key name for *frame*, or ``None``.

    Modifier/lock keys and key-up frames produce ``None``.  Navigation and
    F-keys are named directly (with any modifiers prefixed); ctrl/alt chords
    on nameable keys go through :func:`~yate.keyproto.aliases.chord_to_key_name`
    so they dispatch on exactly the same names the record path delivers.
    Plain keys without ctrl/alt return ``None`` -- they ride the character
    path (:func:`frame_to_char`) to keep one naming pipeline.
    """
    if not frame.is_key_down or frame.vk == 0 or frame.vk in MODIFIER_VKS:
        return None
    ctrl = bool(frame.state & CTRL_BITS)
    alt = bool(frame.state & ALT_BITS)
    shift = bool(frame.state & SHIFT_BIT)
    mods = [name for name, on in (("ctrl", ctrl), ("alt", alt), ("shift", shift)) if on]
    nav = NAV_VK_NAMES.get(frame.vk)
    if nav is not None:
        return "+".join([*mods, nav])
    if ctrl or alt:
        chord = KeyChord(frame.vk, ctrl=ctrl, alt=alt, shift=shift, char=frame.char_text)
        return chord_to_key_name(chord)
    return None


def frame_to_char(frame: Win32InputFrame) -> str:
    """Return the character *frame* contributes to the legacy parser.

    Empty for key-ups, modifier/lock keys and characterless frames; the
    frame's UCS character otherwise (including the C0 bytes the terminal
    puts on ctrl-chords -- the caller ignores them when a key name was
    delivered instead).  Unlike the name path, virtual-key 0 with a real
    character is allowed: that is how IME composition text arrives.
    """
    if not frame.is_key_down or frame.vk in MODIFIER_VKS:
        return ""
    return frame.char_text
