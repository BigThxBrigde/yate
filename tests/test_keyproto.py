"""Tests for the keyproto leaf package: chord model, codecs, chord driver."""

from __future__ import annotations

import sys

import pytest

from yate.keyproto.aliases import chord_to_key_name
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
from yate.keyproto.frames import (
    Win32FrameStream,
    Win32InputFrame,
    frame_to_char,
    frame_to_key_name,
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


def test_chord_names_map_to_legacy_bytes_via_name_codec() -> None:
    # Chords a legacy terminal can carry resolve, through the same name
    # codec the keymaps dispatch on, to the C0 bytes the keymap tables
    # expect -- the name is the single source of truth, no parallel
    # raw-byte table exists.
    cases: list[tuple[KeyChord, str]] = [
        (KeyChord(0x45, ctrl=True), "\x05"),
        (KeyChord(VK_OEM_2, ctrl=True), "\x1f"),
        (KeyChord(VK_OEM_4, ctrl=True), "\x1b"),
        (KeyChord(VK_OEM_6, ctrl=True), "\x1d"),
        (KeyChord(VK_SPACE, ctrl=True), "\x00"),
        (KeyChord(VK_OEM_3, ctrl=True), "\x00"),
    ]
    for chord, raw in cases:
        assert textual_key_to_raw(chord_to_key_name(chord)) == raw


def test_physically_unmappable_chords_have_no_legacy_byte() -> None:
    # These are exactly the Phase B wins: no legacy byte exists, so the
    # name codec maps nothing.
    assert textual_key_to_raw(chord_to_key_name(KeyChord(0x31, ctrl=True))) is None
    assert textual_key_to_raw(chord_to_key_name(KeyChord(0x45, ctrl=True, alt=True))) is None
    assert textual_key_to_raw(chord_to_key_name(KeyChord(0x45, shift=True))) is None


def test_yate_app_selects_chord_driver_on_windows() -> None:
    from yate.app import YateApp
    from yate.config import YateConfig
    from yate.keyproto.driver_windows import YateWindowsDriver
    from textual.drivers.windows_driver import WindowsDriver

    if sys.platform != "win32":
        pytest.skip("chord driver is Windows-only")
    assert YateApp().get_driver_class() is YateWindowsDriver
    # yaterc escape hatch: key_protocol = "legacy" restores the stock driver
    legacy = YateApp(config=YateConfig(key_protocol="legacy"))
    assert legacy.get_driver_class() is WindowsDriver


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


# Frames captured by the 2026-09-26 win32-input-mode probe in Windows
# Terminal (d:/Programming/yate-keybinding-fix-wt/.trae/documents/
# keybinding-fix-wt/win32im_probe.py) -- real terminal output, not invented.
_PROBE_FRAMES: dict[str, str] = {
    "down": "\x1b[40;80;0;1;288;1_",
    "a": "\x1b[65;30;97;1;32;1_",
    "ctrl+shift+e": "\x1b[69;18;5;1;56;1_",
    "ctrl+1": "\x1b[49;2;0;1;40;1_",
    "ctrl+space": "\x1b[32;57;32;1;40;1_",
    "ctrl+q": "\x1b[81;16;17;1;40;1_",
}


def _feed(text: str) -> tuple[list[Win32InputFrame], str]:
    stream = Win32FrameStream()
    return stream.feed(text)


def test_frame_stream_decodes_real_probe_frames() -> None:
    frames, residual = _feed("".join(_PROBE_FRAMES.values()))
    assert residual == ""
    by_vk = {frame.vk: frame for frame in frames}
    # down arrow: VK 0x28 = 40, ENHANCED_KEY|NUMLOCK state (0x100|0x20 = 288)
    down = by_vk[40]
    assert (down.scan, down.char, down.flags, down.state) == (80, 0, 1, 288)
    # ctrl+1: VK 0x31 = 49, NUMLOCK|CTRL (0x20|0x8 = 40), no character
    ctrl1 = by_vk[49]
    assert ctrl1.char == 0 and ctrl1.state == 40 and ctrl1.is_key_down
    # every probe frame decodes as a key-down
    assert all(frame.is_key_down for frame in frames)
    # the decimal-field decoder pads missing trailing fields
    short, _ = _feed("\x1b[97_")
    assert short == [Win32InputFrame(97, 0, 0, 0, 0, 0)]


def test_frame_stream_names_chords_and_respects_keyups() -> None:
    frames, _ = _feed(
        _PROBE_FRAMES["ctrl+shift+e"]
        + _PROBE_FRAMES["ctrl+1"]
        + _PROBE_FRAMES["ctrl+space"]
        + "\x1b[69;18;5;0;56;1_"  # same chord, key-up: bKeyDown BOOL 0 = up
    )
    names = [frame_to_key_name(frame) for frame in frames]
    # key-ups never produce events; downs deliver the canonical names
    assert names == ["ctrl+shift+e", "ctrl+1", "ctrl+space", None]
    # plain typing has no key name -- it rides the character path
    plain = _feed(_PROBE_FRAMES["a"])[0][0]
    assert frame_to_key_name(plain) is None
    assert frame_to_char(plain) == "a"
    # key-ups contribute no character either -- otherwise every typed key
    # would reach the app twice (first real-input harness run proved it)
    plain_up = _feed("\x1b[65;30;97;0;32;1_")[0][0]
    assert frame_to_char(plain_up) == ""


def test_frame_stream_names_navigation_keys_with_modifiers() -> None:
    frames, _ = _feed(
        _PROBE_FRAMES["down"]  # VK 40 -> down
        + "\x1b[34;81;0;1;288;1_"  # pagedown + ENHANCED|NUMLOCK
        + "\x1b[34;81;0;1;304;1_"  # shift+pagedown (0x130 = ENH|NUM|SHIFT)
        + "\x1b[38;75;0;1;296;1_"  # ctrl+up (0x128 = ENH|NUM|CTRL)
    )
    names = [frame_to_key_name(frame) for frame in frames]
    assert names == ["down", "pagedown", "shift+pagedown", "ctrl+up"]
    # navigation frames carry no character for the legacy path
    assert all(frame_to_char(frame) == "" for frame in frames)


def test_frame_stream_returns_residual_and_holds_partial_frames() -> None:
    # Non-frame text (including legacy CSI sequences like "\x1b[A") passes
    # through untouched; only frame-shaped text is extracted.
    frames, residual = _feed("abc\x1b[Adef" + _PROBE_FRAMES["ctrl+1"] + "!")
    assert frames and frame_to_key_name(frames[0]) == "ctrl+1"
    assert residual == "abc\x1b[Adef!"
    # A frame split across feeds decodes once the tail arrives
    stream = Win32FrameStream()
    frames, residual = stream.feed("x\x1b[49;2")
    assert frames == [] and residual == "x"
    frames, residual = stream.feed(";0;1;40;1_y")
    assert len(frames) == 1 and frame_to_key_name(frames[0]) == "ctrl+1"
    assert residual == "y"
    # An aborted frame prefix is flushed, never swallowed
    frames, residual = _feed("\x1b[49x")
    assert frames == [] and residual == "\x1b[49x"


def test_frame_stream_skips_modifier_and_lock_keys() -> None:
    # WT frames modifier presses too (VK 0x10 shift, 0x14 capslock with the
    # CAPSLOCK_ON state bit); neither may produce events nor characters.
    frames, _ = _feed(
        "\x1b[16;42;0;1;16;1_"  # VK_SHIFT down, SHIFT state
        + "\x1b[14;58;0;1;128;1_"  # VK_CAPITAL down, CAPSLOCK_ON
        + "\x1b[0;0;233;1;0;1_"  # IME composition char, VK 0
    )
    assert [frame_to_key_name(frame) for frame in frames] == [None, None, None]
    # shift/capslock contribute no character, IME composition text does
    assert frame_to_char(frames[0]) == ""
    assert frame_to_char(frames[1]) == ""
    assert frame_to_char(frames[2]) == chr(233)
