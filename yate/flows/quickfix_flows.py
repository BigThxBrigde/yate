"""Quickfix dock orchestration (L3 flows, quickfix-nav wave-c).

The durable state is the shared L1 :class:`~yate.session.QuickFixList`
(held by this flow and the panel; no widget, document or server
reference inside it); this module only sequences the verbs: replace a
provider's result slice, open / close / toggle the docked panel, step
the cursor with wrap-around and jump to the selected entry.  Panel
visibility goes through the injected ``show`` / ``hide`` display
switches -- the editor owns the widget, no App handle is held here
(capability injection, issue IKJB0Q).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from yate.editor_components.quickfix_panel import QuickFixPanel
from yate.editor_core.project_search import FileMatch
from yate.flows import MessageFn
from yate.session import EditorSession, QuickFixEntry, QuickFixList

#: ``reveal(path, row, col)`` -- open the target document if needed and
#: land the cursor on the entry (injected by the editor).
type RevealFn = Callable[[Path, int, int], None]

#: ``show()`` / ``hide()`` -- the docked panel display switches (R13: the
#: editor owns the widget and only flips ``display``; no styling here).
type ShowFn = Callable[[], None]
type HideFn = Callable[[], None]

#: ``refresh()`` -- the editor repaint verb (injected).
type RefreshFn = Callable[[], None]


class QuickFixFlows:
    """Quickfix list orchestration over the shared L1 result set.

    One jump pushes exactly one jump-list entry (the origin is captured
    before the reveal and pushed only on success, D7 shape); empty result
    sets keep a stale panel closed.
    """

    def __init__(
        self,
        session: EditorSession,
        panel: QuickFixPanel,
        *,
        entries: QuickFixList,
        reveal: RevealFn,
        show: ShowFn,
        hide: HideFn,
        message: MessageFn,
        refresh: RefreshFn,
    ) -> None:
        self._session = session
        self._panel = panel
        # The panel shares this same instance (single source of truth);
        # it is built before the flow because the panel callbacks resolve
        # the flow lazily, so the list is created by the assembly factory
        # and handed to both.
        self._list = entries
        self._reveal = reveal
        self._show = show
        self._hide = hide
        self._message = message
        self._refresh = refresh

    # ------------------------------------------------------------- results

    def set_results(
        self, provider: str, entries: list[QuickFixEntry], label: str
    ) -> None:
        """Replace *provider*'s slice and open the panel on a non-empty set.

        An empty set keeps a stale panel closed and reports the empty
        state on the message line.
        """
        self._list.replace(provider, entries, label)
        if entries:
            self.open()
        else:
            self._repaint()
            # Keep a stale panel from lingering over an emptied list.
            # Providers own their explicit empty-state messages; a silent
            # clear must not overwrite the last search/replace report.
            self._hide()

    def set_search_results(self, matches: list[FileMatch]) -> None:
        """Flatten project-search hits into entries and publish them.

        One entry per hit row keeps the panel cursor aligned with the
        search screen's own flat table; an empty batch clears the previous
        search slice without emitting a message that could replace the
        search/replace report on the message line.
        """
        entries = [
            QuickFixEntry(
                provider="search",
                path=file_match.path,
                row=hit.row,
                col=hit.start,
                label=file_match.hit_lines.get(hit.row, "").rstrip("\r\n"),
            )
            for file_match in matches
            for hit in file_match.matches
        ]
        self.set_results("search", entries, "project search")

    def open(self) -> None:
        """Show the docked panel over the current result set."""
        self._repaint()
        self._show()

    def close(self) -> None:
        """Hide the panel; the result set stays intact for a later reopen."""
        self._hide()

    def toggle(self) -> None:
        """Flip the panel between visible and hidden."""
        if self._panel.display:
            self.close()
        else:
            self.open()

    # ------------------------------------------------------------- cursor

    def next(self) -> None:
        """Step one entry forward (wrapping) and jump to it."""
        if not self._list.entries:
            self._message("no quickfix entries", "info")
            return
        self._list.step(1)
        self.jump_to(self._list.selected)

    def prev(self) -> None:
        """Step one entry backward (wrapping) and jump to it."""
        if not self._list.entries:
            self._message("no quickfix entries", "info")
            return
        self._list.step(-1)
        self.jump_to(self._list.selected)

    def jump_to(self, index: int) -> None:
        """Jump to *index*, pushing one jump-list entry only on success.

        The origin is captured before the reveal but pushed afterward with
        an explicit document/position, so a failed ``reveal`` leaves both
        jump stacks untouched.  Out-of-range indices are ignored with a
        message; an unopenable target reports the error instead of raising.
        """
        entry = self._list.at(index)
        if entry is None:
            self._message(f"no quickfix entry at index {index}", "warn")
            return
        self._list.selected = index
        origin = self._session.doc
        row = origin.buffer.row
        col = origin.buffer.col
        try:
            self._reveal(entry.path, entry.row, entry.col)
        except OSError:
            self._message(f"cannot open {entry.path}", "error")
            return
        self._session.push_jump(origin, row=row, col=col)
        self._repaint()
        self._refresh()
        self._message(f"jumped to {entry.path}:{entry.row + 1}", "info")

    # ------------------------------------------------------- read-only API

    @property
    def active_entries(self) -> tuple[QuickFixEntry, ...]:
        """The current result set in display order (tests and providers)."""
        return self._list.snapshot()

    @property
    def selected(self) -> int:
        """The selected entry index in the result set."""
        return self._list.selected

    # -------------------------------------------------------------- helpers

    def _repaint(self) -> None:
        """Repaint the panel body from the current result set."""
        self._panel.repaint()
