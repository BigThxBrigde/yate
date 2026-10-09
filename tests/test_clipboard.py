"""Tests for the degrade-safe system clipboard service and vsc actions.

Group A (wave-1) covers :mod:`yate.services.clipboard` itself: success
forwarding and the PyperclipException degrade path.  Group C (wave-3)
covers the vsc action-table sync in :mod:`yate.actions`.  Every test
monkeypatches the pyperclip entry points or the service functions -- the
real system clipboard is never touched.
"""

from __future__ import annotations

from typing import Any, Callable, cast

import pyperclip
import pytest

from yate.actions import populate
from yate.editor_core import BufferReadOnlyError
from yate.registries import ActionRegistry
from yate.services import clipboard as clipboard_service

from conftest import make_action_context


# ------------------------------------------------------------- group A

def test_copy_text_returns_true_and_forwards_on_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """copy_text forwards the text to pyperclip.copy and reports True."""
    copies: list[str] = []

    def fake_copy(text: str) -> None:
        copies.append(text)

    monkeypatch.setattr(pyperclip, "copy", fake_copy)

    assert clipboard_service.copy_text("abc") is True
    assert copies == ["abc"]


def test_copy_text_returns_false_when_backend_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """copy_text swallows PyperclipException and returns False (no raise)."""
    copies: list[str] = []

    def failing_copy(text: str) -> None:
        copies.append(text)
        raise pyperclip.PyperclipException("no backend")

    monkeypatch.setattr(pyperclip, "copy", failing_copy)

    assert clipboard_service.copy_text("abc") is False
    assert copies == ["abc"]


def test_paste_text_returns_clipboard_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """paste_text returns whatever pyperclip.paste yields."""
    monkeypatch.setattr(pyperclip, "paste", lambda: "xyz")

    assert clipboard_service.paste_text() == "xyz"


def test_paste_text_returns_none_when_backend_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """paste_text swallows PyperclipException and returns None (no raise)."""
    def failing_paste() -> str:
        raise pyperclip.PyperclipException("no backend")

    monkeypatch.setattr(pyperclip, "paste", failing_paste)

    assert clipboard_service.paste_text() is None


