"""Marks and jump-list navigation orchestration (L3 flows, issue IKUOCI).

All durable state lives on the L1 session (``EditorSession.marks`` /
``EditorSession.jumps``); this module only sequences the verbs: resolve
targets, switch tabs through the injected ``activate_doc``, reposition and
reveal the buffer cursor, and push the L2 overview screens through the
injected ``push_overlay`` verb.  No App handle is held here (capability
injection, issue IKJB0Q).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

from textual.screen import Screen

from yate.editor_components.marks_palette import (
    JumpRow,
    JumpsScreen,
    MarkRow,
    MarksScreen,
)
from yate.editor_components.panes import PaneManager
from yate.editor_core import Document
from yate.flows import MessageFn
from yate.session import MARK_NAME_CHARS, EditorSession, JumpEntry

#: Preview text width in the marks overview rows (display-only truncation).
PREVIEW_MAX: int = 48


class NavigationFlows:
    """Marks and jump-list navigation flow (issue IKUOCI, L3 orchestration).

    State lives in EditorSession (L1); this module only orchestrates:
    resolve targets, switch tabs via activate_doc, reveal cursors, and
    push the L2 overview screens through the injected push_overlay verb.
    """

    def __init__(
        self,
        session: EditorSession,
        panes: PaneManager,
        activate_doc: Callable[[Document], None],
        push_overlay: Callable[[Screen[None]], None],
        message: MessageFn,
        refresh: Callable[[], None],
    ) -> None:
        self._session = session
        self._panes = panes
        self._activate_doc = activate_doc
        self._push_overlay = push_overlay
        self._message = message
        self._refresh = refresh

    # ---------------------------------------------------------------- verbs

    def set_mark(self, name: str) -> None:
        """Set *name* on the active document at the cursor (D6 creation path).

        An illegal name is refused with a warning and no state change.
        """
        if not (len(name) == 1 and name in MARK_NAME_CHARS):
            self._message(f"mark name must be a-z: {name}", "warn")
            return
        doc = self._session.doc
        buf = doc.buffer
        self._session.marks.set(doc.uid, name, buf.row, buf.col)
        self._message(f"mark {name} set at line {buf.row + 1}", "info")
        self._refresh()

    def jump_to_mark(self, name: str, uid: int | None = None) -> None:
        """Jump to mark *name*, switching tabs when the target buffer differs.

        With *uid* (the panel path) the mark is taken from that buffer.  D6:
        otherwise the first open buffer holding the mark wins (active tab
        first); with no holder anywhere the mark is set here instead -- the
        ``:mark`` command is the only creation entry in v1.
        """
        session = self._session
        if uid is not None:
            doc = session.doc_by_uid(uid)
            if doc is None:
                self._message("mark target buffer not open", "warn")
                return
            mark = session.marks.get(uid, name)
            if mark is None:
                self._message(f"no such mark: {name}", "warn")
                return
            session.push_jump()
            self._land(doc, mark.row, mark.col)
            return
        active = session.doc
        ordered = [active, *(doc for doc in session.docs if doc is not active)]
        for doc in ordered:
            mark = session.marks.get(doc.uid, name)
            if mark is not None:
                session.push_jump()
                self._land(doc, mark.row, mark.col)
                return
        self.set_mark(name)

    def delete_mark(self, name: str, uid: int | None = None) -> bool:
        """Delete mark *name* (the *uid* buffer for the panel, else active).

        Returns ``False`` and warns when the mark was not set (AC6).
        """
        target_uid = uid if uid is not None else self._session.doc.uid
        if not self._session.marks.delete(target_uid, name):
            self._message(f"no such mark: {name}", "warn")
            return False
        self._refresh()
        return True

    def jump_back(self) -> None:
        """Step one entry back; the boundary is an info hint, not a loop."""
        target = self._session.jump_back()
        if target is None:
            self._message("no earlier jump", "info")
            return
        self._go_to(target)

    def jump_forward(self) -> None:
        """Step one entry forward; the boundary is an info hint, not a loop."""
        target = self._session.jump_forward()
        if target is None:
            self._message("no later jump", "info")
            return
        self._go_to(target)

    def show_marks(self) -> None:
        """Push the marks overview over every open buffer's marks."""
        rows: list[MarkRow] = []
        for uid, name, mark in self._session.marks.all_marks():
            doc = self._session.doc_by_uid(uid)
            if doc is None:
                continue
            buf = doc.buffer
            clamped = min(mark.row, buf.line_count - 1)
            rows.append(MarkRow(
                uid=uid,
                name=name,
                doc_name=doc.display_path,
                line_no=clamped + 1,
                preview=buf.lines[clamped][:PREVIEW_MAX],
            ))
        self._push_overlay(MarksScreen(
            rows,
            on_jump=self._on_panel_jump,
            on_delete=self._on_panel_delete,
        ))

    def show_jumps(self) -> None:
        """Push the jump overview: back stack, current pointer, forward stack.

        Stacked entries re-resolve their display path against the open
        buffers (a save-as renames the document after the push snapshot);
        the rows handed to the L2 screen carry the resolved name.
        """
        back, forward = self._session.jumps.stacks()
        rows = [
            JumpRow(entry=self._display_entry(entry), side="back", current=False)
            for entry in back
        ]
        rows.append(JumpRow(
            entry=self._session.current_jump_entry(),
            side="current",
            current=True,
        ))
        rows.extend(
            JumpRow(entry=self._display_entry(entry), side="forward", current=False)
            for entry in reversed(forward)
        )
        self._push_overlay(JumpsScreen(
            rows,
            on_jump=self._on_jump_entry,
            message=self._message,
        ))

    # -------------------------------------------------------------- helpers

    def _display_entry(self, entry: JumpEntry) -> JumpEntry:
        """Re-resolve *entry*'s display path against the open buffers.

        A stacked entry carries the display snapshot taken at push time;
        a save-as renames the document afterwards, so the overview resolves
        the current name through ``doc_by_uid`` (L1) and falls back to the
        snapshot when the buffer has closed.
        """
        doc = self._session.doc_by_uid(entry.uid)
        if doc is None:
            return entry
        return replace(entry, path=doc.display_path)

    def _on_panel_jump(self, row: MarkRow) -> None:
        """Marks-panel enter: jump through the panel (uid-bound) path."""
        self.jump_to_mark(row.name, uid=row.uid)

    def _on_panel_delete(self, row: MarkRow) -> None:
        """Marks-panel ``d``: delete through the panel (uid-bound) path."""
        self.delete_mark(row.name, uid=row.uid)

    def _on_jump_entry(self, row: JumpRow) -> None:
        """Jumps-panel enter: record the origin, then jump (D7).

        The fresh push clears the forward branch past the chosen entry; the
        panel hint says so.
        """
        if row.current:
            return
        self._session.push_jump()
        self._go_to(row.entry)

    def _go_to(self, entry: JumpEntry) -> None:
        """Land on a jump-list *entry*; a closed target buffer warns."""
        doc = self._session.doc_by_uid(entry.uid)
        if doc is None:
            self._message("jump target buffer not open", "warn")
            return
        self._land(doc, entry.row, entry.col)

    def _land(self, doc: Document, row: int, col: int) -> None:
        """Activate *doc* if needed, clamp the position and reveal cursors."""
        if doc is not self._session.doc:
            self._activate_doc(doc)
        buf = doc.buffer
        row = min(row, buf.line_count - 1)
        col = min(col, len(buf.lines[row]))
        buf.set_cursor((row, col))
        buf.anchor = None
        for view in self._panes.views_for(doc):
            view.reveal_cursor()
        self._refresh()
        self._message(f"jumped to line {row + 1}", "info")
