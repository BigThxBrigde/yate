"""The main text editing widget (Textual widget, Rich segments)."""

from __future__ import annotations

import asyncio
from typing import Any, Callable, Optional, Protocol

from rich.segment import Segment
from rich.style import Style
from textual.events import Focus, Key, Resize
from textual.geometry import Size
from textual.scroll_view import ScrollView
from textual.strip import Strip
from textual.timer import Timer

from yate import __version__
from yate.editor_core.buffer import Pos, TextBuffer
from yate.editor_core.document import Document
from yate.editor_lsp import LspManager
from yate.editor_syntax import tokenize_document
from yate.editor_syntax.tokens import Token
from yate.keymaps.registry import KeymapSet
from yate.session import EditorSession, Leaf

from . import theme

# per-cell overlay ids (stacked on top of syntax foreground colors)
S_NORMAL = 0
S_MATCH = 1
S_SELECTION = 2
S_MATCH_ACTIVE = 3
S_CURSOR = 4

# Welcome-page banner: "YATE" in the ANSI Shadow figlet style
# (generated with https://patorjk.com/software/taag/, f=ANSI Shadow).
_WELCOME_BANNER = [
    "██╗   ██╗ █████╗ ████████╗███████╗",
    "╚██╗ ██╔╝██╔══██╗╚══██╔══╝██╔════╝",
    " ╚████╔╝ ███████║   ██║   █████╗",
    "  ╚██╔╝  ██╔══██║   ██║   ██╔══╝",
    "   ██║   ██║  ██║   ██║   ███████╗",
    "   ╚═╝   ╚═╝  ╚═╝   ╚═╝   ╚══════╝",
]


class PaneRegistry(Protocol):
    """The pane-manager lookups a view needs (implemented by ``PaneManager``).

    This is deliberately the only protocol of the widget layer: ``panes.py``
    imports :class:`EditorView` (it builds one view per leaf) while the view
    needs the manager's leaf lookups, so the consumer-owned interface lives
    here and both sides import this module.
    """

    @property
    def active_view(self) -> Optional[object]: ...

    def leaf_by_id(self, leaf_id: int) -> Leaf: ...

    def leaf_for(self, leaf_id: int) -> Optional[Leaf]: ...

    def notify_focus(self, leaf_id: int) -> None: ...