def test_paste_text_keeps_empty_string_distinct_from_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An empty clipboard yields "" -- not None (both degrade at callers)."""
    monkeypatch.setattr(pyperclip, "paste", lambda: "")

    assert clipboard_service.paste_text() == ""


# ------------------------------------------------------------- group C


class _RecordingClip:
    """Recording stand-in replacing the clipboard service entry points."""

    def __init__(self) -> None:
        self.copies: list[str] = []
        self.pastes: list[int] = []
        self.paste_result: str | None = None

    def copy_text(self, text: str) -> bool:
        self.copies.append(text)
        return True

    def paste_text(self) -> str | None:
        self.pastes.append(1)
        return self.paste_result


@pytest.fixture()
def recording_clip(monkeypatch: pytest.MonkeyPatch) -> _RecordingClip:
    """Patch the clipboard service module the action table calls into."""
    fake = _RecordingClip()
    monkeypatch.setattr(clipboard_service, "copy_text", fake.copy_text)
    monkeypatch.setattr(clipboard_service, "paste_text", fake.paste_text)
    return fake


def _recording_editor() -> Any:
    """A recording stand-in for the editor hooks editing actions never reach."""
    class _RecordingEditor:
        def __getattr__(self, name: str) -> Callable[..., None]:
            if name.startswith("_"):
                raise AttributeError(
                    f"{type(self).__name__!r} object has no attribute {name!r}"
                )
            return lambda *args: None

    return cast(Any, _RecordingEditor())


def _action_table() -> ActionRegistry:
    """A populated built-in action table."""
    registry = ActionRegistry()
    populate(registry, _recording_editor())
    return registry


def test_copy_action_mirrors_register_to_clipboard(
    recording_clip: _RecordingClip,
) -> None:
    """copy with a selection fills the register and the system clipboard."""
    registry = _action_table()
    ctx = make_action_context("hello world")
    ctx.buffer.set_cursor((0, 5), select=True)

    assert registry.execute("copy", ctx) is True
    assert ctx.buffer.register == "hello"
    assert recording_clip.copies == ["hello"]


def test_copy_action_without_selection_yanks_line_and_mirrors(
    recording_clip: _RecordingClip,
) -> None:
    """copy without a selection yanks the line (linewise) and mirrors it."""
    registry = _action_table()
    ctx = make_action_context("line1")

    assert registry.execute("copy", ctx) is True
    assert ctx.buffer.register == "line1\n"
    assert recording_clip.copies == ["line1\n"]


def test_cut_action_mirrors_deleted_text_to_clipboard(
    recording_clip: _RecordingClip,
) -> None:
    """cut with a selection deletes the text and mirrors it."""
    registry = _action_table()
    ctx = make_action_context("hello world")
    ctx.buffer.set_cursor((0, 5), select=True)

    assert registry.execute("cut", ctx) is True
    assert ctx.buffer.get_text() == " world"
    assert recording_clip.copies == ["hello"]


def test_cut_action_without_selection_cuts_line_and_mirrors(
    recording_clip: _RecordingClip,
) -> None:
    """cut without a selection cuts the whole line and mirrors it."""
    registry = _action_table()
    ctx = make_action_context("one\ntwo\nthree")
    ctx.buffer.set_cursor((1, 1))

    assert registry.execute("cut", ctx) is True
    assert ctx.buffer.get_text() == "one\nthree"
    assert recording_clip.copies == ["two\n"]


def test_paste_action_prefers_system_clipboard(
    recording_clip: _RecordingClip,
) -> None:
    """paste takes the system clipboard text over the unnamed register."""
    registry = _action_table()
    ctx = make_action_context("")
    ctx.buffer.register = "OLD"
    recording_clip.paste_result = "SYS"

    assert registry.execute("paste", ctx) is True
    assert ctx.buffer.get_text() == "SYS"


def test_paste_action_falls_back_to_register_on_failure(
    recording_clip: _RecordingClip,
) -> None:
    """A failed clipboard read (None) pastes the unnamed register."""
    registry = _action_table()
    ctx = make_action_context("")
    ctx.buffer.register = "OLD"
    recording_clip.paste_result = None

    assert registry.execute("paste", ctx) is True
    assert ctx.buffer.get_text() == "OLD"


def test_paste_action_falls_back_when_clipboard_empty(
    recording_clip: _RecordingClip,
) -> None:
    """An empty clipboard ("") pastes the unnamed register."""
    registry = _action_table()
    ctx = make_action_context("")
    ctx.buffer.register = "OLD"
    recording_clip.paste_result = ""

    assert registry.execute("paste", ctx) is True
    assert ctx.buffer.get_text() == "OLD"


def test_paste_action_on_read_only_buffer_does_not_prime_register(
    recording_clip: _RecordingClip,
) -> None:
    """A read-only buffer fails the paste with the register left intact."""
    registry = _action_table()
    ctx = make_action_context("KEEP")
    ctx.buffer.read_only = True
    ctx.buffer.register = "OLD"
    recording_clip.paste_result = "SYS"

    with pytest.raises(BufferReadOnlyError):
        registry.execute("paste", ctx)
    assert ctx.buffer.register == "OLD"
    assert recording_clip.pastes == []


def test_cut_action_on_read_only_buffer_does_not_prime_register(
    recording_clip: _RecordingClip,
) -> None:
    """A read-only buffer fails the cut with the register left intact.

    The write order matters (review 2026-10-02 #45 round 3): the register
    is only primed after the deletion succeeded, so a failed cut cannot
    leave text in the register that was never removed from the buffer.
    """
    registry = _action_table()
    ctx = make_action_context("KEEP")
    ctx.buffer.select_all()
    ctx.buffer.read_only = True
    ctx.buffer.register = "OLD"

    with pytest.raises(BufferReadOnlyError):
        registry.execute("cut", ctx)
    assert ctx.buffer.register == "OLD"
    assert recording_clip.copies == []
