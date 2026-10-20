"""Live-lua tests for the bundled nethack extension (``nethack.lua``).

The extension runs on the real lupa runtime over the recording fakes from
:mod:`lua_game_harness`, exactly as the editor would drive it: the
registered ``game-nethack`` action, the canvas key callback and the
``snapshot()`` test seam.  Dungeons are pinned through ``set_seed`` and
scenarios are crafted through ``load_state`` (the save-structure seam),
so every assertion is deterministic.  Save documents stay in an
in-memory :class:`~lua_game_harness.FakeData` store -- the real
``~/.yate`` is never touched.

Marked ``@requires_lupa``: the whole module skips without the optional
``yate[lua]`` extra.
"""

from __future__ import annotations

import json
from typing import Any

from lua_game_harness import FakeApi, GameRuntime, requires_lupa

#: The player name written into games/profile.json before every launch.
PROFILE_JSON = json.dumps({"version": 1, "player": "alice"})

#: Save-document key holding the resumable run state.
SAVE_JSON = "games/nethack.json"


def make_game(api: FakeApi | None = None) -> GameRuntime:
    """A fresh nethack runtime over an api whose profile names alice."""
    holder = api if api is not None else FakeApi()
    holder.data.files["games/profile.json"] = PROFILE_JSON
    return GameRuntime("nethack", holder)


def map_row(overrides: dict[int, str] | None = None) -> str:
    """One semantic 50-char map row (floor, with walls placed on top)."""
    cells = ["."] * 50
    for x, ch in (overrides or {}).items():
        cells[x - 1] = ch
    return "".join(cells)


