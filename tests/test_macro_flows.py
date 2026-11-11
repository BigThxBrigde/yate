"""Headless tests for the macro record / replay flow (``MacroFlows``).

Real ``EditorSession`` plus collecting sinks: every raw key dispatched during
a replay lands in ``seen``, every user notice in ``messages``, and the count
prefix comes from a scripted ``counts`` queue.  The state machine contract is
the ``<f6>`` single-prefix chord (``MACRO_PREFIX_KEY``): ``<f6> r {reg}``
records, ``<f6>`` while recording stops, ``<f6> p {reg}`` replays, ``<f6> @``
repeats the last macro.
"""

from __future__ import annotations

from yate.config import YateConfig
from yate.flows.macro_flows import MacroFlows
from yate.keymaps.keys import MACRO_PREFIX_KEY, parse_key
from yate.session import EditorSession

#: The prefix key in raw (dispatch) form -- what pre_dispatch compares.
PREFIX_RAW: str = parse_key(MACRO_PREFIX_KEY)


def _flows(
    session: EditorSession,
    seen: list[str],
    messages: list[str],
    counts: list[int],
) -> MacroFlows:
    """A ``MacroFlows`` wired to collecting sinks (no editor, no mocks)."""
    return MacroFlows(
        session,
        handle_raw_key=lambda raw: (seen.append(raw) or True),
        message=lambda text: messages.append(text),
        count_source=lambda: counts.pop(0) if counts else 1,
    )


def _session() -> EditorSession:
    """A real session with one buffer wired (the headless precedent)."""
    session = EditorSession(YateConfig())
    session.new_buffer()
    return session


def _start_recording(flows: MacroFlows, register: str) -> None:
    """Drive the chord ``<f6> r {register}`` through ``pre_dispatch``."""
    assert flows.pre_dispatch(PREFIX_RAW) is True
    assert flows.pre_dispatch("r") is True
    assert flows.pre_dispatch(register) is True


def test_pre_dispatch_when_record_prefix_then_register_starts_recording() -> None:
    """``<f6>`` then ``r`` then a register walks the chord states.

    Scenario: a fresh session.  Behavior: three ``pre_dispatch`` calls for
    ``<f6>`` / ``r`` / ``a``.  Assertions: all three return ``True``;
    ``macro_awaiting`` moves ``"prefix"`` -> ``"record"`` -> ``None``; the
    session ends in the recording state ``("a", [])``.
    """
    session = _session()
    flows = _flows(session, [], [], [])
    assert flows.pre_dispatch(PREFIX_RAW) is True
    assert session.macro_awaiting == "prefix"
    assert flows.pre_dispatch("r") is True
    assert session.macro_awaiting == "record"
    assert flows.pre_dispatch("a") is True
    assert session.macro_awaiting is None
    assert session.macro_recording == ("a", [])


def test_pre_dispatch_when_record_cancelled_by_non_register_falls_through() -> None:
    """A non-register key after ``<f6> r`` warns and dispatches plainly.

    Scenario: awaiting state is ``"record"``.  Behavior: ``pre_dispatch("?")``.
    Assertions: returns ``False`` (the key continues through the keymap), the
    register-usage notice was emitted, and the awaiting state is cleared.
    """
    session = _session()
    messages: list[str] = []
    flows = _flows(session, [], messages, [])
    assert flows.pre_dispatch(PREFIX_RAW) is True
    assert flows.pre_dispatch("r") is True
    assert session.macro_awaiting == "record"
    assert flows.pre_dispatch("?") is False
    assert messages == ["macro: register name must be a-z or 0-9"]
    assert session.macro_awaiting is None
    assert session.macro_recording is None


def test_pre_dispatch_while_recording_appends_every_raw_key() -> None:
    """Every raw key pressed during a recording joins the sequence.

    Scenario: recording into register ``a``.  Behavior: feed ``"x"``, ``"3"``
    and ``"j"``.  Assertions: each returns ``False`` (dispatched normally)
    and the sequence holds all three keys in order.
    """
    session = _session()
    flows = _flows(session, [], [], [])
    _start_recording(flows, "a")
    assert flows.pre_dispatch("x") is False
    assert flows.pre_dispatch("3") is False
    assert flows.pre_dispatch("j") is False
    assert session.macro_recording == ("a", ["x", "3", "j"])


def test_pre_dispatch_when_record_key_while_recording_stops_and_stores() -> None:
    """``<f6>`` while recording stops and stores the sequence.

    Scenario: recording ``["x", "x"]`` into register ``a``.  Behavior:
    ``pre_dispatch(MACRO_PREFIX_KEY)``.  Assertions: returns ``True``, the
    register is written (overwrite semantics), ``macro_last_register`` is
    ``"a"`` and the recording state is cleared.
    """
    session = _session()
    flows = _flows(session, [], [], [])
    _start_recording(flows, "a")
    flows.pre_dispatch("x")
    flows.pre_dispatch("x")
    assert flows.pre_dispatch(PREFIX_RAW) is True
    assert session.macro_registers == {"a": ["x", "x"]}
    assert session.macro_last_register == "a"
    assert session.macro_recording is None


