"""Pure line/character diff and 3-way merge region computation.

stdlib-only (``difflib`` + ``dataclasses``): no Textual, no imports from
upper layers (architecture R4/R12).  Every interval is a 0-based half-open
index range, aligned with :class:`yate.editor_core.buffer.TextBuffer`
position conventions so that :func:`hunk_replacement` results feed
:meth:`yate.editor_core.buffer.TextBuffer.replace_range` directly.

Usage in a merge/diff viewer::

    result = diff_lines(left_lines, right_lines)
    for hunk in result.hunks:
        start, end, text = hunk_replacement(left_lines, hunk, right_lines,
                                            copy_into="b")
"""

from __future__ import annotations

import difflib
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Literal

from yate.editor_core.buffer import Pos


@dataclass(frozen=True)
class DiffHunk:
    """One changed line span between the two sides of a line diff.

    ``kind`` is ``"replace"``, ``"insert"`` or ``"delete"``; ``a_*`` and
    ``b_*`` bounds are 0-based half-open line indexes into the respective
    side (insert hunks leave the a-span empty, delete hunks the b-span).
    """

    kind: str
    a_start: int
    a_end: int
    b_start: int
    b_end: int


@dataclass(frozen=True)
class DiffResult:
    """Line diff result: hunks, side sizes and a precomputed row map.

    ``_row_map`` is built while the opcodes are walked so :meth:`align`
    answers in O(1) per query; it is excluded from repr and equality.
    """

    hunks: list[DiffHunk]
    a_lines: int
    b_lines: int
    _row_map: tuple[int, ...] = field(repr=False, compare=False)

    def align(self, row: int) -> int:
        """Map a left-side row to its right-side anchor row.

        Rows in equal regions map linearly onto the right side; rows
        inside a hunk anchor to that hunk's ``b_start`` (used to scroll
        both panes of a diff view to the same difference).
        """
        return self._row_map[row]


@dataclass(frozen=True)
class MergeRegion:
    """One classified region of a 3-way merge.

    ``kind`` is ``"same"``, ``"local"``, ``"remote"``, ``"both"`` or
    ``"conflict"``; the three interval pairs are 0-based half-open line
    indexes into *base*, *local* and *remote* respectively.
    """

    kind: str
    base_start: int
    base_end: int
    local_start: int
    local_end: int
    remote_start: int
    remote_end: int


def diff_lines(a: Sequence[str], b: Sequence[str]) -> DiffResult:
    """Diff two line sequences and return hunks plus a row alignment map.

    ``difflib.SequenceMatcher`` runs with ``autojunk=False``: the default
    heuristic treats high-frequency lines as junk on inputs longer than
    200 lines and shifts hunk bounds there (locked by the plan-a guard
    test).  Opcode tags map one-to-one onto :class:`DiffHunk` fields;
    ``equal`` runs only contribute to the alignment map.
    """
    matcher = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    hunks: list[DiffHunk] = []
    row_map: list[int] = [0] * len(a)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for row in range(i1, i2):
                row_map[row] = j1 + (row - i1)
            continue
        for row in range(i1, i2):
            row_map[row] = j1
        hunks.append(DiffHunk(kind=tag, a_start=i1, a_end=i2, b_start=j1, b_end=j2))
    return DiffResult(
        hunks=hunks,
        a_lines=len(a),
        b_lines=len(b),
        _row_map=tuple(row_map),
    )


def diff_words(a: str, b: str) -> tuple[list[tuple[int, int]], list[tuple[int, int]]]:
    """Compute intra-line highlight ranges for a pair of single lines.

    Character-level ``SequenceMatcher`` (``autojunk=False`` for the same
    reason as :func:`diff_lines`); returns the non-equal ``(start, end)``
    character spans (half-open) for each side, ready to be rendered as
    intra-line highlight ranges on a replace-type hunk pair.
    """
    matcher = difflib.SequenceMatcher(None, a, b, autojunk=False)
    a_ranges: list[tuple[int, int]] = []
    b_ranges: list[tuple[int, int]] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        a_ranges.append((i1, i2))
        b_ranges.append((j1, j2))
    return a_ranges, b_ranges


