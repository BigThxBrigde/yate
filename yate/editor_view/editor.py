"""The main text editing widget (Textual widget, Rich segments)."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
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
from textual.timer import Timer

from yate import __version__
from yate.editor_core.buffer import Pos, TextBuffer
from yate.editor_core.document import Document
from yate.editor_core.search import Match, SearchEngine
from yate.editor_lsp import Diagnostic
from yate.editor_lsp.manager import LspManager
from yate.editor_syntax.engine import tokenize_document_with_states
from yate.editor_syntax.engine import tokenize_line_sync
from yate.editor_syntax.tokens import Token
from yate.keymaps.registry import KeymapSet
from yate.logs import tracing
from yate.paths import load_tcss
from yate.session import EditorSession, Leaf

from . import theme
from .scrollbars import apply_scrollbar_theme, apply_slim_scrollbars

log = tracing.get_logger(__name__)

#: Textual mouse button index for the primary (left) button, shared by the
#: mouse-aware views in this package and the L3 mouse dispatch.
LEFT_BUTTON: int = 1

# per-cell overlay ids (stacked on top of syntax foreground colors)
S_NORMAL: int = 0
S_MATCH: int = 1
S_SELECTION: int = 2
S_MATCH_ACTIVE: int = 3
S_CURSOR: int = 4

# Welcome-page banner: "YATE" in the ANSI Shadow figlet style
# (generated with https://patorjk.com/software/taag/, f=ANSI Shadow).
_WELCOME_BANNER: list[str] = [
    "██╗   ██╗ █████╗ ████████╗███████╗",
    "╚██╗ ██╔╝██╔══██╗╚══██╔══╝██╔════╝",
    " ╚████╔╝ ███████║   ██║   █████╗",
    "  ╚██╔╝  ██╔══██║   ██║   ██╔══╝",
    "   ██║   ██║  ██║   ██║   ███████╗",
    "   ╚═╝   ╚═╝  ╚═╝   ╚═╝   ╚══════╝",
]

#: One welcome-page row: (text, color, bold, centered) cell tuples.
_WelcomeRow = list[tuple[str, str | None, bool, bool]]


def _tokenize_with_states(
    lines: list[str], filetype: str
) -> tuple[list[list[Token]], tuple[int, ...]]:
    """Tokenize a whole document plus the regex multiline state per row.

    Runs inside the highlight worker thread.  The states are what
    :meth:`EditorView._rebuild_tokens_on_edit` resumes from after an
    edit -- they are intentionally regex-native even when the tokens came
    from tree-sitter, because the row-level resync re-tokenizes with the
    regex backend.  With the regex backend the combined engine pass
    produces both artifacts in one scan; the tree-sitter path threads the
    states in a guarded regex companion pass (a broken custom LangSpec
    keeps prior states instead of killing the worker pass).
    """
    return tokenize_document_with_states(lines, filetype)


@dataclass(frozen=True)
class HighlightProbe:
    """Read-only snapshot of the syntax-highlight cache (tests/debugging).

    Mirrors the private ``_hl_*`` attributes of :class:`EditorView` so tests
    and tools can assert highlighter state without reaching into privates;
    as a frozen record it offers no way to mutate the widget.
    """

    #: Cached tokens per buffer row (``None`` until the first pass lands).
    tokens: list[list[Token]] | None
    #: Document the cached tokens belong to (``None`` until the first pass).
    doc: Document | None
    #: Buffer content version the cached tokens were tokenized at.
    version: int
    #: Filetype the cached tokens were tokenized for.
    filetype: str
    #: (doc, filetype, version) of the pass waiting to run / in flight.
    scheduled_key: tuple[object, str, int] | None
    #: Debounce timer reference (``None`` when nothing is deferred).
    timer: Timer | None


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


class EditorView(ScrollView):
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

    # Trailing debounce window that merges rapid keystrokes into a single
    # background tokenize pass (same order of magnitude as the 0.12s
    # completion popup debounce).
    _HIGHLIGHT_DEBOUNCE_S = 0.08

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
        # Syntax token cache. Tokens belong to (doc, content_version,
        # filetype); pure cursor/scroll movement leaves the version alone,
        # so moving through a file keeps its colors. After an edit the
        # previous tokens keep coloring the text for one debounce window
        # instead of flashing the whole view uncolored.
        # Search-match buckets for the render path (see _matches_for_row):
        # keyed on the matches *list object* identity, which SearchEngine
        # replaces wholesale on every update.
        self._match_buckets: tuple[
            list[Match], dict[int, list[tuple[int, Match]]]
        ] | None = None
        self._hl_tokens: list[list[Token]] | None = None
        self._hl_doc: Document | None = None
        self._hl_version: int = -1
        self._hl_filetype: str = ""
        # Per-row text snapshot + regex multiline state sequence, written
        # together with every _hl_tokens assignment (single-writer
        # discipline): _rebuild_tokens_on_edit diffs the current lines
        # against the snapshot to reuse unchanged rows and resumes the
        # multiline state machine at the first changed row.
        self._hl_line_snapshot: tuple[str, ...] | None = None
        self._hl_ml_states: tuple[int, ...] | None = None
        # Pending/in-flight highlight pass, keyed by (doc, filetype,
        # content_version). _hl_timer is set only while a debounced pass is
        # still waiting to start; the key survives until the worker stores
        # its result, so renders can never schedule a duplicate pass for a
        # version that is already being tokenized.
        self._hl_timer: Timer | None = None
        self._hl_scheduled_key: tuple[object, str, int] | None = None
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

    def _tokens_for(self, row: int) -> list[Token]:
        """Cached syntax tokens for one line (tokenized off the loop).

        The first render of a document shows plain text while a worker
        thread tokenizes it, then refreshes with colors; this keeps large
        files from blocking the first paint. The cache survives cursor
        movement and scrolling -- it is only stale when the document, its
        content version or its filetype differ. After an edit the previous
        tokens keep coloring the text for one debounce window (no plain
        flash) while :meth:`_rebuild_tokens_on_edit` resyncs the edited
        rows synchronously; a doc/filetype switch never reuses the old
        tokens.
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
                # First paint or doc/filetype switch: drop any row snapshot
                # carried over from the previous document before the fresh
                # pass replaces the cache.
                self._hl_line_snapshot = None
                self._hl_ml_states = None
                self._schedule_highlight(0.0)
                return []
            # Same doc and filetype, version behind: keep coloring from the
            # previous tokens until the debounced pass replaces them, and
            # resync the edited rows on the spot so token boundaries match
            # the current text during the wait.
            self._schedule_highlight(self._HIGHLIGHT_DEBOUNCE_S)
            return self._rebuild_tokens_on_edit(row)
        return self._hl_tokens[row] if row < len(self._hl_tokens) else []

    def _rebuild_tokens_on_edit(self, row: int) -> list[Token]:
        """Resync edited rows synchronously while the worker pass pends.

        The stale tokens returned during the debounce window are computed
        from the pre-edit text, so every token ending at or past the edit
        point colors the newly typed characters with a shifted boundary --
        the end-of-line flicker. This diffs the current lines against the
        row snapshot left by the last finished pass and re-tokenizes only
        the changed rows (plus rows whose multiline state they carry) with
        the microsecond-fast regex backend; unchanged rows reuse the cached
        tokens verbatim. The rebuilt cache is written back together with
        fresh snapshots (same write site as the worker's, keeping the
        single-writer discipline), so later renders of the same version skip
        the diff and the debounced worker still replaces everything with
        exact tokens.

        Reuse is per row and shift-aware: new row r maps to cache row
        j = r - delta (delta = line-count change), and whenever the row
        text is unchanged and the threaded multiline state equals the state
        the cached tokens were built from, the cached tokens are reused
        verbatim (O(1) per row) -- so a line-inserting edit only pays real
        tokenization for rows whose text or surrounding construct actually
        changed, and rows below an inserted blank line reuse instantly
        instead of re-tokenizing to end of file. Without a usable
        snapshot, or when the line count shifted drastically (> 5 rows),
        this degrades to plain stale reuse.
        """
        tokens = self._hl_tokens
        snapshot = self._hl_line_snapshot
        ml_states = self._hl_ml_states
        doc = self.doc
        buf = doc.buffer
        if tokens is None:
            return []
        if (
            snapshot is None
            or ml_states is None
            or abs(len(snapshot) - buf.line_count) > 5
        ):
            # No usable snapshot (startup / doc switch) or a drastic line
            # count change: plain stale reuse until the worker replaces the
            # cache (rows past the end of the old tokens stay plain).
            return tokens[row] if row < len(tokens) else []

        lines = buf.lines
        cur_count = buf.line_count
        common = min(len(snapshot), cur_count)
        changed = {i for i in range(common) if snapshot[i] != lines[i]}
        changed.update(range(common, cur_count))
        if not changed:
            # Version bumped without any line changing (out-of-band mark):
            # the cached tokens still match the text exactly, so record the
            # version here too -- without this the version-staleness check
            # in :meth:`_tokens_for` would re-run the O(lines) diff on
            # every render until the worker replaces the cache.
            self._hl_version = buf.content_version
            return tokens[row] if row < len(tokens) else []

        first = min(changed)
        delta = cur_count - len(snapshot)
        # Rows above the first change are identical to the snapshot, so the
        # multiline state entering the changed region carries over verbatim.
        state = ml_states[first - 1] if 0 < first <= len(ml_states) else 0
        rebuilt: list[list[Token]] = list(tokens[:first])
        states: list[int] = list(ml_states[:first])
        r = first
        while r < cur_count:
            # Shift-aware cache row: below the edited region, new row r
            # holds old row r - delta's text (mismatches fall through to a
            # fresh tokenization, so a wrong mapping can only cost work).
            j = r - delta
            if (
                0 <= j < len(tokens)
                and lines[r] == snapshot[j]
                and state == (ml_states[j - 1] if j > 0 else 0)
            ):
                # Text unchanged and the threaded state matches the state the
                # cached tokens were built from: reuse them verbatim and jump
                # to the recorded next state -- O(1) per row, which keeps
                # line-inserting edits cheap on large files.
                state = ml_states[j]
                rebuilt.append(tokens[j])
                states.append(state)
                r += 1
                continue
            try:
                row_tokens, state = tokenize_line_sync(
                    lines[r], doc.filetype, state
                )
            except Exception:  # noqa: BLE001 - the render path must never
                # crash on a broken custom LangSpec; the row falls back to
                # its stale tokens and the carried state stays unchanged
                log.debug("sync retokenize failed on row %d", r)
                row_tokens = tokens[r] if r < len(tokens) else []
            rebuilt.append(row_tokens)
            states.append(state)
            r += 1

        self._hl_tokens = rebuilt
        self._hl_version = buf.content_version
        self._hl_line_snapshot = tuple(lines)
        self._hl_ml_states = tuple(states)
        return rebuilt[row] if row < len(rebuilt) else []

    def tokens_for(self, row: int) -> list[Token]:
        """Public accessor for one row's syntax tokens (render-path lookup).

        The same lookup the renderer performs for every row; it may schedule
        a background tokenize pass when the cache is stale, so calling it
        outside a render is exactly like rendering the row.  Exists so tests
        and tools can inspect tokens without touching private methods.
        """
        return self._tokens_for(row)

    def highlight_probe(self) -> HighlightProbe:
        """Return a read-only snapshot of the highlight cache state."""
        return HighlightProbe(
            tokens=self._hl_tokens,
            doc=self._hl_doc,
            version=self._hl_version,
            filetype=self._hl_filetype,
            scheduled_key=self._hl_scheduled_key,
            timer=self._hl_timer,
        )

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
        # not cancel each other's highlight passes.  The coroutine
        # *function* is passed, not an eager coroutine: if the pump is
        # closing, the worker never starts and an eager coroutine would
        # leak ("was never awaited" RuntimeWarning).
        self.run_worker(
            self._highlight_later, group="highlight",
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
        tokens, ml_states = await asyncio.to_thread(
            _tokenize_with_states, lines, filetype
        )
        if not self.is_mounted:
            return
        # discard the result if the document changed/closed while we worked;
        # a repaint reschedules a fresh pass for the current state
        if self.doc is not doc or buf.content_version != version:
            self.refresh()
            # Re-schedule immediately: the discarded pass must not cost an
            # extra debounce window on top of the time already spent
            # tokenizing.  The stale tokens keep coloring meanwhile (no
            # flash), and the worker group is exclusive, so this cannot
            # stack up concurrent tokenize passes.
            self._schedule_highlight(0.0)
            return
        self._hl_tokens = tokens
        self._hl_doc = doc
        self._hl_version = version
        self._hl_filetype = filetype
        # The row snapshot and multiline states ride along with every cache
        # write (they are only ever stored here and in
        # _rebuild_tokens_on_edit, always together with _hl_tokens).
        self._hl_line_snapshot = tuple(lines)
        self._hl_ml_states = ml_states
        if self._hl_scheduled_key == (doc, filetype, version):
            self._hl_scheduled_key = None
        self.refresh()

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
            return self._render_welcome(y, view_w, gutter_w, t)

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
        """(text, color, bold, centered) tuples per welcome row.

        The rows embed theme colors and keymap-dependent hints, so they are
        cached per (theme name, vim_keys): the welcome page re-renders every
        frame while visible and used to rebuild the rows each time.  A theme
        or keymap switch changes the cache key and forces a rebuild.
        """
        key = (t.name, vim_keys)
        cached = self._welcome_cache.get(key)
        if cached is not None:
            return cached
        rows: list[_WelcomeRow] = [
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
        self._welcome_cache[key] = rows
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
