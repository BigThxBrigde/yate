"""Pure, reversible comment toggling over text rows (L0 leaf).

The engine takes comment markers from :class:`~yate.editor_syntax.langdefs.LangSpec`
through its caller: it never imports the syntax registry, the buffer or any
UI layer.  Given a row span, it either adds one comment layer to every
non-blank row or removes the layer it previously added, so a second toggle
restores the exact original text (indentation and blank rows included).

Detection is deliberately strict: a row counts as commented only when the
marker is followed by one space (line markers) or the block pair wraps the
content with one space on each side.  Mixed ranges therefore gain one layer
on the first toggle and lose exactly that layer on the second, which keeps
the operation an involution for arbitrary input.
"""

from __future__ import annotations

from collections.abc import Sequence

__all__ = ["comment_range"]


def _indent_of(line: str) -> str:
    """Return the leading whitespace of *line*."""
    return line[: len(line) - len(line.lstrip())]


def _line_is_commented(line: str, marker: str) -> bool:
    """Whether *line* carries a strict ``marker + space`` prefix."""
    return line.lstrip().startswith(marker + " ")


def _block_is_commented(line: str, opening: str, closing: str) -> bool:
    """Whether *line* is strictly wrapped by the block marker pair."""
    stripped = line.lstrip()
    prefix = opening + " "
    suffix = " " + closing
    return (
        stripped.startswith(prefix)
        and stripped.endswith(suffix)
        and len(stripped) > len(prefix) + len(suffix)
    )


def comment_range(
    lines: Sequence[str],
    first: int,
    last: int,
    *,
    line_comment: str | None,
    block_comment: tuple[str, str] | None,
) -> list[str]:
    """Toggle comment markers on rows ``first..last`` (inclusive).

    *lines* is not mutated; a new list is always returned.  Blank rows are
    left untouched.  When *line_comment* is set it wins over *block_comment*
    (the usual linewise vim/`Ctrl+/` semantics); block-only languages wrap
    each non-blank row with ``opening + " " + content + " " + closing``.
    A span with no markers, or one containing no non-blank rows, returns the
    original rows unchanged.
    """
    result = list(lines)
    if first > last or first < 0 or last >= len(result):
        return result
    rows = [row for row in range(first, last + 1) if lines[row].strip()]
    if not rows:
        return result
    if line_comment:
        commented = all(_line_is_commented(lines[row], line_comment) for row in rows)
        for row in rows:
            indent = _indent_of(lines[row])
            content = lines[row][len(indent):]
            if commented:
                result[row] = indent + content[len(line_comment) + 1:]
            else:
                result[row] = indent + line_comment + " " + content
        return result
    if block_comment:
        opening, closing = block_comment
        commented = all(
            _block_is_commented(lines[row], opening, closing) for row in rows
        )
        for row in rows:
            indent = _indent_of(lines[row])
            content = lines[row][len(indent):]
            if commented:
                inner = content[len(opening) + 1 : -(len(closing) + 1)]
                result[row] = indent + inner
            else:
                result[row] = indent + opening + " " + content + " " + closing
    return result
