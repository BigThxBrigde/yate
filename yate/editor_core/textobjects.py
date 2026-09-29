"""Stateless text scanning helpers for vim-style motions and text objects.

Every function here is a pure computation over line strings: no cursor, no
selection, no undo bookkeeping.  :class:`~yate.editor_core.buffer.TextBuffer`
stays the stateful document model; the vim keymap resolves a span with these
helpers and then applies it through the buffer's public mutation methods.

Positions are ``(row, col)`` tuples like everywhere else in editor_core, and
object spans are half-open ``[start, end)`` ranges ready for the buffer's
selection primitives.
"""

from __future__ import annotations

from yate.editor_core.buffer import Pos, next_word_start, prev_word_start

#: Delimiter keys accepted after ``i``/``a``, mapped to their (open, close).
_PAIR_ALIASES = {
    "(": ("(", ")"),
    ")": ("(", ")"),
    "b": ("(", ")"),
    "[": ("[", "]"),
    "]": ("[", "]"),
    "{": ("{", "}"),
    "}": ("{", "}"),
    "B": ("{", "}"),
    "<": ("<", ">"),
    ">": ("<", ">"),
}


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


def resolve_text_object(
    lines: list[str],
    pos: Pos,
    scope: str,
    key: str,
    count: int = 1,
) -> tuple[Pos, Pos] | None:
    """Half-open span of the vim text object *key* at *pos*, or ``None``.

    *scope* is ``"i"`` (inner object) or ``"a"`` (a-round object); *count*
    selects the count-th enclosing object for pairs and tags.  Words and
    quotes stay on the cursor row, pairs and tags span lines.  ``None`` means
    the object does not apply here and nothing should change.
    """
    if key == "w":
        return _word_span(lines, pos, scope, max(1, count))
    if key in ("'", '"'):
        return _quote_span(lines, pos, key, scope)
    if key == "t":
        return _tag_span(lines, pos, scope, max(1, count))
    pair = _PAIR_ALIASES.get(key)
    if pair is not None:
        return _pair_span(lines, pos, pair[0], pair[1], max(1, count), scope)
    return None


def _class(ch: str) -> str:
    """vim-like char class of *ch*: ``"word"``, ``"punct"`` or ``"space"``."""
    if ch.isspace():
        return "space"
    if ch.isalnum() or ch == "_":
        return "word"
    return "punct"


def at_word_end(line: str, col: int) -> bool:
    """Whether the char at *col* is the last char of its non-blank run.

    A run ends here when the line ends, a blank follows, or the next char
    switches char class (word / punctuation) -- vim's ``e`` landing test.
    """
    if col >= len(line) or line[col].isspace():
        return False
    return col + 1 == len(line) or _class(line[col + 1]) != _class(line[col])


def word_end_column(line: str, col: int, *, from_start: bool = False) -> int | None:
    """Find the next vim ``e`` landing column after *col*.

    Scans forward for the end of the next word or punctuation run and
    returns ``None`` when the rest of the line offers no landing, so the
    caller can wrap to the following lines.  The scan starts strictly
    after *col*; *from_start* scans the whole line from column 0 instead
    (a wrapped ``e`` may land on the first word).
    """
    start = 0 if from_start else col + 1
    for i in range(start, len(line)):
        if at_word_end(line, i):
            return i
    return None


def first_non_blank(line: str) -> int:
    """Column of the first non-blank char, or ``len(line)`` when all blank."""
    for i, ch in enumerate(line):
        if not ch.isspace():
            return i
    return len(line)


def next_word_pos(lines: list[str], row: int, col: int) -> Pos | None:
    """Position of vim ``w`` from ``(row, col)``: the next word start.

    The row is scanned first; past the row's last word vim's exclusive
    motion stops on the row's last char and only wraps on the next press.
    Wrapping lands on the first non-blank char of content lines and stops
    on empty lines, while blank-only lines are skipped.  ``None`` when
    nothing below offers a landing.
    """
    nc = next_word_start(lines[row], col)
    if col < nc < len(lines[row]):
        return (row, nc)
    if col < len(lines[row]) - 1:
        return (row, len(lines[row]) - 1)
    for r in range(row + 1, len(lines)):
        line = lines[r]
        if not line:
            return (r, 0)  # vim stops on empty lines
        f = first_non_blank(line)
        if f < len(line):
            return (r, f)
    return None