def make_state(
    player_pos: tuple[int, int],
    *,
    hp: int = 10,
    rows: list[str] | None = None,
    monsters: list[dict[str, Any]] | None = None,
    items: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """A save-structure table (the ``load_state`` seam) for one scenario."""
    return {
        "version": 1,
        "depth": 1,
        "turn": 0,
        "seed": 7,
        "hp": hp,
        "max_hp": 10,
        "gold": 0,
        "weapon": 0,
        "rng": 12345,
        "player_pos": list(player_pos),
        "floor": rows if rows is not None else [map_row() for _ in range(18)],
        "monsters": monsters or [],
        "items": items or [],
    }


def inject(game: GameRuntime, state: dict[str, Any]) -> Any:
    """``load_state`` through the JSON string seam.

    Lupa hands nested Python lists over as opaque objects, so the
    save-structure table travels as JSON (the exact save-file encoding).
    """
    return game.module.load_state(json.dumps(state))


@requires_lupa
class TestNethackCanvas:
    """Opening the canvas and the initial dungeon."""

    def test_game_nethack_opens_the_map_canvas(self) -> None:
        game = make_game()
        canvas = game.launch()
        assert canvas.cols == 52
        assert canvas.rows == 22
        assert "nethack" in canvas.grid
        assert "depth 1" in canvas.grid
        assert "hp 10/10" in canvas.grid
        assert "depth 1" in canvas.status
        assert canvas.status.endswith("escape quits")

    def test_map_is_deterministic_for_a_seed(self) -> None:
        first = make_game()
        first.module.set_seed(4242)
        first.launch()
        second = make_game()
        second.module.set_seed(4242)
        second.launch()
        left, right = first.snapshot(), second.snapshot()
        assert (left["player_x"], left["player_y"]) == (
            right["player_x"],
            right["player_y"],
        )
        assert left["monsters"] == right["monsters"]


@requires_lupa
class TestNethackTurns:
    """Movement, walls, combat and waiting."""

    def test_player_moves_onto_floor(self) -> None:
        game = make_game()
        inject(game,make_state((5, 9)))
        game.launch()
        game.press("right")
        snap = game.snapshot()
        assert snap["player_x"] == 6
        assert snap["turn"] == 1

    def test_wall_blocks_movement_without_a_turn(self) -> None:
        game = make_game()
        rows = [map_row() for _ in range(18)]
        rows[8] = map_row({5: "#"})
        inject(game,make_state((4, 9), rows=rows))
        game.launch()
        game.press("right")
        snap = game.snapshot()
        assert snap["player_x"] == 4
        assert snap["turn"] == 0

    def test_bumping_a_monster_attacks_it(self) -> None:
        game = make_game()
        monster = {"x": 5, "y": 9, "kind": "paw", "hp": 1}
        inject(game,
            make_state((4, 9), monsters=[monster])
        )
        game.launch()
        game.press("right")
        assert len(game.snapshot()["monsters"]) == 0

    def test_monster_attacks_back_and_can_kill_the_player(self) -> None:
        game = make_game()
        monster = {"x": 5, "y": 9, "kind": "paw", "hp": 9}
        inject(game,make_state((4, 9), hp=1, monsters=[monster]))
        game.launch()
        game.press("space")
        snap = game.snapshot()
        assert snap["alive"] is False
        assert "rest in peace" in game.require_canvas().grid


@requires_lupa
class TestNethackItems:
    """Grabbing loot and descending the stairs."""

    def test_grab_collects_gold_potion_and_weapon(self) -> None:
        game = make_game()
        items = [
            {"x": 5, "y": 9, "kind": "gold", "amount": 12},
            {"x": 5, "y": 9, "kind": "potion"},
            {"x": 5, "y": 9, "kind": "weapon"},
        ]
        inject(game,make_state((5, 9), hp=5, items=items))
        game.launch()
        game.press("g")
        snap = game.snapshot()
        assert snap["gold"] == 12
        assert snap["hp"] == 8  # 5 + potion 3
        assert snap["weapon"] == 1

    def test_enter_on_stairs_descends_and_heals(self) -> None:
        game = make_game()
        rows = [map_row() for _ in range(18)]
        rows[8] = map_row({6: ">"})
        inject(game,make_state((6, 9), hp=5, rows=rows))
        game.launch()
        game.press("enter")
        snap = game.snapshot()
        assert snap["depth"] == 2
        assert snap["max_hp"] == 12

    def test_enter_off_stairs_does_nothing(self) -> None:
        game = make_game()
        inject(game,make_state((5, 9)))
        game.launch()
        game.press("enter")
        snap = game.snapshot()
        assert snap["depth"] == 1
        assert snap["turn"] == 0


@requires_lupa
class TestNethackGlyphs:
    """Nerd icons by default with an ASCII fallback."""

    def test_default_glyphs_are_nerd_icons(self) -> None:
        game = make_game()
        canvas = game.launch()
        assert game.snapshot()["glyphs"] == "nerd"
        assert any(byte > 0x7F for byte in canvas.grid.encode("utf-8"))

    def test_v_toggles_ascii_glyphs_and_persists(self) -> None:
        game = make_game()
        game.launch()
        game.press("v")
        snap = game.snapshot()
        assert snap["glyphs"] == "ascii"
        assert "@" in game.require_canvas().grid
        document = json.loads(game.api.data.files[SAVE_JSON])
        assert document["glyphs"] == "ascii"


@requires_lupa
class TestNethackPersistence:
    """Per-turn saves, resume on relaunch and death clearing."""

    def test_turn_state_is_saved_and_resumed(self) -> None:
        api = FakeApi()
        game = make_game(api)
        inject(game,make_state((5, 9)))
        game.launch()
        game.press("right", "right")
        game.close()
        document = json.loads(api.data.files[SAVE_JSON])
        assert document["save"]["turn"] == 2
        replay = make_game(api)  # a fresh runtime over the same data store
        replay.launch()
        snap = replay.snapshot()
        assert snap["turn"] == 2
        assert snap["depth"] == 1
        assert snap["player_x"] == 7

    def test_death_clears_the_save(self) -> None:
        game = make_game()
        monster = {"x": 5, "y": 9, "kind": "paw", "hp": 9}
        inject(game,make_state((4, 9), hp=1, monsters=[monster]))
        game.launch()
        game.press("space")
        assert game.snapshot()["alive"] is False
        assert SAVE_JSON not in game.api.data.files
        game.press("r")
        snap = game.snapshot()
        assert snap["depth"] == 1
        assert snap["alive"] is True

    def test_write_failure_is_reported_once_and_does_not_stop_the_game(self) -> None:
        """A refusing data store costs one notice, never a turn or a crash."""
        api = FakeApi()
        game = make_game(api)
        inject(game, make_state((5, 9)))
        api.data.fail_writes = True

        game.launch()
        game.press("right", "right")

        assert game.snapshot()["turn"] == 2
        assert api.messages.count("save failed: nethack") == 1
