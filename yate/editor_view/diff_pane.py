"""Per-side diff pane: gutter badges + diff-tinted text rendering.

The widget half of the diff viewer, split from :mod:`yate.editor_view.diffview`
(big-module-split wave b).  :class:`DiffPane` is a pure renderer with an
opt-in edit mode; the diff state it paints is computed by
:class:`~yate.editor_view.diffview.DiffScreen` and handed over wholesale as
a :class:`PaneDiffState`.  Theme painting is self-held (R13): the pane
subscribes on mount and repaints itself on broadcast.

Key handling follows R10: in navigation mode :class:`DiffPane` consumes
nothing (arrow keys scroll the focused pane through ScrollView's own
bindings, everything else bubbles once to the screen's BINDINGS); in edit
mode a hit in the per-keymap edit table is stopped and executed, a miss
falls through so screen bindings keep working.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, override

from rich.segment import Segment
from rich.style import Style
from textual.color import Color
from textual.events import Key, Resize
from textual.geometry import Size
from textual.message import Message
from textual.scroll_view import ScrollView
from textual.strip import Strip

from yate.editor_core.buffer import TextBuffer
from yate.editor_core.document import Document
from yate.editor_core.textobjects import word_end_column

from yate.editor_view import theme
from yate.editor_view.scrollbars import apply_scrollbar_theme, apply_slim_scrollbars


@dataclass(frozen=True)
class PaneDiffState:
    """Render state for one file side, derived by :class:`DiffScreen`.

    The screen computes it from the L0 diff result and hands it to the pane
    wholesale; the pane only knows how to paint it.
    """

    #: Per-row classification: ``"same"``, ``"changed"``, ``"added"``,
    #: ``"removed"`` or ``"conflict"``.
    line_states: tuple[str, ...]
    #: Row -> character highlight spans (half-open), for replace-type rows
    #: only (character-level diff of a changed line pair).
    inline: dict[int, tuple[tuple[int, int], ...]]
    #: Rows covered by the currently selected hunk / merge region.
    current_rows: frozenset[int]


# ---------------------------------------------------------------------------
# Edit-mode key tables (module-level constants, built once)
# ---------------------------------------------------------------------------


def _undo(pane: DiffPane) -> None:
    """Undo the pane's last edit (adapter for the bool-returning API)."""
    pane.buffer.undo()


def _vim_arm_dd(pane: DiffPane) -> None:
    """Arm the ``dd`` line-delete chord; a second ``d`` completes it."""
    pane.pending_d = True


def _vim_insert_at(pane: DiffPane) -> None:
    """Switch to the vim insert sub-table before the cursor."""
    pane.vim_insert = True


def _vim_append_at(pane: DiffPane) -> None:
    """Switch to the vim insert sub-table after the cursor (never wrapping).

    ``set_cursor`` clamps to the line end (same as the main vim keymap), so
    ``a`` never spills onto the next line.
    """
    pane.buffer.set_cursor((pane.buffer.row, pane.buffer.col + 1))
    pane.vim_insert = True


def _vim_open_below(pane: DiffPane) -> None:
    """Open a new line below and switch to the insert sub-table."""
    pane.buffer.move_line_end()
    pane.buffer.insert_newline()
    pane.vim_insert = True


def _vim_word_end(pane: DiffPane) -> None:
    """Move to the current line's next word end (vim ``e``, in-line only).

    The cross-line walk of the main vim keymap is out of the bounded
    subset; at a line's last word end the key is a no-op.
    """
    col = word_end_column(pane.buffer.lines[pane.buffer.row], pane.buffer.col)
    if col is not None:
        pane.buffer.set_cursor((pane.buffer.row, col))


def _vim_inert(pane: DiffPane) -> None:
    """Consume ``q`` with no effect (backlog S3).

    Unmapped, it reaches the screen bindings and arms the close guard --
    a vim muscle-memory trap, since ``q`` means macro recording there.
    """
    return None


