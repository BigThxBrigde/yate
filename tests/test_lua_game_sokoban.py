"""Live-lua tests for the bundled sokoban extension (``sokoban.lua``).

The extension is executed by the real lupa runtime over the recording
fakes from :mod:`lua_game_harness`, so these tests drive the shipped Lua
file exactly as the editor would: the registered ``game-sokoban`` action,
the canvas key callback and the ``snapshot()`` / ``load_level()`` /
``level_rows()`` / ``solution()`` test seams.  Save documents stay in an
in-memory :class:`~lua_game_harness.FakeData` store -- the real ``~/.yate``
is never touched.

Levels 1-6 are handwritten (Microban 1-5 plus the teaching level; level 1
is solved through a fixed BFS-verified 33-key solution, level 6 drives the
push / undo coverage).  Levels 7-120 come from the reverse-pull generator:
it only performs legal pulls starting from a solved board, so replaying
``solution(n)`` -- the recorded pull trace reversed and direction-negated
-- must solve the level by construction; a sample of generated levels is
replayed key by key to pin that contract.

Marked ``@requires_lupa``: the whole module skips without the optional
``yate[lua]`` extra.
"""

from __future__ import annotations

import json
import re
from typing import Any, cast

from lua_game_harness import (
    FakeApi,
    GameRuntime,
    bundled_source,
    lua_to_python,
    requires_lupa,
)

#: A BFS-verified 33-move / 9-push solution of built-in level 1.
LEVEL1_SOLUTION: list[str] = [
    "down", "left", "up", "right", "right", "right", "down", "left",
    "up", "left", "left", "down", "down", "right", "up", "left", "up",
    "right", "up", "up", "left", "down", "right", "down", "down",
    "right", "right", "up", "left", "down", "left", "up", "up",
]
assert len(LEVEL1_SOLUTION) == 33

#: Handwritten levels at the front of the set.
HANDWRITTEN_COUNT: int = 6

#: Total level count (6 handwritten + 114 generated).
TOTAL_LEVELS: int = 120

#: Generated levels whose solution is replayed key by key.
REPLAY_SAMPLES: list[int] = [7, 23, 45, 66, 88, 99, 111, 120]


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


def key_for(op: dict[str, Any]) -> str:
    """The Textual key name that walks one solution step's direction."""
    if op["dx"] == -1:
        return "left"
    if op["dx"] == 1:
        return "right"
    if op["dy"] == -1:
        return "up"
    assert op["dy"] == 1, f"malformed solution step: {op}"
    return "down"


def assert_well_formed(rows: list[str], context: str) -> None:
    """One player, as many crates as goals, within the 37 x 17 area."""
    joined = "\n".join(rows)
    assert len(rows) <= 17, f"{context}: too many rows"
    assert joined.count("@") + joined.count("+") == 1, (
        f"{context}: expected exactly one player"
    )
    assert joined.count("$") + joined.count("*") == joined.count(
        "."
    ) + joined.count("*"), f"{context}: crate / goal count mismatch"
    for row in rows:
        assert len(row) <= 37, f"{context}: row too wide"


def rows_of(game: GameRuntime, index: int) -> list[str]:
    """``level_rows(index)`` as a plain Python list of row strings."""
    rows = cast("list[str] | None", lua_to_python(game.module.level_rows(index)))
    assert isinstance(rows, list), f"level {index}: level_rows() not a table"
    return rows


def solution_of(game: GameRuntime, index: int) -> list[dict[str, Any]]:
    """``solution(index)`` as plain Python steps (non-empty for generated)."""
    solution = cast(
        "list[dict[str, Any]] | None", lua_to_python(game.module.solution(index))
    )
    assert isinstance(solution, list), f"level {index}: no solution exposed"
    assert len(solution) > 0, f"level {index}: empty solution"
    return solution


