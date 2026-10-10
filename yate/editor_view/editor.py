"""The main text editing widget (Textual widget, Rich segments)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, override, Protocol

from rich.segment import Segment
from rich.style import Style
from textual.events import (
    Click,
    Focus,
    Key,
    MouseDown,
    MouseMove,
    MouseEvent,
    MouseUp,
    Resize,
)
from textual.geometry import Size
from textual.scroll_view import ScrollView
from textual.strip import Strip

from yate.editor_core.buffer import Pos, TextBuffer
from yate.editor_core.document import Document
from yate.editor_core.search import Match, SearchEngine
from yate.editor_lsp import Diagnostic
from yate.editor_lsp.manager import LspManager
from yate.keymaps.registry import KeymapSet
from yate.paths import load_tcss
from yate.session import EditorSession, Leaf

from . import theme
from .highlighting import HighlightMixin
from .scrollbars import apply_scrollbar_theme, apply_slim_scrollbars
from .welcome import _WelcomeRow, render_welcome_row, welcome_rows

#: Textual mouse button index for the primary (left) button, shared by the
#: mouse-aware views in this package and the L3 mouse dispatch.
LEFT_BUTTON: int = 1

# per-cell overlay ids (stacked on top of syntax foreground colors)
S_NORMAL: int = 0
S_MATCH: int = 1
S_SELECTION: int = 2
S_MATCH_ACTIVE: int = 3
S_CURSOR: int = 4


class PaneRegistry(Protocol):
    """The pane-manager lookups a view needs (implemented by ``PaneManager``).

    This is deliberately the only protocol of the widget layer: ``panes.py``
    imports :class:`EditorView` (it builds one view per leaf) while the view
    needs the manager's leaf lookups, so the consumer-owned interface lives
    here and both sides import this module.
    """

    @property
    def active_view(self) -> object | None:
        """The active pane's mounted view, or ``None`` before it is built."""

    def leaf_by_id(self, leaf_id: int) -> Leaf:
        """Return the pane-tree leaf with *leaf_id*; it must still exist."""
        ...

    def leaf_for(self, leaf_id: int) -> Leaf | None:
        """Return the leaf with *leaf_id*, or ``None`` when it left the tree."""

    def notify_focus(self, leaf_id: int) -> None:
        """EditorView focus hook: switch the active pane to *leaf_id*."""


