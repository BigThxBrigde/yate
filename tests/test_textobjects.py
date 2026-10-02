"""Unit tests for the stateless text-object helpers in editor_core.

The helpers are pure line-string computations, so these tests pin the
scanning rules directly (no buffer, no keymap): the strictly-after start,
the till short-landing, count failure and the count clamp.
"""

from __future__ import annotations

import pytest

from yate.editor_core.textobjects import (
    find_char,
    first_non_blank,
    next_word_pos,
    prev_word_pos,
    resolve_text_object,
)

#: 'x' sits at columns 4, 9 and 14.
LINE: str = "abc xabc xabc x"


@pytest.mark.parametrize(
    ("col", "count", "expected"),
    [
        (0, 1, 4),  # first match after the cursor
        (0, 3, 14),  # the count-th match
        (0, 4, None),  # beyond the matches on the row
        (4, 1, 9),  # the cursor char itself never matches
        (14, 1, None),  # nothing after the last match
        (13, 1, 14),
        (0, 0, 4),  # a nonsense count degrades to one
    ],
)
def test_find_char_forward_finds_the_counted_occurrence(
    col: int, count: int, expected: int | None
) -> None:
    assert find_char(LINE, col, "x", count=count) == expected


@pytest.mark.parametrize(
    ("col", "count", "expected"),
    [
        (14, 1, 9),
        (14, 2, 4),
        (14, 3, None),
        (9, 1, 4),
        (4, 1, None),  # strictly before: the cursor char never matches
        (0, 1, None),  # nothing before column 0
    ],
)
def test_find_char_backward_finds_the_counted_occurrence(
    col: int, count: int, expected: int | None
) -> None:
    assert find_char(LINE, col, "x", count=count, backward=True) == expected


@pytest.mark.parametrize(
    ("line", "col", "expected"),
    [
        ("abc xabc", 0, 3),  # land one before the match
        ("axbc", 0, None),  # landing would not move the cursor
        ("abcx", 2, None),  # match right after the cursor: no room for till
    ],
)
def test_till_forward_lands_one_column_short(
    line: str, col: int, expected: int | None
) -> None:
    assert find_char(line, col, "x", till=True) == expected


@pytest.mark.parametrize(
    ("line", "col", "expected"),
    [
        ("abc xabc", 8, 5),  # land one after the match
        ("abcx", 4, None),  # landing would not move the cursor
        ("abcxe", 5, 4),  # the cursor may sit on the EOL column
    ],
)
def test_till_backward_lands_one_column_after(
    line: str, col: int, expected: int | None
) -> None:
    assert find_char(line, col, "x", till=True, backward=True) == expected


def test_find_char_on_an_empty_line_fails() -> None:
    assert find_char("", 0, "x") is None


# --- text objects ------------------------------------------------------------


def test_inner_word_span() -> None:
    assert resolve_text_object(["foo bar"], (0, 1), "i", "w") == ((0, 0), (0, 3))


def test_a_word_includes_trailing_whitespace() -> None:
    assert resolve_text_object(["foo bar"], (0, 0), "a", "w") == ((0, 0), (0, 4))


def test_a_word_on_the_last_word_takes_the_leading_whitespace() -> None:
    assert resolve_text_object(["foo bar"], (0, 5), "a", "w") == ((0, 3), (0, 7))


def test_word_object_covers_punctuation_runs() -> None:
    assert resolve_text_object(["f(x)"], (0, 1), "i", "w") == ((0, 1), (0, 2))


def test_word_object_on_whitespace_selects_the_run() -> None:
    assert resolve_text_object(["a  b"], (0, 1), "i", "w") == ((0, 1), (0, 3))
    assert resolve_text_object(["a  b"], (0, 1), "a", "w") == ((0, 1), (0, 4))


def test_counted_word_span_extends_forward() -> None:
    assert resolve_text_object(["one two three four"], (0, 0), "i", "w", 3) == (
        (0, 0),
        (0, 13),
    )


def test_inner_and_around_pair() -> None:
    assert resolve_text_object(["f(a, b)g"], (0, 3), "i", "(") == ((0, 2), (0, 6))
    assert resolve_text_object(["f(a, b)g"], (0, 3), "a", "(") == ((0, 1), (0, 7))


def test_pair_span_crosses_lines() -> None:
    lines = ["f(", "ab", ")g"]
    assert resolve_text_object(lines, (1, 1), "i", "(") == ((0, 2), (2, 0))


def test_pair_nesting_selects_the_innermost_and_count_goes_outward() -> None:
    lines = ["(a(b)c)"]
    assert resolve_text_object(lines, (0, 3), "i", "(") == ((0, 3), (0, 4))
    assert resolve_text_object(lines, (0, 3), "i", "(", 2) == ((0, 1), (0, 6))


def test_pair_on_the_delimiters_themselves() -> None:
    assert resolve_text_object(["(ab)"], (0, 0), "i", "(") == ((0, 1), (0, 3))
    assert resolve_text_object(["(ab)"], (0, 3), "i", ")") == ((0, 1), (0, 3))