def test_pre_dispatch_when_play_prefix_then_register_replays() -> None:
    """``<f6> p {reg}`` replays the register through the raw-key sink.

    Scenario: register ``a`` holds ``["x", "x"]``.  Behavior: ``<f6>`` then
    ``p`` then ``a``.  Assertions: all three return ``True``; the raw-key
    sink received exactly ``["x", "x"]``; ``macro_last_register`` is ``"a"``;
    the awaiting state is cleared and no replay is left in flight.
    """
    session = _session()
    seen: list[str] = []
    flows = _flows(session, seen, [], [])
    session.macro_registers = {"a": ["x", "x"]}
    assert flows.pre_dispatch(PREFIX_RAW) is True
    assert flows.pre_dispatch("p") is True
    assert session.macro_awaiting == "play"
    assert flows.pre_dispatch("a") is True
    assert seen == ["x", "x"]
    assert session.macro_last_register == "a"
    assert session.macro_awaiting is None
    assert session.macro_playing is False


def test_pre_dispatch_when_play_prefix_at_repeats_last() -> None:
    """``<f6> @`` repeats the last played-or-recorded macro.

    Scenario: register ``a`` holds ``["x", "y"]`` and ``macro_last_register``
    is ``"a"``.  Behavior: ``<f6>`` then ``@``.  Assertions: both return
    ``True`` and the sink received the full last sequence.
    """
    session = _session()
    seen: list[str] = []
    flows = _flows(session, seen, [], [])
    session.macro_registers = {"a": ["x", "y"]}
    session.macro_last_register = "a"
    assert flows.pre_dispatch(PREFIX_RAW) is True
    assert flows.pre_dispatch("@") is True
    assert seen == ["x", "y"]
    assert session.macro_last_register == "a"


def test_play_when_already_playing_warns_and_is_ignored() -> None:
    """A replay requested while another replay is in flight is rejected.

    Scenario: ``macro_playing`` is already ``True``.  Behavior: ``play("a")``
    with register ``a`` populated.  Assertions: the in-progress notice was
    emitted, the sink received nothing and the flag stays up (AC4).
    """
    session = _session()
    seen: list[str] = []
    messages: list[str] = []
    flows = _flows(session, seen, messages, [])
    session.macro_registers = {"a": ["x"]}
    session.macro_playing = True
    flows.play("a")
    assert messages == ["macro: replay already in progress"]
    assert seen == []
    assert session.macro_playing is True


def test_play_when_register_empty_warns() -> None:
    """Replaying an unrecorded register warns and dispatches nothing.

    Scenario: no register ``a`` was ever recorded.  Behavior: ``play("a")``.
    Assertions: the empty-register notice was emitted and the raw-key sink
    was never called (AC5/AC6).
    """
    session = _session()
    seen: list[str] = []
    messages: list[str] = []
    flows = _flows(session, seen, messages, [])
    flows.play("a")
    assert messages == ["macro: nothing recorded in register a"]
    assert seen == []


def test_play_when_replay_sequence_contains_control_keys_they_dispatch_plainly() -> None:
    """A recorded prefix key replays as a plain key, not as a command.

    Scenario: register ``a`` holds ``[MACRO_PREFIX_KEY, "x"]``.  Behavior:
    ``play("a")``.  Assertions: the sink received the prefix raw key itself,
    the macro state machine did not re-enter (awaiting stays ``None``, no
    recording started) and no replay is left in flight (AC4, no recursion).
    """
    session = _session()
    seen: list[str] = []
    flows = _flows(session, seen, [], [])
    session.macro_registers = {"a": [PREFIX_RAW, "x"]}
    flows.play("a")
    assert seen == [PREFIX_RAW, "x"]
    assert session.macro_awaiting is None
    assert session.macro_recording is None
    assert session.macro_playing is False


def test_play_runs_sequence_count_times() -> None:
    """A count of 3 replays the full sequence three times, in order.

    Scenario: register ``a`` holds ``["x", "y"]``.  Behavior: ``play("a",
    count=3)``.  Assertions: the sink call log is three complete passes of
    the sequence (AC2) and the replay flag is reset afterwards.
    """
    session = _session()
    seen: list[str] = []
    flows = _flows(session, seen, [], [])
    session.macro_registers = {"a": ["x", "y"]}
    flows.play("a", count=3)
    assert seen == ["x", "y", "x", "y", "x", "y"]
    assert session.macro_playing is False


def test_toggle_record_via_command_path_toggles_and_stops() -> None:
    """``toggle_record`` starts and stops a recording (``:macro-record``).

    Scenario: no recording.  Behavior: ``toggle_record("b")``, one raw key,
    then ``toggle_record(None)`` while recording.  Assertions: the first call
    opens the recording state, the second stops it, stores the sequence and
    updates ``macro_last_register``.
    """
    session = _session()
    seen: list[str] = []
    flows = _flows(session, seen, [], [])
    flows.toggle_record("b")
    assert session.macro_recording == ("b", [])
    flows.pre_dispatch("z")
    flows.toggle_record(None)
    assert session.macro_registers == {"b": ["z"]}
    assert session.macro_last_register == "b"
    assert session.macro_recording is None


def test_repeat_last_without_last_warns() -> None:
    """Repeating with no previous macro warns and dispatches nothing.

    Scenario: ``macro_last_register`` is ``None``.  Behavior:
    ``repeat_last()``.  Assertions: the no-previous-macro notice was emitted
    and the raw-key sink was never called.
    """
    session = _session()
    seen: list[str] = []
    messages: list[str] = []
    flows = _flows(session, seen, messages, [])
    flows.repeat_last()
    assert messages == ["macro: no previous macro to repeat"]
    assert seen == []
