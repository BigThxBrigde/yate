"""Prompt-driven flows: find, live-search highlight, replace, go-to-line.

Extracted from :mod:`yate.editor` (review 20260926 #5).  Every flow here is
synchronous session/view interaction -- no app or screen involvement.  Like
:class:`~yate.completion.CompletionFlows` this module is constructed by
the editor and never imports upward.
"""

from __future__ import annotations

import re
from collections.abc import Callable

from yate.editor_view.commandline import PromptBar
from yate.editor_view.panes import PaneManager
from yate.session import EditorSession


class PromptFlows:
    """Runs the search / replace / go-to-line flows on the prompt line."""

    def __init__(
        self,
        session: EditorSession,
        panes: PaneManager,
        prompt: PromptBar,
        message: Callable[[str, str], None],
        readonly_notice: Callable[[], None],
        refresh: Callable[[], None],
    ) -> None:
        self.session = session
        self.panes = panes
        self.prompt = prompt
        self._message = message
        self._readonly_notice = readonly_notice
        self._refresh = refresh

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
        if self.session.buffer.read_only:
            self._readonly_notice()
            return
        matches = self.session.search.update(find, self.session.buffer)
        if not matches:
            self._message(f"no matches for {find!r}", "warn")
            return
        count = self.session.search.replace_all(self.session.buffer, replacement)
        self._message(f"replaced {count} occurrence(s) of {find!r}", "ok")

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
