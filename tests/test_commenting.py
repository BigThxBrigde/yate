"""Round-trip tests for the pure comment engine (L0)."""

from __future__ import annotations

from yate.editor_core.commenting import comment_range


def test_line_comment_adds_marker_after_indent_and_skips_blank_rows() -> None:
    lines = ["def f():", "    return 1", "", "  x = 2"]

    result = comment_range(lines, 0, 3, line_comment="#", block_comment=None)

    assert result == ["# def f():", "    # return 1", "", "  # x = 2"]
    assert lines == ["def f():", "    return 1", "", "  x = 2"]


def test_line_comment_second_toggle_restores_exact_text() -> None:
    lines = ["def f():", "    return 1", "", "  x = 2"]

    once = comment_range(lines, 0, 3, line_comment="#", block_comment=None)
    twice = comment_range(once, 0, 3, line_comment="#", block_comment=None)

    assert twice == lines


def test_mixed_range_gains_one_layer_then_restores() -> None:
    lines = ["# already", "plain", "", "  # indented"]

    once = comment_range(lines, 0, 3, line_comment="#", block_comment=None)
    twice = comment_range(once, 0, 3, line_comment="#", block_comment=None)

    assert once == ["# # already", "# plain", "", "  # # indented"]
    assert twice == lines


def test_line_comment_wins_over_block_markers() -> None:
    lines = ["int x = 1;"]

    result = comment_range(
        lines, 0, 0, line_comment="//", block_comment=("/*", "*/")
    )

    assert result == ["// int x = 1;"]


def test_block_only_language_wraps_each_non_blank_row() -> None:
    lines = ["<p>hi</p>", "  <div>", ""]

    result = comment_range(
        lines, 0, 2, line_comment=None, block_comment=("<!--", "-->")
    )

    assert result == ["<!-- <p>hi</p> -->", "  <!-- <div> -->", ""]


def test_block_only_second_toggle_restores_exact_text() -> None:
    lines = ["<p>hi</p>", "  <div>", ""]

    once = comment_range(
        lines, 0, 2, line_comment=None, block_comment=("<!--", "-->")
    )
    twice = comment_range(once, 0, 2, line_comment=None, block_comment=("<!--", "-->"))

    assert twice == lines


def test_css_style_block_comment_round_trips() -> None:
    lines = ["a {", "  color: red;", "}"]

    once = comment_range(
        lines, 0, 2, line_comment=None, block_comment=("/*", "*/")
    )
    twice = comment_range(once, 0, 2, line_comment=None, block_comment=("/*", "*/"))

    assert once == ["/* a { */", "  /* color: red; */", "/* } */"]
    assert twice == lines


def test_no_markers_leaves_rows_unchanged() -> None:
    lines = ["plain text", "  other"]

    result = comment_range(lines, 0, 1, line_comment=None, block_comment=None)

    assert result == lines


def test_range_restricted_to_selected_rows() -> None:
    lines = ["first", "second", "third", "fourth"]

    result = comment_range(lines, 1, 2, line_comment="#", block_comment=None)

    assert result == ["first", "# second", "# third", "fourth"]


def test_empty_span_returns_copy() -> None:
    lines = ["only"]

    result = comment_range(lines, 2, 3, line_comment="#", block_comment=None)

    assert result == lines
    assert result is not lines
