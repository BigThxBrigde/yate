"""Non-focusable floating Markdown card for LSP hover docs (plan e).

The widget mirrors :class:`yate.editor_components.completion.CompletionPopup`:
it is positioned by the editor with cell-space flipping, owns its own theme
painting (R13) and wires the slim scrollbar pair (R15).  The editor (plan h)
mounts it and feeds ``show`` with LSP hover markdown.
"""

from __future__ import annotations

from typing import override

from rich.markdown import Markdown
from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.css.scalar import ScalarOffset
from textual.widgets import Static

from yate.editor_components import theme
from yate.editor_components.manual import render_doc_lines
from yate.editor_components.scrollbars import (
    apply_scrollbar_theme,
    apply_slim_scrollbars,
)
from yate.paths import load_tcss

class HoverPopup(VerticalScroll):
    """Non-focusable floating Markdown card for LSP hover docs."""

    #: Rendered markdown rows the card may reach before it starts scrolling.
    MAX_ROWS: int = 12
    #: Narrowest usable card, in cells (tiny docs still get a readable box).
    MIN_WIDTH: int = 24
    #: Widest card, in cells; longer markdown lines wrap instead of widening.
    MAX_WIDTH: int = 72

    can_focus = False

    DEFAULT_CSS = load_tcss("hover-popup.tcss")

    #: Docs currently shown; empty when the card is closed (AC5 state).
    _text: str = ""

    @override
    def compose(self) -> ComposeResult:
        """Yield the single body widget the docs are rendered into."""
        yield Static("", id="hover-docs-body")

    def on_mount(self) -> None:
        """Start hidden; wire the scrollbar pair and the theme subscription."""
        self.display = False
        # ScrollBar instantiation needs an app context; a directly constructed
        # widget (no-App geometry tests) has no parent and skips the wiring.
        if self.parent is not None:
            apply_slim_scrollbars(self)
        self._apply_theme()
        theme.attach(self, self._apply_theme)

    def on_unmount(self) -> None:
        """Detach from the theme broadcast (widgets own their painting)."""
        theme.detach(self)

    # -------------------------------------------------------------- state

    @property
    def is_open(self) -> bool:
        """Whether the card is visible and holds non-empty docs."""
        return bool(self.display) and bool(self._text)

    # ------------------------------------------------------------ showing

    def show(
        self,
        text: str,
        anchor: tuple[int, int],
        inner_size: tuple[int, int],
        gutter: int,
        origin_y: int = 0,
    ) -> None:
        """Display the markdown *text* near *anchor*.

        *anchor* is the cursor cell (col, row) relative to the editor's text
        area; *inner_size* is the editor's (width, height) in cells; *gutter*
        is the gutter width in cells; *origin_y* is the offset of the editor
        inside the popup's parent (tab bar + breadcrumbs rows).
        """
        if not text.strip():  # second AC5 defence: never show empty docs
            self.close()
            return
        self._text = text

        lines = text.splitlines()
        widest = max(theme.cell_len(line) for line in lines)
        box_w = max(self.MIN_WIDTH, min(self.MAX_WIDTH, widest + 2))
        rows = render_doc_lines(text, box_w - 2, active=theme.active())
        box_h = min(self.MAX_ROWS, len(rows) + 2)

        # Horizontal: prefer starting at the cursor column, flip left if it
        # would overflow the editor's right edge (same policy as the
        # completion popup).
        x = min(gutter + anchor[0], max(0, inner_size[0] - box_w))
        x = max(0, x)
        # Vertical: open below the cursor unless there is not enough room;
        # then open above it.
        top_limit = origin_y + inner_size[1]
        below = origin_y + anchor[1] + 1
        if below + box_h <= top_limit:
            y = below
        else:
            y = max(origin_y, origin_y + anchor[1] - box_h + 1)

        self.styles.width = box_w
        self.styles.height = box_h
        self.styles.offset = ScalarOffset.from_offset((x, y))
        if self.parent is not None:  # no-App geometry tests have no body yet
            self.query_one("#hover-docs-body", Static).update(Markdown(text))
        self.display = True
        self.refresh()

    def close(self) -> None:
        """Hide the card and drop the docs it held.

        Idempotent: an already-hidden card with no docs skips the repaint
        entirely (no ``Static.update("")`` and no ``display`` write).
        """
        if not self.display and not self._text:
            return
        self._text = ""
        if self.parent is not None:
            self.query_one("#hover-docs-body", Static).update("")
        self.display = False

    # -------------------------------------------------------------- theme

    def _apply_theme(self) -> None:
        """Paint this card with the active theme (bg, fg + scrollbar palette)."""
        t = theme.active()
        self.styles.background = t.panel
        self.styles.color = t.fg
        apply_scrollbar_theme(self)
        self.refresh()
