"""Editor completion orchestration: debounce, LSP/buffer query, popup show.

The controller owns the debounce timer and the query worker; the popup widget
shows the candidates.  It is an editor-level collaborator (not a widget), so
it receives the concrete pieces it drives: the document session, the language
servers, the panes (for the active view geometry), the popup and the prompt
bar (for "no completions" feedback).
"""

from __future__ import annotations

import asyncio
from functools import partial
from pathlib import Path
from typing import Callable, Optional

from textual.app import App

from yate.editor_view import theme
from yate.editor_view.commandline import PromptBar
from yate.editor_view.completion import CompletionPopup, buffer_completions
from yate.editor_view.editor import EditorView
from yate.editor_view.panes import PaneManager
from yate.editor_core import Document
from yate.editor_core.buffer import TextBuffer
from yate.editor_lsp import LspManager
from yate.editor_lsp.client import Completion
from yate.keymaps.registry import KeymapSet
from yate.keymaps.vim import VimKeymap, VimMode
from yate.services.workspace import Workspace
from yate.session import EditorSession


class CompletionController:
    """Debounced completion queries behind the active editor view."""

    #: Idle delay after the last keystroke before the popup is queried.
    _DEBOUNCE_S = 0.12

    def __init__(
        self,
        app: App[object],
        *,
        session: EditorSession,
        lsp: LspManager,
        workspace: Workspace,
        keymaps: KeymapSet,
        panes: PaneManager,
        popup: CompletionPopup,
        prompt: PromptBar,
        refresh: Callable[[], None],
    ) -> None:
        self.app = app
        self.session = session
        self.lsp = lsp
        self.workspace = workspace
        self.keymaps = keymaps
        self.panes = panes
        self.popup = popup
        self.prompt = prompt
        self.refresh = refresh
        self._timer: Optional[asyncio.TimerHandle] = None

    # ----------------------------------------------------------------- hooks

    @property
    def _mounted(self) -> bool:
        return self.popup.is_mounted

    @property
    def _modal(self) -> bool:
        return len(self.app.screen_stack) > 1

    def close(self) -> None:
        popup = self.popup
        if popup.is_open:
            popup.close()

    def after_editor_key(self, raw: str) -> None:
        """Adjust the completion popup after a normal editor keystroke."""
        popup = self.popup
        if not self._mounted:
            return
        if len(raw) == 1 and raw.isprintable():
            if self._is_completion_char(raw) and self._vim_insert_mode():
                self.schedule(raw)
            else:
                self.close()
            return
        if raw == "\x7f":  # backspace: re-query while a popup is open
            if popup.is_open:
                self.schedule(None)
            return
        if raw == "\r":  # newline
            self.close()
            return
        # left/right movement keeps the popup; anything else closes it.
        if raw not in ("\x1b[D", "\x1b[C", "\x1b[1;5D", "\x1b[1;5C"):
            self.close()

    # ------------------------------------------------------------- querying

    def schedule(self, trigger_ch: Optional[str]) -> None:
        # Always schedule: with an LSP we query the server, without one we
        # fall back to buffer words + paths (see _worker).
        timer = self._timer
        if timer is not None:
            timer.cancel()
        loop = asyncio.get_running_loop()
        self._timer = loop.call_later(
            self._DEBOUNCE_S, self.request, False, trigger_ch
        )

    def request(self, manual: bool = True, trigger_ch: Optional[str] = None) -> None:
        """Fetch completions and show the popup (worker; never blocks input)."""
        if not self._mounted or self._modal:
            return
        if not self._vim_insert_mode():
            return
        self._timer = None
        self.app.run_worker(
            # the coroutine *function*: an eager coroutine would leak if the
            # worker never starts
            partial(self._worker, manual, trigger_ch),
            group="lsp-completion", exclusive=True, exit_on_error=False,
        )

    async def _worker(self, manual: bool, trigger_ch: Optional[str]) -> None:
        popup = self.popup
        editor = self.panes.active_view
        if editor is None:
            return
        doc = self.session.doc
        buf = doc.buffer
        row, col = buf.row, buf.col
        line = buf.lines[row] if row < buf.line_count else ""
        col = min(col, len(line))
        i = col
        while i > 0 and (line[i - 1].isalnum() or line[i - 1] == "_"):
            i -= 1
        prefix = line[i:col]

        # No language server for this document -> buffer-based completion
        # (words from every open buffer + filesystem paths).
        if not self.lsp.supports(doc):
            if not manual and not prefix and trigger_ch not in (".",):
                popup.close()
                return
            others = [d.buffer for d in self.session.docs if d is not doc]
            root = self.workspace.root
            base = root if root is not None else Path.cwd()
            items, buf_prefix, _start_col = buffer_completions(
                buf, row, col, extra_buffers=others, base_dir=base
            )
            cur_prefix, cur_col = self._current_prefix(buf, row)
            if self._stale(doc, row, prefix, cur_prefix, cur_col, popup):
                return
            if not items:
                popup.close()
                if manual:
                    self.prompt.write("no completions", kind="info")
                return
            self._show_items(items, buf_prefix, editor, line, col, buf, row)
            return

        if not manual and not prefix and trigger_ch not in (
            ".", *self.lsp.trigger_characters_for(doc)
        ):
            popup.close()
            return

        # Make sure didOpen happened (also starts the server on first use).
        await self.lsp.on_document_shown(doc)
        triggers = self.lsp.trigger_characters_for(doc)
        kind = 2 if trigger_ch in triggers else 1
        items = await self.lsp.request_completion(
            doc, row, col,
            prefix_start_col=i,
            trigger_kind=kind,
            trigger_character=trigger_ch if kind == 2 else None,
        )
        # Stale if the user switched tabs, lines, scrolled away, or changed
        # the prefix on the same row.
        cur_prefix, cur_col = self._current_prefix(buf, row)
        if self._stale(doc, row, prefix, cur_prefix, cur_col, popup):
            return
        if prefix:
            needle = prefix.lower()
            items = [
                c for c in items
                if c.label[: len(prefix)].lower() == needle
                or c.insert_text[: len(prefix)].lower() == needle
            ]
        items = items[:250]
        if not items:
            popup.close()
            if manual:
                self.prompt.write("no completions", kind="info")
            return
        self._show_items(items, prefix, editor, line, col, buf, row)

    def _stale(
        self,
        doc: Document,
        row: int,
        prefix: str,
        cur_prefix: str,
        cur_col: int,
        popup: CompletionPopup,
    ) -> bool:
        buf = self.session.doc.buffer
        return (
            not self._mounted
            or self.session.doc is not doc
            or buf.row != row
            or buf.col != cur_col
            or cur_prefix != prefix
            or not popup.is_mounted
        )

    def _show_items(
        self,
        items: list[Completion],
        prefix: str,
        editor: EditorView,
        line: str,
        col: int,
        buf: TextBuffer,
        row: int,
    ) -> None:
        cell = theme.char_to_cell(line, col, buf.tab_width) - editor.scroll_col
        rel_row = row - editor.scroll_offset.y
        self.popup.show(
            items,
            prefix,
            (cell, rel_row),
            (editor.size.width or 80, editor.size.height or 20),
            editor.gutter_width(),
            origin_y=2,
        )

    # -------------------------------------------------------------- accept

    def accept(self) -> None:
        """Insert the selected completion at its reported range."""
        popup = self.popup
        if not popup.is_open:
            return
        item = popup.selected()
        doc = self.session.doc
        buf = doc.buffer
        popup.close()
        if item is None:
            return
        row, col = buf.row, buf.col
        if item.has_range():
            r0 = item.range_start_row or 0
            c0 = item.range_start_col or 0
            r1 = item.range_end_row or 0
            c1 = item.range_end_col or 0
            # Cursor left the row range the completion was for — discard.
            if row < r0 or row > r1:
                return
            # Characters typed after the request extend the replaced prefix.
            if row == r1 and col >= c1:
                c1 = col
            if (row, col) < (r0, c0) or (r0, c0) > (r1, c1):
                return  # cursor moved away: discard rather than corrupt text
            start, end = (r0, c0), (r1, c1)
        else:
            i = col
            line = buf.lines[row]
            while i > 0 and (line[i - 1].isalnum() or line[i - 1] == "_"):
                i -= 1
            start, end = (row, i), (row, col)
        buf.replace_range(start, end, item.insert_text)
        self.refresh()

    # -------------------------------------------------------------- helpers

    @staticmethod
    def _current_prefix(buf: TextBuffer, row: int) -> tuple[str, int]:
        """Recompute the identifier prefix at the buffer's current cursor.

        Mirrors the prefix definition used in :meth:`_worker` and
        :meth:`accept` (``isalnum() or "_"``).  Returned tuple is
        ``(prefix_text, current_column)`` — the column is clamped to the
        line length so callers can compare it against a previously captured
        column without extra guards.
        """
        line = buf.lines[row] if row < buf.line_count else ""
        col = min(buf.col, len(line))
        i = col
        while i > 0 and (line[i - 1].isalnum() or line[i - 1] == "_"):
            i -= 1
        return line[i:col], col

    def _is_completion_char(self, ch: str) -> bool:
        if ch.isalnum() or ch == "_":
            return True
        return ch in self.lsp.trigger_characters_for(self.session.doc)

    def _vim_insert_mode(self) -> bool:
        """True when vim modal editing would insert typed characters."""
        if self.keymaps.name != "vim":
            return True
        vim = self.keymaps.get("vim")
        if vim is None:
            return True  # key missing in unexpected state; default to insert
        return isinstance(vim, VimKeymap) and vim.mode is VimMode.INSERT
