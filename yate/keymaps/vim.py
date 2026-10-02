"""Modal vim key map for yate.

Implements a practical vim subset: NORMAL / INSERT / VISUAL / VISUAL-LINE
modes, counts, operator+motion (``d``/``y``/``c``), word motions, marks-less
navigation, search via ``/``/``?``/``n``/``N`` and ex commands via ``:``.

Operator-pending state is kept in structured fields (:attr:`op`,
:attr:`prefix`, :attr:`obj_scope`) so combinations like ``c`` + text object
resolve unambiguously; counts multiply between the operator and the motion
(``2d3w`` deletes six words).
"""

from __future__ import annotations

from enum import Enum
from typing import override

from yate.editor_core.buffer import (
    BufferReadOnlyError,
    Pos,
    TextBuffer,
    next_word_start,
)
from yate.editor_core.textobjects import (
    at_word_end,
    find_char,
    first_non_blank,
    next_word_pos,
    prev_word_pos,
    resolve_text_object,
    word_end_column,
)
from yate.keymaps.base import (
    ActionContext,
    KeyBinding,
    KeyUi,
    Keymap,
    parse_key,
)


class VimMode(str, Enum):
    """The modal states the vim keymap dispatches on."""

    NORMAL = "normal"
    INSERT = "insert"
    VISUAL = "visual"
    VISUAL_LINE = "visual_line"


# Motion keys accepted after an operator or in visual mode.
_MOTION_CODES: set[str] = {"h", "l", "j", "k", "w", "b", "e", "0", "$", "g", "G"}
_ARROW: dict[str, str] = {
    "\x1b[D": "h",
    "\x1b[C": "l",
    "\x1b[A": "k",
    "\x1b[B": "j",
}

#: Prefix keys that arm a second key: the ones before the bar can complete an
#: operator (``dg g``/``df x``), ``r`` cannot and drops a pending operator.
_PREFIX_MOTIONS: tuple[str, ...] = ("g", "f", "F", "t", "T")
_PREFIX_KEYS: tuple[str, ...] = (*_PREFIX_MOTIONS, "r")

#: Prefixes whose follower is a printable argument: a digit typed after them
#: is that argument (vim ``f3`` finds the char "3", ``r5`` replaces with "5"),
#: not a count.  The ``g`` prefix keeps taking digits for ``g{count}g``.
_ARG_PREFIXES: tuple[str, ...] = ("f", "F", "t", "T", "r")

_FUNCTION_KEYS: frozenset[str] = frozenset(parse_key(f"<f{i}>") for i in range(1, 13))

# help categories (module level: uppercase constants)
NAV: str = "Vim: motion"
INS: str = "Vim: insert"
EDT: str = "Vim: edit"
CMD: str = "Vim: command"
HLP: str = "Vim: help"


