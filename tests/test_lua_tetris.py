"""Live-lua tests for the bundled tetris extension (``tetris.lua``).

The extension is executed by the real lupa runtime over a recording fake
:class:`ExtensionAPI`, so these tests drive the shipped Lua file exactly as
the editor would: the ``:game`` command, the canvas callbacks (key / tick /
close) and the teardown hook.  Every board assertion is deterministic: the
piece source is pinned through ``tetris.set_piece_source`` instead of the
random Bag-7 generator.

Marked ``@requires_lupa``: the whole module skips without the optional
``yate[lua]`` extra.
"""

from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path
from typing import Any

import pytest

from yate.app import YateApp
from yate.editor_view.canvas_screen import CanvasScreen
from yate.paths import bundled_extensions_dir
from yate.services.extensions.lua.library import lua_api_library_source
from yate.services.extensions.lua.runtime import create_runtime

from conftest import wait_until

#: Live-lua marker: skip when the optional lupa package is not installed.
_lua_missing = importlib.util.find_spec("lupa") is None
requires_lupa = pytest.mark.skipif(
    _lua_missing, reason="lupa is not installed (live-lua group)"
)

#: The shipped extension source, read exactly as the loader will read it.
_TETRIS_SOURCE: str = (
    bundled_extensions_dir() / "tetris.lua"
).read_text(encoding="utf-8")


class _FakeCanvas:
    """Recording stand-in for the Python-side ``CanvasHandle``."""

    def __init__(self) -> None:
        self.cols: int = 0
        self.rows: int = 0
        self.grids: list[str] = []
        self.statuses: list[str] = []
        self.closed: bool = False
        # Lua closures handed over by open_canvas (opaque outside the runtime).
        self.key: Any = None
        self.tick: Any = None
        self.close_cb: Any = None

    @property
    def grid(self) -> str:
        """The most recently drawn newline-joined grid."""
        return self.grids[-1]

    @property
    def status(self) -> str:
        """The most recently pushed status line."""
        return self.statuses[-1]

    def draw(self, grid: str, palette: Any) -> None:
        """Record one frame (the palette is asserted on the library side)."""
        self.grids.append(grid)

    def set_status(self, text: str) -> None:
        """Record one status line."""
        self.statuses.append(text)

    def close(self) -> None:
        """Record that the host was asked to dismiss the canvas."""
        self.closed = True


class _FakeUi:
    """``api.ui``: records the canvas request, refuses segment traffic."""

    def __init__(self, api: _FakeApi) -> None:
        self._api = api

    def open_canvas(
        self,
        cols: int,
        rows: int,
        on_key: Any,
        on_tick: Any,
        on_close: Any,
    ) -> _FakeCanvas:
        """Build the recording canvas and keep the Lua callbacks."""
        canvas = _FakeCanvas()
        canvas.cols = cols
        canvas.rows = rows
        canvas.key = on_key
        canvas.tick = on_tick
        canvas.close_cb = on_close
        self._api.canvas = canvas
        return canvas

    def add_status_segment(self, *_args: Any) -> None:
        """tetris must not contribute a status bar segment."""
        raise AssertionError("tetris added a status segment")

    def remove_status_segment(self, *_args: Any) -> None:
        """tetris must not touch the status bar registry."""
        raise AssertionError("tetris removed a status segment")


class _FakeApi:
    """Recording stand-in for ``ExtensionAPI`` (only the used members)."""

    def __init__(self) -> None:
        self.messages: list[str] = []
        self.commands: dict[str, tuple[Any, str | None]] = {}
        self.canvas: _FakeCanvas | None = None
        self.ui = _FakeUi(self)
        # Raw passthrough namespaces the API library binds at load time.
        self.keymaps: Any = None
        self.highlight: Any = None
        self.sprites: Any = None
        self.lsp: Any = None
        self.syntax: Any = None

    def message(self, text: str) -> None:
        """Record one message-line hint."""
        self.messages.append(text)

    def register_command(
        self, name: str, fn: Any, description: str | None = None
    ) -> None:
        """Record one ``:`` command registration."""
        self.commands[name] = (fn, description)


