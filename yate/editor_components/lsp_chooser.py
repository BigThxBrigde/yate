"""Read-only L2 chooser screen for LSP results (definitions, references).

Driven entirely by injected pure-data rows and a ``on_pick`` callback
(R13): the caller resolves the LSP query and owns the follow-up
navigation, this module only paints the rows and hands the selected one
back.  No App handle and no LSP state live here.  The screen reuses the
shared ``OverlayScreen`` / ``OverlayScroll`` base (dismiss-on-esc/q/ctrl+c
and the R15 slim scrollbar wiring live there; the ``#overlay`` /
``#overlay-body`` ids are frozen by that sheet, R9 component-owned
precedent -- marks_palette).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from rich.text import Text
from textual.app import ComposeResult
from textual.events import Key
from textual.widgets import Static
from typing import override

from yate.editor_lsp.protocol import uri_file_name

from yate.editor_components import theme
from yate.editor_components.modals import OverlayScreen, OverlayScroll

#: Column width of the label / detail fields in the painted layout.
_LABEL_WIDTH: int = 32
_DETAIL_WIDTH: int = 20


@dataclass(frozen=True)
class LspRow:
    """One row of the chooser: pure display data (R13 injection).

    Positions are 0-based (``row`` / ``col`` / ``end_row`` / ``end_col``).
    """

    label: str
    detail: str
    uri: str
    row: int
    col: int
    end_row: int
    end_col: int
    kind: str


class LspChooserScreen(OverlayScreen):
    """Overlay chooser over LSP result rows; enter hands a row back."""

    BINDINGS = [
        ("enter", "pick", "select row"),
    ]

    def __init__(
        self, rows: list[LspRow], title: str, on_pick: Callable[[LspRow], None]
    ) -> None:
        super().__init__()
        self._rows = list(rows)
        self._title = title
        self._on_pick = on_pick
        self._selected: int = 0

    @property
    def rows(self) -> list[LspRow]:
        """The display rows currently painted."""
        return self._rows

    @property
    def selected_row(self) -> LspRow | None:
        """The currently selected row, or ``None`` with no rows (tests)."""
        if not self._rows:
            return None
        return self._rows[self._selected]

    @override
    def compose(self) -> ComposeResult:
        """Overlay box with the rendered rows and the key hint."""
        with OverlayScroll(id="overlay"):
            yield Static(id="overlay-body")
            yield Static(" enter select   esc/q close ", classes="hint")

    def on_mount(self) -> None:
        """Paint once, then follow theme broadcasts (R13)."""
        self._paint()
        theme.attach(self, self._paint)

    def on_unmount(self) -> None:
        """Detach from the theme broadcast."""
        theme.detach(self)

    def on_key(self, event: Key) -> None:
        """Move the selection cursor; stop the event once consumed (R10)."""
        if event.key not in ("up", "down") or not self._rows:
            return
        event.stop()
        event.prevent_default()
        delta = -1 if event.key == "up" else 1
        self._selected = (self._selected + delta) % len(self._rows)
        self._paint()

    def _paint(self) -> None:
        """Re-render the body from the current rows and selection."""
        body = self.query_one("#overlay-body", Static)
        body.update(self._body_text())

    def _body_text(self) -> Text:
        """Header with the title, then one painted line per result row."""
        t = theme.active()
        text = Text()
        text.append(f"  {self._title}\n", style=f"bold {t.accent}")
        if not self._rows:
            text.append("  (no results)\n", style=t.fg_muted)
            return text
        for index, row in enumerate(self._rows):
            selected = index == self._selected
            style = (
                f"{t.on_accent} on {t.accent}" if selected else t.fg_bright
            )
            name = uri_file_name(row.uri)
            text.append(" > " if selected else "   ", style=style)
            text.append(f"{row.label[:_LABEL_WIDTH]:<{_LABEL_WIDTH}}", style=style)
            text.append(f"{row.detail[:_DETAIL_WIDTH]:<{_DETAIL_WIDTH}}", style=style)
            text.append(f"  {name}:{row.row + 1}\n", style=style)
        return text

    def action_pick(self) -> None:
        """Hand the selected row to the callback, then close the screen.

        The dismiss runs in ``finally`` (m7): a pick callback that raises
        must not strand the modal overlay on screen.
        """
        if not self._rows:
            return
        row = self._rows[self._selected]
        try:
            self._on_pick(row)
        finally:
            self.dismiss()
