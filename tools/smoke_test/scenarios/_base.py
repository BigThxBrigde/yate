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
from typing import Any, Callable

__all__ = ["goto", "run_command", "type_text", "wait_until"]

# F5 is the ex command line entry point in vsc mode (":" is intentionally
# unbound there and types literally), and it works in vim mode too.
_COMMAND_KEY = "f5"


async def type_text(pilot: Any, text: str, *, pause: bool = True) -> None:
    """Press each character of *text*, then let the app settle."""
    for ch in text:
        await pilot.press(ch)
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


async def goto(pilot: Any, line: str) -> None:
    """``Ctrl+G`` -> *line* -> enter (the go-to-line prompt)."""
    await pilot.press("ctrl+g")
    await pilot.pause()
    await type_text(pilot, line)
    await pilot.press("enter")
    await pilot.pause()


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
