"""The action and command registries: registration, lookup and execution.

Both registries are plain containers that extensions and the built-in tables
write into, so the interesting behaviour is the overwrite semantics, the
missing-name lookups and the sorted views the help system and the completion
read.
"""

from __future__ import annotations

from typing import Any

from yate.config import YateConfig
from yate.keymaps.base import ActionContext, KeyUi
from yate.registries import Action, ActionRegistry, CommandRegistry
from yate.session import EditorSession


def _context() -> ActionContext:
    """A real action context (the session plus inert UI callbacks)."""
    session = EditorSession(YateConfig())
    session.new_buffer()
    ui = KeyUi(
        execute_action=lambda _name: True,
        message=lambda _text: None,
        command_prompt=lambda: None,
        find_prompt=lambda _forward: None,
        goto_prompt=lambda: None,
        toggle_keymap=lambda: None,
    )
    return ActionContext(session, ui)


# --- ActionRegistry ---------------------------------------------------------


def test_get_returns_the_registered_action() -> None:
    """A registered action is retrievable with its description."""
    registry = ActionRegistry()
    registry.register("save", lambda _ctx: None, "write the buffer")

    action = registry.get("save")
    assert isinstance(action, Action)
    assert action.name == "save"
    assert action.description == "write the buffer"


def test_get_reports_an_unknown_action() -> None:
    """Looking up a name that was never registered yields None."""
    assert ActionRegistry().get("nope") is None


def test_execute_runs_the_action_with_the_context() -> None:
    """A known action runs and reports that it was handled."""
    registry = ActionRegistry()
    seen: list[ActionContext] = []
    registry.register("mark", seen.append)

    ctx = _context()
    assert registry.execute("mark", ctx) is True
    assert seen == [ctx]


def test_execute_reports_an_unknown_action() -> None:
    """An unknown action is not handled (the keymap falls through)."""
    assert ActionRegistry().execute("nope", _context()) is False


def test_names_and_describe_are_sorted_by_name() -> None:
    """The help system relies on both views being name-sorted."""
    registry = ActionRegistry()
    registry.register("zap", lambda _ctx: None, "last")
    registry.register("add", lambda _ctx: None, "first")

    assert registry.names() == ["add", "zap"]
    assert registry.describe() == [("add", "first"), ("zap", "last")]


def test_reregistering_replaces_the_action() -> None:
    """A duplicate name overwrites the entry (there is no allow_override flag)."""
    registry = ActionRegistry()
    first: list[Any] = []
    second: list[Any] = []
    registry.register("dup", first.append, "old")
    registry.register("dup", second.append, "new")

    assert registry.names() == ["dup"]
    assert registry.describe() == [("dup", "new")]
    assert registry.execute("dup", _context()) is True
    assert second and not first


# --- CommandRegistry --------------------------------------------------------


def test_command_registry_round_trip() -> None:
    """Commands round-trip through register / get / names / describe."""
    registry = CommandRegistry()
    calls: list[str] = []

    def handler(args: str) -> None:
        calls.append(args)

    registry.register("write", handler, "write the file")

    entry = registry.get("write")
    assert entry is not None
    func, description = entry
    assert description == "write the file"
    assert registry.names() == ["write"]
    assert registry.describe("write") == "write the file"

    func("notes.txt")
    assert calls == ["notes.txt"]


def test_command_registry_reports_unknown_names() -> None:
    """Unknown commands are reported as missing, not as an error."""
    registry = CommandRegistry()
    assert registry.get("nope") is None
    assert registry.describe("nope") == ""
    assert registry.names() == []


def test_command_registry_names_are_sorted() -> None:
    """The ``:`` completion and the palette read the sorted name list."""
    registry = CommandRegistry()
    for name in ("theme", "open", "quit"):
        registry.register(name, lambda _args: None, name)
    assert registry.names() == ["open", "quit", "theme"]


def test_command_reregistration_replaces_the_handler() -> None:
    """Registering the same name twice keeps only the newest handler."""
    registry = CommandRegistry()
    registry.register("dup", lambda _args: "old", "old")
    registry.register("dup", lambda _args: "new", "new")

    entry = registry.get("dup")
    assert entry is not None
    assert entry[0]("") == "new"
    assert entry[1] == "new"
    assert registry.names() == ["dup"]


def test_command_registry_accepts_arbitrary_callables() -> None:
    """A command handler may return anything; the registry stores it as-is."""
    registry = CommandRegistry()
    marker = object()

    def handler(_args: str) -> object:
        return marker

    registry.register("thing", handler, "returns a marker")

    entry = registry.get("thing")
    assert entry is not None
    assert entry[0]("") is marker
