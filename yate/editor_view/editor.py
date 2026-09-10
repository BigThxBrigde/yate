"""The main text editing widget (Textual widget, Rich segments)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

from rich.segment import Segment
from rich.style import Style
from textual.events import Key, Resize
from textual.geometry import Size
from textual.scroll_view import ScrollView
from textual.strip import Strip

from yate import __version__
from yate.editor_core.buffer import TextBuffer

from . import highlight, theme
from .highlight import Token
from .keys import event_to_raw

if TYPE_CHECKING:
    from yate.app import YateApp

# per-cell overlay ids (stacked on top of syntax foreground colors)
S_NORMAL = 0
S_MATCH = 1
S_SELECTION = 2
S_MATCH_ACTIVE = 3
S_CURSOR = 4

# Welcome-page block wordmark: "Y[>A terminal |T]E".  Kept as an ASCII
# template and translated so the source stays readable:
#   '#' full block   '>' arrow   '.' terminal title-bar dot
_BANNER_GLYPHS = {"#": "\u2588", ">": "\u25b6", ".": "\u2022"}
_BANNER_TEMPLATE = [
    "##    ##  ##               #                  ##",
    " ##  ##   #       ##       #        ########   # ########",
    "  ####    #      ####      #        ########   # ########",
    "   ##     #     ##  ##                ###      # ##",
    "   ##     #    ##    ## ###########   ###      # ##",
    "   ##     #  > ######## # . .     #   ###      # #######",
    "   ##     #    ##    ## #         #   ###      # #######",
    "   ##     #    ##    ## #         #   ###      # ##",
    "   ##     #    ##    ## ###########   ###      # ########",
    "          ##                                  ##",
]
_WELCOME_BANNER = [
    "".join(_BANNER_GLYPHS.get(ch, ch) for ch in line)
    for line in _BANNER_TEMPLATE
]


class EditorView(ScrollView):
    """Renders the active document: gutter, syntax, selection, matches, cursor.

    A ScrollView (like TextArea) so the framework honours the virtual size we
    set from the buffer and the viewport follows the cursor when it leaves
    the visible area.
    """

    can_focus = True

    DEFAULT_CSS = """
    EditorView {
        padding: 0;
        overflow-x: hidden;
    }
    """

    def __init__(self, app: YateApp, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.yate = app
        self.scroll_col = 0
        self._hl_tokens: Optional[list[list[Token]]] = None

    # ------------------------------------------------------------ helpers

    @property
    def buffer(self) -> TextBuffer:
        """The buffer of the currently active document."""
        return self.yate.buffer

    def content_changed(self) -> None:
        """Call after any buffer mutation / document switch."""
        self._hl_tokens = None
        self._update_virtual_size()
        self.reveal_cursor()
        self.refresh()

    def on_mount(self) -> None:
        """Apply the active theme background once mounted."""
        self.styles.background = theme.active().bg

    def _update_virtual_size(self) -> None:
        buf = self.buffer
        # Width tracks the scrollable content area so max_scroll_x stays 0:
        # horizontal movement is manual (scroll_col), not Textual scrolling.
        width = self.scrollable_content_region.width or self.size.width or 80
        self.virtual_size = Size(width, max(1, buf.line_count))

    def on_resize(self, _event: Resize) -> None:
        """Recompute the virtual (scrollable) size when the widget resizes."""
        self._update_virtual_size()

    def on_key(self, event: Key) -> None:
        """Forward keys to the yate keymap while the editor is focused."""
        if len(self.yate.screen_stack) > 1:
            return  # a modal screen owns input
        raw = event_to_raw(event.key, event.character)
        if raw is None:
            return
        if self.yate.handle_raw_key(raw):
            event.stop()
            event.prevent_default()

    def reveal_cursor(self) -> None:
        buf = self.buffer
        row, col = buf.cursor
        line = buf.lines[row]
        text_w = max(1, (self.size.width or 80) - self._gutter_w())
        cell = theme.char_to_cell(line, col, buf.tab_width)
        if cell < self.scroll_col:
            self.scroll_col = cell
        elif cell >= self.scroll_col + text_w:
            self.scroll_col = cell - text_w + 1
        self.scroll_col = max(0, self.scroll_col)
        # Follow the cursor only once it leaves the visible row window;
        # unconditionally scrolling here would pin it to the top row.
        view_h = max(1, self.size.height or 20)
        top = self.scroll_offset.y
        if row < top:
            self.scroll_to(y=row, animate=False)
        elif row >= top + view_h:
            self.scroll_to(y=row - view_h + 1, animate=False)
        self.refresh()

    def page_delta(self, half: bool = False) -> int:
        return max(1, ((self.size.height or 20) // 2) if half else (self.size.height or 20))

    def _gutter_w(self) -> int:
        return max(3, len(str(self.buffer.line_count))) + 2

    def _tokens_for(self, row: int) -> list[Token]:
        """Cached syntax tokens for one line (lazily tokenized)."""
        if self._hl_tokens is None:
            self._hl_tokens = highlight.tokenize_document(
                self.buffer.lines, self.yate.doc.filetype
            )
        return self._hl_tokens[row] if row < len(self._hl_tokens) else []

    def _syntax_kinds(self, row: int, line: str, cell_count: int) -> list[Optional[str]]:
        """Per-cell syntax token kind (char ranges mapped to display cells)."""
        tw = self.buffer.tab_width
        kinds: list[Optional[str]] = [None] * cell_count
        for tok in self._tokens_for(row):
            cs = theme.char_to_cell(line, tok.start, tw)
            ce = theme.char_to_cell(line, tok.end, tw)
            for c in range(max(0, cs), min(ce, cell_count)):
                kinds[c] = tok.kind
        return kinds

    # -------------------------------------------------------------- render

    def render_line(self, y: int) -> Strip:
        t = theme.active()
        buf = self.buffer
        view_w = self.size.width or 80
        gutter_w = self._gutter_w()
        text_w = max(1, view_w - gutter_w)

        digits = gutter_w - 2
        segments: list[Segment] = []

        def fill_line(bg: Optional[str]) -> None:
            segments.append(Segment(" " * view_w, Style(bgcolor=bg)))

        if self._welcome_active():
            return self._render_welcome(y, view_w, gutter_w, t)

        # Textual hands us the row relative to the visible widget region;
        # translate it into a buffer row via the scroll offset.
        y += self.scroll_offset.y
        if y >= buf.line_count:
            fill_line(t.bg)
            return Strip(segments)

        line = buf.lines[y]
        cells: list[str] = []
        for ch in line:
            theme.expand_char(ch, cells, buf.tab_width)
        if y == buf.row and buf.col == len(line):
            cells.append(" ")  # block cursor at end of line

        n_cells = len(cells)
        styles = [S_NORMAL] * (n_cells + 1)
        kinds = self._syntax_kinds(y, line, n_cells + 1)

        for start, end, sid in self._row_style_ranges(y, line):
            for c in range(max(0, start), min(end, n_cells + 1)):
                if sid > styles[c]:
                    styles[c] = sid

        is_current = y == buf.row
        line_bg = t.surface if is_current else None

        # gutter
        num = str(y + 1).rjust(digits)
        if is_current:
            segments.append(Segment(" ", Style(bgcolor=line_bg)))
            segments.append(Segment(num, Style(color=t.accent, bold=True, bgcolor=line_bg)))
            segments.append(Segment(" ", Style(bgcolor=line_bg)))
        else:
            segments.append(Segment(f" {num} ", Style(color=t.fg_dim, bgcolor=t.bg)))

        # text window (manual horizontal scroll)
        end = min(self.scroll_col + text_w, n_cells)
        used = 0
        for cell_idx in range(self.scroll_col, end):
            sid = styles[cell_idx]
            kind = kinds[cell_idx]
            ch = cells[cell_idx] if cell_idx < n_cells else " "
            segments.append(Segment(ch if ch else " ", self._cell_style(t, sid, kind, line_bg)))
            used += 1
        # pad remainder
        pad = view_w - gutter_w - used
        if pad > 0:
            segments.append(Segment(" " * pad, Style(bgcolor=line_bg if is_current else t.bg)))
        return Strip(segments)

    # ------------------------------------------------------------- welcome

    def _welcome_active(self) -> bool:
        """Show the VS Code-style welcome page for an empty unnamed buffer."""
        doc = self.yate.doc
        buf = self.buffer
        return (
            doc.path is None
            and not doc.modified
            and buf.line_count == 1
            and buf.lines[0] == ""
        )

    @staticmethod
    def _welcome_lines(
        t: theme.Theme,
    ) -> list[list[tuple[str, Optional[str], bool, bool]]]:
        """(text, color, bold, centered) tuples per welcome row."""
        rows: list[list[tuple[str, Optional[str], bool, bool]]] = [
            [],  # row 0: keep the cursor line blank
        ]
        for art in _WELCOME_BANNER:
            rows.append([(art, t.green, False, True)])
        rows.append([])
        rows.append([
            ("yate ", t.accent, True, True),
            (__version__, t.fg_bright, True, True),
        ])
        rows.append([("yet another terminal editor", t.fg_dim, False, True)])
        rows.append([])
        hints: list[tuple[str, str]] = [
            ("Ctrl+P", "quick open file"),
            ("Alt+Shift+P", "command palette"),
            (":", "ex command prompt (:w :q :e ...)"),
            ("Ctrl+F", "find in file"),
            ("Ctrl+S", "save file"),
            ("F1", "keyboard reference"),
        ]
        for kbd, desc in hints:
            rows.append([
                ("  " + kbd.ljust(15), t.green, True, False),
                (desc, t.fg_bright, False, False),
            ])
        rows.append([])
        rows.append([("  start typing to edit, or :e <path> to open a file",
                      t.fg_dim, False, False)])
        return rows

    def _render_welcome(
        self, y: int, view_w: int, gutter_w: int, t: theme.Theme
    ) -> Strip:
        """Render one welcome page row (gutter stays blank, no cursor)."""
        segments: list[Segment] = [Segment(" " * gutter_w, Style(bgcolor=t.bg))]
        rows = self._welcome_lines(t)
        used = gutter_w
        if y < len(rows):
            row = rows[y]
            if row and all(item[3] for item in row):
                text_w = sum(len(item[0]) for item in row)
                indent = max(0, (view_w - gutter_w - text_w) // 2)
                if indent:
                    segments.append(Segment(" " * indent, Style(bgcolor=t.bg)))
                    used += indent
            for text, color, bold, _centered in row:
                segments.append(Segment(text, Style(color=color, bold=bold, bgcolor=t.bg)))
                used += len(text)
        pad = view_w - used
        if pad > 0:
            segments.append(Segment(" " * pad, Style(bgcolor=t.bg)))
        return Strip(segments)

    def _row_style_ranges(self, row: int, line: str) -> list[tuple[int, int, int]]:
        buf = self.buffer
        tw = buf.tab_width
        ranges: list[tuple[int, int, int]] = []

        sel = buf.selection()
        if sel is not None:
            (r1, c1), (r2, c2) = sel
            cs: Optional[int] = None
            ce: Optional[int] = None
            if r1 < row < r2:
                cs, ce = 0, len(line)
            elif r1 == row == r2:
                cs, ce = c1, c2
            elif row == r1:
                cs, ce = c1, len(line)
            elif row == r2:
                cs, ce = 0, c2
            if cs is not None and ce is not None and ce > cs:
                start = theme.char_to_cell(line, cs, tw)
                end = theme.char_to_cell(line, ce, tw)
                ranges.append((start, end, S_SELECTION))

        search = self.yate.search
        if search.query:
            for i, match in enumerate(search.matches):
                if match.row != row:
                    continue
                sid = S_MATCH_ACTIVE if i == search.index else S_MATCH
                ranges.append((
                    theme.char_to_cell(line, match.start, tw),
                    theme.char_to_cell(line, match.end, tw),
                    sid,
                ))

        if row == buf.row:
            cell = theme.char_to_cell(line, buf.col, tw)
            ranges.append((cell, cell + 1, S_CURSOR))

        ranges.sort()
        return ranges

    @staticmethod
    def _cell_style(t: theme.Theme, sid: int, kind: Optional[str], line_bg: Optional[str]) -> Style:
        """Merge a syntax token kind with an overlay (selection/match/cursor)."""
        if sid == S_MATCH:
            return Style(bgcolor=t.match_bg, color=t.on_accent)
        if sid == S_MATCH_ACTIVE:
            return Style(bgcolor=t.match_active_bg, color=t.on_accent, bold=True)
        if sid == S_SELECTION:
            fg = t.syntax_color(kind) if kind is not None else t.fg
            return Style(bgcolor=t.selection_bg, color=fg)
        if sid == S_CURSOR:
            return Style(reverse=True, bold=True)
        if kind is not None:
            return t.syntax_style(kind, bgcolor=line_bg)
        return Style(color=t.fg, bgcolor=line_bg)
