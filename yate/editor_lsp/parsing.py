"""Wire-format to buffer-coordinate parsing for the LSP manager.

Pure functions converting LSP wire payloads (untyped JSON dicts with
UTF-16 code-unit columns) into buffer coordinates (code-point columns)
and the typed :class:`~yate.editor_lsp.client.Completion` /
:class:`~yate.editor_lsp.client.Diagnostic` records the editor consumes.
Split out of :mod:`yate.editor_lsp.manager` (big-module-split wave f):
the manager keeps the state orchestration, this module holds the parsing,
and neither imports anything above the ``editor_lsp`` leaf package.

The functions are package-private (consumed only by
:mod:`yate.editor_lsp.manager`, which re-exports the UTF-16 helpers);
they are listed in ``__all__`` so those imports read as deliberate
re-exports to pyright (wave-a private-registry precedent), not as
``reportPrivateUsage`` violations.
"""

from __future__ import annotations

from typing import Any, cast

from yate.editor_core.document import Document

from yate.editor_lsp.client import Completion, Diagnostic, DiagnosticSeverity

__all__ = [
    "_from_utf16",
    "_parse_completion_item",
    "_parse_diagnostics",
    "_range_from",
    "_range_to_buffer_cols",
    "_to_utf16",
    "_unwrap_completion",
]


def _to_utf16(line: str, col: int) -> int:
    """Buffer column (code points) -> LSP UTF-16 code unit offset.

    The LSP spec measures ``character`` offsets in UTF-16 code units, so a
    non-BMP character (emoji, some CJK extension blocks) counts as two.
    ASCII-only lines -- the overwhelming majority -- are the fast path.
    """
    if line.isascii():
        return col
    return len(line[:col].encode("utf-16-le")) // 2


def _from_utf16(line: str, units: int) -> int:
    """LSP UTF-16 code unit offset -> buffer column (code points)."""
    if line.isascii():
        return units
    seen = 0
    for i, ch in enumerate(line):
        if seen >= units:
            return i
        seen += 2 if ord(ch) > 0xFFFF else 1
    return len(line)


def _unwrap_completion(raw: Any) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if isinstance(raw, list):
        return (
            [cast(dict[str, Any], x) for x in cast(list[Any], raw)
             if isinstance(x, dict)],
            {},
        )
    if isinstance(raw, dict):
        payload = cast(dict[str, Any], raw)
        raw_items = payload.get("items")
        raw_defaults = payload.get("itemDefaults")
        items = (
            [cast(dict[str, Any], x) for x in cast(list[Any], raw_items)
             if isinstance(x, dict)]
            if isinstance(raw_items, list) else []
        )
        defaults = (
            cast(dict[str, Any], raw_defaults)
            if isinstance(raw_defaults, dict) else {}
        )
        return items, defaults
    return [], {}


def _range_from(value: Any) -> tuple[int, int, int, int] | None:
    """Normalize Range | {insert,replace} into (r0,c0,r1,c1)."""
    if not isinstance(value, dict):
        return None
    candidate = cast(dict[str, Any], value)
    target_raw = candidate.get("insert") if "insert" in candidate else candidate
    if not isinstance(target_raw, dict):
        return None
    target = cast(dict[str, Any], target_raw)
    start_raw, end_raw = target.get("start"), target.get("end")
    if not isinstance(start_raw, dict) or not isinstance(end_raw, dict):
        return None
    start = cast(dict[str, Any], start_raw)
    end = cast(dict[str, Any], end_raw)
    return (
        int(start.get("line", 0)),
        int(start.get("character", 0)),
        int(end.get("line", 0)),
        int(end.get("character", 0)),
    )


def _range_to_buffer_cols(
    rng: tuple[int, int, int, int], doc: Document
) -> tuple[int, int, int, int]:
    """Convert a server range's UTF-16 columns to buffer columns."""
    r0, c0, r1, c1 = rng
    lines = doc.buffer.lines
    line0 = lines[r0] if 0 <= r0 < len(lines) else ""
    line1 = lines[r1] if 0 <= r1 < len(lines) else ""
    return (r0, _from_utf16(line0, c0), r1, _from_utf16(line1, c1))


