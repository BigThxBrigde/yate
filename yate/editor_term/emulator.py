"""A small VT100/xterm terminal emulator.

Pure, UI independent and dependency free: bytes in (the PTY output) update a
cell grid plus scrollback; the Textual widget renders the grid and converts
key events back to byte sequences via :func:`key_to_terminal`.

The parser implements the subset that makes modern shells usable:

* C0 controls (CR/LF/BS/TAB/BEL), autowrap and wide characters;
* cursor movement, insert/delete line/character, erase commands;
* SGR styles (bold/dim/italic/underline/reverse), the 16 ANSI colors,
  256-color palette and truecolor;
* DECSTBM scroll regions, the 1047/1049 alternate screen, DECSC/DECRC;
* OSC strings (titles are captured, the rest skipped);
* device queries shells rely on (CPR cursor position, primary attributes);
  replies go through the ``on_response`` sink straight back to the PTY.
"""

from __future__ import annotations

import codecs
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass, replace

from yate.editor_term.keys import key_to_terminal as key_to_terminal
from yate.editor_term.palette import ANSI_16_RGB, RGB, palette_color

#: Maximum scrollback lines kept (older lines are dropped).
MAX_SCROLLBACK: int = 5000

#: Maximum bytes buffered for a partial CSI sequence; a malformed stream
#: that never terminates the sequence cannot grow the parser state.
_CSI_MAX: int = 64

#: Maximum bytes buffered for an OSC string (OSC 52 payloads can be large,
#: hence the generous cap); beyond it the string is discarded.
_OSC_MAX: int = 1 << 20


@dataclass
class Cell:
    """One terminal character cell with its SGR attributes."""

    char: str = " "
    fg: RGB | None = None
    bg: RGB | None = None
    bold: bool = False
    dim: bool = False
    italic: bool = False
    underline: bool = False
    reverse: bool = False

    def style_key(self) -> tuple[object, ...]:
        """Hashable SGR signature of the cell (colors and flags, no glyph)."""
        return (self.fg, self.bg, self.bold, self.dim, self.italic,
                self.underline, self.reverse)


def _char_width(ch: str) -> int:
    """Terminal column width of *ch* (0 = combining, 2 = wide)."""
    if not ch or unicodedata.combining(ch) or ord(ch) < 0x20:
        return 0
    return 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1


# ------------------------------------------------------------------ emulator

_GROUND: int = 0
_ESCAPE: int = 1
_CSI: int = 2
_OSC: int = 3
_ESC_INTERMEDIATE: int = 4


#: ``on_response(data)`` -- bytes the terminal must answer with (device
#: reports, cursor queries); the dock writes them back to the PTY.
type ResponseFn = Callable[[bytes], None]