class EditorView(ScrollView):
    """Renders one pane's document: gutter, syntax, selection, matches, cursor.

    A pure renderer: it owns geometry, highlighting and the per-pane view
    state, and forwards every key to the editor (``handle_key``), which does
    the dispatch (keymap, completion, terminal, window chords).  Its
    collaborators are concrete -- the pane registry, the document session,
    the language servers and the keymap set.
    """

    can_focus = True

    # Trailing debounce window that merges rapid keystrokes into a single
    # background tokenize pass (same order of magnitude as the 0.12s
    # completion popup debounce).
    _HIGHLIGHT_DEBOUNCE_S = 0.08

    DEFAULT_CSS = """
    EditorView {
        padding: 0;
        overflow-x: hidden;
    }
    """

    def __init__(
        self,
        leaf_id: int,
        *,
        panes: PaneRegistry,
        session: EditorSession,
        lsp: LspManager,
        keymaps: KeymapSet,
        handle_key: Callable[[Key], bool],
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.leaf_id = leaf_id
        self.panes = panes
        self.session = session
        self.lsp = lsp
        self.keymaps = keymaps
        #: Runs the editor's key dispatch (keymap, completion, terminal, ...);
        #: returns True when the key was consumed.  Named apart from
        #: ``Widget.handle_key`` (Textual's own async hook).
        self.dispatch_key = handle_key
        self.scroll_col = 0
        # Syntax token cache. Tokens belong to (doc, content_version,
        # filetype); pure cursor/scroll movement leaves the version alone,
        # so moving through a file keeps its colors. After an edit the
        # previous tokens keep coloring the text for one debounce window
        # instead of flashing the whole view uncolored.
        self._hl_tokens: Optional[list[list[Token]]] = None
        self._hl_doc: object = None
        self._hl_version: int = -1
        self._hl_filetype: str = ""
        # Pending/in-flight highlight pass, keyed by (doc, filetype,
        # content_version). _hl_timer is set only while a debounced pass is
        # still waiting to start; the key survives until the worker stores
        # its result, so renders can never schedule a duplicate pass for a
        # version that is already being tokenized.
        self._hl_timer: Optional[Timer] = None
        self._hl_scheduled_key: Optional[tuple[object, str, int]] = None

    # ------------------------------------------------------------ helpers

    @property
    def leaf(self) -> Leaf:
        """The pane-tree leaf rendered by this view."""
        return self.panes.leaf_by_id(self.leaf_id)

    @property
    def doc(self) -> Document:
        """The document bound to this pane (may differ from the active doc)."""
        return self.leaf.doc

    @property
    def buffer(self) -> TextBuffer:
        """The buffer of this pane's document."""
        return self.leaf.doc.buffer

    @property
    def is_active_view(self) -> bool:
        """Whether this view is the currently focused pane."""
        return self.panes.active_view is self

    def _cursor_anchor(self) -> tuple[Pos, Optional[Pos]]:
        """Cursor/anchor to render: the live buffer for the active pane, the
        stored view state for inactive panes (independent cursors)."""
        buf = self.buffer
        if self.is_active_view:
            return buf.cursor, buf.anchor
        state = self.leaf.state_for(self.doc)
        return state.cursor, state.anchor

    def _selection(self) -> Optional[tuple[Pos, Pos]]:
        cursor, anchor = self._cursor_anchor()
        if anchor is None or anchor == cursor:
            return None
        return (min(anchor, cursor), max(anchor, cursor))

    def on_focus(self, _event: Focus) -> None:
        """Report pane activation to the pane manager."""
        self.panes.notify_focus(self.leaf_id)

    def content_changed(self) -> None:
        """Call after any buffer mutation / document switch / theme change.

        Geometry and repaint only: syntax tokens are invalidated lazily by
        the document's content version in :meth:`_tokens_for`, so this is
        cheap for keys that merely move the cursor or scroll the view.
        """
        self._update_virtual_size()
        self.reveal_cursor()
        self.refresh()

    def on_mount(self) -> None:
        """Apply the active theme background once mounted."""
        self.styles.background = theme.active().bg
        self.apply_scrollbar_theme()

    def apply_scrollbar_theme(self) -> None:
        """Paint the vertical scrollbar with active-theme colors.

        Textual draws the scrollbar itself; without explicit styling it keeps
        the framework defaults which clash with the Catppuccin palette. The
        colors are picked so the track nearly disappears and the thumb stays
        legible but unobtrusive.
        """
        t = theme.active()
        s = self.styles
        s.scrollbar_background = t.border
        s.scrollbar_background_hover = t.surface
        s.scrollbar_color = t.fg_dim
        s.scrollbar_color_hover = t.fg_muted
        s.scrollbar_color_active = t.accent

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
        """Forward the key to the editor's dispatcher while focused.

        The editor view is the end of the line for keyboard input: the event
        is stopped whether or not the key was consumed, so it never bubbles
        up to the application shell and gets dispatched a second time.
        """
        self.dispatch_key(event)
        event.stop()
        event.prevent_default()

    def reveal_cursor(self) -> None:
        buf = self.buffer
        row, col = self._cursor_anchor()[0]
        if not self.is_active_view:
            # the shared buffer may have shrunk since this pane's view state
            # was last captured -- clamp without mutating the stored state
            row = min(row, buf.line_count - 1)
            col = min(col, len(buf.lines[row]))
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

    def gutter_width(self) -> int:
        """Total gutter width: line number column + LSP diagnostic mark."""
        return max(3, len(str(self.buffer.line_count))) + 3

    def _gutter_w(self) -> int:
        return self.gutter_width()

    def _tokens_for(self, row: int) -> list[Token]:
        """Cached syntax tokens for one line (tokenized off the loop).

        The first render of a document shows plain text while a worker
        thread tokenizes it, then refreshes with colors; this keeps large
        files from blocking the first paint. The cache survives cursor
        movement and scrolling -- it is only stale when the document, its
        content version or its filetype differ. After an edit the previous
        tokens keep coloring the text for one debounce window (no plain
        flash); a doc/filetype switch never reuses the old tokens.
        """
        doc = self.doc
        buf = doc.buffer
        if (
            self._hl_tokens is None
            or self._hl_doc is not doc
            or self._hl_version != buf.content_version
            or self._hl_filetype != doc.filetype
        ):
            tokens = self._hl_tokens
            if tokens is None or self._hl_doc is not doc or self._hl_filetype != doc.filetype:
                self._schedule_highlight(0.0)
                return []
            # Same doc and filetype, version behind: keep coloring from the
            # previous tokens until the debounced pass replaces them (rows
            # past the end of the old tokens stay plain).
            self._schedule_highlight(self._HIGHLIGHT_DEBOUNCE_S)
            return tokens[row] if row < len(tokens) else []
        return self._hl_tokens[row] if row < len(self._hl_tokens) else []

    def _schedule_highlight(self, delay: float) -> None:
        """Arrange a tokenize pass for the current doc/filetype/version.

        Keyed by (doc, filetype, content_version): repeated calls for the
        same state keep the existing timer or in-flight worker, only a new
        edit restarts the trailing debounce window.
        """
        doc = self.doc
        key = (doc, doc.filetype, doc.buffer.content_version)
        if self._hl_scheduled_key == key:
            return
        if self._hl_timer is not None:
            self._hl_timer.stop()
            self._hl_timer = None
        self._hl_scheduled_key = key
        if delay > 0.0:
            self._hl_timer = self.set_timer(
                delay, self._launch_highlight, name="highlight-debounce"
            )
        else:
            # No grace period (first paint / doc or filetype switch): start
            # tokenizing right away so the first paint gets colored ASAP.
            self._launch_highlight()

    def _launch_highlight(self) -> None:
        """Timer callback: hand the pending pass to the tokenizer worker.

        Deliberately does not clear ``_hl_timer``: a stopped timer's
        already-queued callback can still fire after a newer timer was
        scheduled, and clobbering the reference here would lose the newer
        pending timer. A fired timer is inert (``stop()`` is a no-op), and
        duplicate passes are prevented by the scheduled-key guard plus the
        exclusive worker group.
        """
        if not self.is_mounted:
            return
        # Keyed to *this* widget (not the app) so concurrent panes do
        # not cancel each other's highlight passes.
        self.run_worker(
            self._highlight_later(), group="highlight",
            exclusive=True, exit_on_error=False,
        )

    async def _highlight_later(self) -> None:
        """Tokenize the current document in a thread, then repaint."""
        doc = self.doc
        buf = doc.buffer
        # shallow copy: the buffer may keep mutating while the thread runs
        lines = list(buf.lines)
        filetype = doc.filetype
        version = buf.content_version
        tokens = await asyncio.to_thread(
            tokenize_document, lines, filetype
        )
        if not self.is_mounted:
            return
        # discard the result if the document changed/closed while we worked;
        # a repaint reschedules a fresh pass for the current state
        if self.doc is not doc or buf.content_version != version:
            self.refresh()
            return
        self._hl_tokens = tokens
        self._hl_doc = doc
        self._hl_version = version
        self._hl_filetype = filetype
        if self._hl_scheduled_key == (doc, filetype, version):
            self._hl_scheduled_key = None
        self.refresh()

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
        view_w = self.size.width or 80
        # Textual may schedule one final compositor render for an EditorView
        # whose leaf was already dropped by a structural reconcile (``:only``)
        # or app teardown -- between ``self.root`` being replaced and the old
        # widget actually unmounting, a timer tick can still reach
        # render_line. The pane tree no longer holds this leaf, so paint a
        # blank strip instead of tripping the leaf-lookup assertion.
        if self.panes.leaf_for(self.leaf_id) is None:
            return Strip([Segment(" " * view_w, Style(bgcolor=t.bg))])
        buf = self.buffer
        gutter_w = self._gutter_w()
        text_w = max(1, view_w - gutter_w)

        digits = gutter_w - 3
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
        cursor_row, cursor_col = self._cursor_anchor()[0]
        cells: list[str] = []
        for ch in line:
            theme.expand_char(ch, cells, buf.tab_width)
        if y == cursor_row and cursor_col == len(line):
            cells.append(" ")  # block cursor at end of line

        n_cells = len(cells)
        styles = [S_NORMAL] * (n_cells + 1)
        kinds = self._syntax_kinds(y, line, n_cells + 1)
        underlines = self._diagnostic_underlines(y, line, n_cells + 1)

        for start, end, sid in self._row_style_ranges(y, line):
            for c in range(max(0, start), min(end, n_cells + 1)):
                if sid > styles[c]:
                    styles[c] = sid

        is_current = y == cursor_row
        line_bg = t.surface if is_current else None

        # gutter
        line_diags = self.lsp.diagnostics_on_line(self.doc, y)
        line_error = any(d.is_error for d in line_diags)
        line_warn = any(d.is_warning for d in line_diags)
        if line_error:
            num_color, mark = t.red, "✖"
        elif line_warn:
            num_color, mark = t.yellow, "▲"
        else:
            mark = " "
            num_color = t.accent if is_current else t.fg_dim
        num = str(y + 1).rjust(digits)
        num_style = Style(
            color=num_color, bold=is_current, bgcolor=line_bg or t.bg,
        )
        mark_style = Style(
            color=t.red if line_error else (t.yellow if line_warn else num_color),
            bgcolor=line_bg or t.bg, bold=True,
        )
        segments.append(Segment(" ", Style(bgcolor=line_bg or t.bg)))
        segments.append(Segment(num, num_style))
        segments.append(Segment(" ", Style(bgcolor=line_bg or t.bg)))
        segments.append(Segment(mark, mark_style))

        # text window (manual horizontal scroll)
        end = min(self.scroll_col + text_w, n_cells)
        used = 0
        for cell_idx in range(self.scroll_col, end):
            sid = styles[cell_idx]
            kind = kinds[cell_idx]
            ch = cells[cell_idx] if cell_idx < n_cells else " "
            style = self._cell_style(t, sid, kind, line_bg)
            if underlines[cell_idx] and sid != S_CURSOR:
                style += Style(underline=True)
            if ch:
                # an empty cell is the second column of a wide glyph
                # (expand_char): Rich already advanced 2 cells for the
                # glyph itself, so emitting a space here would add a
                # visible blank after every CJK/fullwidth character.
                # The one exception is a wide glyph clipped by horizontal
                # scroll at its first half: draw a blank replacement cell.
                segments.append(Segment(ch, style))
            elif cell_idx == self.scroll_col and cell_idx > 0:
                segments.append(Segment(" ", style))
            used += 1
        # pad remainder
        pad = view_w - gutter_w - used
        if pad > 0:
            segments.append(Segment(" " * pad, Style(bgcolor=line_bg if is_current else t.bg)))
        return Strip(segments)

    # ------------------------------------------------------------- welcome

    def _welcome_active(self) -> bool:
        """Show the VS Code-style welcome page for an empty unnamed buffer.

        Besides the pristine-buffer condition the session-level
        ``welcome_visible`` flag must be set: it is on at startup only and is
        dismissed once the user creates a new buffer (``:enew``); ``:welcome``
        turns it back on.
        """
        doc = self.doc
        buf = self.buffer
        return (
            self.session.welcome_visible
            and doc.path is None
            and not doc.modified
            and buf.line_count == 1
            and buf.lines[0] == ""
        )

    @staticmethod
    def _welcome_lines(
        t: theme.Theme,
        *,
        vim_keys: bool = False,
    ) -> list[list[tuple[str, Optional[str], bool, bool]]]:
        """(text, color, bold, centered) tuples per welcome row."""
        rows: list[list[tuple[str, Optional[str], bool, bool]]] = [
            [],  # row 0: keep the cursor line blank
        ]
        # pad all banner lines to the same width so the per-line centering
        # below keeps the figlet block aligned (trailing spaces were trimmed
        # from the generator output, which would otherwise shift short lines)
        banner_w = max(len(art) for art in _WELCOME_BANNER)
        for art in _WELCOME_BANNER:
            rows.append([(art.ljust(banner_w), t.green, False, True)])
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
        ]
        if vim_keys:
            # The ex command prompt (":") exists in vim mode only; in vsc
            # mode ":" is an ordinary character typed into the buffer.
            hints.append((":", "ex command prompt (:w :q :e ...)"))
        hints.extend([
            ("Ctrl+F", "find in file"),
            ("Ctrl+`", "integrated terminal"),
            ("Ctrl+S", "save file"),
            ("F1", "keyboard reference"),
        ])
        for kbd, desc in hints:
            rows.append([
                ("  " + kbd.ljust(15), t.green, True, False),
                (desc, t.fg_bright, False, False),
            ])
        rows.append([])
        footer = (
            "  start typing to edit, or :e <path> to open a file"
            if vim_keys
            else "  start typing to edit; Alt+Shift+P opens the command palette"
        )
        rows.append([(footer, t.fg_dim, False, False)])
        return rows

    def _render_welcome(
        self, y: int, view_w: int, gutter_w: int, t: theme.Theme
    ) -> Strip:
        """Render one welcome page row (gutter stays blank, no cursor)."""
        segments: list[Segment] = [Segment(" " * gutter_w, Style(bgcolor=t.bg))]
        rows = self._welcome_lines(
            t, vim_keys=self.keymaps.name == "vim"
        )
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

    def _diagnostic_underlines(
        self, row: int, line: str, cell_count: int
    ) -> list[bool]:
        """Per-cell underline flags contributed by LSP diagnostics on *row*."""
        flags = [False] * cell_count
        tw = self.buffer.tab_width
        for d in self.lsp.diagnostics_on_line(self.doc, row):
            if d.start_row == d.end_row:
                cs, ce = d.start_col, d.end_col
            elif row == d.start_row:
                cs, ce = d.start_col, len(line)
            elif row == d.end_row:
                cs, ce = 0, d.end_col
            else:
                cs, ce = 0, len(line)
            start = theme.char_to_cell(line, max(0, min(cs, len(line))), tw)
            finish = theme.char_to_cell(line, max(0, min(ce, len(line))), tw)
            for c in range(max(0, start), min(finish, cell_count)):
                flags[c] = True
        return flags

    def _row_style_ranges(self, row: int, line: str) -> list[tuple[int, int, int]]:
        buf = self.buffer
        tw = buf.tab_width
        cursor_row, cursor_col = self._cursor_anchor()[0]
        ranges: list[tuple[int, int, int]] = []

        sel = self._selection()
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

        # Search state belongs to the active document; other panes showing
        # the same file would otherwise paint matches on wrong rows anyway.
        search = self.session.search
        if search.query and self.doc is self.session.doc:
            for i, match in enumerate(search.matches):
                if match.row != row:
                    continue
                sid = S_MATCH_ACTIVE if i == search.index else S_MATCH
                ranges.append((
                    theme.char_to_cell(line, match.start, tw),
                    theme.char_to_cell(line, match.end, tw),
                    sid,
                ))

        if row == cursor_row:
            cell = theme.char_to_cell(line, cursor_col, tw)
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
            # explicit base bg keeps reverse video inside the theme palette
            # (None would swap with the terminal's own background)
            return Style(reverse=True, bold=True, bgcolor=t.bg)
        if kind is not None:
            # always fill with an explicit theme color: a None bgcolor would
            # let the terminal's own background bleed through, which clashes
            # with the gutter/padding painted in theme.bg when the terminal
            # profile uses a different background color
            return t.syntax_style(kind, bgcolor=line_bg or t.bg)
        return Style(color=t.fg, bgcolor=line_bg or t.bg)
