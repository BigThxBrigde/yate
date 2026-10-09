"""Mouse flows: text-area cursor moves, drag & click-chain selection.

Dispatches the mouse events forwarded by :class:`~yate.editor_view.editor.EditorView`
(mouse analogue of the key dispatch): single click positions the cursor,
left-button drag makes a characterwise selection, ``Alt`` + left-button
drag/press makes a rectangular (column) selection, double/triple click
selects the word/line under the pointer, and a click ends vim visual
mode.  Selection state stays in the buffer (``set_cursor``), exactly like
the keyboard paths.  Constructed by the editor; never imports upward.
"""

from __future__ import annotations

from collections.abc import Callable

from textual.events import Click, MouseDown, MouseMove, MouseUp, MouseEvent

from yate.config import YateConfig
from yate.editor_core.words import word_span
from yate.editor_view.editor import LEFT_BUTTON, EditorView
from yate.keymaps.registry import KeymapSet
from yate.keymaps.vim import VimKeymap


class MouseFlows:
    """Mouse dispatch for editor views (one shared pointer, so the drag
    state lives here rather than per view)."""

    def __init__(
        self,
        keymaps: KeymapSet,
        config: YateConfig,
        refresh: Callable[[], None],
    ) -> None:
        self.keymaps = keymaps
        self.config = config
        self._refresh = refresh
        self._dragging: bool = False

    def handle_view_mouse(self, view: EditorView, event: MouseEvent) -> bool:
        """Dispatch one mouse event over *view*; ``True`` when consumed."""
        if not self.config.support_mouse:
            # A mid-drag ``:set support_mouse off`` must not leave the drag
            # flag stuck: with the gate closed no MouseUp path can clear it.
            self._dragging = False
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

    def cancel_drag(self) -> None:
        """Drop an in-flight text drag (``:set support_mouse off`` mid-drag).

        With the app gate closed no MouseUp path can clear the flag, and a
        later re-enable would resume the stale drag on the next left-button
        MouseMove.  The selection itself is left untouched.
        """
        self._dragging = False

    def _on_down(self, view: EditorView, event: MouseDown) -> bool:
        if event.button != LEFT_BUTTON:
            return False
        keymap = self.keymaps.active
        if isinstance(keymap, VimKeymap):
            keymap.drop_visual()
        pos = view.buffer_pos_from_mouse(event)
        if pos is None:
            return False
        if event.meta:
            # Column selection: anchor at the press point; the block flag
            # survives the select=True extends below (TextBuffer.set_cursor
            # keeps it while an anchor exists).  Textual represents the Alt
            # modifier of mouse events as ``meta`` (SGR bit 8).
            view.buffer.set_cursor(pos)
            view.buffer.begin_block_selection()
        else:
            view.buffer.set_cursor(pos, select=event.shift)
        view.content_changed()
        self._refresh()
        self._dragging = True
        return True

    def _on_move(self, view: EditorView, event: MouseMove) -> bool:
        if not self._dragging or event.button != LEFT_BUTTON:
            return False
        pos = view.buffer_pos_from_mouse(event)
        if pos is not None:  # outside the text area: keep the drag alive
            # The block-vs-charwise track is decided once at mouse-down;
            # toggling Alt mid-drag does not re-route (VS Code parity).
            view.buffer.set_cursor(pos, select=True)
            view.content_changed()
            self._refresh()
        return True

    def _on_up(self, view: EditorView, event: MouseUp) -> bool:
        # Same button gate as _on_move / PaneHost.on_mouse_up: releasing a
        # different button (chording) must not terminate an in-flight
        # left-button drag selection.
        if not self._dragging or event.button != LEFT_BUTTON:
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
