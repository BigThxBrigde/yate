"""Key chord model: a virtual-key code plus modifiers, independent of any
terminal byte encoding."""

from __future__ import annotations

from dataclasses import dataclass

#: Win32 virtual-key codes yate can name (US-layout subset; sufficient for
#: every chord the keymaps dispatch on).
VK_SPACE = 0x20
VK_OEM_1 = 0xBA  # ;: on US
VK_OEM_PLUS = 0xBB  # =+ on US
VK_OEM_COMMA = 0xBC  # ,< on US
VK_OEM_MINUS = 0xBD  # -_ on US
VK_OEM_PERIOD = 0xBE  # .> on US
VK_OEM_2 = 0xBF  # /? on US
VK_OEM_3 = 0xC0  # `~ on US
VK_OEM_4 = 0xDB  # [{ on US
VK_OEM_5 = 0xDC  # \| on US
VK_OEM_6 = 0xDD  # ]} on US
VK_OEM_7 = 0xDE  # '" on US


def vk_is_letter(vk: int) -> bool:
    """Return whether *vk* is one of ``VK_A``..``VK_Z`` (``0x41``..``0x5A``)."""
    return 0x41 <= vk <= 0x5A


def vk_is_digit(vk: int) -> bool:
    """Return whether *vk* is one of ``VK_0``..``VK_9`` (``0x30``..``0x39``)."""
    return 0x30 <= vk <= 0x39


@dataclass(frozen=True, slots=True)
class KeyChord:
    """A physical key press: virtual-key code plus modifier state.

    *char* carries the Unicode character the console input record already
    translated (``""`` when the record carries none); it is transport data
    for printable input -- the identity of the chord is (*vk*, modifiers),
    which is exactly what legacy terminal encodings cannot preserve.
    """

    vk: int
    ctrl: bool = False
    alt: bool = False
    shift: bool = False
    char: str = ""
