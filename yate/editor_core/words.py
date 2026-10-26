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

#: Greedy run matchers: one whole regex call per word/punctuation segment
#: instead of one per character (scan loops stay out of Python-level loops).
_WORD_RUN: re.Pattern[str] = re.compile(r"\w+")
_PUNCT_RUN: re.Pattern[str] = re.compile(r"[^\w\s]+")
_SPACE_RUN: re.Pattern[str] = re.compile(r"\s+")


def _is_word(ch: str) -> bool:
    """Whether *ch* counts as a word character for word motions."""
    return bool(_WORD_CHARS.match(ch))


def _run_start(line: str, i: int, *, word: bool) -> int:
    """Start column of the run ending at *i*.

    Matches the same run class the forward scanners use: word characters
    when *word* is set, otherwise non-word non-space characters.  Returns
    *i* unchanged when no such run ends there (empty prefix or the run
    class does not apply), mirroring the per-character loops this replaces.
    """
    pattern = _WORD_RUN if word else _PUNCT_RUN
    start = i
    for found in pattern.finditer(line, 0, i):
        if found.end() == i:
            start = found.start()
    return start


def next_word_start(line: str, col: int) -> int:
    """Column of the next word start at or after ``col``."""
    n = len(line)
    i = min(col, n)
    found = _WORD_RUN.match(line, i)
    if found is not None:
        i = found.end()
    else:
        found = _PUNCT_RUN.match(line, i)
        if found is not None:
            i = found.end()
    found = _SPACE_RUN.match(line, i)
    if found is not None:
        i = found.end()
    return i


def prev_word_start(line: str, col: int) -> int:
    """Column of the word start before ``col``."""
    i = min(col, len(line))
    while i > 0 and line[i - 1].isspace():
        i -= 1
    if i > 0 and _is_word(line[i - 1]):
        return _run_start(line, i, word=True)
    return _run_start(line, i, word=False)


def word_end(line: str, col: int) -> int:
    """Exclusive column of the end of the word at/after ``col``."""
    n = len(line)
    i = min(col, n)
    found = _SPACE_RUN.match(line, i)
    if found is not None:
        i = found.end()
    found = _WORD_RUN.match(line, i)
    if found is not None:
        return found.end()
    found = _PUNCT_RUN.match(line, i)
    if found is not None:
        return found.end()
    return i


def word_span(line: str, col: int) -> tuple[int, int]:
    """The (start, end) char span of the word at *col*.

    A non-word character or an out-of-range column yields an empty span
    ``(col, col)`` -- double-clicking whitespace moves the cursor without
    inventing a selection.  Word membership follows :func:`_is_word`.
    """
    if not 0 <= col < len(line) or not _is_word(line[col]):
        return (col, col)
    # the run start is walked back directly; prev_word_start would jump the
    # gap into the previous word when *col* is the word's first character
    return (_run_start(line, col, word=True), word_end(line, col))
