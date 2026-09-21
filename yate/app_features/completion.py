"""Editor completion orchestration: debounce, LSP/buffer query, popup show.

The controller owns the debounce timer and the worker coroutine; the
application supplies the popup widget, the editor state and the spawn
primitive through :class:`CompletionHost`.
"""

from __future__ import annotations

import asyncio
from functools import partial
from pathlib import Path
from typing import Awaitable, Callable, Optional, Protocol

from yate.editor_core import Document
from yate.editor_core.buffer import TextBuffer
from yate.editor_lsp import LspManager
from yate.editor_view import theme
from yate.editor_view.completion import CompletionPopup, buffer_completions
from yate.editor_view.editor import EditorView
from yate.keymaps.base import Keymap
from yate.keymaps.vim import VimKeymap, VimMode
from yate.services.workspace import Workspace


class CompletionHost(Protocol):
    """What :class:`CompletionController` needs from the application."""

    lsp: LspManager

    @property
    def completion_popup(self) -> Optional[CompletionPopup]: ...

    @property
    def mounted(self) -> bool: ...

    @property
    def editor_view(self) -> Optional[EditorView]: ...

    @property
    def doc(self) -> Document: ...

    @property
    def docs(self) -> list[Document]: ...

    @property
    def workspace(self) -> Workspace: ...

    @property
    def keymap_name(self) -> str: ...

    @property
    def keymaps(self) -> dict[str, Keymap]: ...

    def message(self, text: str, kind: str = "info") -> None: ...

    def ui_refresh(self) -> None: ...

    def has_modal_screen(self) -> bool: ...

    def spawn(self, work: Callable[[], Awaitable[None]], *, group: str,
              exclusive: bool = False, exit_on_error: bool = True) -> None: ...


class CompletionController:
    """Debounced completion queries behind the active editor view."""

    #: Idle delay after the last keystroke before the popup is queried.
    _DEBOUNCE_S = 0.12

    def __init__(self, host: CompletionHost) -> None:
        self._host = host
        self._timer: Optional[asyncio.TimerHandle] = None

    # ----------------------------------------------------------------- hooks

    def close(self) -> None:
        popup = self._host.completion_popup
        if popup is not None and popup.is_open:
            popup.close()

    def after_editor_key(self, raw: str) -> None:
        """Adjust the completion popup after a normal editor keystroke."""
        host = self._host
        popup = host.completion_popup
        if popup is None or not host.mounted:
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
        host = self._host
        if host.completion_popup is None or not host.mounted:
            return
        if host.has_modal_screen():
            return
        if not self._vim_insert_mode():
            return
        self._timer = None
        host.spawn(
            partial(self._worker, manual, trigger_ch),
            group="lsp-completion", exclusive=True, exit_on_error=False,
        )

    async def _worker(self, manual: bool, trigger_ch: Optional[str]) -> None:
        host = self._host
        popup = host.completion_popup
        editor = host.editor_view
        if popup is None or editor is None:
            return
        doc = host.doc
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
        if not host.lsp.supports(doc):
            if not manual and not prefix and trigger_ch not in (".",):
                popup.close()
                return
            others = [d.buffer for d in host.docs if d is not doc]
            base = host.workspace.root if host.workspace.root is not None else Path.cwd()
            items, buf_prefix, _start_col = buffer_completions(
                buf, row, col, extra_buffers=others, base_dir=base
            )
            cur_prefix, cur_col = self._current_prefix(buf, row)
            if (
                not host.mounted
                or host.doc is not doc
                or buf.row != row
                or buf.col != cur_col
                or cur_prefix != prefix
                or not popup.is_mounted
            ):
                return
            if not items:
                popup.close()
                if manual:
                    host.message("no completions", kind="info")
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
            ".", *host.lsp.trigger_characters_for(doc)
        ):
            popup.close()
            return

        # Make sure didOpen happened (also starts the server on first use).
        await host.lsp.on_document_shown(doc)
        triggers = host.lsp.trigger_characters_for(doc)
        kind = 2 if trigger_ch in triggers else 1
        items = await host.lsp.request_completion(
            doc, row, col,
            prefix_start_col=i,
            trigger_kind=kind,
            trigger_character=trigger_ch if kind == 2 else None,
        )
        # Stale if the user switched tabs, lines, scrolled away, or changed
        # the prefix on the same row.
        cur_prefix, cur_col = self._current_prefix(buf, row)
        if (
            not host.mounted
            or host.doc is not doc
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
                host.message("no completions", kind="info")
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
        host = self._host
        popup = host.completion_popup
        if popup is None or not popup.is_open:
            return
        item = popup.selected()
        doc = host.doc
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
        host.ui_refresh()

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
        return ch in self._host.lsp.trigger_characters_for(self._host.doc)

    def _vim_insert_mode(self) -> bool:
        """True when vim modal editing would insert typed characters."""
        if self._host.keymap_name != "vim":
            return True
        vim = self._host.keymaps.get("vim")
        if vim is None:
            return True  # key missing in unexpected state; default to insert
        return isinstance(vim, VimKeymap) and vim.mode is VimMode.INSERT
