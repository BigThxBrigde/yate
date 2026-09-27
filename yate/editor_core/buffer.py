"""The text buffer: lines, cursor, selection, mutations and undo/redo.

The buffer is deliberately free of any terminal/UI code.  Positions are
``(row, col)`` tuples where *col* is a character index on the row (the view
layer is responsible for turning tabs and wide characters into cells).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from yate.logs import tracing

Pos = tuple[int, int]

log = tracing.get_logger(__name__)


class BufferReadOnlyError(Exception):
    """Raised when a mutation is attempted on a read-only :class:`TextBuffer`.

    The read-only flag lives on the buffer (``read_only``) so every write
    path -- typing, vim operators, actions, completion acceptance, search
    replace, extensions -- funnels through the same guarded public mutation
    methods and fails with this single exception type.
    """


_WORD_CHARS = re.compile(r"\w")

#: Maximum undo steps kept in memory.  Each step snapshots the full line
#: list, so an unbounded stack would grow without limit on large documents;
#: oldest steps are dropped once the cap is reached (like most editors).
MAX_UNDO_STEPS = 1000


def _is_word(ch: str) -> bool:
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


@dataclass
class _Snapshot:
    lines: tuple[str, ...]
    cursor: Pos
    anchor: Pos | None


@dataclass
class _Edit:
    before: _Snapshot
    after: _Snapshot
    kind: str  # "char" coalesces with adjacent typing/deletion, "step" does not
    #: Number of line-change commits folded into this step (1 for a plain
    #: step, more for coalesced typing).  :attr:`content_edits` is adjusted
    #: by this amount on undo/redo so the counter stays aligned with the
    #: actual number of reverted changes even across coalescing.
    weight: int = 1


class TextBuffer:
    """A mutable, undoable multi-line text buffer."""

    def __init__(
        self,
        text: str = "",
        *,
        tab_width: int = 4,
        use_spaces: bool = True,
        read_only: bool = False,
    ) -> None:
        self.lines: list[str] = text.split("\n") if text else [""]
        self.cursor: Pos = (0, 0)
        self.anchor: Pos | None = None
        self.tab_width = tab_width
        self.use_spaces = use_spaces
        # When True every public mutation raises ``BufferReadOnlyError``;
        # cursor/selection movement stays allowed (browsing a read-only
        # buffer must keep working).
        self.read_only = read_only
        self.register: str = ""  # internal yank/clipboard register
        self._undo: list[_Edit] = []
        self._redo: list[_Edit] = []
        # Bumped whenever the textual content (not just the cursor or
        # selection) changes; the view uses it to invalidate highlight
        # tokens without re-tokenizing on every cursor-movement key.
        self.content_version: int = 0
        # Number of content-changing commits since buffer creation (undo
        # decrements, redo increments).  ``Document.modified`` compares this
        # against the value recorded at the last save: O(1) dirty tracking
        # that stays exact across undo/redo, unlike a full-text diff.
        self.content_edits: int = 0
        # Desired column for vertical movement (vim/VS Code semantics):
        # consecutive up/down motions remember the column the cursor started
        # from, so crossing a shorter line does not permanently pull the
        # cursor to that line's end.  Cleared by any horizontal move, edit
        # or explicit cursor positioning (see :meth:`set_cursor`).
        self._goal_col: int | None = None

    # ------------------------------------------------------------------ state

    def _ensure_writable(self) -> None:
        """Raise :class:`BufferReadOnlyError` unless the buffer is writable."""
        if self.read_only:
            raise BufferReadOnlyError("buffer is read-only")

    @property
    def row(self) -> int:
        return self.cursor[0]

    @property
    def col(self) -> int:
        return self.cursor[1]

    @property
    def line_count(self) -> int:
        return len(self.lines)

    def line(self, row: int) -> str:
        return self.lines[max(0, min(row, len(self.lines) - 1))]

    def get_text(self) -> str:
        return "\n".join(self.lines)

    def set_text(self, text: str) -> None:
        self._ensure_writable()
        self.lines = text.split("\n") if text else [""]
        self.cursor = (0, 0)
        self.anchor = None
        self._undo.clear()
        self._redo.clear()
        self._goal_col = None
        self.content_version += 1
        self.content_edits += 1

    def mark_content_changed(self) -> None:
        """Bump :attr:`content_version` after an out-of-band mutation.

        Extensions that replace ``buffer.lines`` entries directly (instead
        of going through an undoable edit) call this so syntax highlight
        caches are re-synchronized on the next repaint.  Also counts one
        content edit: out-of-band mutations cannot be undone, so the only
        way back to a clean state is saving again.  The vertical goal
        column is cleared because the lines may have changed shape.
        """
        log.debug("out-of-band buffer change: lines=%d", len(self.lines))
        self._goal_col = None
        self.content_version += 1
        self.content_edits += 1

    # ------------------------------------------------------------- snapshots

    def _snapshot(self) -> _Snapshot:
        return _Snapshot(tuple(self.lines), self.cursor, self.anchor)

    def _restore(self, snap: _Snapshot) -> None:
        changed = tuple(self.lines) != snap.lines
        self.lines = list(snap.lines)
        self.cursor = snap.cursor
        self.anchor = snap.anchor
        self._goal_col = None
        if changed:
            self.content_version += 1

    def _commit(self, before: _Snapshot, kind: str = "step") -> None:
        after = self._snapshot()
        if after == before:
            return
        # content changed: the remembered vertical column may be past the
        # end of the mutated line, so vertical tracking restarts
        self._goal_col = None
        lines_changed = after.lines != before.lines
        weight = 1 if lines_changed else 0
        if kind == "char" and self._undo:
            top = self._undo[-1]
            if top.kind == "char" and top.after == before:
                top.after = after
                top.weight += weight
                self._redo.clear()
                if lines_changed:
                    self.content_version += 1
                    self.content_edits += 1
                return
        self._undo.append(_Edit(before, after, kind, weight))
        if len(self._undo) > MAX_UNDO_STEPS:
            del self._undo[0]
        self._redo.clear()
        if lines_changed:
            self.content_version += 1
            self.content_edits += 1

    # ------------------------------------------------- bulk-edit transactions
    #
    # Cooperating editor_core engines (SearchEngine.replace_all) perform many
    # line edits as one logical operation; they bracket the edits with a
    # public snapshot/commit pair instead of touching undo internals.

    def snapshot(self) -> _Snapshot:
        """Capture undo state before a bulk edit (pair with :meth:`commit`)."""
        return self._snapshot()

    def commit(self, before: _Snapshot, kind: str = "step") -> None:
        """Record history for a bulk edit started with :meth:`snapshot`."""
        self._commit(before, kind)

    def undo(self) -> bool:
        self._ensure_writable()
        if not self._undo:
            return False
        edit = self._undo.pop()
        self.content_edits -= edit.weight
        self._restore(edit.before)
        self._redo.append(edit)
        return True

    def redo(self) -> bool:
        self._ensure_writable()
        if not self._redo:
            return False
        edit = self._redo.pop()
        self.content_edits += edit.weight
        self._restore(edit.after)
        self._undo.append(edit)
        return True

    # -------------------------------------------------------------- selection

    def has_selection(self) -> bool:
        return self.anchor is not None and self.anchor != self.cursor

    def selection(self) -> tuple[Pos, Pos] | None:
        if not self.has_selection():
            return None
        assert self.anchor is not None
        return (min(self.anchor, self.cursor), max(self.anchor, self.cursor))

    def selected_text(self) -> str | None:
        sel = self.selection()
        if sel is None:
            return None
        (r1, c1), (r2, c2) = sel
        if r1 == r2:
            return self.lines[r1][c1:c2]
        parts = [self.lines[r1][c1:]]
        parts.extend(self.lines[r1 + 1 : r2])
        parts.append(self.lines[r2][:c2])
        return "\n".join(parts)

    def selected_rows(self) -> tuple[int, int] | None:
        sel = self.selection()
        if sel is None:
            return None
        return sel[0][0], sel[1][0]

    def clear_selection(self) -> None:
        self.anchor = None

    def set_cursor(self, pos: Pos, select: bool = False) -> None:
        """Move the cursor to *pos*, clamped to the text, handling selection.

        Public so stateful keymaps (vim motions) can position the cursor
        without re-implementing the clamp/anchor semantics.  Explicit
        positioning ends vertical goal-column tracking.
        """
        r, c = pos
        r = max(0, min(r, len(self.lines) - 1))
        c = max(0, min(c, len(self.lines[r])))
        if select and self.anchor is None:
            self.anchor = self.cursor
        elif not select:
            self.anchor = None
        self.cursor = (r, c)
        self._goal_col = None

    def select_all(self) -> None:
        self.anchor = (0, 0)
        self.cursor = (len(self.lines) - 1, len(self.lines[-1]))
        self._goal_col = None

    # ------------------------------------------------------------ mutations

    def _delete_range(self, start: Pos, end: Pos) -> None:
        """Delete the half-open range [start, end)."""
        (r1, c1), (r2, c2) = start, end
        if r1 == r2:
            self.lines[r1] = self.lines[r1][:c1] + self.lines[r1][c2:]
        else:
            self.lines[r1] = self.lines[r1][:c1] + self.lines[r2][c2:]
            del self.lines[r1 + 1 : r2 + 1]
        self.cursor = (r1, c1)

    def insert_text(self, text: str, kind: str = "char") -> None:
        """Insert ``text`` (may contain newlines) at the cursor."""
        self._ensure_writable()
        if text == "":
            return
        before = self._snapshot()
        if self.has_selection():
            sel = self.selection()
            assert sel is not None
            self._delete_range(*sel)
        self._apply_text(text)
        self.anchor = None
        self._commit(before, kind)

    def _apply_text(self, text: str) -> None:
        """Insert ``text`` at the cursor without snapshot bookkeeping."""
        r, c = self.cursor
        parts = text.split("\n")
        line = self.lines[r]
        if len(parts) == 1:
            self.lines[r] = line[:c] + parts[0] + line[c:]
            self.cursor = (r, c + len(parts[0]))
        else:
            self.lines[r] = line[:c] + parts[0]
            tail = line[c:]
            new_lines = list(parts[1:-1])
            new_lines.append(parts[-1] + tail)
            self.lines[r + 1 : r + 1] = new_lines
            self.cursor = (r + len(parts) - 1, len(parts[-1]))

    def replace_range(self, start: Pos, end: Pos, text: str) -> None:
        """Replace the half-open range [start, end) with ``text``.

        One undo step; used for LSP completion acceptance (text may contain
        newlines).
        """
        self._ensure_writable()
        before = self._snapshot()
        self.cursor = start
        self.anchor = None
        self._delete_range(start, end)
        self._apply_text(text)
        self.anchor = None
        self._commit(before, "step")

    def insert_newline(self) -> None:
        """Insert a newline, continuing the indentation of the current line."""
        r, _ = self.cursor
        matched = re.match(r"[ \t]*", self.lines[r])
        indent = matched.group(0) if matched is not None else ""
        self.insert_text("\n" + indent, kind="char")

    def insert_tab(self) -> None:
        if self.has_selection():
            rows = self.selected_rows()
            if rows is not None and rows[0] != rows[1]:
                self.indent_selection()
                return
        _, c = self.cursor
        if self.use_spaces:
            width = self.tab_width - (c % self.tab_width)
            self.insert_text(" " * width, kind="char")
        else:
            self.insert_text("\t", kind="char")

    def delete_selection(self) -> str | None:
        self._ensure_writable()
        sel = self.selection()
        if sel is None:
            return None
        before = self._snapshot()
        text = self.selected_text()
        self._delete_range(*sel)
        self.anchor = None
        self._commit(before, "step")
        return text

    def delete_backward(self, word: bool = False) -> None:
        self._ensure_writable()
        if self.has_selection():
            self.delete_selection()
            return
        before = self._snapshot()
        r, c = self.cursor
        if r == 0 and c == 0:
            return
        if c == 0:
            prev_len = len(self.lines[r - 1])
            self.lines[r - 1] = self.lines[r - 1] + self.lines[r]
            del self.lines[r]
            self.cursor = (r - 1, prev_len)
        else:
            nc = prev_word_start(self.lines[r], c) if word else c - 1
            self.lines[r] = self.lines[r][:nc] + self.lines[r][c:]
            self.cursor = (r, nc)
        self._commit(before, "step" if word else "char")

    def delete_forward(self, word: bool = False) -> None:
        self._ensure_writable()
        if self.has_selection():
            self.delete_selection()
            return
        before = self._snapshot()
        r, c = self.cursor
        line = self.lines[r]
        if c >= len(line) and r == len(self.lines) - 1:
            return
        if c >= len(line):
            self.lines[r] = line + self.lines[r + 1]
            del self.lines[r + 1]
        else:
            nc = word_end(line, c) if word else c + 1
            self.lines[r] = line[:c] + line[nc:]
        self.cursor = (r, c)
        self._commit(before, "step" if word else "char")

    # ------------------------------------------------------------- movements

    def move_left(self, select: bool = False, word: bool = False) -> None:
        r, c = self.cursor
        if word and c > 0:
            c = prev_word_start(self.lines[r], c)
        else:
            c -= 1
        if c < 0:
            if r > 0:
                r -= 1
                c = len(self.lines[r])
            else:
                c = 0
        self.set_cursor((r, c), select)

    def move_right(self, select: bool = False, word: bool = False) -> None:
        r, c = self.cursor
        line = self.lines[r]
        if word:
            nc = next_word_start(line, c)
            if nc == c and r < len(self.lines) - 1:
                r += 1
                nc = 0
            c = nc
        else:
            c += 1
            if c > len(line):
                if r < len(self.lines) - 1:
                    r += 1
                    c = 0
                else:
                    c = len(line)
        self.set_cursor((r, c), select)

    def move_up(self, select: bool = False) -> None:
        r, c = self.cursor
        goal = self._goal_col if self._goal_col is not None else c
        if r > 0:
            r -= 1
        self.set_cursor((r, goal), select)
        # set_cursor cleared the goal; restore it so consecutive vertical
        # motions keep aiming at the column the run started from
        self._goal_col = goal

    def move_down(self, select: bool = False) -> None:
        r, c = self.cursor
        goal = self._goal_col if self._goal_col is not None else c
        if r < len(self.lines) - 1:
            r += 1
        self.set_cursor((r, goal), select)
        self._goal_col = goal

    def move_line_start(self, select: bool = False, toggle: bool = True) -> None:
        r, c = self.cursor
        line = self.lines[r]
        first_non_ws = len(line) - len(line.lstrip(" \t"))
        if toggle and c == first_non_ws and first_non_ws != 0:
            target = 0
        else:
            target = first_non_ws
        self.set_cursor((r, target), select)

    def move_line_end(self, select: bool = False) -> None:
        r, _ = self.cursor
        self.set_cursor((r, len(self.lines[r])), select)

    def move_doc_start(self, select: bool = False) -> None:
        self.set_cursor((0, 0), select)

    def move_doc_end(self, select: bool = False) -> None:
        r = len(self.lines) - 1
        self.set_cursor((r, len(self.lines[r])), select)

    # --------------------------------------------------------- line commands

    def indent_selection(self) -> None:
        self._ensure_writable()
        sel = self.selection()
        if sel is None:
            self.insert_tab()
            return
        before = self._snapshot()
        (r1, _), (r2, _) = sel
        unit = "\t" if not self.use_spaces else " " * self.tab_width
        for r in range(r1, r2 + 1):
            self.lines[r] = unit + self.lines[r]
        self.anchor = (r1, 0)
        self.cursor = (r2, len(self.lines[r2]))
        self._commit(before, "step")

    def outdent_selection(self) -> None:
        self._ensure_writable()
        sel = self.selection()
        if sel is None:
            r = self.cursor[0]
            r1 = r2 = r
        else:
            (r1, _), (r2, _) = sel
        before = self._snapshot()
        for r in range(r1, r2 + 1):
            line = self.lines[r]
            if line.startswith("\t"):
                self.lines[r] = line[1:]
            elif line.startswith(" "):
                # Space indents outdent to the previous tab stop, not a full
                # width: 3 spaces with tab_width=4 all go, 8 spaces lose 4.
                stripped = line.lstrip(" ")
                removed = len(line) - len(stripped)
                rrem = removed % self.tab_width
                self.lines[r] = " " * (removed - (rrem or self.tab_width)) + stripped
        if sel is not None:
            self.anchor = (r1, 0)
            self.cursor = (r2, len(self.lines[r2]))
        else:
            # Outdenting shortens the line; the cursor must stay inside it
            # (shift+tab on a 4-space indented line at col 4 would otherwise
            # leave the cursor one column past the end of the text).
            row = self.cursor[0]
            self.cursor = (row, min(self.col, len(self.lines[row])))
        self._commit(before, "step")

    def yank_lines(self) -> str:
        """Yank the selected lines, or the current line (line-wise)."""
        rows = self.selected_rows()
        if rows is None:
            r1 = r2 = self.cursor[0]
        else:
            r1, r2 = rows
        text = "\n".join(self.lines[r1 : r2 + 1]) + "\n"
        self.register = text
        return text

    def yank_selection(self) -> str:
        """Yank the selection, or the current line if there is none."""
        if self.has_selection():
            text = self.selected_text() or ""
        else:
            text = self.lines[self.cursor[0]]
        self.register = text
        return text

    def delete_lines(self) -> str:
        """Delete selected lines (or the current line) and yank them."""
        self._ensure_writable()
        before = self._snapshot()
        rows = self.selected_rows()
        if rows is None:
            r1 = r2 = self.cursor[0]
        else:
            r1, r2 = rows
        text = "\n".join(self.lines[r1 : r2 + 1]) + "\n"
        self.register = text
        del self.lines[r1 : r2 + 1]
        if not self.lines:
            self.lines = [""]
        r = min(r1, len(self.lines) - 1)
        self.cursor = (r, 0)
        self.anchor = None
        self._commit(before, "step")
        return text

    def duplicate_line(self) -> None:
        self._ensure_writable()
        before = self._snapshot()
        rows = self.selected_rows()
        r1, r2 = rows if rows is not None else (self.row, self.row)
        block = list(self.lines[r1 : r2 + 1])
        self.lines[r2 + 1 : r2 + 1] = block
        self.cursor = (r2 + len(block), min(self.col, len(self.lines[r2 + len(block)])))
        self.anchor = None
        self._commit(before, "step")

    def move_line(self, delta: int) -> None:
        self._ensure_writable()
        before = self._snapshot()
        r = self.cursor[0]
        target = r + delta
        if target < 0 or target >= len(self.lines):
            return
        line = self.lines.pop(r)
        self.lines.insert(target, line)
        self.cursor = (target, min(self.col, len(line)))
        self.anchor = None
        self._commit(before, "step")

    def join_lines(self) -> None:
        """Join the current line with the next one (vim ``J``)."""
        self._ensure_writable()
        before = self._snapshot()
        r, c = self.cursor
        if r >= len(self.lines) - 1:
            return
        cur = self.lines[r]
        nxt = self.lines[r + 1]
        if cur and not cur.endswith((" ", "\t")) and nxt and not nxt.startswith((" ", "\t")):
            joined = cur + " " + nxt.lstrip(" \t") if nxt else cur + nxt
        else:
            joined = cur + nxt
        self.lines[r] = joined
        del self.lines[r + 1]
        self.cursor = (r, min(c, len(joined)))
        self.anchor = None
        self._commit(before, "step")

    def delete_to_line_start(self) -> None:
        """Delete from the start of the line up to the cursor (vim ctrl-u)."""
        self._ensure_writable()
        r, c = self.cursor
        if c == 0:
            return
        before = self._snapshot()
        self.anchor = (r, 0)
        self.cursor = (r, c)
        self._delete_range((r, 0), (r, c))
        self.anchor = None
        self._commit(before, "step")

    def paste(self, below: bool = True) -> None:
        self._ensure_writable()
        text = self.register
        if not text:
            return
        if text.endswith("\n"):
            # line-wise paste
            r = self.cursor[0]
            target = r + 1 if below else r
            self.set_cursor((target, 0))
            self.insert_text(text[:-1] + "\n", kind="step")
            self.move_line_end()
            self.move_left()
        else:
            self.insert_text(text, kind="step")
