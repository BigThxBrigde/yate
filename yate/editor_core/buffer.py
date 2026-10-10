"""The text buffer: lines, cursor, selection, mutations and undo/redo.

The buffer is deliberately free of any terminal/UI code.  Positions are
``(row, col)`` tuples where *col* is a character index on the row (the view
layer is responsible for turning tabs and wide characters into cells).
"""

from __future__ import annotations

from dataclasses import dataclass

from yate.editor_core.indentation import (
    CLOSERS,
    indent_unit,
    is_pair_of,
    opens_block,
    pair_for,
    rules_for,
)
from yate.editor_core.words import next_word_start, prev_word_start, word_end
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


#: Maximum undo steps kept in memory.  Each step snapshots the full line
#: list, so an unbounded stack would grow without limit on large documents;
#: oldest steps are dropped once the cap is reached (like most editors).
MAX_UNDO_STEPS: int = 1000


@dataclass
class _Snapshot:
    lines: tuple[str, ...]
    cursor: Pos
    anchor: Pos | None
    #: Multi-cursor points captured with the lines (empty = single cursor).
    extra_cursors: tuple[Pos, ...] = ()


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


def _remap_after_insert(new_pos: dict[Pos, Pos], pos: Pos, parts: list[str]) -> None:
    """Retarget positions already recorded for earlier points through one insert.

    Multi-point primitives edit in descending order, so every recorded
    position sits at or after the edit point.  Inserting
    ``"\\n".join(parts)`` at *pos* (``k = len(parts) - 1`` new rows) shifts
    rows below *pos* down by *k*.  With row-splitting text every recorded
    position is strictly below the edited row (a split never records on
    the row it splits), so the same-row column shift only applies to
    single-line inserts.  Remaps entries recorded by *earlier* loop
    iterations; the caller writes *pos*'s own entry right after.
    """
    r = pos[0]
    k = len(parts) - 1
    for p, (pr, pc) in new_pos.items():
        if pr > r:
            new_pos[p] = (pr + k, pc)
        else:
            new_pos[p] = (pr, pc + len(parts[0]))


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
        #: Additional multi-cursor points (issue IKKJHH).  Empty list = the
        #: regular single-cursor behaviour everywhere.  Points are bare
        #: ``(row, col)`` cursors without anchors -- multi-cursor selections
        #: are a non-goal -- and the primary cursor stays :attr:`cursor`, so
        #: every existing consumer keeps working unchanged.
        self.extra_cursors: list[Pos] = []
        self.tab_width = tab_width
        self.use_spaces = use_spaces
        # When True every public mutation raises ``BufferReadOnlyError``;
        # cursor/selection movement stays allowed (browsing a read-only
        # buffer must keep working).
        self.read_only = read_only
        self.register: str = ""  # internal yank/clipboard register
        #: Explicit ``"a``-``"z`` registers (vim named registers).  Purely
        #: internal storage -- they never mirror the system clipboard.
        self.named_registers: dict[str, str] = {}
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
        """Return the cursor's row index (0-based)."""
        return self.cursor[0]

    @property
    def col(self) -> int:
        """Return the cursor's column index (character offset on the row)."""
        return self.cursor[1]

    @property
    def line_count(self) -> int:
        """Return the number of lines in the buffer."""
        return len(self.lines)

    def line(self, row: int) -> str:
        """Return the text of *row*, clamped to the valid row range."""
        return self.lines[max(0, min(row, len(self.lines) - 1))]

    def get_text(self) -> str:
        """Return the buffer content as a single string joined by newlines."""
        return "\n".join(self.lines)

    def set_text(self, text: str) -> None:
        """Replace the whole content, resetting cursor, selection and history."""
        self._ensure_writable()
        self.lines = text.split("\n") if text else [""]
        self.cursor = (0, 0)
        self.anchor = None
        self.extra_cursors = []
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
        return _Snapshot(
            tuple(self.lines), self.cursor, self.anchor, tuple(self.extra_cursors)
        )

    def _restore(self, snap: _Snapshot) -> None:
        changed = tuple(self.lines) != snap.lines
        self.lines = list(snap.lines)
        self.cursor = snap.cursor
        self.anchor = snap.anchor
        # Out-of-range points are clamped, not dropped: undo may have
        # rewound the document below a point's row, and keeping the point
        # at the nearest legal position matches the VS Code behaviour.
        self.extra_cursors = []
        for pos in snap.extra_cursors:
            r = max(0, min(pos[0], len(self.lines) - 1))
            self.extra_cursors.append((r, max(0, min(pos[1], len(self.lines[r])))))
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
        """Undo the most recent edit; return ``False`` when history is empty."""
        self._ensure_writable()
        if not self._undo:
            return False
        edit = self._undo.pop()
        self.content_edits -= edit.weight
        self._restore(edit.before)
        self._redo.append(edit)
        return True

    def redo(self) -> bool:
        """Redo the most recently undone edit; return ``False`` when none is pending."""
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
        """Return whether an active selection spans at least one character."""
        return self.anchor is not None and self.anchor != self.cursor

    def selection(self) -> tuple[Pos, Pos] | None:
        """Return the selection as ordered (start, end) positions, or ``None``."""
        if not self.has_selection():
            return None
        assert self.anchor is not None
        return (min(self.anchor, self.cursor), max(self.anchor, self.cursor))

    def selected_text(self) -> str | None:
        """Return the selected text (possibly spanning rows), or ``None``."""
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
        """Return the (first, last) rows covered by the selection, or ``None``."""
        sel = self.selection()
        if sel is None:
            return None
        return sel[0][0], sel[1][0]

    def clear_selection(self) -> None:
        """Drop the selection anchor, keeping the cursor where it is."""
        self.anchor = None

    # ------------------------------------------------------- multi-cursor

    def add_cursor_at(self, pos: Pos) -> bool:
        """Add a multi-cursor point at *pos*; ``False`` when it already exists.

        Entering multi-cursor mode clears the primary selection (the anchor),
        keeping the two state axes (selection vs extra cursors) exclusive.
        *pos* is clamped exactly like :meth:`set_cursor`.
        """
        r = max(0, min(pos[0], len(self.lines) - 1))
        c = max(0, min(pos[1], len(self.lines[r])))
        point = (r, c)
        self.anchor = None
        if point in self.extra_cursors:
            return False
        self.extra_cursors.append(point)
        return True

    def add_cursor_below(self) -> bool:
        """Add a cursor on the next row at the last point's column.

        The "last point" is the bottom-most of the primary cursor and the
        extra cursors, so repeated ``ALT+C`` walks downward one point per
        press.  ``False`` (no-op) when there is no next row.  Like
        :meth:`add_cursor_at`, entering multi-cursor mode clears the
        primary selection.  No duplicate check is needed: the target row
        (bottom-most row + 1) is strictly below every existing point, so
        it can never collide with one.
        """
        bottom = max(self._multi_points())
        row, col = bottom
        if row >= len(self.lines) - 1:
            return False
        self.anchor = None
        self.extra_cursors.append((row + 1, min(col, len(self.lines[row + 1]))))
        return True

    def clear_extra_cursors(self) -> None:
        """Drop every extra multi-cursor point (back to single cursor)."""
        self.extra_cursors = []

    def has_extra_cursors(self) -> bool:
        """Whether multi-cursor mode is active (any extra point exists)."""
        return bool(self.extra_cursors)

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
        """Select the whole document from (0, 0) to the end of the last line."""
        self.anchor = (0, 0)
        self.cursor = (len(self.lines) - 1, len(self.lines[-1]))
        self._goal_col = None

    # ------------------------------------------------------------ mutations

    def _delete_range(self, start: Pos, end: Pos) -> None:
        """Delete the half-open range [start, end).

        Purely a line-structure primitive: it does *not* move the cursor.
        Callers that used to rely on the old cursor side effect position
        the cursor (or a multi-cursor point) themselves -- the multi-point
        primitives drive this method once per point with the primary
        cursor's new position written back explicitly.
        """
        (r1, c1), (r2, c2) = start, end
        if r1 == r2:
            self.lines[r1] = self.lines[r1][:c1] + self.lines[r1][c2:]
        else:
            self.lines[r1] = self.lines[r1][:c1] + self.lines[r2][c2:]
            del self.lines[r1 + 1 : r2 + 1]

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
            self.cursor = sel[0]
        self.cursor = self._apply_text(text, self.cursor)
        self.anchor = None
        self._commit(before, kind)

    def _apply_text(self, text: str, pos: Pos) -> Pos:
        """Insert ``text`` at *pos* without snapshot bookkeeping.

        Returns the position following the inserted text; the caller owns
        every cursor bookkeeping (single cursor or multi-cursor points).
        """
        r, c = pos
        parts = text.split("\n")
        line = self.lines[r]
        if len(parts) == 1:
            self.lines[r] = line[:c] + parts[0] + line[c:]
            return (r, c + len(parts[0]))
        self.lines[r] = line[:c] + parts[0]
        tail = line[c:]
        new_lines = list(parts[1:-1])
        new_lines.append(parts[-1] + tail)
        self.lines[r + 1 : r + 1] = new_lines
        return (r + len(parts) - 1, len(parts[-1]))

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
        self.cursor = self._apply_text(text, self.cursor)
        self.anchor = None
        self._commit(before, "step")

    def type_char(self, ch: str, *, language: str = "plaintext") -> None:
        """Insert a typed character, auto-completing and skipping bracket pairs.

        This is the single entry point the keymaps use for printable keys, so
        every editor mode shares one behaviour.  Branches, in priority order:
        anything that is not a single printable character falls back to
        :meth:`insert_text`; a selection wraps (``(sel) -> (sel)`` with the
        cursor left before the closing symbol) or, for any other key, is
        replaced as usual; **without** a selection a closing symbol typed in
        front of its twin only moves right instead of doubling it -- that test
        runs before the completion branch on purpose, so the quotes (whose
        left and right halves are the same character) skip too; otherwise a
        left symbol inserts both halves and parks the cursor between them.
        Both halves of an auto-completed pair land in one undo step
        (``"char"`` kind), so a single Ctrl+Z never leaves an orphan bracket
        behind.

        *language* is the seam that keeps the feature extensible per language:
        the keymaps pass :attr:`~yate.session.Document.filetype` straight
        through, and V1 reads it not at all because one pair table serves
        every language.  Should pairs ever diverge (Python quote handling, say),
        dispatch on the value right here -- no keymap change needed.
        """
        # Explicit guard, not a redundant one: the "closing symbol in front of
        # its twin" branch further down returns without touching the text, so
        # nothing it calls would ever raise on a read-only buffer.  Delegating
        # the check to ``insert_text`` alone would let that path type happily
        # on a buffer that must refuse every mutation.
        self._ensure_writable()
        if len(ch) != 1 or not ch.isprintable():
            self.insert_text(ch)
            return
        right = pair_for(ch)
        sel = self.selection()
        if sel is not None:
            if right is None:
                self.insert_text(ch)
                return
            (r1, c1), (r2, c2) = sel
            inner = self.selected_text() or ""
            before = self._snapshot()
            # Deliberately not :meth:`replace_range`: it hard-codes
            # ``kind="step"``, and the wrap has to stay a ``"char"`` edit so
            # that the auto-completed pair merges with the keystrokes around
            # it into one undo entry.  Under ``"step"`` the closing symbol
            # would survive a Ctrl+Z that takes back the opening one, leaving
            # an orphan bracket behind (issue G8).
            self.set_cursor((r1, c1))
            self._delete_range((r1, c1), (r2, c2))
            self.cursor = self._apply_text(f"{ch}{inner}{right}", self.cursor)
            self.move_left()  # park before the closing symbol, not after it
            self._commit(before, "char")
            return
        r, c = self.cursor
        line = self.lines[r]
        # Ahead of the completion branch: for the quotes ``pair_for`` returns
        # the character itself, so a completion-first order would make the
        # skip unreachable and turn `""` + `"` into `""""`.
        if ch in CLOSERS and c < len(line) and line[c] == ch:
            self.move_right()
            return
        if right is not None:
            before = self._snapshot()
            self.cursor = self._apply_text(ch + right, self.cursor)
            self.move_left()
            self._commit(before, "char")
            return
        self.insert_text(ch)

    def insert_newline(self, *, language: str = "plaintext") -> None:
        """Insert a newline carrying (or opening) the current line's indentation.

        The new line starts with the current line's leading whitespace, plus one
        :func:`~yate.editor_core.indentation.indent_unit` when that line opens a
        block for *language* (in Python: a trailing ``:``).  Blank lines and
        block-closing statements such as ``return`` keep the current level --
        undoing a level on ``else:`` / ``elif:`` is a syntax-level feature V1
        leaves out.
        """
        self._ensure_writable()
        r, _ = self.cursor
        line = self.lines[r]
        # Two scans where the old code made three.  ``strip`` answers both the
        # blank test and the block test at once, and ``opens_block`` rstrips
        # internally anyway, so handing it the stripped text means that third
        # scan now walks no characters.  The indent keeps its own left-only
        # strip: slicing ``line[: len(line) - len(stripped)]`` would be shorter
        # code but wrong whenever the line has trailing whitespace, because
        # ``strip`` eats both ends and the slice would then reach past the
        # indent into the line's own text (``"if x:  "`` -> ``"if"``).
        stripped = line.strip()
        indent = line[: len(line) - len(line.lstrip(" \t"))]
        rules = rules_for(language)
        if stripped and opens_block(rules, stripped):
            indent += indent_unit(self.tab_width, self.use_spaces)
        self.insert_text("\n" + indent, kind="char")

    def insert_tab(self) -> None:
        """Indent the selected rows, or insert a tab / spaces to the next tab stop."""
        if self.has_selection():
            self.indent_selection()
            return
        _, c = self.cursor
        if self.use_spaces:
            width = self.tab_width - (c % self.tab_width)
            self.insert_text(" " * width, kind="char")
        else:
            self.insert_text("\t", kind="char")

    def delete_selection(self) -> str | None:
        """Delete the selection and return the removed text, or ``None``."""
        self._ensure_writable()
        sel = self.selection()
        if sel is None:
            return None
        before = self._snapshot()
        text = self.selected_text()
        self._delete_range(*sel)
        self.cursor = sel[0]
        self.anchor = None
        self._commit(before, "step")
        return text

    def delete_backward(self, word: bool = False) -> None:
        """Delete backward one character (or *word*), joining rows at column 0.

        With the cursor between the two halves of an emptied bracket pair,
        Backspace removes both of them at once (unless *word* asks for a whole
        word) -- they go as a single ``"char"`` undo step, so one Ctrl+Z undoes
        the pair-typed and the pair-deleted keystroke together.
        """
        self._ensure_writable()
        if self.has_selection():
            self.delete_selection()
            return
        before = self._snapshot()
        r, c = self.cursor
        if r == 0 and c == 0:
            return
        line = self.lines[r]
        if not word and 0 < c < len(line) and is_pair_of(line[c - 1], line[c]):
            self.lines[r] = line[: c - 1] + line[c + 1 :]
            # set_cursor, not a bare assignment: the row just lost two
            # characters, and the buffer's invariant ends vertical goal-column
            # tracking only when the cursor is placed through here.  Same
            # rationale as the selection-wrapping branch in ``type_char``.
            self.set_cursor((r, c - 1))
            self._commit(before, "char")
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
        """Delete forward one character (or *word*), joining rows at end of line."""
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

    # ------------------------------------------------- multi-point primitives

    def _multi_points(self) -> list[Pos]:
        """Return all active points, primary first, deduplicated and clamped.

        The primary cursor always comes first; extras equal to the primary
        (or to each other) are dropped so one physical location never edits
        twice.  Every point is clamped exactly like :meth:`set_cursor`, so
        stale points surviving an undo or an external rewrite stay legal.
        """
        points: list[Pos] = [self.cursor]
        last = len(self.lines) - 1
        for pos in self.extra_cursors:
            r = max(0, min(pos[0], last))
            c = max(0, min(pos[1], len(self.lines[r])))
            if (r, c) not in points:
                points.append((r, c))
        return points

    def insert_at_points(self, text: str, kind: str = "char") -> None:
        """Insert *text* at every active point as ONE undo step.

        Points are processed in descending (row, col) order so an insertion
        containing newlines never invalidates a not-yet-processed point's
        position; the primary cursor ends at its own post-insert position
        and every extra point follows its own insertion.  Positions already
        recorded for earlier points are remapped through each later edit
        (rows below shift down, same-row columns shift with the text), so
        no point drifts off its own insertion.  No bracket auto-completion
        (a single-cursor :meth:`type_char` affordance) and no per-point
        auto-indent: a ``"\\n"`` inserts a bare newline at each point
        (known limitation).  Read-only buffers raise
        :class:`BufferReadOnlyError`.  Any multi-point edit drops the
        primary selection anchor first: the selection and multi-cursor
        axes stay exclusive for the whole edit, not just at entry.
        """
        self._ensure_writable()
        if text == "":
            return
        self.anchor = None
        points = self._multi_points()
        before = self._snapshot()
        log.debug("multi-cursor insert: points=%d", len(points))
        parts = text.split("\n")
        new_pos: dict[Pos, Pos] = {}
        for pos in sorted(points, reverse=True):
            recorded = self._apply_text(text, pos)
            _remap_after_insert(new_pos, pos, parts)
            new_pos[pos] = recorded
        self.cursor = new_pos[points[0]]
        self.extra_cursors = [new_pos[pos] for pos in points[1:]]
        self._goal_col = None
        self._commit(before, kind)

    def delete_at_points(self) -> None:
        """Delete one character before every active point as ONE undo step.

        At column 0 the point joins the previous row (newline deletion);
        (0, 0) is a no-op for that point.  Descending order, deduplicated.
        Positions already recorded for earlier points are remapped through
        each later deletion (same-row columns shift left; a joined row
        folds onto the seam with the rows below shifting up).  Read-only
        buffers raise :class:`BufferReadOnlyError`.  Any multi-point edit
        drops the primary selection anchor first: the selection and
        multi-cursor axes stay exclusive for the whole edit, not just at
        entry.
        """
        self._ensure_writable()
        self.anchor = None
        points = self._multi_points()
        before = self._snapshot()
        log.debug("multi-cursor delete: points=%d", len(points))
        new_pos: dict[Pos, Pos] = {}
        for pos in sorted(points, reverse=True):
            r, c = pos
            if r == 0 and c == 0:
                new_pos[pos] = pos
            elif c == 0:
                start = (r - 1, len(self.lines[r - 1]))
                self._delete_range(start, pos)
                # Descending order leaves every recorded point on row r or
                # below: its row folds into row r - 1 at the seam, rows
                # further down shift up one.
                for p, (pr, pc) in new_pos.items():
                    if pr == r:
                        new_pos[p] = (r - 1, start[1] + pc)
                    else:
                        new_pos[p] = (pr - 1, pc)
                new_pos[pos] = start
            else:
                self._delete_range((r, c - 1), (r, c))
                for p, (pr, pc) in new_pos.items():
                    if pr == r and pc >= c:
                        new_pos[p] = (r, pc - 1)
                new_pos[pos] = (r, c - 1)
        self.cursor = new_pos[points[0]]
        self.extra_cursors = [new_pos[pos] for pos in points[1:]]
        self._goal_col = None
        self._commit(before, "char")

    def delete_forward_at_points(self) -> None:
        """Delete one character after every active point as ONE undo step.

        At end-of-row the point joins the next row; end of document is a
        no-op for that point.  Descending order, deduplicated.  Positions
        already recorded for earlier points are remapped
        through each later deletion (same-row columns shift left; a joined
        next row folds onto the seam with the rows below shifting up).  Read-only
        buffers raise :class:`BufferReadOnlyError`.  Any multi-point edit
        drops the primary selection anchor first: the selection and
        multi-cursor axes stay exclusive for the whole edit, not just at
        entry.
        """
        self._ensure_writable()
        self.anchor = None
        points = self._multi_points()
        before = self._snapshot()
        log.debug("multi-cursor delete forward: points=%d", len(points))
        new_pos: dict[Pos, Pos] = {}
        for pos in sorted(points, reverse=True):
            r, c = pos
            line = self.lines[r]
            if c >= len(line) and r >= len(self.lines) - 1:
                new_pos[pos] = pos
            elif c >= len(line):
                self._delete_range(pos, (r + 1, 0))
                # Descending order leaves every recorded point on row r + 1
                # or below: the joined row folds into row r at the seam,
                # rows further down shift up one.
                for p, (pr, pc) in new_pos.items():
                    if pr == r + 1:
                        new_pos[p] = (r, c + pc)
                    else:
                        new_pos[p] = (pr - 1, pc)
                new_pos[pos] = pos
            else:
                self._delete_range(pos, (r, c + 1))
                for p, (pr, pc) in new_pos.items():
                    if pr == r and pc > c:
                        new_pos[p] = (r, pc - 1)
                new_pos[pos] = pos
        self.cursor = new_pos[points[0]]
        self.extra_cursors = [new_pos[pos] for pos in points[1:]]
        self._goal_col = None
        self._commit(before, "char")

    # ------------------------------------------------------------- movements

    def move_left(self, select: bool = False, word: bool = False) -> None:
        """Move left one character (or *word*), wrapping to the previous row."""
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
        """Move right one character (or *word*), wrapping to the next row."""
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
        """Move up one row, keeping the vertical goal column."""
        r, c = self.cursor
        goal = self._goal_col if self._goal_col is not None else c
        if r > 0:
            r -= 1
        self.set_cursor((r, goal), select)
        # set_cursor cleared the goal; restore it so consecutive vertical
        # motions keep aiming at the column the run started from
        self._goal_col = goal

    def move_down(self, select: bool = False) -> None:
        """Move down one row, keeping the vertical goal column."""
        r, c = self.cursor
        goal = self._goal_col if self._goal_col is not None else c
        if r < len(self.lines) - 1:
            r += 1
        self.set_cursor((r, goal), select)
        self._goal_col = goal

    def move_line_start(self, select: bool = False, toggle: bool = True) -> None:
        """Move to the first non-blank column, toggling to column 0 when already there."""
        r, c = self.cursor
        line = self.lines[r]
        first_non_ws = len(line) - len(line.lstrip(" \t"))
        if toggle and c == first_non_ws and first_non_ws != 0:
            target = 0
        else:
            target = first_non_ws
        self.set_cursor((r, target), select)

    def move_line_end(self, select: bool = False) -> None:
        """Move the cursor to the end of the current row."""
        r, _ = self.cursor
        self.set_cursor((r, len(self.lines[r])), select)

    def move_doc_start(self, select: bool = False) -> None:
        """Move the cursor to the start of the document."""
        self.set_cursor((0, 0), select)

    def move_doc_end(self, select: bool = False) -> None:
        """Move the cursor to the end of the last row."""
        r = len(self.lines) - 1
        self.set_cursor((r, len(self.lines[r])), select)

    # --------------------------------------------------------- line commands

    def indent_selection(self) -> None:
        """Indent the selected rows by one unit (a lone cursor inserts a tab)."""
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
        """Outdent the selected rows (or the cursor row) by one tab stop."""
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

    def yank_lines(self, *, named: str | None = None) -> str:
        """Yank the selected lines, or the current line (line-wise).

        With *named* the text goes to that explicit ``"`` register instead
        of the unnamed one (and never touches the system clipboard).
        """
        rows = self.selected_rows()
        if rows is None:
            r1 = r2 = self.cursor[0]
        else:
            r1, r2 = rows
        text = "\n".join(self.lines[r1 : r2 + 1]) + "\n"
        if named is None:
            self.register = text
        else:
            self.named_registers[named] = text
        return text

    def yank_selection(self, *, named: str | None = None) -> str:
        """Yank the selection, or the current line if there is none.

        With *named* the text goes to that explicit ``"`` register instead
        of the unnamed one (and never touches the system clipboard).
        """
        if self.has_selection():
            text = self.selected_text() or ""
        else:
            text = self.lines[self.cursor[0]]
        if named is None:
            self.register = text
        else:
            self.named_registers[named] = text
        return text

    def delete_lines(self, *, named: str | None = None) -> str:
        """Delete selected lines (or the current line) and yank them.

        With *named* the deleted text goes to that explicit ``"`` register
        instead of the unnamed one (and never touches the system clipboard).
        """
        self._ensure_writable()
        before = self._snapshot()
        rows = self.selected_rows()
        if rows is None:
            r1 = r2 = self.cursor[0]
        else:
            r1, r2 = rows
        text = "\n".join(self.lines[r1 : r2 + 1]) + "\n"
        if named is None:
            self.register = text
        else:
            self.named_registers[named] = text
        del self.lines[r1 : r2 + 1]
        if not self.lines:
            self.lines = [""]
        r = min(r1, len(self.lines) - 1)
        self.cursor = (r, 0)
        self.anchor = None
        self._commit(before, "step")
        return text

    def duplicate_line(self) -> None:
        """Duplicate the selected rows (or the current row) directly below them."""
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
        """Move the current row by *delta* rows; no-op when the target is out of range."""
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
            # ``nxt`` is non-empty here (guarded above), so a single join
            # with a separating space is all that is needed.
            joined = cur + " " + nxt.lstrip(" \t")
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
        self.cursor = (r, 0)
        self.anchor = None
        self._commit(before, "step")

    def paste(self, below: bool = True, *, named: str | None = None) -> None:
        """Paste a register at the cursor (below it when *below*).

        With *named* the text comes from that explicit ``"`` register
        instead of the unnamed one; a missing named register is a no-op.
        """
        self._ensure_writable()
        text = (
            self.named_registers.get(named, "") if named is not None else self.register
        )
        if not text:
            return
        if text.endswith("\n"):
            # line-wise paste
            r = self.cursor[0]
            if below and r >= len(self.lines) - 1:
                # Pasting below the last line: set_cursor would clamp the
                # target row back onto r and split the current line, so the
                # pasted lines would land *above* the cursor's line.  Append
                # from the end of the last line instead (vim ``p`` inserts
                # after the current line).
                self.set_cursor((r, len(self.lines[r])))
                self.insert_text("\n" + text[:-1], kind="step")
                self.move_line_end()
                self.move_left()
                return
            target = r + 1 if below else r
            self.set_cursor((target, 0))
            self.insert_text(text[:-1] + "\n", kind="step")
            self.move_line_end()
            self.move_left()
        else:
            self.insert_text(text, kind="step")
