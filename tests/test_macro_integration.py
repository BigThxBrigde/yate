"""End-to-end macro recording / replay coverage (AC1-AC7, wave-5 plan-k).

Every case drives a real Textual pilot against a fresh YateApp; assertions
land on concrete buffer lines / cursor positions, macro state fields and the
(text, kind) pairs written to the prompt bar. No case presses the reserved
function key behind the F18 smoke prerequisite.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path

import pytest
from textual.pilot import Pilot

from conftest import wait_until
from yate.app import YateApp
from yate.editor_components.commandline import OWNER_APP
from yate.flows.macro_flows import MAX_MACRO_KEYS, MacroFlows
from yate.keymaps.keys import (
    MACRO_PLAY_KEY,
    MACRO_RECORD_KEY,
    MACRO_REPLAY_LAST_KEY,
    parse_key,
)

_RECORD = "f10"
_PLAY = "f11"
_REPLAY_LAST = "f12"
_COMMAND = "f5"
_TOGGLE_KEYMAP = "ctrl+/"
_ESC = "escape"
_USAGE = (
    "usage: :macro-record [reg] | :macro-stop | "
    ":macro-play <reg> [count] | :macro-replay-last [count]"
)
_REPLAY_BUSY = "macro replay already in progress"


def _app(tmp_path: Path, name: str) -> YateApp:
    """A fresh app whose startup buffer is a single empty line."""
    return YateApp(target=tmp_path / name)


def _snapshot(app: YateApp) -> tuple[list[str], tuple[int, int]]:
    """The exact buffer lines and (row, col) cursor of *app*."""
    buffer = app.editor.session.buffer
    return list(buffer.lines), (buffer.cursor[0], buffer.cursor[1])


async def _press(pilot: Pilot[None], *keys: str) -> None:
    """Press *keys* in order, then let the app settle."""
    for key in keys:
        await pilot.press(key)
    await pilot.pause()


async def _command(pilot: Pilot[None], app: YateApp, text: str) -> None:
    """Submit *text* on the ex command line (F5 in both keymaps)."""
    bar = app.editor.prompt_bar
    assert bar is not None
    await pilot.press(_COMMAND)
    assert await wait_until(pilot, lambda: bar.active_mode == "command")
    assert await wait_until(pilot, lambda: app.focused is bar.input)
    keys = ["space" if ch == " " else ch for ch in text]
    await pilot.press(*keys)
    assert await wait_until(pilot, lambda: bar.input.value == text)
    await pilot.press("enter")
    await pilot.pause()
    await pilot.pause()
    assert await wait_until(pilot, lambda: bar.active_mode is None)


def _capture_messages(
    app: YateApp, monkeypatch: pytest.MonkeyPatch,
) -> list[tuple[str, str]]:
    """Record every (text, kind) written to the prompt bar message line."""
    records: list[tuple[str, str]] = []
    bar = app.editor.prompt_bar
    assert bar is not None
    original = bar.write

    def write(text: str, kind: str = "info", owner: str = OWNER_APP) -> None:
        records.append((text, kind))
        original(text, kind=kind, owner=owner)

    monkeypatch.setattr(bar, "write", write)
    return records


async def _record(pilot: Pilot[None], reg: str, *sequence: str) -> None:
    """Record *sequence* into *reg* with the key entry and stop with f10."""
    await _press(pilot, _RECORD, reg, *sequence, _RECORD)


def _arm_reentry(
    app: YateApp, trigger: Callable[[], object],
) -> dict[str, bool]:
    """Rebuild MacroFlows so *trigger* fires once while a replay is in flight."""
    state: dict[str, bool] = {"armed": True}
    original = app.editor.handle_raw_key

    def dispatch(raw: str) -> bool:
        result = original(raw)
        if state["armed"] and app.editor.session.macro.playing:
            state["armed"] = False
            trigger()
        return result

    app.editor.macro_flows = MacroFlows(
        app.editor.session, dispatch, app.editor.message
    )
    return state


def test_macro_record_stop_play_matches_manual_sequence(tmp_path: Path) -> None:
    """AC1: a replay reproduces the buffer of a manual run of the same keys."""

    async def scenario() -> None:
        replay = _app(tmp_path, "ac1_replay.txt")
        manual = _app(tmp_path, "ac1_manual.txt")
        async with replay.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            await _press(pilot, _TOGGLE_KEYMAP)
            assert replay.editor.keymaps.name == "vim"
            await _record(pilot, "a", "i", "x", "y", _ESC)
            macro = replay.editor.session.macro
            assert macro.registers["a"] == ("i", "x", "y", "\x1b")
            assert macro.recording is None
            # A clean slate makes the replay the only effect left in A.
            await _command(pilot, replay, "enew")
            assert _snapshot(replay) == ([""], (0, 0))
            await _press(pilot, _PLAY, "a")
            assert _snapshot(replay)[0] == ["xy"]
            assert macro.last_played == ("a", 1)
        async with manual.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            await _press(pilot, _TOGGLE_KEYMAP)
            assert manual.editor.keymaps.name == "vim"
            await _press(pilot, "i", "x", "y", _ESC)
        assert _snapshot(replay) == _snapshot(manual)
        assert _snapshot(manual)[0] == ["xy"]

    asyncio.run(scenario())


def test_macro_play_three_times_is_exact(tmp_path: Path) -> None:
    """AC2: :macro-play a 3 replays the register exactly three times."""
    app = _app(tmp_path, "ac2_cmd3.txt")

    async def scenario() -> None:
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            await _record(pilot, "a", "x")
            assert _snapshot(app) == (["x"], (0, 1))
            await _command(pilot, app, "macro-play a 3")
            macro = app.editor.session.macro
            assert _snapshot(app) == (["xxxx"], (0, 4))
            assert macro.registers["a"] == ("x",)
            assert macro.last_played == ("a", 3)
            assert macro.playing is False
            assert macro.play_depth == 0
            assert macro.pending_count == 1

    asyncio.run(scenario())


def test_macro_play_defaults_to_once(tmp_path: Path) -> None:
    """AC2: a bare play key replays the register exactly once."""
    app = _app(tmp_path, "ac2_once.txt")

    async def scenario() -> None:
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            await _record(pilot, "a", "x")
            await _press(pilot, _PLAY, "a")
            macro = app.editor.session.macro
            assert _snapshot(app) == (["xx"], (0, 2))
            assert macro.last_played == ("a", 1)
            assert macro.playing is False
            assert macro.play_depth == 0

    asyncio.run(scenario())


def test_macro_replay_last_repeats_previous_count(tmp_path: Path) -> None:
    """AC2: f12 without a prefix repeats the previous replay count."""
    app = _app(tmp_path, "ac2_last.txt")

    async def scenario() -> None:
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            await _record(pilot, "a", "x")
            await _command(pilot, app, "macro-play a 2")
            macro = app.editor.session.macro
            assert _snapshot(app) == (["xxx"], (0, 3))
            assert macro.last_played == ("a", 2)
            await _press(pilot, _REPLAY_LAST)
            assert _snapshot(app) == (["xxxxx"], (0, 5))
            assert macro.last_played == ("a", 2)
            assert macro.playing is False
            assert macro.play_depth == 0

    asyncio.run(scenario())


def test_macro_replay_last_with_count_override(tmp_path: Path) -> None:
    """AC2: :macro-replay-last 3 overrides the previous replay count."""
    app = _app(tmp_path, "ac2_override.txt")

    async def scenario() -> None:
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            await _record(pilot, "a", "x")
            await _command(pilot, app, "macro-play a 2")
            assert _snapshot(app) == (["xxx"], (0, 3))
            await _command(pilot, app, "macro-replay-last 3")
            macro = app.editor.session.macro
            assert _snapshot(app) == (["xxxxxx"], (0, 6))
            assert macro.last_played == ("a", 3)
            assert macro.playing is False
            assert macro.play_depth == 0

    asyncio.run(scenario())


def test_macro_keys_resolve_to_same_actions_in_vim_and_vsc(
    tmp_path: Path,
) -> None:
    """AC3: both keymaps bind the same raw keys to the same action names."""

    async def scenario() -> None:
        probe = _app(tmp_path, "ac3_probe.txt")
        async with probe.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            keymaps = probe.editor.keymaps
            expected = (
                (MACRO_RECORD_KEY, "macro_record"),
                (MACRO_PLAY_KEY, "macro_play"),
                (MACRO_REPLAY_LAST_KEY, "macro_replay_last"),
            )
            for name in ("vim", "vsc"):
                km = keymaps.get(name)
                assert km is not None
                for key, action in expected:
                    binding = km.lookup(parse_key(key))
                    assert binding is not None
                    assert binding.action == action
        for name in ("vsc", "vim"):
            app = _app(tmp_path, f"ac3_{name}.txt")
            async with app.run_test(size=(100, 30)) as pilot:
                await pilot.pause()
                if name == "vim":
                    await _press(pilot, _TOGGLE_KEYMAP)
                assert app.editor.keymaps.name == name
                await _press(pilot, _RECORD)
                macro = app.editor.session.macro
                assert macro.awaiting == "record"
                assert macro.recording is None

    asyncio.run(scenario())


def test_macro_replay_during_replay_is_rejected_with_visible_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC4: a macro key fired mid-replay is refused by dispatch with a warn."""
    app = _app(tmp_path, "ac4.txt")

    async def scenario() -> None:
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            records = _capture_messages(app, monkeypatch)
            await _record(pilot, "a", "x")
            state = _arm_reentry(
                app,
                lambda: app.editor.handle_raw_key(parse_key(MACRO_PLAY_KEY)),
            )
            await _press(pilot, _PLAY, "a")
            macro = app.editor.session.macro
            assert state["armed"] is False
            assert sum(
                1 for text, kind in records
                if text == _REPLAY_BUSY and kind == "warn"
            ) == 1
            assert _snapshot(app) == (["xx"], (0, 2))
            assert macro.last_played == ("a", 1)
            assert macro.playing is False
            assert macro.play_depth == 0

    asyncio.run(scenario())


