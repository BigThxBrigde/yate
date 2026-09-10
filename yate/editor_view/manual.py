"""Read-only viewer for the bundled user manual.

Renders ``yate/resources/manual.<lang>.md`` with Textual's markdown
widget.  Textual's built-in Catppuccin theme is applied while the screen
is open (switched by the app *before* this screen is pushed, so the very
first frame is already themed) so headings, code blocks and tables match
yate's palette.

Tables are laid out by a CSS grid that squeezes cells when the table is
container-bound; auto-width keeps cells on one line so the keylines of
CJK tables stay aligned.
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
    /* table cells default to a squeezed 1fr grid which wraps long CJK
       labels and breaks the keyline alignment; auto-width renders each
       cell on a single line with clean borders */
    ManualScreen MarkdownTable {
        width: auto;
    }
    """

    def __init__(self, yate: YateApp, lang: str = "en") -> None:
        super().__init__()
        self.yate = yate
        self._lang = lang

    def compose(self) -> ComposeResult:
        with Vertical(id="manual-box"):
            with VerticalScroll(id="manual-scroll"):
                yield Markdown(load_manual_markdown(self._lang), id="manual-md")
            yield Static(" press esc or q to close  ·  pgup/pgdn or wheel to scroll ",
                         classes="hint")
