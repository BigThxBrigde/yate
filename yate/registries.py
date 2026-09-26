"""The registries extensions and the built-in tables write into.

Both registries are plain, UI-free containers: ``ActionRegistry`` maps action
names to callables, ``CommandRegistry`` maps ``:`` command names to handlers.
They live in their own leaf module (below ``keymaps`` and below
:mod:`yate.editor`) so every layer can hold the same concrete objects without
import cycles.

The *contents* -- the built-in action and command tables -- live in
:mod:`yate.actions` / :mod:`yate.commands`, which wire the tables against a
concrete :class:`~yate.editor.Editor`.
"""

from __future__ import annotations

from dataclasses import dataclass

from collections.abc import Callable

from yate.keymaps.base import ActionContext
from yate.logs import tracing

#: A ``:`` command handler: receives the raw argument string.
CommandFunc = Callable[[str], object]

log = tracing.get_logger(__name__)


@dataclass
class Action:
    """A named operation registered in :class:`ActionRegistry`."""

    name: str
    func: Callable[[ActionContext], object]
    description: str


class ActionRegistry:
    """Maps action names to context callables."""

    def __init__(self) -> None:
        self._actions: dict[str, Action] = {}

    def register(
        self, name: str, func: Callable[[ActionContext], object], description: str = ""
    ) -> None:
        """Add (or replace) the action *name*."""
        if name in self._actions:
            log.warning("action overwritten: %s", name)
        self._actions[name] = Action(name, func, description)

    def get(self, name: str) -> Action | None:
        """Return the :class:`Action` for *name*, or ``None``."""
        return self._actions.get(name)

    def execute(self, name: str, ctx: ActionContext) -> bool:
        """Run *name* with *ctx*; returns ``False`` for unknown names."""
        action = self._actions.get(name)
        if action is None:
            return False
        action.func(ctx)
        return True

    def names(self) -> list[str]:
        """Sorted list of registered action names."""
        return sorted(self._actions)

    def describe(self) -> list[tuple[str, str]]:
        """Sorted ``(name, description)`` pairs for the help system."""
        return sorted((a.name, a.description) for a in self._actions.values())


class CommandRegistry:
    """``:`` commands, extendable by extensions."""

    def __init__(self) -> None:
        self._commands: dict[str, tuple[CommandFunc, str]] = {}

    def register(self, name: str, func: CommandFunc, description: str) -> None:
        if name in self._commands:
            log.warning("command overwritten: %s", name)
        self._commands[name] = (func, description)

    def get(self, name: str) -> tuple[CommandFunc, str] | None:
        return self._commands.get(name)

    def names(self) -> list[str]:
        return sorted(self._commands)

    def describe(self, name: str) -> str:
        entry = self._commands.get(name)
        return entry[1] if entry else ""
