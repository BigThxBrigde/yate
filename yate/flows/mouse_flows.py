"""Mouse flows: text-area cursor moves, drag & click-chain selection.

Dispatches the mouse events forwarded by :class:`~yate.editor_view.editor.EditorView`
(mouse analogue of the key dispatch): single click positions the cursor,
left-button drag makes a characterwise selection, double/triple click
selects the word/line under the pointer, and a click ends vim visual
mode.  Selection state stays in the buffer (``set_cursor``), exactly like
the keyboard paths.  Constructed by the editor; never imports upward.
"""

from __future__ import annotations

from collections.abc import Callable

from textual.events import Click, MouseDown, MouseMove, MouseUp, MouseEvent

from yate.config import YateConfig
from yate.editor_core.buffer import word_span
from yate.editor_view.editor import EditorView
from yate.flows import MessageFn
from yate.keymaps.registry import KeymapSet
from yate.keymaps.vim import VimKeymap
from yate.session import EditorSession


class MouseFlows:
    """Mouse dispatch for editor views (one shared pointer, so the drag
    state lives here rather than per view)."""

    def __init__(
        self,
        session: EditorSession,
        keymaps: KeymapSet,
        config: YateConfig,
        refresh: Callable[[], None],
        message: MessageFn,
    ) -> None:
        self.session = session
        self.keymaps = keymaps
        self.config = config
        self._refresh = refresh
        self._message = message
        self._dragging: bool = False

    def handle_view_mouse(self, view: EditorView, event: MouseEvent) -> bool:
        """Dispatch one mouse event over *view*; ``True`` when consumed."""
        if not self.config.support_mouse:
            return False
        if isinstance(event, MouseDown):
            return self._on_down(view, event)
        if isinstance(event, MouseMove):
            return self._on_move(view, event)
        if isinstance(event, MouseUp):
            return self._on_up(view, event)
        if isinstance(event, Click):
            return self._on_click(view, event)
        return False

    def _on_down(self, view: EditorView, event: MouseDown) -> bool:
        if event.button != 1:
            return False
        keymap = self.keymaps.active
        if isinstance(keymap, VimKeymap):
            keymap.drop_visual()
        pos = view.buffer_pos_from_mouse(event)
        if pos is None:
            return False
        view.buffer.set_cursor(pos, select=event.shift)
        view.content_changed()
        self._refresh()
        self._dragging = True
        return True

    def _on_move(self, view: EditorView, event: MouseMove) -> bool:
        if not self._dragging or event.button != 1:
            return False
        pos = view.buffer_pos_from_mouse(event)
        if pos is not None:  # outside the text area: keep the drag alive
            view.buffer.set_cursor(pos, select=True)
            view.content_changed()
            self._refresh()
        return True

    def _on_up(self, view: EditorView, event: MouseUp) -> bool:
        if not self._dragging:
            return False
        self._dragging = False
        self._refresh()
        return True

    def _on_click(self, view: EditorView, event: Click) -> bool:
        if event.chain < 2:
            return False  # single click handled at mouse-down
        pos = view.buffer_pos_from_mouse(event)
        if pos is None:
            return False
        row, col = pos
        line = view.buffer.lines[row]
        start, end = word_span(line, col) if event.chain == 2 else (0, len(line))
        if end <= start:
            view.buffer.set_cursor(pos)
        else:
            view.buffer.set_cursor((row, start))
            view.buffer.set_cursor((row, end), select=True)
        view.content_changed()
        self._refresh()
        return True
