"""The command / message line at the very bottom (Textual Input based).

The bar owns the whole prompt lifecycle: a caller (the explorer, a key
binding, a command) calls :meth:`PromptBar.activate` with the callbacks for
that prompt and the bar handles typing, history, tab completion, submission,
cancellation and focus restore by itself.  It never needs a host protocol:
the few editor-side primitives it uses (completion candidates, cancel hook,
focus and repaint) are injected callables.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, override

from rich.markup import escape
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.events import Key
from textual.widgets import Input, Static

from yate.logs import tracing
from yate.paths import load_tcss

from yate.editor_view import theme
from yate.editor_view.icons import SEARCH, TERMINAL

log = tracing.get_logger(__name__)

#: ``completer(text, mode) -> candidates`` -- the prompt's completion source
#: (LSP, history, buffers, ...); *mode* is the active prompt mode, whose
#: accepted prefixes live in :data:`PREFIXES`.
type PromptCompleter = Callable[[str, str], list[str]]

# prompt prefixes per mode: (prefix, Theme attribute name for the color)
PREFIXES: dict[str, tuple[str, str]] = {
    "command": (":", "yellow"),
    "goto": (":", "yellow"),
    "find": (SEARCH, "accent"),
    "find_back": ("?", "accent"),
    "replace_find": ("Replace:", "accent2"),
    "replace_with": ("With:", "accent2"),
    "replace_confirm": ("Replace:", "accent2"),
    "shell": (TERMINAL, "green"),
    "open": ("Open: ", "fg_bright"),
    "save": ("Save as: ", "fg_bright"),
    "new_file": ("New file: ", "green"),
    "new_dir": ("New folder: ", "accent"),
    "rename": ("Rename: ", "yellow"),
    "delete": ("Delete? ", "red"),
}

#: message kind -> Theme attribute name for the color
MESSAGE_COLORS: dict[str, str] = {
    "info": "fg_bright", "error": "red", "warn": "yellow", "ok": "green",
}


def prefix_spec(mode: str) -> tuple[str, str]:
    """``(prefix, Theme attribute name)`` for a prompt *mode*.

    Falls back to the command-mode spec for unknown modes; ``activate`` and
    :meth:`PromptBar._apply_theme` both go through here so the default never
    drifts between the two call sites.
    """
    return PREFIXES.get(mode, (":", "yellow"))


#: Where the message line's current text came from; the LSP echo only clears
#: its own message (``owner == "lsp"``) when the cursor leaves the diagnostic.
OWNER_APP: str = "app"
OWNER_LSP: str = "lsp"
OWNER_IDLE: str = "idle"
#: The tab-completion candidate string shown by ``show_candidates``.
OWNER_CANDIDATES: str = "candidates"


class CommandInput(Input):
    """Input with command history (up/down) and escape-to-cancel."""

    DEFAULT_CSS = load_tcss("command-input.tcss")

    def __init__(self, bar: PromptBar) -> None:
        super().__init__()
        self.bar = bar
        self.history: list[str] = []
        self._hist_index: int = -1
        # bash-style tab completion state
        self._tab_matches: list[str] = []
        self._tab_index: int = -1

    def push_history(self, text: str) -> None:
        """Append *text* unless it duplicates the newest entry, then reset the cursor."""
        if text and (not self.history or self.history[-1] != text):
            self.history.append(text)
        self.reset_history_cursor()

    def reset_history_cursor(self) -> None:
        """Place the history cursor after the newest entry."""
        self._hist_index = len(self.history)

    def reset_tab_state(self) -> None:
        """Drop any pending tab-completion round.

        Public because :meth:`PromptBar.activate` (the single prompt entry
        point) must also be able to clear a stale round left over from the
        previous prompt.
        """
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
        """Emacs-style two-phase tab completion on the current prompt value.

        First Tab: complete to the longest common prefix of all matches and
        list the remaining candidates on the message line instead of applying
        one right away (a single match is still applied at once).  The next
        Tab applies the first candidate, and further Tabs cycle through every
        match.  Any edit key / escape resets the round.
        """
        current = self.value
        mode = self.bar.active_mode
        if mode is None:
            return
        matches = self.bar.completer(current, mode)
        if not matches:
            self.reset_tab_state()
            self.bar.clear_candidates()
            return
        if len(matches) == 1:
            self._apply_value(matches[0])
            self.reset_tab_state()
            self.bar.clear_candidates()
            return
        # Repeated Tab with the value still at one of the applied matches ->
        # cycle to the next one.
        if self._tab_matches and self._tab_index >= 0 \
                and current in self._tab_matches:
            self._tab_index = (self._tab_index + 1) % len(self._tab_matches)
            self._apply_value(self._tab_matches[self._tab_index])
            self.bar.clear_candidates()
            return
        # Candidates from the first phase are still pending: this Tab applies
        # the first one and starts cycling from there.
        if self._tab_matches and self._tab_index == -1:
            self._tab_index = 0
            self._apply_value(self._tab_matches[0])
            self.bar.clear_candidates()
            return
        # New completion round: extend to the common prefix if it is longer
        # than what the user typed, show the remaining candidates and wait
        # for the next Tab instead of applying a value right away.
        lcp = self._common_prefix(matches)
        self._tab_matches = matches
        self._tab_index = -1
        if len(lcp) > len(current):
            self._apply_value(lcp)
            remaining = [m for m in matches if m != lcp]
            if remaining:
                self.bar.show_candidates(remaining)
            else:
                self.bar.clear_candidates()
        else:
            self.bar.show_candidates(matches)

    def on_key(self, event: Key) -> None:
        """Handle cancel/tab-completion/history keys; leave the rest to Input."""
        # Confirm-style prompts (e.g. the per-match replace loop) intercept
        # every key before escape/cancel handling, so their own escape means
        # "leave the loop", not "cancel the prompt".  Only a consumed key is
        # stopped (R10); with no hook installed nothing changes here.
        hook = self.bar.key_hook
        if hook is not None and hook(event.key):
            event.stop()
            event.prevent_default()
            # A consumed key ends any pending completion round even though
            # the hook swallows it before the tab branch can see it.
            self.reset_tab_state()
            return
        if event.key in ("escape", "ctrl+c"):
            event.stop()
            event.prevent_default()
            self.reset_tab_state()
            self.bar.cancel()
            return
        if event.key == "tab":
            event.stop()
            event.prevent_default()
            self._do_tab_completion()
            return
        # any other key ends an active tab-completion round and drops the
        # candidate string shown on the message line
        self.reset_tab_state()
        self.bar.clear_candidates()
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

    DEFAULT_CSS = load_tcss("prompt-bar.tcss")

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
        self._on_submit: Callable[[str], None] | None = None
        self._on_changed: Callable[[str], None] | None = None
        self._refocus: Callable[[], None] | None = None
        #: Single-key confirm hook (confirm-style prompts); receives the raw
        #: ``event.key``, returns True when the key was consumed.  Public
        #: (like ``cancel_hook``) because CommandInput reads it from its own
        #: ``on_key`` before the Input sees any key.
        self.key_hook: Callable[[str], bool] | None = None
        #: ``(text, Theme attr)`` of the current message line; re-rendered
        #: with the active palette on theme changes (``None`` = no message).
        self._message: tuple[str, str] | None = None

    @override
    def compose(self) -> ComposeResult:
        """Lay out the prompt prefix, input and message widgets in a row."""
        yield self.prompt
        yield self.input
        yield self.message

    #: unsubscribe hook from :func:`yate.editor_view.theme.subscribe`;
    #: ``None`` while not mounted.
    _theme_unsubscribe: theme.Unsubscribe | None = None

    def on_mount(self) -> None:
        """Own the theme painting and register for theme-change updates."""
        self._apply_theme()
        theme.attach(self, self._apply_theme)
        self.input.display = False
        self.prompt.display = False

    def on_unmount(self) -> None:
        """Detach from the theme broadcast."""
        theme.detach(self)

    def _apply_theme(self) -> None:
        """Paint the bar and its children with the active theme."""
        t = theme.active()
        self.styles.background = t.panel
        self.message.styles.background = t.panel
        self.prompt.styles.background = t.panel
        self.input.styles.background = t.panel
        # An open prompt's prefix color was resolved at activate() time --
        # re-derive it so a theme switch is visible immediately.
        if self.active_mode is not None:
            self.prompt.styles.color = getattr(t, prefix_spec(self.active_mode)[1])
        # The message color is baked into its markup at write time; re-render
        # with the new palette (text and owner semantics untouched).
        if self.message.display:
            self._render_message()

    # ------------------------------------------------------------ states

    def activate(
        self,
        mode: str,
        *,
        initial: str = "",
        placeholder: str = "",
        on_submit: Callable[[str], None] | None = None,
        on_changed: Callable[[str], None] | None = None,
        on_key: Callable[[str], bool] | None = None,
        refocus: Callable[[], None] | None = None,
    ) -> bool:
        """Show the prompt in *mode*; ``False`` when the bar is not mounted.

        *on_submit* receives the submitted text; when the handler neither
        opens a follow-up prompt nor reports anything, the bar closes itself
        and restores focus (``refocus``, default: the editor).  *on_key*
        (confirm prompts) intercepts every key before the Input sees it;
        returning True consumes the key.
        """
        if not self.is_mounted:
            return False
        log.debug("prompt activate: mode=%s", mode)
        # A stale tab round from the previous prompt must not leak into this
        # one: reset the completion state up front (activate is the single
        # entry point, so every prompt starts from a clean round).
        self.input.reset_tab_state()
        self.clear_candidates()
        prefix, attr = prefix_spec(mode)
        self.active_mode = mode
        self._on_submit = on_submit
        self._on_changed = on_changed
        self.key_hook = on_key
        self._refocus = refocus
        # Either a prompt is active or a message is shown -- never both; the
        # stored (text, attr) of the previous message is dropped here.
        self._message = None
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
        self._show_message(text, MESSAGE_COLORS.get(kind, "fg_bright"))

    def show_candidates(self, candidates: list[str]) -> None:
        """List tab-completion *candidates* on the message slot (Emacs style).

        Formatted as ``{opt1, opt2}`` and truncated to the input width with a
        ``...`` hint when it does not fit.  The prompt stays active: the
        message slot is only shown while the candidates are pending (cleared
        by :meth:`clear_candidates`, escape or any edit key).
        """
        bar = ", ".join(candidates)
        display = "{" + bar
        max_width = self.input.size.width if self.input.size.width else 40
        if len(display) > max_width:
            display = display[: max_width - 3] + "..."
        display += "}"
        # escape(): candidates are external text (file names, command names)
        # and may contain brackets -- without escaping, Rich would parse
        # "[test].py" as a markup tag and mangle the shown string.
        self.message.update(escape(display))
        self.message.display = True
        self.owner = OWNER_CANDIDATES

    def clear_candidates(self) -> None:
        """Drop the candidate string shown by :meth:`show_candidates`.

        The message slot goes back to hidden: while a prompt is active the
        bar shows either the prompt or a message, never both.
        """
        if self.owner == OWNER_CANDIDATES:
            self.message.display = False
            self.owner = OWNER_IDLE

    def idle(self, text: str = " Ready. Press F1 for help.") -> None:
        """Back to the idle hint line."""
        self.owner = OWNER_IDLE
        self._show_message(text, "fg_dim")

    def _show_message(self, text: str, attr: str) -> None:
        """Show *text* painted with the theme color named by *attr*."""
        self.active_mode = None
        self._on_submit = None
        self._on_changed = None
        self.key_hook = None
        self.input.display = False
        self.prompt.display = False
        self.message.display = True
        self._message = (text, attr)
        self._render_message()

    def _render_message(self) -> None:
        """(Re)render the stored message with the active theme's color.

        Purely visual: neither the message state nor the ``owner`` semantics
        are touched, so a theme change never disturbs the LSP echo contract.
        """
        if self._message is None:
            return
        text, attr = self._message
        # escape(): message text is external (LSP diagnostics, file names,
        # OS errors) and may contain brackets -- without escaping, Rich would
        # parse "[test].py" as a markup tag and mangle or crash the render.
        self.message.update(
            f"[{getattr(theme.active(), attr)}]{escape(text)}[/]"
        )

    def cancel(self) -> None:
        """Esc / ctrl+c on the prompt line: run the cancel hook and close."""
        log.debug("prompt cancelled: mode=%s", self.active_mode)
        self.key_hook = None  # a confirm hook never survives a cancel
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
        """Record history, run the submit handler, then close or chain."""
        mode = self.active_mode
        if mode is None or event.input is not self.input:
            return
        handler = self._on_submit
        self.input.push_history(event.value)
        log.debug("prompt submit: mode=%s value=%r", mode, event.value)
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
        """Forward live input changes to the active prompt's on_changed hook."""
        if event.input is not self.input or self._on_changed is None:
            return
        self._on_changed(event.value)
