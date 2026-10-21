"""Live-lua tests for the bundled pacman extension (``pacman.lua``).

The extension is executed by the real lupa runtime over the recording
fakes from :mod:`lua_game_harness`, so these tests drive the shipped Lua
file exactly as the editor would: the registered ``game-pacman`` action,
the canvas callbacks (key / tick / close) and the ``snapshot()`` test
seam.  Test mazes and positions are injected through ``set_maze`` /
``set_state`` (Lua closures built inside the same runtime), the ghost AI
is deterministic, and the save documents stay in an in-memory
:class:`~lua_game_harness.FakeData` store -- the real ``~/.yate`` is never
touched.

Marked ``@requires_lupa``: the whole module skips without the optional
``yate[lua]`` extra.
"""

from __future__ import annotations

import json
from typing import Any

from lua_game_harness import FakeApi, GameRuntime, requires_lupa

#: The player name written into games/profile.json before every launch.
PROFILE_JSON = json.dumps({"version": 1, "player": "alice"})


def make_game(api: FakeApi | None = None) -> GameRuntime:
    """A fresh pacman runtime over an api whose profile names alice."""
    holder = api if api is not None else FakeApi()
    holder.data.files["games/profile.json"] = PROFILE_JSON
    return GameRuntime("pacman", holder)


def inject_maze(game: GameRuntime, rows: list[str]) -> None:
    """Replace the maze with *rows* through a Lua closure."""
    literal = "{" + ", ".join(f'"{row}"' for row in rows) + "}"
    fn: Any = game.runtime.execute(
        f"return function(mod) mod.set_maze({literal}) end"
    )
    fn(game.module)


def inject_state(game: GameRuntime, literal: str) -> None:
    """Apply a ``set_state`` table written as a Lua table literal."""
    fn: Any = game.runtime.execute(
        f"return function(mod) mod.set_state({literal}) end"
    )
    fn(game.module)


def open_maze() -> list[str]:
    """A 21 x 19 open maze: power pellet left of P, open row below."""
    rows = ["#" * 19]
    rows.append("#oP" + "." * 15 + "#")
    rows.append("#" + " " * 17 + "#")
    for _ in range(17):
        rows.append("#" + "." * 17 + "#")
    rows.append("#" * 19)
    assert len(rows) == 21 and all(len(row) == 19 for row in rows)
    return rows


def one_pellet_maze() -> list[str]:
    """A 21 x 19 maze whose only pellet sits left of the P spawn."""
    wall_row = "#" + "#" * 17 + "#"
    rows = ["#" * 19]
    rows += [wall_row] * 8  # rows 2..9
    rows.append("#" + "#" * 7 + "." + "P" + "#" * 8 + "#")  # row 10
    rows.append(wall_row)  # row 11
    rows.append("#" + "#" * 7 + "   " + "#" * 7 + "#")  # row 12: pockets
    rows += [wall_row] * 8  # rows 13..20
    rows.append("#" * 19)
    assert len(rows) == 21 and all(len(row) == 19 for row in rows)
    return rows


def corridor_maze() -> list[str]:
    """A 21 x 19 maze: P at (5,10), ghosts right of it, one far pellet."""
    wall_row = "#" + "#" * 17 + "#"
    rows = ["#" * 19]
    rows += [wall_row] * 8  # rows 2..9
    rows.append("#" + "###P" + "GGGG" + "####." + "####" + "#")  # row 10
    rows += [wall_row] * 10  # rows 11..20
    rows.append("#" * 19)
    assert len(rows) == 21 and all(len(row) == 19 for row in rows)
    return rows


def maze_rows_from_grid(grid: str, rows: int) -> list[str]:
    """Strip the canvas frame off the rendered grid (*rows* maze rows)."""
    lines = grid.splitlines()
    return [line[1:-1] for line in lines[1 : rows + 1]]


@requires_lupa
class TestPacmanCanvas:
    """Opening the canvas and the built-in maze contract."""

    def test_game_pacman_opens_the_maze_canvas(self) -> None:
        game = make_game()
        canvas = game.launch()
        assert canvas.cols == 41
        assert canvas.rows == 29
        assert "\u256d" in canvas.grid  # rounded "╭" top border
        assert "\u2588" in canvas.grid  # "█" wall block
        assert "score 0" in canvas.status
        assert canvas.status.endswith("escape quits")

    def test_builtin_maze_meets_the_contract(self) -> None:
        game = make_game()
        canvas = game.launch()
        rows = maze_rows_from_grid(canvas.grid, 27)
        assert len(rows) == 27
        assert all(len(row) == 39 for row in rows)
        # 1) the border is all walls
        assert set(rows[0]) == {"█"} and set(rows[-1]) == {"█"}
        assert all(row[0] == "█" and row[-1] == "█" for row in rows)
        flat = "".join(rows)
        # 2) four power pellets, exactly one pacman
        assert flat.count("●") == 4
        assert flat.count("◉") == 1
        # 3) every pellet is reachable from the spawn (BFS)
        start = flat.index("◉")
        width = 39
        passable = set(flat) - {"█", "▒"}
        seen = {start}
        frontier = [start]
        while frontier:
            here = frontier.pop()
            x, y = here % width, here // width
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if 0 <= nx < width and 0 <= ny < 27:
                    there = ny * width + nx
                    if there not in seen and flat[there] in passable:
                        seen.add(there)
                        frontier.append(there)
        pellets = [i for i, char in enumerate(flat) if char in "·●"]
        assert all(i in seen for i in pellets)


