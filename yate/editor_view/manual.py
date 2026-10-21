"""Read-only viewer for bundled markdown docs (user manual, changelog).

Renders ``yate/resources/<kind>.<lang>.md`` as markdown *once*, into cached
render rows, and paints those rows from a single widget.  Textual's
``Markdown`` widget mounts one child widget per markdown block (1788 for the
manual, 3733 for the changelog), and the per-widget CSS matching and box-model
resolution that comes with them -- not the markdown parsing -- is what made
opening a document cost ~11s and closing it 2-8s.  Pre-rendering keeps the
rendered text (headings, code fences, tables, emphasis) while paying the
layout cost once per document instead of once per block.

Rows are produced off the loop by :func:`render_doc_lines` in the loader
worker.  Two inputs are baked into them -- the body width and the active
theme -- so a resize or a theme switch re-renders (both are cheap: ~0.5s for
the largest bundled document, off the loop).

Colors follow the active yate theme: :func:`doc_rich_theme` maps Rich's
``markdown.*`` style names onto the yate palette, which is the same palette
the Textual theme bridge (``themes.to_textual_theme``) feeds the rest of the
app, so the viewer keeps matching the app theme.

In-screen search (``/`` or ``ctrl+f``): the query is matched
case-insensitively against the plain text of every rendered row (table cells
included -- they are rows like any other).  Every hit row is tinted, the
current one stronger, and enter / shift+enter cycle matches and scroll them
into view; after closing the search bar ``n`` / ``N`` repeat the last search.
Typing is debounced briefly so rapid input merges into a single rebuild
instead of re-painting per keystroke.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterable, Sequence
from functools import partial
from importlib.resources import files
from io import StringIO
from typing import cast, override

from rich.console import Console
from rich.markdown import Markdown
from rich.segment import Segment
from rich.style import Style
from rich.theme import Theme as RichTheme
from textual import events
from textual.app import ComposeResult
from textual.color import Color
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.geometry import Size
from textual.screen import ModalScreen
from textual.strip import Strip
from textual.widget import Widget
from textual.widgets import Input, Static

from yate.paths import load_tcss

from yate.editor_view import theme
from yate.editor_view.scrollbars import apply_scrollbar_theme, apply_slim_scrollbars
from yate.editor_view.themes import Theme
from yate.logs import tracing

log = tracing.get_logger(__name__)

_DOC_LANGS: tuple[str, ...] = ("en", "zh")

#: Fixed notice rendered when a doc is not shipped with the build.  The
#: changelog (unlike the manual) is a generated artifact that a build may
#: legitimately lack; every entry point degrades to this text, never raises.
_UNAVAILABLE: dict[str, dict[str, str]] = {
    "manual": {
        "en": "# User Manual\n\nNo manual is shipped with this build.",
        "zh": "# 用户手册\n\n此构建未包含用户手册。",
    },
    "changelog": {
        "en": "# Changelog\n\nNo changelog is shipped with this build.",
        "zh": "# 变更日志\n\n此构建未包含变更日志。",
    },
}

#: Width the rows are rendered for until the body has been laid out.
_FALLBACK_WIDTH: int = 80

#: Opacity of a search-hit tint and of the current-hit tint, applied over the
#: surface color (the same 12% / 40% the Textual theme bridge used to expose as
#: ``$doc-hit-background`` / ``$doc-hit-current-background``).
_HIT_ALPHA: float = 0.12
_CURRENT_HIT_ALPHA: float = 0.40


def load_doc_markdown(kind: str, lang: str = "en") -> str:
    """Read ``resources/<kind>.<lang>.md``; fall back to en, then to a
    fixed "unavailable" notice. Never raises for a missing resource."""
    lang = lang.strip().lower()
    if lang not in _DOC_LANGS:
        lang = "en"
    root = files("yate.resources")
    resource = root.joinpath(f"{kind}.{lang}.md")
    if not resource.is_file() and lang != "en":
        resource = root.joinpath(f"{kind}.en.md")
    if not resource.is_file():
        return _UNAVAILABLE.get(kind, _UNAVAILABLE["manual"])[lang]
    return resource.read_text(encoding="utf-8")


def load_manual_markdown(lang: str = "en") -> str:
    """Return the bundled manual for *lang* (``en``/``zh``) as markdown."""
    return load_doc_markdown("manual", lang)


def load_changelog_markdown(lang: str = "en") -> str:
    """Return the bundled changelog for *lang* (``en``/``zh``) as markdown."""
    return load_doc_markdown("changelog", lang)


def doc_rich_theme(active: Theme) -> RichTheme:
    """Build the Rich console theme the markdown renderer paints with.

    Rich resolves its ``markdown.*`` style names through the console theme, so
    this mapping is the single place the viewer binds colors.  The slots mirror
    the Textual theme bridge: headings take the accent the bridge maps to
    ``$primary``, code and tables the panel surface, quotes and rules the muted
    foreground.
    """
    heading = f"bold {active.accent2}"
    return RichTheme({
        "markdown.h1": f"bold underline {active.accent2}",
        "markdown.h2": heading,
        "markdown.h3": heading,
        "markdown.h4": f"bold {active.fg}",
        "markdown.h5": f"bold {active.fg}",
        "markdown.h6": f"bold {active.fg}",
        "markdown.code": f"bold {active.green} on {active.panel}",
        "markdown.code_block": f"{active.fg} on {active.panel}",
        "markdown.block_quote": active.fg_muted,
        "markdown.item.bullet": active.accent2,
        "markdown.item.number": active.accent2,
        "markdown.link": active.accent,
        "markdown.link_url": f"underline {active.accent}",
        "markdown.table.border": active.fg_muted,
        "markdown.table.header": f"bold {active.fg}",
        "markdown.hr": active.fg_dim,
        "markdown.kbd": f"bold {active.fg} on {active.panel}",
    })


def render_doc_lines(
    source: str, width: int, *, active: Theme | None = None
) -> list[Strip]:
    """Render markdown *source* into rows *width* columns wide.

    Pure: no widget, no app, no loop -- safe to call from a worker thread and
    cheap to test.  *active* defaults to the current yate theme; callers that
    already hold a palette pass it to keep one snapshot per render.
    """
    palette = active if active is not None else theme.active()
    console = Console(
        file=StringIO(),
        width=max(20, width),
        color_system="truecolor",
        theme=doc_rich_theme(palette),
        legacy_windows=False,
    )
    renderable = Markdown(source)
    lines = console.render_lines(renderable, console.options, pad=False)
    return [Strip(list(line)) for line in lines]


def _strip_text(strip: Strip) -> str:
    """Plain text of one rendered row (``Strip.text``, Textual 8.2.8)."""
    return strip.text


def _tint_strip(strip: Strip, tint: Style) -> Strip:
    """Lay *tint* over every segment of *strip*.

    The tint goes on the right of the merge: ``a + b`` in
    :class:`rich.style.Style` lets *b* win its own attributes, so a code
    fence's background would otherwise survive and hide the tint on exactly
    the rows a user searches for.
    """
    return Strip([
        Segment(segment.text, segment.style + tint if segment.style else tint)
        for segment in strip
    ])


def _hit_styles(active: Theme) -> tuple[Style, Style]:
    """The (hit, current-hit) tints for *active*, blended over the surface."""
    base = Color.parse(active.surface)
    yellow = Color.parse(active.yellow)
    hit = Style(bgcolor=base.blend(yellow, _HIT_ALPHA).rich_color)
    current = Style(
        bgcolor=base.blend(yellow, _CURRENT_HIT_ALPHA).rich_color, bold=True
    )
    return hit, current


class _SearchInput(Input):
    """Search field that traps escape (close search) and shift+enter.

    A plain ``Input`` lets both keys bubble, where the screen's
    escape/dismiss binding would close the whole document instead of just
    the search bar.  Not focusable until the search bar is opened, so
    keys (esc/q/n/N) reach the screen bindings while the bar is hidden.
    """

    can_focus = False

    @override
    async def _on_key(self, event: events.Key) -> None:
        if event.key == "escape":
            event.stop()
            event.prevent_default()
            cast(MarkdownDocScreen, self.screen).close_search()
            return
        if event.key == "shift+enter":
            event.stop()
            event.prevent_default()
            cast(MarkdownDocScreen, self.screen).search_step(-1)
            return
        await super()._on_key(event)


class DocScroll(VerticalScroll):
    """Scrollable markdown body owning its slim scrollbar painting."""

    def on_mount(self) -> None:
        """Own the slim-scrollbar wiring and the theme painting."""
        # no super()/@override here: VerticalScroll's MRO (ScrollableContainer
        # -> Widget) has no on_mount to chain -- unlike RichLog's ScrollView
        # base. Revisit if a Textual upgrade adds one.
        apply_slim_scrollbars(self)
        self._apply_theme()
        theme.attach(self, self._apply_theme)

    def on_unmount(self) -> None:
        """Detach from the theme broadcast."""
        theme.detach(self)

    def _apply_theme(self) -> None:
        """Paint the scrollbar palette from the active theme (IKJUU2, IKINF3 pattern)."""
        apply_scrollbar_theme(self)


class DocBody(Widget):
    """The whole document in one widget: cached rows plus search tints.

    One widget instead of one per markdown block is the entire point of this
    module: the rows are rendered once (see :func:`render_doc_lines`) and this
    widget paints them straight from :meth:`render_line`, so a search hit only
    costs a ``refresh()`` over the visible rows -- no document-sized rebuild.
    """

    def __init__(self) -> None:
        super().__init__(id="doc-md")
        self.source = ""
        self._rows: list[Strip] = []
        self._texts: list[str] = []
        self._hit_rows: frozenset[int] = frozenset()
        self._current_row: int | None = None
        self._render_width = 0
        self._hit_style, self._current_style = _hit_styles(theme.active())

    @override
    def get_content_height(self, container: Size, viewport: Size, width: int) -> int:
        """Every rendered row is one content row (no re-wrapping)."""
        return len(self._rows)

    @override
    def render_line(self, y: int) -> Strip:
        """Paint row *y* with its search tint, padded to the widget width."""
        if not 0 <= y < len(self._rows):
            return Strip.blank(self.size.width)
        strip = self._rows[y]
        tint: Style | None = None
        if y == self._current_row:
            tint = self._current_style
        elif y in self._hit_rows:
            tint = self._hit_style
        if tint is None:
            return strip.adjust_cell_length(self.size.width)
        return _tint_strip(strip, tint).adjust_cell_length(
            self.size.width, tint
        )

    @property
    def row_count(self) -> int:
        """How many rendered rows the loaded document has (0 before load)."""
        return len(self._rows)

    @property
    def render_width(self) -> int:
        """Width (columns) the cached rows were rendered for (0 before load)."""
        return self._render_width

    @property
    def hit_rows(self) -> frozenset[int]:
        """Rows currently tinted as search hits."""
        return self._hit_rows

    @property
    def current_row(self) -> int | None:
        """The row tinted as the current hit (``None`` when there is none)."""
        return self._current_row

    def row_text(self, row: int) -> str:
        """Plain text of rendered *row* (empty string when out of range)."""
        if 0 <= row < len(self._texts):
            return self._texts[row]
        return ""

    def set_document(
        self, source: str, rows: Sequence[Strip], width: int
    ) -> None:
        """Adopt freshly rendered *rows*, dropping any previous search tint."""
        self.source = source
        self._rows = list(rows)
        self._texts = [_strip_text(strip) for strip in self._rows]
        self._render_width = width
        self._hit_rows = frozenset()
        self._current_row = None
        self._hit_style, self._current_style = _hit_styles(theme.active())
        # layout, not just repaint: the content height follows the row count
        self.refresh(layout=True)

    def on_resize(self, event: events.Resize) -> None:
        """Ask the screen to re-render when the body's laid-out width changes.

        The width settles *after* the first render: mounting a tall document
        makes the scroll container reserve its scrollbar, which narrows the
        body by a column.  Without this the rows stay one column too wide and
        every one of them is cropped on the right.
        """
        screen = self.screen
        if isinstance(screen, MarkdownDocScreen):
            screen.body_resized(event.size.width)

    def set_hits(self, rows: Iterable[int], current: int | None) -> None:
        """Tint *rows* as matches and *current* as the focused one."""
        hit_rows = frozenset(rows)
        if hit_rows == self._hit_rows and current == self._current_row:
            return
        self._hit_rows = hit_rows
        self._current_row = current
        self.refresh()


class MarkdownDocScreen(ModalScreen[None]):
    """A bundled markdown document (manual/changelog), read-only."""

    BINDINGS = [
        ("escape", "dismiss", "close"),
        ("q", "dismiss", "close"),
        ("ctrl+c", "dismiss", "close"),
        ("slash", "search", "search"),
        ("ctrl+f", "search", "search"),
        ("n", "search_next", "next match"),
        ("N", "search_prev", "previous match"),
    ]

    # footer text switches with the search bar: while typing, n/N are
    # ordinary search characters -- only Enter / Shift+Enter move there;
    # n/N repeat the search only AFTER the bar is closed with Esc
    _FOOTER_SEARCH = (
        " enter: next match  ·  shift+enter: previous  ·  esc: close search"
        "  ·  pgup/pgdn scroll "
    )
    _FOOTER_BROWSE = (
        " esc/q close  ·  / or ctrl+f search  ·  n/N repeat last match"
        "  ·  pgup/pgdn scroll "
    )

    #: Trailing debounce that merges rapid search typing into a single
    #: hit-rebuild pass (same order of magnitude as the editor's highlight
    #: and completion debounces).
    _SEARCH_DEBOUNCE_S = 0.12

    #: Delay before a resize re-renders, so a live drag re-renders once.
    _RERENDER_DELAY_S = 0.15

    DEFAULT_CSS = load_tcss("markdown-doc-screen.tcss")

    def __init__(self, *, kind: str, lang: str, title: str) -> None:
        super().__init__()
        self._kind = kind
        self._lang = lang
        self._title = title
        # (row, column, query length) over the rendered rows, document order
        self._hits: list[tuple[int, int, int]] = []
        self._hit_index = -1
        self._query = ""
        # pending debounced search: the asyncio timer plus the last typed
        # query it will run (typing merges into one rebuild per window)
        self._search_timer: asyncio.TimerHandle | None = None
        self._pending_query: str | None = None

    @override
    def compose(self) -> ComposeResult:
        """Compose the doc box: search bar, scrollable body and footer."""
        with Vertical(id="doc-box"):
            with Horizontal(id="doc-search-bar"):
                yield _SearchInput(
                    placeholder=f"search {self._title}…  enter: next  shift+enter: prev",
                    id="doc-search-input",
                )
                yield Static("", id="doc-search-status")
            with DocScroll(id="doc-scroll"):
                # empty initially: the content loads in a background worker
                # so the screen itself can paint without a hitch
                yield Static(f" loading {self._title}…", id="doc-loading")
                yield DocBody()
            yield Static(
                self._FOOTER_BROWSE,
                id="doc-footer",
                classes="hint",
            )

    def on_mount(self) -> None:
        """Start the background loader and follow theme switches."""
        # coroutine *function*: an eager coroutine would leak if the
        # worker never starts (closing pump)
        self.run_worker(
            self._load_doc, group="doc-load", exclusive=True,
            exit_on_error=False,
        )
        theme.attach(self, self._on_theme_change)

    def on_unmount(self) -> None:
        """Drop the pending debounce and the theme subscription.

        A search typed within :attr:`_SEARCH_DEBOUNCE_S` and then dismissed with
        ``escape`` would otherwise leave an armed :class:`asyncio.TimerHandle`
        holding a reference to this unmounted screen until it fires.  Mirrors
        :meth:`FindReplaceScreen.on_unmount` and the diff screen's teardown.
        """
        if self._search_timer is not None:
            self._search_timer.cancel()
            self._search_timer = None
        self._pending_query = None
        theme.detach(self)

    def on_resize(self, event: events.Resize) -> None:
        """Re-render when the body width changes (rows are pre-wrapped)."""
        self._schedule_rerender()

    # ------------------------------------------------------------ loading

    def _doc_body(self) -> DocBody | None:
        """The body widget, or ``None`` before ``compose`` has mounted it.

        A resize lands before the first compose on a freshly pushed screen, so
        the resize / theme paths must tolerate a missing body.
        """
        found = self.query("#doc-md")
        if not found:
            return None
        return cast(DocBody, found.first())

    def _body_width(self) -> int:
        """Columns available to the document body.

        The body's own laid-out width is the only value that matches what
        :meth:`DocBody.render_line` pads to, so it wins whenever it is known.
        Before the first layout it is 0: fall back to the scroll viewport and
        then to :data:`_FALLBACK_WIDTH`, and let
        :meth:`_correct_render_width` re-render once the real width lands.
        """
        body = self._doc_body()
        if body is not None and body.size.width > 0:
            return body.size.width
        scroll = self.query_one("#doc-scroll", DocScroll)
        width = scroll.scrollable_content_region.width
        if width > 0:
            return width
        return _FALLBACK_WIDTH

    async def _load_doc(self) -> None:
        """Read the document, render its rows off the loop, then show them."""
        try:
            source = await asyncio.to_thread(
                load_doc_markdown, self._kind, self._lang
            )
        except OSError as exc:  # pragma: no cover - resources are bundled
            source = f"failed to load the {self._title}: {exc}"
        # the viewer may have been closed while the read was in flight
        if not self.is_mounted:
            return
        # the file read yields to the loop, so the first layout has usually
        # landed by now -- still re-checked after mounting the rows below
        width = self._body_width()
        rows = await self._render_or_failure(source, width)
        if not self.is_mounted:
            return
        body = self.query_one("#doc-md", DocBody)
        body.set_document(source, rows, width)
        self.query_one("#doc-loading", Static).display = False
        self.query_one("#doc-scroll", DocScroll).scroll_home(animate=False)
        self.call_after_refresh(self._correct_render_width)

    async def _render_or_failure(self, source: str, width: int) -> list[Strip]:
        """Render *source*, degrading to one error row instead of hanging.

        The loader worker runs with ``exit_on_error=False``, so an exception
        escaping here would leave the viewer on its loading line forever --
        and :func:`render_doc_lines` runs user-controlled markdown through Rich.
        """
        try:
            return await asyncio.to_thread(
                render_doc_lines, source, width, active=theme.active()
            )
        except Exception as exc:  # noqa: BLE001 - a bad render must not hang the viewer
            log.exception("failed to render the %s", self._title)
            return [Strip([Segment(
                f" failed to render the {self._title}: {exc}", Style(color="red")
            )])]

    def _correct_render_width(self) -> None:
        """Re-render when the laid-out width differs from the rendered one.

        The first render may race the layout (see :meth:`_body_width`); the
        mismatch would otherwise silently crop every row wider than the body
        until the user resizes the window.
        """
        body = self._doc_body()
        if body is None or not body.source:
            return
        width = body.size.width
        if width > 0 and width != body.render_width:
            self.run_worker(
                partial(self._rerender, width), group="doc-load", exclusive=True
            )

    def body_resized(self, width: int) -> None:
        """The body's laid-out width changed: re-render if it now mismatches."""
        if width <= 0:
            return
        self._schedule_rerender()

    def _on_theme_change(self) -> None:
        """Re-render the cached rows: their colors are baked in at render time."""
        body = self._doc_body()
        if body is None or not body.source:
            return
        self.run_worker(
            partial(self._rerender, body.render_width),
            group="doc-load", exclusive=True,
        )

    def _schedule_rerender(self) -> None:
        """Re-render once the resize settles (a live drag would re-render often)."""
        body = self._doc_body()
        if body is None or not body.source:
            return
        if self._body_width() == body.render_width:
            return
        self.set_timer(self._RERENDER_DELAY_S, self._rerender_now)

    def _rerender_now(self) -> None:
        """Timer callback: re-render at the current body width."""
        body = self._doc_body()
        if body is None or not body.source:
            return
        width = self._body_width()
        if width == body.render_width:
            return
        self.run_worker(
            partial(self._rerender, width), group="doc-load", exclusive=True
        )

    async def _rerender(self, width: int) -> None:
        """Re-render the loaded document for *width* (resize / theme change)."""
        current = self._doc_body()
        if current is None:
            return
        body = current
        source = body.source
        if not source or not self.is_mounted:
            return
        # a re-render must not throw the reader's place away: remember the
        # current hit row and restore the nearest one afterwards
        previous_row = (
            self._hits[self._hit_index][0]
            if 0 <= self._hit_index < len(self._hits) else None
        )
        rows = await self._render_or_failure(source, width)
        if not self.is_mounted:
            return
        body.set_document(source, rows, width)
        if self._query:
            self._run_search(self._query)
            self._restore_hit(previous_row)

    def _restore_hit(self, previous_row: int | None) -> None:
        """Return to the hit nearest *previous_row* after a re-render."""
        if not self._hits:
            return
        if previous_row is None:
            return
        self._hit_index = min(
            range(len(self._hits)),
            key=lambda index: abs(self._hits[index][0] - previous_row),
        )
        self._goto_current_hit()

    # ------------------------------------------------------------ search

    def action_search(self) -> None:
        """Reveal/focus the search bar (``/`` or ctrl+f)."""
        bar = self.query_one("#doc-search-bar", Horizontal)
        if not bar.display:
            bar.display = True
        field = self.query_one("#doc-search-input", _SearchInput)
        field.can_focus = True
        field.focus()
        self._set_footer(self._FOOTER_SEARCH)
        if self._hits:
            self._set_status(
                f"{self._hit_index + 1}/{len(self._hits)} matches")
        else:
            self._set_status("type to search")

    def close_search(self) -> None:
        """Hide the search bar but keep the hit highlights for n/N."""
        field = self.query_one("#doc-search-input", _SearchInput)
        field.can_focus = False
        self.set_focus(None)
        self.query_one("#doc-search-bar", Horizontal).display = False
        self._set_footer(self._FOOTER_BROWSE)

    def _set_footer(self, text: str) -> None:
        """Swap the bottom hint line to match the current input context."""
        footer = self.query("#doc-footer")
        if footer:
            cast(Static, footer.first()).update(text)

    def action_search_next(self) -> None:
        """Binding for ``n``: step to the next match."""
        self.search_step(1)

    def action_search_prev(self) -> None:
        """Binding for ``N``: step to the previous match."""
        self.search_step(-1)

    def search_step(self, delta: int) -> None:
        """Advance the current hit by *delta* and scroll it into view."""
        if not self._hits:
            return
        self._hit_index = (self._hit_index + delta) % len(self._hits)
        self._goto_current_hit()

    def on_input_changed(self, event: Input.Changed) -> None:
        """Re-run the search (debounced) while typing in the search field."""
        if event.input.id == "doc-search-input":
            self._schedule_search(event.value)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Enter in the search field: jump to the next match."""
        if event.input.id == "doc-search-input":
            # enter cycles matches: flush the pending query first so the
            # step below sees the hits for what was actually typed
            self._flush_pending_search()
            self.search_step(1)

    def _schedule_search(self, query: str) -> None:
        """Defer the search rebuild until typing pauses briefly.

        Rebuilding per keystroke repainted the hit tints synchronously, which
        stutters on large documents; the trailing window merges rapid input
        into one pass carrying the final query.
        """
        if self._search_timer is not None:
            self._search_timer.cancel()
        self._pending_query = query
        self._search_timer = asyncio.get_running_loop().call_later(
            self._SEARCH_DEBOUNCE_S, self._flush_search
        )

    def _flush_search(self) -> None:
        """Timer callback: run the pending debounced search now."""
        self._search_timer = None
        self._flush_pending_search()

    def _flush_pending_search(self) -> None:
        """Cancel any pending debounce and search for the pending query."""
        if self._search_timer is not None:
            self._search_timer.cancel()
            self._search_timer = None
        query = self._pending_query
        if query is None or not self.is_mounted:
            # the screen may have been dismissed while the timer was armed
            return
        self._pending_query = None
        self._run_search(query)

    def _run_search(self, query: str) -> None:
        """Scan every rendered row for *query* and tint the matches."""
        needle = query.strip().lower()
        self._query = needle
        body = self.query_one("#doc-md", DocBody)
        hits: list[tuple[int, int, int]] = []
        if needle:
            for row in range(body.row_count):
                line = body.row_text(row).lower()
                start = 0
                while True:
                    idx = line.find(needle, start)
                    if idx < 0:
                        break
                    hits.append((row, idx, len(needle)))
                    start = idx + len(needle)
        self._hits = hits
        body.set_hits((row for row, _col, _length in hits), None)
        if not needle:
            self._hit_index = -1
            self._set_status("type to search")
            return
        if not hits:
            self._hit_index = -1
            self._set_status("no matches")
            return
        self._hit_index = 0
        self._goto_current_hit()

    def _goto_current_hit(self) -> None:
        """Tint the current hit stronger and scroll its row into view."""
        if self._hit_index < 0 or not self._hits:
            return
        body = self.query_one("#doc-md", DocBody)
        row, _col, _length = self._hits[self._hit_index]
        body.set_hits((r for r, _c, _l in self._hits), row)
        # one row is one scroll offset: the rows are pre-wrapped, so the row
        # index is the exact line the match sits on
        self.query_one("#doc-scroll", DocScroll).scroll_to(
            y=row, animate=False, immediate=True
        )
        self._set_status(
            f"{self._hit_index + 1}/{len(self._hits)} matches")

    def _set_status(self, text: str) -> None:
        status = self.query_one("#doc-search-status", Static)
        status.update(f" {text} ")
