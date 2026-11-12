"""Session-level macro state: defaults, sharing, isolation and the count.

``MacroState`` is pure L1 data owned by ``EditorSession``; these cases exercise
it headlessly with no UI or Textual wiring involved.
"""

from __future__ import annotations

from pathlib import Path

from yate.config import YateConfig
from yate.session import EditorSession, MacroState


def test_macro_state_defaults_empty_and_not_recording() -> None:
    """A fresh MacroState starts empty with pending_count at the N default 1."""
    state = MacroState()

    assert state.registers == {}
    assert state.buffer == []
    assert state.recording is None
    assert state.awaiting is None
    assert state.last_played is None
    assert state.playing is False
    assert state.play_depth == 0
    assert state.pending_count == 1
    assert state.recording_label() is None
    assert state.get("a") == ()


def test_macro_state_recording_label_formats_register() -> None:
    """The recording label formats the register and disappears when idle."""
    state = MacroState()

    state.recording = "a"
    assert state.recording_label() == "rec @a"

    state.recording = "9"
    assert state.recording_label() == "rec @9"

    state.recording = None
    assert state.recording_label() is None


def test_macro_state_get_returns_immutable_tuple() -> None:
    """get() returns the stored tuple and () for unrecorded registers."""
    state = MacroState()
    state.registers["a"] = ("x", "y")

    recorded = state.get("a")
    assert recorded == ("x", "y")
    assert isinstance(recorded, tuple)
    assert state.get("z") == ()
    assert state.registers == {"a": ("x", "y")}


def test_macro_state_is_shared_across_documents_of_one_session(tmp_path: Path) -> None:
    """Switching the active document keeps the same session macro object."""
    session = EditorSession(YateConfig())
    first_path = tmp_path / "first.txt"
    second_path = tmp_path / "second.txt"
    first_path.write_text("one\n", encoding="utf-8")
    second_path.write_text("two\n", encoding="utf-8")
    first = session.open(first_path)
    second = session.open(second_path)
    assert first is not None
    assert second is not None

    macro = session.macro
    macro_id = id(macro)
    session.macro.registers["a"] = ("x",)

    for doc in (first, second):
        session.activate(doc)
        assert session.macro is session.macro
        assert session.macro is macro
        assert id(session.macro) == macro_id
        assert session.macro.registers["a"] == ("x",)


def test_macro_state_is_not_shared_between_sessions() -> None:
    """Each session owns its own in-memory macro state (no persistence)."""
    first = EditorSession(YateConfig())
    second = EditorSession(YateConfig())

    first.macro.registers["a"] = ("x",)

    assert first.macro is not second.macro
    assert second.macro.registers == {}
    assert second.macro.get("a") == ()


def test_macro_state_fields_reject_no_default_mutation_leak() -> None:
    """Mutable fields use default_factory, so instances never share containers."""
    first = MacroState()
    second = MacroState()

    first.buffer.append("x")
    first.registers["a"] = ("y",)

    assert second.buffer == []
    assert second.registers == {}


def test_macro_state_literal_awaiting_values_are_constrained() -> None:
    """awaiting is a Literal of record / play (or None); pyright enforces it."""
    state = MacroState()
    assert state.awaiting is None

    state.awaiting = "record"
    assert state.awaiting == "record"

    state.awaiting = "play"
    assert state.awaiting == "play"


def test_macro_state_pending_count_defaults_to_one_and_is_resettable() -> None:
    """pending_count defaults to 1, carries a captured N, and resets to 1."""
    state = MacroState()
    assert state.pending_count == 1

    state.pending_count = 3
    assert state.pending_count == 3

    state.pending_count = 1
    assert state.pending_count == 1
    assert state.last_played is None
    assert state.playing is False
    assert state.play_depth == 0
