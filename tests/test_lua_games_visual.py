"""Frame-level visual guards for the bundled games (the alignment contract).

The per-game modules assert behaviour; this module asserts what the user
actually sees: every rendered row is exactly the canvas width in display
columns, the box borders line up column-for-column, and no game falls back to
ASCII placeholders where Unicode glyphs are the contract.
"""

from __future__ import annotations

from lua_game_harness import FakeApi, GameRuntime, requires_lupa

#: Documented canvas geometry per game (cols, rows).
_GEOMETRY: dict[str, tuple[int, int]] = {
    "snake": (80, 24),
    "tetris": (59, 22),
    "pacman": (39, 23),
    "nethack": (74, 24),
}

#: Games whose whole frame must be free of ASCII placeholder glyphs.
_NO_ASCII_PLACEHOLDERS = ("snake", "tetris", "pacman")


def make_game(name: str) -> GameRuntime:
    """A game runtime over a fresh api (profile name pinned to alice)."""
    holder = FakeApi()
    holder.data.files["games/profile.json"] = '{"version":1,"player":"alice"}'
    return GameRuntime(name, holder)


def top_boxes(row: str) -> tuple[list[int], list[int]]:
    """Column indexes of the top-left / top-right corner of every box."""
    lefts = [i for i, char in enumerate(row) if char in "╭┌"]
    rights = [i for i, char in enumerate(row) if char in "╮┐"]
    return lefts, rights


@requires_lupa
class TestFrameGeometry:
    """Row widths and border alignment for every shipped game."""

    def test_every_row_is_exactly_the_canvas_width(self) -> None:
        for name, (cols, rows) in _GEOMETRY.items():
            game = make_game(name)
            canvas = game.launch()
            assert (canvas.cols, canvas.rows) == (cols, rows), name
            lines = canvas.grid.split("\n")
            assert len(lines) == rows, name
            for index, line in enumerate(lines):
                # len() counts codepoints: exactly the display width contract
                assert len(line) == cols, f"{name} row {index} is {len(line)} wide"

    def test_borders_line_up_column_for_column(self) -> None:
        for name in _GEOMETRY:
            game = make_game(name)
            lines = game.launch().grid.split("\n")
            lefts, rights = top_boxes(lines[0])
            if not lefts:
                # pacman draws no frame of its own: the blue maze wall border
                # is the frame, checked in its dedicated test below
                continue
            assert len(lefts) == len(rights), name
            for line in lines[1:-1]:
                for column in lefts:
                    # a box that already ended leaves a blank column; its own
                    # bottom/top border draws a corner there
                    assert line[column] in "│╰╭ ", f"{name} left drift at {column}"
                for column in rights:
                    assert line[column] in "│╯╮ ", f"{name} right drift at {column}"
            # the bottom border may be a side box (tetris: the board box);
            # it must still be a closed rounded corner
            assert "╰" in lines[-1] and lines[-1].rstrip().endswith("╯"), name

    def test_pacman_frame_is_the_blue_wall_border(self) -> None:
        """No drawn frame: the maze walls are the outer border, tunnel open."""
        lines = make_game("pacman").launch().grid.split("\n")
        assert set(lines[0]) == {"█"} and set(lines[-1]) == {"█"}
        for index, line in enumerate(lines):
            if index == 13:  # the wrap tunnel: both edges are open
                assert line[0] != "█" and line[-1] != "█"
            else:
                assert line[0] == "█" and line[-1] == "█", f"row {index}"


@requires_lupa
class TestGlyphLayer:
    """Unicode glyphs everywhere; ASCII only where a mode allows it."""

    def test_no_ascii_placeholders_in_unicode_frames(self) -> None:
        for name in _NO_ASCII_PLACEHOLDERS:
            grid = make_game(name).launch().grid
            for banned in "#@$":
                assert banned not in grid, f"{name} draws {banned!r}"

    def test_pacman_counts_are_visible(self) -> None:
        grid = make_game("pacman").launch().grid
        assert grid.count("◉") == 1  # pacman
        assert grid.count("●") == 4  # power pellets
        assert grid.count("·") > 300  # the pellet field

    def test_nethack_structures_use_blocks_not_icons(self) -> None:
        grid = make_game("nethack").launch().grid
        assert "█" in grid  # walls
        assert "·" in grid  # floors
        assert "#" not in grid  # no ASCII wall fallback in the default mode
