"""Editor completion orchestration: debounce, LSP/buffer query, popup show.

Extracted from :class:`yate.app.YateApp`: the controller owns the debounce
timer and the worker coroutine; the app object forwards calls and stays the
owner of the popup widget and shared session state.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from yate.editor_core.buffer import TextBuffer
from yate.editor_view import theme
from yate.editor_view.completion import buffer_completions
from yate.keymaps.vim import VimKeymap, VimMode

if TYPE_CHECKING:
    from yate.app import YateApp


class CompletionController:
    """Debounced completion queries behind the active editor view."""

    #: Idle delay after the last keystroke before the popup is queried.
    _DEBOUNCE_S = 0.12

    def __init__(self, app: "YateApp") -> None:
        self._app = app
        self._timer: Optional[asyncio.TimerHandle] = None

    # ----------------------------------------------------------------- hooks

    def close(self) -> None:
        popup = self._app.completion_popup
        if popup is not None and popup.is_open:
            popup.close()

    def after_editor_key(self, raw: str) -> None:
        """Adjust the completion popup after a normal editor keystroke."""
        app = self._app
        popup = app.completion_popup
        if popup is None or not app.mounted:
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
        app = self._app
        if app.completion_popup is None or not app.mounted:
            return
        if len(app.screen_stack) > 1:
            return
        if not self._vim_insert_mode():
            return
        self._timer = None
        app.run_worker(
            self._worker(manual, trigger_ch),
            group="lsp-completion", exclusive=True, exit_on_error=False,
        )

    async def _worker(self, manual: bool, trigger_ch: Optional[str]) -> None:
        app = self._app
        popup = app.completion_popup
        editor = app.editor_view
        if popup is None or editor is None:
            return
        doc = app.doc
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
        if not app.lsp.supports(doc):
            if not manual and not prefix and trigger_ch not in (".",):
                popup.close()
                return
            others = [d.buffer for d in app.docs if d is not doc]
            base = app.workspace.root if app.workspace.root is not None else Path.cwd()
            items, buf_prefix, _start_col = buffer_completions(
                buf, row, col, extra_buffers=others, base_dir=base
            )
            cur_prefix, cur_col = self._current_prefix(buf, row)
            if (
                not app.mounted
                or app.doc is not doc
                or buf.row != row
                or buf.col != cur_col
                or cur_prefix != prefix
                or not popup.is_mounted
            ):
                return
            if not items:
                popup.close()
                if manual:
                    app.message("no completions", kind="info")
                return
            cell = theme.char_to_cell(line, col, buf.tab_width) - editor.scroll_col
            rel_row = row - editor.scroll_offset.y
            popup.show(
                items, buf_prefix,
                (cell, rel_row),
                (editor.size.width or 80, editor.size.height or 20),
                editor.gutter_width(),
                origin_y=2,
            )
            return

        if not manual and not prefix and trigger_ch not in (
            ".", *app.lsp.trigger_characters_for(doc)
        ):
            popup.close()
            return

        # Make sure didOpen happened (also starts the server on first use).
        await app.lsp.on_document_shown(doc)
        triggers = app.lsp.trigger_characters_for(doc)
        kind = 2 if trigger_ch in triggers else 1
        items = await app.lsp.request_completion(
            doc, row, col,
            prefix_start_col=i,
            trigger_kind=kind,
            trigger_character=trigger_ch if kind == 2 else None,
        )
        # Stale if the user switched tabs, lines, scrolled away, or changed
        # the prefix on the same row.
        cur_prefix, cur_col = self._current_prefix(buf, row)
        if (
            not app.mounted
            or app.doc is not doc
            or buf.row != row
            or buf.col != cur_col
            or cur_prefix != prefix
            or not popup.is_mounted
        ):
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
                app.message("no completions", kind="info")
            return
        cell = theme.char_to_cell(line, col, buf.tab_width) - editor.scroll_col
        rel_row = row - editor.scroll_offset.y
        popup.show(
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
        app = self._app
        popup = app.completion_popup
        if popup is None or not popup.is_open:
            return
        item = popup.selected()
        doc = app.doc
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
            # Cursor left the row(s) the completion was for — discard.
            if row != r0 or row != r1:
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
        app.ui_refresh()

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
        return ch in self._app.lsp.trigger_characters_for(self._app.doc)

    def _vim_insert_mode(self) -> bool:
        """True when vim modal editing would insert typed characters."""
        if self._app.keymap_name != "vim":
            return True
        vim = self._app.keymaps["vim"]
        return isinstance(vim, VimKeymap) and vim.mode is VimMode.INSERT
