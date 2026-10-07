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
from yate.config import SET_OPTION_SPECS, OptionParser, set_option_names
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
