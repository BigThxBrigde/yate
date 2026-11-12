"""Unit coverage for the L3 macro orchestration flows.

The tests drive a real ``EditorSession`` with recording dispatch / notice
callbacks, so only the sequencing contract is under test (not the real editor
key dispatch, which belongs to the dispatch / integration plans).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

import pytest

from yate.config import YateConfig
from yate.flows import macro_flows
from yate.flows.macro_flows import MacroFlows
from yate.keymaps.keys import MACRO_RECORD_KEY, parse_key
from yate.session import EditorSession, MacroState


@dataclass
class _Recorder:
    """Captures dispatch / notice calls; an optional hook drives reentrancy."""

    calls: list[str] = field(default_factory=list[str])
    notes: list[tuple[str, str]] = field(default_factory=list[tuple[str, str]])
    hook: Callable[[str], None] | None = None

    def dispatch(self, raw: str) -> bool:
        self.calls.append(raw)
        if self.hook is not None:
            self.hook(raw)
        return True

    def notify(self, text: str, kind: str) -> None:
        self.notes.append((text, kind))


@dataclass
class _Harness:
    """Session + flow under test + the shared recorder."""

    session: EditorSession
    flow: MacroFlows
    recorder: _Recorder

    @property
    def macro(self) -> MacroState:
        return self.session.macro


@pytest.fixture
def config() -> YateConfig:
    """A pristine config, matching the wave-1 state tests' construction."""
    return YateConfig()


@pytest.fixture
def harness(config: YateConfig) -> _Harness:
    """A real session with recording dispatch / notify callbacks."""
    session = EditorSession(config)
    recorder = _Recorder()
    flow = MacroFlows(session, recorder.dispatch, recorder.notify)
    return _Harness(session, flow, recorder)


def test_toggle_record_enters_awaiting_then_starts_with_register(
    harness: _Harness,
) -> None:
    harness.flow.toggle_record()
    assert harness.macro.awaiting == "record"
    assert harness.macro.recording is None

    harness.flow.begin_with("a")
    assert harness.macro.recording == "a"
    assert harness.macro.awaiting is None
    assert harness.macro.buffer == []
    assert harness.macro.registers == {}
    assert harness.macro.recording_label() == "rec @a"


def test_toggle_record_while_recording_stops_and_freezes_tuple(
    harness: _Harness,
) -> None:
    harness.macro.recording = "a"
    harness.macro.buffer = ["x", "y"]

    harness.flow.toggle_record()

    assert harness.macro.registers["a"] == ("x", "y")
    assert isinstance(harness.macro.registers["a"], tuple)
    assert harness.macro.recording is None
    assert harness.macro.buffer == []


def test_stop_overwrites_same_register_and_keeps_others(
    harness: _Harness,
) -> None:
    harness.macro.recording = "a"
    harness.macro.buffer = ["x", "y"]
    harness.flow.stop()
    harness.macro.recording = "b"
    harness.macro.buffer = ["p"]
    harness.flow.stop()
    harness.macro.recording = "a"
    harness.macro.buffer = ["z"]
    harness.flow.stop()

    assert harness.macro.registers == {"a": ("z",), "b": ("p",)}


def test_play_repeats_raw_sequence_exact_count(harness: _Harness) -> None:
    harness.macro.registers["a"] = ("x", "y")

    harness.flow.play("a", 3)

    assert harness.recorder.calls == ["x", "y", "x", "y", "x", "y"]
    assert harness.macro.last_played == ("a", 3)
    assert harness.macro.playing is False
    assert harness.macro.play_depth == 0
    assert harness.recorder.notes == []


def test_play_default_count_is_one_via_begin_with_play(harness: _Harness) -> None:
    harness.macro.registers["q"] = ("j",)

    harness.flow.request_play()
    harness.flow.begin_with("q")

    assert harness.recorder.calls == ["j"]
    assert harness.macro.last_played == ("q", 1)
    assert harness.macro.awaiting is None
    assert harness.macro.pending_count == 1


def test_play_empty_register_warns_and_dispatches_nothing(
    harness: _Harness,
) -> None:
    harness.flow.play("a", 1)

    assert harness.recorder.notes == [("macro register @a is empty", "warn")]
    assert harness.recorder.calls == []
    assert harness.macro.playing is False
    assert harness.macro.play_depth == 0
    assert harness.macro.last_played is None


def test_rejects_replay_while_playing_direct(harness: _Harness) -> None:
    harness.macro.registers["a"] = ("x",)

    def reenter(_raw: str) -> None:
        harness.flow.play("a", 1)

    harness.recorder.hook = reenter
    harness.flow.play("a", 1)

    assert harness.recorder.notes == [
        ("macro replay already in progress", "warn")
    ]
    assert harness.recorder.calls == ["x"]
    assert harness.macro.playing is False
    assert harness.macro.play_depth == 0


def test_rejects_indirect_self_recursion_via_replay_last(
    harness: _Harness,
) -> None:
    harness.macro.registers["a"] = ("x",)
    harness.macro.last_played = ("a", 1)

    def reenter(_raw: str) -> None:
        harness.flow.replay_last()

    harness.recorder.hook = reenter
    harness.flow.play("a", 1)

    assert harness.recorder.notes == [
        ("macro replay already in progress", "warn")
    ]
    assert harness.recorder.calls == ["x"]
    assert harness.macro.playing is False
    assert harness.macro.play_depth == 0