def diff3_regions(
    base: Sequence[str],
    local: Sequence[str],
    remote: Sequence[str],
) -> list[MergeRegion]:
    """Classify 3-way merge regions between *base*, *local* and *remote*.

    Base line spans touched by either side are coalesced into contiguous
    regions (overlapping or adjacent spans merge) and classified:
    one-sided edits become ``"local"`` / ``"remote"``, identical edits on
    both sides ``"both"``, differing edits ``"conflict"``.  Untouched base
    spans are reported as ``"same"`` and kept in the output -- callers
    filter by ``kind`` as needed.  Region order follows the base line
    order.
    """
    local_ops = difflib.SequenceMatcher(a=base, b=local, autojunk=False).get_opcodes()
    remote_ops = difflib.SequenceMatcher(a=base, b=remote, autojunk=False).get_opcodes()
    local_changed = [(i1, i2) for tag, i1, i2, _j1, _j2 in local_ops if tag != "equal"]
    remote_changed = [(i1, i2) for tag, i1, i2, _j1, _j2 in remote_ops if tag != "equal"]

    def classify(base_start: int, base_end: int) -> MergeRegion:
        local_start, local_end = _side_span(local_ops, base_start, base_end)
        remote_start, remote_end = _side_span(remote_ops, base_start, base_end)
        local_touched = any(s < base_end and e > base_start for s, e in local_changed)
        remote_touched = any(s < base_end and e > base_start for s, e in remote_changed)
        if local_touched and remote_touched:
            identical = list(local[local_start:local_end]) == list(
                remote[remote_start:remote_end]
            )
            kind = "both" if identical else "conflict"
        elif local_touched:
            kind = "local"
        elif remote_touched:
            kind = "remote"
        else:
            kind = "same"
        return MergeRegion(
            kind=kind,
            base_start=base_start,
            base_end=base_end,
            local_start=local_start,
            local_end=local_end,
            remote_start=remote_start,
            remote_end=remote_end,
        )

    regions: list[MergeRegion] = []
    cursor = 0
    for base_start, base_end in _merge_spans([*local_changed, *remote_changed]):
        if cursor < base_start:
            regions.append(classify(cursor, base_start))
        regions.append(classify(base_start, base_end))
        cursor = base_end
    if cursor < len(base):
        regions.append(classify(cursor, len(base)))
    return regions


def hunk_replacement(
    target: Sequence[str],
    hunk: DiffHunk,
    source: Sequence[str],
    copy_into: Literal["a", "b"],
) -> tuple[Pos, Pos, str]:
    """Build a ``TextBuffer.replace_range`` triple applying *hunk* to *target*.

    ``copy_into`` names the diff side whose content is copied: with
    ``"b"`` the *target* lines follow side **a** of *hunk* and the
    replacement text is the side-**b** span of ``source`` (``"a"`` is the
    symmetric case with *target* on side b).  The returned
    ``(start, end, text)`` feeds
    :meth:`yate.editor_core.buffer.TextBuffer.replace_range` directly:
    ``end`` falls back to the last line's end when the span reaches end of
    file, a pure end-of-file insertion collapses to that position with
    a leading ``"\\n"`` so the new lines append after it, and a
    mid-document span re-emits the newline its range consumes (an empty
    replacement is a pure line deletion and keeps no trailing newline).
    The buffer itself is never touched here -- the caller applies the
    triple, which keeps this module unit-testable.
    """
    if copy_into == "b":
        t_start, t_end = hunk.a_start, hunk.a_end
        s_start, s_end = hunk.b_start, hunk.b_end
    else:
        t_start, t_end = hunk.b_start, hunk.b_end
        s_start, s_end = hunk.a_start, hunk.a_end
    text = "\n".join(source[s_start:s_end])
    line_count = len(target)
    if t_end < line_count:
        # A (t_start, 0) - (t_end, 0) span consumes the newline after the
        # last replaced line; re-emit it so the following line stays put.
        # An empty text is a pure line deletion and needs no newline.
        if text:
            text += "\n"
        return (t_start, 0), (t_end, 0), text
    if line_count == 0:
        # Empty target: the only expressible position is the document start.
        return (0, 0), (0, 0), text
    # Span reaches EOF: the half-open end lands on the last line's end.
    eof: Pos = (line_count - 1, len(target[line_count - 1]))
    if t_start == t_end:
        return eof, eof, "\n" + text
    return (t_start, 0), eof, text


def _merge_spans(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Coalesce overlapping or adjacent half-open spans into sorted runs."""
    merged: list[list[int]] = []
    for start, end in sorted(spans):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return [(start, end) for start, end in merged]


def _side_span(
    ops: Sequence[tuple[str, int, int, int, int]],
    start: int,
    end: int,
) -> tuple[int, int]:
    """Map a base line span onto one side via that side's opcodes.

    Equal coverage maps linearly; a non-equal hunk overlapping the span
    contributes its whole target interval.  Hunks never straddle a merged
    region boundary (regions are built from the coalesced hunk spans), so
    partial overlaps cannot occur.
    """
    pieces: list[tuple[int, int]] = []
    for tag, i1, i2, j1, j2 in ops:
        if i2 <= start:
            continue
        if i1 >= end:
            break
        if tag == "equal":
            pieces.append((j1 + max(i1, start) - i1, j1 + min(i2, end) - i1))
        else:
            pieces.append((j1, j2))
    if not pieces:
        raise ValueError(f"base span [{start}, {end}) is not covered by opcodes")
    return pieces[0][0], pieces[-1][1]
