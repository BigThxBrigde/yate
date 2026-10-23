"""Unit tests for ``yate.editor_view.cells`` (character geometry helpers).

Pure-function coverage: terminal cell widths (combining / wide / tab / ASCII),
truncation, the tab-aware cell<->char mappings, the prefix offset table and
the wide-glyph / combining-mark / tab expansion rules.  No fixtures needed --
the module is theme independent and its only state is a read-only LRU cache.
"""

from __future__ import annotations

from yate.editor_view.cells import (
    cell_len,
    cell_offsets,
    cell_to_char,
    cell_width,
    char_to_cell,
    expand_char,
    truncate_to_cells,
)

COMBINING_ACUTE = "\u0301"  # U+0301 combining acute accent (zero width)


# --- cell_width ---------------------------------------------------------------


def test_cell_width_combining_mark_is_zero() -> None:
    assert cell_width(COMBINING_ACUTE) == 0


def test_cell_width_wide_cjk_is_two() -> None:
    assert cell_width("中") == 2


def test_cell_width_tab_counts_one() -> None:
    assert cell_width("\t") == 1


def test_cell_width_ascii_is_one() -> None:
    assert cell_width("a") == 1


# --- cell_len / truncate_to_cells ---------------------------------------------


def test_cell_len_mixed_string_counts_display_cells() -> None:
    assert cell_len("a中b") == 4
    assert cell_len("a\tb") == 3


def test_truncate_to_cells_stops_before_overflowing_wide_char() -> None:
    assert truncate_to_cells("a中", 2) == "a"


def test_truncate_to_cells_zero_limit_returns_empty() -> None:
    assert truncate_to_cells("abc", 0) == ""


# --- char_to_cell / cell_to_char / cell_offsets --------------------------------


def test_char_to_cell_expands_tab_to_next_stop() -> None:
    # default tab_width=4: the tab before char 1 pushes to the next stop
    assert char_to_cell("\tx", 1) == 4


def test_cell_to_char_maps_back_from_cell_column() -> None:
    # cells: a=0, b=1, wide cjk=2..3, c=4 -- display column 4 is 'c' at char 3
    assert cell_to_char("ab中cd", 4) == 3
    # beyond the line end: maps to len(line)
    assert cell_to_char("ab", 99) == 2


def test_cell_to_char_skips_attached_marks_before_the_boundary() -> None:
    # cell 1 is the column right after 'a': the combining mark attaches to
    # that cell, so the boundary test must not stop on the mark -- the
    # click lands on the next base character 'b'
    line = "a" + COMBINING_ACUTE + "b"
    assert cell_to_char(line, 1) == 2
    # the inverse map round-trips through char_to_cell for the base
    # characters and the line end (the mark index itself shares cell 1
    # with 'b', so the many-to-one forward map cannot round-trip it)
    for i in (0, 2, 3):
        assert cell_to_char(line, char_to_cell(line, i)) == i


def test_cell_offsets_matches_char_to_cell_prefix() -> None:
    line = "a\t中b"
    offsets = cell_offsets(line)
    assert len(offsets) == len(line) + 1
    for i in range(len(line) + 1):
        assert offsets[i] == char_to_cell(line, i)


def test_cell_offsets_keep_a_combining_mark_in_the_previous_cell() -> None:
    # a mid-line combining mark advances nothing: it rides the previous cell
    assert cell_offsets("a" + COMBINING_ACUTE + "b") == [0, 1, 1, 2]


def test_char_to_cell_and_cell_offsets_agree_on_combining_marks() -> None:
    line = COMBINING_ACUTE + "a" + COMBINING_ACUTE + "b"
    offsets = cell_offsets(line)
    for i in range(len(line) + 1):
        assert offsets[i] == char_to_cell(line, i)


def test_leading_combining_mark_still_occupies_one_cell() -> None:
    # a leading mark degrades to one cell, like expand_char
    assert cell_offsets(COMBINING_ACUTE + "a") == [0, 1, 2]


# --- expand_char ---------------------------------------------------------------


def test_expand_char_doubles_wide_glyph_into_two_cells() -> None:
    cells: list[str] = []
    expand_char("中", cells, 4)
    assert cells == ["中", ""]


def test_expand_char_attaches_combining_mark_to_previous_cell() -> None:
    cells: list[str] = []
    expand_char("a", cells, 4)
    expand_char(COMBINING_ACUTE, cells, 4)
    # the mark attaches to the previous cell: one cell holding the
    # decomposed sequence (rendered as a single accented glyph)
    assert cells == ["a\u0301"]


def test_expand_char_tab_advances_to_next_stop() -> None:
    # expand_char pads to the next tab stop without splitting existing
    # cells, so the arrange uses per-char cells as the render path builds
    cells = ["a", "b"]
    expand_char("\t", cells, 4)
    assert cells == ["a", "b", " ", " "]
