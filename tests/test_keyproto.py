"""Tests for the keyproto leaf package: chord model, codecs, chord driver."""

from __future__ import annotations

import sys

import pytest

from yate.keyproto.aliases import chord_to_key_name, chord_to_raw
from yate.keyproto.chords import (
    VK_OEM_2,
    VK_OEM_3,
    VK_OEM_4,
    VK_OEM_6,
    VK_SPACE,
    KeyChord,
    vk_is_digit,
    vk_is_letter,
)
from yate.keyproto.legacy import textual_key_to_raw


def test_vk_helpers_classify_letters_and_digits() -> None:
    assert vk_is_letter(0x41) and vk_is_letter(0x5A)
    assert not vk_is_letter(0x40) and not vk_is_letter(0x5B)
    assert vk_is_digit(0x30) and vk_is_digit(0x39)
    assert not vk_is_digit(0x2F) and not vk_is_digit(0x3A)


def test_chord_to_key_name_covers_phase_b_target_chords() -> None:
    # The chords legacy terminals cannot deliver, named canonically.
    assert chord_to_key_name(KeyChord(0x31, ctrl=True)) == "ctrl+1"
    assert chord_to_key_name(KeyChord(0x45, ctrl=True)) == "ctrl+e"
    assert chord_to_key_name(KeyChord(0x45, ctrl=True, shift=True)) == "ctrl+shift+e"
    assert chord_to_key_name(KeyChord(VK_OEM_3, ctrl=True)) == "ctrl+`"
    assert chord_to_key_name(KeyChord(VK_OEM_2, ctrl=True)) == "ctrl+/"
    assert chord_to_key_name(KeyChord(VK_SPACE, ctrl=True)) == "ctrl+space"
    # plain key with no modifiers
    assert chord_to_key_name(KeyChord(0x41, char="a")) == "a"
    # unknown VK falls back to an explicit, never-empty name
    assert chord_to_key_name(KeyChord(0xFF, ctrl=True)) == "vk:255"


def test_chord_to_raw_matches_legacy_codec_where_representable() -> None:
    assert chord_to_raw(KeyChord(0x45, ctrl=True)) == "\x05"
    assert chord_to_raw(KeyChord(VK_OEM_2, ctrl=True)) == "\x1f"
    assert chord_to_raw(KeyChord(VK_OEM_4, ctrl=True)) == "\x1b"
    assert chord_to_raw(KeyChord(VK_OEM_6, ctrl=True)) == "\x1d"
    assert chord_to_raw(KeyChord(VK_SPACE, ctrl=True)) == "\x00"
    # round-trip against the name codec the keymaps dispatch on
    for name in ("ctrl+e", "ctrl+/", "ctrl+`", "ctrl+space"):
        chord = KeyChord(
            {"ctrl+e": 0x45, "ctrl+/": VK_OEM_2, "ctrl+`": VK_OEM_3, "ctrl+space": VK_SPACE}[name],
            ctrl=True,
        )
        assert textual_key_to_raw(chord_to_key_name(chord)) == chord_to_raw(chord)


def test_chord_to_raw_returns_none_for_physically_unmappable_chords() -> None:
    # These are exactly the Phase B wins: no legacy byte exists.
    assert chord_to_raw(KeyChord(0x31, ctrl=True)) is None
    assert chord_to_raw(KeyChord(0x45, ctrl=True, alt=True)) is None
    assert chord_to_raw(KeyChord(0x45, shift=True)) is None


def test_yate_app_selects_chord_driver_on_windows() -> None:
    from yate.app import YateApp
    from yate.keyproto.driver_windows import YateWindowsDriver

    if sys.platform != "win32":
        pytest.skip("chord driver is Windows-only")
    assert YateApp().get_driver_class() is YateWindowsDriver


def test_record_key_override_builds_phase_b_chords() -> None:
    from yate.keyproto.driver_windows import record_key_override

    # ctrl+1: no legacy byte, now delivered (LEFT_CTRL_PRESSED = 0x0008)
    chord = record_key_override(0x31, 0x0008, "")
    assert chord is not None and chord.ctrl and not chord.shift
    # ctrl+shift+e finally differs from ctrl+e (SHIFT_PRESSED = 0x0010)
    chord = record_key_override(0x45, 0x0008 | 0x0010, "E")
    assert chord is not None and chord.shift and chord.ctrl
    # alt+digit (LEFT_ALT_PRESSED = 0x0002)
    chord = record_key_override(0x32, 0x0002, "")
    assert chord is not None and chord.alt and not chord.ctrl
    # capslock/numlock bits alone must not produce chords (0x0080/0x0020)
    assert record_key_override(0x45, 0x0080, "e") is None
    assert record_key_override(0x45, 0x0020, "e") is None
    # plain typing keeps the legacy char path
    assert record_key_override(0x41, 0, "a") is None
    # modifier keys themselves never chord
    assert record_key_override(0x11, 0x0008, "") is None
    assert record_key_override(0x10, 0x0010, "") is None
    # navigation VKs stay on the legacy path (not in _CHORD_VKS)
    assert record_key_override(0x26, 0x0008, "") is None
    # zero-VK conpty modifier records stay on the stock skip path
    assert record_key_override(0, 0x0008, "") is None