def _parse_completion_item(  # noqa: Any - completion items are untyped server wire data
    item: dict[str, Any],
    defaults: dict[str, Any],
    doc: Document,
    row: int,
    col: int,
    prefix_start_col: int,
) -> Completion | None:
    label_raw = item.get("label")
    if not isinstance(label_raw, str) or not label_raw:
        return None
    label = label_raw

    insert_text = label
    text_format = item.get("insertTextFormat")
    text_edit = item.get("textEdit")
    rng: tuple[int, int, int, int] | None = None

    if isinstance(text_edit, str):
        insert_text = text_edit
    elif isinstance(text_edit, dict) and "newText" in text_edit:
        edit = cast(dict[str, Any], text_edit)
        insert_text = str(edit["newText"])
        rng = _range_from(edit.get("range"))
    else:
        raw_insert = item.get("insertText")
        if isinstance(raw_insert, str) and raw_insert:
            insert_text = raw_insert

    if rng is None:
        rng = _range_from(defaults.get("editRange"))
    if rng is not None:
        # Server columns are UTF-16 code units; the buffer counts code
        # points (ASCII lines, the fast path, are identical).
        rng = _range_to_buffer_cols(rng, doc)
    if rng is None:
        # No server range: replace the identifier prefix the UI computed.
        rng = (row, prefix_start_col, row, col)

    # Snippet items (format 2) use tab stops we don't support; fall back
    # to the plain label so accepting never inserts raw "$1" placeholders.
    if text_format == 2 and isinstance(text_edit, dict):
        insert_text = label
    elif text_format == 2 and not isinstance(item.get("insertText"), str):
        insert_text = label

    detail_raw = item.get("detail")
    kind_raw = item.get("kind")
    sort_raw = item.get("sortText")
    return Completion(
        label=label,
        insert_text=insert_text,
        detail=detail_raw if isinstance(detail_raw, str) else "",
        kind=kind_raw if isinstance(kind_raw, int) else 0,
        sort_text=sort_raw if isinstance(sort_raw, str) else "",
        range_start_row=rng[0],
        range_start_col=rng[1],
        range_end_row=rng[2],
        range_end_col=rng[3],
    )


def _parse_diagnostics(
    raw: Any, lines: list[str] | None = None
) -> list[Diagnostic]:
    """Parse a publishDiagnostics payload, skipping malformed entries.

    Numeric coercion is defensive -- a single malformed notification
    must not kill the connection (the caller runs inside the read
    loop), so a non-integer coordinate degrades to 0 instead of
    crashing the session.  Server columns are UTF-16 code units;
    *lines* (the document's current lines) converts them to buffer
    columns.
    """

    def _coord(pos: dict[str, Any], key: str) -> int:
        value = pos.get(key, 0)
        if isinstance(value, int) and not isinstance(value, bool):
            return value
        return 0

    result: list[Diagnostic] = []
    for entry_raw in cast(list[Any], raw):
        if not isinstance(entry_raw, dict):
            continue
        entry = cast(dict[str, Any], entry_raw)
        rng_raw = entry.get("range")
        if not isinstance(rng_raw, dict):
            continue
        rng = cast(dict[str, Any], rng_raw)
        start: dict[str, Any] = {}
        end: dict[str, Any] = {}
        start_raw, end_raw = rng.get("start"), rng.get("end")
        if isinstance(start_raw, dict):
            start = cast(dict[str, Any], start_raw)
        if isinstance(end_raw, dict):
            end = cast(dict[str, Any], end_raw)
        if not start or not end:
            continue
        message = entry.get("message", "")
        source = entry.get("source", "")
        severity = entry.get("severity")
        start_row = max(0, _coord(start, "line"))
        end_row = max(0, _coord(end, "line"))
        line0 = (
            lines[start_row]
            if lines is not None and start_row < len(lines)
            else ""
        )
        line1 = (
            lines[end_row]
            if lines is not None and end_row < len(lines)
            else ""
        )
        result.append(Diagnostic(
            start_row=start_row,
            start_col=max(0, _from_utf16(line0, _coord(start, "character"))),
            end_row=end_row,
            end_col=max(0, _from_utf16(line1, _coord(end, "character"))),
            severity=int(severity) if isinstance(severity, int)
            else DiagnosticSeverity.ERROR,
            message=message if isinstance(message, str) else "",
            source=source if isinstance(source, str) else "",
        ))
    result.sort(key=lambda d: (d.start_row, d.start_col))
    return result