@requires_lupa
class TestSokobanCanvas:
    """Opening the canvas and the built-in level data."""

    def test_game_sokoban_opens_the_level_canvas(self) -> None:
        game = make_game()
        canvas = game.launch()
        assert canvas.cols == 41
        assert canvas.rows == 22
        lines = canvas.grid.split("\n")
        assert len(lines) == 22
        assert "sokoban" in lines[0]
        assert "level 1/120" in lines[18]
        # two help rows carry the four key words in full
        assert "u undo" in lines[19]
        assert "r restart" in lines[19]
        assert "n next" in lines[20]
        assert "p pause" in lines[20]
        assert canvas.status.endswith("escape quits")

    def test_builtin_levels_are_well_formed(self) -> None:
        levels = parse_builtin_levels()
        assert len(levels) == HANDWRITTEN_COUNT
        for index, rows in enumerate(levels, start=1):
            assert_well_formed(rows, f"handwritten level {index}")

    def test_every_level_is_well_formed(self) -> None:
        """All 120 levels (generated ones built on demand) pass the checks."""
        game = make_game()
        game.launch()
        for index in range(1, TOTAL_LEVELS + 1):
            assert_well_formed(rows_of(game, index), f"level {index}")

    def test_solution_seam_only_covers_generated_levels(self) -> None:
        game = make_game()
        game.launch()
        for index in range(1, HANDWRITTEN_COUNT + 1):
            assert game.module.solution(index) is None
        for index in (HANDWRITTEN_COUNT + 1, 60, TOTAL_LEVELS):
            for op in solution_of(game, index):
                assert set(op) == {"dx", "dy", "push"}
                assert op["push"] in (True, False)


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
        game.module.load_level(TOTAL_LEVELS)
        solution = solution_of(game, TOTAL_LEVELS)
        game.press(*[key_for(op) for op in solution])
        assert game.snapshot()["solved"] is True
        game.press("n")
        assert "all levels cleared" in game.require_canvas().grid
        game.press("r")
        snap = game.snapshot()
        assert snap["level"] == 1
        assert snap["moves"] == 0


@requires_lupa
class TestGeneratedLevels:
    """The reverse-pull generator and its solvability contract."""

    def test_totals_and_clamped_levels_in_the_snapshot(self) -> None:
        game = make_game()
        game.launch()
        game.module.load_level(9999)
        snap = game.snapshot()
        assert snap["total"] == TOTAL_LEVELS
        assert snap["level"] == TOTAL_LEVELS
        game.module.load_level(0)
        assert game.snapshot()["level"] == 1

    def test_generated_levels_are_deterministic(self) -> None:
        """The same index always regenerates the exact same board."""
        game = make_game()
        game.launch()
        for index in (7, 45):
            assert rows_of(game, index) == rows_of(game, index)

    def test_generated_start_state_is_not_already_solved(self) -> None:
        game = make_game()
        game.launch()
        for index in REPLAY_SAMPLES:
            game.module.load_level(index)
            snap = game.snapshot()
            assert snap["goals"] >= 2
            assert snap["solved"] is False, (
                f"generated level {index} starts solved"
            )
            assert any(not box["on_goal"] for box in snap["boxes"])

    def test_replaying_the_solution_solves_generated_levels(self) -> None:
        """The reversed pull trace pushes every crate back onto its goal."""
        for index in REPLAY_SAMPLES:
            game = make_game()
            game.launch()
            game.module.load_level(index)
            solution = solution_of(game, index)
            game.press(*[key_for(op) for op in solution])
            snap = game.snapshot()
            assert snap["solved"] is True, (
                f"level {index} not solved by its own solution"
            )
            assert all(box["on_goal"] for box in snap["boxes"])


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

    def test_out_of_range_saved_level_is_clamped(self) -> None:
        api = FakeApi()
        api.data.files["games/sokoban.json"] = json.dumps(
            {"version": 1, "level": 999, "completed": [], "moves": 0,
             "pushes": 0}
        )
        game = GameRuntime("sokoban", api)
        game.launch()
        assert game.snapshot()["level"] == TOTAL_LEVELS

    def test_saved_completed_levels_beyond_the_set_are_dropped(self) -> None:
        api = FakeApi()
        api.data.files["games/sokoban.json"] = json.dumps(
            {"version": 1, "level": 1, "completed": [1, 500], "moves": 0,
             "pushes": 0}
        )
        game = GameRuntime("sokoban", api)
        game.launch()
        assert game.snapshot()["completed"] == [1]
