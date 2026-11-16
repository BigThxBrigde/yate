"""NavigationFlows orchestration: marks, jump list and overview pushes.

No Textual App: every collaborator is a fake (panes/views, activate_doc,
push_overlay, message, refresh) except the session, which uses the real
``EditorSession`` / ``Document`` types with two manual multi-line buffers
(the plan-a session fixture shape).  All durable state assertions read the
L1 model; the screens are asserted by identity and their injected rows.
"""

from __future__ import annotations

from typing import cast

from textual.screen import Screen

from yate.config import YateConfig
from yate.editor_components.marks_palette import JumpsScreen, MarksScreen
from yate.editor_components.panes import PaneManager
from yate.editor_core import Document
from yate.editor_core.buffer import TextBuffer
from yate.flows.navigation_flows import NavigationFlows
from yate.session import EditorSession, Mark


# ------------------------------------------------------------------- fakes


class _FakeView:
    """Records ``reveal_cursor`` calls (the EditorView slice the flow uses)."""

    def __init__(self) -> None:
        self.reveals = 0

    def reveal_cursor(self) -> None:
        self.reveals += 1


class _FakePanes:
    """The PaneManager slice NavigationFlows drives: one view per doc."""

    def __init__(self) -> None:
        self.view = _FakeView()

    def views_for(self, doc: Document) -> list[_FakeView]:
        return [self.view]


class _Shell:
    """Records the injected capability verbs (no App handle anywhere)."""

    def __init__(self) -> None:
        self.activated: list[Document] = []
        self.pushed: list[Screen[None]] = []
        self.messages: list[tuple[str, str]] = []
        self.refreshes = 0

    def activate_doc(self, doc: Document) -> None:
        self.activated.append(doc)

    def push_overlay(self, screen: Screen[None]) -> None:
        self.pushed.append(screen)

    def message(self, text: str, kind: str) -> None:
        self.messages.append((text, kind))

    def refresh(self) -> None:
        self.refreshes += 1


def _session() -> EditorSession:
    """A headless session with two manual multi-line documents (no disk)."""
    session = EditorSession(YateConfig())
    for text in ("alpha\nbeta\ngamma\ndelta\n", "one\ntwo\nthree\nfour\n"):
        session.docs.append(Document(None, TextBuffer(text)))
    session.index = 0
    return session


def _flows() -> tuple[NavigationFlows, EditorSession, _FakePanes, _Shell]:
    """A flow wired to recorders; returns ``(flows, session, panes, shell)``."""
    session = _session()
    panes = _FakePanes()
    shell = _Shell()
    flows = NavigationFlows(
        session=session,
        panes=cast(PaneManager, panes),
        activate_doc=shell.activate_doc,
        push_overlay=shell.push_overlay,
        message=shell.message,
        refresh=shell.refresh,
    )
    return flows, session, panes, shell


def _last_message(shell: _Shell) -> tuple[str, str]:
    assert shell.messages, "expected a message, got none"
    return shell.messages[-1]


# ------------------------------------------------------------------ set


def test_set_mark_records_cursor_and_messages() -> None:
    """set_mark stores the cursor on the active doc and announces it."""
    flows, session, _panes, shell = _flows()
    session.doc.buffer.set_cursor((2, 1))

    flows.set_mark("a")

    uid = session.doc.uid
    assert session.marks.get(uid, "a") == Mark(2, 1)
    text, kind = _last_message(shell)
    assert "mark a set" in text
    assert kind == "info"
    assert shell.refreshes == 1


def test_set_mark_rejects_illegal_name() -> None:
    """An illegal name warns and leaves the markbook untouched."""
    flows, session, _panes, shell = _flows()

    flows.set_mark("A")

    assert session.marks.all_marks() == []
    text, kind = _last_message(shell)
    assert "a-z" in text
    assert kind == "warn"


# ------------------------------------------------------- jump to a mark


def test_jump_to_mark_same_doc_moves_cursor_clamped() -> None:
    """An out-of-range mark row clamps to the last line (D3) and pushes."""
    flows, session, panes, shell = _flows()
    uid = session.doc.uid
    session.marks.set(uid, "a", 50, 0)

    flows.jump_to_mark("a")

    assert session.doc.buffer.cursor == (4, 0)
    back, _forward = session.jumps.stacks()
    assert len(back) == 1
    assert panes.view.reveals == 1
    assert shell.refreshes == 1


def test_jump_to_mark_switches_tab_via_activate_doc() -> None:
    """A mark on the other tab activates it; the push records the origin."""
    flows, session, _panes, shell = _flows()
    doc_a, doc_b = session.docs
    doc_b.buffer.set_cursor((3, 1))
    session.marks.set(doc_b.uid, "a", 3, 1)

    flows.jump_to_mark("a")

    # The injected activate_doc verb is a recorder, so session.doc does not
    # move; the flow's contract is that it *asked* to switch and landed the
    # cursor on the target buffer (DocumentFlows.activate_doc activates).
    assert shell.activated == [doc_b]
    back, _forward = session.jumps.stacks()
    assert back[-1].uid == doc_a.uid
    assert (back[-1].row, back[-1].col) == (0, 0)
    assert doc_b.buffer.cursor == (3, 1)