class TerminalEmulator:
    """A grid-based VT emulator fed by :meth:`feed`."""

    def __init__(
        self,
        cols: int = 80,
        rows: int = 24,
        *,
        on_response: ResponseFn | None = None,
    ) -> None:
        self.cols = max(1, cols)
        self.rows = max(1, rows)
        self._on_response = on_response
        self.title = ""

        self.grid: list[list[Cell]] = []
        self.alt_grid: list[list[Cell]] = []
        self.scrollback: list[list[Cell]] = []
        self.in_alt = False

        # Cursor state per screen (primary, alternate).
        self._cur = [0, 0]
        self._alt_cur = [0, 0]
        self._saved = [0, 0]
        self._alt_saved = [0, 0]
        self.cursor_visible = True
        self.bracketed_paste = False

        # SGR attributes.
        self.fg: RGB | None = None
        self.bg: RGB | None = None
        self.bold = self.dim = self.italic = False
        self.underline = self.reverse = False

        self.scroll_top = 0
        self.scroll_bottom = self.rows - 1

        self.autowrap = True
        self._pen = False  # pending autowrap after writing the last column

        self._state = _GROUND
        self._csi = ""
        self._osc = ""
        self._osc_via_st = False
        # Incremental UTF-8 decoder held across feeds: a multi-byte sequence
        # split across two read blocks decodes once both halves arrived.
        self._decoder = codecs.getincrementaldecoder("utf-8")("replace")

        self._reset_grids()

    # ---------------------------------------------------------- grid helpers

    def _blank(self) -> Cell:
        return Cell(fg=self.fg, bg=self.bg, bold=self.bold, dim=self.dim,
                    italic=self.italic, underline=self.underline,
                    reverse=self.reverse)

    def _blank_line(self) -> list[Cell]:
        return [self._blank() for _ in range(self.cols)]

    def _reset_grids(self) -> None:
        self.grid = [self._blank_line() for _ in range(self.rows)]
        self.alt_grid = [self._blank_line() for _ in range(self.rows)]

    @property
    def _screen(self) -> list[list[Cell]]:
        return self.alt_grid if self.in_alt else self.grid

    @property
    def cursor(self) -> tuple[int, int]:
        """Cursor ``(row, col)`` of the active screen (primary or alternate)."""
        cur = self._alt_cur if self.in_alt else self._cur
        return cur[0], cur[1]

    def resize(self, cols: int, rows: int) -> None:
        """Resize the viewport, preserving the bottom of the screen.

        On the primary screen, rows removed from the top when shrinking
        move into the scrollback (xterm keeps them as history) instead of
        vanishing.
        """
        cols = max(1, cols)
        rows = max(1, rows)
        old_rows, old_cols = self.rows, self.cols
        new_grid = [[Cell() for _ in range(cols)] for _ in range(rows)]
        old = self._screen
        copy_rows = min(rows, old_rows)
        copy_cols = min(cols, old_cols)
        row_offset = rows - copy_rows
        col_offset = 0
        if not self.in_alt and rows < old_rows:
            dropped = old_rows - rows
            for i in range(dropped):
                self.scrollback.append(list(old[i]))
            overflow = len(self.scrollback) - MAX_SCROLLBACK
            if overflow > 0:
                del self.scrollback[:overflow]
        for i in range(copy_rows):
            for j in range(copy_cols):
                new_grid[row_offset + i][col_offset + j] = old[
                    old_rows - copy_rows + i
                ][j]
        if self.in_alt:
            self.alt_grid = new_grid
        else:
            self.grid = new_grid
        self.cols, self.rows = cols, rows
        cur = self._alt_cur if self.in_alt else self._cur
        cur[0] = min(cur[0], rows - 1)
        cur[1] = min(cur[1], cols - 1)
        self.scroll_top = 0
        self.scroll_bottom = rows - 1

    # ----------------------------------------------------------------- feed

    def feed(self, data: bytes) -> None:
        """Decode raw PTY output incrementally and parse each character.

        The decoder persists between feeds, so a multi-byte UTF-8 sequence
        split across two read blocks decodes once both halves arrived
        (per-call decoding would turn each half into U+FFFD).  Undecodable
        sequences are replaced, so malformed output can never abort the
        parser.
        """
        for ch in self._decoder.decode(data):
            self._consume(ch)

    def _respond(self, payload: str) -> None:
        if self._on_response is not None:
            self._on_response(payload.encode("ascii", errors="ignore"))

    def _consume(self, ch: str) -> None:
        if self._state == _GROUND:
            self._ground(ch)
        elif self._state == _ESCAPE:
            self._escape(ch)
        elif self._state == _ESC_INTERMEDIATE:
            # Charset designators etc. -- final byte is ignored.
            self._state = _GROUND
        elif self._state == _CSI:
            if ch == "\x1b":
                # ESC aborts a partial CSI (malformed stream): the next
                # character dispatches as the start of the new sequence.
                self._csi = ""
                self._state = _ESCAPE
            elif 0x40 <= ord(ch) <= 0x7E:
                params = self._csi
                self._csi = ""
                self._state = _GROUND
                self._csi_dispatch(ch, params)
            elif len(self._csi) < _CSI_MAX:
                self._csi += ch
            # Parameter bytes past _CSI_MAX are dropped; the final byte
            # still terminates the (garbage) sequence.
        elif self._state == _OSC:
            if ch == "\x07":
                self._osc_finish()
            elif ch == "\x1b":
                # Possible ST (ESC \\); the backslash is consumed in _escape.
                self._state = _ESCAPE
                self._osc_via_st = True
            elif len(self._osc) < _OSC_MAX:
                self._osc += ch
            # Payloads past _OSC_MAX are dropped (the terminator still
            # returns the parser to ground).

    def _osc_finish(self) -> None:
        text = self._osc
        self._osc = ""
        self._state = _GROUND
        # OSC 0/2 set the window title; nothing else is surfaced yet.
        if text.startswith(("0;", "2;")) and ";" in text:
            self.title = text.split(";", 1)[1]

    def _ground(self, ch: str) -> None:
        if ch == "\r":
            self._cur_col(0)
            self._pen = False
        elif ch == "\n" or ch == "\v" or ch == "\f":
            self._index()
        elif ch == "\b":
            cur = self._alt_cur if self.in_alt else self._cur
            cur[1] = max(0, cur[1] - 1)
            self._pen = False
        elif ch == "\t":
            self._tab()
        elif ch == "\x07":
            pass  # BEL
        elif ch == "\x1b":
            self._state = _ESCAPE
        elif ord(ch) >= 0x20:
            self._print(ch)

    def _escape(self, ch: str) -> None:
        if self._osc_via_st:
            self._osc_via_st = False
            if ch == "\\":
                self._osc_finish()
                return
            # A bare ESC aborted the OSC: fall through and dispatch *ch* as
            # the start of the next escape sequence instead of eating it.
        if ch == "[":
            self._state = _CSI
            self._csi = ""
        elif ch == "]":
            self._state = _OSC
        elif ch in "()*+%#":
            # Charset designators / DEC double-width line: swallow final.
            self._state = _ESC_INTERMEDIATE
        elif ch == "7":
            self._save_cursor()
            self._state = _GROUND
        elif ch == "8":
            self._restore_cursor()
            self._state = _GROUND
        elif ch == "D":
            self._index()
            self._state = _GROUND
        elif ch == "M":
            self._reverse_index()
            self._state = _GROUND
        elif ch == "E":
            self._index()
            self._cur_col(0)
            self._state = _GROUND
        elif ch == "c":
            self._soft_reset()
            self._state = _GROUND
        elif ch in "=>":
            self._state = _GROUND  # keypad modes, irrelevant
        else:
            self._state = _GROUND

    def _soft_reset(self) -> None:
        # RIS returns to the primary screen (xterm leaves the alternate
        # buffer and homes the cursor there); save_cursor=False because the
        # cursor is homed below anyway.
        self._set_alt_screen(False, save_cursor=False)
        self.fg = self.bg = None
        self.bold = self.dim = self.italic = False
        self.underline = self.reverse = False
        self.cursor_visible = True
        self.autowrap = True
        self.scroll_top = 0
        self.scroll_bottom = self.rows - 1
        self._cur = [0, 0]
        self._erase_display(2)

    # --------------------------------------------------------------- printing

    def _cur_col(self, col: int) -> None:
        cur = self._alt_cur if self.in_alt else self._cur
        cur[1] = max(0, min(col, self.cols - 1))

    def _print(self, ch: str) -> None:
        cur = self._alt_cur if self.in_alt else self._cur
        row, col = cur[0], cur[1]
        if self._pen and self.autowrap:
            self._index()
            row, col = cur[0], 0
        elif col >= self.cols:
            col = self.cols - 1
        self._pen = False
        width = _char_width(ch)
        if width == 0:
            # Combining mark: append to the previous cell.
            if col > 0:
                target_row, prev_col = row, col - 1
            elif row > 0:
                target_row, prev_col = row - 1, self.cols - 1
            else:
                return
            cell = self._screen[target_row][prev_col]
            if cell.char != " ":
                cell.char += ch
            return
        if col >= self.cols - (width - 1):
            if width == 2 and self.autowrap:
                # A wide glyph cannot straddle the margin: blank the last
                # cell, wrap now and draw it whole at column 0 of the next
                # line.  (The ASCII path above defers the wrap instead --
                # there the last column still fits, a wide glyph never does.)
                self._screen[row][self.cols - 1] = self._styled_cell("")
                self._index()
                row, col = cur[0], 0
            else:
                if width == 2:
                    self._screen[row][self.cols - 1] = self._styled_cell("")
                self._pen = True
                return
        cell = self._styled_cell(ch)
        self._screen[row][col] = cell
        if width == 2 and col + 1 < self.cols:
            self._screen[row][col + 1] = self._styled_cell("")
        cur[1] = col + width
        if cur[1] >= self.cols:
            cur[1] = self.cols
            self._pen = True

    def _styled_cell(self, char: str) -> Cell:
        return Cell(
            char=char,
            fg=self.fg,
            bg=self.bg,
            bold=self.bold,
            dim=self.dim,
            italic=self.italic,
            underline=self.underline,
            reverse=self.reverse,
        )

    def _tab(self) -> None:
        cur = self._alt_cur if self.in_alt else self._cur
        nxt = min(((cur[1] // 8) + 1) * 8, self.cols - 1)
        if nxt > cur[1]:
            cur[1] = nxt

    def _index(self) -> None:
        cur = self._alt_cur if self.in_alt else self._cur
        if cur[0] == self.scroll_bottom:
            self._scroll_up(1)
        elif cur[0] < self.rows - 1:
            cur[0] += 1

    def _reverse_index(self) -> None:
        cur = self._alt_cur if self.in_alt else self._cur
        if cur[0] == self.scroll_top:
            self._scroll_down(1)
        elif cur[0] > 0:
            cur[0] -= 1

    def _scroll_up(self, count: int) -> None:
        screen = self._screen
        top, bottom = self.scroll_top, self.scroll_bottom
        for _ in range(count):
            leaving = screen[top]
            if top == 0 and not self.in_alt:
                self.scrollback.append(leaving)
                if len(self.scrollback) > MAX_SCROLLBACK:
                    del self.scrollback[: len(self.scrollback) - MAX_SCROLLBACK]
            for r in range(top, bottom):
                screen[r] = screen[r + 1]
            screen[bottom] = self._blank_line()

    def _scroll_down(self, count: int) -> None:
        screen = self._screen
        top, bottom = self.scroll_top, self.scroll_bottom
        for _ in range(count):
            for r in range(bottom, top, -1):
                screen[r] = screen[r - 1]
            screen[top] = self._blank_line()

    def _save_cursor(self) -> None:
        target = self._alt_saved if self.in_alt else self._saved
        cur = self._alt_cur if self.in_alt else self._cur
        target[0], target[1] = cur[0], cur[1]

    def _restore_cursor(self) -> None:
        saved = self._alt_saved if self.in_alt else self._saved
        cur = self._alt_cur if self.in_alt else self._cur
        cur[0] = max(0, min(saved[0], self.rows - 1))
        cur[1] = max(0, min(saved[1], self.cols - 1))

    # ------------------------------------------------------------- CSI dispatch

    @staticmethod
    def _parse_params(params: str, default: int = 0) -> list[int]:
        if not params:
            return [default]
        tokens: list[int] = []
        for part in params.split(";"):
            head = part.split(":", 1)[0]
            try:
                tokens.append(int(head) if head else default)
            except ValueError:
                tokens.append(default)
        return tokens

    def _csi_dispatch(self, final: str, params: str) -> None:
        private = params.startswith("?")
        raw_params = params[1:] if private else params
        nums = self._parse_params(raw_params, default=0)

        if final in "h":
            if private:
                self._set_modes(nums, True)
            return
        if final in "l":
            if private:
                self._set_modes(nums, False)
            return

        cur = self._alt_cur if self.in_alt else self._cur

        if final in "HfABCDEFGdsu":
            # Any cursor movement cancels the pending autowrap state.
            self._pen = False

        if final in "Hf":
            row = max(1, nums[0] if nums else 1) - 1
            col = (nums[1] if len(nums) > 1 else 1) - 1
            cur[0] = max(0, min(row, self.rows - 1))
            cur[1] = max(0, min(col, self.cols - 1))
            self._pen = False
        elif final == "A":
            cur[0] = max(cur[0] - max(1, nums[0]), 0)
        elif final == "B" or final == "e":
            cur[0] = min(cur[0] + max(1, nums[0]), self.rows - 1)
        elif final in "Ca":
            cur[1] = min(cur[1] + max(1, nums[0]), self.cols - 1)
        elif final == "D":
            cur[1] = max(cur[1] - max(1, nums[0]), 0)
        elif final == "E":
            cur[0] = min(cur[0] + max(1, nums[0]), self.rows - 1)
            cur[1] = 0
        elif final == "F":
            cur[0] = max(cur[0] - max(1, nums[0]), 0)
            cur[1] = 0
        elif final == "G":
            col = max(1, nums[0]) - 1
            cur[1] = max(0, min(col, self.cols - 1))
        elif final == "d":
            row = max(1, nums[0]) - 1
            cur[0] = max(0, min(row, self.rows - 1))
        elif final == "J":
            self._erase_display(nums[0] if nums else 0)
        elif final == "K":
            self._erase_line(nums[0] if nums else 0)
        elif final == "m":
            self._sgr(nums if raw_params else [0])
        elif final == "r":
            top = (nums[0] - 1) if nums and nums[0] else 0
            bottom = (nums[1] - 1) if len(nums) > 1 and nums[1] else self.rows - 1
            if 0 <= top < bottom <= self.rows - 1:
                self.scroll_top, self.scroll_bottom = top, bottom
                cur[0], cur[1] = 0, 0
        elif final == "s":
            self._save_cursor()
        elif final == "u":
            self._restore_cursor()
        elif final == "@":
            self._insert_chars(max(1, nums[0]))
        elif final == "P":
            self._delete_chars(max(1, nums[0]))
        elif final == "X":
            self._erase_chars(max(1, nums[0]))
        elif final == "L":
            self._insert_lines(max(1, nums[0]))
        elif final == "M":
            self._delete_lines(max(1, nums[0]))
        elif final == "S":
            self._scroll_region_up(max(1, nums[0]))
        elif final == "T":
            self._scroll_region_down(max(1, nums[0]))
        elif final == "n":
            if nums and nums[0] == 6:
                self._respond(f"\x1b[{cur[0] + 1};{cur[1] + 1}R")
            elif nums and nums[0] == 5:
                self._respond("\x1b[0n")
        elif final == "c":
            self._respond("\x1b[?1;2c")

    def _set_modes(self, nums: list[int], on: bool) -> None:
        for num in nums:
            if num == 7:
                self.autowrap = on
            elif num == 25:
                self.cursor_visible = on
            elif num == 2004:
                self.bracketed_paste = on
            elif num in (47, 1047, 1049):
                self._set_alt_screen(on, save_cursor=(num == 1049))
            # other private modes are accepted and ignored

    def _set_alt_screen(self, on: bool, *, save_cursor: bool) -> None:
        if on == self.in_alt:
            return
        if on:
            if save_cursor:
                self._save_cursor()
            self.in_alt = True
            self.alt_grid = [
                [Cell() for _ in range(self.cols)] for _ in range(self.rows)
            ]
            self._alt_cur = [0, 0]
        else:
            self.in_alt = False
            if save_cursor:
                self._restore_cursor()

    # --------------------------------------------------------------- erasing

    def _fill(self, cell: Cell) -> Cell:
        return replace(cell, char=" ")

    def _erase_line(self, mode: int) -> None:
        cur = self._alt_cur if self.in_alt else self._cur
        row, col = cur[0], cur[1]
        line = self._screen[row]
        blank = self._blank()
        if mode == 0:
            for j in range(col, self.cols):
                line[j] = self._fill(blank)
        elif mode == 1:
            for j in range(0, col + 1):
                line[j] = self._fill(blank)
        else:
            for j in range(self.cols):
                line[j] = self._fill(blank)

    def _erase_display(self, mode: int) -> None:
        cur = self._alt_cur if self.in_alt else self._cur
        row = cur[0]
        blank = self._blank()
        if mode == 0:
            self._erase_line(0)
            for r in range(row + 1, self.rows):
                self._screen[r] = [self._fill(blank) for _ in range(self.cols)]
        elif mode == 1:
            for r in range(0, row):
                self._screen[r] = [self._fill(blank) for _ in range(self.cols)]
            self._erase_line(1)
        elif mode == 2:
            for r in range(self.rows):
                self._screen[r] = [self._fill(blank) for _ in range(self.cols)]
        elif mode == 3:
            self._erase_display(2)
            if not self.in_alt:
                self.scrollback.clear()

    def _insert_chars(self, count: int) -> None:
        cur = self._alt_cur if self.in_alt else self._cur
        row, col = cur[0], cur[1]
        line = self._screen[row]
        for _ in range(min(count, self.cols)):
            line.insert(col, self._blank())
            line.pop()

    def _delete_chars(self, count: int) -> None:
        cur = self._alt_cur if self.in_alt else self._cur
        row, col = cur[0], cur[1]
        line = self._screen[row]
        for _ in range(min(count, self.cols)):
            if col < len(line):
                line.pop(col)
                line.append(self._blank())

    def _erase_chars(self, count: int) -> None:
        cur = self._alt_cur if self.in_alt else self._cur
        row, col = cur[0], cur[1]
        line = self._screen[row]
        for j in range(col, min(col + count, self.cols)):
            line[j] = self._blank()

    def _insert_lines(self, count: int) -> None:
        cur = self._alt_cur if self.in_alt else self._cur
        top, bottom = self.scroll_top, self.scroll_bottom
        if not (top <= cur[0] <= bottom):
            return
        for _ in range(min(count, bottom - top + 1)):
            for r in range(bottom, cur[0], -1):
                self._screen[r] = self._screen[r - 1]
            self._screen[cur[0]] = self._blank_line()

    def _delete_lines(self, count: int) -> None:
        cur = self._alt_cur if self.in_alt else self._cur
        top, bottom = self.scroll_top, self.scroll_bottom
        if not (top <= cur[0] <= bottom):
            return
        for _ in range(min(count, bottom - top + 1)):
            for r in range(cur[0], bottom):
                self._screen[r] = self._screen[r + 1]
            self._screen[bottom] = self._blank_line()

    def _scroll_region_up(self, count: int) -> None:
        for _ in range(count):
            self._scroll_up(1)

    def _scroll_region_down(self, count: int) -> None:
        for _ in range(count):
            self._scroll_down(1)

    # -------------------------------------------------------------------- SGR

    def _sgr(self, nums: list[int]) -> None:
        i = 0
        if not nums:
            nums = [0]
        while i < len(nums):
            code = nums[i]

            if code == 0:
                self.fg = self.bg = None
                self.bold = self.dim = self.italic = False
                self.underline = self.reverse = False
            elif code == 1:
                self.bold = True
            elif code == 2:
                self.dim = True
            elif code == 3:
                self.italic = True
            elif code == 4:
                self.underline = True
            elif code == 7:
                self.reverse = True
            elif code == 22:
                self.bold = self.dim = False
            elif code == 23:
                self.italic = False
            elif code == 24:
                self.underline = False
            elif code == 27:
                self.reverse = False
            elif 30 <= code <= 37:
                self.fg = ANSI_16_RGB[code - 30]
            elif code == 39:
                self.fg = None
            elif 40 <= code <= 47:
                self.bg = ANSI_16_RGB[code - 40]
            elif code == 49:
                self.bg = None
            elif 90 <= code <= 97:
                self.fg = ANSI_16_RGB[code - 90 + 8]
            elif 100 <= code <= 107:
                self.bg = ANSI_16_RGB[code - 100 + 8]
            elif code in (38, 48) and i + 1 < len(nums):
                kind = nums[i + 1]
                if kind == 5 and i + 2 < len(nums):
                    color = palette_color(nums[i + 2])
                    i += 2
                    if code == 38:
                        self.fg = color
                    else:
                        self.bg = color
                elif kind == 2 and i + 4 < len(nums):
                    color = (
                        max(0, min(255, nums[i + 2])),
                        max(0, min(255, nums[i + 3])),
                        max(0, min(255, nums[i + 4])),
                    )
                    i += 4
                    if code == 38:
                        self.fg = color
                    else:
                        self.bg = color
            i += 1

    # ------------------------------------------------------------------ views

    def max_scroll(self) -> int:
        """How many rows the view may move back into the scrollback."""
        return 0 if self.in_alt else len(self.scrollback)

    def view_lines(self, scroll: int) -> list[list[Cell]]:
        """Return the *rows* lines to paint; *scroll* rows into scrollback."""
        if self.in_alt:
            return [list(line) for line in self.alt_grid]
        scroll = max(0, min(scroll, len(self.scrollback)))
        total = len(self.scrollback) + self.rows
        start = total - self.rows - scroll
        result: list[list[Cell]] = []
        if start < 0:
            result.extend([[Cell() for _ in range(self.cols)]
                           for _ in range(-start)])
            start = 0
        end = min(total, start + self.rows)
        sb_len = len(self.scrollback)
        for idx in range(max(0, start), end):
            # Index into the two sources directly: concatenating
            # scrollback + grid copies every line pointer on each frame.
            if idx < sb_len:
                result.append(list(self.scrollback[idx]))
            else:
                result.append(list(self.grid[idx - sb_len]))
        while len(result) < self.rows:
            result.append([Cell() for _ in range(self.cols)])
        return result