#: VS Code-style edit table: cursor keys, deletion, newline, undo.
#: Printable characters are handled by the pane itself (``is_printable``),
#: so the table only lists named keys.
_VSC_EDIT_KEYS: dict[str, Callable[[DiffPane], None]] = {
    "up": lambda pane: pane.buffer.move_up(),
    "down": lambda pane: pane.buffer.move_down(),
    "left": lambda pane: pane.buffer.move_left(),
    "right": lambda pane: pane.buffer.move_right(),
    "home": lambda pane: pane.buffer.move_line_start(),
    "end": lambda pane: pane.buffer.move_line_end(),
    "backspace": lambda pane: pane.buffer.delete_backward(),
    "delete": lambda pane: pane.buffer.delete_forward(),
    "enter": lambda pane: pane.buffer.insert_newline(),
    "ctrl+z": _undo,
}

#: Vim normal-mode edit table (main-plan D2: bounded subset).  ``d`` arms
#: the ``dd`` line-delete chord (second ``d`` deletes, any other key
#: cancels); ``i``/``a``/``o`` switch to the insert sub-table; ``e`` moves
#: to the current line's word end; ``q`` is consumed inert (backlog S3).
_VIM_EDIT_KEYS: dict[str, Callable[[DiffPane], None]] = {
    "h": lambda pane: pane.buffer.move_left(),
    "j": lambda pane: pane.buffer.move_down(),
    "k": lambda pane: pane.buffer.move_up(),
    "l": lambda pane: pane.buffer.move_right(),
    "0": lambda pane: pane.buffer.set_cursor((pane.buffer.row, 0)),
    # Textual normalizes "$" to its unicode key name (probe: _character_to_key).
    "dollar_sign": lambda pane: pane.buffer.move_line_end(),
    "x": lambda pane: pane.buffer.delete_forward(),
    "e": _vim_word_end,
    "q": _vim_inert,
    "d": _vim_arm_dd,
    "i": _vim_insert_at,
    "a": _vim_append_at,
    "o": _vim_open_below,
}

#: Vim insert sub-table: printable characters fall through to typing.
_VIM_INSERT_KEYS: dict[str, Callable[[DiffPane], None]] = {
    "enter": lambda pane: pane.buffer.insert_newline(),
    "backspace": lambda pane: pane.buffer.delete_backward(),
}


# ---------------------------------------------------------------------------
# Paint helpers
# ---------------------------------------------------------------------------


#: Gutter badge per line state: glyph + theme palette attribute.
_BADGES: dict[str, tuple[str, str]] = {
    "added": ("+", "green"),
    "removed": ("-", "red"),
    "changed": ("~", "yellow"),
    "conflict": ("!", "red"),
}

#: Tint strength per line state (blend of the state color over the theme
#: background); conflicts get the strongest wash (main-plan D5).
_TINTS: dict[str, float] = {
    "added": 0.22,
    "removed": 0.22,
    "changed": 0.18,
    "conflict": 0.45,
}


def _line_background(t: theme.Theme, state: str, current: bool) -> str | None:
    """Row background for *state* (``None`` = plain theme background).

    Same-classified rows inside the current hunk get the surface color so
    the selection stays visible without a diff tint of its own.
    """
    if state in _TINTS:
        color = getattr(t, _BADGES[state][1])
        return Color.parse(color).blend(Color.parse(t.bg), 1 - _TINTS[state]).hex
    return t.surface if current else None


def _in_spans(spans: tuple[tuple[int, int], ...], index: int) -> bool:
    """Whether character *index* falls inside any half-open span."""
    return any(start <= index < end for start, end in spans)


# ---------------------------------------------------------------------------
# DiffPane
# ---------------------------------------------------------------------------


