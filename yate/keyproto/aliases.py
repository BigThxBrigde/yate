"""Normalize a :class:`~yate.keyproto.chords.KeyChord` to the names and raw
bytes yate dispatches on."""

from __future__ import annotations

from yate.keyproto.chords import (
    VK_OEM_2,
    VK_OEM_3,
    VK_OEM_4,
    VK_OEM_5,
    VK_OEM_6,
    VK_SPACE,
    KeyChord,
    vk_is_digit,
    vk_is_letter,
)

#: OEM virtual-key codes -> the canonical name fragment yate's tables already
#: understand (US layout); ``ctrl+``/``alt+`` prefixes are added by
#: :func:`chord_to_key_name`.  These match Textual's plain-character names
#: (``ctrl+[``), NOT the win32 driver's long names (``ctrl+right_square_bracket``),
#: so a chord delivered as a key event dispatches through the existing tables.
_OEM_NAMES: dict[int, str] = {
    VK_OEM_2: "/",
    VK_OEM_3: "`",
    VK_OEM_4: "[",
    VK_OEM_5: "\\",
    VK_OEM_6: "]",
}

#: ctrl-chord -> C0 byte for the chords legacy terminals can carry (same
#: values as the ctrl+punctuation table in :mod:`yate.keyproto.legacy`).
_OEM_CTRL_RAW: dict[int, int] = {
    VK_OEM_2: 0x1F,
    VK_OEM_3: 0x00,
    VK_OEM_4: 0x1B,
    VK_OEM_5: 0x1C,
    VK_OEM_6: 0x1D,
}


def chord_to_key_name(chord: KeyChord) -> str:
    """Return the Textual-style key name for *chord*.

    Digits and letters derive from the VK value itself (``"ctrl+1"``,
    ``"ctrl+e"``, ``"ctrl+shift+e"``); OEM keys map through
    :data:`_OEM_NAMES` (``"ctrl+`"``, ``"ctrl+/"``); unknown keys fall back to
    ``"vk:<code>"`` so a driver never has to drop an event silently.
    """
    mods = [
        name
        for name, on in (("ctrl", chord.ctrl), ("alt", chord.alt), ("shift", chord.shift))
        if on
    ]
    if vk_is_digit(chord.vk) or vk_is_letter(chord.vk):
        base = chr(chord.vk).lower()
    elif chord.vk in _OEM_NAMES:
        base = _OEM_NAMES[chord.vk]
    elif chord.vk == VK_SPACE:
        base = "space"
    else:
        return f"vk:{chord.vk}"
    prefix = "+".join([*mods, ""]) if mods else ""
    return f"{prefix}{base}"


def chord_to_raw(chord: KeyChord) -> str | None:
    """Return the legacy C0 byte for *chord*, or ``None``.

    ``None`` means no legacy terminal encoding exists for the chord --
    precisely the keys this package exists to deliver (ctrl+digit, and the
    ctrl+shift distinctions legacy bytes collapse).  Ctrl+letter uses the
    ``0x40`` offset arithmetic; ctrl+OEM and ctrl+space reuse the same byte
    values the legacy codec's tables map the textual names to.
    """
    if chord.ctrl and not chord.alt:
        if vk_is_letter(chord.vk):
            return chr(chord.vk - 0x40)
        if chord.vk in _OEM_CTRL_RAW:
            return chr(_OEM_CTRL_RAW[chord.vk])
        if chord.vk == VK_SPACE:
            return "\x00"
    return None
