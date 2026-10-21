"""End-to-end smoke for the whole game pack in a running YateApp.

The per-game modules are covered by their own live-lua tests; this module
proves the *shipped* wiring: the bundled loader registers ``:game`` and the
five ``game-*`` actions, the dispatcher resolves them, every canvas opens with
its documented size and ``escape`` closes it again.
"""

from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path

import pytest

from yate.app import YateApp
from yate.editor_view.canvas_screen import CanvasScreen

from conftest import wait_until

#: Live-lua marker: the games need the optional lupa package.
requires_lupa = pytest.mark.skipif(
    importlib.util.find_spec("lupa") is None,
    reason="lupa is not installed (live-lua group)",
)

#: Documented canvas size per game (cols, rows).
_CANVAS_SIZES: tuple[tuple[str, int, int], ...] = (
    ("snake", 80, 24),
    ("pacman", 41, 29),
    ("sokoban", 41, 22),
    ("nethack", 74, 24),
    ("tetris", 59, 22),
)


@requires_lupa
def test_every_bundled_game_opens_and_closes(tmp_path: Path) -> None:
    """``:game <name>`` pushes that game's canvas and escape pops it."""

    async def scenario() -> None:
        target = tmp_path / "notes.txt"
        target.write_text("x", encoding="utf-8")
        app = YateApp(target=target)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            assert app.editor.commands.get("game") is not None

            for name, cols, rows in _CANVAS_SIZES:
                app.editor.run_command(f"game {name}")
                await pilot.pause()
                canvas = app.screen
                assert isinstance(canvas, CanvasScreen), f"{name} did not open a canvas"
                assert (canvas.cols, canvas.rows) == (cols, rows), name
                assert canvas.drawn, f"{name} painted nothing"

                await pilot.press("escape")
                assert await wait_until(pilot, lambda: app.screen is not canvas), name

    asyncio.run(scenario())
