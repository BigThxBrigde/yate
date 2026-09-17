"""Modal vim key map for yate.

Implements a practical vim subset: NORMAL / INSERT / VISUAL / VISUAL-LINE
modes, counts, operator+motion (d/y), word motions, marks-less navigation,
search via ``/``/``?``/``n``/``N`` and ex commands via ``:``.
"""

from __future__ import annotations

from enum import Enum

from yate.editor_core.buffer import TextBuffer, word_end
from yate.interfaces import AppProtocol
from yate.keymaps.base import ActionContext, KeyBinding, Keymap, parse_key


class VimMode(str, Enum):
    NORMAL = "normal"
    INSERT = "insert"
    VISUAL = "visual"
    VISUAL_LINE = "visual_line"


# Motion keys accepted after an operator or in visual mode.
_MOTION_CODES = {"h", "l", "j", "k", "w", "b", "e", "0", "$", "g", "G"}
_ARROW = {
    "\x1b[D": "h",
    "\x1b[C": "l",
    "\x1b[A": "k",
    "\x1b[B": "j",
}

_FUNCTION_KEYS = frozenset(parse_key(f"<f{i}>") for i in range(1, 13))

# help categories (module level: uppercase constants)
NAV = "Vim: motion"
INS = "Vim: insert"
EDT = "Vim: edit"
CMD = "Vim: command"
HLP = "Vim: help"


