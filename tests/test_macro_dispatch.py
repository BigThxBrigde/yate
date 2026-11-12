"""Unit coverage for the L3 raw-key macro dispatch hooks.

A lightweight editor stub stands in for ``yate.editor.Editor`` so the
dispatch guards are verified without the real ``Editor.macro_flows``
attribute (plan-f wiring is a parallel wave).  A real ``EditorSession``
and a real ``MacroFlows`` keep the sequencing contract honest.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import cast

import pytest

import yate.editor
from conftest import make_key_ui
from yate.config import YateConfig
from yate.editor_core import BufferReadOnlyError
from yate.editor_dispatch import _handle_raw_key
from yate.flows.macro_flows import MAX_MACRO_KEYS, MacroFlows
from yate.keymaps.base import ActionContext, KeyUi
from yate.keymaps.keys import (
    MACRO_PLAY_KEY,
    MACRO_RECORD_KEY,
    MACRO_REPLAY_LAST_KEY,
    parse_key,
)
from yate.session import EditorSession, MacroState


@dataclass
class _ActiveKeymap:
    """Records dispatch calls; can fake a read-only refusal or a macro action."""

    handled: bool = True
    raise_readonly: bool = False
    pending_count: int = 1
    macro_action: Callable[[str], None] | None = None
    handle_calls: list[str] = field(default_factory=list[str])
    take_calls: int = 0

    def handle_key(self, _ctx: ActionContext, raw: str) -> bool:
        self.handle_calls.append(raw)
        if self.macro_action is not None:
            self.macro_action(raw)
        if self.raise_readonly:
            raise BufferReadOnlyError("buffer is read-only")
        return self.handled

    def take_pending_count(self) -> int:
        self.take_calls += 1
        return self.pending_count


@dataclass
class _Completion:
    """Records completion feed calls."""

    calls: list[str] = field(default_factory=list[str])

    def after_editor_key(self, raw: str) -> None:
        self.calls.append(raw)


@dataclass
class _Keymaps:
    """Holds the stub active keymap."""

    active: _ActiveKeymap = field(default_factory=_ActiveKeymap)


class _EditorStub:
    """Minimal editor surface consumed by ``_handle_raw_key``."""

    def __init__(self, session: EditorSession) -> None:
        self.session: EditorSession = session
        self.key_ui: KeyUi = make_key_ui()
        self.keymaps: _Keymaps = _Keymaps()
        self.completion: _Completion = _Completion()
        self.messages: list[tuple[str, str]] = []
        self.refresh_calls: int = 0
        self.readonly_calls: int = 0
        self.raw_calls: list[str] = []
        self.macro_flows: MacroFlows = MacroFlows(
            session, self.handle_raw_key, self.message
        )

    def message(self, text: str, kind: str = "info") -> None:
        self.messages.append((text, kind))

    def refresh_ui(self) -> None:
        self.refresh_calls += 1

    def readonly_notice(self) -> None:
        self.readonly_calls += 1

    def handle_raw_key(self, raw: str) -> bool:
        self.raw_calls.append(raw)
        return True


@dataclass
class _Harness:
    """The stub, its cast Editor view, and the shared session macro state."""

    stub: _EditorStub
    ed: yate.editor.Editor

    @property
    def macro(self) -> MacroState:
        return self.stub.session.macro


@pytest.fixture
def h() -> _Harness:
    """A fresh stub editor with a real session and real MacroFlows."""
    session = EditorSession(YateConfig())
    stub = _EditorStub(session)
    return _Harness(stub, cast("yate.editor.Editor", stub))


def _arm_macro_actions(h: _Harness) -> None:
    """Mimic plan-h control-key action bodies on the keymap stub.

    Dispatch itself never sets ``awaiting`` (that is an action job), so the
    ``3<play>`` / out-of-range closed-loop cases wire a minimal stand-in.
    """

    def on_key(raw: str) -> None:
        if raw == parse_key(MACRO_PLAY_KEY):
            h.stub.macro_flows.request_play(h.stub.session.macro.pending_count)
        elif raw == parse_key(MACRO_REPLAY_LAST_KEY):
            h.stub.macro_flows.replay_last(h.stub.session.macro.pending_count)

    h.stub.keymaps.active.macro_action = on_key


def test_handle_raw_key_records_every_raw_while_recording(h: _Harness) -> None:
    h.macro.recording = "a"

    for raw in ("x", "y", "\x1b"):
        assert _handle_raw_key(h.ed, raw) is True

    assert h.macro.buffer == ["x", "y", "\x1b"]
    assert h.stub.keymaps.active.handle_calls == ["x", "y", "\x1b"]
    assert h.stub.refresh_calls == 3


def test_handle_raw_key_excludes_macro_control_keys_from_recording(
    h: _Harness,
) -> None:
    h.macro.recording = "a"

    for key in (MACRO_RECORD_KEY, MACRO_PLAY_KEY, MACRO_REPLAY_LAST_KEY):
        assert _handle_raw_key(h.ed, parse_key(key)) is True

    assert h.macro.buffer == []
    assert len(h.stub.keymaps.active.handle_calls) == 3


def test_handle_raw_key_consumes_awaiting_register_without_dispatch(
    h: _Harness,
) -> None:
    h.macro.awaiting = "record"

    assert _handle_raw_key(h.ed, "a") is True

    assert h.macro.recording == "a"
    assert h.macro.awaiting is None
    assert h.macro.buffer == []
    assert h.stub.keymaps.active.handle_calls == []
    assert h.stub.completion.calls == []


def test_handle_raw_key_invalid_awaiting_char_warns_and_cancels(
    h: _Harness,
) -> None:
    for raw in ("!", "A", "ab", "\x1b"):
        h.macro.awaiting = "play"
        assert _handle_raw_key(h.ed, raw) is True

    assert h.stub.messages == [
        ("macro register must be one character in a-z0-9", "warn")
    ] * 4
    assert h.macro.awaiting is None
    assert h.macro.recording is None
    assert h.stub.keymaps.active.handle_calls == []


def test_handle_raw_key_rejects_macro_key_while_playing(h: _Harness) -> None:
    h.macro.playing = True

    assert _handle_raw_key(h.ed, parse_key(MACRO_PLAY_KEY)) is True

    assert h.stub.messages == [
        ("macro replay already in progress", "warn")
    ]
    assert h.stub.keymaps.active.handle_calls == []
    assert h.stub.refresh_calls == 0
    assert h.stub.completion.calls == []


def test_handle_raw_key_not_playing_macro_key_dispatches_normally(
    h: _Harness,
) -> None:
    assert _handle_raw_key(h.ed, parse_key(MACRO_RECORD_KEY)) is True

    assert h.stub.keymaps.active.handle_calls == [parse_key(MACRO_RECORD_KEY)]
    assert not any(kind == "warn" for _, kind in h.stub.messages)


def test_handle_raw_key_dispatches_each_raw_once(h: _Harness) -> None:
    assert _handle_raw_key(h.ed, "x") is True

    assert h.stub.keymaps.active.handle_calls == ["x"]
    assert h.stub.completion.calls == ["x"]
    assert h.stub.refresh_calls == 1


def test_handle_raw_key_unhandled_key_skips_refresh_but_feeds_completion(
    h: _Harness,
) -> None:
    h.stub.keymaps.active.handled = False

    assert _handle_raw_key(h.ed, "q") is False

    assert h.stub.refresh_calls == 0
    assert h.stub.completion.calls == ["q"]
    assert h.macro.buffer == []


def test_handle_raw_key_readonly_refusal_consumes_key_and_skips_recording(
    h: _Harness,
) -> None:
    h.macro.recording = "a"
    h.stub.keymaps.active.raise_readonly = True

    assert _handle_raw_key(h.ed, "z") is True

    assert h.stub.readonly_calls == 1
    assert h.macro.buffer == []


def test_handle_raw_key_play_via_begin_with_dispatches_sequence(
    h: _Harness,
) -> None:
    h.macro.awaiting = "play"
    h.macro.registers["a"] = ("x", "y")

    assert _handle_raw_key(h.ed, "a") is True

    assert h.stub.raw_calls == ["x", "y"]
    assert h.macro.playing is False
    assert h.macro.play_depth == 0
    assert h.macro.last_played == ("a", 1)
    assert h.macro.awaiting is None


def test_handle_raw_key_awaiting_char_is_not_recorded_when_recording(
    h: _Harness,
) -> None:
    h.macro.recording = "a"
    h.macro.awaiting = "play"

    assert _handle_raw_key(h.ed, "b") is True

    assert h.macro.buffer == []
    assert h.stub.keymaps.active.handle_calls == []
    assert h.macro.recording == "a"


def test_handle_raw_key_captures_count_three_for_macro_play_key(
    h: _Harness,
) -> None:
    h.stub.keymaps.active.pending_count = 3

    assert _handle_raw_key(h.ed, parse_key(MACRO_PLAY_KEY)) is True

    assert h.stub.keymaps.active.take_calls == 1
    assert h.macro.pending_count == 3
    assert h.stub.keymaps.active.handle_calls == [parse_key(MACRO_PLAY_KEY)]


def test_handle_raw_key_captures_count_three_for_replay_last_key(
    h: _Harness,
) -> None:
    h.stub.keymaps.active.pending_count = 3

    assert _handle_raw_key(h.ed, parse_key(MACRO_REPLAY_LAST_KEY)) is True

    assert h.stub.keymaps.active.take_calls == 1
    assert h.macro.pending_count == 3
    assert len(h.stub.keymaps.active.handle_calls) == 1


def test_handle_raw_key_macro_record_key_does_not_consume_count(
    h: _Harness,
) -> None:
    assert _handle_raw_key(h.ed, parse_key(MACRO_RECORD_KEY)) is True

    assert h.stub.keymaps.active.take_calls == 0
    assert h.macro.pending_count == 1
    assert h.stub.keymaps.active.handle_calls == [parse_key(MACRO_RECORD_KEY)]


def test_handle_raw_key_vsc_take_pending_count_is_one(h: _Harness) -> None:
    assert _handle_raw_key(h.ed, parse_key(MACRO_PLAY_KEY)) is True

    assert h.macro.pending_count == 1
    assert h.stub.keymaps.active.take_calls == 1


def test_handle_raw_key_three_play_then_register_plays_three_times(
    h: _Harness,
) -> None:
    h.macro.registers["a"] = ("x", "y")
    h.stub.keymaps.active.pending_count = 3
    _arm_macro_actions(h)

    assert _handle_raw_key(h.ed, parse_key(MACRO_PLAY_KEY)) is True
    assert _handle_raw_key(h.ed, "a") is True

    assert h.stub.raw_calls == ["x", "y"] * 3
    assert h.macro.pending_count == 1
    assert h.macro.last_played == ("a", 3)
    assert h.macro.playing is False
    assert h.macro.play_depth == 0


def test_handle_raw_key_count_out_of_range_warns_and_dispatches_nothing(
    h: _Harness,
) -> None:
    h.stub.keymaps.active.pending_count = MAX_MACRO_KEYS + 1
    h.macro.registers["a"] = ("x",)
    _arm_macro_actions(h)

    assert _handle_raw_key(h.ed, parse_key(MACRO_PLAY_KEY)) is True
    assert _handle_raw_key(h.ed, "a") is True

    assert h.stub.messages == [
        ("macro count must be a positive integer", "warn")
    ]
    assert h.stub.raw_calls == []
    assert h.macro.playing is False
    assert h.macro.play_depth == 0
