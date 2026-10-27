"""Incremental didChange diff for the LSP manager.

Pure functions turning the row-snapshot diff between the last-synced line
tuple and the current buffer lines into a single contiguous LSP content
change, plus the :class:`ChangePatch` record that carries it.  The change
range is expressed in LSP UTF-16 code-unit coordinates resolved against
the *old* document, exactly what an incremental ``textDocument/didChange``
consumer expects.

No I/O and no Textual imports: ``editor_lsp`` is an L0 leaf package and
this module must stay a pure computation the manager can call from its
incremental send path.  Row alignment (common prefix / suffix) yields at
most one contiguous change region; an in-line character-level prefix /
suffix refinement then shrinks the region where both sides share edge
characters, with a bounds self-check that falls back to the row-level
patch whenever the refinement would overlap itself.

Usage in :mod:`yate.editor_lsp.manager`::

    from yate.editor_lsp.diff import build_change_patches

    patches = build_change_patches(state.last_synced_lines, new_lines)
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from yate.editor_lsp.parsing import _to_utf16

__all__ = [
    "ChangePatch",
    "build_change_patches",
    "build_content_changes",
]


@dataclass(frozen=True)
class ChangePatch:
    """A single LSP content change derived from a row-snapshot diff.

    ``start_row`` / ``end_row`` are zero-based rows and
    ``start_col_utf16`` / ``end_col_utf16`` are UTF-16 code-unit columns,
    all resolved against the *old* document (the last-synced snapshot) --
    the coordinate frame a server applies ``didChange`` ranges in.
    ``range_length_utf16`` is the UTF-16 code-unit count of the replaced
    span (one extra unit per interior line break); it is advisory only --
    LSP deprecated the wire ``rangeLength`` field, so it is sent along for
    debugging and older servers but carries no semantic weight.
    ``text`` is the replacement text with lines joined by ``"\n"``.
    """

    start_row: int
    start_col_utf16: int
    end_row: int
    end_col_utf16: int
    range_length_utf16: int
    text: str


def _common_prefix_len(a: str, b: str) -> int:
    """Return the length of the longest common code-point prefix."""
    n = min(len(a), len(b))
    i = 0
    while i < n and a[i] == b[i]:
        i += 1
    return i


def _common_suffix_len(a: str, b: str) -> int:
    """Return the length of the longest common code-point suffix."""
    n = min(len(a), len(b))
    i = 0
    while i < n and a[len(a) - 1 - i] == b[len(b) - 1 - i]:
        i += 1
    return i


def _refinement_fits(
    old_mid: Sequence[str], new_mid: Sequence[str], pc: int, sc: int
) -> bool:
    """Check that an in-line refinement keeps both sides non-overlapping.

    When the old (or new) region is a single row, the prefix trim and the
    suffix trim both land on that row and must not cross: ``pc + sc`` may
    not exceed the row length.  Multi-row regions trim different rows on
    each side, so the per-row bounds hold by construction.
    """
    if len(old_mid) == 1 and pc + sc > len(old_mid[0]):
        return False
    if len(new_mid) == 1 and pc + sc > len(new_mid[0]):
        return False
    return True


def _replacement_text(new_mid: Sequence[str], pc: int, sc: int) -> str:
    """Build the replacement text for the refined new region.

    The first ``pc`` code points of the first row and the last ``sc`` code
    points of the last row are kept by the range itself, so the text only
    carries the shrunk interior.
    """
    # Contract: callers only reach the replacement path with a non-empty
    # new region -- pure deletions return earlier with empty text.
    assert new_mid
    if len(new_mid) == 1:
        line = new_mid[0]
        return line[pc : len(line) - sc]
    first = new_mid[0][pc:]
    last = new_mid[-1][: len(new_mid[-1]) - sc]
    return "\n".join([first, *new_mid[1:-1], last])


def build_change_patches(
    old_lines: Sequence[str], new_lines: Sequence[str]
) -> list[ChangePatch]:
    """Diff two line snapshots into at most one contiguous change patch.

    Row-level common prefix / suffix alignment isolates a single changed
    region ``old[pre:len(old)-suf]`` vs ``new[pre:len(new)-suf]``; when the
    regions are equal (no change at all) the result is an empty list.  An
    in-line character-level prefix / suffix refinement then shrinks the
    region on its first/last rows, falling back to the row-level patch if
    the refinement would overlap itself.  A pure insertion (empty old
    region) produces a zero-width range at the insertion point; a pure
    deletion (empty new region, e.g. the whole document wiped) produces a
    single patch spanning the deleted rows plus one adjacent line break
    (so the rows themselves disappear, not just their contents) with
    empty text.

    Range coordinates are UTF-16 code units resolved against *old_lines*
    via :func:`yate.editor_lsp.parsing._to_utf16`; character comparisons
    are code-point based (Python ``str``), so non-BMP characters survive
    both the alignment and the coordinate conversion.
    """
    old = list(old_lines)
    new = list(new_lines)
    pre = 0
    while pre < len(old) and pre < len(new) and old[pre] == new[pre]:
        pre += 1
    suf = 0
    while (
        suf < len(old) - pre
        and suf < len(new) - pre
        and old[len(old) - 1 - suf] == new[len(new) - 1 - suf]
    ):
        suf += 1
    old_mid = old[pre : len(old) - suf]
    new_mid = new[pre : len(new) - suf]
    if not old_mid and not new_mid:
        return []

    pc = 0
    sc = 0
    if old_mid and new_mid:
        pc = _common_prefix_len(old_mid[0], new_mid[0])
        sc = _common_suffix_len(old_mid[-1], new_mid[-1])
        if not _refinement_fits(old_mid, new_mid, pc, sc):
            pc = 0
            sc = 0

    if not old_mid:
        # Pure insertion.  A zero-width range at (pre, 0) with plain
        # ``"\n".join(new_mid)`` would splice the last inserted row onto
        # the existing row ``pre`` (no line break between them), so the
        # carried text must close with a line break -- except on an empty
        # document, whose single empty row already provides it.  Anchoring
        # at the end of the previous row (pre > 0) avoids relying on
        # end-of-document clamping for append-at-end insertions.
        if not old:
            start_row = end_row = 0
            start_col = end_col = 0
            text = "\n".join(new_mid)
        elif pre == 0:
            start_row = end_row = 0
            start_col = end_col = 0
            text = "\n".join(new_mid) + "\n"
        else:
            start_row = end_row = pre - 1
            start_col = end_col = _to_utf16(old[pre - 1], len(old[pre - 1]))
            text = "\n" + "\n".join(new_mid)
        return [
            ChangePatch(
                start_row=start_row,
                start_col_utf16=start_col,
                end_row=end_row,
                end_col_utf16=end_col,
                range_length_utf16=0,
                text=text,
            )
        ]

    old_first = old_mid[0]
    old_last = old_mid[-1]
    start_row = pre
    end_row = pre + len(old_mid) - 1
    if not new_mid:
        # Pure row deletion.  Removing just the row contents would leave
        # empty rows behind (the row count could not change), so the range
        # must also swallow one adjacent line break: prefer the break after
        # the last deleted row, fall back to the break before the first
        # deleted row when the block runs to end of document, and span the
        # whole document when everything is deleted (a trailing empty row
        # in the replayed document joins to the same full text).
        # The branches only decide the coordinates; the replaced span is
        # always the deleted rows plus one interior line break per row gap.
        if end_row + 1 < len(old):
            start_col = 0
            end_row += 1
            end_col = 0
        elif pre > 0:
            start_row = pre - 1
            start_col = _to_utf16(old[pre - 1], len(old[pre - 1]))
            end_col = _to_utf16(old_last, len(old_last))
        else:
            start_col = 0
            end_col = _to_utf16(old_last, len(old_last))
        range_length = (
            sum(_to_utf16(line, len(line)) for line in old_mid)
            + (end_row - start_row)
        )
        return [
            ChangePatch(
                start_row=start_row,
                start_col_utf16=start_col,
                end_row=end_row,
                end_col_utf16=end_col,
                range_length_utf16=range_length,
                text="",
            )
        ]

    start_col = _to_utf16(old_first, pc)
    end_col = _to_utf16(old_last, len(old_last) - sc)
    spanned = end_row - start_row + 1
    if spanned == 1:
        range_length = end_col - start_col
    else:
        range_length = (
            _to_utf16(old_first, len(old_first))
            - start_col
            + sum(_to_utf16(line, len(line)) for line in old_mid[1:-1])
            + end_col
            + (spanned - 1)
        )
    return [
        ChangePatch(
            start_row=start_row,
            start_col_utf16=start_col,
            end_row=end_row,
            end_col_utf16=end_col,
            range_length_utf16=range_length,
            text=_replacement_text(new_mid, pc, sc),
        )
    ]


def build_content_changes(
    old_lines: Sequence[str], new_lines: Sequence[str]
) -> list[dict[str, Any]]:
    """Build the LSP wire ``contentChanges`` list for a row-snapshot diff.

    Convenience wrapper turning :func:`build_change_patches` output into
    the ``textDocument/didChange`` payload dicts the manager sends: each
    patch becomes ``{"range": {...}, "rangeLength": n, "text": s}`` with
    UTF-16 range coordinates.  The ``dict[str, Any]`` shape matches the
    heterogeneous wire values the LSP client's ``notify`` already takes.
    """
    return [
        {
            "range": {
                "start": {
                    "line": patch.start_row,
                    "character": patch.start_col_utf16,
                },
                "end": {
                    "line": patch.end_row,
                    "character": patch.end_col_utf16,
                },
            },
            "rangeLength": patch.range_length_utf16,
            "text": patch.text,
        }
        for patch in build_change_patches(old_lines, new_lines)
    ]
