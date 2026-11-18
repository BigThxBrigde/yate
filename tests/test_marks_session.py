"""Session-level marks and the jump list: pure L1 model semantics.

``MarkBook`` / ``JumpList`` live on ``EditorSession`` next to ``MacroState``;
these cases exercise them headlessly with no UI or Textual wiring involved.
Navigation repositioning (writing the buffer cursor after a jump) is the L3
wiring's job (a later wave); here the tests move ``buffer.set_cursor`` by
hand and only the model contract is asserted (issue IKUOCI).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from yate.config import YateConfig
from yate.editor_core import Document
from yate.editor_core.buffer import TextBuffer
from yate.session import (
    JUMP_LIST_LIMIT,
    EditorSession,
    JumpEntry,
    Mark,
    MarkBook,
)


def _session() -> EditorSession:
    """A headless session with two manual multi-line documents (no disk)."""
    session = EditorSession(YateConfig())
    for text in ("alpha\nbeta\ngamma\ndelta\n", "one\ntwo\nthree\nfour\n"):
        session.docs.append(Document(None, TextBuffer(text)))
    session.index = 0
    return session


# ------------------------------------------------------------------ MarkBook


def test_markbook_set_get_overwrite() -> None:
    """Setting the same mark name twice overwrites with the latest position."""
    book = MarkBook()

    book.set(1, "a", 1, 1)
    book.set(1, "a", 5, 2)

    assert book.get(1, "a") == Mark(5, 2)


def test_markbook_rejects_illegal_name() -> None:
    """Only single lowercase letters are legal mark names."""
    book = MarkBook()

    with pytest.raises(ValueError):
        book.set(1, "A", 0, 0)
    with pytest.raises(ValueError):
        book.set(1, "ab", 0, 0)

    assert book.get(1, "A") is None


def test_markbook_delete_returns_false_for_missing() -> None:
    """Deleting a missing mark reports False; a set mark deletes once."""
    book = MarkBook()

    assert book.delete(1, "a") is False

    book.set(1, "a", 2, 0)
    assert book.delete(1, "a") is True
    assert book.get(1, "a") is None
    assert book.delete(1, "a") is False


def test_markbook_drop_doc_removes_all_marks() -> None:
    """drop_doc removes every mark of one document and keeps the others."""
    book = MarkBook()

    book.set(1, "b", 0, 0)
    book.set(1, "a", 1, 0)
    book.set(2, "a", 2, 0)

    assert [(uid, name) for uid, name, _ in book.all_marks()] == [
        (1, "a"),
        (1, "b"),
        (2, "a"),
    ]

    book.drop_doc(1)

    assert book.all_marks() == [(2, "a", Mark(2, 0))]


# ------------------------------------------------------------------- push


def test_push_jump_records_active_cursor() -> None:
    """push_jump with no arguments records the active document's cursor."""
    session = _session()
    doc = session.doc

    session.push_jump()

    back, _forward = session.jumps.stacks()
    assert back[-1] == JumpEntry(doc.uid, doc.display_path, 0, 0)


def test_push_jump_dedups_consecutive_same_position() -> None:
    """Pushing the same position twice in a row keeps one back entry."""
    session = _session()

    session.push_jump()
    session.push_jump()

    back, _forward = session.jumps.stacks()
    assert len(back) == 1


def test_push_jump_clears_forward_branch() -> None:
    """A fresh push discards the forward branch left by a backward jump.

    Note: the plan sketch's endpoint (``back=[X, Z]``) is unreachable under
    the plan's own verbatim ``JumpList`` code -- ``take_back`` pops the back
    entry and pushes the *current* position onto the forward stack, so after
    one ``jump_back`` the back stack is empty and the forward stack holds the
    current position.  This case asserts the implemented semantics.
    """
    session = _session()
    doc_a, doc_b = session.docs

    # X: the active cursor position on doc A is the jump origin.
    session.push_jump()

    # The cursor moves to Y on doc B (the jump lands: the caller activates
    # the target document and repositions its buffer), then one step back:
    # Y (the current position) lands on the forward stack and X is handed back.
    doc_b.buffer.set_cursor((2, 1))
    session.activate(doc_b)
    back_target = session.jump_back()
    assert back_target is not None
    assert back_target.uid == doc_a.uid
    _, forward = session.jumps.stacks()
    assert len(forward) == 1

    # Z: a fresh push clears the forward branch entirely.
    session.push_jump()
    back, forward = session.jumps.stacks()
    assert forward == []
    assert len(back) == 1
    assert back[-1].uid == doc_b.uid


def test_jump_back_roundtrip_then_boundary() -> None:
    """Back/forward round-trips and stops at empty stacks (no looping)."""
    session = _session()
    doc_a, doc_b = session.docs

    # Cursor at A: push (simulating the jump about to leave A).
    session.push_jump()

    # The cursor moves to B (the jump landed: activate + reposition);
    # one step back returns A.
    doc_b.buffer.set_cursor((1, 0))
    session.activate(doc_b)
    back_target = session.jump_back()
    assert back_target == JumpEntry(doc_a.uid, doc_a.display_path, 0, 0)

    # The back stack is exhausted: the boundary returns None.
    assert session.jump_back() is None

    # Stepping forward returns B (the position the back step left behind).
    assert session.jump_forward() == JumpEntry(
        doc_b.uid, doc_b.display_path, 1, 0
    )
    assert session.jump_forward() is None


def test_jump_list_trims_to_limit() -> None:
    """The back stack keeps at most JUMP_LIST_LIMIT entries, oldest dropped."""
    session = _session()

    for row in range(120):
        session.push_jump(row=row)

    back, _forward = session.jumps.stacks()
    assert len(back) == JUMP_LIST_LIMIT
    assert back[0].row == 20


# ------------------------------------------------------------- close cleanup


def test_close_active_drops_marks_and_jumps() -> None:
    """Closing the active tab drops its marks and prunes its jump entries."""
    session = _session()
    closed = session.doc

    session.marks.set(closed.uid, "a", 3, 0)
    session.push_jump()

    session.close_active()

    assert session.doc_by_uid(closed.uid) is None
    assert session.marks.all_marks() == []
    back, forward = session.jumps.stacks()
    assert all(entry.uid != closed.uid for entry in back + forward)


def test_close_under_drops_marks_and_jumps(tmp_path: Path) -> None:
    """Closing every tab under a directory drops their marks and jumps."""
    session = EditorSession(YateConfig())
    first_path = tmp_path / "first.txt"
    second_path = tmp_path / "second.txt"
    first_path.write_text("one\n", encoding="utf-8")
    second_path.write_text("two\n", encoding="utf-8")
    first = session.open(first_path)
    second = session.open(second_path)
    assert first is not None
    assert second is not None

    session.marks.set(first.uid, "a", 1, 0)
    session.push_jump()

    closed = session.close_under(tmp_path)

    assert [doc.uid for doc in closed] == [first.uid, second.uid]
    assert session.doc_by_uid(first.uid) is None
    assert session.marks.all_marks() == []
    back, forward = session.jumps.stacks()
    assert back == []
    assert forward == []


# -------------------------------------------------------------- uid lookup


def test_doc_by_uid_roundtrip() -> None:
    """doc_by_uid finds an open document by uid and None for a closed one."""
    session = _session()
    doc = session.doc

    assert session.doc_by_uid(doc.uid) is doc
    assert session.doc_by_uid(999) is None
