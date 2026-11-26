"""Docked quickfix panel: an inert L2 view over a shared :class:`QuickFixList`.

The panel is driven entirely by the injected pure-data
:class:`~yate.session.QuickFixList` and two callbacks -- ``on_pick``
called with the selected index, ``on_close`` to dismiss the dock.  The
caller owns the follow-up navigation; no App handle and no editor state
live here.

Theme ownership is self-held (R13): the panel subscribes to the theme
broadcast on mount and repaints itself.  Scrollbar rendering follows the
R15 pair -- ``apply_slim_scrollbars`` on mount,
``apply_scrollbar_theme`` in the paint path.  Key handling consumes only
``up`` / ``down`` / ``enter`` / ``escape``; every other key falls
through untouched (R10).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import override

from rich.cells import chop_cells
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.events import Key
from textual.widgets import Static

from yate.editor_components import theme
from yate.editor_components.scrollbars import apply_scrollbar_theme, apply_slim_scrollbars
from yate.session import QuickFixList

#: Called with the selected entry index (injected by the dock owner).
type PickFn = Callable[[int], None]

#: Called when the user presses ``escape`` (injected by the dock owner).
type CloseFn = Callable[[], None]


class QuickFixPanel(VerticalScroll):
    """Scrollable list of quickfix entries with a movable cursor."""

    def __init__(
        self,
        entries: QuickFixList,
        *,
        on_pick: PickFn,
        on_close: CloseFn,
        id: str = "quickfix-panel",
    ) -> None:
        super().__init__(id=id)
        self._entries = entries
        self._on_pick = on_pick
        self._on_close = on_close

    @override
    def compose(self) -> ComposeResult:
        """The single body static painting all entry lines."""
        yield Static(id="quickfix-body")

    def on_mount(self) -> None:
        """Install slim scrollbars, paint once, then follow the theme (R13)."""
        apply_slim_scrollbars(self)
        self._paint()
        theme.attach(self, self._paint)

    def on_unmount(self) -> None:
        """Detach from the theme broadcast."""
        theme.detach(self)

    def on_key(self, event: Key) -> None:
        """Handle the four consumed keys; everything else falls through."""
        if event.key not in ("up", "down", "enter", "escape"):
            return
        event.stop()
        event.prevent_default()
        if event.key == "up":
            self._entries.step(-1)
            self._paint()
        elif event.key == "down":
            self._entries.step(1)
            self._paint()
        elif event.key == "enter":
            self._on_pick(self._entries.selected)
        else:
            self._on_close()

    def repaint(self) -> None:
        """Repaint the body and the scrollbar palette from current state."""
        self._paint()

    def _paint(self) -> None:
        """Apply the shared paint path to body, palette and scroll offset."""
        apply_scrollbar_theme(self)
        body = self.query_one("#quickfix-body", Static)
        body.update(self._body_text())
        self._reveal_selection()

    def _body_text(self) -> Text:
        """One line per entry (selected prefixed ``> ``) or the placeholder.

        Each entry is chopped to the content width so it always renders
        as exactly one physical row; this keeps the logical entry index
        aligned with the physical scroll rows used by
        :meth:`_reveal_selection`.  The chop applies to the rendered
        text only -- ``QuickFixEntry.label`` itself is never trimmed.
        """
        entries = self._entries.snapshot()
        if not entries:
            return Text("(no results)", style=theme.active().fg_muted)
        t = theme.active()
        text = Text()
        # Two cells are reserved for the selection marker prefix.  A
        # not-yet-laid-out widget reports an empty content region, so fall
        # back to the widget width (same fallback as the view layer).
        width = self.scrollable_content_region.width or self.size.width
        inner_width = width - 2
        for index, entry in enumerate(entries):
            selected = index == self._entries.selected
            style = f"bold {t.on_accent} on {t.accent}" if selected else t.fg_bright
            marker = "> " if selected else "  "
            location = f"{entry.path.name}:{entry.row + 1}:{entry.col + 1}"
            line = f"{entry.provider} | {entry.severity} | {entry.label} @ {location}"
            if inner_width > 0:
                # chop_cells yields one or more width-bounded rows; keep
                # only the first so each entry stays a single physical line.
                line = chop_cells(line, inner_width)[0]
            text.append(marker, style=style)
            text.append(f"{line}\n", style=style)
        return text

    def _reveal_selection(self) -> None:
        """Scroll only when the selected line falls outside the viewport."""
        height = self.size.height
        if height <= 0:
            return
        top = self.scroll_offset.y
        selected = self._entries.selected
        if not top <= selected < top + height:
            self.scroll_to(y=selected, animate=False)