class VimKeymap(Keymap):
    """Mode-aware vim keymap provider dispatching on :class:`VimMode`.

    Pending chord state (:attr:`mode`, :attr:`op`, :attr:`prefix`,
    :attr:`obj_scope`, :attr:`count_str`) is instance-local, so every
    keypress extends or resolves exactly one in-flight chord and no
    half-typed combination ever leaks between keymap instances.
    """

    name = "vim"
    label = "Vim (modal)"

    def __init__(self) -> None:
        super().__init__()
        self.mode = VimMode.NORMAL
        self.op: str | None = None  # armed operator: "d", "y" or "c"
        self.prefix: str | None = None  # armed prefix key: g/f/F/t/T/r
        self.obj_scope: str | None = None  # text-object scope: "i" or "a"
        self.op_count: int | None = None  # count typed before the operator
        self.count_str = ""
        # (char, backward, till) of the last successful find, for ; and ,
        self.last_find: tuple[str, bool, bool] | None = None

    # ------------------------------------------------------------------ help

    @override
    def build_bindings(self) -> list[KeyBinding]:
        """The vim binding table (normal, insert and visual share one list)."""
        return [
            KeyBinding("h", "move left", "Move left", NAV),
            KeyBinding("l", "move right", "Move right", NAV),
            KeyBinding("j", "move down", "Move down", NAV),
            KeyBinding("k", "move up", "Move up", NAV),
            KeyBinding("w", "word forward", "Next word", NAV),
            KeyBinding("b", "word backward", "Previous word", NAV),
            KeyBinding("e", "word end", "End of word", NAV),
            KeyBinding("0", "line start", "Line start", NAV),
            KeyBinding("$", "line end", "Line end", NAV),
            KeyBinding("gg", "doc start", "Document start", NAV),
            KeyBinding("G", "doc end", "Document end / jump to [count]", NAV),
            KeyBinding("f{char}", "find char", "Find char forward", NAV),
            KeyBinding("F{char}", "find char back", "Find char backward", NAV),
            KeyBinding("t{char}", "till char", "To char forward", NAV),
            KeyBinding("T{char}", "till char back", "To char backward", NAV),
            KeyBinding(";", "find repeat", "Repeat the last find forward", NAV),
            KeyBinding(",", "find repeat back", "Repeat the last find backward", NAV),
            KeyBinding(parse_key("<ctrl-g>"), "go to line", "Go to line (enter line number)", NAV),
            KeyBinding(parse_key("<ctrl-d>"), "half page down", "Half page down", NAV),
            KeyBinding(parse_key("<ctrl-u>"), "half page up", "Half page up", NAV),
            KeyBinding(parse_key("<ctrl-f>"), "page down", "Page down", NAV),
            KeyBinding(parse_key("<ctrl-b>"), "page up", "Page up", NAV),
            KeyBinding("i", "insert mode", "Insert before cursor", INS),
            KeyBinding("a", "insert after", "Insert after cursor", INS),
            KeyBinding("I", "insert at line start", "Insert at line start", INS),
            KeyBinding("A", "insert at line end", "Insert at line end", INS),
            KeyBinding("o", "open line below", "Open line below", INS),
            KeyBinding("O", "open line above", "Open line above", INS),
            KeyBinding(parse_key("<esc>"), "back to normal", "Return to normal mode", INS),
            KeyBinding("v", "visual mode", "Characterwise visual mode", EDT),
            KeyBinding("V", "visual line mode", "Linewise visual mode", EDT),
            KeyBinding("x", "delete char", "Delete character", EDT),
            KeyBinding("r{char}", "replace char", "Replace [count] chars with {char}", EDT),
            KeyBinding("dd", "delete line", "Delete line", EDT),
            KeyBinding("yy", "yank line", "Yank line", EDT),
            KeyBinding("cc", "change line", "Change line", EDT),
            KeyBinding("d{motion}", "delete motion", "Delete over motion", EDT),
            KeyBinding("y{motion}", "yank motion", "Yank over motion", EDT),
            KeyBinding("c{motion}", "change motion", "Change over motion", EDT),
            KeyBinding("{op}{i|a}{object}", "text object",
                "Operate on a text object (iw aw i( i\" it ...)", EDT,
            ),
            KeyBinding("p", "paste below", "Paste after", EDT),
            KeyBinding("P", "paste above", "Paste before", EDT),
            KeyBinding("u", "undo", "Undo", EDT),
            KeyBinding(parse_key("<ctrl-r>"), "redo", "Redo", EDT),
            KeyBinding("J", "join lines", "Join lines", EDT),
            KeyBinding("/", "search forward", "Search forward", CMD),
            KeyBinding("?", "search backward", "Search backward", CMD),
            KeyBinding("n", "next match", "Next match", CMD),
            KeyBinding("N", "previous match", "Previous match", CMD),
            KeyBinding(":", "ex command", "Ex command (:w :q :e :! ...)", CMD),
            KeyBinding(parse_key("<f1>"), "help", "Keyboard shortcuts help", HLP),
            KeyBinding(parse_key("<f2>"), "shell_prompt", "Run shell command", CMD),
            KeyBinding(parse_key("<f3>"), "find_next", "Next match", CMD),
            KeyBinding(parse_key("<f4>"), "replace", "Find & replace", CMD),
            KeyBinding(parse_key("<f5>"), "command_prompt",
                "Ex command line (:w :q :e :! ...)", CMD,
            ),
            KeyBinding(parse_key("<f8>"), "manual", "Open user manual (read-only)", HLP),
            KeyBinding(
                parse_key("<alt-shift-s>"), "toggle_screensaver",
                "Toggle the idle screensaver", CMD,
            ),
            KeyBinding("\x1f", "toggle_keymap", "Toggle vim/vsc keymap (ctrl+/)", HLP),
        ]

    # --------------------------------------------------------------- dispatch

    @override
    def handle_key(self, ctx: ActionContext, key: str) -> bool:
        """Dispatch one key according to the current vim mode.

        The ctrl+/ keymap toggle and the function keys are handled before
        mode dispatch (see the comment below); everything else routes to
        the insert, visual or normal handler.
        """
        # ctrl+/ is a raw (non-printable) key that never reaches mode dispatch;
        # handle it first so the toggle works in every vim mode and drops any
        # half-finished operator/count state.
        if key == "\x1f":
            self._clear_pending()
            ctx.ui.toggle_keymap()
            return True
        if key in _FUNCTION_KEYS:
            self._clear_pending()
            binding = self.lookup(key)
            if binding is not None:
                # A dead action (typo / unloaded extension) is reported by
                # dispatch(); the key stays consumed either way -- unbound
                # F-keys are swallowed too, and a dead action on an
                # extension-bound normal key is absorbed the same way.
                self.dispatch(binding, ctx)
            return True
        if self.mode == VimMode.INSERT:
            return self._handle_insert(ctx, key)
        if self.mode in (VimMode.VISUAL, VimMode.VISUAL_LINE):
            return self._handle_visual(ctx, key)
        return self._handle_normal(ctx, key)

    def _extension_binding(self, ctx: ActionContext, key: str) -> bool:
        """Run an extension-registered binding for *key*, if any."""
        binding = self._index.get(key)
        if binding is not None and binding.category == "extension":
            return self.dispatch(binding, ctx)
        return False

    def _clear_pending(self) -> None:
        """Drop every half-finished operator/prefix/count state."""
        self._clear_operator()
        self.prefix = None
        self.count_str = ""

    def _clear_operator(self) -> None:
        """Drop the armed operator with its scope and count companions."""
        self.op = None
        self.obj_scope = None
        self.op_count = None

    # ------------------------------------------------------------- insert mode

    def _handle_insert(self, ctx: ActionContext, key: str) -> bool:
        ui = ctx.ui
        if key in ("\x1b",):  # esc / ctrl-[
            self.mode = VimMode.NORMAL
            ctx.buffer.move_left()
            ui.message("-- NORMAL --")
            return True
        if key == "\r":
            ui.execute_action("newline")
            return True
        if key == "\t":
            ui.execute_action("insert_tab")
            return True
        if key == "\x7f":
            ui.execute_action("delete_backward")
            return True
        if key == "\x1b[3~":
            ui.execute_action("delete_forward")
            return True
        if key == "\x17":  # ctrl-w: delete word backwards
            ui.execute_action("delete_word_back")
            return True
        if key == "\x15":  # ctrl-u: delete to line start
            ui.execute_action("delete_to_line_start")
            return True
        if key in _ARROW:
            self._motion(ctx, _ARROW[key], 1, select=False)
            return True
        if len(key) == 1 and key.isprintable():
            ctx.buffer.insert_text(key)
            return True
        return True

    # ------------------------------------------------------------ visual mode

    def _handle_visual(self, ctx: ActionContext, key: str) -> bool:
        buf = ctx.buffer
        ui = ctx.ui
        linewise = self.mode == VimMode.VISUAL_LINE

        if key == "\x1b":
            buf.clear_selection()
            self.mode = VimMode.NORMAL
            ui.message("-- NORMAL --")
            return True
        if key == "v":
            if self.mode == VimMode.VISUAL:
                buf.clear_selection()
                self.mode = VimMode.NORMAL
            else:
                self.mode = VimMode.VISUAL
            return True
        if key == "V":
            self.mode = VimMode.VISUAL_LINE if not linewise else VimMode.VISUAL
            self._fix_linewise(buf)
            return True
        if key in ("y", "d", "x"):
            if linewise:
                if key == "y":
                    buf.yank_lines()
                    sel = buf.selection()
                    if sel is not None:
                        # vim lands on the first column of the first yanked row
                        buf.set_cursor((sel[0][0], 0))
                    ui.message("yanked lines")
                else:
                    buf.delete_lines()
                    ui.message("deleted lines")
            else:
                if key == "y":
                    buf.yank_selection()
                    ui.message("yanked")
                    sel = buf.selection()
                    r, c = sel[0] if sel is not None else buf.cursor
                    buf.clear_selection()
                    buf.cursor = (r, c)
                else:
                    text = buf.delete_selection()
                    if text is not None:
                        buf.register = text
                    ui.message("deleted selection")
            self.mode = VimMode.NORMAL
            return True
        if key == ":":
            buf.clear_selection()
            self.mode = VimMode.NORMAL
            ui.command_prompt()
            return True
        if key == "/":
            self.mode = VimMode.NORMAL
            buf.clear_selection()
            ui.find_prompt(True)
            return True
        if key == "?":
            self.mode = VimMode.NORMAL
            buf.clear_selection()
            ui.find_prompt(False)
            return True
        # motions extend the selection; digits are consumed but not stored
        # (visual mode deliberately ignores counts, see the test pinning it)
        typed = self._typed_count()
        self.count_str = ""
        if key in _ARROW:
            self._motion(ctx, _ARROW[key], typed, select=True)
        elif key in _MOTION_CODES:
            self._motion(ctx, key, typed, select=True)
        else:
            return True
        if self.mode == VimMode.VISUAL_LINE:
            self._fix_linewise(buf)
        return True

    def _fix_linewise(self, buf: TextBuffer) -> None:
        sel = buf.selection()
        if sel is None:
            r = buf.row
            buf.anchor = (r, 0)
            buf.cursor = (r, len(buf.lines[r]))
            return
        (r1, _), (r2, _) = sel
        buf.anchor = (r1, 0)
        buf.cursor = (r2, len(buf.lines[r2]))

    # ------------------------------------------------------------ normal mode

    def _handle_normal(self, ctx: ActionContext, key: str) -> bool:
        ui = ctx.ui
        buf = ctx.buffer

        if key == "\x1b":
            self._clear_pending()
            return True

        if key == "\x07":  # ctrl-g: go to line (same as typing :42)
            self._clear_pending()
            ui.goto_prompt()
            return True

        if (
            key.isdigit()
            and not (key == "0" and not self.count_str)
            and self.prefix not in _ARG_PREFIXES
        ):
            self.count_str += key
            return True

        # resolve an armed prefix: "g" completes on a second "g", the
        # find-char prefixes complete on their printable argument key
        if self.prefix == "g" and key == "g":
            self._resolve_gg(ctx)
            return True
        if self.prefix in ("f", "F", "t", "T") and len(key) == 1 and key.isprintable():
            assert self.prefix is not None
            self._resolve_find(
                ctx,
                key,
                backward=self.prefix in ("F", "T"),
                till=self.prefix in ("t", "T"),
            )
            return True
        if self.prefix == "r" and len(key) == 1 and key.isprintable():
            self._resolve_replace(ctx, key)
            return True
        if self.prefix is not None:
            # unknown follower: drop the prefix, process the key as a fresh one
            self.prefix = None

        if self.op is not None and self._handle_operator_pending(ctx, key):
            return True

        # arm a prefix key ("g" / find-char / "r"); a pending operator survives
        # for the motion-completing prefixes and was already dropped otherwise
        if key in _PREFIX_KEYS:
            if key == "r" and self.op is not None:
                # r cannot complete an operator, vim cancels it instead
                self._clear_operator()
            self.prefix = key
            return True

        # arm an operator
        if key in ("d", "y", "c"):
            self.op = key
            self.op_count = self._typed_count()
            self.count_str = ""
            return True

        if key in _ARROW or key in _MOTION_CODES:
            self._motion(ctx, _ARROW.get(key, key), self._typed_count(), select=False)
            self.count_str = ""
            return True

        if key in (";", ",") and self.last_find is not None:
            self._repeat_find(ctx, key)
            return True

        if key == "x":
            for _ in range(self._take_count()):
                buf.delete_forward()
            return True
        if key == "p":
            for _ in range(self._take_count()):
                buf.paste(below=True)
            return True
        if key == "P":
            for _ in range(self._take_count()):
                buf.paste(below=False)
            return True
        if key == "u":
            buf.undo()
            return True
        if key == "\x12":  # ctrl-r
            buf.redo()
            return True
        if key == "J":
            ui.execute_action("join_lines")
            return True
        if key == "\x04":  # ctrl-d
            ui.execute_action("page_half_down")
            return True
        if key == "\x15":  # ctrl-u
            ui.execute_action("page_half_up")
            return True
        if key == "\x06":  # ctrl-f
            ui.execute_action("page_down")
            return True
        if key == "\x02":  # ctrl-b
            ui.execute_action("page_up")
            return True

        # insert entry points
        entry = {
            "i": lambda: None,
            "I": buf.move_line_start,
            # set_cursor clamps to the line end, so "a" never spills onto the
            # next line the way raw move_right does from the EOL column
            "a": lambda: buf.set_cursor((buf.row, buf.col + 1)),
            "A": buf.move_line_end,
        }
        if key in entry:
            # Refuse insert entry on a read-only buffer (vim E21): stay in
            # NORMAL and surface the notice through the dispatch handler,
            # matching the o/O refusal path.
            if buf.read_only:
                raise BufferReadOnlyError("buffer is read-only")
            entry[key]()
            self._enter_insert(ui)
            return True
        if key == "o":
            buf.move_line_end()
            buf.insert_newline()
            self._enter_insert(ui)
            return True
        if key == "O":
            buf.move_line_start()
            buf.insert_newline()
            buf.move_up()
            self._enter_insert(ui)
            return True

        if key == "v":
            self.mode = VimMode.VISUAL
            buf.anchor = buf.cursor
            ui.message("-- VISUAL --")
            return True
        if key == "V":
            self.mode = VimMode.VISUAL_LINE
            r = buf.row
            buf.anchor = (r, 0)
            buf.cursor = (r, len(buf.lines[r]))
            ui.message("-- VISUAL LINE --")
            return True

        if key == "/":
            ui.find_prompt(True)
            return True
        if key == "?":
            ui.find_prompt(False)
            return True
        if key == ":":
            ui.command_prompt()
            return True
        if key == "n":
            ui.execute_action("find_next")
            return True
        if key == "N":
            ui.execute_action("find_prev")
            return True

        # extensions may bind extra keys in normal mode
        if self._extension_binding(ctx, key):
            return True

        # swallow unmapped normal keys
        return True

    def _handle_operator_pending(self, ctx: ActionContext, key: str) -> bool:
        """Resolve *key* against the armed operator; ``False`` drops it."""
        op = self.op
        if op is None:
            return False
        if self.obj_scope is not None:
            return self._apply_text_object(ctx, key)
        if key == op:  # dd / yy / cc
            self._linewise_op(ctx, op)
            return True
        if key in ("i", "a"):
            self.obj_scope = key
            return True
        if key in _PREFIX_MOTIONS:
            self.prefix = key
            return True
        if key in (";", ",") and self.last_find is not None:
            self._repeat_find(ctx, key)
            return True
        if key in _MOTION_CODES or key in _ARROW:
            self._apply_operator(ctx, op, _ARROW.get(key, key))
            return True
        # Not a motion this operator understands: cancel it like vim does and
        # let the key fall through as a fresh normal-mode key.  Leaving the
        # operator armed would fire it on the next motion key instead.
        self._clear_pending()
        return False

    def _linewise_op(self, ctx: ActionContext, op: str) -> None:
        """Run a counted linewise ``dd`` / ``yy`` / ``cc``."""
        buf = ctx.buffer
        ui = ctx.ui
        n = self.op_count or 1
        self._clear_operator()
        r1 = buf.row
        col = buf.col  # yy keeps the cursor where it is, like vim
        r2 = min(r1 + n - 1, len(buf.lines) - 1)
        buf.anchor = (r1, 0)
        buf.cursor = (r2, len(buf.lines[r2]))
        if op == "d":
            buf.delete_lines()
            ui.message("deleted line")
        elif op == "y":
            buf.yank_lines()
            buf.anchor = None
            buf.cursor = (r1, min(col, len(buf.lines[r1])))
            ui.message("yanked line")
        else:
            # change: the merged remains collapse into one empty line
            buf.delete_selection()
            self._enter_insert(ui)

    def _resolve_gg(self, ctx: ActionContext) -> None:
        """Complete ``gg``: a jump, or a linewise span for a pending operator."""
        self.prefix = None
        buf = ctx.buffer
        ui = ctx.ui
        motion_typed = self._typed_count()
        self.count_str = ""
        target = motion_typed if motion_typed is not None else self.op_count or 1
        op = self.op
        self._clear_operator()
        if op is None:
            r = min(target - 1, len(buf.lines) - 1)
            buf.set_cursor((r, first_non_blank(buf.lines[r])))
            return
        r1, r2 = sorted((target - 1, buf.row))
        r2 = min(r2, len(buf.lines) - 1)
        buf.anchor = (r1, 0)
        buf.cursor = (r2, len(buf.lines[r2]))
        if op == "y":
            buf.yank_lines()
            buf.anchor = None
            buf.cursor = (r1, 0)
            ui.message("yanked")
        elif op == "d":
            buf.delete_lines()
            ui.message("deleted")
        else:
            buf.delete_selection()
            self._enter_insert(ui)

    def _find_target(
        self, ctx: ActionContext, ch: str, backward: bool, till: bool
    ) -> Pos | None:
        """Locate the counted occurrence of *ch* on the cursor row.

        The count is the operator count times the motion count (vim ``2dfx``
        deletes through the second ``x``).  ``None`` when the row has fewer
        matches, in which case nothing moves.
        """
        buf = ctx.buffer
        motion_typed = self._typed_count()
        self.count_str = ""
        n = (self.op_count or 1) * (motion_typed or 1)
        col = find_char(buf.lines[buf.row], buf.col, ch, count=n, backward=backward, till=till)
        if col is None:
            return None
        return (buf.row, col)

    def _resolve_find(
        self,
        ctx: ActionContext,
        ch: str,
        *,
        backward: bool,
        till: bool,
        record: bool = True,
    ) -> None:
        """Complete a find-char prefix: move, or run the pending operator.

        A miss reports through the UI and leaves the buffer untouched.  The
        operator span is inclusive of both the found char and the cursor char
        (vim ``dfx`` / ``dFx``); *record* is ``False`` for ``;``/`,` repeats
        so the direction flip on ``,` never rewrites the stored find.
        """
        op = self.op
        target = self._find_target(ctx, ch, backward, till)
        self.prefix = None
        self._clear_operator()
        if target is None:
            ctx.ui.message("not found")
            return
        if record:
            self.last_find = (ch, backward, till)
        buf = ctx.buffer
        if op is None:
            buf.set_cursor(target)
            return
        if backward:
            # [target, cursor] inclusive -> half-open [target, cursor+1)
            end = (buf.row, min(buf.col + 1, len(buf.lines[buf.row])))
            self._apply_span(ctx, op, target, end)
        else:
            # [cursor, target] inclusive -> half-open [cursor, target+1)
            self._apply_span(ctx, op, buf.cursor, (buf.row, target[1] + 1))

    def _repeat_find(self, ctx: ActionContext, key: str) -> None:
        """Re-run the last find: ``;`` keeps its direction, ``,`` flips it."""
        assert self.last_find is not None
        ch, backward, till = self.last_find
        if key == ",":
            backward = not backward
        self._resolve_find(ctx, ch, backward=backward, till=till, record=False)

    def _resolve_replace(self, ctx: ActionContext, ch: str) -> None:
        """Complete ``r{char}``: swap *count* chars for *ch*, or report.

        vim refuses a replace that would run past the end of the line; the
        cursor ends on the last replaced character.
        """
        self.prefix = None
        buf = ctx.buffer
        n = self._take_count()
        r, c = buf.cursor
        line = buf.lines[r]
        if c + n > len(line):
            ctx.ui.message("nothing to replace")
            return
        buf.replace_range((r, c), (r, c + n), ch * n)
        buf.cursor = (r, c + n - 1)

    def _enter_insert(self, ui: KeyUi) -> None:
        self.mode = VimMode.INSERT
        ui.message("-- INSERT --")

    # -------------------------------------------------------------- counts

    def _typed_count(self) -> int | None:
        """The count typed so far, or ``None`` when no digits were given."""
        return int(self.count_str) if self.count_str else None

    def _take_count(self) -> int:
        n = self._peek_count()
        self.count_str = ""
        return n

    def _peek_count(self) -> int:
        return int(self.count_str) if self.count_str else 1

    # -------------------------------------------------------------- motions

    def _motion(self, ctx: ActionContext, code: str, count: int | None, select: bool) -> None:
        buf = ctx.buffer
        n = count if count is not None else 1
        for _ in range(n):
            if code == "h":
                buf.move_left(select=select)
            elif code == "l":
                buf.move_right(select=select)
            elif code == "j":
                buf.move_down(select=select)
            elif code == "k":
                buf.move_up(select=select)
            elif code == "w":
                pos = next_word_pos(buf.lines, buf.row, buf.col)
                if pos is not None:
                    buf.set_cursor(pos, select=select)
            elif code == "b":
                pos = prev_word_pos(buf.lines, buf.row, buf.col)
                if pos is not None:
                    buf.set_cursor(pos, select=select)
            elif code == "e":
                r, c = buf.cursor
                nc = word_end_column(buf.lines[r], c)
                while nc is None and r < len(buf.lines) - 1:
                    r += 1
                    nc = word_end_column(buf.lines[r], 0, from_start=True)
                if nc is not None:
                    # normal mode lands on the word's last char; visual and
                    # operator mode land one past it so the half-open
                    # selection keeps the whole word
                    buf.set_cursor((r, nc + 1 if select else nc), select=select)
            elif code == "0":
                # move_line_start has a "col 0 <-> first non-blank" toggle;
                # vim's 0 always lands on column 0
                buf.set_cursor((buf.row, 0), select=select)
            elif code == "$":
                if select:
                    buf.move_line_end(select=True)
                else:
                    # vim's $ sits on the last char; operator and visual mode
                    # keep the virtual EOL column so half-open spans reach it
                    r = buf.row
                    buf.set_cursor((r, max(0, len(buf.lines[r]) - 1)))
            elif code == "G":
                # jump, not repeatable: a count names the target line.  Normal
                # mode lands on the first non-blank like vim's G; visual and
                # operator mode keep the line-edge column so half-open spans
                # (d5G, dG) still reach the target char.
                if count is not None:
                    r = count - 1
                else:
                    r = len(buf.lines) - 1
                if select:
                    col = 0 if count is not None else len(buf.lines[r])
                    buf.set_cursor((r, col), select=True)
                else:
                    buf.set_cursor((r, first_non_blank(buf.lines[r])))
                break  # G is a jump, never repeat it count times
            elif code == "g":
                # pending gg handled in caller
                break

    # ------------------------------------------------------------ operators

    def _apply_operator(self, ctx: ActionContext, op: str, code: str) -> None:
        """Run *op* over the charwise region covered by motion *code*."""
        motion_typed = self._typed_count()
        self.count_str = ""
        effective = (self.op_count or 1) * (motion_typed or 1)
        given = self.op_count is not None or motion_typed is not None
        count = effective if given else None
        self._clear_operator()
        buf = ctx.buffer
        start = buf.cursor
        if code == "w":
            row = buf.lines[start[0]]
            nc = next_word_start(row, start[1])
            if not start[1] < nc < len(row):
                # vim's exclusive rule: when w leaves the row (no further
                # word start on it) the operator stops at the line end
                # instead of swallowing the newline
                code = "$"
            elif op == "c" and self._on_non_blank(buf):
                # vim special case: cw on a word is ce; on whitespace it
                # stays dw.  On the last char of that word vim changes only
                # that char -- the e motion would run on to the next word.
                if count is None and at_word_end(buf.lines[start[0]], start[1]):
                    code = "l"
                else:
                    code = "e"
        elif code == "b":
            pos = prev_word_pos(buf.lines, *start)
            if pos is None or pos[0] != start[0]:
                # same rule backwards: b stops at the line start
                code = "0"
        buf.anchor = start
        self._motion(ctx, code, count, select=True)
        if code == "G" and count is not None:
            # vim's G lands on the first char of the target line and the
            # operator span includes it; yate selections are half-open
            r = buf.row
            buf.cursor = (r, min(1, len(buf.lines[r])))
        self._apply_span(ctx, op, start, buf.cursor)

    def _apply_span(self, ctx: ActionContext, op: str, start: Pos, end: Pos) -> None:
        """Run *op* over the charwise span from *start* inclusive to *end* exclusive.

        *end* is the first kept column, so ``len(row)`` is a legal end (span
        reaches the line end).  Callers build endpoints with ``+1`` arithmetic
        and pass through object spans; clamping the column here keeps an
        overshoot from reaching the buffer's half-open deletion, whose
        multi-row join would silently swallow text past the row end.
        """
        buf = ctx.buffer
        ui = ctx.ui
        er, ec = end
        if er < len(buf.lines) and ec > len(buf.lines[er]):
            end = (er, len(buf.lines[er]))
        buf.anchor = start
        buf.cursor = end
        if op == "y":
            if buf.has_selection():
                buf.yank_selection()
                buf.cursor = start
                buf.anchor = None
                ui.message("yanked")
            else:
                buf.anchor = None
            return
        text = buf.delete_selection()
        if text is not None:
            buf.register = text
        if op == "c":
            self._enter_insert(ui)
        elif text is not None:
            ui.message("deleted")

    def _apply_text_object(self, ctx: ActionContext, key: str) -> bool:
        """Resolve *key* as a text object and run the pending operator on it.

        The key is always consumed: a miss (unknown object, unbalanced pair)
        drops the operator without touching the buffer.
        """
        op = self.op
        scope = self.obj_scope
        motion_typed = self._typed_count()
        count = (self.op_count or 1) * (motion_typed or 1)
        self.prefix = None
        self._clear_operator()
        self.count_str = ""
        assert op is not None and scope is not None
        buf = ctx.buffer
        span = resolve_text_object(buf.lines, buf.cursor, scope, key, count)
        if span is None:
            ctx.ui.message("no text object")
            return True
        self._apply_span(ctx, op, span[0], span[1])
        return True

    @staticmethod
    def _on_non_blank(buf: TextBuffer) -> bool:
        """Whether the cursor sits on a non-blank character."""
        line = buf.lines[buf.row]
        return buf.col < len(line) and not line[buf.col].isspace()
