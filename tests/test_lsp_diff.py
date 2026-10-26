"""Differential guard for the incremental didChange diff.

The guard replays :func:`yate.editor_lsp.diff.build_change_patches` output
through a server simulator (:func:`apply_changes`) that applies content
changes exactly as an LSP server must: ranges are UTF-16 code-unit
coordinates on the pre-change document, applied one change at a time.  The
simulator deliberately shares no forward logic with ``diff.py`` -- it only
uses :func:`yate.editor_lsp.parsing._from_utf16` and the protocol
semantics -- so a shared bug cannot validate itself.

Two layers of coverage:

- a seeded randomized guard: random documents (astral characters, CJK,
  empty lines) hit with random edit sequences (insert / delete / replace /
  cross-line splice / wipe), asserting byte-exact equality between the
  simulated incremental final state and the full text every step
  (2000 groups by default; ``YATE_LSP_DIFF_STRESS=1`` raises it to
  100000 for the pre-merge stress round);
- directed cases pinning the tricky coordinates: edits around astral
  characters, line start / end, empty lines, whole-document deletion,
  first-row edits, and the no-change fast path, plus the
  ``_to_utf16`` / ``_from_utf16`` round-trip identity.
"""

from __future__ import annotations

import os
import random
from collections.abc import Sequence
from typing import cast

from yate.editor_lsp.diff import ChangePatch, build_change_patches
from yate.editor_lsp.parsing import _from_utf16, _to_utf16

#: Characters randomized documents are drawn from (code points only; new
#: lines are built separately so line content never contains ``"\n"``).
_LINE_CHARS = "abc XYZ\t你好世界\U0001F600\U0001F40D"

#: Edit payloads may additionally splice rows via ``"\n"``.
_EDIT_CHARS = _LINE_CHARS + "\n"


def _apply_one(lines: list[str], change: dict[str, object]) -> list[str]:
    """Apply a single LSP content change to a line snapshot."""
    rng = cast(dict[str, object], change["range"])
    start = cast(dict[str, object], rng["start"])
    end = cast(dict[str, object], rng["end"])
    text = cast(str, change["text"])
    start_row = cast(int, start["line"])
    start_col = cast(int, start["character"])
    end_row = cast(int, end["line"])
    end_col = cast(int, end["character"])

    # LSP clamping: positions past the document resolve to its end.
    if start_row >= len(lines):
        start_row = end_row = len(lines) - 1
        start_col = end_col = len(lines[-1])
    elif end_row >= len(lines):
        end_row = len(lines) - 1
        end_col = len(lines[end_row])

    start_cp = _from_utf16(lines[start_row], start_col)
    end_cp = _from_utf16(lines[end_row], end_col)
    prefix = lines[start_row][:start_cp]
    suffix = lines[end_row][end_cp:]
    inserted = text.split("\n")
    inserted[0] = prefix + inserted[0]
    inserted[-1] = inserted[-1] + suffix
    return lines[:start_row] + inserted + lines[end_row + 1 :]


def apply_changes(
    snapshot_lines: Sequence[str], content_changes: Sequence[dict[str, object]]
) -> list[str]:
    """Replay LSP ``contentChanges`` on a line snapshot, server-style.

    Changes are applied in order, each against the document produced by
    the previous one, per the LSP specification.  The snapshot is the
    pre-change line list; an empty snapshot behaves as a single empty
    line, matching what a server sees for a freshly opened empty document.
    """
    lines = list(snapshot_lines) if snapshot_lines else [""]
    for change in content_changes:
        lines = _apply_one(lines, change)
    return lines


def _patch_to_wire(patch: ChangePatch) -> dict[str, object]:
    """Convert a :class:`ChangePatch` to the LSP wire ``contentChanges``
    item shape."""
    return {
        "range": {
            "start": {"line": patch.start_row, "character": patch.start_col_utf16},
            "end": {"line": patch.end_row, "character": patch.end_col_utf16},
        },
        "rangeLength": patch.range_length_utf16,
        "text": patch.text,
    }


def _random_lines(rng: random.Random, count: int, chars: str) -> list[str]:
    """Build ``count`` random lines from ``chars`` (empty lines included)."""
    return [
        "".join(rng.choice(chars) for _ in range(rng.randint(0, 8)))
        for _ in range(count)
    ]


