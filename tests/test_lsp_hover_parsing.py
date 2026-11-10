"""Unit tests for ``parse_hover_contents`` in yate.editor_lsp.parsing.

The function normalizes every LSP ``Hover.contents`` wire shape into a
display string, collapsing empty / whitespace-only / malformed shapes to
``""``.  These tests cover the full AC4 / AC5 matrix from the issue brief:
``MarkupContent`` (markdown + plaintext), ``MarkedString`` (fenced code
block), bare strings, string and mixed arrays, and the negative corpus.
All cases are arrange/act/assert on the pure function -- no App, no LSP
server.
"""

from __future__ import annotations

import pytest

from yate.editor_lsp.parsing import parse_hover_contents


def test_parse_hover_contents_with_none_returns_empty_string() -> None:
    """A ``None`` payload normalizes to the empty string."""
    assert parse_hover_contents(None) == ""


def test_parse_hover_contents_with_empty_dict_returns_empty_string() -> None:
    """An empty Hover dict has no ``contents`` and normalizes to ``""``."""
    assert parse_hover_contents({}) == ""


def test_parse_hover_contents_with_missing_contents_returns_empty_string() -> None:
    """A Hover dict without a ``contents`` field normalizes to ``""``."""
    assert parse_hover_contents({"range": {"start": {}, "end": {}}}) == ""


def test_parse_hover_contents_with_markup_markdown_returns_value() -> None:
    """Markdown ``MarkupContent`` keeps its markdown value verbatim."""
    hover = {"contents": {"kind": "markdown", "value": "**f()** docs"}}
    assert parse_hover_contents(hover) == "**f()** docs"


def test_parse_hover_contents_with_markup_plaintext_returns_value() -> None:
    """A bare plaintext ``MarkupContent`` payload keeps its value."""
    assert parse_hover_contents({"kind": "plaintext", "value": "plain docs"}) == (
        "plain docs"
    )


@pytest.mark.parametrize(
    ("raw",),
    [
        ("  \n\t ",),
        ({"contents": {"kind": "markdown", "value": " \n "}},),
    ],
)
def test_parse_hover_contents_with_whitespace_only_returns_empty_string(
    raw: object,
) -> None:
    """Whitespace-only content -- bare or nested -- collapses to ``""``."""
    assert parse_hover_contents(raw) == ""


def test_parse_hover_contents_with_bare_string_returns_text() -> None:
    """A bare string ``contents`` passes through unchanged."""
    assert parse_hover_contents({"contents": "hover text"}) == "hover text"


def test_parse_hover_contents_with_marked_string_wraps_language_in_fence() -> None:
    """``MarkedString`` with a language renders as a fenced code block."""
    hover = {"contents": {"language": "python", "value": "def f(x: int) -> str:"}}
    result = parse_hover_contents(hover)
    assert result.startswith("```python")
    assert "def f(x: int) -> str:" in result


@pytest.mark.parametrize(
    ("value", "language"),
    [
        ("", "python"),
        ("   ", "python"),
        (" \n\t ", "c++"),
        ("", ""),
        ("  ", "python"),
        ("\t", "c++"),
    ],
    ids=[
        "empty-python",
        "spaces-python",
        "whitespace-cpp",
        "empty-no-language",
        "spaces-python-again",
        "tab-cpp",
    ],
)
def test_parse_hover_contents_with_empty_value_and_language_returns_empty_string(
    value: str, language: str
) -> None:
    """An empty ``MarkedString`` value never produces a bare code fence."""
    hover = {"contents": {"language": language, "value": value}}
    assert parse_hover_contents(hover) == ""


@pytest.mark.parametrize(
    ("language",),
    [("python",), ("c++",)],
    ids=["plain", "plus-plus"],
)
def test_parse_hover_contents_with_safe_language_wraps_fence(
    language: str,
) -> None:
    """A plain safe language token still produces a tagged code fence."""
    hover = {"contents": {"language": language, "value": "sig"}}
    result = parse_hover_contents(hover)
    assert result.startswith(f"```{language}\n")
    assert "sig" in result


def test_parse_hover_contents_with_hostile_language_does_not_fence() -> None:
    """A language with newlines or backticks cannot break out of the fence."""
    hover = {
        "contents": {"language": "py\n```\nINJECTED", "value": "sig"},
    }
    result = parse_hover_contents(hover)
    assert "```" not in result
    assert "sig" in result


def test_parse_hover_contents_with_string_array_joins_nonempty_parts() -> None:
    """A string array joins its non-empty parts with a blank line."""
    assert parse_hover_contents(["sig", "", "docs"]) == "sig\n\ndocs"


def test_parse_hover_contents_with_mixed_array_preserves_order() -> None:
    """A mixed array keeps order: fenced signature, markdown, plain tail."""
    hover = [
        {"language": "python", "value": "def f():"},
        {"kind": "markdown", "value": "docs"},
        "tail",
    ]
    result = parse_hover_contents(hover)
    assert result.startswith("```python")
    assert "def f():" in result
    parts = result.split("\n\n")
    assert parts[0].startswith("```python")
    assert parts[1] == "docs"
    assert parts[2] == "tail"


@pytest.mark.parametrize(
    ("raw",),
    [
        ([],),
        (["", "  "],),
    ],
)
def test_parse_hover_contents_with_empty_array_returns_empty_string(
    raw: object,
) -> None:
    """Empty arrays and all-blank arrays collapse to ``""``."""
    assert parse_hover_contents(raw) == ""


@pytest.mark.parametrize(
    ("raw",),
    [
        ({"contents": 42},),
        ({"value": 7},),
        ({"contents": [None, True, {"value": None}]},),
        (object(),),
    ],
)
def test_parse_hover_contents_with_malformed_shapes_returns_empty_string(
    raw: object,
) -> None:
    """Malformed wire shapes collapse to ``""`` instead of raising."""
    assert parse_hover_contents(raw) == ""


def test_parse_hover_contents_is_total_for_hostile_input() -> None:
    """The function never raises on arbitrary hostile input."""
    corpus: list[object] = [
        None,
        42,
        True,
        3.14,
        object(),
        {},
        {"contents": None},
        {"contents": {"kind": "markdown"}},
        {"contents": {"language": "python"}},
        {"contents": [None, [True], {"value": 7}, {}]},
        [[[[["\n  "]]]]],
        {"contents": [{"language": "", "value": "no fence"}, {"value": ""}]},
    ]
    for raw in corpus:
        result = parse_hover_contents(raw)
        assert isinstance(result, str)