@requires_lupa
class TestPacmanMovement:
    """Stepping, eating and the frightened mode."""

    def test_pacman_moves_one_tile_per_interval(self) -> None:
        game = make_game()
        game.launch()
        assert game.snapshot()["pac_x"] == 20
        game.press("left")
        game.tick(4)
        assert game.snapshot()["pac_x"] == 19

    def test_pellet_is_eaten_and_scored(self) -> None:
        game = make_game()
        game.launch()
        game.press("left")
        game.tick(4)
        snap = game.snapshot()
        assert snap["pellets"] == 772
        assert snap["score"] == 10

    def test_power_pellet_sets_fright_mode(self) -> None:
        game = make_game()
        game.launch()
        inject_maze(game, open_maze())
        assert game.snapshot()["pac_x"] == 3  # spawn next to the "o"
        game.press("left")
        game.tick(4)
        snap = game.snapshot()
        assert snap["fright_ticks"] > 0
        assert all(ghost["mode"] == "fright" for ghost in snap["ghosts"])


@requires_lupa
class TestPacmanGhosts:
    """Eating frightened ghosts and losing lives to hungry ones."""

    def test_frightened_ghost_is_eaten_and_scored_200(self) -> None:
        game = make_game()
        game.launch()
        inject_maze(game, corridor_maze())  # no pellets: a clean +200
        inject_state(
            game,
            "{ ghosts = { { x = 6, y = 10, mode = 'fright' } } }",
        )
        game.press("right")
        game.tick(4)  # pacman steps onto the frightened ghost
        snap = game.snapshot()
        assert snap["score"] == 200
        assert snap["ghosts"][0]["mode"] == "eyes"

    def test_ghost_collision_costs_a_life(self) -> None:
        game = make_game()
        game.launch()
        inject_state(
            game,
            "{ pac = { x = 10, y = 6, dir = { x = -1, y = 0 } },"
            " ghosts = { { x = 9, y = 6, mode = 'chase' } } }",
        )
        game.press("left")
        game.tick(4)
        snap = game.snapshot()
        assert snap["lives"] == 2
        assert snap["pac_x"] == 20  # back on the spawn tile
        assert snap["pac_y"] == 26

    def test_last_life_ends_the_game_and_r_restarts(self) -> None:
        game = make_game()
        game.launch()
        inject_state(
            game,
            "{ lives = 1,"
            " pac = { x = 10, y = 4, dir = { x = -1, y = 0 } },"
            " ghosts = { { x = 9, y = 4, mode = 'chase' } } }",
        )
        game.press("left")
        game.tick(4)
        snap = game.snapshot()
        assert snap["alive"] is False
        assert "press r" in game.require_canvas().grid
        game.press("r")
        snap = game.snapshot()
        assert snap["lives"] == 3
        assert snap["level"] == 1
        assert snap["alive"] is True


@requires_lupa
class TestPacmanLevels:
    """Level clear, pause and the clocks."""

    def test_clearing_all_pellets_advances_the_level(self) -> None:
        game = make_game()
        game.launch()
        inject_maze(game, one_pellet_maze())
        game.press("left")
        game.tick(4)  # the one pellet: 10 + the 500 clear bonus
        snap = game.snapshot()
        assert snap["level"] == 2
        assert snap["score"] == 510

    def test_pause_freezes_every_clock(self) -> None:
        game = make_game()
        game.launch()
        game.press("p")
        before = (game.snapshot()["pac_x"], game.snapshot()["pac_y"])
        game.tick(40)
        snap = game.snapshot()
        assert (snap["pac_x"], snap["pac_y"]) == before


@requires_lupa
class TestPacmanPersistence:
    """High score board, stats and the saved best."""

    def test_high_score_saved_with_player_and_games(self) -> None:
        game = make_game()
        game.launch()
        inject_state(
            game,
            "{ lives = 1,"
            " pac = { x = 10, y = 4, dir = { x = -1, y = 0 } },"
            " ghosts = { { x = 9, y = 4, mode = 'chase' } } }",
        )
        game.press("left")
        game.tick(4)  # last life gone: the run is recorded
        document = json.loads(game.api.data.files["games/pacman.json"])
        assert document["version"] == 1
        assert document["stats"]["games"] == 1
        assert document["high_scores"][0]["player"] == "alice"

    def test_relaunch_shows_saved_best(self) -> None:
        api = FakeApi()
        game = make_game(api)
        game.launch()
        game.press("left")
        game.tick(4)  # score 10 on the built-in maze
        inject_maze(game, corridor_maze())  # no pellets, ghosts at (6..9,10)
        inject_state(game, "{ lives = 1 }")
        game.press("right")
        game.tick(4)  # die on the chase ghost: best 10 is recorded
        replay = make_game(api)  # a fresh runtime over the same data store
        replay.launch()
        assert replay.snapshot()["best"] == 10