def prev_word_pos(lines: list[str], row: int, col: int) -> Pos | None:
    """Position of vim ``b`` from ``(row, col)``: the previous word start.

    Mirrors :func:`next_word_pos` upward: the row is scanned first, then
    earlier lines land on their last word start, empty lines stop the
    motion and blank-only lines are skipped.  ``None`` when nothing above
    offers a landing.
    """
    pc = prev_word_start(lines[row], col)
    # prev_word_start returns 0 when nothing precedes *col*; column 0 only
    # counts as a landing when it actually starts a word
    if 0 < pc < col or (pc == 0 and not lines[row][:1].isspace() and col > 0):
        return (row, pc)
    for r in range(row - 1, -1, -1):
        line = lines[r]
        if not line:
            return (r, 0)  # vim stops on empty lines
        i = len(line)
        while i > 0 and line[i - 1].isspace():
            i -= 1
        if i > 0:
            return (r, prev_word_start(line, i))
    return None


def _word_span(
    lines: list[str], pos: Pos, scope: str, count: int
) -> tuple[Pos, Pos] | None:
    """The word (or punct/space run) at *pos*, extended by *count*."""
    r, c = pos
    if not (0 <= r < len(lines)):
        return None
    line = lines[r]
    c = min(c, len(line))
    kind = _class(line[c]) if c < len(line) else "space"
    start = c
    while start > 0 and _class(line[start - 1]) == kind:
        start -= 1
    end = c
    while end < len(line) and _class(line[end]) == kind:
        end += 1
    for _ in range(count - 1):
        # swallow the separator run, then the next word/punct run
        while end < len(line) and line[end].isspace():
            end += 1
        if end >= len(line):
            break
        nxt = _class(line[end])
        while end < len(line) and _class(line[end]) == nxt:
            end += 1
    if scope == "a":
        if kind == "space":
            # aw on whitespace takes the following word too
            while end < len(line) and not line[end].isspace():
                end += 1
        elif end < len(line) and line[end].isspace():
            while end < len(line) and line[end].isspace():
                end += 1
        else:
            while start > 0 and line[start - 1].isspace():
                start -= 1
    return (r, start), (r, end)


def _quote_positions(line: str, quote: str) -> list[int]:
    """Columns of *quote* characters in *line* that are not backslash-escaped."""
    cols: list[int] = []
    i = 0
    while i < len(line):
        if line[i] == "\\":
            i += 2  # skip the escaped character wholesale
            continue
        if line[i] == quote:
            cols.append(i)
        i += 1
    return cols


def _quote_span(
    lines: list[str], pos: Pos, quote: str, scope: str
) -> tuple[Pos, Pos] | None:
    """The single-row *quote* pair enclosing *pos*, honoring ``\\`` escapes."""
    r, c = pos
    if not (0 <= r < len(lines)):
        return None
    line = lines[r]
    c = min(c, len(line))
    quotes = _quote_positions(line, quote)
    if c in quotes:
        # cursor on a real quote: prefer treating it as the opener
        idx = quotes.index(c)
        if idx + 1 < len(quotes):
            opener, closer = c, quotes[idx + 1]
        elif idx > 0:
            opener, closer = quotes[idx - 1], c
        else:
            return None
    else:
        before = [q for q in quotes if q < c]
        after = [q for q in quotes if q > c]
        if not before or not after:
            return None
        opener, closer = before[-1], after[0]
    if scope == "a":
        return (r, opener), (r, closer + 1)
    return (r, opener + 1), (r, closer)


def _pair_span(
    lines: list[str],
    pos: Pos,
    open_ch: str,
    close_ch: str,
    level: int,
    scope: str,
) -> tuple[Pos, Pos] | None:
    """The *level*-th (innermost first) *open_ch*/*close_ch* block around *pos*."""
    r, c = pos
    if not (0 <= r < len(lines)):
        return None
    line = lines[r]
    cur = line[c] if c < len(line) else ""
    if cur == open_ch:
        opener = (r, c)
    else:
        opener = _unmatched_backward(
            lines,
            r,
            c - 1 if cur == close_ch else min(c, len(line) - 1),
            open_ch,
            close_ch,
            level,
        )
    if opener is None:
        return None
    closer = _matching_forward(lines, opener, open_ch, close_ch)
    if closer is None:
        return None
    if scope == "a":
        return opener, (closer[0], closer[1] + 1)
    return (opener[0], opener[1] + 1), closer


def _unmatched_backward(
    lines: list[str], row: int, col: int, open_ch: str, close_ch: str, level: int
) -> Pos | None:
    """The *level*-th unmatched *open_ch* at or before ``(row, col)``."""
    depth = 0
    found = 0
    r, i = row, col
    while r >= 0:
        line = lines[r]
        while i >= 0:
            ch = line[i]
            if ch == close_ch:
                depth += 1
            elif ch == open_ch:
                if depth > 0:
                    depth -= 1
                else:
                    found += 1
                    if found == level:
                        return (r, i)
            i -= 1
        r -= 1
        i = len(lines[r]) - 1 if r >= 0 else -1
    return None


