"""Read-only viewer for the bundled user manual.

Renders ``yate/resources/manual.<lang>.md`` with Textual's markdown
widget.  Textual's built-in Catppuccin theme is applied while the screen
is open (switched by the app *before* this screen is pushed, so the very
first frame is already themed) so headings, code blocks and tables match
yate's palette.

The screen paints immediately with a loading line; the file is read in a
worker thread and the markdown is parsed/mounted afterwards (Textual's
Markdown.update already parses in an executor and mounts in batches), so
opening the manual never blocks the UI.

Tables are laid out by a CSS grid that squeezes cells when the table is
container-bound; auto-width keeps cells on one line so the keylines of
CJK tables stay aligned.

In-screen search (``/`` or ``ctrl+f``): the query is matched
case-insensitively against the visible text of every rendered block
(including table cells).  Every hit block is tinted, the current one
stronger, and enter / shift+enter cycle matches and scroll them into
view; after closing the search bar ``n`` / ``N`` repeat the last search.
"""

from __future__ import annotations

import asyncio
from importlib.resources import files
from typing import Any, cast

from textual import events
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widget import Widget
from textual.widgets import Input, Markdown, Static

_MANUAL_LANGS = ("en", "zh")


def load_manual_markdown(lang: str = "en") -> str:
    """Return the bundled manual for *lang* (``en``/``zh``) as markdown."""
    code = lang.strip().lower()
    if code not in _MANUAL_LANGS:
        code = "en"
    resource = files("yate.resources").joinpath(f"manual.{code}.md")
    if not resource.is_file():
        resource = files("yate.resources").joinpath("manual.en.md")
    return resource.read_text(encoding="utf-8")


def _widget_plain_text(widget: Widget) -> str:
    """Best-effort visible text a widget owns itself.

    MarkdownBlock stores a rich Content; table cells/static children may
    carry a renderable (str / Text / Content). Table cell widgets expose
    neither but render a Content with no children, so fall back to
    ``render()`` for childless widgets. Layout containers (whose children
    own the text) stay empty so matches are not double counted.
    """
    content = getattr(widget, "_content", None)
    if content is not None and hasattr(content, "plain"):
        plain = cast(str, content.plain)
        if plain:
            return plain
    renderable = getattr(widget, "renderable", None)
    if isinstance(renderable, str):
        return renderable
    if renderable is not None and hasattr(renderable, "plain"):
        return cast(str, renderable.plain)
    if not getattr(widget, "children", ()):
        try:
            rendered = widget.render()
        except Exception:
            return ""
        plain = getattr(rendered, "plain", None)
        if isinstance(plain, str):
            return plain
    return ""


def _strip_text(strip: Any) -> str:
    """Plain text of one rendered row (Strip)."""
    segments = getattr(strip, "_segments", None)
    if segments is None:
        segments = getattr(strip, "segments", ())
    return "".join(seg.text or "" for seg in segments)


class _SearchInput(Input):
    """Search field that traps escape (close search) and shift+enter.

    A plain ``Input`` lets both keys bubble, where the screen's
    escape/dismiss binding would close the whole manual instead of just
    the search bar.  Not focusable until the search bar is opened, so
    keys (esc/q/n/N) reach the screen bindings while the bar is hidden.
    """

    can_focus = False

    async def _on_key(self, event: events.Key) -> None:
        if event.key == "escape":
            event.stop()
            event.prevent_default()
            cast(ManualScreen, self.screen).close_search()
            return
        if event.key == "shift+enter":
            event.stop()
            event.prevent_default()
            cast(ManualScreen, self.screen).search_step(-1)
            return
        await super()._on_key(event)


