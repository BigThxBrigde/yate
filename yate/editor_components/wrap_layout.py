"""Pure soft-wrap layout: maps logical buffer lines to display rows.

This module owns the display-line geometry for soft wrap (issue IKVRXT,
plan A).  It is a plain L2 helper in the spirit of
:mod:`yate.editor_components.cells`: no Textual widget base, no theme
dependency, no buffer mutation -- only cell arithmetic over the line
strings handed to :meth:`WrapLayout.update`.

Width authority is :func:`yate.editor_components.cells.cell_offsets`
(tabs expand to the next tab stop, wide glyphs occupy two cells, combining
marks attach to the previous cell).  Wrapping is character-level: a span
ends at the last character that still fits into ``text_w`` cells, and a
character whose expansion would straddle the boundary (a wide glyph or an
overshooting tab) is pushed wholly onto the next display row, so tab
expansions and wide glyphs are never split across rows (AC2).

Caching contract (AC8): :meth:`WrapLayout.update` is called every render
frame, but it rebuilds the span table only when the cache key
``(content_version, text_w, wrap_enabled, document)`` changes.
``content_version`` is bumped by every buffer edit and by chunked
``fill_lines`` / ``extend_placeholders``, so a stable key guarantees the
``lines`` sequence is unchanged and the cached mapping stays valid; on a key
change the table is rebuilt once per change, never once per frame.

Wrap disabled is the default state and takes an O(1) identity fast path: the
mapping is ``display_row == logical_row`` and no span table is materialized.
The no-wrap render path windows lines with ``scroll_col`` and never consumes
a span's cell window, so building an identity table over every logical line
on each keystroke would be pure O(document) work (the perf-audit pattern).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import NamedTuple

from yate.editor_components.cells import cell_offsets

__all__ = ["RowSpan", "WrapLayout"]


class RowSpan(NamedTuple):
    """One display row: a cell window of a logical line.

    ``logical_row`` is the owning buffer line, ``cell_start`` / ``cell_end``
    delimit the half-open cell window inside that line's expanded cell
    sequence, and ``continuation`` is the display-row index within the
    logical row (0 for its first display row).
    """

    logical_row: int
    cell_start: int
    cell_end: int
    continuation: int


def _wrap_line(line: str, logical_row: int, text_w: int, tab_width: int) -> list[RowSpan]:
    """Cut *line* into display spans of at most *text_w* cells each.

    Spans are cell windows of the line's expanded cell sequence (see
    :func:`yate.editor_components.cells.cell_offsets`).  A character whose
    expansion would cross the row boundary (a wide glyph or an overshooting
    tab) starts the next span instead, so neither is ever split; a lone
    character wider than *text_w* still gets its own span so every display
    row shows at least one character.
    """
    offsets = cell_offsets(line, tab_width)
    if not line:
        return [RowSpan(logical_row, 0, 0, 0)]
    spans: list[RowSpan] = []
    start = 0
    total = len(line)
    while start < total:
        base = offsets[start]
        end = start
        while end < total and offsets[end + 1] - base <= text_w:
            end += 1
        if end == start:
            end = start + 1
        spans.append(RowSpan(logical_row, base, offsets[end], len(spans)))
        start = end
    return spans


class WrapLayout:
    """Incremental cache mapping logical buffer lines to display rows.

    The layout keeps one :class:`RowSpan` per display row plus a prefix-sum
    array :attr:`cumulative`, where ``cumulative[i]`` is the number of
    display rows before logical line ``i``; :attr:`version_key` mirrors the
    cache key ``(content_version, text_w, wrap_enabled)`` of the last
    rebuild.

    When wrap is disabled the mapping is the identity: every logical line
    yields exactly one display row spanning its full expanded cell width,
    so no-wrap rendering stays byte-identical to the unwrapped path (AC3).
    An empty line -- including an unloaded chunked placeholder row -- always
    yields exactly one display row (AC7).
    """

    def __init__(self) -> None:
        self.logical_rows: list[RowSpan] = []
        self.cumulative: list[int] = [0]
        self.version_key: tuple[int, int, bool, object | None] | None = None
        #: Number of span-table rebuilds performed; test seam for the AC8
        #: "no rebuild while the cache key is unchanged" guarantee.
        self.rebuild_count: int = 0
        self._identity: bool = False
        self._identity_count: int = 0

    def update(
        self,
        version: int,
        text_w: int,
        lines: Sequence[str],
        tab_width: int,
        enabled: bool,
        identity: object | None = None,
    ) -> None:
        """Refresh the mapping for *lines*; rebuild only when the key changed.

        Called once per render frame with the buffer's ``content_version``
        as *version*, the text-area width in cells as *text_w*, the logical
        line list, the editor *tab_width*, the soft-wrap switch *enabled*,
        and an optional *identity* of the owning document.  The rebuild runs
        only when ``(version, text_w, enabled, identity)`` differs from the
        cached key: a stable version proves the line contents are unchanged,
        so the cached spans stay valid and the per-frame cost is a tuple
        comparison (AC8).  *identity* must be passed by views that can
        rebind to a different document: a freshly opened document also starts
        at content version 0, so without the document identity a tab switch
        between two unedited files would reuse the previous file's spans
        (AC2/AC6).
        """
        key = (version, text_w, enabled, identity)
        if key == self.version_key:
            return
        self.version_key = key
        self.rebuild_count += 1
        self._identity = not enabled
        if not enabled:
            # O(1) identity fast path: no-wrap rendering windows lines with
            # scroll_col and never reads a span's cell window, so building an
            # identity table of every line on each keystroke is wasted O(n).
            self._identity_count = len(lines)
            self.logical_rows = []
            self.cumulative = [0]
            return
        rows: list[RowSpan] = []
        cumulative: list[int] = [0]
        for row, line in enumerate(lines):
            rows.extend(_wrap_line(line, row, text_w, tab_width))
            cumulative.append(len(rows))
        self.logical_rows = rows
        self.cumulative = cumulative

    def display_count(self) -> int:
        """Return the total number of display rows (virtual-size height)."""
        if self._identity:
            return self._identity_count
        return self.cumulative[-1]

    def display_to_logical(self, display_row: int) -> RowSpan | None:
        """Return the span shown at *display_row*, or ``None`` if out of range.

        Span ``k`` in :attr:`logical_rows` is exactly display row ``k``:
        every logical line contributes at least one span and the spans are
        appended in line order, so the lookup is a direct O(1) index after a
        bounds check against :attr:`cumulative`.  With wrapping disabled the
        identity fast path returns the trivial span without materializing a
        table: ``cell_start`` / ``cell_end`` are unused by the no-wrap render
        path (which windows with ``scroll_col`` instead).
        """
        if self._identity:
            if display_row < 0 or display_row >= self._identity_count:
                return None
            return RowSpan(display_row, 0, 0, 0)
        if display_row < 0 or display_row >= self.cumulative[-1]:
            return None
        return self.logical_rows[display_row]

    def logical_to_display(self, row: int, cell_col: int) -> tuple[int, int]:
        """Locate *cell_col* of logical *row*; return display row and offset.

        Returns ``(display_row, cell_col - span.cell_start)`` where the
        display row is the span whose cell window contains *cell_col* (a
        boundary cell belongs to the span starting there), used by cursor
        exposure.  A *row* outside the buffer clamps to the nearest line; a
        cell past the end of the line clamps to its last display row; an
        empty layout (never updated, or updated with no lines) returns
        ``(0, 0)``.
        """
        if self._identity:
            if not self._identity_count:
                return (0, 0)
            return (min(max(row, 0), self._identity_count - 1), max(0, cell_col))
        if not self.logical_rows:
            return (0, 0)
        row = min(max(row, 0), len(self.cumulative) - 2)
        first = self.cumulative[row]
        last = self.cumulative[row + 1] - 1
        if cell_col < 0:
            cell_col = 0
        for index in range(first, last):
            span = self.logical_rows[index]
            if cell_col < span.cell_end:
                return (index, cell_col - span.cell_start)
        return (last, cell_col - self.logical_rows[last].cell_start)

    def logical_display_rows(self, row: int) -> int:
        """Return how many display rows logical *row* occupies.

        Out-of-range rows (including an empty layout) report ``0``; every
        in-range line reports at least ``1``.
        """
        if self._identity:
            return 1 if 0 <= row < self._identity_count else 0
        if row < 0 or row >= len(self.cumulative) - 1:
            return 0
        return self.cumulative[row + 1] - self.cumulative[row]