def _matching_forward(
    lines: list[str], opener: Pos, open_ch: str, close_ch: str
) -> Pos | None:
    """The first unmatched *close_ch* after the opener at *opener*."""
    r, c = opener
    depth = 0
    first = True
    while 0 <= r < len(lines):
        line = lines[r]
        i = c + 1 if first else 0
        first = False
        while i < len(line):
            ch = line[i]
            if ch == open_ch:
                depth += 1
            elif ch == close_ch:
                if depth == 0:
                    return (r, i)
                depth -= 1
            i += 1
        r += 1
    return None


def _name_char(ch: str) -> bool:
    """Whether *ch* can be part of a tag name."""
    return ch.isalnum() or ch in "_-:"


def _matching_tag_close(
    lines: list[str], name: str, row: int, col: int
) -> tuple[Pos, Pos] | None:
    """The matching ``</name>`` from ``(row, col)``: its '<' and '>' positions."""
    open_pat = "<" + name
    close_pat = "</" + name
    depth = 0
    r, i = row, col
    while r < len(lines):
        line = lines[r]
        n = len(line)
        while i < n:
            if line.startswith(close_pat, i):
                j = i + len(close_pat)
                if j >= n or not _name_char(line[j]):
                    if depth == 0:
                        gt = line.find(">", i)
                        if gt == -1:
                            return None
                        return (r, i), (r, gt)
                    depth -= 1
                    i = j
                    continue
            if line.startswith(open_pat, i):
                j = i + len(open_pat)
                if j >= n or not _name_char(line[j]):
                    depth += 1
                    i = j
                    continue
            i += 1
        r += 1
        i = 0
    return None


def _tag_span(
    lines: list[str], pos: Pos, scope: str, count: int
) -> tuple[Pos, Pos] | None:
    """The *count*-th tag block around *pos* (innermost first)."""
    found = _enclosing_tag(lines, pos, count)
    if found is None:
        return None
    opener_lt, opener_gt, closer_lt, closer_gt = found
    if scope == "a":
        return opener_lt, (closer_gt[0], closer_gt[1] + 1)
    return (opener_gt[0], opener_gt[1] + 1), closer_lt


def _tag_closer(lines: list[str], row: int, lt: int, gt: int) -> tuple[Pos, Pos] | None:
    """The closer of the opening tag at ``lines[row][lt..gt]``, or ``None``.

    Closing (``</x>``) and self-closing (``<x/>``) tags never qualify as
    openers; the returned pair is the closer's '<' and '>' positions.
    """
    line = lines[row]
    inner = line[lt + 1 : gt].strip()
    if not inner or inner.startswith("/") or inner.endswith("/"):
        return None
    name = inner.split()[0]
    return _matching_tag_close(lines, name, row, gt + 1)


def _enclosing_tag(
    lines: list[str], pos: Pos, level: int
) -> tuple[Pos, Pos, Pos, Pos] | None:
    """The *level*-th tag block containing *pos* (innermost first).

    Returns the opener's '<' and '>', then the closer's '<' and '>'.  A tag
    must start and end on one row, and a candidate only encloses when its
    closer sits after the cursor.  The cursor column is scanned too, so the
    cursor may sit on the opener's '<' or '>' and still resolve.
    """
    r, c = pos
    line = lines[r] if 0 <= r < len(lines) else ""
    if c < len(line) and line[c] == "<":
        # cursor on an opener's '<': its '>' lies ahead of the cursor and the
        # backward scan below would never see it
        g = line.find(">", c)
        if g != -1:
            closer = _tag_closer(lines, r, c, g)
            if closer is not None and closer[0] > pos:
                if level == 1:
                    return (r, c), (r, g), closer[0], closer[1]
                level -= 1
    first = True
    while r >= 0:
        line = lines[r]
        i = min(c, len(line) - 1) if first else len(line) - 1
        first = False
        while i >= 0:
            if line[i] == ">":
                lt = line.rfind("<", 0, i)
                if lt != -1:
                    closer = _tag_closer(lines, r, lt, i)
                    if closer is not None and closer[0] > pos:
                        if level == 1:
                            return (r, lt), (r, i), closer[0], closer[1]
                        level -= 1
                    i = lt
                    continue
            i -= 1
        r -= 1
    return None