def test_jump_to_mark_unset_name_sets_here_d6() -> None:
    """D6: with no open buffer holding the name, the mark is set here."""
    flows, session, _panes, shell = _flows()
    session.doc.buffer.set_cursor((1, 2))

    flows.jump_to_mark("b")

    uid = session.doc.uid
    mark = session.marks.get(uid, "b")
    assert mark is not None
    assert (mark.row, mark.col) == (1, 2)
    _text, kind = _last_message(shell)
    assert kind == "info"


def test_jump_to_mark_illegal_name_warns() -> None:
    """An illegal name on the D6 path warns and never moves the cursor."""
    flows, session, _panes, shell = _flows()

    flows.jump_to_mark("A")

    _text, kind = _last_message(shell)
    assert kind == "warn"
    assert session.marks.all_marks() == []
    assert session.doc.buffer.cursor == (0, 0)


def test_jump_to_mark_closed_target_warns() -> None:
    """A panel entry whose buffer closed warns instead of jumping."""
    flows, session, _panes, shell = _flows()
    session.marks.set(999, "a", 0, 0)

    flows.jump_to_mark("a", uid=999)

    text, kind = _last_message(shell)
    assert text == "mark target buffer not open"
    assert kind == "warn"
    assert session.doc.buffer.cursor == (0, 0)


def test_jump_to_mark_panel_missing_warns() -> None:
    """A panel row whose mark was deleted meanwhile warns (AC6 wording)."""
    flows, session, _panes, shell = _flows()
    uid = session.doc.uid

    flows.jump_to_mark("z", uid=uid)

    text, kind = _last_message(shell)
    assert text == "no such mark: z"
    assert kind == "warn"


# ------------------------------------------------------------ delete


def test_delete_mark_missing_warns() -> None:
    """Deleting an unset mark returns False and warns (AC6)."""
    flows, _session, _panes, shell = _flows()

    assert flows.delete_mark("z") is False

    text, kind = _last_message(shell)
    assert text == "no such mark: z"
    assert kind == "warn"


# ------------------------------------------------------------ jump list


def test_jump_back_boundary_is_info_not_loop() -> None:
    """An empty history is an info hint; the cursor never moves (AC2)."""
    flows, session, _panes, shell = _flows()

    flows.jump_back()

    text, kind = _last_message(shell)
    assert text == "no earlier jump"
    assert kind == "info"
    assert session.doc.buffer.cursor == (0, 0)


def test_jump_back_moves_cursor_to_entry() -> None:
    """jump_back returns the cursor to the pushed origin position."""
    flows, session, panes, _shell = _flows()
    session.doc.buffer.set_cursor((1, 0))
    session.push_jump()
    session.doc.buffer.set_cursor((3, 2))

    flows.jump_back()

    assert session.doc.buffer.cursor == (1, 0)
    assert panes.view.reveals == 1


def test_show_marks_pushes_screen_with_rows() -> None:
    """show_marks builds one 1-based row per mark over the open buffers."""
    flows, session, _panes, shell = _flows()
    doc_a, doc_b = session.docs
    session.marks.set(doc_a.uid, "a", 1, 0)
    session.marks.set(doc_b.uid, "b", 2, 1)

    flows.show_marks()

    assert len(shell.pushed) == 1
    screen = shell.pushed[0]
    assert isinstance(screen, MarksScreen)
    rows = screen.rows
    assert len(rows) == 2
    first, second = rows
    assert (first.name, first.line_no) == ("a", 2)
    assert first.preview == "beta"
    assert (second.name, second.line_no) == ("b", 3)


def test_show_marks_skips_closed_buffers() -> None:
    """Marks of closed buffers do not render in the overview."""
    flows, session, _panes, shell = _flows()
    doc_a, _doc_b = session.docs
    session.marks.set(999, "a", 0, 0)
    session.marks.set(doc_a.uid, "b", 0, 0)

    flows.show_marks()

    screen = shell.pushed[0]
    assert isinstance(screen, MarksScreen)
    assert [row.name for row in screen.rows] == ["b"]


def test_show_jumps_rows_mark_current_side() -> None:
    """Back / current / forward rows annotate the stacks consistently (AC3)."""
    flows, session, _panes, shell = _flows()
    session.doc.buffer.set_cursor((1, 0))
    session.push_jump()
    session.doc.buffer.set_cursor((2, 1))
    session.push_jump()

    flows.show_jumps()

    screen = shell.pushed[0]
    assert isinstance(screen, JumpsScreen)
    rows = screen.rows
    back, _forward = session.jumps.stacks()
    assert [row.side for row in rows] == ["back", "back", "current"]
    assert rows[0].entry == back[0]
    assert rows[1].entry == back[1]
    assert rows[2].current is True

    # One step back creates a forward branch: current sits between the stacks.
    session.jump_back()
    flows.show_jumps()
    screen = shell.pushed[1]
    assert isinstance(screen, JumpsScreen)
    _back, forward = session.jumps.stacks()
    rows = screen.rows
    assert [row.side for row in rows] == ["back", "current", "forward"]
    assert rows[2].entry == forward[-1]
