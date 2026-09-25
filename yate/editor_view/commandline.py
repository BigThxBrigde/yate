"""The command / message line at the very bottom (Textual Input based).

The bar owns the whole prompt lifecycle: a caller (the explorer, a key
binding, a command) calls :meth:`PromptBar.activate` with the callbacks for
that prompt and the bar handles typing, history, tab completion, submission,
cancellation and focus restore by itself.  It never needs a host protocol:
the few editor-side primitives it uses (completion candidates, cancel hook,
focus and repaint) are injected callables.
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.events import Key
from textual.widgets import Input, Static

from . import theme
from .icons import SEARCH, TERMINAL

#: ``(text, mode) -> candidates`` -- bash-style tab completion.
PromptCompleter = Callable[[str, str], list[str]]

# prompt prefixes per mode: (prefix, Theme attribute name for the color)
PREFIXES = {
    "command": (":", "yellow"),
    "goto": (":", "yellow"),
    "find": (SEARCH, "accent"),
    "find_back": ("?", "accent"),
    "replace_find": ("Replace:", "accent2"),
    "replace_with": ("With:", "accent2"),
    "shell": (TERMINAL, "green"),
    "open": ("Open: ", "fg_bright"),
    "save": ("Save as: ", "fg_bright"),
    "new_file": ("New file: ", "green"),
    "new_dir": ("New folder: ", "accent"),
    "rename": ("Rename: ", "yellow"),
    "delete": ("Delete? ", "red"),
}

#: message kind -> Theme attribute name for the color
MESSAGE_COLORS = {"info": "fg_bright", "error": "red", "warn": "yellow", "ok": "green"}

#: Where the message line's current text came from; the LSP echo only clears
#: its own message (``owner == "lsp"``) when the cursor leaves the diagnostic.
OWNER_APP = "app"
OWNER_LSP = "lsp"
OWNER_IDLE = "idle"


class CommandInput(Input):
    """Input with command history (up/down) and escape-to-cancel."""

    DEFAULT_CSS = """
    CommandInput {
        background: $surface;
        border: none !important;
        height: 1;
        padding: 0;
    }
    /* Textual's built-in Input:focus adds a tall border which would cover
       the only content row of this height-1 widget, hiding typed text. */
    CommandInput:focus {
        border: none !important;
        background-tint: transparent;
    }
    """

    def __init__(self, bar: PromptBar) -> None:
        super().__init__()
        self.bar = bar
        self.history: list[str] = []
        self._hist_index: int = -1
        # bash-style tab completion state
        self._tab_matches: list[str] = []
        self._tab_index: int = -1

    def push_history(self, text: str) -> None:
        if text and (not self.history or self.history[-1] != text):
            self.history.append(text)
        self.reset_history_cursor()

    def reset_history_cursor(self) -> None:
        """Place the history cursor after the newest entry."""
        self._hist_index = len(self.history)

    def _reset_tab_state(self) -> None:
        self._tab_matches = []
        self._tab_index = -1

    def _apply_value(self, text: str) -> None:
        self.value = text
        self.cursor_position = len(text)

    @staticmethod
    def _common_prefix(words: list[str]) -> str:
        if not words:
            return ""
        first = words[0]
        for i, ch in enumerate(first):
            for w in words[1:]:
                if i >= len(w) or w[i] != ch:
                    return first[:i]
        return first

    def _do_tab_completion(self) -> None:
        """Bash-style tab completion on the current prompt value.

        First Tab: complete to the longest common prefix of all matches; with
        a single match it is applied at once.  Repeated Tabs (while the value
        has not been edited) cycle through every match.
        """
        current = self.value
        mode = self.bar.active_mode
        if mode is None:
            return
        matches = self.bar.completer(current, mode)
        if not matches:
            self._reset_tab_state()
            return
        if len(matches) == 1:
            self._apply_value(matches[0])
            self._reset_tab_state()
            return
        # Repeated Tab with the value still at one of the matches -> cycle.
        if self._tab_matches and current in self._tab_matches:
            self._tab_index = (self._tab_index + 1) % len(self._tab_matches)
            self._apply_value(self._tab_matches[self._tab_index])
            return
        # New completion round: extend to the common prefix if it is longer
        # than what the user typed, otherwise start cycling from the first.
        lcp = self._common_prefix(matches)
        self._tab_matches = matches
        if len(lcp) > len(current):
            self._apply_value(lcp)
            self._tab_index = -1
        else:
            self._tab_index = 0
            self._apply_value(matches[0])

    def on_key(self, event: Key) -> None:
        if event.key in ("escape", "ctrl+c"):
            event.stop()
            event.prevent_default()
            self.bar.cancel()
            return
        if event.key == "tab":
            event.stop()
            event.prevent_default()
            self._do_tab_completion()
            return
        # any other key ends an active tab-completion round
        self._reset_tab_state()
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
    """Bottom bar: either an editable prompt or a one-line message.

    One prompt at a time; :meth:`activate` installs the callbacks of the
    active prompt and :meth:`write` replaces the line with a message.
    """

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

    def __init__(
        self,
        completer: PromptCompleter,
        *,
        cancel_hook: Callable[[], None],
        focus_editor: Callable[[], None],
        refresh: Callable[[], None],
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.completer = completer
        self.cancel_hook = cancel_hook
        self.focus_editor = focus_editor
        #: Editor repaint hook (named apart from ``Widget.refresh``).
        self.refresh_ui = refresh
        self.prompt = Static("", id="cl_prompt")
        self.input = CommandInput(self)
        self.message = Static(" Ready. Press F1 for help.", id="cl_msg")
        self.active_mode: str | None = None
        #: Who wrote the current message line (see ``OWNER_*``).
        self.owner = OWNER_IDLE
        self._on_submit: Optional[Callable[[str], None]] = None
        self._on_changed: Optional[Callable[[str], None]] = None
        self._refocus: Optional[Callable[[], None]] = None

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

    def activate(
        self,
        mode: str,
        *,
        initial: str = "",
        placeholder: str = "",
        on_submit: Optional[Callable[[str], None]] = None,
        on_changed: Optional[Callable[[str], None]] = None,
        refocus: Optional[Callable[[], None]] = None,
    ) -> bool:
        """Show the prompt in *mode*; ``False`` when the bar is not mounted.

        *on_submit* receives the submitted text; when the handler neither
        opens a follow-up prompt nor reports anything, the bar closes itself
        and restores focus (``refocus``, default: the editor).
        """
        if not self.is_mounted:
            return False
        prefix, attr = PREFIXES.get(mode, (":", "yellow"))
        self.active_mode = mode
        self._on_submit = on_submit
        self._on_changed = on_changed
        self._refocus = refocus
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
        return True

    def write(self, text: str, kind: str = "info", owner: str = OWNER_APP) -> None:
        """Replace the prompt line with the message *text*."""
        self.owner = owner
        self._show_message(text, getattr(theme.active(), MESSAGE_COLORS.get(kind, "fg_bright")))

    def idle(self, text: str = " Ready. Press F1 for help.") -> None:
        """Back to the idle hint line."""
        self.owner = OWNER_IDLE
        self._show_message(text, theme.active().fg_dim)

    def _show_message(self, text: str, color: Optional[str]) -> None:
        self.active_mode = None
        self._on_submit = None
        self._on_changed = None
        self.input.display = False
        self.prompt.display = False
        self.message.display = True
        self.message.update(f"[{color or theme.active().fg_bright}]{text}[/]")

    def cancel(self) -> None:
        """Esc / ctrl+c on the prompt line: run the cancel hook and close."""
        self.cancel_hook()
        self.idle()
        self._finish()

    def _finish(self) -> None:
        """The prompt line is done: restore focus and repaint."""
        refocus = self._refocus or self.focus_editor
        self._refocus = None
        refocus()
        self.refresh_ui()

    # ---------------------------------------------------------- submission

    def on_input_submitted(self, event: Input.Submitted) -> None:
        mode = self.active_mode
        if mode is None or event.input is not self.input:
            return
        handler = self._on_submit
        self.input.push_history(event.value)
        if handler is not None:
            handler(event.value)
        if self.active_mode is not None:
            if self.active_mode != mode:
                return  # a follow-up prompt is active (replace_with)
            # The handler neither reported anything nor opened a follow-up
            # prompt (``:bn``, an empty find string, ...).  Close the line
            # instead of leaving it open with stale text: a focused prompt
            # Input swallows F5, so the next command would never start.
            self.idle()
        self._finish()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input is not self.input or self._on_changed is None:
            return
        self._on_changed(event.value)
