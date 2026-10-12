"""Unit tests for yate.editor_term.palette: xterm 256-color resolution.

The emulator tests only touch two symbols on the render side; this module
covers the index-resolution branches: the ANSI-16 base table, the 6-6-6
color cube formula, the exact-black shortcut, the grayscale ramp and the
out-of-range clamping.
"""

from __future__ import annotations

from yate.editor_term.palette import ANSI_16_RGB, palette_color


def test_palette_color_base_16_reads_ansi_table() -> None:
    """Indices 0-15 read straight from the ANSI-16 table."""
    assert palette_color(0) == ANSI_16_RGB[0]
    assert palette_color(5) == ANSI_16_RGB[5]


def test_palette_color_color_cube_matches_level_formula() -> None:
    """A color-cube index resolves through the 6-6-6 level table.

    Index 218 = 16 + 36*5 + 6*3 + 4 reads levels[5], levels[3], levels[4]
    of ``(0, 95, 135, 175, 215, 255)``.
    """
    assert palette_color(16 + 36 * 5 + 6 * 3 + 4) == (255, 175, 215)


def test_palette_color_color_cube_black_is_exact_zero() -> None:
    """Cube index 0 (palette index 16) takes the exact-black shortcut."""
    assert palette_color(16) == (0, 0, 0)


def test_palette_color_grayscale_ramp_starts_at_8_step_10() -> None:
    """The grayscale ramp runs 8..238 in steps of 10."""
    assert palette_color(232) == (8, 8, 8)
    assert palette_color(255) == (238, 238, 238)


def test_palette_color_clamps_out_of_range_indices() -> None:
    """Out-of-range indices clamp into the valid 0-255 window."""
    assert palette_color(-5) == palette_color(0)
    assert palette_color(999) == palette_color(255)
