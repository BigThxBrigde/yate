"""Coverage for the macro action / ``:`` command entry points (AC7).

Both built-in tables are wired against a minimal editor stand-in that owns a
real ``EditorSession`` plus a real ``MacroFlows``; only the entry-point
behaviour is under test (the orchestration itself is pinned by
``test_macro_flows.py``).  Key actions and ``:`` commands must agree, including
the count-prefix path (AC2 / AC7).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

import pytest

from yate.actions import populate
from yate.commands import register_commands
from yate.config import YateConfig
from yate.editor import Editor
from yate.flows.macro_flows import MacroFlows
from yate.keymaps.base import ActionContext
from yate.registries import ActionRegistry, CommandRegistry
from yate.session import EditorSession, MacroState

from conftest import make_key_ui

_USAGE = (
    "usage: :macro-record [reg] | :macro-stop | "
    ":macro-play <reg> [count] | :macro-replay-last [count]"
)


class _FakeEditor:
    """Minimal editor stand-in: real session/flows, recorded notices."""

    def __init__(self) -> None:
        self.session = EditorSession(YateConfig())
        self.notes: list[tuple[str, str]] = []
        self.dispatched: list[str] = []
        self.macro_flows = MacroFlows(self.session, self._dispatch, self.message)

    def message(self, text: str, kind: str = "info") -> None:
        """Record a user-facing notice as a ``(text, kind)`` pair."""
        self.notes.append((text, kind))

    def _dispatch(self, raw: str) -> bool:
        """Record one replayed raw key."""
        self.dispatched.append(raw)
        return True

    @property
    def macro(self) -> MacroState:
        """Shortcut to the session macro state."""
        return self.session.macro


@dataclass
class _Env:
    """One isolated editor with its action / command registries."""

    editor: _FakeEditor
    actions: ActionRegistry
    commands: CommandRegistry
    ctx: ActionContext

    @property
    def macro(self) -> MacroState:
        """Shortcut to the editor macro state."""
        return self.editor.session.macro

    def command(self, name: str, args: str = "") -> None:
        """Invoke a registered ``:`` command by name."""
        entry = self.commands.get(name)
        assert entry is not None
        entry.func(args)

    def action(self, name: str) -> None:
        """Execute a registered action by name."""
        assert self.actions.execute(name, self.ctx)


def _make_env() -> _Env:
    """Build an isolated editor with both built-in tables populated."""
    editor = _FakeEditor()
    actions = ActionRegistry()
    commands = CommandRegistry()
    populate(actions, cast(Editor, editor))
    register_commands(commands, cast(Editor, editor))
    return _Env(editor, actions, commands, ActionContext(editor.session, make_key_ui()))


@pytest.fixture
def env() -> _Env:
    """Fresh isolated environment for a single assertion batch."""
    return _make_env()


def test_macro_record_command_with_valid_register_starts_recording(env: _Env) -> None:
    env.command("macro-record", "a")

    assert env.macro.recording == "a"
    assert env.macro.awaiting is None
    assert env.macro.registers == {}
    assert env.macro.recording_label() == "rec @a"


def test_macro_record_command_without_register_enters_awaiting(env: _Env) -> None:
    env.command("macro-record")

    assert env.macro.awaiting == "record"
    assert env.macro.recording is None


def test_macro_record_command_too_many_args_warns_usage(env: _Env) -> None:
    env.command("macro-record", "a b")

    assert env.editor.notes == [(_USAGE, "warn")]
    assert env.macro.awaiting is None


def test_macro_record_command_invalid_register_warns(env: _Env) -> None:
    for reg in ("A", "ab", "!", "1a"):
        env.command("macro-record", reg)

    assert env.editor.notes == [
        ("macro register must be one character in a-z0-9", "warn")
    ] * 4
    assert env.macro.recording is None
    assert env.macro.awaiting is None


def test_macro_record_command_restarts_when_already_recording(env: _Env) -> None:
    env.macro.registers["a"] = ("x",)

    env.command("macro-record", "b")

    assert env.macro.registers["a"] == ("x",)
    assert env.macro.recording == "b"
    assert env.macro.buffer == []


def test_macro_stop_command_freezes_sequence_and_warns_when_idle(env: _Env) -> None:
    env.macro.recording = "a"
    env.macro.buffer = ["x", "y"]

    env.command("macro-stop")

    assert env.macro.registers["a"] == ("x", "y")
    assert env.macro.recording is None

    env.command("macro-stop")

    assert env.editor.notes == [("not recording a macro", "warn")]


def test_macro_stop_command_rejects_extra_args(env: _Env) -> None:
    env.command("macro-stop", "x")

    assert env.editor.notes == [(_USAGE, "warn")]
    assert env.macro.recording is None
    assert env.macro.awaiting is None
    assert env.macro.registers == {}


def test_macro_play_command_plays_exact_count(env: _Env) -> None:
    env.macro.registers["a"] = ("x", "y")

    env.command("macro-play", "a 3")

    assert env.editor.dispatched == ["x", "y"] * 3
    assert env.macro.last_played == ("a", 3)
    assert env.macro.playing is False


def test_macro_play_command_defaults_count_to_one(env: _Env) -> None:
    env.macro.registers["q"] = ("j",)

    env.command("macro-play", "q")

    assert env.editor.dispatched == ["j"]
    assert env.macro.last_played == ("q", 1)


def test_macro_play_command_missing_register_warns_usage(env: _Env) -> None:
    env.command("macro-play")

    assert env.editor.notes == [(_USAGE, "warn")]
    assert env.editor.dispatched == []


def test_macro_play_command_non_integer_count_warns(env: _Env) -> None:
    env.macro.registers["a"] = ("x",)

    env.command("macro-play", "a abc")
    env.command("macro-play", "a 1.5")

    assert env.editor.notes == [
        ("macro count must be a positive integer", "warn")
    ] * 2
    assert env.editor.dispatched == []


def test_macro_play_command_non_positive_count_warns_via_flow(env: _Env) -> None:
    env.macro.registers["a"] = ("x",)

    env.command("macro-play", "a 0")
    env.command("macro-play", "a -1")

    assert env.editor.notes == [
        ("macro count must be a positive integer", "warn")
    ] * 2
    assert env.editor.dispatched == []
    assert env.macro.playing is False


def test_macro_play_command_empty_register_warns(env: _Env) -> None:
    env.command("macro-play", "z")

    assert env.editor.notes == [("macro register @z is empty", "warn")]
    assert env.editor.dispatched == []


def test_macro_play_command_arg_completer_returns_recorded_names(env: _Env) -> None:
    env.macro.registers = {"a": ("x",), "b": ("y",)}
    entry = env.commands.get("macro-play")
    assert entry is not None
    completer = entry.arg_completer
    assert completer is not None

    assert set(completer("")) == {"a", "b"}
    assert completer("a") == []


def test_macro_replay_last_command_reuses_last_count(env: _Env) -> None:
    env.macro.registers["a"] = ("x", "y")
    env.editor.macro_flows.play("a", 2)
    env.editor.dispatched.clear()

    env.command("macro-replay-last")

    assert env.editor.dispatched == ["x", "y", "x", "y"]
    assert env.macro.last_played == ("a", 2)


def test_macro_replay_last_command_overrides_count(env: _Env) -> None:
    env.macro.registers["a"] = ("x", "y")
    env.editor.macro_flows.play("a", 2)
    env.editor.dispatched.clear()

    env.command("macro-replay-last", "3")

    assert env.editor.dispatched == ["x", "y"] * 3
    assert env.macro.last_played == ("a", 3)


def test_macro_replay_last_command_without_history_warns(env: _Env) -> None:
    env.command("macro-replay-last")

    assert env.editor.notes == [("no last macro replay", "warn")]
    assert env.editor.dispatched == []


def test_macro_commands_and_actions_are_registered_with_exact_names(env: _Env) -> None:
    assert {"macro_record", "macro_play", "macro_replay_last"} <= set(env.actions.names())
    assert {
        "macro-record", "macro-stop", "macro-play", "macro-replay-last",
    } <= set(env.commands.names())

    for name in ("macro_record", "macro_play", "macro_replay_last"):
        action = env.actions.get(name)
        assert action is not None and action.description
    for name in ("macro-record", "macro-stop", "macro-play", "macro-replay-last"):
        command = env.commands.get(name)
        assert command is not None and command.description


def test_key_and_command_entries_produce_identical_state() -> None:
    key_env = _make_env()
    cmd_env = _make_env()

    key_env.action("macro_record")
    cmd_env.command("macro-record")

    for env in (key_env, cmd_env):
        assert env.macro.awaiting == "record"
        assert env.macro.recording is None

    key_env.editor.macro_flows.begin_with("a")
    cmd_env.editor.macro_flows.begin_with("a")

    for env in (key_env, cmd_env):
        assert env.macro.recording == "a"


def test_all_command_warnings_use_warn_kind(env: _Env) -> None:
    env.macro.registers["a"] = ("x",)

    env.command("macro-record", "a b")
    env.command("macro-record", "A")
    env.command("macro-stop", "x")
    env.command("macro-stop")
    env.command("macro-play")
    env.command("macro-play", "ab")
    env.command("macro-play", "a abc")
    env.command("macro-replay-last")

    assert len(env.editor.notes) == 8
    assert all(kind == "warn" for _, kind in env.editor.notes)
    assert all(text for text, _ in env.editor.notes)


def test_key_and_command_entries_agree_on_count_prefix() -> None:
    key_env = _make_env()
    cmd_env = _make_env()
    for env in (key_env, cmd_env):
        env.macro.registers["a"] = ("x", "y")

    key_env.macro.pending_count = 3
    key_env.action("macro_play")
    key_env.editor.macro_flows.begin_with("a")
    cmd_env.command("macro-play", "a 3")

    assert key_env.editor.dispatched == ["x", "y"] * 3
    assert cmd_env.editor.dispatched == ["x", "y"] * 3
    for env in (key_env, cmd_env):
        assert env.macro.last_played == ("a", 3)
        assert env.macro.playing is False


def test_key_and_command_entries_agree_on_replay_last_count() -> None:
    key_env = _make_env()
    cmd_env = _make_env()
    for env in (key_env, cmd_env):
        env.macro.registers["a"] = ("x", "y")
        env.editor.macro_flows.play("a", 2)
        env.editor.dispatched.clear()

    key_env.macro.pending_count = 3
    key_env.action("macro_replay_last")
    cmd_env.command("macro-replay-last", "3")

    assert key_env.editor.dispatched == ["x", "y"] * 3
    assert cmd_env.editor.dispatched == ["x", "y"] * 3
    for env in (key_env, cmd_env):
        assert env.macro.last_played == ("a", 3)

    # No prefix / vsc constant 1: both entries reuse the last count (2).
    key_idle = _make_env()
    cmd_idle = _make_env()
    for env in (key_idle, cmd_idle):
        env.macro.registers["a"] = ("x", "y")
        env.editor.macro_flows.play("a", 2)
        env.editor.dispatched.clear()

    key_idle.action("macro_replay_last")
    cmd_idle.command("macro-replay-last")

    assert key_idle.editor.dispatched == ["x", "y"] * 2
    assert cmd_idle.editor.dispatched == ["x", "y"] * 2
    for env in (key_idle, cmd_idle):
        assert env.macro.last_played == ("a", 2)