def test_macro_statusbar_indicator_shows_then_clears(tmp_path: Path) -> None:
    """AC5: rec @a appears while recording and disappears after stop."""
    app = _app(tmp_path, "ac5_bar.txt")

    async def scenario() -> None:
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            bar = app.editor.status_bar
            macro = app.editor.session.macro
            await _press(pilot, _RECORD, "a")
            bar.refresh_status()
            shown = str(bar.render())
            assert macro.recording_label() == "rec @a"
            assert macro.recording == "a"
            assert "rec @a" in shown
            await _press(pilot, _RECORD)
            bar.refresh_status()
            hidden = str(bar.render())
            assert macro.recording_label() is None
            assert macro.recording is None
            assert "rec @" not in hidden
            assert shown != hidden
            assert macro.registers["a"] == ()

    asyncio.run(scenario())


def test_macro_empty_register_warns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC5: replaying an unrecorded register warns and changes nothing."""
    app = _app(tmp_path, "ac5_empty.txt")

    async def scenario() -> None:
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            records = _capture_messages(app, monkeypatch)
            before = _snapshot(app)
            await _press(pilot, _PLAY, "z")
            assert ("macro register @z is empty", "warn") in records
            assert _snapshot(app) == before
            macro = app.editor.session.macro
            assert macro.playing is False
            assert macro.play_depth == 0
            assert macro.registers == {}
            assert macro.last_played is None

    asyncio.run(scenario())


def test_macro_same_register_overwrite_and_other_register_untouched(
    tmp_path: Path,
) -> None:
    """AC6: rerecording a overwrites it; b is untouched; D10: f10 stops."""
    app = _app(tmp_path, "ac6.txt")

    async def scenario() -> None:
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            macro = app.editor.session.macro
            await _record(pilot, "a", "x")           # S1
            await _record(pilot, "b", "y", "y")      # S2
            await _record(pilot, "a", "z")           # S3 (overwrite)
            assert macro.registers["a"] == ("z",)
            assert macro.registers["b"] == ("y", "y")
            assert _snapshot(app) == (["xyyz"], (0, 4))
            await _press(pilot, _PLAY, "a")
            assert _snapshot(app) == (["xyyzz"], (0, 5))
            # D10: toggling the record switch while recording stops it and
            # freezes the just-recorded register; a/b stay untouched.
            await _press(pilot, _RECORD, "c", "p", "q")
            assert macro.recording == "c"
            assert macro.buffer == ["p", "q"]
            assert macro.registers.get("c") is None
            await _press(pilot, _RECORD)
            assert macro.recording is None
            assert macro.awaiting is None
            assert macro.buffer == []
            frozen = macro.registers["c"]
            assert frozen == ("p", "q")
            await _press(pilot, "w")
            assert macro.registers["c"] == frozen
            assert macro.buffer == []
            assert macro.registers["a"] == ("z",)
            assert macro.registers["b"] == ("y", "y")

    asyncio.run(scenario())


def test_macro_command_and_key_entries_agree(tmp_path: Path) -> None:
    """AC7: :macro-record / :macro-play agree with the key entries."""
    key_app = _app(tmp_path, "ac7_keys.txt")
    cmd_app = _app(tmp_path, "ac7_cmds.txt")

    async def scenario() -> None:
        async with key_app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            await _press(pilot, _RECORD, "a", "x", "y", _RECORD)
            key_regs = dict(key_app.editor.session.macro.registers)
            await _press(pilot, _PLAY, "a")
            key_snapshot = _snapshot(key_app)
            key_last = key_app.editor.session.macro.last_played
        async with cmd_app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            await _command(pilot, cmd_app, "macro-record a")
            assert cmd_app.editor.session.macro.recording == "a"
            await _press(pilot, "x", "y")
            await _press(pilot, _RECORD)
            cmd_regs = dict(cmd_app.editor.session.macro.registers)
            await _command(pilot, cmd_app, "macro-play a")
            cmd_snapshot = _snapshot(cmd_app)
            cmd_last = cmd_app.editor.session.macro.last_played
        assert key_regs == {"a": ("x", "y")}
        assert key_regs == cmd_regs
        assert key_snapshot == cmd_snapshot == (["xyxy"], (0, 4))
        assert key_last == cmd_last == ("a", 1)

    asyncio.run(scenario())


def test_macro_invalid_register_and_syntax_warn(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC7: invalid register / syntax / count each produce a warn notice."""
    app = _app(tmp_path, "ac7_invalid.txt")

    async def scenario() -> None:
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            records = _capture_messages(app, monkeypatch)
            await _record(pilot, "a", "x")
            await _command(pilot, app, "macro-play a")
            assert app.editor.session.macro.last_played == ("a", 1)
            records.clear()
            before = _snapshot(app)
            await _command(pilot, app, "macro-play Z")
            await _command(pilot, app, "macro-play")
            await _command(pilot, app, "macro-record a b")
            await _command(pilot, app, "macro-replay-last abc")
            warns = [text for text, kind in records if kind == "warn"]
            assert warns == [
                "macro register must be one character in a-z0-9",
                _USAGE,
                _USAGE,
                "macro count must be a positive integer",
            ]
            assert _snapshot(app) == before
            macro = app.editor.session.macro
            assert macro.playing is False
            assert macro.play_depth == 0

    asyncio.run(scenario())