class ManualScreen(ModalScreen[None]):
    """The user manual, rendered as read-only markdown."""

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

    DEFAULT_CSS = """
    ManualScreen {
        align: center middle;
    }
    ManualScreen #manual-box {
        width: 90%;
        height: 90%;
        background: $surface;
        border: tall $primary;
        padding: 0 2;
    }
    ManualScreen #manual-search-bar {
        height: 3;
        padding: 0 1;
        background: $surface;
        display: none;
    }
    ManualScreen #manual-search-input {
        width: 1fr;
        height: 3;
        border: none;
        background: $surface;
        padding: 0;
    }
    ManualScreen #manual-search-status {
        width: auto;
        min-width: 14;
        height: 1;
        padding: 1 1;
        color: $text-muted;
        background: $surface;
    }
    ManualScreen #manual-scroll {
        height: 1fr;
    }
    ManualScreen #manual-loading {
        height: 1;
        padding: 1 0;
        color: $text-muted;
    }
    ManualScreen .hint {
        height: 1;
        color: $text-muted;
        text-align: center;
    }
    /* search hit tints (manual is always shown with catppuccin-mocha, so
       fixed yellow alphas match that palette) */
    ManualScreen .manual-hit {
        background: #f9e2af1f;
    }
    ManualScreen .manual-hit-current {
        background: #f9e2af66;
        text-style: bold;
    }
    /* table cells default to a squeezed 1fr grid which wraps long CJK
       labels and breaks the keyline alignment; auto-width renders each
       cell on a single line with clean borders */
    ManualScreen MarkdownTable {
        width: auto;
    }
    """

    def __init__(self, yate: Any, lang: str = "en") -> None:
        super().__init__()
        self.yate = yate
        self._lang = lang
        # (widget, inner row, inner column, query length), document order
        self._hits: list[tuple[Widget, int, int, int]] = []
        self._hit_index = -1
        self._hit_widgets: set[Widget] = set()
        self._current_widget: Widget | None = None

    def compose(self) -> ComposeResult:
        with Vertical(id="manual-box"):
            with Horizontal(id="manual-search-bar"):
                yield _SearchInput(
                    placeholder="search manual…  enter: next  shift+enter: prev",
                    id="manual-search-input",
                )
                yield Static("", id="manual-search-status")
            with VerticalScroll(id="manual-scroll"):
                # empty initially: the content loads in a background worker
                # so the screen itself can paint without a hitch
                yield Static(" loading manual…", id="manual-loading")
                yield Markdown("", id="manual-md")
            yield Static(
                self._FOOTER_BROWSE,
                id="manual-footer",
                classes="hint",
            )

    def on_mount(self) -> None:
        self.run_worker(
            self._load_manual(), group="manual-load", exclusive=True,
            exit_on_error=False,
        )

    async def _load_manual(self) -> None:
        """Read the manual off the loop, then let Markdown mount in batches."""
        try:
            source = await asyncio.to_thread(load_manual_markdown, self._lang)
        except OSError as exc:  # pragma: no cover - resource is bundled
            source = f"failed to load the manual: {exc}"
        # the viewer may have been closed while the read was in flight
        if not self.is_mounted:
            return
        try:
            markdown = self.query_one("#manual-md", Markdown)
            loading = self.query_one("#manual-loading", Static)
            await markdown.update(source)
            if self.is_mounted:
                loading.display = False
        except Exception:
            # widget torn down mid-update after a quick esc/q; nothing to do
            if self.is_mounted:
                raise

    # ------------------------------------------------------------ search

    def action_search(self) -> None:
        """Reveal/focus the search bar (``/`` or ctrl+f)."""
        bar = self.query_one("#manual-search-bar", Horizontal)
        if not bar.display:
            bar.display = True
        field = self.query_one("#manual-search-input", _SearchInput)
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
        field = self.query_one("#manual-search-input", _SearchInput)
        field.can_focus = False
        self.set_focus(None)
        self.query_one("#manual-search-bar", Horizontal).display = False
        self._set_footer(self._FOOTER_BROWSE)

    def _set_footer(self, text: str) -> None:
        """Swap the bottom hint line to match the current input context."""
        footer = self.query("#manual-footer")
        if footer:
            cast(Static, footer.first()).update(text)

    def action_search_next(self) -> None:
        self.search_step(1)

    def action_search_prev(self) -> None:
        self.search_step(-1)

    def search_step(self, delta: int) -> None:
        if not self._hits:
            return
        self._hit_index = (self._hit_index + delta) % len(self._hits)
        self._goto_current_hit()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "manual-search-input":
            self._run_search(event.value)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "manual-search-input":
            self.search_step(1)

    def _run_search(self, query: str) -> None:
        needle = query.strip().lower()
        hits: list[tuple[Widget, int, int, int]] = []
        if needle:
            markdown = self.query_one("#manual-md", Markdown)
            for widget in markdown.walk_children(Widget):
                if not _widget_plain_text(widget):
                    continue
                # ranges (in widget-local rows/cols) painted by direct
                # children, e.g. the language label of a code fence --
                # their strips are composited into ours but the children
                # are searched separately
                child_boxes = [
                    (
                        child.region.y - widget.region.y,
                        child.region.y - widget.region.y + child.region.height,
                        child.region.x - widget.region.x,
                        child.region.x - widget.region.x + child.region.width,
                    )
                    for child in widget.children
                ]
                for row in range(widget.region.height):
                    try:
                        line = _strip_text(widget.render_line(row)).lower()
                    except Exception:
                        continue
                    start = 0
                    while True:
                        idx = line.find(needle, start)
                        if idx < 0:
                            break
                        end = idx + len(needle)
                        covered = any(
                            y0 <= row < y1 and idx < x1 and end > x0
                            for (y0, y1, x0, x1) in child_boxes
                        )
                        if not covered:
                            hits.append((widget, row, idx, len(needle)))
                        start = end
        self._hits = hits
        self._clear_hit_classes()
        if not needle:
            self._hit_index = -1
            self._set_status("type to search")
            return
        if not hits:
            self._hit_index = -1
            self._set_status("no matches")
            return
        self._hit_widgets = {widget for widget, _r, _c, _l in hits}
        for widget in self._hit_widgets:
            widget.add_class("manual-hit")
        self._hit_index = 0
        self._goto_current_hit()

    def _goto_current_hit(self) -> None:
        if self._hit_index < 0:
            return
        widget, row, _col, _length = self._hits[self._hit_index]
        if self._current_widget is not None and self._current_widget is not widget:
            self._current_widget.remove_class("manual-hit-current")
        widget.add_class("manual-hit-current")
        self._current_widget = widget
        # align the widget's top first, then offset to the exact rendered
        # row, so several matches inside one wrapped paragraph land on
        # distinct lines (widget.scroll_visible alone would not move)
        scroll = self.query_one("#manual-scroll", VerticalScroll)
        # immediate=True applies before the second scroll_to, which refines
        # the position to the exact rendered row (several matches can share
        # one wrapped widget, widget-level scrolling would not move)
        scroll.scroll_to_widget(
            widget, top=True, animate=False, immediate=True
        )
        scroll.scroll_to(
            y=scroll.scroll_target_y + row,
            animate=False,
            immediate=True,
        )
        self._set_status(
            f"{self._hit_index + 1}/{len(self._hits)} matches")

    def _clear_hit_classes(self) -> None:
        for widget in self._hit_widgets:
            widget.remove_class("manual-hit", "manual-hit-current")
        self._hit_widgets.clear()
        self._current_widget = None

    def _set_status(self, text: str) -> None:
        status = self.query_one("#manual-search-status", Static)
        status.update(f" {text} ")
