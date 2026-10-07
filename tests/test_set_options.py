"""Guards for the single ``:set`` option table (audit A8).

The table in :mod:`yate.config` is the one source of option knowledge:
``commands._set`` dispatches through it and
:mod:`yate.flows.prompt_completion` derives its candidates from it.
These tests pin the table <-> dispatch and table <-> completion
contracts so a new option cannot drift apart between the three sides.
"""

from __future__ import annotations

from collections.abc import Callable

from yate.commands import SET_APPLY, SET_OPTION_INDEX
from yate.config import SET_OPTION_SPECS, set_option_names
from yate.flows.prompt_completion import SET_OPTIONS


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
    parse: Callable[[str], object | None] = spec.parse
    assert parse("41") is None
    assert parse("2") is None
    assert parse("abc") is None
    assert parse("12") == 12


def test_set_option_names_feed_prompt_completion() -> None:
    """The completion candidates are exactly the table's spellings."""
    assert SET_OPTIONS == set_option_names()
