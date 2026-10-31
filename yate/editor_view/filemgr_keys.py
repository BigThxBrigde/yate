"""Key bindings and input-window constants for the file manager screen.

Split from :mod:`yate.editor_view.filemgr` (plan-d's ``filemgr_keys``
escape hatch for the size guard): the binding tables are pure data with
no widget or workspace coupling, so they live apart from the screen
logic.  Action names referenced here are defined on
:class:`~yate.editor_view.filemgr.FileManagerScreen` and on its
middle-pane ``ListView`` subclass.
"""

from __future__ import annotations

from textual.binding import Binding, BindingType

#: Double-click window for the middle pane (seconds): a second click on
#: the same row within this window opens it.  Patched by tests to keep
#: them off real-sleep timing (coding-style 4.7).
DOUBLE_CLICK_WINDOW: float = 0.3

#: ``g`` prefix timeout (seconds): after this window a second ``g`` acts
#: as a fresh prefix instead of jump-to-top.
G_PENDING_TIMEOUT: float = 1.0

#: Screen-level key bindings (R7 key map, plan-d).  ``left`` / ``right``
#: / ``home`` / ``end`` are shadowed by the middle pane's remapped
#: scroll bindings while the list is focused; they cover the unfocused
#: fallback.
SCREEN_BINDINGS: list[BindingType] = [
    Binding("j,down", "cursor_down", "Cursor down", show=False),
    Binding("k,up", "cursor_up", "Cursor up", show=False),
    Binding("l,enter,right", "open", "Open", show=False),
    Binding("h,left,backspace", "up", "Parent directory", show=False),
    Binding("G,end", "bottom", "Jump to bottom", show=False),
    Binding("home", "top", "Jump to top", show=False),
    Binding("ctrl+d", "half_page_down", "Half page down", show=False),
    Binding("ctrl+u", "half_page_up", "Half page up", show=False),
    Binding("slash,f", "filter", "Filter", show=False),
    Binding("H,full_stop", "toggle_hidden", "Toggle hidden", show=False),
    Binding("s", "cycle_sort", "Cycle sort", show=False),
    Binding("r,f5", "refresh", "Refresh", show=False),
    Binding("space", "mark", "Mark", show=False),
    Binding("v", "invert_marks", "Invert marks", show=False),
    Binding("escape", "escape", "Back / close", show=False),
    Binding("q", "quit", "Close", show=False),
    Binding("a", "new_file", "New file", show=False),
    Binding("A", "new_dir", "New directory", show=False),
    Binding("R", "rename", "Rename", show=False),
    Binding("d", "delete", "Delete", show=False),
    Binding("y", "yank", "Copy (yank)", show=False),
    Binding("x", "cut", "Cut", show=False),
    Binding("p", "paste", "Paste", show=False),
]

#: Middle-pane list bindings: the inherited ``ScrollableContainer``
#: scroll bindings would swallow these keys, so they are remapped to the
#: screen's navigation actions via ``nav(name)``.
LIST_BINDINGS: list[BindingType] = [
    Binding("left", "nav(up)", "Parent directory", show=False),
    Binding("right", "nav(open)", "Open", show=False),
    Binding("home", "nav(top)", "Jump to top", show=False),
    Binding("end", "nav(bottom)", "Jump to bottom", show=False),
    Binding("pageup", "nav(half_page_up)", "Half page up", show=False),
    Binding("pagedown", "nav(half_page_down)", "Half page down", show=False),
]
