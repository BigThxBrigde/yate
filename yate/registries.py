"""The registries extensions and the built-in tables write into.

Both registries are plain, UI-free containers: ``ActionRegistry`` maps action
names to callables, ``CommandRegistry`` maps ``:`` command names to handlers.
Layer-wise this module sits *above* :mod:`yate.keymaps.base` (it imports
:class:`~yate.keymaps.base.ActionContext`, and ``keymaps.base`` itself imports
:mod:`yate.session`) and *below* its consumers (:mod:`yate.actions`,
:mod:`yate.commands`, :mod:`yate.editor`), so every layer can hold the same
concrete objects without import cycles.

The *contents* -- the built-in action and command tables -- live in
:mod:`yate.actions` / :mod:`yate.commands`, which wire the tables against a
concrete :class:`~yate.editor.Editor`.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

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

    def unregister(self, name: str) -> bool:
        """Remove the action *name*; ``False`` when it was not registered.

        Used by the extension loader to roll back a failed ``setup``
        (architecture-boundaries rule 4, audit A13).
        """
        return self._actions.pop(name, None) is not None

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
        """Add (or replace) the ``:`` command *name*."""
        if name in self._commands:
            log.warning("command overwritten: %s", name)
        self._commands[name] = (func, description)

    def get(self, name: str) -> tuple[CommandFunc, str] | None:
        """Return the ``(handler, description)`` pair for *name*, or ``None``."""
        return self._commands.get(name)

    def unregister(self, name: str) -> bool:
        """Remove the ``:`` command *name*; ``False`` when it was not registered.

        Used by the extension loader to roll back a failed ``setup``
        (architecture-boundaries rule 4, audit A13).
        """
        return self._commands.pop(name, None) is not None

    def names(self) -> list[str]:
        """Sorted list of registered command names."""
        return sorted(self._commands)

    def describe(self, name: str) -> str:
        """The description of *name*; empty string when unknown."""
        entry = self._commands.get(name)
        return entry[1] if entry else ""