def test_replay_last_without_history_warns(harness: _Harness) -> None:
    harness.flow.replay_last()

    assert harness.recorder.notes == [("no last macro replay", "warn")]
    assert harness.recorder.calls == []


def test_replay_last_reuses_last_count(harness: _Harness) -> None:
    harness.macro.registers["a"] = ("x", "y")
    harness.flow.play("a", 2)
    harness.recorder.calls.clear()

    harness.flow.replay_last()

    assert harness.recorder.calls == ["x", "y", "x", "y"]
    assert harness.macro.last_played == ("a", 2)


def test_begin_with_invalid_register_warns_and_clears_awaiting(
    harness: _Harness,
) -> None:
    for reg in ("A", "ab", "!", ""):
        harness.macro.awaiting = "record"
        harness.flow.begin_with(reg)

    assert harness.recorder.notes == [
        ("macro register must be one character in a-z0-9", "warn")
    ] * 4
    assert harness.macro.recording is None
    assert harness.macro.awaiting is None
    assert harness.recorder.calls == []


def test_play_invalid_count_warns_and_dispatches_nothing(
    harness: _Harness,
) -> None:
    harness.macro.registers["a"] = ("x",)

    for bad in (0, -1, macro_flows.MAX_MACRO_KEYS + 1):
        harness.flow.play("a", bad)

    assert harness.recorder.notes == [
        ("macro count must be a positive integer", "warn")
    ] * 3
    assert harness.recorder.calls == []
    assert harness.macro.playing is False
    assert harness.macro.play_depth == 0


def test_record_raw_enforces_sequence_limit(
    harness: _Harness,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(macro_flows, "MAX_MACRO_KEYS", 2)
    harness.macro.recording = "a"

    harness.flow.record_raw("x")
    harness.flow.record_raw("y")
    harness.flow.record_raw("z")

    assert harness.macro.buffer == ["x", "y"]
    assert harness.recorder.notes == [("macro sequence limit reached", "warn")]
    assert harness.macro.playing is False


def test_record_raw_skips_macro_control_keys(harness: _Harness) -> None:
    harness.macro.recording = "a"

    harness.flow.record_raw("x")
    harness.flow.record_raw(parse_key(MACRO_RECORD_KEY))
    harness.flow.record_raw("y")

    assert harness.macro.buffer == ["x", "y"]


def test_play_resets_playing_after_dispatch_raises(harness: _Harness) -> None:
    harness.macro.registers["a"] = ("x",)

    def boom(_raw: str) -> None:
        raise RuntimeError("boom")

    harness.recorder.hook = boom
    with pytest.raises(RuntimeError, match="boom"):
        harness.flow.play("a", 1)

    assert harness.macro.playing is False
    assert harness.macro.play_depth == 0
    assert harness.macro.last_played is None


def test_all_rejection_notifications_use_warn_kind(harness: _Harness) -> None:
    harness.macro.registers["a"] = ("x",)
    harness.flow.play("z", 1)
    harness.flow.play("a", 0)
    harness.macro.playing = True
    harness.flow.play("a", 1)
    harness.macro.playing = False
    harness.flow.replay_last()

    assert len(harness.recorder.notes) == 4
    assert all(kind == "warn" for _, kind in harness.recorder.notes)


def test_request_play_with_count_three_then_begin_with_plays_three(
    harness: _Harness,
) -> None:
    harness.macro.registers["q"] = ("j",)

    harness.flow.request_play(3)
    harness.flow.begin_with("q")

    assert harness.recorder.calls == ["j", "j", "j"]
    assert harness.macro.pending_count == 1
    assert harness.macro.last_played == ("q", 3)
    assert harness.macro.awaiting is None


def test_begin_with_reads_pending_count_directly_and_resets(
    harness: _Harness,
) -> None:
    harness.macro.registers["a"] = ("x", "y")
    harness.macro.pending_count = 3
    harness.macro.awaiting = "play"

    harness.flow.begin_with("a")

    assert harness.recorder.calls == ["x", "y"] * 3
    assert harness.macro.pending_count == 1
    assert harness.macro.last_played == ("a", 3)


def test_replay_last_with_count_three_overrides_last_count(
    harness: _Harness,
) -> None:
    harness.macro.registers["a"] = ("x", "y")
    harness.flow.play("a", 2)
    harness.recorder.calls.clear()

    harness.flow.replay_last(3)

    assert harness.recorder.calls == ["x", "y"] * 3
    assert harness.macro.last_played == ("a", 3)


def test_replay_last_with_count_one_falls_back_to_last_played_count(
    harness: _Harness,
) -> None:
    harness.macro.registers["a"] = ("x", "y")
    harness.flow.play("a", 2)
    harness.recorder.calls.clear()

    harness.flow.replay_last(1)

    assert harness.recorder.calls == ["x", "y", "x", "y"]
    assert harness.macro.last_played == ("a", 2)


def test_play_count_out_of_range_via_pending_count_warns(
    harness: _Harness,
) -> None:
    harness.macro.registers["a"] = ("x",)
    harness.macro.pending_count = macro_flows.MAX_MACRO_KEYS + 1
    harness.macro.awaiting = "play"

    harness.flow.begin_with("a")

    assert harness.recorder.notes == [
        ("macro count must be a positive integer", "warn")
    ]
    assert harness.recorder.calls == []
    assert harness.macro.playing is False
    assert harness.macro.play_depth == 0
    assert harness.macro.pending_count == 1
