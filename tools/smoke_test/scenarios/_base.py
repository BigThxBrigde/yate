"""Helpers shared by every smoke scenario.

All scenarios are plain ``async def (tmp: Path) -> ScenarioResult`` and are
run headless under ``pilot.run_test()``.  The helpers here keep the
scenario bodies to "press keys, read app state, append a :class:`Check`":

* :func:`type_text` -- press one key at a time (no ``sleep`` guessing);
* :func:`run_command` / :func:`goto` -- drive the ex command line the way
  the vsc keymap expects (F5, never ``:``);
* :func:`wait_until` -- the one polling primitive allowed, for work that
  finishes in a background worker.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from collections.abc import Callable

__all__ = [
    "goto",
    "message_text",
    "plain_text",
    "run_command",
    "type_path",
    "type_text",
    "wait_until",
]

# F5 is the ex command line entry point in vsc mode (":" is intentionally
# unbound there and types literally), and it works in vim mode too.
_COMMAND_KEY = "f5"


async def type_text(pilot: Any, text: str, *, pause: bool = True) -> None:
    """Type *text*, then let the app settle.

    The characters are posted in a single ``pilot.press`` call: every
    ``press`` waits for the whole widget tree to drain its message queue
    (~70ms headless), so one call per character turned a 70-character path
    into five seconds of wall clock.
    """
    keys = ["space" if ch == " " else ch for ch in text]
    if keys:
        await pilot.press(*keys)
    if pause:
        await pilot.pause()


async def run_command(pilot: Any, text: str) -> None:
    """Enter ``text`` on the ex command line and submit it.

    The command is written without a leading ``:`` -- the prompt bar draws
    the prefix itself.
    """
    await pilot.press(_COMMAND_KEY)
    await pilot.pause()
    await type_text(pilot, text)
    await pilot.press("enter")
    await pilot.pause()
    await pilot.pause()


async def type_path(pilot: Any, path: Path) -> None:
    """Type an absolute *path* into the active prompt.

    Windows paths are typed with forward slashes: ``\\`` has no stable
    Textual key name but ``Path`` accepts ``/`` on every platform.
    """
    await type_text(pilot, str(path).replace("\\", "/"))


async def goto(pilot: Any, line: str) -> None:
    """``Ctrl+G`` -> *line* -> enter (the go-to-line prompt)."""
    await pilot.press("ctrl+g")
    await pilot.pause()
    await type_text(pilot, line)
    await pilot.press("enter")
    await pilot.pause()


def plain_text(content: Any) -> str:
    """Plain text of a widget renderable (rich ``Text``, str, or other)."""
    plain = getattr(content, "plain", None)
    return plain if isinstance(plain, str) else str(content)


def message_text(app: Any) -> str:
    """The current bottom-bar message (assertions read the app state)."""
    bar = app.editor.prompt_bar
    if bar is None:
        return ""
    return plain_text(bar.message.content)


def cursor_path(app: Any) -> Any | None:
    """Path of the explorer node under the cursor (``None`` if unknown)."""
    tree = app.editor.explorer_tree
    if tree is None:
        return None
    node = tree.cursor_node
    data = node.data if node is not None else None
    return data if data is not None else None


async def wait_until(
    pilot: Any,
    predicate: Callable[[], bool],
    timeout: float = 5.0,
    step: float = 0.05,
) -> bool:
    """Pause until *predicate* holds; ``False`` on timeout.

    The only place a scenario may wait on something other than
    ``pilot.pause()``: worker-backed work (file open, LSP, shell) needs a
    few event-loop turns to land.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        await pilot.pause(step)
        if predicate():
            return True
    return predicate()
