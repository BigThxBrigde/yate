"""Word-motion primitives over single line strings (vim ``w``/``b``/``e``).

Stateless pure functions: they take a line and a column and return the
column to move to.  :class:`~yate.editor_core.buffer.TextBuffer` calls them
for its word-wise edit and movement methods, and the vim keymap, text
objects and mouse selection build on them too.  Word membership follows
:func:`_is_word` -- the ``re`` word class ``\\w`` plus underscore.
"""

from __future__ import annotations

import re

#: Word character class for all word motions: ``re``'s ``\\w``.
_WORD_CHARS: re.Pattern[str] = re.compile(r"\w")


def _is_word(ch: str) -> bool:
    """Whether *ch* counts as a word character for word motions."""
    return bool(_WORD_CHARS.match(ch))


def next_word_start(line: str, col: int) -> int:
    """Column of the next word start at or after ``col``."""
    n = len(line)
    i = min(col, n)
    if i < n and _is_word(line[i]):
        while i < n and _is_word(line[i]):
            i += 1
    else:
        while i < n and not _is_word(line[i]) and not line[i].isspace():
            i += 1
    while i < n and line[i].isspace():
        i += 1
    return i


def prev_word_start(line: str, col: int) -> int:
    """Column of the word start before ``col``."""
    i = min(col, len(line))
    while i > 0 and line[i - 1].isspace():
        i -= 1
    if i > 0 and not _is_word(line[i - 1]):
        while i > 0 and not _is_word(line[i - 1]) and not line[i - 1].isspace():
            i -= 1
    else:
        while i > 0 and _is_word(line[i - 1]):
            i -= 1
    return i


def word_end(line: str, col: int) -> int:
    """Exclusive column of the end of the word at/after ``col``."""
    n = len(line)
    i = min(col, n)
    if i < n and line[i].isspace():
        while i < n and line[i].isspace():
            i += 1
    if i < n and _is_word(line[i]):
        while i < n and _is_word(line[i]):
            i += 1
    else:
        while i < n and not _is_word(line[i]) and not line[i].isspace():
            i += 1
    return i


def word_span(line: str, col: int) -> tuple[int, int]:
    """The (start, end) char span of the word at *col*.

    A non-word character or an out-of-range column yields an empty span
    ``(col, col)`` -- double-clicking whitespace moves the cursor without
    inventing a selection.  Word membership follows :func:`_is_word`.
    """
    if not 0 <= col < len(line) or not _is_word(line[col]):
        return (col, col)
    # walk back over the word itself; prev_word_start would jump the gap
    # into the previous word when *col* is the word's first character
    start = col
    while start > 0 and _is_word(line[start - 1]):
        start -= 1
    return (start, word_end(line, col))
