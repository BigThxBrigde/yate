"""Prompt-driven flows: find, live-search highlight, replace, go-to-line.

Extracted from :mod:`yate.editor` (review 20260926 #5).  Every flow here is
synchronous session/view interaction -- no app or screen involvement.  Like
:class:`~yate.flows.completion_flows.CompletionFlows` this module is constructed by
the editor and never imports upward.
"""

from __future__ import annotations

import re
from collections.abc import Callable

from yate.editor_view.commandline import PromptBar
from yate.editor_view.panes import PaneManager
from yate.flows import MessageFn
from yate.session import EditorSession


class PromptFlows:
    """Runs the search / replace / go-to-line flows on the prompt line."""

    def __init__(
        self,
        session: EditorSession,
        panes: PaneManager,
        prompt: PromptBar,
        message: MessageFn,
        readonly_notice: Callable[[], None],
        refresh: Callable[[], None],
    ) -> None:
        self.session = session
        self.panes = panes
        self.prompt = prompt
        self._message = message
        self._readonly_notice = readonly_notice
        self._refresh = refresh
        # Per-match confirm loop state (``_do_replace``); zeroed when the
        # loop ends so a stale replacement never survives into the next one.
        self._replacement: str = ""
        self._confirm_total: int = 0
        self._confirm_done: int = 0

    def find_prompt(self, forward: bool) -> None:
        """Open the search prompt (``/``, ``?``, ctrl+f)."""
        self.prompt.activate(
            "find" if forward else "find_back",
            initial=self.session.search.query,
            placeholder="search pattern (enter to jump, esc to cancel)",
            on_submit=lambda text: self._submit_search(text, forward),
            on_changed=self._live_search,
        )

    def _live_search(self, text: str) -> None:
        """Highlight matches while the search prompt is being typed."""
        self.session.search.update(text, self.session.buffer)
        for view in self.panes.views_for(self.session.doc):
            view.refresh()

    def _submit_search(self, text: str, forward: bool) -> None:
        if not text:
            return
        self.find_next(forward)

    def find_next(self, forward: bool) -> None:
        """``n``/``N``: jump to the next / previous match."""
        search = self.session.search
        if not search.query:
            self._message("no active search — press / to start one", "warn")
            return
        match = search.next(self.session.buffer, forward=forward)
        if match is None:
            self._message(f"no matches for {search.query!r}", "warn")
        else:
            self._message(
                f"[{search.index + 1}/{len(search.matches)}] {search.query!r}",
                "info",
            )

    def replace_prompt(self) -> None:
        """``:s`` style replace: ask for the search text."""
        self.prompt.activate(
            "replace_find",
            placeholder="text to find",
            on_submit=self._replace_find_step,
        )

    def _replace_find_step(self, find: str) -> None:
        find = find.strip()
        if not find:
            self._message("replace cancelled", "info")
            return
        self.prompt.activate(
            "replace_with",
            placeholder="replacement text",
            on_submit=lambda replacement: self._do_replace(find, replacement),
        )

    def _do_replace(self, find: str, replacement: str) -> None:
        """Start the per-match confirm loop for *find* -> *replacement*.

        Read-only buffers and zero matches keep the refusal semantics the
        direct ``replace_all`` call used before the loop existed; everything
        else opens a ``replace_confirm`` prompt and shows the first match.
        """
        if self.session.buffer.read_only:
            self._readonly_notice()
            return
        matches = self.session.search.update(find, self.session.buffer)
        if not matches:
            self._message(f"no matches for {find!r}", "warn")
            return
        self._replacement = replacement
        self._confirm_total = len(matches)
        self._confirm_done = 0
        self.prompt.activate(
            "replace_confirm",
            placeholder="",
            on_key=self._confirm_step,
        )
        self._advance()

    def _confirm_step(self, key: str) -> bool:
        """Handle one keypress of the per-match confirm loop; True = consumed.

        The loop always terminates (overview decision D2, risk R2): every
        ``y``/``n`` increments ``_confirm_done`` while ``_confirm_total``
        stays frozen once the loop has started, and
        :meth:`_finish_or_advance` checks ``done >= total`` *before* walking
        on, so the loop ends within ``total`` steps however the buffer
        evolves.  A replacement that matches itself cannot trap the walk
        either: ``SearchEngine.replace_current`` recomputes the match list
        and leaves the cursor at the end of the inserted text, and every
        self-match inside that text starts *before* the cursor, so
        ``_nearest_index``'s forward branch (which only picks matches at or
        after the cursor) never re-selects text inside the replacement; when
        the matches run out, ``SearchEngine.next`` returns ``None`` and
        :meth:`_end_confirm` exits the loop.
        """
        if key == "y":
            if self.session.search.replace_current(
                self.session.buffer, self._replacement
            ):
                self._confirm_done += 1
            self._finish_or_advance()
            return True
        if key == "n":
            self._confirm_done += 1  # skip the match _advance selected
            self._finish_or_advance()
            return True
        if key == "a":
            count = self.session.search.replace_all(
                self.session.buffer, self._replacement
            )
            self._end_confirm(
                f"replaced {count} occurrence(s) of "
                f"{self.session.search.query!r}"
            )
            return True
        if key in ("q", "escape", "ctrl+c"):
            self._end_confirm("replace cancelled")
            return True
        if key in ("enter",) or (len(key) == 1 and key.isprintable()):
            return True  # swallow stray keys; the Input stays empty
        return False  # up/down/history etc. fall through

    def _advance(self) -> None:
        """Select the next unconfirmed match and show loop progress.

        Progress goes through ``prompt.input.placeholder`` on purpose
        (overview fact F7): ``write()`` hides the Input, which the still
        running loop needs focused to receive the next key.
        """
        match = self.session.search.next(self.session.buffer, forward=True)
        if match is None:
            self._end_confirm("no further matches")
            return
        self.prompt.input.placeholder = (
            f"[{self._confirm_done + 1}/{self._confirm_total}] replace "
            f"{self.session.search.query!r} with {self._replacement!r}? "
            "(y)es (n)o (a)ll (q)uit"
        )

    def _finish_or_advance(self) -> None:
        """Stop after the fixed total, else move to the next match."""
        if self._confirm_done >= self._confirm_total:
            self._end_confirm(
                f"replaced {self._confirm_done} occurrence(s) of "
                f"{self.session.search.query!r}"
            )
            return
        self._advance()

    def _end_confirm(self, text: str) -> None:
        """Leave the confirm loop and report *text* on the message line.

        ``write()`` hides the prompt input and uninstalls the key hook; the
        counters and the pending replacement are reset with it.  Unlike the
        submit path (``on_input_submitted`` -> ``_finish``) the confirm loop
        consumes its keys before the Input sees them, so nothing restores
        focus: the bar's editor-focus callback is invoked here explicitly,
        otherwise the hidden Input keeps focus and swallows F5.
        """
        self._confirm_total = 0
        self._confirm_done = 0
        self._replacement = ""
        self._message(text, "ok" if "replaced" in text else "info")
        self.prompt.focus_editor()

    def goto_prompt(self) -> None:
        """Open the command line in go-to-line mode (Ctrl+G)."""
        line_count = self.session.buffer.line_count
        self.prompt.activate(
            "goto",
            placeholder=f"line number (1-{line_count})",
            on_submit=self.goto_line_command,
        )

    def goto_line_command(self, text: str) -> None:
        """Jump to an absolute (``42``) or signed-relative (``+5``) line."""
        text = text.strip()
        if not re.fullmatch(r"[+-]?\d+", text):
            self._message(f"not a line number: {text!r}", "warn")
            return
        value = int(text)
        buf = self.session.buffer
        if text[:1] in ("+", "-"):
            target = buf.row + 1 + value  # 1-based current row + offset
        else:
            target = value
        self.goto_line(target)

    def goto_line(self, line: int) -> None:
        """Move the cursor to 1-based *line*, clamped to the document.

        The column is preserved (clamped to the destination line), matching
        VS Code's Go to Line; the selection is cleared and the view follows.
        """
        buf = self.session.buffer
        row = max(0, min(line - 1, buf.line_count - 1))
        col = min(buf.col, len(buf.lines[row]))
        buf.anchor = None
        buf.set_cursor((row, col))
        self.session.search.update("", buf)
        view = self.panes.active_view
        if view is not None:
            view.scroll_col = 0
            view.reveal_cursor()
        self._message(f"line {row + 1} of {buf.line_count}", "info")
        self._refresh()
