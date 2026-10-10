"""Two/three-way diff viewer screen (DiffScreen).

The screen half of the diff viewer, split from the original single module
(big-module-split wave b): one :class:`~yate.editor_view.diff_pane.DiffPane`
per file side renders gutter badges plus diff-tinted lines from a
:class:`~yate.editor_view.diff_pane.PaneDiffState` the screen derives from
the L0 engine (:mod:`yate.editor_core.diff`).  The screen owns navigation
(alt+up/down), block copying (alt+left/right, WinMerge semantics: the arrow
names the target side), pane focus, per-side edit mode, saving and a
close guard for unsaved sides.

Usage (plan-c wires the entry points)::

    screen = DiffScreen(docs, "2way", keymaps, labels=["left", "right"])
    app.push_screen(screen)
"""

from __future__ import annotations

import asyncio
from typing import Literal, override

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Static

from yate.editor_core.buffer import BufferReadOnlyError, Pos
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

from yate.editor_view import theme
from yate.editor_view.diff_pane import DiffPane, PaneDiffState

log = tracing.get_logger(__name__)

#: Maximum lines accepted per file side.  ``diff_lines`` / ``diff3_regions``
#: run on the UI loop and ``difflib`` degrades badly beyond this size, so
#: callers must reject larger files up front instead of opening the screen;
#: the overlay entry point (:meth:`~yate.flows.overlay_flows.OverlayFlows.open_diff`)
#: compares against this constant directly so its message can name the file.
MAX_DIFF_LINES: int = 20000

#: Debounce window for post-edit recomputes (main-plan review R2): every
#: edit-mode keystroke posts a :class:`DiffPane.PaneChanged` and each
#: recompute re-runs the full difflib pass on the UI loop, so bursts of
#: keystrokes collapse into one recompute scheduled after the last one.
RECOMPUTE_DEBOUNCE_SECONDS: float = 0.15

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

        Any edit / copy resets the latch (:meth:`_pane_changed`,
        :meth:`_apply_copy`, :meth:`action_undo_pane`), so the warning
        always reflects the state at warning time.
        """
        if self._confirm_close:
            self.dismiss(None)
            return
        self._confirm_close = True
        if any(doc.modified for doc in self._docs):
            self._set_hint("unsaved changes — press esc again to close")
        else:
            self._set_hint("press esc again to close")
