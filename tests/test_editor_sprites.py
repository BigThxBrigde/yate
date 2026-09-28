"""Tests for the screensaver sprite pack (rendering + registry)."""

from __future__ import annotations

import random
from typing import cast

import pytest

from yate.editor_sprites import characters
from yate.editor_sprites.render import render_rows, walk_x

RED = "#ff0000"
BLUE = "#0000ff"


class TestRenderRows:
    """Half-block mapping: two pixel rows per text row, four glyph forms."""

    def test_same_color_upper_lower_solid_block(self) -> None:
        rows = render_rows(("RR", "RR"), {"R": RED})
        assert rows == [[("█", RED), ("█", RED)]]

    def test_different_colors_uses_upper_fg_on_lower_bg(self) -> None:
        rows = render_rows(("AA", "BB"), {"A": RED, "B": BLUE})
        assert rows == [[("▀", f"{RED} on {BLUE}"), ("▀", f"{RED} on {BLUE}")]]

    def test_upper_only_is_top_half_block(self) -> None:
        rows = render_rows(("AA", ".."), {"A": RED})
        assert rows == [[("▀", RED), ("▀", RED)]]

    def test_lower_only_is_bottom_half_block(self) -> None:
        rows = render_rows(("..", "BB"), {"B": BLUE})
        assert rows == [[("▄", BLUE), ("▄", BLUE)]]

    def test_transparent_is_blank_cell(self) -> None:
        rows = render_rows(("..", ".."), {"A": RED})
        assert rows == [[(" ", ""), (" ", "")]]

    def test_odd_row_count_renders_last_row_as_upper_half(self) -> None:
        rows = render_rows(("AA", "..", "AA"), {"A": RED})
        assert len(rows) == 2
        assert rows[1] == [("▀", RED), ("▀", RED)]

    def test_row_count_is_half_pixel_rows_ceil(self) -> None:
        assert len(render_rows(("A", "A", "A"), {"A": RED})) == 2


class TestWalkX:
    """Left-to-right walking with wraparound past both screen edges."""

    def test_starts_fully_offscreen_left(self) -> None:
        assert walk_x(0, 80, 14) == -14

    def test_advances_one_column_per_tick(self) -> None:
        assert walk_x(1, 80, 14) == -13

    def test_enters_screen_when_left_edge_reaches_zero(self) -> None:
        assert walk_x(14, 80, 14) == 0

    def test_wraps_after_fully_exiting_right(self) -> None:
        # travel = 80 + 14: tick 93 -> 79 (left edge's last on-screen
        # column), tick 94 -> wrapped to the starting position again.
        assert walk_x(93, 80, 14) == 79
        assert walk_x(94, 80, 14) == -14


class TestRegistry:
    """Roster invariants: geometry, palettes, completeness."""

    def test_character_names_count(self) -> None:
        assert len(characters.character_names()) == 27

    def test_every_sprite_has_two_or_more_frames(self) -> None:
        for sprite in characters.CHARACTERS.values():
            assert len(sprite.frames) >= 2

    def test_frames_are_uniform_within_each_sprite(self) -> None:
        for name, sprite in characters.CHARACTERS.items():
            widths = {len(row) for frame in sprite.frames for row in frame}
            heights = {len(frame) for frame in sprite.frames}
            assert len(widths) == 1, name
            assert len(heights) == 1, name

    def test_palette_keys_cover_all_frame_characters(self) -> None:
        for name, sprite in characters.CHARACTERS.items():
            for frame in sprite.frames:
                for row in frame:
                    assert set(row) <= set(sprite.palette) | {"."}, name

    def test_every_frame_renders(self) -> None:
        for name, sprite in characters.CHARACTERS.items():
            for frame in sprite.frames:
                rows = render_rows(frame, sprite.palette)
                assert len(rows) == -(-len(frame) // 2), name
                for cells in rows:
                    assert all(isinstance(g, str) for g, _ in cells)

    def test_ghost_variants_share_frames_and_differ_in_color(self) -> None:
        blinky = characters.get_character("ghost_blinky")
        clyde = characters.get_character("ghost_clyde")
        assert blinky.frames == clyde.frames
        assert blinky.palette["C"] != clyde.palette["C"]

    def test_get_character_unknown_name_raises(self) -> None:
        with pytest.raises(KeyError):
            characters.get_character("nokia_snake")


class TestShuffleOrder:
    """Playlist shuffling: permutation, no adjacent repeats, boundary."""

    NAMES = ("mario", "goomba", "slime", "frog", "jax")

    def test_result_is_a_permutation(self) -> None:
        rng = random.Random(42)
        order = characters.shuffle_order(self.NAMES, rng)
        assert sorted(order) == sorted(self.NAMES)

    def test_no_adjacent_duplicates(self) -> None:
        rng = random.Random(42)
        names = list(characters.character_names())
        for _ in range(500):
            order = characters.shuffle_order(names, rng)
            assert all(a != b for a, b in zip(order, order[1:]))

    def test_avoid_excludes_previous_cycle_last(self) -> None:
        rng = random.Random(7)
        for _ in range(200):
            order = characters.shuffle_order(self.NAMES, rng, avoid="mario")
            assert order[0] != "mario"

    def test_single_entry_list_passes_through(self) -> None:
        rng = random.Random(1)
        assert characters.shuffle_order(["mario"], rng) == ["mario"]
        # a single name can never avoid a replay -- must not hang
        assert characters.shuffle_order(["mario"], rng, avoid="mario") == ["mario"]

    def test_unsalvageable_multiset_returns_as_is(self) -> None:
        """A multiset with no adjacency-free order returns without looping.

        Three marios and one luigi can never avoid adjacent duplicates
        (pigeonhole), so retrying would hang the spawn tick forever.
        """
        rng = random.Random(42)
        names = ("mario", "mario", "mario", "luigi")
        assert characters.shuffle_order(names, rng) == list(names)

    def test_rejection_sampling_is_capped(self) -> None:
        """Rejection sampling gives up after 1000 tries instead of stalling.

        A stub shuffle that always leaves the order untouched forces every
        retry to fail on this pigeonhole-passing but adjacency-duplicated
        list, so only the hard cap can end the loop (PR #33 review).
        """
        class _StuckRng:
            def shuffle(self, order: list[str]) -> None:
                pass  # never rearranges: every retry is rejected

        stuck = cast(random.Random, _StuckRng())
        names = ("a", "a", "b")
        assert characters.shuffle_order(names, stuck) == list(names)

    def test_barely_satisfiable_multiset_terminates(self) -> None:
        """A tight multiset with avoid returns a permutation every time.

        Three a's against two b's and two c's plus ``avoid="b"`` leaves
        only a handful of valid orders; the 1000-retry cap guarantees the
        call always comes back (PR #33 review).
        """
        rng = random.Random(42)
        names = ("a", "a", "a", "b", "b", "c", "c")
        for _ in range(50):
            order = characters.shuffle_order(names, rng, avoid="b")
            assert sorted(order) == sorted(names)
