"""Guards for the single ``:set`` option table (audit A8).

The table in :mod:`yate.config` is the one source of option knowledge:
``commands._set`` dispatches through it and
:mod:`yate.flows.prompt_completion` derives its candidates from it.
These tests pin the table <-> dispatch and table <-> completion
contracts so a new option cannot drift apart between the three sides.
"""

from __future__ import annotations

from typing import Any, cast

from yate.commands import SET_APPLY, SET_OPTION_INDEX, register_commands
from yate.config import SET_OPTION_SPECS, OptionParser, YateConfig, set_option_names
from yate.flows.prompt_completion import SET_OPTIONS
from yate.registries import CommandRegistry


def test_set_option_specs_cover_all_dispatched_options() -> None:
    """Every spec's canonical name has an apply entry, and vice versa."""
    spec_names = {spec.name for spec in SET_OPTION_SPECS}
    apply_names = set(SET_APPLY)
    assert spec_names == apply_names, (sorted(spec_names), sorted(apply_names))


def test_set_option_aliases_are_unique_across_specs() -> None:
    """A spelling (name or alias) must belong to exactly one option."""
    spellings = [
        spelling for spec in SET_OPTION_SPECS for spelling in (spec.name, *spec.aliases)
    ]
    assert len(spellings) == len(set(spellings)), sorted(spellings)
    assert set(SET_OPTION_INDEX) == set(spellings)


def test_terminal_height_parser_rejects_out_of_range() -> None:
    """``terminal_height`` shares the config loader's 3..40 range."""
    spec = next(spec for spec in SET_OPTION_SPECS if spec.name == "terminal_height")
    parse: OptionParser = spec.parse
    assert parse("41") is None
    assert parse("2") is None
    assert parse("abc") is None
    assert parse("12") == 12


def test_set_option_names_feed_prompt_completion() -> None:
    """The completion candidates are exactly the table's spellings."""
    assert SET_OPTIONS == set_option_names()


def test_set_dispatch_survives_a_missing_apply(
    monkeypatch: Any,
) -> None:
    """A forgotten apply entry degrades to a warning, not a KeyError (PR !61).

    Deletes one handler through the public dispatch surface: the command
    must report the internal error on the message line instead of crashing.
    """
    notes: list[tuple[str, str]] = []

    class _RecordingEditor:
        """Editor stand-in recording every message call."""

        def message(self, text: str, kind: str = "") -> None:
            """Record one message-line output."""
            notes.append((text, kind))

    registry = CommandRegistry()
    register_commands(registry, cast(Any, _RecordingEditor()))
    entry = registry.get("set")
    assert entry is not None

    monkeypatch.delitem(SET_APPLY, "keymap")
    entry[0]("keymap=vsc")

    assert ("internal error: no handler for keymap", "warn") in notes


# --- support_mouse dispatch -------------------------------------------------


class _ConfigEditor:
    """Editor stand-in with a real config plus message recording."""

    def __init__(self) -> None:
        self.config = YateConfig()
        self.notes: list[tuple[str, str]] = []
        self.mouse_state_canceled = 0

    def message(self, text: str, kind: str = "") -> None:
        """Record one message-line output."""
        self.notes.append((text, kind))

    def cancel_mouse_state(self) -> None:
        """Record a mid-drag state sweep (fired on support_mouse off)."""
        self.mouse_state_canceled += 1


def _set_driver() -> tuple[CommandRegistry, _ConfigEditor]:
    """Register the built-in commands against a :class:`_ConfigEditor`."""
    editor = _ConfigEditor()
    registry = CommandRegistry()
    register_commands(registry, cast(Any, editor))
    return registry, editor


def test_set_support_mouse_on_off_roundtrip() -> None:
    """``:set support_mouse=off/on`` flips the config master switch."""
    registry, editor = _set_driver()
    entry = registry.get("set")
    assert entry is not None

    entry[0]("support_mouse=off")
    assert editor.config.support_mouse is False
    assert editor.mouse_state_canceled == 1
    entry[0]("support_mouse=on")
    assert editor.config.support_mouse is True
    # the sweep only fires on disable: enabling drops no in-flight state
    assert editor.mouse_state_canceled == 1


def test_set_support_mouse_invalid_value_reports() -> None:
    """An unrecognised value warns on the message line, value unchanged."""
    registry, editor = _set_driver()
    entry = registry.get("set")
    assert entry is not None

    entry[0]("support_mouse=maybe")
    assert any(
        "support_mouse must be on|off" in text for text, _ in editor.notes
    )
    assert editor.config.support_mouse is True
