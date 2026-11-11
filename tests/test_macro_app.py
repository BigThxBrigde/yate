"""Pilot end-to-end tests for macro record / replay (plan e, <f6> protocol).

Full-app headless Textual scenarios (``YateApp`` + ``run_test`` + ``pilot``),
mirroring ``tests/test_app_panes.py``.  Key chords go through the real
dispatch path: ``pilot.press("f6")`` reaches the macro hook at the top of
``_handle_raw_key`` and the ``macro_prefix`` action both keymaps bind.
"""

# tests legitimately poke at internals:
# pyright: reportPrivateUsage=false

from __future__ import annotations

import asyncio
from pathlib import Path

import pyperclip
import pytest

from yate.app import YateApp
from yate.keymaps.keys import MACRO_PREFIX_KEY
from yate.keymaps.vim import VimKeymap
from conftest import message_text


def _status_strip(app: YateApp) -> str:
    """The status bar's rendered text as one plain string."""
    return "".join(seg.text for seg in app.editor.status_bar.render_line(0))


def test_macro_record_then_replay_matches_manual_sequence(tmp_path: Path) -> None:
    """AC1: key-path record -> stop -> replay equals the manual sequence."""

    async def scenario() -> str:
        target = tmp_path / "record.txt"
        target.write_text("seed\n", encoding="utf-8")
        app = YateApp(target=target, keymap="vim")
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            s = app.editor.session
            # <f6> r a arms the recording into register a
            await pilot.press("f6", "r", "a")
            await pilot.pause()
            assert s.macro_recording is not None
            assert s.macro_recording[0] == "a"
            # the editing sequence lands in the register as raw keys
            await pilot.press("x", "i", *"foo", "escape", "j")
            await pilot.pause()
            assert s.macro_recording[1] == ["x", "i", "f", "o", "o", "\x1b", "j"]
            # the prefix key stops the recording (overview sec 2.4 branch 5)
            await pilot.press("f6")
            await pilot.pause()
            assert s.macro_recording is None
            assert s.macro_registers["a"] == ["x", "i", "f", "o", "o", "\x1b", "j"]
            # replay the register on a fresh line below
            await pilot.press("o", "escape")
            await pilot.pause()
            await pilot.press("f6", "p", "a")
            await pilot.pause()
            assert not s.macro_playing
            return s.buffer.get_text()

    recorded = asyncio.run(scenario())

    async def manual() -> str:
        target = tmp_path / "manual.txt"
        target.write_text("seed\n", encoding="utf-8")
        app = YateApp(target=target, keymap="vim")
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            # the identical editing sequence typed by hand, twice
            await pilot.press("x", "i", *"foo", "escape", "j")
            await pilot.pause()
            await pilot.press("o", "escape")
            await pilot.pause()
            await pilot.press("x", "i", *"foo", "escape", "j")
            await pilot.pause()
            return app.editor.session.buffer.get_text()

    assert recorded == asyncio.run(manual())


def test_macro_count_prefix_replays_n_times(tmp_path: Path) -> None:
    """AC2: a vim count prefix replays n times and is then cleared."""

    async def scenario() -> None:
        target = tmp_path / "count.txt"
        target.write_text("abcdef\n", encoding="utf-8")
        app = YateApp(target=target, keymap="vim")
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            s = app.editor.session
            # seed register a = ["x"] through the command path
            app.editor.run_command("macro-record a")
            app.editor.handle_raw_key("x")
            app.editor.run_command("macro-record")
            assert s.macro_registers["a"] == ["x"]
            # a pristine buffer for the counted replay
            s.buffer.set_text("abcdef\n")
            s.buffer.set_cursor((0, 0))
            # 3 <f6> p a: the count is consumed via take_pending_count
            await pilot.press("3", "f6", "p", "a")
            await pilot.pause()
            assert s.buffer.get_text() == "def\n"
            assert not s.macro_playing
            km = app.editor.keymaps.get("vim")
            assert isinstance(km, VimKeymap)
            assert km.count_str == ""  # consumed, not left pending
            # the next x is a single, uncounted edit
            await pilot.press("x")
            await pilot.pause()
            assert s.buffer.get_text() == "ef\n"

    asyncio.run(scenario())


