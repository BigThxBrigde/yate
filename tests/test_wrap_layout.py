"""Tests for the soft-wrap display-row mapping (plan A)."""

from __future__ import annotations

import pytest

import yate.editor_components.wrap_layout as wrap_module
from yate.editor_components.wrap_layout import RowSpan, WrapLayout


def test_ascii_long_line_wraps_by_character() -> None:
    layout = WrapLayout()
    layout.update(1, 3, ["abcdefgh"], 4, True)
    assert layout.display_count() == 3
    assert layout.display_to_logical(0) == RowSpan(0, 0, 3, 0)
    assert layout.display_to_logical(1) == RowSpan(0, 3, 6, 1)
    assert layout.display_to_logical(2) == RowSpan(0, 6, 8, 2)
    assert layout.display_to_logical(3) is None
    assert layout.display_to_logical(-1) is None


def test_tab_at_boundary_is_never_split() -> None:
    # "ab\tcd": the tab expands columns 2..4, exactly filling the row.
    layout = WrapLayout()
    layout.update(1, 4, ["ab\tcd"], 4, True)
    assert layout.display_count() == 2
    assert layout.display_to_logical(0) == RowSpan(0, 0, 4, 0)
    assert layout.display_to_logical(1) == RowSpan(0, 4, 6, 1)


def test_overshooting_tab_pushed_whole_to_next_row() -> None:
    # "abc\t" with tab_width=8: the tab expands columns 3..8, wider than the
    # remaining cell of the row, so it moves wholly onto the next row.
    layout = WrapLayout()
    layout.update(1, 4, ["abc\t"], 8, True)
    assert layout.display_count() == 2
    assert layout.display_to_logical(0) == RowSpan(0, 0, 3, 0)
    assert layout.display_to_logical(1) == RowSpan(0, 3, 8, 1)


def test_cjk_wide_char_is_never_split() -> None:
    # The wide glyph needs two cells; at text_w=2 it straddles row one and
    # is pushed wholly onto its own display row.
    layout = WrapLayout()
    layout.update(1, 2, ["a漢b"], 4, True)
    assert layout.display_count() == 3
    assert layout.display_to_logical(0) == RowSpan(0, 0, 1, 0)
    assert layout.display_to_logical(1) == RowSpan(0, 1, 3, 1)
    assert layout.display_to_logical(2) == RowSpan(0, 3, 4, 2)


def test_empty_line_yields_one_display_row() -> None:
    layout = WrapLayout()
    layout.update(1, 4, ["", "x", ""], 4, True)
    assert layout.display_count() == 3
    assert layout.display_to_logical(0) == RowSpan(0, 0, 0, 0)
    assert layout.display_to_logical(1) == RowSpan(1, 0, 1, 0)
    assert layout.display_to_logical(2) == RowSpan(2, 0, 0, 0)
    assert layout.logical_display_rows(0) == 1
    assert layout.logical_display_rows(2) == 1
    assert layout.logical_display_rows(3) == 0


def test_disabled_wrap_is_identity_mapping() -> None:
    layout = WrapLayout()
    layout.update(1, 4, ["ab", "a\tb"], 4, False)
    assert layout.display_count() == 2
    # With wrapping off the span's cell window is unused by the render path
    # (which windows with scroll_col), so the O(1) identity path reports a
    # zero-width sentinel instead of scanning every line to expand tabs.
    assert layout.display_to_logical(0) == RowSpan(0, 0, 0, 0)
    assert layout.display_to_logical(1) == RowSpan(1, 0, 0, 0)


def test_display_and_logical_mappings_round_trip() -> None:
    layout = WrapLayout()
    layout.update(1, 4, ["abcdef", "xy"], 4, True)
    assert layout.display_count() == 3
    assert layout.logical_display_rows(0) == 2
    assert layout.logical_display_rows(1) == 1
    for display_row in range(layout.display_count()):
        span = layout.display_to_logical(display_row)
        assert span is not None
        located = layout.logical_to_display(span.logical_row, span.cell_start)
        assert located == (display_row, 0)
    # a mid-line cell lands on the display row that starts at that cell
    assert layout.logical_to_display(0, 5) == (1, 1)
    # an end-of-line cursor (cell past the last span) clamps to the last row
    assert layout.logical_to_display(0, 6) == (1, 2)


def test_rebuild_only_when_cache_key_changes() -> None:
    layout = WrapLayout()
    layout.update(1, 10, ["abc"], 4, True)
    assert layout.rebuild_count == 1
    first = layout.logical_rows
    # identical key: zero rebuilds even though update runs every frame
    layout.update(1, 10, ["abc"], 4, True)
    assert layout.rebuild_count == 1
    assert layout.logical_rows is first
    # a content edit bumps the version -> exactly one rebuild
    layout.update(2, 10, ["abcd"], 4, True)
    assert layout.rebuild_count == 2
    # a viewport resize changes text_w -> exactly one rebuild
    layout.update(2, 20, ["abcd"], 4, True)
    assert layout.rebuild_count == 3
    # toggling wrap changes enabled -> exactly one rebuild
    layout.update(2, 20, ["abcd"], 4, False)
    assert layout.rebuild_count == 4


def test_document_identity_change_rebuilds_even_at_same_version() -> None:
    layout = WrapLayout()
    doc_a, doc_b = object(), object()
    layout.update(0, 2, ["aaaa"], 4, True, doc_a)
    assert layout.rebuild_count == 1
    # a freshly opened document also starts at content version 0; rebinding
    # to it must invalidate the cache despite the identical numeric key.
    layout.update(0, 2, ["b"], 4, True, doc_b)
    assert layout.rebuild_count == 2
    assert layout.display_count() == 1
    assert layout.display_to_logical(0) == RowSpan(0, 0, 1, 0)
    # returning to the first document rebuilds again (no cross-file reuse)
    layout.update(0, 2, ["aaaa"], 4, True, doc_a)
    assert layout.rebuild_count == 3
    assert layout.display_count() == 2


def test_disabled_wrap_identity_update_is_o1(monkeypatch: pytest.MonkeyPatch) -> None:
    """Wrap-off rebuilds never scan the document (default-state hot path)."""
    calls: list[str] = []

    def counting_offsets(line: str, tab_width: int) -> list[int]:
        calls.append(line)
        return [0] * (len(line) + 1)

    monkeypatch.setattr(wrap_module, "cell_offsets", counting_offsets)
    layout = WrapLayout()
    lines = ["x" * 80 for _ in range(20_000)]
    layout.update(1, 40, lines, 4, False)
    assert layout.rebuild_count == 1
    assert calls == []
    # identity queries still answer correctly without a materialized table
    assert layout.display_count() == 20_000
    assert layout.display_to_logical(19_999) == RowSpan(19_999, 0, 0, 0)
    assert layout.display_to_logical(20_000) is None
    assert layout.logical_to_display(7, 12) == (7, 12)
    assert layout.logical_display_rows(7) == 1
    # an edit bumps the version: rebuild is counted, but still no line scan
    layout.update(2, 40, lines, 4, False)
    assert layout.rebuild_count == 2
    assert calls == []
