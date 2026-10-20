"""Live-lua tests for the bundled snake extension (``snake.lua``).

The extension is executed by the real lupa runtime over the recording
fakes from :mod:`lua_game_harness`, so these tests drive the shipped Lua
file exactly as the editor would: the registered ``game-snake`` action,
the canvas callbacks (key / tick / close) and the ``snapshot()`` test
seam.  Food placement is pinned through ``snake.set_food_source`` (a Lua
closure built inside the same runtime) so every board assertion is
deterministic, and the save documents stay in an in-memory
:class:`~lua_game_harness.FakeData` store -- the real ``~/.yate`` is never
touched.

Marked ``@requires_lupa``: the whole module skips without the optional
``yate[lua]`` extra.
"""

from __future__ import annotations

import importlib.util
import json
from typing import Any

import pytest

from lua_game_harness import FakeApi, GameRuntime, requires_lupa

#: Live-lua marker: skip when the optional lupa package is not installed.
_lua_missing = importlib.util.find_spec("lupa") is None
requires_lupa = pytest.mark.skipif(
    _lua_missing, reason="lupa is not installed (live-lua group)"
)

#: The player name written into games/profile.json before every launch.
PROFILE_JSON = json.dumps({"version": 1, "player": "alice"})


def make_game(api: FakeApi | None = None) -> GameRuntime:
    """A fresh snake runtime over an api whose profile names alice."""
    holder = api if api is not None else FakeApi()
    holder.data.files["games/profile.json"] = PROFILE_JSON
    return GameRuntime("snake", holder)


def pin_food(game: GameRuntime, x: int, y: int) -> None:
    """Pin the food source to one fixed free cell (a Lua closure)."""
    fn: Any = game.runtime.execute(
        f"return function() return {{x = {x}, y = {y}}} end"
    )
    game.module.set_food_source(fn)


def pin_food_march(game: GameRuntime) -> None:
    """Pin the food source to (4,9), (5,9), ... along the starting row."""
    fn: Any = game.runtime.execute(
        "local counter = 0\n"
        "return function()\n"
        "  counter = counter + 1\n"
        "  return { x = 3 + counter, y = 9 }\n"
        "end"
    )
    game.module.set_food_source(fn)


@requires_lupa
class TestSnakeBoard:
    """Opening the canvas and the initial board state."""

    def test_game_snake_opens_the_board_canvas(self) -> None:
        game = make_game()
        canvas = game.launch()
        assert canvas.cols == 62
        assert canvas.rows == 22
        assert "\u256d\u2500 snake" in canvas.grid  # rounded "╭─ snake"
        assert "score 0" in canvas.status
        assert canvas.status.endswith("escape quits")

    def test_initial_snake_and_food_are_inside_the_board(self) -> None:
        game = make_game()
        game.launch()
        snap = game.snapshot()
        assert snap["length"] == 3
        assert snap["head_x"] == 3
        assert snap["head_y"] == 9
        assert 1 <= snap["food_x"] <= 30
        assert 1 <= snap["food_y"] <= 18


@requires_lupa
class TestSnakeMovement:
    """Turning, stepping and dying."""

    def test_reverse_direction_is_ignored(self) -> None:
        game = make_game()
        game.launch()
        pin_food(game, 30, 18)
        game.press("left")  # heading right: a 180-degree turn is refused
        game.tick(10)
        assert game.snapshot()["head_x"] == 4

    def test_up_key_moves_the_head_up_after_one_step(self) -> None:
        game = make_game()
        game.launch()
        pin_food(game, 30, 18)
        game.press("up")
        game.tick(10)
        snap = game.snapshot()
        assert snap["head_x"] == 3
        assert snap["head_y"] == 8

    def test_wall_collision_ends_the_game(self) -> None:
        game = make_game()
        game.launch()
        pin_food(game, 30, 18)
        game.press("up")
        game.tick(90)  # nine steps: from row 9 out through the top wall
        snap = game.snapshot()
        assert snap["alive"] is False
        assert "game over" in game.require_canvas().grid

    def test_self_collision_ends_the_game(self) -> None:
        game = make_game()
        game.launch()
        pin_food_march(game)
        game.tick(20)  # eat twice: length 5, head at (5,9)
        assert game.snapshot()["length"] == 5
        # Loop around the head (up, right, down, left): the final left step
        # lands on the snake's own body, which ends the run.
        for key in ("up", "right", "down", "left"):
            game.press(key)
            game.tick(10)
        assert game.snapshot()["alive"] is False


@requires_lupa
class TestSnakeRules:
    """Food, speed, pause and restart."""

    def test_eating_food_scores_and_grows(self) -> None:
        game = make_game()
        game.launch()
        pin_food(game, 4, 9)
        game.tick(10)  # one step onto the food cell
        snap = game.snapshot()
        assert snap["score"] == 10
        assert snap["length"] == 4
        # the HUD best tracks a run that overtakes the saved record
        assert snap["best"] == 10
        assert "best 10" in game.require_canvas().status
        food = (snap["food_x"], snap["food_y"])
        assert food != (4, 9)  # the food respawned somewhere else

    def test_pause_freezes_movement_and_overlays_text(self) -> None:
        game = make_game()
        game.launch()
        pin_food(game, 30, 18)
        game.press("p")
        before = (game.snapshot()["head_x"], game.snapshot()["head_y"])
        game.tick(30)
        snap = game.snapshot()
        assert (snap["head_x"], snap["head_y"]) == before
        assert "paused" in game.require_canvas().grid
        game.press("p")  # resume
        assert game.snapshot()["paused"] is False

    def test_speed_increases_with_score(self) -> None:
        game = make_game()
        game.launch()
        pin_food_march(game)
        game.tick(50)  # five eats: score 50
        snap = game.snapshot()
        assert snap["score"] == 50
        assert snap["step_ticks"] == 9

    def test_restart_resets_score_and_length(self) -> None:
        game = make_game()
        game.launch()
        pin_food_march(game)
        game.tick(60)
        game.press("up")
        game.tick(100)  # run into the wall
        assert game.snapshot()["alive"] is False
        game.press("r")
        snap = game.snapshot()
        assert snap["score"] == 0
        assert snap["length"] == 3
        assert snap["alive"] is True


@requires_lupa
class TestSnakePersistence:
    """High score board, saved best and close behaviour."""

    def test_high_score_is_saved_with_the_player_name(self) -> None:
        game = make_game()
        game.launch()
        pin_food(game, 4, 9)
        game.tick(10)  # score 10
        pin_food(game, 30, 18)
        game.press("up")
        game.tick(100)  # then die on the top wall
        document = json.loads(game.api.data.files["games/snake.json"])
        top = document["high_scores"][0]
        assert top["score"] == 10
        assert top["player"] == "alice"

    def test_relaunch_shows_the_saved_best(self) -> None:
        api = FakeApi()
        game = make_game(api)
        game.launch()
        pin_food(game, 4, 9)
        game.tick(10)
        pin_food(game, 30, 18)
        game.press("up")
        game.tick(100)  # die: best 10 hits games/snake.json
        replay = make_game(api)  # a fresh runtime over the same data store
        canvas = replay.launch()
        assert "best 10" in canvas.status
        assert replay.snapshot()["best"] == 10

    def test_close_saves_and_deadens_the_session(self) -> None:
        game = make_game()
        game.launch()
        pin_food(game, 30, 18)
        frames = len(game.require_canvas().grids)
        game.close()
        assert "games/snake.json" in game.api.data.files
        game.tick(5)
        assert len(game.require_canvas().grids) == frames