class EditorView(ScrollView, HighlightMixin):
    """Renders one pane's document: gutter, syntax, selection, matches, cursor.

    A pure renderer: it owns geometry, highlighting and the per-pane view
    state, and forwards every key to the editor (``handle_key``), which does
    the dispatch (keymap, completion, terminal, window chords).  Its
    collaborators are concrete -- the pane registry, the document session,
    the language servers and the keymap set.
    """

    can_focus = True

    #: unsubscribe hook from :func:`yate.editor_view.theme.subscribe`;
    #: ``None`` while not mounted.
    _theme_unsubscribe: theme.Unsubscribe | None = None

    DEFAULT_CSS = load_tcss("editor-view.tcss")

    def __init__(
        self,
        leaf_id: int,
        *,
        panes: PaneRegistry,
        session: EditorSession,
        lsp: LspManager,
        keymaps: KeymapSet,
        handle_key: Callable[[Key], bool],
        handle_mouse: Callable[[MouseEvent], bool] | None = None,
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
        #: Mouse analogue of ``dispatch_key``: runs the editor's mouse
        #: dispatch (cursor moves, drag & click-chain selection); returns
        #: True when the event was consumed.  ``None`` = no mouse handling
        #: (headless / legacy tests construct the view without it).
        self.handle_mouse = handle_mouse
        self.scroll_col = 0
        self._init_highlight_state()
        # Welcome rows cached by (theme name, vim_keys): the rows embed
        # theme colors and keymap-dependent hints, so a theme or keymap
        # switch changes the key and forces a rebuild. The welcome page
        # re-renders every frame while visible, which used to rebuild the
        # rows each time.
        self._welcome_cache: dict[tuple[str, bool], list[_WelcomeRow]] = {}

    # ------------------------------------------------------------ helpers

    @property
    def leaf(self) -> Leaf:
        """The pane-tree leaf rendered by this view."""
        return self.panes.leaf_by_id(self.leaf_id)

    @property
    @override
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

    def _cursor_anchor(self) -> tuple[Pos, Pos | None]:
        """Cursor/anchor to render: the live buffer for the active pane, the
        stored view state for inactive panes (independent cursors)."""
        buf = self.buffer
        if self.is_active_view:
            return buf.cursor, buf.anchor
        state = self.leaf.state_for(self.doc)
        return state.cursor, state.anchor

    def _selection(
        self, cursor: Pos, anchor: Pos | None
    ) -> tuple[Pos, Pos] | None:
        """Normalized (start, end) pair between *cursor* and *anchor*."""
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

    @override
    def on_mount(self) -> None:
        """Apply the active theme and register for theme-change updates."""
        # ScrollView.on_mount refreshes scrollbar visibility; skipping it
        # would defer the initial show/hide decision to the first resize.
        super().on_mount()
        apply_slim_scrollbars(self)
        self._apply_theme()
        theme.attach(self, self._apply_theme)

    def on_unmount(self) -> None:
        """Detach from the theme broadcast (widgets own their painting)."""
        theme.detach(self)

    def _apply_theme(self) -> None:
        """Paint this view with the active theme (bg + scrollbar palette)."""
        self.styles.background = theme.active().bg
        apply_scrollbar_theme(self)
        self.content_changed()

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

    def buffer_pos_from_mouse(self, event: MouseEvent) -> Pos | None:
        """Map a mouse event over this view to a clamped buffer position.

        Same geometry the renderer uses in reverse: the widget-relative y is
        translated by the scroll offset, the x by the gutter width and the
        manual horizontal scroll, then ``cell_to_char`` resolves the character
        column (tab / wide-glyph aware).  Gutter clicks clamp to column 0.
        ``None`` for an empty buffer.
        """
        buf = self.buffer
        if buf.line_count == 0:
            return None
        row = max(0, min(event.y + self.scroll_offset.y, buf.line_count - 1))
        cell = event.x - self._gutter_w() + self.scroll_col
        col = theme.cell_to_char(buf.lines[row], max(0, cell), buf.tab_width)
        return (row, col)

    def _is_pane_border(self, event: MouseEvent) -> bool:
        """True when the press lands on this view's pane-separator border
        (plan-b contract: the border cell belongs to PaneHost's drag)."""
        # Widget.classes is a frozenset: membership is exact-token, no
        # substring collisions (verified on Textual 8.2.8).
        return (
            ("pane-sep-v" in self.classes and event.x >= self.size.width - 1)
            or ("pane-sep-h" in self.classes and event.y >= self.size.height - 1)
        )

    def _forward_mouse(self, event: MouseEvent) -> None:
        """R10 analogue: stop only the events the dispatcher consumed."""
        if self.handle_mouse is not None and self.handle_mouse(event):
            event.stop()
            event.prevent_default()

    def on_mouse_down(self, event: MouseDown) -> None:
        if self._is_pane_border(event):
            return  # bubbles to PaneHost: separator drag owns this cell
        if event.button == LEFT_BUTTON:
            self.focus()  # on_focus -> notify_focus activates the pane
            if self.handle_mouse is not None and self.handle_mouse(event):
                self.capture_mouse()  # drags continue outside the bounds
                event.stop()
                event.prevent_default()
            # unconsumed: a bare return lets the MouseDown bubble to PaneHost
            # (MouseDown bubble=True, Textual 8.2.8) -- _forward_mouse here
            # would re-dispatch the same event to MouseFlows a second time
            return
        self._forward_mouse(event)

    def on_mouse_move(self, event: MouseMove) -> None:
        self._forward_mouse(event)

    def on_mouse_up(self, event: MouseUp) -> None:
        if event.button == LEFT_BUTTON:
            self.release_mouse()  # chording: other buttons keep the capture
        self._forward_mouse(event)

    def on_click(self, event: Click) -> None:
        """Double/triple click arrive as Click events with chain >= 2."""
        self._forward_mouse(event)

    def reveal_cursor(self) -> None:
        """Scroll the view so the cursor stays inside the visible area."""
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
        """Rows per full page (or half page when *half* is set)."""
        return max(1, ((self.size.height or 20) // 2) if half else (self.size.height or 20))

    def gutter_width(self) -> int:
        """Total gutter width: line number column + LSP diagnostic mark."""
        return max(3, len(str(self.buffer.line_count))) + 3

    def _gutter_w(self) -> int:
        return self.gutter_width()

    def _syntax_kinds(self, row: int, line: str, cell_count: int) -> list[str | None]:
        """Per-cell syntax token kind (char ranges mapped to display cells)."""
        tw = self.buffer.tab_width
        kinds: list[str | None] = [None] * cell_count
        for tok in self._tokens_for(row):
            cs = theme.char_to_cell(line, tok.start, tw)
            ce = theme.char_to_cell(line, tok.end, tw)
            for c in range(max(0, cs), min(ce, cell_count)):
                kinds[c] = tok.kind
        return kinds

    # -------------------------------------------------------------- render

    @override
    def render_line(self, y: int) -> Strip:
        """Render one visible row (welcome page, gutter, syntax, selection, cursor)."""
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

        def fill_line(bg: str | None) -> None:
            segments.append(Segment(" " * view_w, Style(bgcolor=bg)))

        if self._welcome_active():
            return render_welcome_row(
                y, view_w, gutter_w, t,
                vim_keys=self.keymaps.name == "vim",
                cache=self._welcome_cache,
            )

        # Textual hands us the row relative to the visible widget region;
        # translate it into a buffer row via the scroll offset.
        y += self.scroll_offset.y
        if y >= buf.line_count:
            fill_line(t.bg)
            return Strip(segments)

        line = buf.lines[y]
        # one cursor/anchor lookup and one diagnostics lookup per rendered
        # row: both used to be repeated per consumer (3x pane-tree walks and
        # 2x full diagnostic scans per row) and are now computed once here
        # and passed down to the gutter, underline and style passes
        cursor, anchor = self._cursor_anchor()
        cursor_row, cursor_col = cursor
        cells: list[str] = []
        for ch in line:
            theme.expand_char(ch, cells, buf.tab_width)
        if y == cursor_row and cursor_col == len(line):
            cells.append(" ")  # block cursor at end of line
        # extra multi-cursor points need the same padding: a point resting
        # on (y, len(line)) must own one visible block cell (issue IKKJHH)
        for point in buf.extra_cursors:
            if point[0] == y and point[1] == len(line):
                cells.append(" ")
                break

        n_cells = len(cells)
        styles = [S_NORMAL] * (n_cells + 1)
        kinds = self._syntax_kinds(y, line, n_cells + 1)
        line_diags = self.lsp.diagnostics_on_line(self.doc, y)
        underlines = self._diagnostic_underlines(y, line, n_cells + 1, line_diags)

        for start, end, sid in self._row_style_ranges(y, line, cursor, anchor):
            for c in range(max(0, start), min(end, n_cells + 1)):
                if sid > styles[c]:
                    styles[c] = sid

        is_current = y == cursor_row
        line_bg = t.surface if is_current else None

        # gutter
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

    def _welcome_lines(
        self, t: theme.Theme, *, vim_keys: bool = False
    ) -> list[_WelcomeRow]:
        """Thin delegate to :func:`yate.editor_view.welcome.welcome_rows`.

        Kept as a method so the frozen test surface
        (:meth:`tests.test_app_render` welcome-cache assertions) keeps
        calling the widget; the cache dict object is this view's
        ``_welcome_cache``, so the identity semantics are unchanged.
        """
        return welcome_rows(t, vim_keys=vim_keys, cache=self._welcome_cache)

    def _diagnostic_underlines(
        self, row: int, line: str, cell_count: int, diags: list[Diagnostic]
    ) -> list[bool]:
        """Per-cell underline flags contributed by *diags* on *row*.

        *diags* is the row's diagnostics as looked up once by the caller
        (:meth:`render_line` shares one lookup between this pass and the
        gutter marks).
        """
        flags = [False] * cell_count
        tw = self.buffer.tab_width
        for d in diags:
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

    def _row_style_ranges(
        self, row: int, line: str, cursor: Pos, anchor: Pos | None
    ) -> list[tuple[int, int, int]]:
        """Overlay style ranges (selection / matches / cursor) for *row*.

        *cursor* / *anchor* are the pane's cursor and anchor as looked up
        once by the caller (:meth:`render_line` shares one pane-tree walk
        between this pass and the cursor painting).
        """
        buf = self.buffer
        tw = buf.tab_width
        cursor_row, cursor_col = cursor
        ranges: list[tuple[int, int, int]] = []

        sel = self._selection(cursor, anchor)
        if sel is not None:
            (r1, c1), (r2, c2) = sel
            cs: int | None = None
            ce: int | None = None
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
            for i, match in self._matches_for_row(row, search):
                sid = S_MATCH_ACTIVE if i == search.index else S_MATCH
                ranges.append((
                    theme.char_to_cell(line, match.start, tw),
                    theme.char_to_cell(line, match.end, tw),
                    sid,
                ))

        if row == cursor_row:
            cell = theme.char_to_cell(line, cursor_col, tw)
            ranges.append((cell, cell + 1, S_CURSOR))

        # extra multi-cursor points paint their own block cursor on this
        # row; S_CURSOR is the highest overlay id, so the existing max
        # merge above wins over selection/match overlaps (issue IKKJHH)
        for point in buf.extra_cursors:
            if point[0] == row:
                cell = theme.char_to_cell(line, point[1], tw)
                ranges.append((cell, cell + 1, S_CURSOR))

        ranges.sort()
        return ranges

    def _matches_for_row(
        self, row: int, search: SearchEngine
    ) -> list[tuple[int, Match]]:
        """The search matches on *row*, from a per-row bucket cache.

        ``render_line`` asks for matches once per visible row per frame;
        scanning the full match list for every row is O(visible x total
        matches).  The buckets are rebuilt only when the match list object
        changes (:meth:`SearchEngine.update` assigns a fresh list), so an
        incremental-search keystroke pays one O(matches) pass per repaint.
        """
        cached = self._match_buckets
        if cached is None or cached[0] is not search.matches:
            buckets: dict[int, list[tuple[int, Match]]] = {}
            for i, match in enumerate(search.matches):
                buckets.setdefault(match.row, []).append((i, match))
            cached = (search.matches, buckets)
            self._match_buckets = cached
        return cached[1].get(row, [])

    @staticmethod
    def _cell_style(t: theme.Theme, sid: int, kind: str | None, line_bg: str | None) -> Style:
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
