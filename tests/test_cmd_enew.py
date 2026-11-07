# pyright: reportPrivateUsage=false
"""Command-level tests for the ``:enew`` zero-argument guard.

Drives the ``:enew`` registration in :mod:`yate.commands` against a
headless editor stub (a real :class:`~yate.registries.CommandRegistry`
wired with recording stand-ins, no Textual app is started), mirroring
the headless pattern of ``tests/test_cmd_cd.py``.  Covered: bare
``:enew`` and whitespace-only arguments still create exactly one
unnamed buffer; a plain or quoted filename argument warns with the
exact usage message and creates no buffer; the registration
description states the no-arguments contract.
"""

from __future__ import annotations

from typing import Any, cast

from yate.commands import register_commands
from yate.registries import CommandRegistry

_USAGE_MESSAGE = (
    "usage: :enew takes no arguments; use :e FILE to open/create a "
    "named buffer or :saveas FILE to name this buffer"
)


class _RecordingFlows:
    """Document-flows stand-in: counts new-buffer creations."""

    def __init__(self) -> None:
        self.new_buffer_calls: list[int] = []

    def new_buffer(self) -> None:
        """Record one new-buffer creation (the guarded contract)."""
        self.new_buffer_calls.append(1)


class _EnewEditor:
    """Editor stand-in exposing the flows and the message line."""

    def __init__(self, flows: _RecordingFlows) -> None:
        self.document_flows = flows
        self.notes: list[tuple[str, str]] = []

    def message(self, text: str, kind: str = "info") -> None:
        """Record one message-line output with its kind."""
        self.notes.append((text, kind))


class _EnewFixture:
    """Bundle of the registry entry plus every recorder a test inspects."""

    def __init__(self) -> None:
        self.flows = _RecordingFlows()
        self.editor = _EnewEditor(self.flows)
        registry = CommandRegistry()
        register_commands(registry, cast(Any, self.editor))
        entry = registry.get("enew")
        assert entry is not None
        self.entry = entry


def test_enew_without_arguments_creates_one_unnamed_buffer() -> None:
    """Bare ``:enew`` creates exactly one unnamed buffer and stays silent."""
    fx = _EnewFixture()

    fx.entry.func("")

    assert fx.flows.new_buffer_calls == [1]
    assert fx.editor.notes == []


def test_enew_with_whitespace_only_arguments_creates_one_unnamed_buffer() -> None:
    """Whitespace-only arguments count as no arguments: one buffer, silent."""
    fx = _EnewFixture()

    fx.entry.func("   \t ")

    assert fx.flows.new_buffer_calls == [1]
    assert fx.editor.notes == []


def test_enew_with_filename_warns_and_creates_no_buffer() -> None:
    """A filename argument warns with the exact usage message, no buffer."""
    fx = _EnewFixture()

    fx.entry.func("test.py")

    assert fx.flows.new_buffer_calls == []
    assert fx.editor.notes == [(_USAGE_MESSAGE, "warn")]


def test_enew_with_quoted_filename_warns_and_creates_no_buffer() -> None:
    """A quoted filename is still an argument: warns, no buffer, no strip."""
    fx = _EnewFixture()

    fx.entry.func('"test.py"')

    assert fx.flows.new_buffer_calls == []
    assert fx.editor.notes == [(_USAGE_MESSAGE, "warn")]


def test_enew_with_multiple_arguments_warns_and_creates_no_buffer() -> None:
    """Multiple arguments still count as arguments: warns, no buffer."""
    fx = _EnewFixture()

    fx.entry.func("a.py b.py")

    assert fx.flows.new_buffer_calls == []
    assert fx.editor.notes == [(_USAGE_MESSAGE, "warn")]


def test_enew_registration_description_states_no_arguments() -> None:
    """The registration description pins the no-arguments contract."""
    fx = _EnewFixture()

    description = fx.entry.description

    assert "no arguments" in description
    assert "open a new empty buffer" in description