def test_macro_rejects_nested_recording(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """N4/AC4: a record switch fired mid-replay is refused; no nesting."""
    app = _app(tmp_path, "n4.txt")

    async def scenario() -> None:
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            records = _capture_messages(app, monkeypatch)
            await _record(pilot, "a", "x")
            state = _arm_reentry(
                app, lambda: app.editor.execute_action("macro_record")
            )
            await _press(pilot, _PLAY, "a")
            macro = app.editor.session.macro
            assert state["armed"] is False
            assert (_REPLAY_BUSY, "warn") in records
            assert macro.recording is None
            assert macro.awaiting is None
            assert macro.playing is False
            assert macro.play_depth == 0
            assert macro.last_played == ("a", 1)
            assert macro.registers == {"a": ("x",)}
            assert _snapshot(app) == (["xx"], (0, 2))

    asyncio.run(scenario())


def test_macro_key_prefix_three_play_is_exact(tmp_path: Path) -> None:
    """AC2: 3<f11> replays exactly three times through the key entry."""
    app = _app(tmp_path, "ac2_key3.txt")

    async def scenario() -> None:
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            await _press(pilot, _TOGGLE_KEYMAP)
            assert app.editor.keymaps.name == "vim"
            await _record(pilot, "a", "i", "x", _ESC)
            macro = app.editor.session.macro
            assert macro.registers["a"] == ("i", "x", "\x1b")
            assert _snapshot(app) == (["x"], (0, 0))
            await _press(pilot, "3", _PLAY, "a")
            assert _snapshot(app) == (["xxxx"], (0, 0))
            assert macro.last_played == ("a", 3)
            assert macro.playing is False
            assert macro.play_depth == 0
            assert macro.pending_count == 1

    asyncio.run(scenario())


def test_macro_key_prefix_three_replay_last_is_exact(tmp_path: Path) -> None:
    """AC2: 3<f12> overrides the previous count with exactly three replays."""
    app = _app(tmp_path, "ac2_key_last3.txt")

    async def scenario() -> None:
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            await _press(pilot, _TOGGLE_KEYMAP)
            assert app.editor.keymaps.name == "vim"
            await _record(pilot, "a", "i", "x", _ESC)
            await _command(pilot, app, "macro-play a 2")
            macro = app.editor.session.macro
            assert _snapshot(app) == (["xxx"], (0, 0))
            assert macro.last_played == ("a", 2)
            await _press(pilot, "3", _REPLAY_LAST)
            assert _snapshot(app) == (["xxxxxx"], (0, 0))
            assert macro.last_played == ("a", 3)
            assert macro.playing is False
            assert macro.play_depth == 0

    asyncio.run(scenario())


def test_macro_vsc_keymap_has_no_count_state_and_plays_once(
    tmp_path: Path,
) -> None:
    """AC2: vsc has no count state; play and replay-last both fire once."""
    app = _app(tmp_path, "ac2_vsc.txt")

    async def scenario() -> None:
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            assert app.editor.keymaps.name == "vsc"
            assert app.editor.keymaps.active.take_pending_count() == 1
            await _record(pilot, "a", "x")
            macro = app.editor.session.macro
            await _press(pilot, _PLAY, "a")
            assert _snapshot(app) == (["xx"], (0, 2))
            assert macro.last_played == ("a", 1)
            await _press(pilot, _REPLAY_LAST)
            assert _snapshot(app) == (["xxx"], (0, 3))
            assert macro.last_played == ("a", 1)
            assert macro.playing is False
            assert macro.play_depth == 0

    asyncio.run(scenario())


def test_macro_key_prefix_count_out_of_range_warns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC2: a count above MAX_MACRO_KEYS warns and dispatches nothing."""
    app = _app(tmp_path, "ac2_range.txt")

    async def scenario() -> None:
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            records = _capture_messages(app, monkeypatch)
            await _press(pilot, _TOGGLE_KEYMAP)
            assert app.editor.keymaps.name == "vim"
            await _record(pilot, "a", "i", "x", _ESC)
            before = _snapshot(app)
            overflow = str(MAX_MACRO_KEYS + 1)
            await _press(pilot, *overflow, _PLAY, "a")
            macro = app.editor.session.macro
            assert ("macro count must be a positive integer", "warn") in records
            assert _snapshot(app) == before
            assert macro.playing is False
            assert macro.play_depth == 0
            assert macro.pending_count == 1

    asyncio.run(scenario())