def _random_edit(rng: random.Random, text: str) -> str:
    """Apply one random edit (insert / delete / replace / wipe) to text."""
    kind = rng.choice(("insert", "delete", "replace", "wipe"))
    if kind == "wipe":
        return ""
    if not text:
        kind = "insert"
    pos = rng.randint(0, len(text))
    if kind == "insert":
        payload = "".join(rng.choice(_EDIT_CHARS) for _ in range(rng.randint(0, 10)))
        return text[:pos] + payload + text[pos:]
    end = rng.randint(pos, len(text))
    if kind == "delete":
        return text[:pos] + text[end:]
    payload = "".join(rng.choice(_EDIT_CHARS) for _ in range(rng.randint(0, 10)))
    return text[:pos] + payload + text[end:]


def _run_random_guard(rng: random.Random, groups: int) -> None:
    """Run the randomized differential guard for ``groups`` documents.

    Every step asserts that replaying the produced patches through the
    server simulator reproduces the full target text byte for byte, and
    that the diff never emits more than one contiguous change.
    """
    for _ in range(groups):
        text = "\n".join(_random_lines(rng, rng.randint(1, 6), _LINE_CHARS))
        for _ in range(rng.randint(1, 5)):
            new_text = _random_edit(rng, text)
            old_lines = text.split("\n") if text else []
            new_lines = new_text.split("\n") if new_text else []
            patches = build_change_patches(old_lines, new_lines)
            assert len(patches) <= 1, f"multiple patches for {old_lines!r} -> {new_lines!r}"
            replay = apply_changes(old_lines, [_patch_to_wire(p) for p in patches])
            replay_text = "\n".join(replay)
            assert replay_text == new_text, (
                f"mismatch: old={old_lines!r} new={new_lines!r} "
                f"patches={patches!r} replay={replay_text!r}"
            )
            text = new_text


def test_random_differential_guard_matches_full_text() -> None:
    """Seeded random edit sequences replay to the exact full text."""
    groups = 100000 if os.environ.get("YATE_LSP_DIFF_STRESS") == "1" else 2000
    _run_random_guard(random.Random(20260101), groups)


def test_no_change_yields_no_patches() -> None:
    """Equal snapshots produce an empty patch list."""
    assert build_change_patches(["a", "b"], ["a", "b"]) == []
    assert build_change_patches([], []) == []


def test_edit_after_astral_character_uses_utf16_columns() -> None:
    """An edit right of U+1F600 counts the emoji as two code units."""
    old = ["a\U0001F600b"]
    new = ["a\U0001F600c"]
    (patch,) = build_change_patches(old, new)
    assert (patch.start_row, patch.start_col_utf16) == (0, 3)
    assert (patch.end_row, patch.end_col_utf16) == (0, 4)
    assert patch.range_length_utf16 == 1
    assert patch.text == "c"
    replay = apply_changes(old, [_patch_to_wire(patch)])
    assert replay == new


def test_edit_before_astral_character_uses_utf16_columns() -> None:
    """An edit left of U+1F600 keeps the emoji untouched in the range."""
    old = ["\U0001F600ab"]
    new = ["\U0001F600xb"]
    (patch,) = build_change_patches(old, new)
    assert (patch.start_row, patch.start_col_utf16) == (0, 2)
    assert (patch.end_row, patch.end_col_utf16) == (0, 3)
    assert patch.range_length_utf16 == 1
    assert patch.text == "x"
    replay = apply_changes(old, [_patch_to_wire(patch)])
    assert replay == new


def test_edit_at_line_start_shrinks_to_inserted_text() -> None:
    """Prepending at column zero yields a zero-width range at the start."""
    (patch,) = build_change_patches(["abc"], ["Xabc"])
    assert (patch.start_row, patch.start_col_utf16) == (0, 0)
    assert (patch.end_row, patch.end_col_utf16) == (0, 0)
    assert patch.text == "X"
    assert apply_changes(["abc"], [_patch_to_wire(patch)]) == ["Xabc"]


def test_edit_at_line_end_appends_via_zero_width_range() -> None:
    """Appending at end of line yields a zero-width range after the text."""
    (patch,) = build_change_patches(["abc"], ["abcX"])
    assert (patch.start_row, patch.start_col_utf16) == (0, 3)
    assert (patch.end_row, patch.end_col_utf16) == (0, 3)
    assert patch.text == "X"
    assert apply_changes(["abc"], [_patch_to_wire(patch)]) == ["abcX"]


