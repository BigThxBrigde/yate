"""The command / message line at the very bottom (Textual Input based)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.events import Key
from textual.widgets import Input, Static

from . import theme
from .icons import SEARCH, TERMINAL

if TYPE_CHECKING:
    from yate.app import YateApp

# prompt prefixes per mode: (prefix, Theme attribute name for the color)
PREFIXES = {
    "command": (":", "yellow"),
    "find": (SEARCH, "accent"),
    "find_back": ("?", "accent"),
    "replace_find": ("Replace:", "accent2"),
    "replace_with": ("With:", "accent2"),
    "shell": (TERMINAL, "green"),
    "open": ("Open: ", "fg_bright"),
    "save": ("Save as: ", "fg_bright"),
}

#: message kind -> Theme attribute name for the color
MESSAGE_COLORS = {"info": "fg_bright", "error": "red", "warn": "yellow", "ok": "green"}


class CommandInput(Input):
    """Input with command history (up/down) and escape-to-cancel."""

    DEFAULT_CSS = """
    CommandInput {
        background: $surface;
        border: none;
        height: 1;
        padding: 0;
    }
    """

    def __init__(self, yate: YateApp) -> None:
        super().__init__()
        self.yate = yate
        self.history: list[str] = []
        self._hist_index: int = -1

    def push_history(self, text: str) -> None:
        if text and (not self.history or self.history[-1] != text):
            self.history.append(text)
        self.reset_history_cursor()

    def reset_history_cursor(self) -> None:
        """Place the history cursor after the newest entry."""
        self._hist_index = len(self.history)

    def on_key(self, event: Key) -> None:
        if event.key in ("escape", "ctrl+c"):
            event.stop()
            event.prevent_default()
            self.yate.on_prompt_cancel()
            return
        if event.key == "up":
            event.stop()
            event.prevent_default()
            if self.history and self._hist_index > 0:
                self._hist_index -= 1
                self.value = self.history[self._hist_index]
                self.cursor_position = len(self.value)
            return
        if event.key == "down":
            event.stop()
            event.prevent_default()
            if self._hist_index < len(self.history) - 1:
                self._hist_index += 1
                self.value = self.history[self._hist_index]
            else:
                self._hist_index = len(self.history)
                self.value = ""
            self.cursor_position = len(self.value)
            return
        # All other keys are handled by Input's own _on_key (textual picks it
        # up from the MRO automatically); do not stop the event.


class PromptBar(Horizontal):
    """Bottom bar: either an editable prompt or a one-line message."""

    DEFAULT_CSS = """
    PromptBar {
        height: 1;
        background: $surface;
        padding: 0;
    }
    PromptBar Static {
        height: 1;
        padding: 0;
        background: $surface;
    }
    PromptBar #cl_prompt {
        width: auto;
        min-width: 2;
    }
    PromptBar #cl_msg {
        height: 1;
    }
    PromptBar CommandInput {
        width: 1fr;
    }
    """

    def __init__(self, yate: YateApp) -> None:
        super().__init__()
        self.yate = yate
        self.prompt = Static("", id="cl_prompt")
        self.input = CommandInput(yate)
        self.message = Static(" Ready. Press F1 for help.", id="cl_msg")
        self.active_mode: str | None = None

    def compose(self) -> ComposeResult:
        yield self.prompt
        yield self.input
        yield self.message

    def on_mount(self) -> None:
        t = theme.active()
        self.styles.background = t.panel
        self.message.styles.background = t.panel
        self.prompt.styles.background = t.panel
        self.input.styles.background = t.panel
        self.input.display = False
        self.prompt.display = False

    # ------------------------------------------------------------ states

    def activate(self, mode: str, initial: str = "", placeholder: str = "") -> None:
        prefix, attr = PREFIXES.get(mode, (":", "yellow"))
        self.active_mode = mode
        self.message.display = False
        self.prompt.display = True
        self.prompt.update(prefix + " ")
        self.prompt.styles.color = getattr(theme.active(), attr)
        self.input.display = True
        self.input.disabled = False
        self.input.value = initial
        self.input.placeholder = placeholder
        self.input.cursor_position = len(initial)
        self.input.reset_history_cursor()
        self.input.focus()

    def show_message(self, text: str, color: str | None = None, kind: str = "info") -> None:
        self.active_mode = None
        self.input.display = False
        self.prompt.display = False
        self.message.display = True
        if color is None:
            color = getattr(theme.active(), MESSAGE_COLORS.get(kind, "fg_bright"))
        self.message.update(f"[{color}]{text}[/]")

    def idle(self, text: str = " Ready. Press F1 for help.") -> None:
        self.show_message(text, theme.active().fg_dim)