class _Game:
    """One tetris module loaded into a fresh lua runtime over a fake api."""

    def __init__(self) -> None:
        self.api = _FakeApi()
        self.runtime: Any = create_runtime(self.api, lua_api_library_source())
        # The chunk returns the module table (module-table entry form); setup
        # is invoked by hand here because the test owns the runtime directly.
        self.module: Any = self.runtime.execute(_TETRIS_SOURCE)
        self.module.setup(self.api)

    def set_pieces(self, *kinds: str) -> None:
        """Pin the piece source to *kinds* (the last kind repeats forever)."""
        queue: list[str] = list(kinds)

        def next_piece() -> str:
            return queue.pop(0) if len(queue) > 1 else queue[0]

        self.module.set_piece_source(next_piece)

    def command(self, args: str) -> None:
        """Run the registered ``:game`` handler with *args*."""
        handler, _description = self.api.commands["game"]
        handler(args)

    def launch(self, *kinds: str) -> _FakeCanvas:
        """Open a canvas with a pinned piece sequence."""
        self.set_pieces(*kinds)
        self.command("tetris")
        return self.require_canvas()

    def require_canvas(self) -> _FakeCanvas:
        """The canvas opened so far; fails when none was opened."""
        canvas = self.api.canvas
        assert canvas is not None, "no canvas was opened"
        return canvas

    def press(self, *keys: str) -> None:
        """Deliver Textual key names to the canvas' on_key callback."""
        canvas = self.require_canvas()
        for key in keys:
            canvas.key(key)

    def tick(self, count: int = 1) -> None:
        """Fire *count* canvas clock ticks."""
        canvas = self.require_canvas()
        for _ in range(count):
            canvas.tick()


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


def _move_to(game: _Game, x: int) -> None:
    """Shift the spawning piece (offset ``x = 3``) to horizontal offset *x*."""
    delta = x - 3
    key = "right" if delta > 0 else "left"
    game.press(*([key] * abs(delta)))


@pytest.fixture
def game() -> _Game:
    """A loaded tetris extension over a recording api."""
    return _Game()


# --- command registration and argument handling ------------------------------


@requires_lupa
def test_game_command_registered_with_description(game: _Game) -> None:
    """setup registers exactly one ``game`` command, with its palette help."""
    assert set(game.api.commands) == {"game"}
    _handler, description = game.api.commands["game"]
    assert description == "launch a game (tetris)"


@requires_lupa
def test_empty_argument_reports_usage(game: _Game) -> None:
    """No argument (or blanks only) prints the usage hint, opens nothing."""
    game.command("")
    game.command("   ")

    assert game.api.messages == ["usage: :game tetris", "usage: :game tetris"]
    assert game.api.canvas is None


@requires_lupa
def test_unknown_game_reports_available_games(game: _Game) -> None:
    """An unknown name names itself and lists the one available game."""
    game.command("chess")

    assert game.api.messages == ["unknown game: chess (available: tetris)"]
    assert game.api.canvas is None


@requires_lupa
def test_tetris_opens_the_three_box_layout(game: _Game) -> None:
    """``:game tetris`` opens the composed canvas and paints the spawn frame."""
    canvas = game.launch("O")

    # 17 stats + 1 gap + 22 board box + 1 gap + 18 right column, 20 rows + 2.
    assert (canvas.cols, canvas.rows) == (59, 22)
    assert len(canvas.grid.split("\n")) == 22
    assert canvas.status == "escape quits"
    # O spawns at x offset 3: board cells 4-5 of the top two board rows.
    assert _board_cells(canvas.grid, "O") == {(1, 4), (1, 5), (2, 4), (2, 5)}
    # stats box shows score and level; empty board means zero points
    stats = _stats(canvas.grid)
    assert "┌─ stats" in stats and " score        0" in stats
    assert " level        1" in stats
    # right column previews the next piece and lists the key bindings
    right = _right_boxes(canvas.grid)
    assert "┌─ next" in right and "OOOO" in right
    assert "┌─ help" in right and " restart" in right and " quit" in right


@requires_lupa
def test_second_launch_reports_already_running(game: _Game) -> None:
    """A canvas already open is not replaced; the message line says so."""
    first = game.launch("O")

    game.command("tetris")

    assert game.api.messages == ["tetris is already running"]
    assert game.require_canvas() is first
    assert first.closed is False


# --- key mapping --------------------------------------------------------------