class DiffPane(ScrollView):
    """One file side of the diff screen: gutter badges + tinted text.

    A pure renderer with an opt-in edit mode.  Theme painting is self-held
    (R13): the pane subscribes on mount and repaints itself on broadcast.
    """

    can_focus = True

    class PaneChanged(Message):
        """A pane's edit-mode flag or buffer content changed."""

        def __init__(self, pane: DiffPane) -> None:
            super().__init__()
            self.pane = pane

    #: unsubscribe hook from :func:`yate.editor_view.theme.subscribe`;
    #: ``None`` while not mounted.
    _theme_unsubscribe: theme.Unsubscribe | None = None

    def __init__(
        self,
        doc: Document,
        title: str,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.doc = doc
        self.title = title
        # Read-only enforcement reads ``self.buffer.read_only`` directly (it
        # is the single source of truth and can change between diff runs);
        # a pane-level copy of the flag would only drift from it.
        #: Edit mode is entered/exited by the screen (``toggle_edit``).
        self.editing: bool = False
        self._state: PaneDiffState | None = None
        self._edit_table: str | None = None
        self.vim_insert: bool = False
        self.pending_d: bool = False

    @property
    def buffer(self) -> TextBuffer:
        """The text buffer of this side's document."""
        return self.doc.buffer

    # ------------------------------------------------------- theme (R13)

    @override
    def on_mount(self) -> None:
        """Apply the active theme and register for theme-change updates."""
        super().on_mount()
        apply_slim_scrollbars(self)
        self._apply_theme()
        theme.attach(self, self._apply_theme)
        self._update_virtual_size()

    def on_unmount(self) -> None:
        """Detach from the theme broadcast (widgets own their painting)."""
        theme.detach(self)

    def _apply_theme(self) -> None:
        """Paint this pane with the active theme (bg + scrollbar palette)."""
        self.styles.background = theme.active().bg
        apply_scrollbar_theme(self)
        self.refresh()

    # ------------------------------------------------------------- state

    def set_state(self, state: PaneDiffState) -> None:
        """Replace the render state wholesale and repaint."""
        self._state = state
        self._update_virtual_size()
        self.refresh()

    def _update_virtual_size(self) -> None:
        buf = self.doc.buffer
        width = self.size.width or 80
        self.virtual_size = Size(width, max(1, buf.line_count))

    def on_resize(self, _event: Resize) -> None:
        """Recompute the virtual (scrollable) size when the widget resizes."""
        self._update_virtual_size()

    def _gutter_width(self) -> int:
        """Gutter width: padding + line-number column + badge column."""
        digits = max(2, len(str(max(1, self.doc.buffer.line_count))))
        return digits + 3

    # ------------------------------------------------------------- render

    @override
    def render_line(self, y: int) -> Strip:
        """Render one visible row: gutter (number + badge) and tinted text."""
        t = theme.active()
        view_w = self.size.width or 80
        gutter_w = self._gutter_width()
        buf = self.doc.buffer
        row = y + self.scroll_offset.y
        if row >= buf.line_count:
            return Strip([Segment(" " * view_w, Style(bgcolor=t.bg))])

        state = self._state
        line_state = "same"
        inline: tuple[tuple[int, int], ...] = ()
        in_current = False
        if state is not None and row < len(state.line_states):
            line_state = state.line_states[row]
            inline = state.inline.get(row, ())
            in_current = row in state.current_rows

        line = buf.lines[row]
        line_bg = _line_background(t, line_state, in_current)
        inline_bg: str | None = None
        if line_state in _TINTS:
            color = getattr(t, _BADGES[line_state][1])
            inline_bg = Color.parse(color).blend(Color.parse(t.bg), 0.55).hex

        # text window: no horizontal scrolling (long lines clip), so
        # expanding the whole line is wasted work on very long input
        # (review 2026-10-03 #49.2) -- cap the expansion at the largest
        # prefix that can still paint the visible window.  Wide glyphs
        # take 2 cells and a tab up to ``tab_width``, so the review's
        # ``text_w * 2 + tab_width`` bound always over-covers.
        text_w = max(1, view_w - gutter_w)
        cap = min(len(line), text_w * 2 + buf.tab_width)
        cells: list[str] = []
        for ch in line[:cap]:
            theme.expand_char(ch, cells, buf.tab_width)
        cursor_row = buf.row if self.editing else -1
        cursor_cell = (
            theme.char_to_cell(line, buf.col, buf.tab_width)
            if row == cursor_row
            else -1
        )
        if row == cursor_row and buf.col >= len(line):
            cells.append(" ")  # block cursor at end of line

        # gutter: " " + line number + badge (one cell each)
        badge, badge_attr = _BADGES.get(line_state, (" ", "fg_dim"))
        badge_color = t.fg_dim if badge == " " else getattr(t, badge_attr)
        num = str(row + 1).rjust(gutter_w - 3)
        bg = line_bg or t.bg
        segments: list[Segment] = [
            Segment(" ", Style(bgcolor=bg)),
            Segment(
                num,
                Style(
                    color=t.accent if in_current else t.fg_dim,
                    bold=in_current,
                    bgcolor=bg,
                ),
            ),
            Segment(" ", Style(bgcolor=bg)),
            Segment(badge, Style(color=badge_color, bgcolor=bg, bold=True)),
        ]

        # text window (no horizontal scrolling: long lines clip)
        used = 0
        span = 0  # character index of the cell being painted
        for cell_idx in range(text_w):
            if cell_idx >= len(cells):
                break
            ch = cells[cell_idx]
            cell_bg = inline_bg if _in_spans(inline, span) else line_bg
            style = Style(bgcolor=cell_bg or t.bg, color=t.fg)
            if row == cursor_row and cell_idx == cursor_cell:
                style += Style(reverse=True)
            if ch:
                # empty cells are the second half of a wide glyph: the
                # glyph itself already advanced Rich by 2 cells (see
                # editor.py render_line)
                segments.append(Segment(ch, style))
            else:
                segments.append(Segment(" ", style))
            used += 1
            if ch:
                span += 1
        pad = view_w - gutter_w - used
        if pad > 0:
            segments.append(Segment(" " * pad, Style(bgcolor=line_bg or t.bg)))
        return Strip(segments)

    # ------------------------------------------------------------- editing

    def enter_edit_mode(self, table: str) -> None:
        """Switch the pane into edit mode with the named key table."""
        self.editing = True
        self._edit_table = table
        self.vim_insert = False
        self.pending_d = False
        self.refresh()

    def exit_edit_mode(self) -> None:
        """Leave edit mode back to navigation (sub-modes reset)."""
        self.editing = False
        self.vim_insert = False
        self.pending_d = False
        self.refresh()

    def on_key(self, event: Key) -> None:
        """Consume edit-table hits; let everything else fall through (R10).

        Navigation mode consumes nothing at all: arrows are handled by
        ScrollView's own bindings, every other key bubbles once to the
        screen.  In edit mode a table hit (or printable character) stops the
        event; a miss must fall through so screen bindings -- escape close
        guard, ctrl+s, ctrl+z -- keep working (the completion-popup lesson).
        """
        if not self.editing:
            return
        version = self.buffer.content_version
        was_editing = self.editing
        consumed = self._handle_edit_key(event)
        if consumed:
            event.stop()
            event.prevent_default()
            self._reveal_cursor()
            self.refresh()
            if (
                self.buffer.content_version != version
                or self.editing != was_editing
            ):
                self.post_message(DiffPane.PaneChanged(self))

    def _handle_edit_key(self, event: Key) -> bool:
        """Run one key against the active edit table; ``False`` = miss.

        Escape always belongs to the pane while editing: in the vim insert
        sub-mode it returns to normal, otherwise it exits edit mode (the
        screen's close guard only sees escape in navigation mode).
        """
        table = self._edit_table
        if table is None:
            return False
        if event.key == "escape":
            if table == "vim" and self.vim_insert:
                self.vim_insert = False
            else:
                self.exit_edit_mode()
            return True
        if table == "vsc":
            handler = _VSC_EDIT_KEYS.get(event.key)
            if handler is not None:
                handler(self)
                return True
            if event.is_printable and event.character is not None:
                self.buffer.insert_text(event.character)
                return True
            return False
        # vim: normal vs insert sub-mode
        if self.vim_insert:
            handler = _VIM_INSERT_KEYS.get(event.key)
            if handler is not None:
                handler(self)
                return True
            if event.is_printable and event.character is not None:
                self.buffer.insert_text(event.character)
                return True
            return False
        if self.pending_d:
            self.pending_d = False
            if event.key == "d":
                self.buffer.delete_lines()
                return True
            # any other key cancels the chord and is handled normally
        handler = _VIM_EDIT_KEYS.get(event.key)
        if handler is not None:
            handler(self)
            return True
        return False

    def _reveal_cursor(self) -> None:
        """Scroll vertically so the cursor row stays inside the view."""
        row = self.buffer.row
        top = self.scroll_offset.y
        view_h = max(1, self.size.height or 20)
        if row < top:
            self.scroll_to(y=row, animate=False)
        elif row >= top + view_h:
            self.scroll_to(y=row - view_h + 1, animate=False)
