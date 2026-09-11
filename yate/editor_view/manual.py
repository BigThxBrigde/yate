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
    """Best-effort visible text of a rendered markdown child widget."""
    # MarkdownBlock stores a rich Content; table cells/static children may
    # carry a renderable (str / Text / Content).
    content = getattr(widget, "_content", None)
    if content is not None and hasattr(content, "plain"):
        return cast(str, content.plain)
    renderable = getattr(widget, "renderable", None)
    if isinstance(renderable, str):
        return renderable
    if renderable is not None and hasattr(renderable, "plain"):
        return cast(str, renderable.plain)
    return ""


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
        # (widget, start offset in visible text, query length), doc order
        self._hits: list[tuple[Widget, int, int]] = []
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
                " esc/q close  ·  / or ctrl+f search  ·  n/N next match  ·  "
                "pgup/pgdn or wheel to scroll ",
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
        hits: list[tuple[Widget, int, int]] = []
        if needle:
            markdown = self.query_one("#manual-md", Markdown)
            for widget in markdown.walk_children(Widget):
                text = _widget_plain_text(widget)
                if not text:
                    continue
                lowered = text.lower()
                start = 0
                while True:
                    idx = lowered.find(needle, start)
                    if idx < 0:
                        break
                    hits.append((widget, idx, len(needle)))
                    start = idx + len(needle)
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
        self._hit_widgets = {widget for widget, _s, _l in hits}
        for widget in self._hit_widgets:
            widget.add_class("manual-hit")
        self._hit_index = 0
        self._goto_current_hit()

    def _goto_current_hit(self) -> None:
        if self._hit_index < 0:
            return
        widget, _start, _length = self._hits[self._hit_index]
        if self._current_widget is not None and self._current_widget is not widget:
            self._current_widget.remove_class("manual-hit-current")
        widget.add_class("manual-hit-current")
        self._current_widget = widget
        widget.scroll_visible(animate=False)
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
