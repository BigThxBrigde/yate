"""Two/three-way diff viewer screen: DiffScreen + per-side DiffPane.

A standalone modal tool screen (main-plan D2): one :class:`DiffPane` per file
side renders gutter badges plus diff-tinted lines from a
:class:`~yate.editor_view.diffview.PaneDiffState` the screen derives from the
L0 engine (:mod:`yate.editor_core.diff`).  The screen owns navigation
(alt+up/down), block copying (alt+left/right, WinMerge semantics: the arrow
names the target side), pane focus, per-side edit mode, saving and a
close guard for unsaved sides.

Key handling follows R10: in navigation mode :class:`DiffPane` consumes
nothing (arrow keys scroll the focused pane through ScrollView's own
bindings, everything else bubbles once to the screen's BINDINGS); in edit
mode a hit in the per-keymap edit table is stopped and executed, a miss
falls through so screen bindings keep working.

Usage (plan-c wires the entry points)::

    screen = DiffScreen(docs, "2way", keymaps, labels=["left", "right"])
    app.push_screen(screen)
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal, override

from rich.segment import Segment
from rich.style import Style
from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.color import Color
from textual.containers import Horizontal, Vertical
from textual.events import Key, Resize
from textual.geometry import Size
from textual.message import Message
from textual.screen import ModalScreen
from textual.scroll_view import ScrollView
from textual.strip import Strip
from textual.widgets import Static

from yate.editor_core.buffer import BufferReadOnlyError, Pos, TextBuffer
from yate.editor_core.diff import (
    DiffHunk,
    MergeRegion,
    diff3_regions,
    diff_lines,
    diff_words,
    hunk_replacement,
)
from yate.editor_core.document import Document
from yate.keymaps.registry import KeymapSet
from yate.logs import tracing
from yate.paths import load_tcss

from . import theme
from .scrollbars import apply_slim_scrollbars

log = tracing.get_logger(__name__)

#: Maximum lines accepted per file side.  ``diff_lines`` / ``diff3_regions``
#: run on the UI loop and ``difflib`` degrades badly beyond this size, so
#: callers must reject larger files up front instead of opening the screen;
#: the overlay entry point (:meth:`~yate.overlays.OverlayFlows.open_diff`)
#: compares against this constant directly so its message can name the file.
MAX_DIFF_LINES: int = 20000

#: Debounce window for post-edit recomputes (main-plan review R2): every
#: edit-mode keystroke posts a :class:`DiffPane.PaneChanged` and each
#: recompute re-runs the full difflib pass on the UI loop, so bursts of
#: keystrokes collapse into one recompute scheduled after the last one.
RECOMPUTE_DEBOUNCE_SECONDS: float = 0.15


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
# Edit-mode key tables (module-level functions, not classes)
# ---------------------------------------------------------------------------


def _undo(pane: DiffPane) -> None:
    """Undo the pane's last edit (adapter for the bool-returning API)."""
    pane.buffer.undo()


