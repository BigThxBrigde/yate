"""LSP hover orchestration: keyboard requests, mouse debounce and staleness.

The controller owns the debounce timer, the staleness token and the popup
lifecycle; the widget only paints what it is told to.  It is an editor-level
collaborator (not a widget), so it receives the concrete pieces it drives:
the document session, the language servers, the panes (for the active view
geometry) and the hover popup.  Hover feedback is deliberately silent: a
failed, empty or stale request never writes to the message line, the status
bar or the prompt (AC5).
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from functools import partial

from yate.editor_components import theme
from yate.editor_components.hover_popup import HoverPopup
from yate.editor_components.panes import PaneManager
from yate.editor_core import Document
from yate.editor_core.buffer import Pos
from yate.editor_lsp.manager import LspManager
from yate.flows import SpawnFn
from yate.logs import tracing
from yate.session import EditorSession

log = tracing.get_logger(__name__)

#: Delay before a non-drag MouseMove starts a hover request.
HOVER_DEBOUNCE_S: float = 0.35


class HoverFlows:
    """Own hover requests, debounce, staleness tokens and card dismissal."""

    def __init__(
        self,
        *,
        spawn: SpawnFn,
        lsp: LspManager,
        session: EditorSession,
        panes: PaneManager,
        popup: HoverPopup,
        has_modal_screen: Callable[[], bool],
    ) -> None:
        # Bound ``App.run_worker``: the background-work verb injected by the
        # editor (this module never holds the App handle itself).
        self._spawn = spawn
        self.lsp = lsp
        self.session = session
        self.panes = panes
        self.popup = popup
        self._has_modal_screen = has_modal_screen
        self._timer: asyncio.TimerHandle | None = None
        # Invalidates every in-flight result issued before it (plan g D6).
        self._token: int = 0
        self._source: str = ""
        self._target: Pos | None = None
        self._doc_path: str | None = None

    # ---------------------------------------------------------------- hooks

    def request_at_cursor(self) -> None:
        """Start a hover request at the buffer cursor (keyboard path).

        No debounce: the keystroke that triggers hover is already an
        explicit intent, unlike pointer movement.
        """
        doc = self.session.doc
        buf = doc.buffer
        self._schedule(doc, (buf.row, buf.col), "key")

    def on_mouse_move(self, pos: Pos | None) -> None:
        """Debounced hover entry point driven by :class:`MouseFlows`.

        ``None`` means the pointer left the text area, the gate turned off
        or a drag started: dismiss outright.  A new position closes any
        visible card immediately (a stale card must not sit there while
        the new debounce runs) and rearms the single debounce timer; the
        same position while a card is visible is a no-op (no flicker).
        """
        if pos is None:
            self.dismiss()
            return
        if self._target == pos and self.popup.is_open:
            return
        if self._target != pos and self.popup.is_open:
            # No stale card while the new debounce runs; a card that is
            # already closed is left untouched (no spurious close/flash).
            self.popup.close()
        timer = self._timer
        if timer is not None:
            timer.cancel()
        loop = asyncio.get_running_loop()
        self._timer = loop.call_later(
            HOVER_DEBOUNCE_S, self._schedule_mouse, pos
        )

    def dismiss(self) -> None:
        """Cancel the debounce timer, invalidate in-flight results and hide.

        Idempotent; never writes to the message or status bar (AC5).
        """
        timer = self._timer
        if timer is not None:
            timer.cancel()
            self._timer = None
        self._token += 1
        self.popup.close()

    # ------------------------------------------------------------ scheduling

    def _schedule_mouse(self, pos: Pos) -> None:
        """Fire after the debounce delay elapsed on one stable position."""
        self._timer = None
        self._schedule(self.session.doc, pos, "mouse")

    def _schedule(self, doc: Document, pos: Pos, source: str) -> None:
        """Guard, snapshot the staleness state and spawn the worker.

        Guards return silently (never closing a card without a real
        result): a modal screen blocks the request outright, and a missing
        server only closes the card when one is actually visible.
        """
        if self._has_modal_screen():
            return
        if not self.lsp.supports(doc):
            if self.popup.is_open:
                self.popup.close()
            return
        timer = self._timer
        if timer is not None:
            timer.cancel()
            self._timer = None
        self._doc_path = str(doc.path) if doc.path is not None else None
        self._source = source
        self._target = pos
        self._token += 1
        token = self._token
        self._spawn(
            # the coroutine *function*: an eager coroutine would leak if the
            # worker never starts
            partial(self._worker, doc, pos, token),
            group="lsp-hover", exclusive=True, exit_on_error=False,
        )

    # ---------------------------------------------------------------- worker

    async def _worker(
        self, doc: Document, pos: Pos, token: int
    ) -> None:
        """Query the LSP and drive the popup from the result."""
        try:
            text = await self.lsp.request_hover(doc, pos[0], pos[1])
        except Exception:  # noqa: BLE001 - a failed request must be silent
            log.debug("hover request failed for %s", doc.path, exc_info=False)
            text = ""
        if self._stale(doc, pos, token):
            return
        if not text.strip():
            # Zero UI feedback, including the "card was visible then the
            # new result is empty" case (AC5).
            self.popup.close()
            return
        view = self.panes.active_view
        if view is None:
            return
        buf = doc.buffer
        line = buf.lines[pos[0]] if pos[0] < buf.line_count else ""
        cell = theme.char_to_cell(line, pos[1], buf.tab_width) - view.scroll_col
        rel_row = pos[0] - view.scroll_offset.y
        self.popup.show(
            text,
            (cell, rel_row),
            (view.size.width or 80, view.size.height or 20),
            view.gutter_width(),
            origin_y=2,
        )

    def _stale(self, doc: Document, pos: Pos, token: int) -> bool:
        """True when the result no longer matches what the user sees.

        Stale responses are discarded, never displayed and never close an
        unrelated newer card.
        """
        path_now = str(doc.path) if doc.path is not None else None
        if (
            token != self._token
            or self.session.doc is not doc
            or path_now != self._doc_path
            or not self.popup.is_mounted
        ):
            return True
        if self._source == "key":
            buf = self.session.doc.buffer
            return (buf.row, buf.col) != pos
        if self._source == "mouse":
            return self._target != pos
        return True
