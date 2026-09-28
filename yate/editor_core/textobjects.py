"""Stateless text scanning helpers for vim-style motions and text objects.

Every function here is a pure computation over line strings: no cursor, no
selection, no undo bookkeeping.  :class:`~yate.editor_core.buffer.TextBuffer`
stays the stateful document model; the vim keymap resolves a span with these
helpers and then applies it through the buffer's public mutation methods.

Positions are ``(row, col)`` tuples like everywhere else in editor_core.
"""

from __future__ import annotations


def find_char(
    line: str,
    col: int,
    ch: str,
    *,
    count: int = 1,
    backward: bool = False,
    till: bool = False,
) -> int | None:
    """Column of the *count*-th *ch* seen from *col*, or ``None``.

    Forward searches start strictly after *col* and backward searches strictly
    before it, matching vim's ``f``/``F``: the character under the cursor never
    matches.  *till* (vim ``t``/``T``) lands one column short of the match and
    fails when that would not move the cursor.  A *count* beyond the matches
    available fails, and a failed search never moves anything.
    """
    n = len(line)
    count = max(1, count)
    if not backward:
        seen = 0
        for i in range(col + 1, n):
            if line[i] == ch:
                seen += 1
                if seen == count:
                    if not till:
                        return i
                    if i - 1 > col:
                        return i - 1
                    return None
        return None
    seen = 0
    for i in range(col - 1, -1, -1):
        if line[i] == ch:
            seen += 1
            if seen == count:
                if not till:
                    return i
                if i + 1 < col:
                    return i + 1
                return None
    return None