def _vsc_edit_keys() -> dict[str, Callable[[DiffPane], None]]:
    """VS Code-style edit table: cursor keys, deletion, newline, undo.

    Printable characters are handled by the pane itself (``is_printable``),
    so the table only lists named keys.
    """
    return {
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


def _vim_edit_keys() -> dict[str, Callable[[DiffPane], None]]:
    """Vim normal-mode edit table (main-plan D2: bounded subset).

    ``d`` arms the ``dd`` line-delete chord (second ``d`` deletes, any other
    key cancels); ``i``/``a``/``o`` switch to the insert sub-table.
    """

    def arm_dd(pane: DiffPane) -> None:
        pane.pending_d = True

    def insert_at(pane: DiffPane) -> None:
        pane.vim_insert = True

    def append_at(pane: DiffPane) -> None:
        # set_cursor clamps to the line end (same as the main vim keymap),
        # so "a" never spills onto the next line.
        pane.buffer.set_cursor((pane.buffer.row, pane.buffer.col + 1))
        pane.vim_insert = True

    def open_below(pane: DiffPane) -> None:
        pane.buffer.move_line_end()
        pane.buffer.insert_newline()
        pane.vim_insert = True

    return {
        "h": lambda pane: pane.buffer.move_left(),
        "j": lambda pane: pane.buffer.move_down(),
        "k": lambda pane: pane.buffer.move_up(),
        "l": lambda pane: pane.buffer.move_right(),
        "0": lambda pane: pane.buffer.set_cursor((pane.buffer.row, 0)),
        # Textual normalizes "$" to its unicode key name (probe: _character_to_key).
        "dollar_sign": lambda pane: pane.buffer.move_line_end(),
        "x": lambda pane: pane.buffer.delete_forward(),
        "d": arm_dd,
        "i": insert_at,
        "a": append_at,
        "o": open_below,
    }


def vim_insert_keys() -> dict[str, Callable[[DiffPane], None]]:
    """Vim insert sub-table: printable characters fall through to typing."""
    return {
        "enter": lambda pane: pane.buffer.insert_newline(),
        "backspace": lambda pane: pane.buffer.delete_backward(),
    }


# ---------------------------------------------------------------------------
# DiffPane
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
    _theme_unsubscribe: Callable[[], None] | None = None

    def __init__(
        self,
        doc: Document,
        title: str,
        read_only: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.doc = doc
        self.title = title
        self.read_only = read_only
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
        self._theme_unsubscribe = theme.subscribe(self._apply_theme)
        self._update_virtual_size()

    def on_unmount(self) -> None:
        """Detach from the theme broadcast (widgets own their painting)."""
        if self._theme_unsubscribe is not None:
            self._theme_unsubscribe()
            self._theme_unsubscribe = None

    def _apply_theme(self) -> None:
        """Paint this pane with the active theme (bg + scrollbar palette)."""
        t = theme.active()
        self.styles.background = t.bg
        s = self.styles
        s.scrollbar_background = Color(0, 0, 0, 0)
        s.scrollbar_background_hover = Color.parse(t.surface).with_alpha(0.35)
        s.scrollbar_color = t.border
        s.scrollbar_color_hover = t.fg_dim
        s.scrollbar_color_active = t.accent
        s.scrollbar_corner_color = Color(0, 0, 0, 0)
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

        cells: list[str] = []
        for ch in line:
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
        text_w = max(1, view_w - gutter_w)
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
            handler = _vsc_edit_keys().get(event.key)
            if handler is not None:
                handler(self)
                return True
            if event.is_printable and event.character is not None:
                self.buffer.insert_text(event.character)
                return True
            return False
        # vim: normal vs insert sub-mode
        if self.vim_insert:
            handler = vim_insert_keys().get(event.key)
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
        handler = _vim_edit_keys().get(event.key)
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


def _in_spans(spans: tuple[tuple[int, int], ...], index: int) -> bool:
    """Whether character *index* falls inside any half-open span."""
    return any(start <= index < end for start, end in spans)


# ---------------------------------------------------------------------------
# DiffScreen
# ---------------------------------------------------------------------------

_2WAY_ROLES: tuple[str, ...] = ("left", "right")
_3WAY_ROLES: tuple[str, ...] = ("base", "local", "remote")


class DiffScreen(ModalScreen[None]):
    """Full-screen two/three-way diff viewer (main-plan D2-D6).

    Owns the diff state: it recomputes regions from the side buffers,
    derives per-pane render states, navigates hunks/regions, copies blocks
    between sides and guards closing while a side is modified.
    """

    DEFAULT_CSS = load_tcss("diff-view.tcss")

    BINDINGS = [
        ("alt+up", "diff_prev", "previous change"),
        ("ctrl+up", "diff_prev", "previous change"),
        ("alt+down", "diff_next", "next change"),
        ("ctrl+down", "diff_next", "next change"),
        ("alt+right", "copy_right", "copy to right"),
        ("alt+left", "copy_left", "copy to left"),
        ("tab", "cycle_focus_next", "next pane"),
        ("shift+tab", "cycle_focus_prev", "previous pane"),
        ("ctrl+1", "focus_pane(0)", "focus pane 1"),
        ("ctrl+2", "focus_pane(1)", "focus pane 2"),
        ("ctrl+3", "focus_pane(2)", "focus pane 3"),
        ("enter", "toggle_edit", "edit focused side"),
        ("e", "toggle_edit", "edit focused side"),
        ("ctrl+s", "save_pane", "save focused side"),
        ("ctrl+z", "undo_pane", "undo focused side"),
        ("escape", "dismiss_guarded", "close"),
        ("q", "dismiss_guarded", "close"),
    ]

    def __init__(
        self,
        docs: list[Document],
        mode: Literal["2way", "3way"],
        keymaps: KeymapSet,
        labels: list[str] | None = None,
    ) -> None:
        super().__init__()
        expected = 2 if mode == "2way" else 3
        if len(docs) != expected:
            raise ValueError(
                f"{mode} screen needs {expected} documents, got {len(docs)}"
            )
        self._docs = docs
        self._mode = mode
        self._keymaps = keymaps
        roles = _2WAY_ROLES if mode == "2way" else _3WAY_ROLES
        self._labels: list[str] = [
            labels[i] if labels is not None and i < len(labels) else role
            for i, role in enumerate(roles)
        ]
        #: Index of the selected hunk / merge region; -1 = none selected.
        self._current: int = -1
        #: Non-same regions: ``DiffHunk`` list (2way) or ``MergeRegion``
        #: list (3way).  Rebuilt by :meth:`_recompute`.
        self._regions: list[DiffHunk] | list[MergeRegion] = []
        #: Full region list of a 3way merge (``same`` included) -- needed
        #: to paint the untouched spans between merge regions.
        self._all_regions: list[MergeRegion] = []
        #: Close-guard latch: the next escape/q pops after one warning.
        self._confirm_close: bool = False
        #: Edit table chosen when edit mode was entered (header hint).
        self._edit_table: str = "vsc"
        self._panes: list[DiffPane] = []
        self._hint: str = ""
        #: Pending debounced recompute handle; ``None`` when nothing scheduled.
        self._recompute_handle: asyncio.TimerHandle | None = None

    # ------------------------------------------------------------ compose

    @override
    def compose(self) -> ComposeResult:
        """Header + one DiffPane per side + bottom hint line."""
        with Vertical(id="diff-screen"):
            yield Static("", id="diff-header")
            with Horizontal(id="diff-body"):
                for i, doc in enumerate(self._docs):
                    yield DiffPane(
                        doc,
                        title=self._labels[i],
                        read_only=doc.buffer.read_only,
                        id=f"diff-pane-{i}",
                    )
            yield Static("", id="diff-hint")

    def on_mount(self) -> None:
        """Cache panes, compute the initial diff and focus the first pane."""
        self._panes = list(self.query(DiffPane))
        self._recompute()
        if self._panes:
            self._panes[0].focus()

    def on_unmount(self) -> None:
        """Cancel a pending debounced recompute (the screen is going away)."""
        if self._recompute_handle is not None:
            self._recompute_handle.cancel()
            self._recompute_handle = None

    @on(DiffPane.PaneChanged)
    def _pane_changed(self, event: DiffPane.PaneChanged) -> None:
        """A pane edited its buffer or toggled edit mode: recompute (debounced).

        Every keystroke in edit mode posts a :class:`DiffPane.PaneChanged`;
        each recompute re-runs the full difflib pass on the UI loop, so a
        burst collapses into one :meth:`_recompute` scheduled
        :data:`RECOMPUTE_DEBOUNCE_SECONDS` after the last message.  The
        close-guard latch resets here -- at the moment the action happens --
        not inside the deferred recompute, which may fire after the user
        already started the two-step close.
        """
        self._confirm_close = False
        if self._recompute_handle is not None:
            self._recompute_handle.cancel()
        self._recompute_handle = asyncio.get_running_loop().call_later(
            RECOMPUTE_DEBOUNCE_SECONDS, self._recompute
        )

    # ------------------------------------------------------------ helpers

    @property
    def _is_3way(self) -> bool:
        """Whether the screen shows a three-way merge."""
        return self._mode == "3way"

    def _focused_pane(self) -> DiffPane | None:
        """The focused DiffPane, or ``None`` when focus moved elsewhere."""
        focused = self.focused
        return focused if isinstance(focused, DiffPane) else None

    def _set_hint(self, text: str) -> None:
        """Update the bottom hint line."""
        self._hint = text
        self.query_one("#diff-hint", Static).update(text)

    def _hint_text(self) -> str:
        """Current hint text (test hook)."""
        return self._hint

    def _update_header(self) -> None:
        """Repaint the header: per-side title/path/modified + key hints."""
        t = theme.active()
        text = Text()
        focused = self._focused_pane()
        for pane in self._panes:
            if text.plain:
                text.append("   ", style=t.border)
            text.append(f"{pane.title}", style=t.fg_bright)
            text.append(f" {pane.doc.name}", style=t.fg_muted)
            if pane.doc.modified:
                text.append(" ●", style=t.yellow)
            if pane is focused and pane.editing:
                text.append(f" [EDIT:{self._edit_table}]", style=f"bold {t.green}")
        text.append(
            "   alt+↓/↑ change · alt+←/→ copy · enter edit"
            " · ctrl+s save · esc close",
            style=t.fg_dim,
        )
        self.query_one("#diff-header", Static).update(text)

    # ------------------------------------------------------------ diffing

    def _recompute(self) -> None:
        """Re-run the L0 diff and repaint every pane + header.

        Pure render refresh: the close-guard latch is reset by the actions
        that change content (:meth:`_pane_changed`, :meth:`_apply_copy`,
        :meth:`action_undo_pane`), never by a deferred recompute.  Direct
        callers (copy, undo, mount) cancel a pending debounced recompute
        here, so the synchronous result is final.
        """
        if self._recompute_handle is not None:
            self._recompute_handle.cancel()
            self._recompute_handle = None
        if self._is_3way:
            base, local, remote = (doc.buffer.lines for doc in self._docs)
            self._all_regions = diff3_regions(base, local, remote)
            self._regions = [r for r in self._all_regions if r.kind != "same"]
        else:
            result = diff_lines(self._docs[0].buffer.lines, self._docs[1].buffer.lines)
            self._regions = list(result.hunks)
            self._all_regions = []
        if self._current >= len(self._regions):
            self._current = len(self._regions) - 1
        self._dispatch_states()
        self._update_header()

    def _dispatch_states(self) -> None:
        """Derive each pane's :class:`PaneDiffState` from the cached diff."""
        if self._is_3way:
            states = self._states_3way()
        else:
            states = self._states_2way()
        for pane, state in zip(self._panes, states):
            pane.set_state(state)

    def _states_2way(self) -> list[PaneDiffState]:
        """Paint states for the two sides of a line diff."""
        hunks = [r for r in self._regions if isinstance(r, DiffHunk)]
        left, right = self._docs[0].buffer.lines, self._docs[1].buffer.lines
        states: list[list[str]] = [
            ["same"] * len(left),
            ["same"] * len(right),
        ]
        inline: list[dict[int, tuple[tuple[int, int], ...]]] = [{}, {}]
        for hunk in hunks:
            if hunk.kind == "insert":
                marks = [(1, hunk.b_start, hunk.b_end, "added")]
            elif hunk.kind == "delete":
                marks = [(0, hunk.a_start, hunk.a_end, "removed")]
            else:
                marks = [
                    (0, hunk.a_start, hunk.a_end, "changed"),
                    (1, hunk.b_start, hunk.b_end, "changed"),
                ]
            for side, start, end, label in marks:
                for row in range(start, end):
                    states[side][row] = label
            if hunk.kind == "replace":
                pairs = min(hunk.a_end - hunk.a_start, hunk.b_end - hunk.b_start)
                for k in range(pairs):
                    a_row, b_row = hunk.a_start + k, hunk.b_start + k
                    a_ranges, b_ranges = diff_words(left[a_row], right[b_row])
                    if a_ranges:
                        inline[0][a_row] = tuple(a_ranges)
                    if b_ranges:
                        inline[1][b_row] = tuple(b_ranges)
        current = self._current
        cur: list[frozenset[int]] = [frozenset(), frozenset()]
        if 0 <= current < len(hunks):
            hunk = hunks[current]
            cur[0] = frozenset(range(hunk.a_start, hunk.a_end))
            cur[1] = frozenset(range(hunk.b_start, hunk.b_end))
        return [
            PaneDiffState(tuple(states[0]), inline[0], cur[0]),
            PaneDiffState(tuple(states[1]), inline[1], cur[1]),
        ]

    def _states_3way(self) -> list[PaneDiffState]:
        """Paint states for base/local/remote of a merge classification."""
        base, local, remote = (doc.buffer.lines for doc in self._docs)
        states: list[list[str]] = [
            ["same"] * len(base),
            ["same"] * len(local),
            ["same"] * len(remote),
        ]
        spans: dict[str, tuple[int, int]] = {}
        for region in self._all_regions:
            if region.kind == "same":
                continue
            spans["base"] = (region.base_start, region.base_end)
            spans["local"] = (region.local_start, region.local_end)
            spans["remote"] = (region.remote_start, region.remote_end)
            conflict = region.kind == "conflict"
            base_label = "conflict" if conflict else "changed"
            local_label = (
                "conflict"
                if conflict
                else ("changed" if region.kind in ("local", "both") else "same")
            )
            remote_label = (
                "conflict"
                if conflict
                else ("changed" if region.kind in ("remote", "both") else "same")
            )
            for side, label in (
                ("base", base_label),
                ("local", local_label),
                ("remote", remote_label),
            ):
                if label == "same":
                    continue
                start, end = spans[side]
                for row in range(start, end):
                    states[_3WAY_ROLES.index(side)][row] = label
        current = self._current
        cur: list[frozenset[int]] = [frozenset(), frozenset(), frozenset()]
        if 0 <= current < len(self._regions):
            region = self._regions[current]
            if isinstance(region, MergeRegion):
                cur[0] = frozenset(range(region.base_start, region.base_end))
                cur[1] = frozenset(range(region.local_start, region.local_end))
                cur[2] = frozenset(range(region.remote_start, region.remote_end))
        return [PaneDiffState(tuple(states[i]), {}, cur[i]) for i in range(3)]

    def _region_anchors(self, index: int) -> list[int]:
        """Start row of region *index* on each pane's side."""
        region = self._regions[index]
        if isinstance(region, DiffHunk):
            return [region.a_start, region.b_start]
        return [region.base_start, region.local_start, region.remote_start]

    def _nearest_region(self, row: int, side: int) -> int:
        """Index of the region whose *side* start is nearest to *row*."""
        if not self._regions:
            return -1
        return min(
            range(len(self._regions)),
            key=lambda i: abs(self._region_anchors(i)[side] - row),
        )

    # ---------------------------------------------------------- navigation

    def _show_current(self) -> None:
        """Repaint states and scroll every pane to the selected change."""
        self._dispatch_states()
        anchors = self._region_anchors(self._current)
        for pane, anchor in zip(self._panes, anchors):
            pane.scroll_to(y=max(0, anchor), animate=False)
        self._update_header()

    def action_diff_prev(self) -> None:
        """Step to the previous change (clamped, no wrap-around)."""
        if not self._regions:
            self._set_hint("no differences")
            return
        if self._current <= 0:
            self._current = 0
            self._show_current()
            self._set_hint("no previous change")
            return
        self._current -= 1
        self._show_current()

    def action_diff_next(self) -> None:
        """Step to the next change (clamped, no wrap-around)."""
        count = len(self._regions)
        if count == 0:
            self._set_hint("no differences")
            return
        if self._current + 1 >= count:
            self._current = count - 1
            self._show_current()
            self._set_hint("no next change")
            return
        self._current += 1
        self._show_current()

    # -------------------------------------------------------------- copying

    def action_copy_right(self) -> None:
        """Copy the selected change onto the right side (2way left→right,
        3way local→remote)."""
        self._copy(direction=1)

    def action_copy_left(self) -> None:
        """Copy the selected change onto the left side (2way right→left,
        3way remote→local)."""
        self._copy(direction=-1)

    def _copy(self, direction: int) -> None:
        """Apply the selected change to the target side named by *direction*."""
        if self._current < 0 or self._current >= len(self._regions):
            self._set_hint("no change selected (alt+down to step)")
            return
        if self._is_3way:
            self._copy_3way(direction)
        else:
            self._copy_2way(direction)

    def _apply_copy(
        self, target: Document, triple: tuple[Pos, Pos, str], side: int
    ) -> None:
        """Write a ``hunk_replacement`` triple into the target side."""
        start, end, text = triple
        try:
            target.buffer.replace_range(start, end, text)
        except BufferReadOnlyError:
            self._set_hint("side is read-only")
            log.debug("diff copy refused: target side is read-only")
            return
        self._confirm_close = False
        self._recompute()
        self._current = self._nearest_region(start[0], side)
        if self._current >= 0:
            self._show_current()
        else:
            self._set_hint("sides are identical")

    def _copy_2way(self, direction: int) -> None:
        """2way copy: the arrow names the target side (main-plan D4)."""
        hunk = self._regions[self._current]
        if not isinstance(hunk, DiffHunk):
            return
        if direction > 0:
            target, source, side = self._docs[1], self._docs[0], 1
            triple = hunk_replacement(
                target.buffer.lines, hunk, source.buffer.lines, copy_into="a"
            )
        else:
            target, source, side = self._docs[0], self._docs[1], 0
            triple = hunk_replacement(
                target.buffer.lines, hunk, source.buffer.lines, copy_into="b"
            )
        self._apply_copy(target, triple, side)

    def _copy_3way(self, direction: int) -> None:
        """3way copy between local (1) and remote (2); base is never a target."""
        region = self._regions[self._current]
        if not isinstance(region, MergeRegion):
            return
        src_side, dst_side = (1, 2) if direction > 0 else (2, 1)
        source, target = self._docs[src_side], self._docs[dst_side]
        s_start, s_end = (
            (region.local_start, region.local_end)
            if src_side == 1
            else (region.remote_start, region.remote_end)
        )
        t_start, t_end = (
            (region.remote_start, region.remote_end)
            if dst_side == 2
            else (region.local_start, region.local_end)
        )
        if source.buffer.lines[s_start:s_end] == target.buffer.lines[t_start:t_end]:
            self._set_hint("nothing to copy")
            return
        hunk = DiffHunk(
            kind="replace",
            a_start=s_start,
            a_end=s_end,
            b_start=t_start,
            b_end=t_end,
        )
        triple = hunk_replacement(
            target.buffer.lines, hunk, source.buffer.lines, copy_into="a"
        )
        self._apply_copy(target, triple, dst_side)

    # --------------------------------------------------------------- focus

    def _cycle_focus(self, delta: int) -> None:
        """Rotate focus among the diff panes."""
        panes = self._panes
        if not panes:
            return
        focused = self._focused_pane()
        index = panes.index(focused) if focused is not None else 0
        panes[(index + delta) % len(panes)].focus()
        self._update_header()

    def action_cycle_focus_next(self) -> None:
        """Move focus to the next pane."""
        self._cycle_focus(1)

    def action_cycle_focus_prev(self) -> None:
        """Move focus to the previous pane."""
        self._cycle_focus(-1)

    def action_focus_pane(self, index: int) -> None:
        """Focus pane *index* directly (no-op when it does not exist)."""
        if 0 <= index < len(self._panes):
            self._panes[index].focus()
            self._update_header()

    # ------------------------------------------------------ edit/save/undo

    def action_toggle_edit(self) -> None:
        """Toggle edit mode on the focused pane (page header shows it)."""
        pane = self._focused_pane()
        if pane is None:
            return
        if pane.editing:
            pane.exit_edit_mode()
        else:
            if pane.buffer.read_only:
                self._set_hint("side is read-only")
                return
            self._edit_table = "vim" if self._keymaps.name == "vim" else "vsc"
            pane.enter_edit_mode(self._edit_table)
        self._update_header()

    def action_save_pane(self) -> None:
        """Save the focused side's document; report failures as hints."""
        pane = self._focused_pane()
        if pane is None:
            return
        try:
            pane.doc.save()
        except BufferReadOnlyError:
            self._set_hint("side is read-only")
            return
        except (OSError, ValueError) as exc:
            self._set_hint(f"save failed: {exc}")
            log.warning("diff screen save failed: %s", exc)
            return
        self._set_hint("saved")
        self._update_header()

    def action_undo_pane(self) -> None:
        """Undo the focused side's last edit (works outside edit mode)."""
        pane = self._focused_pane()
        if pane is None:
            return
        try:
            pane.buffer.undo()
        except BufferReadOnlyError:
            self._set_hint("side is read-only")
            return
        self._confirm_close = False
        self._recompute()

    # -------------------------------------------------------------- closing

    def action_dismiss_guarded(self) -> None:
        """Two-step close: first press warns, second press pops.

        Any edit / copy resets the latch (via :meth:`_recompute`), so the
        warning always reflects the state at warning time.
        """
        if self._confirm_close:
            self.dismiss(None)
            return
        self._confirm_close = True
        if any(doc.modified for doc in self._docs):
            self._set_hint("unsaved changes — press esc again to close")
        else:
            self._set_hint("press esc again to close")