def test_macro_play_when_replay_in_progress_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC4: a self-referential replay cannot recurse; the app survives."""

    # the replayed sequence contains a paste key: pin the OS clipboard so the
    # scenario stays deterministic when the suite runs without xdist
    monkeypatch.setattr(pyperclip, "paste", lambda: "")

    async def scenario() -> None:
        target = tmp_path / "selfref.txt"
        target.write_text("seed\n", encoding="utf-8")
        app = YateApp(target=target, keymap="vim")
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            s = app.editor.session
            # register a replays itself: prefix + play + the same register
            s.macro_registers["a"] = [MACRO_PREFIX_KEY, "p", "a"]
            await pilot.press("f6", "p", "a")
            await pilot.pause()
            # replayed keys dispatch plainly (no macro machine re-entry):
            # the replay finished, nothing nested, the app is alive
            assert app.is_running
            assert not s.macro_playing
            assert s.buffer.get_text() == "seed\n"

    asyncio.run(scenario())


def test_statusbar_shows_recording_indicator_during_record(tmp_path: Path) -> None:
    """AC5: the status bar carries rec @<reg> while recording, gone after."""

    async def scenario() -> None:
        target = tmp_path / "indicator.txt"
        target.write_text("seed\n", encoding="utf-8")
        app = YateApp(target=target, keymap="vim")
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            # recording armed through the key chord
            await pilot.press("f6", "r", "a")
            await pilot.pause()
            assert app.editor.session.macro_recording is not None
            assert "rec @a" in _status_strip(app)
            # stopping through the command path clears the indicator; the
            # bar is pull-model (plan e allows the refresh_status route),
            # so a repaint is triggered before reading the rendered text
            app.editor.run_command("macro-record")
            await pilot.pause()
            app.editor.status_bar.refresh_status()
            assert app.editor.session.macro_recording is None
            assert "rec @a" not in _status_strip(app)

    asyncio.run(scenario())


def test_register_override_and_independent_registers(tmp_path: Path) -> None:
    """AC6: re-recording overwrites a register; other registers stand alone."""

    async def scenario() -> None:
        target = tmp_path / "registers.txt"
        target.write_text("one two\n", encoding="utf-8")
        app = YateApp(target=target, keymap="vim")
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            s = app.editor.session
            # first recording into a: one delete
            await pilot.press("f6", "r", "a")
            await pilot.pause()
            app.editor.handle_raw_key("x")
            app.editor.run_command("macro-record")
            assert s.macro_registers["a"] == ["x"]
            # re-recording over a replaces the sequence
            await pilot.press("f6", "r", "a")
            await pilot.pause()
            app.editor.handle_raw_key("j")
            app.editor.run_command("macro-record")
            assert s.macro_registers["a"] == ["j"]
            # register b is recorded independently
            await pilot.press("f6", "r", "b")
            await pilot.pause()
            app.editor.handle_raw_key("w")
            app.editor.run_command("macro-record")
            assert s.macro_registers == {"a": ["j"], "b": ["w"]}
            # replaying an empty register is refused without side effects
            before = s.buffer.get_text()
            await pilot.press("f6", "p", "z")
            await pilot.pause()
            assert "nothing recorded in register z" in message_text(app)
            assert s.buffer.get_text() == before
            assert app.is_running

    asyncio.run(scenario())


def test_colon_command_entry_matches_key_entry(tmp_path: Path) -> None:
    """AC7: the :macro-* commands and the key chords agree on the buffer."""

    async def scenario() -> str:
        target = tmp_path / "key_entry.txt"
        target.write_text("seed\n", encoding="utf-8")
        app = YateApp(target=target, keymap="vim")
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            s = app.editor.session
            # key entry: record via the chord, stop via the command (the
            # in-recording prefix key is pinned by the AC1 test), replay
            # via the chord
            await pilot.press("f6", "r", "a")
            await pilot.pause()
            app.editor.handle_raw_key("x")
            app.editor.run_command("macro-record")
            assert s.macro_registers["a"] == ["x"]
            s.buffer.set_text("seed\n")  # undo the recorded edit
            s.buffer.set_cursor((0, 0))
            await pilot.press("f6", "p", "a")
            await pilot.pause()
            return s.buffer.get_text()

    key_text = asyncio.run(scenario())

    async def command_entry() -> str:
        target = tmp_path / "cmd_entry.txt"
        target.write_text("seed\n", encoding="utf-8")
        app = YateApp(target=target, keymap="vim")
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            s = app.editor.session
            app.editor.run_command("macro-record a")
            app.editor.handle_raw_key("x")
            app.editor.run_command("macro-record")
            s.buffer.set_text("seed\n")
            s.buffer.set_cursor((0, 0))
            app.editor.run_command("macro-play a")
            return s.buffer.get_text()

    assert key_text == asyncio.run(command_entry())
