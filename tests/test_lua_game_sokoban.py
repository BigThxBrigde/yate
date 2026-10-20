"""Live-lua tests for the bundled sokoban extension (``sokoban.lua``).

The extension is executed by the real lupa runtime over the recording
fakes from :mod:`lua_game_harness`, so these tests drive the shipped Lua
file exactly as the editor would: the registered ``game-sokoban`` action,
the canvas key callback and the ``snapshot()`` / ``load_level()`` test
seams.  Save documents stay in an in-memory
:class:`~lua_game_harness.FakeData` store -- the real ``~/.yate`` is
never touched.

Level 1 (Microban #1) is solved in tests through a fixed 22-key solution;
level 6 is the one-move teaching level used for push / undo coverage.

Marked ``@requires_lupa``: the whole module skips without the optional
``yate[lua]`` extra.
"""

from __future__ import annotations

import json
import re
from typing import Any

from lua_game_harness import FakeApi, GameRuntime, bundled_source, requires_lupa

#: A BFS-verified 33-move / 9-push solution of built-in level 1.
LEVEL1_SOLUTION: list[str] = [
    "down", "left", "up", "right", "right", "right", "down", "left",
    "up", "left", "left", "down", "down", "right", "up", "left", "up",
    "right", "up", "up", "left", "down", "right", "down", "down",
    "right", "right", "up", "left", "down", "left", "up", "up",
]
assert len(LEVEL1_SOLUTION) == 33


def make_game(api: FakeApi | None = None) -> GameRuntime:
    """A fresh sokoban runtime over a recording api."""
    return GameRuntime("sokoban", api)


def parse_builtin_levels() -> list[list[str]]:
    """The LEVELS table rows, extracted from the shipped Lua source."""
    source = bundled_source("sokoban")
    match = re.search(r"local LEVELS = \{(.*?)\n\}", source, re.S)
    assert match is not None, "LEVELS table not found in sokoban.lua"
    levels: list[list[str]] = []
    for block in re.findall(r"\{([^{}]*)\}", match.group(1)):
        levels.append(re.findall(r'"([^"]*)"', block))
    return levels


@requires_lupa
class TestSokobanCanvas:
    """Opening the canvas and the built-in level data."""

    def test_game_sokoban_opens_the_level_canvas(self) -> None:
        game = make_game()
        canvas = game.launch()
        assert canvas.cols == 23
        assert canvas.rows == 17
        lines = canvas.grid.split("\n")
        assert "sokoban" in lines[0]
        assert "level 1/6" in lines[13]
        # two help rows carry the four key words in full
        assert "r restart" in lines[14]
        assert "n next" in lines[15]
        assert canvas.status.endswith("escape quits")

    def test_builtin_levels_are_well_formed(self) -> None:
        levels = parse_builtin_levels()
        assert len(levels) == 6
        for rows in levels:
            joined = "\n".join(rows)
            assert joined.count("@") + joined.count("+") == 1
            assert joined.count("$") + joined.count("*") == joined.count(
                "."
            ) + joined.count("*")
            assert len(rows) <= 12
            for row in rows:
                assert len(row) <= 21