def test_empty_line_edits_stay_in_bounds() -> None:
    """Edits touching empty lines keep zero columns and replay exactly."""
    (patch,) = build_change_patches(["a", "", "b"], ["a", "x", "b"])
    assert (patch.start_row, patch.start_col_utf16) == (1, 0)
    assert (patch.end_row, patch.end_col_utf16) == (1, 0)
    assert patch.text == "x"
    assert apply_changes(["a", "", "b"], [_patch_to_wire(patch)]) == ["a", "x", "b"]

    (patch,) = build_change_patches([""], ["y"])
    assert (patch.start_row, patch.start_col_utf16) == (0, 0)
    assert patch.text == "y"
    assert apply_changes([""], [_patch_to_wire(patch)]) == ["y"]


def test_whole_document_deletion_spans_all_rows() -> None:
    """Deleting everything produces one full-span patch with empty text."""
    (patch,) = build_change_patches(["hello", "world"], [])
    assert (patch.start_row, patch.start_col_utf16) == (0, 0)
    assert (patch.end_row, patch.end_col_utf16) == (1, 5)
    assert patch.range_length_utf16 == 11
    assert patch.text == ""
    assert apply_changes(["hello", "world"], [_patch_to_wire(patch)]) == [""]


def test_first_row_edit_keeps_later_rows_out_of_the_range() -> None:
    """An edit on the first row aligns the trailing rows into the suffix."""
    (patch,) = build_change_patches(["ab", "cd"], ["axb", "cd"])
    assert (patch.start_row, patch.start_col_utf16) == (0, 1)
    assert (patch.end_row, patch.end_col_utf16) == (0, 1)
    assert patch.text == "x"
    assert apply_changes(["ab", "cd"], [_patch_to_wire(patch)]) == ["axb", "cd"]


def test_cross_line_splice_collapses_to_single_patch() -> None:
    """A two-row region replaced by one row keeps UTF-16 newline counts."""
    (patch,) = build_change_patches(["ab", "cd"], ["aXbcd"])
    assert (patch.start_row, patch.start_col_utf16) == (0, 1)
    assert (patch.end_row, patch.end_col_utf16) == (1, 0)
    assert patch.range_length_utf16 == 2
    assert patch.text == "Xb"
    assert apply_changes(["ab", "cd"], [_patch_to_wire(patch)]) == ["aXbcd"]


def test_pure_row_insertion_carries_trailing_line_break() -> None:
    """Inserting whole rows must close the carried text with a break.

    A zero-width range at (pre, 0) with a plain join would splice the last
    inserted row onto the existing row ``pre``; the range therefore anchors
    at the end of the previous row and the text opens with the break.
    """
    (patch,) = build_change_patches(["a", "c"], ["a", "b", "c"])
    assert (patch.start_row, patch.start_col_utf16) == (0, 1)
    assert (patch.end_row, patch.end_col_utf16) == (0, 1)
    assert patch.range_length_utf16 == 0
    assert patch.text == "\nb"
    assert apply_changes(["a", "c"], [_patch_to_wire(patch)]) == ["a", "b", "c"]

    (patch,) = build_change_patches(["a"], ["b", "a"])
    assert (patch.start_row, patch.start_col_utf16) == (0, 0)
    assert patch.text == "b\n"
    assert apply_changes(["a"], [_patch_to_wire(patch)]) == ["b", "a"]

    (patch,) = build_change_patches([], ["b", "a"])
    assert (patch.start_row, patch.start_col_utf16) == (0, 0)
    assert patch.text == "b\na"
    assert apply_changes([], [_patch_to_wire(patch)]) == ["b", "a"]


def test_pure_row_deletion_swallows_one_line_break() -> None:
    """Deleting whole rows removes the rows, not just their contents."""
    (patch,) = build_change_patches(["a", "b", "c"], ["a", "c"])
    assert (patch.start_row, patch.start_col_utf16) == (1, 0)
    assert (patch.end_row, patch.end_col_utf16) == (2, 0)
    assert patch.range_length_utf16 == 2
    assert patch.text == ""
    assert apply_changes(["a", "b", "c"], [_patch_to_wire(patch)]) == ["a", "c"]

    # Block running to end of document anchors at the previous row's end.
    (patch,) = build_change_patches(["a", "b", "c"], ["a"])
    assert (patch.start_row, patch.start_col_utf16) == (0, 1)
    assert (patch.end_row, patch.end_col_utf16) == (2, 1)
    assert apply_changes(["a", "b", "c"], [_patch_to_wire(patch)]) == ["a"]


def test_utf16_helpers_round_trip_identity() -> None:
    """``_from_utf16(_to_utf16(line, cp)) == cp`` for every split point."""
    samples = ["", "abc", "你好world", "a\U0001F600b", "你好\U0001F600x", "\t "]
    for line in samples:
        for cp in range(len(line) + 1):
            assert _from_utf16(line, _to_utf16(line, cp)) == cp