@requires_lupa
def test_left_right_move_and_soft_drop_steps_one_row(game: _Game) -> None:
    """left/right shift by one column; down drops one row without locking."""
    canvas = game.launch("O")

    game.press("left")
    assert _board_cells(canvas.grid, "O") == {(1, 3), (1, 4), (2, 3), (2, 4)}

    game.press("right", "right")
    assert _board_cells(canvas.grid, "O") == {(1, 5), (1, 6), (2, 5), (2, 6)}

    game.press("down")
    assert _board_cells(canvas.grid, "O") == {(2, 5), (2, 6), (3, 5), (3, 6)}


@requires_lupa
def test_space_hard_drops_to_the_floor(game: _Game) -> None:
    """space lands the piece on the bottom row and the next one spawns."""
    canvas = game.launch("O")

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
def test_up_and_x_rotate_clockwise(game: _Game) -> None:
    """up and x both advance the rotation state by one step."""
    canvas = game.launch("T")
    assert _board_cells(canvas.grid, "T") == {(1, 5), (2, 4), (2, 5), (2, 6)}

    game.press("up")
    assert _board_cells(canvas.grid, "T") == {(1, 4), (2, 4), (2, 5), (3, 4)}

    game.press("x")
    assert _board_cells(canvas.grid, "T") == {(1, 4), (1, 5), (1, 6), (2, 5)}


@requires_lupa
def test_rotation_kicks_off_the_right_wall(game: _Game) -> None:
    """A vertical I at the wall rotates back in with the -1 kick."""
    canvas = game.launch("I")

    game.press("up")  # vertical, columns 6
    assert _board_cells(canvas.grid, "I") == {(1, 6), (2, 6), (3, 6), (4, 6)}

    game.press("right", "right", "right", "right")  # offset 3 -> 7, column 10
    game.press("up")  # would stick out one column: kicked back to offset 6

    assert _board_cells(canvas.grid, "I") == {(2, 7), (2, 8), (2, 9), (2, 10)}


@requires_lupa
def test_enter_rushes_the_fall_and_locks_piece_controls(game: _Game) -> None:
    """enter commits the piece: one row per tick, no move / rotate until it
    locks; the spawned piece is controllable again."""
    canvas = game.launch("T")
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
def test_gravity_steps_on_the_level_clock(game: _Game) -> None:
    """Level 1 gravity fires on the 14th tick (15 - level), not before."""
    canvas = game.launch("O")

    game.tick(13)
    assert _board_cells(canvas.grid, "O") == {(1, 4), (1, 5), (2, 4), (2, 5)}

    game.tick(1)
    assert _board_cells(canvas.grid, "O") == {(2, 4), (2, 5), (3, 4), (3, 5)}


@requires_lupa
def test_pause_freezes_gravity_until_resumed(game: _Game) -> None:
    """p freezes the clock; the next p resumes where the counter stopped."""
    canvas = game.launch("O")

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
def test_line_clears_score_lines_and_level(game: _Game) -> None:
    """Five O pieces fill two rows: 300 points, 10 lines -> level 2."""
    canvas = game.launch("O")

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
def test_gravity_speeds_up_with_the_level(game: _Game) -> None:
    """At level 2 gravity fires on the 13th tick (max(2, 15 - level))."""
    game.launch("O")
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
def test_stack_to_the_top_ends_the_game_and_r_restarts(game: _Game) -> None:
    """Ten O pieces fill one column pair; the next spawn is game over."""
    canvas = game.launch("O")

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
def test_r_restarts_a_running_game(game: _Game) -> None:
    """r also works mid-game: score and stack are wiped."""
    canvas = game.launch("O")
    game.press("space")
    game.press("space")
    assert " score        0" in _stats(canvas.grid)

    game.press("r")

    assert _board_cells(canvas.grid, "O") == {(1, 4), (1, 5), (2, 4), (2, 5)}


# --- canvas lifecycle ---------------------------------------------------------


@requires_lupa
def test_close_callback_invalidates_the_canvas(game: _Game) -> None:
    """After on_close a racing tick is ignored and a relaunch is allowed."""
    canvas = game.launch("O")

    canvas.close_cb()
    frames = len(canvas.grids)
    canvas.tick()
    assert len(canvas.grids) == frames

    game.command("tetris")
    assert game.api.canvas is not canvas


@requires_lupa
def test_teardown_closes_the_open_canvas(game: _Game) -> None:
    """teardown dismisses the active canvas and deadens its callbacks."""
    canvas = game.launch("O")

    game.module.teardown(game.api)

    assert canvas.closed is True
    frames = len(canvas.grids)
    canvas.tick()
    assert len(canvas.grids) == frames


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
