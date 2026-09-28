"""Unit tests for the stateless text-object helpers in editor_core.

The helpers are pure line-string computations, so these tests pin the
scanning rules directly (no buffer, no keymap): the strictly-after start,
the till short-landing, count failure and the count clamp.
"""

from __future__ import annotations

import pytest

from yate.editor_core.textobjects import find_char

#: 'x' sits at columns 4, 9 and 14.
LINE = "abc xabc xabc x"


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
