"""Live-lua tests for the bundled tetris extension (``tetris.lua``).

The extension is executed by the real lupa runtime over the recording fake
api from :mod:`lua_game_harness`, so these tests drive the shipped Lua file
exactly as the editor would: the ``game-tetris`` action, the canvas callbacks
(key / tick / close) and the teardown hook.  Every board assertion is
deterministic: the piece source is pinned through ``tetris.set_piece_source``
instead of the random Bag-7 generator.

The ``:game`` command itself lives in ``games.lua`` and is covered by
``tests/test_lua_engine.py``.

Marked ``@requires_lupa``: the whole module skips without the optional
``yate[lua]`` extra.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from lua_game_harness import FakeCanvas, GameRuntime, requires_lupa
from yate.app import YateApp
from yate.editor_view.canvas_screen import CanvasScreen

from conftest import wait_until

_BOARD_COLS = 10
_LEFT_W = 17  # stats box width; then one blank gap column
_BOARD_AT = 18  # 0-based column of the board's left border
_RIGHT_AT = _BOARD_AT + 1 + 2 * _BOARD_COLS + 1  # 0-based right column start


def _board_cells(grid: str, char: str) -> set[tuple[int, int]]:
    """1-based ``(row, cell)`` board coordinates of *char* in a rendered frame.

    The board cells start after the stats box, the gap and the board's left
    border, every cell spans two identical characters, and the board's top
    border occupies canvas row 1 (board row *r* is canvas row *r + 1*).  The
    side boxes are ignored.
    """
    cells: set[tuple[int, int]] = set()
    for row, line in enumerate(grid.split("\n"), start=1):
        board = line[_BOARD_AT + 1 : _BOARD_AT + 1 + 2 * _BOARD_COLS]
        for index in range(0, len(board), 2):
            if board[index] == char and board[index + 1] == char:
                cells.add((row - 1, index // 2 + 1))
    return cells


def _stats(grid: str) -> str:
    """The left stats box column of a rendered frame."""
    return "\n".join(line[:_LEFT_W] for line in grid.split("\n"))


def _right_boxes(grid: str) -> str:
    """The right column (next + help boxes) of a rendered frame."""
    return "\n".join(line[_RIGHT_AT:] for line in grid.split("\n"))


def _move_to(game: GameRuntime, x: int) -> None:
    """Shift the spawning piece (offset ``x = 3``) to horizontal offset *x*."""
    delta = x - 3
    key = "right" if delta > 0 else "left"
    game.press(*([key] * abs(delta)))


def _start(game: GameRuntime, *kinds: str) -> FakeCanvas:
    """Open a game with a pinned piece sequence (the last kind repeats)."""
    queue: list[str] = list(kinds)

    def next_piece() -> str:
        return queue.pop(0) if len(queue) > 1 else queue[0]

    game.module.set_piece_source(next_piece)
    return game.launch()


@pytest.fixture
def game() -> GameRuntime:
    """A loaded tetris extension over a recording api."""
    return GameRuntime("tetris")


# --- canvas lifecycle ---------------------------------------------------------


@requires_lupa
def test_tetris_opens_the_three_box_layout(game: GameRuntime) -> None:
    """``game-tetris`` opens the composed canvas and paints the spawn frame."""
    canvas = _start(game, "O")

    # 17 stats + 1 gap + 22 board box + 1 gap + 18 right column, 20 rows + 2.
    assert (canvas.cols, canvas.rows) == (59, 22)
    assert len(canvas.grid.split("\n")) == 22
    assert canvas.status == "score 0  lines 0  level 1  escape quits"
    # O spawns at x offset 3: board cells 4-5 of the top two board rows.
    assert _board_cells(canvas.grid, "O") == {(1, 4), (1, 5), (2, 4), (2, 5)}
    # stats box shows score, level and best; empty board means zero points
    stats = _stats(canvas.grid)
    assert "╭─ stats" in stats and " score        0" in stats
    assert " level        1" in stats
    assert " best         0" in stats
    # right column previews the next piece and lists the key bindings
    right = _right_boxes(canvas.grid)
    assert "╭─ next" in right and "OOOO" in right
    assert "╭─ help" in right and " restart" in right and " quit" in right


@requires_lupa
def test_second_launch_reports_already_running(game: GameRuntime) -> None:
    """A canvas already open is not replaced; the message line says so."""
    first = _start(game, "O")

    game.launch()

    assert game.api.messages == ["tetris is already running"]
    assert game.require_canvas() is first
    assert first.closed is False


@requires_lupa
def test_close_callback_invalidates_the_canvas(game: GameRuntime) -> None:
    """After on_close a racing tick is ignored and a relaunch is allowed."""
    canvas = _start(game, "O")

    canvas.close_cb()
    frames = len(canvas.grids)
    canvas.tick()
    assert len(canvas.grids) == frames

    game.launch()
    assert game.api.canvas is not canvas


@requires_lupa
def test_teardown_closes_the_open_canvas(game: GameRuntime) -> None:
    """teardown dismisses the active canvas and deadens its callbacks."""
    canvas = _start(game, "O")

    game.module.teardown(game.api)

    assert canvas.closed is True
    frames = len(canvas.grids)
    canvas.tick()
    assert len(canvas.grids) == frames


# --- key mapping --------------------------------------------------------------


@requires_lupa
def test_left_right_move_and_soft_drop_steps_one_row(game: GameRuntime) -> None:
    """left/right shift by one column; down drops one row without locking."""
    canvas = _start(game, "O")

    game.press("left")
    assert _board_cells(canvas.grid, "O") == {(1, 3), (1, 4), (2, 3), (2, 4)}

    game.press("right", "right")
    assert _board_cells(canvas.grid, "O") == {(1, 5), (1, 6), (2, 5), (2, 6)}

    game.press("down")
    assert _board_cells(canvas.grid, "O") == {(2, 5), (2, 6), (3, 5), (3, 6)}


@requires_lupa
def test_space_hard_drops_to_the_floor(game: GameRuntime) -> None:
    """space lands the piece on the bottom row and the next one spawns."""
    canvas = _start(game, "O")

    game.press("space")

    assert _board_cells(canvas.grid, "O") == {
        (1, 4),
        (1, 5),
        (2, 4),
        (2, 5),
        (19, 4),
        (19, 5),
        (20, 4),
        (20, 5),
    }


@requires_lupa
def test_up_and_x_rotate_clockwise(game: GameRuntime) -> None:
    """up and x both advance the rotation state by one step."""
    canvas = _start(game, "T")
    assert _board_cells(canvas.grid, "T") == {(1, 5), (2, 4), (2, 5), (2, 6)}

    game.press("up")
    assert _board_cells(canvas.grid, "T") == {(1, 4), (2, 4), (2, 5), (3, 4)}

    game.press("x")
    assert _board_cells(canvas.grid, "T") == {(1, 4), (1, 5), (1, 6), (2, 5)}


@requires_lupa
def test_rotation_kicks_off_the_right_wall(game: GameRuntime) -> None:
    """A vertical I at the wall rotates back in with the -1 kick."""
    canvas = _start(game, "I")

    game.press("up")  # vertical, columns 6
    assert _board_cells(canvas.grid, "I") == {(1, 6), (2, 6), (3, 6), (4, 6)}

    game.press("right", "right", "right", "right")  # offset 3 -> 7, column 10
    game.press("up")  # would stick out one column: kicked back to offset 6

    assert _board_cells(canvas.grid, "I") == {(2, 7), (2, 8), (2, 9), (2, 10)}


@requires_lupa
def test_enter_rushes_the_fall_and_locks_piece_controls(game: GameRuntime) -> None:
    """enter commits the piece: one row per tick, no move / rotate until it
    locks; the spawned piece is controllable again."""
    canvas = _start(game, "T")
    assert _board_cells(canvas.grid, "T") == {(1, 5), (2, 4), (2, 5), (2, 6)}

    game.press("enter")
    game.tick(1)
    assert _board_cells(canvas.grid, "T") == {(2, 5), (3, 4), (3, 5), (3, 6)}

    # a committed piece ignores left / right / rotate
    game.press("left", "right", "up")
    assert _board_cells(canvas.grid, "T") == {(2, 5), (3, 4), (3, 5), (3, 6)}

    # 18 more ticks land it at the floor and lock it; a fresh piece spawns
    game.tick(18)
    assert _board_cells(canvas.grid, "T") == {
        (1, 5), (2, 4), (2, 5), (2, 6),
        (19, 5), (20, 4), (20, 5), (20, 6),
    }

    # the fresh piece is controllable again
    game.press("left")
    assert _board_cells(canvas.grid, "T") == {
        (1, 4), (2, 3), (2, 4), (2, 5),
        (19, 5), (20, 4), (20, 5), (20, 6),
    }


# --- clock, gravity, pause ----------------------------------------------------


@requires_lupa
def test_gravity_steps_on_the_level_clock(game: GameRuntime) -> None:
    """Level 1 gravity fires on the 14th tick (15 - level), not before."""
    canvas = _start(game, "O")

    game.tick(13)
    assert _board_cells(canvas.grid, "O") == {(1, 4), (1, 5), (2, 4), (2, 5)}

    game.tick(1)
    assert _board_cells(canvas.grid, "O") == {(2, 4), (2, 5), (3, 4), (3, 5)}


@requires_lupa
def test_pause_freezes_gravity_until_resumed(game: GameRuntime) -> None:
    """p freezes the clock; the next p resumes where the counter stopped."""
    canvas = _start(game, "O")

    game.press("p")
    paused = canvas.grid
    game.tick(30)
    assert canvas.grid == paused
    assert "paused" in paused

    game.press("p")
    game.tick(14)
    assert "paused" not in canvas.grid
    assert _board_cells(canvas.grid, "O") == {(2, 4), (2, 5), (3, 4), (3, 5)}


# --- clearing, scoring, levels ------------------------------------------------


@requires_lupa
def test_line_clears_score_lines_and_level(game: GameRuntime) -> None:
    """Five O pieces fill two rows: 300 points, 10 lines -> level 2."""
    canvas = _start(game, "O")

    for _batch in range(5):
        # Two O pieces per row: offsets 0/2/4/6/8 tile columns 1-10 exactly.
        for target in (0, 2, 4, 6, 8):
            _move_to(game, target)
            game.press("space")

    stats = _stats(canvas.grid)
    assert " score     1500" in stats
    assert " level        2" in stats
    # Every cleared row is gone: only the freshly spawned O is drawn.
    assert _board_cells(canvas.grid, "O") == {(1, 4), (1, 5), (2, 4), (2, 5)}


@requires_lupa
def test_gravity_speeds_up_with_the_level(game: GameRuntime) -> None:
    """At level 2 gravity fires on the 13th tick (max(2, 15 - level))."""
    _start(game, "O")
    for _batch in range(5):
        for target in (0, 2, 4, 6, 8):
            _move_to(game, target)
            game.press("space")
    canvas = game.require_canvas()
    assert " level        2" in _stats(canvas.grid)

    game.tick(12)
    assert _board_cells(canvas.grid, "O") == {(1, 4), (1, 5), (2, 4), (2, 5)}
    game.tick(1)
    assert _board_cells(canvas.grid, "O") == {(2, 4), (2, 5), (3, 4), (3, 5)}


# --- game over and restart ----------------------------------------------------


@requires_lupa
def test_stack_to_the_top_ends_the_game_and_r_restarts(game: GameRuntime) -> None:
    """Ten O pieces fill one column pair; the next spawn is game over."""
    canvas = _start(game, "O")

    for _ in range(10):
        game.press("space")

    assert "game over" in canvas.grid
    assert "press r" in canvas.grid

    game.tick(15)  # the clock no longer moves anything
    assert "game over" in canvas.grid

    game.press("r")
    assert "game over" not in canvas.grid
    assert " score        0" in _stats(canvas.grid)
    assert _board_cells(canvas.grid, "O") == {(1, 4), (1, 5), (2, 4), (2, 5)}


@requires_lupa
def test_r_restarts_a_running_game(game: GameRuntime) -> None:
    """r also works mid-game: score and stack are wiped."""
    canvas = _start(game, "O")
    game.press("space")
    game.press("space")
    assert " score        0" in _stats(canvas.grid)

    game.press("r")

    assert _board_cells(canvas.grid, "O") == {(1, 4), (1, 5), (2, 4), (2, 5)}


# --- persistence --------------------------------------------------------------


@requires_lupa
def test_stats_box_shows_the_saved_best(game: GameRuntime) -> None:
    """A stored high score is loaded into the stats box."""
    game.api.data.files["games/tetris.json"] = json.dumps(
        {
            "version": 1,
            "high_scores": [
                {"score": 1500, "player": "alice", "at": "2026-10-20T21:00:00"}
            ],
        }
    )

    canvas = _start(game, "O")

    assert " best      1500" in _stats(canvas.grid)


@requires_lupa
def test_game_over_saves_the_high_score_with_player(game: GameRuntime) -> None:
    """Stacking out writes one high score entry with the player name."""
    _start(game, "O")
    for _ in range(10):
        game.press("space")

    assert game.snapshot()["over"] is True
    document = json.loads(game.api.data.files["games/tetris.json"])
    entry = document["high_scores"][0]

    assert entry["score"] == 0
    assert entry["player"]
    assert entry["at"]


@requires_lupa
def test_snapshot_reports_the_score_and_level(game: GameRuntime) -> None:
    """snapshot() exposes the running numbers for tests and telemetry."""
    _start(game, "O")
    assert game.snapshot()["lines"] == 0

    for _batch in range(5):
        for target in (0, 2, 4, 6, 8):
            _move_to(game, target)
            game.press("space")

    snapshot = game.snapshot()
    assert snapshot["lines"] == 10
    assert snapshot["level"] == 2
    assert snapshot["over"] is False


@requires_lupa
def test_teardown_saves_stats(game: GameRuntime) -> None:
    """Starting a game bumps the games counter, kept across teardown."""
    _start(game, "O")

    game.module.teardown(game.api)

    document = json.loads(game.api.data.files["games/tetris.json"])
    assert document["stats"]["games"] >= 1


# --- end-to-end: the real app over the real loader -----------------------------


def _board_has_a_piece(canvas: CanvasScreen) -> bool:
    """Whether any drawn cell carries a tetromino letter."""
    return any(ch in "IOTSZJL" for row in canvas.drawn for ch in row)


@requires_lupa
def test_game_tetris_opens_and_closes_in_the_real_app(tmp_path: Path) -> None:
    """``:game tetris`` in a running YateApp pushes the canvas, the bundled
    load path registers the command, the clock paints a piece and the key
    path works; escape pops the screen again."""

    async def scenario() -> None:
        target = tmp_path / "notes.txt"
        target.write_text("x", encoding="utf-8")
        app = YateApp(target=target)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            # the bundled extension registered the command at startup
            assert app.editor.commands.get("game") is not None

            app.editor.run_command("game tetris")
            await pilot.pause()
            canvas = app.screen
            assert isinstance(canvas, CanvasScreen)
            assert canvas.cols == 59 and canvas.rows == 22
            # the canvas clock paints the spawned piece within a few ticks
            assert await wait_until(pilot, lambda: _board_has_a_piece(canvas))

            # a game key reaches the Lua state machine (nothing crashes)
            await pilot.press("left")
            await pilot.press("space")
            await pilot.pause()
            assert isinstance(app.screen, CanvasScreen)

            # escape exits the canvas without killing the app
            await pilot.press("escape")
            assert await wait_until(pilot, lambda: app.screen is not canvas)

    asyncio.run(scenario())
