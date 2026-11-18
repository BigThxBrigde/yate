"""Ex-command routing for the marks / jumps commands (plan-c).

The stub editor exposes just the ``navigation_flows`` recorder and the
``message`` recorder the four commands drive (R7 shape: one registry, one
``register_commands`` pass, cast to the real ``Editor`` type).  Only the
routing is under test here; the orchestration itself is pinned by
``test_marks_navigation_flows.py``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from yate.commands import register_commands
from yate.editor import Editor
from yate.registries import CommandRegistry


class _FlowsRecorder:
    """Records the NavigationFlows verbs the command table forwards to."""

    def __init__(self) -> None:
        self.calls: list[tuple[object, ...]] = []

    def show_marks(self) -> None:
        self.calls.append(("show_marks",))

    def show_jumps(self) -> None:
        self.calls.append(("show_jumps",))

    def jump_to_mark(self, name: str, uid: int | None = None) -> None:
        self.calls.append(("jump_to_mark", name, uid))

    def delete_mark(self, name: str, uid: int | None = None) -> bool:
        self.calls.append(("delete_mark", name, uid))
        return False


class _StubEditor:
    """The editor surface the marks / jumps commands touch."""

    def __init__(self) -> None:
        self.navigation_flows = _FlowsRecorder()
        self.notes: list[tuple[str, str]] = []

    def message(self, text: str, kind: str = "info") -> None:
        """Record a user-facing notice as a ``(text, kind)`` pair."""
        self.notes.append((text, kind))


@dataclass
class _Env:
    """One isolated registry wired to the stub editor."""

    editor: _StubEditor
    commands: CommandRegistry

    def command(self, name: str, args: str = "") -> None:
        """Invoke a registered ``:`` command by name."""
        entry = self.commands.get(name)
        assert entry is not None, f"command not registered: {name}"
        entry.func(args)


def _make_env() -> _Env:
    """Build an isolated registry over a recording stub editor."""
    editor = _StubEditor()
    commands = CommandRegistry()
    register_commands(commands, cast(Editor, editor))
    return _Env(editor, commands)


def test_marks_and_jumps_commands_open_overlays() -> None:
    """:marks and :jumps open their overview screens through the flow."""
    env = _make_env()

    env.command("marks")
    env.command("jumps")

    assert env.editor.navigation_flows.calls == [
        ("show_marks",),
        ("show_jumps",),
    ]


def test_mark_command_valid_name_calls_flow() -> None:
    """:mark <a-z> forwards to jump_to_mark (D6 semantics live in the flow)."""
    env = _make_env()

    env.command("mark", "a")

    assert env.editor.navigation_flows.calls == [("jump_to_mark", "a", None)]
    assert env.editor.notes == []


def test_mark_command_illegal_name_warns() -> None:
    """:mark with an illegal or missing name warns and skips the flow."""
    env = _make_env()

    env.command("mark", "A")
    env.command("mark")

    assert env.editor.navigation_flows.calls == []
    assert len(env.editor.notes) == 2
    assert all(kind == "warn" for _text, kind in env.editor.notes)


def test_delmark_command_routes_to_flow() -> None:
    """:delmark <a-z> forwards to delete_mark."""
    env = _make_env()

    env.command("delmark", "a")

    assert env.editor.navigation_flows.calls == [("delete_mark", "a", None)]


def test_delmark_command_empty_warns() -> None:
    """:delmark without a name warns the usage line."""
    env = _make_env()

    env.command("delmark")

    assert env.editor.navigation_flows.calls == []
    assert env.editor.notes and env.editor.notes[-1][1] == "warn"
