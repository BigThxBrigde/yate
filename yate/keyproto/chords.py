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

#: ``dwControlKeyState`` bits (wincon.h).  CapsLock/NumLock/ScrollLock bits
#: are keyboard state, not modifier inputs, and must not produce chords.
CTRL_BITS = 0x0004 | 0x0008  # RIGHT_CTRL_PRESSED | LEFT_CTRL_PRESSED
ALT_BITS = 0x0001 | 0x0002  # RIGHT_ALT_PRESSED | LEFT_ALT_PRESSED
SHIFT_BIT = 0x0010  # SHIFT_PRESSED

#: Modifier and lock keys themselves never form chords.
MODIFIER_VKS = frozenset(
    [
        0x10, 0x11, 0x12,  # VK_SHIFT, VK_CONTROL, VK_MENU
        0x14,  # VK_CAPITAL
        0x5B, 0x5C,  # VK_LWIN, VK_RWIN
        0x90, 0x91,  # VK_NUMLOCK, VK_SCROLL
        *range(0xA0, 0xA6),  # VK_L/R SHIFT, CONTROL, MENU
    ]
)


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