class VimKeymap(Keymap):
    name = "vim"
    label = "Vim (modal)"

    def __init__(self) -> None:
        super().__init__()
        self.mode = VimMode.NORMAL
        self.pending = ""  # operator prefix: "d", "y", "g"
        self.count_str = ""

    # ------------------------------------------------------------------ help

    def build_bindings(self) -> list[KeyBinding]:
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
            KeyBinding("dd", "delete line", "Delete line", EDT),
            KeyBinding("yy", "yank line", "Yank line", EDT),
            KeyBinding("d{motion}", "delete motion", "Delete over motion", EDT),
            KeyBinding("y{motion}", "yank motion", "Yank over motion", EDT),
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
            KeyBinding(parse_key("<f5>"), "command_prompt", "Ex command line (:w :q :e :! ...)", CMD),
            KeyBinding(parse_key("<f8>"), "manual", "Open user manual (read-only)", HLP),
        ]

    # --------------------------------------------------------------- dispatch

    def handle_key(self, ctx: ActionContext, key: str) -> bool:
        if key in _FUNCTION_KEYS:
            self.pending = ""
            self.count_str = ""
            binding = self.lookup(key)
            if binding is not None:
                return self.dispatch(binding, ctx)
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

    # ------------------------------------------------------------- insert mode

    def _handle_insert(self, ctx: ActionContext, key: str) -> bool:
        app = ctx.app
        if key in ("\x1b",):  # esc / ctrl-[
            self.mode = VimMode.NORMAL
            ctx.buffer.move_left()
            app.message("-- NORMAL --")
            return True
        if key == "\r":
            app.execute_action("newline")
            return True
        if key == "\t":
            app.execute_action("insert_tab")
            return True
        if key == "\x7f":
            app.execute_action("delete_backward")
            return True
        if key == "\x1b[3~":
            app.execute_action("delete_forward")
            return True
        if key == "\x17":  # ctrl-w: delete word backwards
            app.execute_action("delete_word_back")
            return True
        if key == "\x15":  # ctrl-u: delete to line start
            app.execute_action("delete_to_line_start")
            return True
        if key in _ARROW:
            self._motion(ctx, _ARROW[key], 1, select=False)
            return True
        if len(key) == 1 and key.isprintable():
            app.insert_char(key)
            return True
        return True

    # ------------------------------------------------------------ visual mode

    def _handle_visual(self, ctx: ActionContext, key: str) -> bool:
        buf = ctx.buffer
        app = ctx.app
        linewise = self.mode == VimMode.VISUAL_LINE

        if key == "\x1b":
            buf.clear_selection()
            self.mode = VimMode.NORMAL
            app.message("-- NORMAL --")
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
                    app.message("yanked lines")
                else:
                    buf.delete_lines()
                    app.message("deleted lines")
            else:
                if key == "y":
                    buf.yank_selection()
                    app.message("yanked")
                    sel = buf.selection()
                    r, c = sel[0] if sel is not None else buf.cursor
                    buf.clear_selection()
                    buf.cursor = (r, c)
                else:
                    text = buf.delete_selection()
                    if text is not None:
                        buf.register = text
                    app.message("deleted selection")
            self.mode = VimMode.NORMAL
            return True
        if key == ":":
            buf.clear_selection()
            self.mode = VimMode.NORMAL
            app.command_prompt()
            return True
        if key == "/":
            self.mode = VimMode.NORMAL
            buf.clear_selection()
            app.find_prompt(forward=True)
            return True
        if key == "?":
            self.mode = VimMode.NORMAL
            buf.clear_selection()
            app.find_prompt(forward=False)
            return True
        # motions extend the selection
        count = self._take_count()
        if key in _ARROW:
            self._motion(ctx, _ARROW[key], count, select=True)
        elif key in _MOTION_CODES or (self.pending == "g" and key == "g"):
            self._motion(ctx, key, count, select=True)
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
        app = ctx.app
        buf = ctx.buffer

        if key == "\x1b":
            self.pending = ""
            self.count_str = ""
            return True

        if key == "\x07":  # ctrl-g: go to line (same as typing :42)
            self.pending = ""
            self.count_str = ""
            app.goto_prompt()
            return True

        if key.isdigit() and not (key == "0" and not self.count_str):
            self.count_str += key
            return True

        count = self._peek_count()

        # g prefix
        if self.pending == "g" and key == "g":
            self.pending = ""
            n = self._take_count()
            if self.count_str == "" and n == 1:
                buf.move_doc_start()
            else:
                # motion needs direct cursor placement; TextBuffer.set_cursor
                # provides the clamp/anchor semantics for an arbitrary jump
                buf.set_cursor((n - 1, 0))
            return True
        if key == "g" and self.pending == "":
            self.pending = "g"
            return True
        if self.pending == "g":
            # "g" followed by something we don't support: drop the prefix.
            self.pending = ""

        # operators d / y
        if key in ("d", "y") and self.pending == "":
            self.pending = key
            return True
        if self.pending in ("d", "y"):
            op = self.pending
            self.pending = ""
            n = self._take_count()
            if key == op:
                # dd / yy
                if op == "d":
                    buf.delete_lines()
                    app.message("deleted line")
                else:
                    buf.yank_lines()
                    app.message("yanked line")
                return True
            if key in _MOTION_CODES or key in _ARROW:
                self._apply_operator(ctx, op, key, n)
                return True
            # unknown motion: drop operator, fall through with key
            self.count_str = ""

        if key in _ARROW or key in _MOTION_CODES:
            self._motion(ctx, _ARROW.get(key, key), count, select=False)
            self._take_count()
            return True

        if key == "x":
            for _ in range(self._take_count()):
                buf.delete_forward()
            return True
        if key == "p":
            buf.paste(below=True)
            return True
        if key == "P":
            buf.paste(below=False)
            return True
        if key == "u":
            buf.undo()
            return True
        if key == "\x12":  # ctrl-r
            buf.redo()
            return True
        if key == "J":
            app.execute_action("join_lines")
            return True
        if key == "\x04":  # ctrl-d
            app.execute_action("page_half_down")
            return True
        if key == "\x15":  # ctrl-u
            app.execute_action("page_half_up")
            return True
        if key == "\x06":  # ctrl-f
            app.execute_action("page_down")
            return True
        if key == "\x02":  # ctrl-b
            app.execute_action("page_up")
            return True

        # insert entry points
        entry = {
            "i": lambda: None,
            "I": buf.move_line_start,
            "a": buf.move_right,
            "A": buf.move_line_end,
        }
        if key in entry:
            entry[key]()
            self._enter_insert(app)
            if key == "o":
                pass
            return True
        if key == "o":
            buf.move_line_end()
            buf.insert_newline()
            self._enter_insert(app)
            return True
        if key == "O":
            buf.move_line_start()
            buf.insert_newline()
            buf.move_up()
            self._enter_insert(app)
            return True

        if key == "v":
            self.mode = VimMode.VISUAL
            buf.anchor = buf.cursor
            app.message("-- VISUAL --")
            return True
        if key == "V":
            self.mode = VimMode.VISUAL_LINE
            r = buf.row
            buf.anchor = (r, 0)
            buf.cursor = (r, len(buf.lines[r]))
            app.message("-- VISUAL LINE --")
            return True

        if key == "/":
            app.find_prompt(forward=True)
            return True
        if key == "?":
            app.find_prompt(forward=False)
            return True
        if key == ":":
            app.command_prompt()
            return True
        if key == "n":
            app.execute_action("find_next")
            return True
        if key == "N":
            app.execute_action("find_prev")
            return True

        # extensions may bind extra keys in normal mode
        if self._extension_binding(ctx, key):
            return True

        # swallow unmapped normal keys
        return True

    def _enter_insert(self, app: AppProtocol) -> None:
        self.mode = VimMode.INSERT
        app.message("-- INSERT --")

    # -------------------------------------------------------------- motions

    def _peek_count(self) -> int:
        return int(self.count_str) if self.count_str else 1

    def _take_count(self) -> int:
        n = self._peek_count()
        self.count_str = ""
        return n

    def _motion(self, ctx: ActionContext, code: str, count: int, select: bool) -> None:
        buf = ctx.buffer
        for _ in range(count):
            if code == "h":
                buf.move_left(select=select)
            elif code == "l":
                buf.move_right(select=select)
            elif code == "j":
                buf.move_down(select=select)
            elif code == "k":
                buf.move_up(select=select)
            elif code == "w":
                buf.move_right(select=select, word=True)
            elif code == "b":
                buf.move_left(select=select, word=True)
            elif code == "e":
                r, c = buf.cursor
                line = buf.lines[r]
                nc = word_end(line, c)
                if nc == c and r < len(buf.lines) - 1:
                    r += 1
                    nc = 0
                buf.set_cursor((r, nc), select=select)
            elif code == "0":
                # move_line_start has a "col 0 <-> first non-blank" toggle;
                # vim's 0 always lands on column 0
                buf.set_cursor((buf.row, 0), select=select)
            elif code == "$":
                buf.move_line_end(select=select)
            elif code == "G":
                if self.count_str:
                    # jump, not repeatable
                    buf.set_cursor((self._take_count() - 1, 0), select=select)
                else:
                    buf.move_doc_end(select=select)
                break  # G is a jump, never repeat it count times
            elif code == "g":
                # pending gg handled in caller
                break

    def _apply_operator(self, ctx: ActionContext, op: str, code: str, count: int) -> None:
        buf = ctx.buffer
        app = ctx.app
        start = buf.cursor
        buf.anchor = start
        self._motion(ctx, code, count, select=True)
        if op == "y":
            buf.yank_selection()
            buf.cursor = start
            buf.anchor = None
            app.message("yanked")
        else:
            buf.delete_selection()
            app.message("deleted")
