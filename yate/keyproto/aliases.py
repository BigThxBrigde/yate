"""Normalize a :class:`~yate.keyproto.chords.KeyChord` to the canonical
Textual key name yate dispatches on."""

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
