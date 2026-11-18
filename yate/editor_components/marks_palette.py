"""Marks and jump-list overview palette screens (L2, self-owned UI).

Two read-only modal overlays driven by
:class:`yate.flows.navigation_flows.NavigationFlows` through injected
pure-data rows and callbacks (R13): the flow resolves marks and jump
entries against the session, this module only paints them and hands rows
back via ``on_jump`` / ``on_delete``.  Both screens reuse the shared
``OverlayScreen`` / ``OverlayScroll`` base (dismiss-on-esc/q/ctrl+c and
the R15 scrollbar wiring live there; the ``#overlay`` / ``#overlay-body``
ids are frozen by that sheet, R9 component-owned precedent).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from rich.text import Text
from textual.app import ComposeResult
from textual.events import Key
from textual.widgets import Static
from typing import override

from yate.session import JumpEntry

from yate.editor_components import theme
# Deliberate intra-package reuse of the shared overlay base (R13 theme
# subscription and R15 scrollbar wiring already live there) through the
# public aliases modals.py exposes for cross-component screens.
from yate.editor_components.modals import OverlayScreen, OverlayScroll

#: Column width of the document name in the overview header layout.
_DOC_WIDTH: int = 24

#: Message-line callback (text + severity kind, as ``Editor.message``).
type MessageFn = Callable[[str, str], None]


@dataclass(frozen=True)
class MarkRow:
    """One row of the marks overview: pure display data (R13 injection)."""

    uid: int
    name: str
    doc_name: str
    line_no: int  # 1-based for display
    preview: str


@dataclass(frozen=True)
class JumpRow:
    """One row of the jumps overview: stack side + entry + current flag."""

    entry: JumpEntry
    side: str  # "back" | "forward" | "current"
    current: bool


class _RowPaletteScreen(OverlayScreen):
    """Shared cursor / paint machinery for both overview screens.

    Rows render into the single ``#overlay-body`` static (the palette's
    results-rendering shape); ``on_key`` owns cursor movement and stops the
    event after consuming it so the focused scroll body never also scrolls
    on the same keystroke (R10, palette precedent).
    """

    def __init__(self) -> None:
        super().__init__()
        self._selected: int = 0

    # Subclass contract (concrete overrides only, no Protocols per R2):
    # ``_row_count`` / ``_body_text`` / ``_hint``; subclasses additionally
    # expose a ``rows`` property for the flows layer and the tests.
    def _row_count(self) -> int:
        raise NotImplementedError  # pragma: no cover - subclass contract

    def _body_text(self) -> Text:
        raise NotImplementedError  # pragma: no cover - subclass contract

    def _hint(self) -> str:
        raise NotImplementedError  # pragma: no cover - subclass contract

    @override
    def compose(self) -> ComposeResult:
        """Overlay box with the rendered rows and the key hint."""
        with OverlayScroll(id="overlay"):
            yield Static(id="overlay-body")
            yield Static(self._hint(), classes="hint")

    def on_mount(self) -> None:
        """Paint once, then follow theme broadcasts (R13)."""
        self._paint()
        theme.attach(self, self._paint)

    def on_unmount(self) -> None:
        """Detach from the theme broadcast."""
        theme.detach(self)

    def on_key(self, event: Key) -> None:
        """Move the selection cursor; stop the event once consumed (R10)."""
        if event.key not in ("up", "down") or self._row_count() == 0:
            return
        event.stop()
        event.prevent_default()
        delta = -1 if event.key == "up" else 1
        self._selected = (self._selected + delta) % self._row_count()
        self._paint()

    def _paint(self) -> None:
        """Re-render the body from the current rows and selection."""
        body = self.query_one("#overlay-body", Static)
        body.update(self._body_text())

    def _row_style(self, selected: bool) -> str:
        """Theme style for one row: the accent bar when selected."""
        t = theme.active()
        return f"{t.on_accent} on {t.accent}" if selected else t.fg_bright


class MarksScreen(_RowPaletteScreen):
    """Every set mark across open buffers: name, document, line, preview."""

    BINDINGS = [
        ("enter", "jump", "jump to mark"),
        ("d", "delete", "delete mark"),
    ]

    def __init__(
        self,
        rows: list[MarkRow],
        on_jump: Callable[[MarkRow], None],
        on_delete: Callable[[MarkRow], None],
    ) -> None:
        super().__init__()
        self._rows = list(rows)
        self._on_jump = on_jump
        self._on_delete = on_delete

    @property
    def rows(self) -> list[MarkRow]:
        """The display rows currently painted (shrinks on in-place delete)."""
        return self._rows

    @override
    def _row_count(self) -> int:
        return len(self._rows)

    @override
    def _body_text(self) -> Text:
        t = theme.active()
        text = Text()
        text.append(
            f"  {'NAME':<6}{'DOC':<{_DOC_WIDTH}}{'LINE':>5}  TEXT\n",
            style=t.fg_muted,
        )
        if not self._rows:
            text.append("  (no marks)\n", style=t.fg_muted)
            return text
        for index, row in enumerate(self._rows):
            selected = index == self._selected
            style = self._row_style(selected)
            text.append(" > " if selected else "   ", style=style)
            text.append(f"{row.name:<5}", style=style)
            text.append(f"{row.doc_name[:_DOC_WIDTH]:<{_DOC_WIDTH}}", style=style)
            text.append(f"{row.line_no:>5}", style=style)
            text.append(f"  {row.preview}\n", style=style)
        return text

    @override
    def _hint(self) -> str:
        return " enter jump   d delete   esc/q close "

    def action_jump(self) -> None:
        """Hand the selected row to the flow, then close the screen."""
        if not self._rows:
            return
        row = self._rows[self._selected]
        self._on_jump(row)
        self.dismiss()

    def action_delete(self) -> None:
        """Delete the selected mark in place; the screen stays open (AC6)."""
        if not self._rows:
            return
        row = self._rows.pop(self._selected)
        self._on_delete(row)
        if self._selected >= len(self._rows):
            self._selected = max(0, len(self._rows) - 1)
        self._paint()


class JumpsScreen(_RowPaletteScreen):
    """The jump history: back stack (old to new), current row, forward stack."""

    BINDINGS = [
        ("enter", "jump", "jump to entry"),
    ]

    def __init__(
        self,
        rows: list[JumpRow],
        on_jump: Callable[[JumpRow], None],
        message: MessageFn,
    ) -> None:
        super().__init__()
        self._rows = list(rows)
        self._on_jump = on_jump
        self._message = message

    @property
    def rows(self) -> list[JumpRow]:
        """The display rows currently painted."""
        return self._rows

    @override
    def _row_count(self) -> int:
        return len(self._rows)

    @override
    def _body_text(self) -> Text:
        t = theme.active()
        text = Text()
        text.append(
            f"  {'STACK':<10}{'DOC':<{_DOC_WIDTH}}{'LINE':>5}  COL\n",
            style=t.fg_muted,
        )
        if not self._rows:
            text.append("  (no jumps)\n", style=t.fg_muted)
            return text
        for index, row in enumerate(self._rows):
            if row.current:
                # Current pointer position between the stacks (AC3).
                text.append(" > ", style=t.fg_muted)
                text.append(
                    f"{'current':<9}{row.entry.path[:_DOC_WIDTH]:<{_DOC_WIDTH}}"
                    f"{row.entry.row + 1:>5}  {row.entry.col + 1}\n",
                    style=t.fg_muted,
                )
                continue
            style = self._row_style(index == self._selected)
            text.append(" > " if index == self._selected else "   ", style=style)
            text.append(
                f"{row.side:<9}{row.entry.path[:_DOC_WIDTH]:<{_DOC_WIDTH}}"
                f"{row.entry.row + 1:>5}  {row.entry.col + 1}\n",
                style=style,
            )
        return text

    @override
    def _hint(self) -> str:
        # D7: a direct jump pushes, which clears the forward branch -- say so.
        return " enter jump (clears forward)   esc/q close "

    def action_jump(self) -> None:
        """Hand the selected entry to the flow, then close the screen.

        Enter on the current row stays put and hints instead: that is where
        the editor already sits, so there is nothing to jump to.
        """
        if not self._rows:
            return
        row = self._rows[self._selected]
        if row.current:
            self._message("already at latest jump", "info")
            return
        self._on_jump(row)
        self.dismiss()