def test_pair_from_the_eol_column_still_finds_the_block() -> None:
    """A cursor parked on the EOL column inside a block still resolves."""
    lines = ["(", "ab", ")x"]
    assert resolve_text_object(lines, (1, 2), "i", "(") == ((0, 1), (2, 0))


def test_unbalanced_pair_fails() -> None:
    assert resolve_text_object(["(ab"], (0, 2), "i", "(") is None


def test_delimiter_aliases_select_their_pairs() -> None:
    assert resolve_text_object(["(x)"], (0, 1), "i", "b") == ((0, 1), (0, 2))
    assert resolve_text_object(["{x}"], (0, 1), "i", "B") == ((0, 1), (0, 2))


def test_quote_objects_stay_on_the_cursor_row() -> None:
    assert resolve_text_object(['say "hi"'], (0, 6), "i", '"') == ((0, 5), (0, 7))
    assert resolve_text_object(['say "hi"'], (0, 6), "a", '"') == ((0, 4), (0, 8))


def test_quote_object_fails_outside_or_across_lines() -> None:
    assert resolve_text_object(['say "hi"'], (0, 0), "i", '"') is None
    assert resolve_text_object(['"ab', 'cd"'], (0, 1), "i", '"') is None


def test_quote_object_with_cursor_on_the_quote() -> None:
    """Sitting on a real quote prefers reading it as the opener."""
    assert resolve_text_object(['say "hi"'], (0, 4), "i", '"') == ((0, 5), (0, 7))
    assert resolve_text_object(['say "hi"'], (0, 7), "i", '"') == ((0, 5), (0, 7))
    # a lone quote has neither a follower nor a predecessor: no object
    assert resolve_text_object(['say "'], (0, 4), "i", '"') is None


def test_quote_span_ignores_escaped_quotes() -> None:
    """``\\"`` is content, not a delimiter; the real pair wins."""
    line = 'say "hi\\"there" ok'  # say "hi\"there" ok
    assert resolve_text_object([line], (0, 6), "i", '"') == ((0, 5), (0, 14))
    assert resolve_text_object([line], (0, 6), "a", '"') == ((0, 4), (0, 15))
    # cursor on the escaped quote itself still resolves the enclosing pair
    assert resolve_text_object([line], (0, 8), "i", '"') == ((0, 5), (0, 14))


def test_tag_objects_on_the_inner_text() -> None:
    assert resolve_text_object(["<p>x</p>"], (0, 3), "i", "t") == ((0, 3), (0, 4))
    assert resolve_text_object(["<p>x</p>"], (0, 3), "a", "t") == ((0, 0), (0, 8))


def test_tag_object_with_the_cursor_on_the_opener() -> None:
    assert resolve_text_object(["<p>x</p>"], (0, 0), "i", "t") == ((0, 3), (0, 4))


def test_tag_objects_span_lines_and_nest() -> None:
    lines = ["<div>", "<span>x</span>", "</div>"]
    assert resolve_text_object(lines, (1, 6), "i", "t") == ((1, 6), (1, 7))
    assert resolve_text_object(lines, (1, 6), "i", "t", 2) == ((0, 5), (2, 0))
    assert resolve_text_object(lines, (1, 6), "a", "t", 2) == ((0, 0), (2, 6))


def test_self_closing_tag_is_not_an_enclosing_tag() -> None:
    assert resolve_text_object(["<br/> x"], (0, 5), "i", "t") is None


def test_unknown_object_key_fails() -> None:
    assert resolve_text_object(["abc"], (0, 1), "i", "z") is None


# --- cross-line word motion positions -----------------------------------------


def test_first_non_blank() -> None:
    assert first_non_blank("  ab") == 2
    assert first_non_blank("ab") == 0
    assert first_non_blank("   ") == 3  # all blank: the virtual EOL column
    assert first_non_blank("") == 0


def test_next_word_pos_scans_the_row_then_wraps_down() -> None:
    lines = ["ab cd", "  ef", "", "gh"]
    assert next_word_pos(lines, 0, 0) == (0, 3)
    assert next_word_pos(lines, 0, 3) == (0, 4)  # last word: stop on the last char
    assert next_word_pos(lines, 0, 4) == (1, 2)  # wrap lands on first non-blank
    assert next_word_pos(lines, 1, 2) == (1, 3)  # same rule on the indented row
    assert next_word_pos(lines, 1, 3) == (2, 0)  # empty lines stop the motion
    assert next_word_pos(lines, 2, 0) == (3, 0)  # resume after the empty line
    assert next_word_pos(lines, 3, 0) == (3, 1)
    assert next_word_pos(lines, 3, 1) is None


def test_prev_word_pos_scans_the_row_then_wraps_up() -> None:
    lines = ["ab cd", "  ef", "", "gh"]
    assert prev_word_pos(lines, 1, 3) == (1, 2)
    assert prev_word_pos(lines, 1, 2) == (0, 3)  # wrap lands on last word start
    assert prev_word_pos(lines, 2, 0) == (1, 2)  # blank row wraps upward
    assert prev_word_pos(lines, 0, 0) is None
