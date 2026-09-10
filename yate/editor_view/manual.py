"""Read-only viewer for the bundled user manual.

Renders ``yate/resources/manual.md`` with Textual's markdown widget.
Textual's built-in Catppuccin theme is applied while the screen is open
so headings, code blocks and tables match yate's palette; the app's own
theme is restored on close.
"""

from __future__ import annotations

from importlib.resources import files
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Markdown, Static

if TYPE_CHECKING:
    from yate.app import YateApp


def load_manual_markdown() -> str:
    """Return the bundled manual as markdown text."""
    return files("yate.resources").joinpath("manual.md").read_text(encoding="utf-8")


class ManualScreen(ModalScreen[None]):
    """The user manual, rendered as read-only markdown."""

    BINDINGS = [
        ("escape", "dismiss", "close"),
        ("q", "dismiss", "close"),
        ("ctrl+c", "dismiss", "close"),
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
    ManualScreen #manual-scroll {
        height: 1fr;
    }
    ManualScreen .hint {
        height: 1;
        color: $text-muted;
        text-align: center;
    }
    """

    def __init__(self, yate: YateApp) -> None:
        super().__init__()
        self.yate = yate
        self._prev_theme: str | None = None

    def compose(self) -> ComposeResult:
        with Vertical(id="manual-box"):
            with VerticalScroll(id="manual-scroll"):
                yield Markdown(load_manual_markdown(), id="manual-md")
            yield Static(" press esc or q to close  ·  pgup/pgdn or wheel to scroll ",
                         classes="hint")

    def on_screen_resume(self) -> None:
        # the markdown widget's styles follow textual design tokens; the
        # built-in catppuccin theme matches yate's default mocha palette
        self._prev_theme = self.yate.theme
        self.yate.theme = "catppuccin-mocha"

    def on_screen_suspend(self) -> None:
        if self._prev_theme is not None:
            self.yate.theme = self._prev_theme
            self._prev_theme = None
