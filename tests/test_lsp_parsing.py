"""Unit tests for yate.editor_lsp.parsing: wire format -> buffer coordinates.

``_parse_diagnostics`` already has coverage in tests/test_diagnostics.py;
this module covers the rest of the module's ``__all__`` surface: the UTF-16
round trips, completion payload unwrapping, range normalization and
completion item parsing.  The shared *doc* fixture is a three-line document
whose second line carries a non-BMP character so the UTF-16 conversions
are exercised against real buffer lines.
"""

# _-prefixed names are the module's __all__ surface (wave-a private-registry
# precedent, same as tests/test_diagnostics.py).
# pyright: reportPrivateUsage=false

from __future__ import annotations

import pytest

from yate.config import YateConfig
from yate.editor_core.document import Document
from yate.editor_lsp.client import Completion
from yate.editor_lsp.parsing import (
    _from_utf16,
    _parse_completion_item,
    _range_from,
    _range_to_buffer_cols,
    _to_utf16,
    _unwrap_completion,
)
from yate.session import EditorSession

#: A line with one non-BMP character: U+1F600 counts as two UTF-16 units,
#: so the line is 3 code points / 4 UTF-16 code units long.
EMOJI_LINE = "a\U0001F600b"


@pytest.fixture()
def doc() -> Document:
    """A three-line document; line 1 carries a non-BMP character."""
    session = EditorSession(YateConfig())
    return Document(None, session.make_buffer("alpha\n" + EMOJI_LINE + "\ngamma"))


# --- UTF-16 code unit conversions -------------------------------------------


def test_to_utf16_ascii_line_is_passthrough() -> None:
    """ASCII lines are the fast path: code points == code units."""
    assert _to_utf16("abc", 2) == 2


def test_to_utf16_counts_non_bmp_as_two_units() -> None:
    """A non-BMP character counts as two units: ``a`` (1) + emoji (2)."""
    assert _to_utf16(EMOJI_LINE, 2) == 3


def test_from_utf16_maps_units_back_to_code_points() -> None:
    """The inverse map is the round trip of :func:`_to_utf16`."""
    assert _from_utf16(EMOJI_LINE, 3) == 2
    assert _from_utf16(EMOJI_LINE, 0) == 0


def test_from_utf16_units_beyond_line_returns_line_length() -> None:
    """Units past the end of the line clamp to the line length."""
    assert _from_utf16(EMOJI_LINE, 99) == len(EMOJI_LINE)


# --- completion payload unwrapping ------------------------------------------


def test_unwrap_completion_plain_list_returns_items_no_defaults() -> None:
    """A plain list yields the dict items (non-dicts filtered) and no defaults."""
    items, defaults = _unwrap_completion([{"label": "x"}, "junk"])
    assert items == [{"label": "x"}]
    assert defaults == {}


def test_unwrap_completion_dict_uses_items_and_item_defaults() -> None:
    """The dict form passes ``items`` and ``itemDefaults`` through; a
    payload without ``items`` degrades to an empty list."""
    edit_range = {
        "start": {"line": 0, "character": 0},
        "end": {"line": 0, "character": 1},
    }
    items, defaults = _unwrap_completion(
        {"items": [{"label": "x"}], "itemDefaults": {"editRange": edit_range}}
    )
    assert items == [{"label": "x"}]
    assert defaults == {"editRange": edit_range}
    missing, empty_defaults = _unwrap_completion({"itemDefaults": {}})
    assert missing == []
    assert empty_defaults == {}


def test_unwrap_completion_garbage_returns_empty_pair() -> None:
    """Any non-list/dict payload degrades to an empty (items, defaults)."""
    assert _unwrap_completion(42) == ([], {})


# --- range normalization ----------------------------------------------------


def test_range_from_insert_key_wins_over_outer_range() -> None:
    """An ``insert`` member overrides the outer range object."""
    value = {
        "range": {
            "start": {"line": 9, "character": 9},
            "end": {"line": 9, "character": 9},
        },
        "insert": {
            "start": {"line": 1, "character": 2},
            "end": {"line": 3, "character": 4},
        },
    }
    assert _range_from(value) == (1, 2, 3, 4)


def test_range_from_malformed_returns_none() -> None:
    """Non-dict payloads and ranges missing start/end degrade to None."""
    assert _range_from(42) is None
    assert _range_from({"start": {"line": 0, "character": 0}}) is None
    assert _range_from({"start": {"line": 0, "character": 0}, "end": 7}) is None


def test_range_to_buffer_cols_converts_utf16_columns(doc: Document) -> None:
    """UTF-16 server columns map to code-point buffer columns; an
    out-of-range row converts against the empty line (column 0 stays 0)."""
    assert _range_to_buffer_cols((1, 1, 1, 3), doc) == (1, 1, 1, 2)
    assert _range_to_buffer_cols((5, 0, 5, 0), doc) == (5, 0, 5, 0)


# --- completion item parsing -------------------------------------------------


def test_parse_completion_item_label_becomes_insert_text(doc: Document) -> None:
    """A minimal item inserts the label over the computed prefix range."""
    item = _parse_completion_item({"label": "foo"}, {}, doc, 1, 3, 1)
    assert isinstance(item, Completion)
    assert item.label == "foo"
    assert item.insert_text == "foo"
    assert (
        item.range_start_row, item.range_start_col,
        item.range_end_row, item.range_end_col,
    ) == (1, 1, 1, 3)


def test_parse_completion_item_text_edit_dict_uses_new_text_and_range(
    doc: Document,
) -> None:
    """A dict textEdit wins: its newText is inserted and its UTF-16 range
    lands on buffer columns (server units 1..3 -> code points 1..2)."""
    item = _parse_completion_item(
        {
            "label": "foo",
            "textEdit": {
                "newText": "bar",
                "range": {
                    "start": {"line": 1, "character": 1},
                    "end": {"line": 1, "character": 3},
                },
            },
        },
        {}, doc, 1, 3, 1,
    )
    assert item is not None
    assert item.insert_text == "bar"
    assert (
        item.range_start_row, item.range_start_col,
        item.range_end_row, item.range_end_col,
    ) == (1, 1, 1, 2)


def test_parse_completion_item_snippet_falls_back_to_label(doc: Document) -> None:
    """Snippet tab stops are unsupported: a format-2 item falls back to the
    plain label so accepting never inserts raw ``$1`` placeholders."""
    item = _parse_completion_item(
        {
            "label": "foo",
            "insertTextFormat": 2,
            "textEdit": {
                "newText": "f$1oo",
                "range": {
                    "start": {"line": 1, "character": 0},
                    "end": {"line": 1, "character": 1},
                },
            },
        },
        {}, doc, 1, 3, 1,
    )
    assert item is not None
    assert item.insert_text == "foo"


def test_parse_completion_item_missing_label_returns_none(doc: Document) -> None:
    """An absent, empty or non-string label yields no completion."""
    assert _parse_completion_item({"label": ""}, {}, doc, 1, 3, 1) is None
    assert _parse_completion_item({"label": 42}, {}, doc, 1, 3, 1) is None
    assert _parse_completion_item({}, {}, doc, 1, 3, 1) is None
