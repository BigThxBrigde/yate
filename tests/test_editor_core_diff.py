"""Headless tests for the L0 diff engine (yate.editor_core.diff).

Pure-function coverage: hunk boundaries (half-open), the autojunk trap,
row alignment, intra-line character ranges, 3-way merge region
classification and the ``hunk_replacement`` triples that must align with
``TextBuffer.replace_range``.  No fixtures needed -- every case calls the
engine directly.

Run with:  python -m pytest tests/test_editor_core_diff.py -q
"""

from __future__ import annotations

from yate.editor_core.buffer import TextBuffer
from yate.editor_core.diff import (
    DiffHunk,
    diff3_regions,
    diff_lines,
    diff_words,
    hunk_replacement,
)


# --- diff_lines -------------------------------------------------------------


def test_diff_lines_identical_inputs_yields_no_hunks() -> None:
    result = diff_lines(["a", "b"], ["a", "b"])
    assert result.hunks == []
    assert result.a_lines == 2
    assert result.b_lines == 2


def test_diff_lines_replace_hunk_bounds_are_half_open() -> None:
    result = diff_lines(["a", "x", "c"], ["a", "y", "c"])
    assert len(result.hunks) == 1
    hunk = result.hunks[0]
    assert hunk.kind == "replace"
    assert (hunk.a_start, hunk.a_end) == (1, 2)
    assert (hunk.b_start, hunk.b_end) == (1, 2)


def test_diff_lines_insert_yields_b_side_only_hunk() -> None:
    result = diff_lines(["a"], ["a", "new"])
    assert len(result.hunks) == 1
    hunk = result.hunks[0]
    assert hunk.kind == "insert"
    assert hunk.a_start == hunk.a_end == 1
    assert (hunk.b_start, hunk.b_end) == (1, 2)


def test_diff_lines_delete_yields_a_side_only_hunk() -> None:
    result = diff_lines(["a", "gone"], ["a"])
    assert len(result.hunks) == 1
    hunk = result.hunks[0]
    assert hunk.kind == "delete"
    assert (hunk.a_start, hunk.a_end) == (1, 2)
    assert hunk.b_start == hunk.b_end == 1


def test_diff_lines_autojunk_disabled_on_long_inputs() -> None:
    # 300 highly-repeated lines (each one appears 5 times > the popular
    # threshold) plus one modified line: with the default autojunk the
    # repeated lines are dropped as junk and the hunk wrongly swallows
    # half the file (measured: bounds become (150, 301)).
    base = ["L%d" % i for i in range(60)] * 5
    a = base[:150] + ["MID-A"] + base[150:]
    b = base[:150] + ["MID-B"] + base[150:]
    result = diff_lines(a, b)
    assert len(result.hunks) == 1
    hunk = result.hunks[0]
    assert hunk.kind == "replace"
    assert (hunk.a_start, hunk.a_end) == (150, 151)
    assert (hunk.b_start, hunk.b_end) == (150, 151)


# --- DiffResult.align -------------------------------------------------------


def test_align_maps_equal_rows_and_changed_rows() -> None:
    result = diff_lines(["a", "x", "c"], ["a", "y", "c"])
    assert result.align(0) == 0
    assert result.align(2) == 2
    assert result.align(1) == 1  # changed row anchors to the hunk's b_start


# --- diff_words -------------------------------------------------------------


def test_diff_words_returns_char_ranges_for_changed_spans() -> None:
    # Character-level matcher: "foo ba" matches, only "r" vs "z" differs.
    a_ranges, b_ranges = diff_words("foo bar", "foo baz")
    assert (6, 7) in a_ranges
    assert (6, 7) in b_ranges
    for start, end in [*a_ranges, *b_ranges]:
        assert 0 <= start < end <= 7


def test_diff_words_identical_lines_yield_empty_ranges() -> None:
    a_ranges, b_ranges = diff_words("same", "same")
    assert a_ranges == []
    assert b_ranges == []


# --- diff3_regions ----------------------------------------------------------


def test_diff3_regions_classifies_conflict_on_overlapping_edits() -> None:
    regions = diff3_regions(["1", "2", "3"], ["1", "2L", "3"], ["1", "2R", "3"])
    conflicts = [region for region in regions if region.kind == "conflict"]
    assert len(conflicts) == 1
    assert (conflicts[0].base_start, conflicts[0].base_end) == (1, 2)


def test_diff3_regions_classifies_disjoint_changes_independent() -> None:
    regions = diff3_regions(["1", "2", "3"], ["1L", "2", "3"], ["1", "2", "3R"])
    assert [region.kind for region in regions] == ["local", "same", "remote"]


def test_diff3_regions_identical_changes_are_both_kind() -> None:
    regions = diff3_regions(["1", "2", "3"], ["1", "2X", "3"], ["1", "2X", "3"])
    kinds = [region.kind for region in regions]
    assert "both" in kinds
    assert "conflict" not in kinds


# --- hunk_replacement -------------------------------------------------------


def test_hunk_replacement_b_side_spans_target_range() -> None:
    target = ["a", "x", "c"]
    source = ["a", "y1", "y2", "c"]
    hunk = DiffHunk(kind="replace", a_start=1, a_end=2, b_start=1, b_end=3)
    start, end, text = hunk_replacement(target, hunk, source, copy_into="b")
    assert (start, end, text) == ((1, 0), (2, 0), "y1\ny2\n")


def test_hunk_replacement_triple_replays_through_replace_range() -> None:
    """The triple must merge cleanly through TextBuffer.replace_range."""
    target = ["one", "TWO", "three"]
    source = ["one", "two", "three"]
    hunk = DiffHunk(kind="replace", a_start=1, a_end=2, b_start=1, b_end=2)
    start, end, text = hunk_replacement(target, hunk, source, copy_into="b")
    buffer = TextBuffer("\n".join(target))
    buffer.replace_range(start, end, text)
    assert buffer.lines == ["one", "two", "three"]


def test_hunk_replacement_at_end_of_buffer_handles_last_line() -> None:
    target = ["a", "x"]
    source = ["a", "x", "new"]
    hunk = DiffHunk(kind="insert", a_start=2, a_end=2, b_start=2, b_end=3)
    start, end, text = hunk_replacement(target, hunk, source, copy_into="b")
    assert start == end == (1, 1)  # collapsed onto the last line's end
    assert text == "\nnew"  # newline-first line-insertion semantics