@requires_lupa
class TestSokobanRules:
    """Walking, pushing, undo, restart and level advance."""

    def test_walk_moves_the_player_once(self) -> None:
        game = make_game()
        game.launch()
        game.module.load_level(6)
        assert game.snapshot()["player_x"] == 3
        game.press("left")
        snap = game.snapshot()
        assert snap["player_x"] == 2
        assert snap["moves"] == 1

    def test_pushing_a_box_onto_a_goal_marks_it_solved(self) -> None:
        game = make_game()
        game.launch()
        game.module.load_level(6)
        game.press("right")
        snap = game.snapshot()
        assert snap["solved"] is True
        assert snap["pushes"] == 1
        assert snap["completed"] == [6]

    def test_pushing_the_crate_off_the_goal_unsolves_the_level(self) -> None:
        """A second push leaves the goal empty again; solved must follow."""
        game = make_game()
        game.launch()
        game.module.load_level(6)
        game.press("right", "right")
        snap = game.snapshot()
        assert snap["solved"] is False
        assert snap["completed"] == {}

    def test_box_against_a_wall_does_not_move(self) -> None:
        game = make_game()
        game.launch()  # level 1: crate at (4,5), wall at (6,5)
        game.press("down", "right", "right")
        snap = game.snapshot()
        assert snap["moves"] == 2  # the blocked push does not count
        assert snap["player_x"] == 4
        crate = [box for box in snap["boxes"] if box["y"] == 5]
        assert crate[0]["x"] == 5

    def test_undo_restores_the_previous_position(self) -> None:
        game = make_game()
        game.launch()
        game.module.load_level(6)
        game.press("right")  # push the crate onto the goal
        game.press("u")
        snap = game.snapshot()
        assert snap["player_x"] == 3
        assert snap["boxes"][0]["x"] == 4
        assert snap["moves"] == 0
        assert snap["pushes"] == 0
        assert snap["undo_depth"] == 0

    def test_undo_after_solving_rolls_the_level_back(self) -> None:
        """Undoing the solving push revives the level (no skipped progress)."""
        game = make_game()
        game.launch()
        game.module.load_level(6)
        game.press("right")
        assert game.snapshot()["solved"] is True

        game.press("u")

        snap = game.snapshot()
        assert snap["solved"] is False
        assert snap["completed"] == {}
        saved = json.loads(game.api.data.files["games/sokoban.json"])
        assert saved["completed"] == []

    def test_undo_at_start_is_a_no_op(self) -> None:
        game = make_game()
        game.launch()
        game.press("u")
        snap = game.snapshot()
        assert snap["player_x"] == 3
        assert snap["moves"] == 0
        assert snap["undo_depth"] == 0

    def test_restart_restores_the_level_layout(self) -> None:
        game = make_game()
        game.launch()
        game.module.load_level(6)
        game.press("right", "right")
        game.press("r")
        snap = game.snapshot()
        assert snap["moves"] == 0
        assert snap["solved"] is False
        assert snap["player_x"] == 3
        assert snap["boxes"][0]["x"] == 4

    def test_next_level_only_after_solving(self) -> None:
        game = make_game()
        game.launch()
        game.press("n")
        assert game.snapshot()["level"] == 1
        game.press(*LEVEL1_SOLUTION)
        game.press("n")
        assert game.snapshot()["level"] == 2

    def test_last_level_cleared_reports_and_restarts(self) -> None:
        game = make_game()
        game.launch()
        game.module.load_level(6)
        game.press("right")
        game.press("n")
        assert "all levels cleared" in game.require_canvas().grid
        game.press("r")
        snap = game.snapshot()
        assert snap["level"] == 1
        assert snap["moves"] == 0


@requires_lupa
class TestSokobanPersistence:
    """Progress saved to games/sokoban.json and resumed."""

    def test_progress_is_saved_and_resumed(self) -> None:
        api = FakeApi()
        game = make_game(api)
        game.launch()
        game.press(*LEVEL1_SOLUTION)
        assert game.snapshot()["solved"] is True
        game.close()
        document: dict[str, Any] = json.loads(
            api.data.files["games/sokoban.json"]
        )
        assert document["level"] == 2
        assert document["completed"] == [1]
        assert document["moves"] == 33
        assert document["pushes"] == 8
        replay = GameRuntime("sokoban", api)
        replay.launch()
        assert replay.snapshot()["level"] == 2

    def test_moves_and_pushes_accumulate_across_levels(self) -> None:
        api = FakeApi()
        game = make_game(api)
        game.launch()
        game.press(*LEVEL1_SOLUTION)  # 33 moves / 8 pushes on level 1
        game.press("n")  # advance to level 2, counters carried over
        game.press("right")  # one more move on level 2 (player at (4,3))
        game.close()
        document: dict[str, Any] = json.loads(
            api.data.files["games/sokoban.json"]
        )
        assert document["moves"] == 34
        assert document["pushes"] == 8
