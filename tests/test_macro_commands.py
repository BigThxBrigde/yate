"""Command-level tests for ``:macro-record`` / ``:macro-play`` / ``:macro-repeat``.

Drives the registrations in :mod:`yate.commands` against a headless editor
stub (a real :class:`~yate.registries.CommandRegistry` wired with a real
:class:`~yate.flows.macro_flows.MacroFlows` over a bare session; no Textual
app is started), mirroring the headless pattern of ``tests/test_cmd_enew.py``.
Replay is observed through a recording ``handle_raw_key`` sink, so the tests
pin exactly which raw keys the command layer replays and how many times.
"""

# tests legitimately poke at command-table privates:
# pyright: reportPrivateUsage=false

from __future__ import annotations

from typing import Any, cast

from yate.commands import register_commands
from yate.config import YateConfig
from yate.flows.macro_flows import MacroFlows
from yate.registries import CommandRegistry
from yate.session import EditorSession

_USAGE_RECORD = "macro: usage :macro-record {a-z0-9}"
_USAGE_PLAY = "macro: usage :macro-play {a-z0-9} [count]"
_BAD_COUNT = "macro: count must be a positive integer"
_NO_LAST = "macro: no previous macro to repeat"


class _MacroEditor:
    """Editor stand-in: a real MacroFlows over a bare UI-free session.

    ``handle_raw_key`` collects every replayed raw key instead of editing a
    buffer; ``message`` records ``(kind, text)`` pairs exactly as the command
    layer and the flow emit them.
    """

    def __init__(self) -> None:
        self.session = EditorSession(YateConfig())
        self.notes: list[tuple[str, str]] = []
        self.replayed: list[str] = []
        #: What the keymap's ``take_pending_count`` would hand back.
        self.pending_count = 1
        self.macro = MacroFlows(
            session=self.session,
            handle_raw_key=self._handle_raw_key,
            message=self.message,
            count_source=lambda: self.pending_count,
        )

    def _handle_raw_key(self, raw: str) -> bool:
        self.replayed.append(raw)
        return True

    def message(self, text: str, kind: str = "info") -> None:
        self.notes.append((kind, text))


class _MacroFixture:
    """One registry entry plus every recorder a test inspects."""

    def __init__(self, command: str) -> None:
        self.editor = _MacroEditor()
        registry = CommandRegistry()
        register_commands(registry, cast(Any, self.editor))
        entry = registry.get(command)
        assert entry is not None
        self.entry = entry

    def run(self, args: str) -> None:
        """Execute the command with *args* (the ex-line's argument string)."""
        self.entry.func(args)


def test_macro_record_command_without_args_while_recording_stops() -> None:
    """Blank ``:macro-record`` stops the running recording; bare re-run warns."""
    fx = _MacroFixture("macro-record")
    flow = fx.editor.macro
    flow.toggle_record("a")
    # one key arrives while recording: it must land in the stopped sequence
    flow.pre_dispatch("x")

    fx.run("")  # stop the recording

    s = fx.editor.session
    assert s.macro_recording is None
    assert s.macro_registers == {"a": ["x"]}
    assert s.macro_last_register == "a"
    assert fx.editor.replayed == []
    assert fx.editor.notes == []

    # without a running recording the blank command is a usage notice and
    # leaves every piece of macro state untouched
    fx.run("")

    assert fx.editor.notes == [("info", _USAGE_RECORD)]
    assert s.macro_recording is None
    assert s.macro_registers == {"a": ["x"]}
    assert s.macro_last_register == "a"
    assert fx.editor.replayed == []


def test_macro_record_command_with_invalid_register_errors() -> None:
    """A non-register argument surfaces the usage notice and changes nothing."""
    fx = _MacroFixture("macro-record")

    fx.run("!")

    assert fx.editor.notes == [("info", _USAGE_RECORD)]
    assert fx.editor.session.macro_recording is None
    assert fx.editor.session.macro_registers == {}
    assert fx.editor.session.macro_last_register is None


def test_macro_play_command_parses_register_and_count() -> None:
    """``:macro-play a 3`` replays register a's sequence exactly three times."""
    fx = _MacroFixture("macro-play")
    fx.editor.session.macro_registers["a"] = ["1", "2"]

    fx.run("a 3")

    assert fx.editor.replayed == ["1", "2"] * 3
    assert fx.editor.session.macro_last_register == "a"
    assert fx.editor.notes == []


def test_macro_play_command_rejects_bad_count() -> None:
    """A zero or non-numeric count errors out and replays nothing."""
    fx = _MacroFixture("macro-play")
    fx.editor.session.macro_registers["a"] = ["1"]

    fx.run("a 0")

    assert fx.editor.notes[-1] == ("error", _BAD_COUNT)
    assert fx.editor.replayed == []

    fx.run("a x")

    assert fx.editor.notes[-1] == ("error", _BAD_COUNT)
    assert fx.editor.replayed == []
    assert fx.editor.session.macro_last_register is None


def test_macro_repeat_command_replays_last_register() -> None:
    """``:macro-repeat`` replays the last register, with an optional count."""
    fx = _MacroFixture("macro-repeat")
    s = fx.editor.session
    s.macro_registers["a"] = ["1"]
    s.macro_last_register = "a"

    fx.run("")  # default: one replay

    assert fx.editor.replayed == ["1"]

    fx.run("2")  # explicit count: two more replays

    assert fx.editor.replayed == ["1", "1", "1"]

    # without a last register the command reports and replays nothing
    fx2 = _MacroFixture("macro-repeat")

    fx2.run("")

    assert fx2.editor.notes[-1] == ("info", _NO_LAST)
    assert fx2.editor.replayed == []


def test_macro_play_command_requires_register_argument() -> None:
    """Bare ``:macro-play`` with no last register is a usage notice."""
    fx = _MacroFixture("macro-play")

    fx.run("")

    assert fx.editor.notes[-1] == ("info", _USAGE_PLAY)
    assert fx.editor.replayed == []
    assert fx.editor.session.macro_last_register is None
