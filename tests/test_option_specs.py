"""Guards for the shared option definition table in :mod:`yate.config`.

One :class:`~yate.config.OptionSpec` row drives both yaterc loading
(native values) and ``:set`` (text values).  These tests pin that the
derived views stay in sync with the table and that the historical
differences between the two input forms are preserved.
"""

from __future__ import annotations

import dataclasses

import pytest

from yate.config import (
    KNOWN_OPTIONS,
    OPTION_SPECS,
    SET_OPTION_SPECS,
    VALID_KEYMAPS,
    VALID_TRACE_LEVELS,
    YateConfig,
    set_option_names,
    set_option_value_candidates,
)
from yate.logs import LEVEL_NAMES

_CONFIG_FIELDS = frozenset(f.name for f in dataclasses.fields(YateConfig))


def test_option_specs_cover_all_known_scalar_options() -> None:
    """Every rc-visible spec is a KNOWN_OPTIONS entry, in fixed order."""
    spec_names = tuple(s.name for s in OPTION_SPECS if s.rc_visible)
    assert spec_names + ("large_file",) == KNOWN_OPTIONS
    assert len(set(KNOWN_OPTIONS)) == len(KNOWN_OPTIONS)


def test_option_specs_cover_all_settable_options() -> None:
    """The ``:set`` view and its spelling list derive from the same rows."""
    spec_settable = {s.name for s in OPTION_SPECS if s.settable}
    assert spec_settable == {spec.name for spec in SET_OPTION_SPECS}
    expected = tuple(
        spelling for spec in OPTION_SPECS if spec.settable
        for spelling in (spec.name, *spec.aliases)
    )
    assert set_option_names() == expected


def test_terminal_height_range_is_single_source() -> None:
    """The 3..40 bounds are declared once on the spec and shared both ways."""
    spec = next(s for s in OPTION_SPECS if s.name == "terminal_height")
    assert spec.domain == (3, 40)
    assert [spec.validate_native(v) for v in (2, 3, 40, 41, True)] == [
        None, 3, 40, None, None,
    ]
    assert [spec.parse_set_text(v) for v in ("2", "12", "41", "abc")] == [
        None, 12, None, None,
    ]


def test_bool_native_rejects_strings_but_set_text_accepts_spellings() -> None:
    """yaterc wants native booleans; ``:set`` keeps the on/off spellings."""
    spec = next(s for s in OPTION_SPECS if s.name == "support_mouse")
    assert spec.validate_native("on") is None
    assert spec.validate_native(True) is True
    assert spec.parse_set_text("on") is True
    assert spec.parse_set_text("yes") is True
    assert spec.parse_set_text("maybe") is None


def test_shell_keeps_its_empty_string_difference() -> None:
    """yaterc rejects an empty shell; ``:set`` still accepts empty text."""
    spec = next(s for s in OPTION_SPECS if s.name == "shell")
    assert spec.validate_native("") is None
    assert spec.validate_native("   ") is None
    assert spec.parse_set_text("") == ""
    assert spec.validate_native(" pwsh ") == "pwsh"


def test_theme_native_accepts_whitespace_but_set_text_rejects() -> None:
    """The pre-unification theme rules differ between the two surfaces."""
    spec = next(s for s in OPTION_SPECS if s.name == "theme")
    assert spec.validate_native("   ") == "   "
    assert spec.parse_set_text("   ") is None


def test_trace_level_domain_uses_logs_level_names() -> None:
    """The level domain is the logging module's list, not a copy."""
    spec = next(s for s in OPTION_SPECS if s.name == "yate_trace_level")
    assert spec.domain == VALID_TRACE_LEVELS
    assert VALID_TRACE_LEVELS == LEVEL_NAMES
    assert spec.validate_native("  info ") == "INFO"
    assert spec.native_error("  info ") == (
        f"yate_trace_level must be one of {VALID_TRACE_LEVELS}, got {'  info '!r}"
    )
    assert spec.native_error("") == (
        "yate_trace_level must be a non-empty string, got ''"
    )


def test_set_option_value_candidates_returns_static_enum_only() -> None:
    """Only settable enums yield candidates; other options yield none."""
    assert set_option_value_candidates("keymap") == VALID_KEYMAPS
    assert set_option_value_candidates("theme") == ()
    assert set_option_value_candidates("key_protocol") == ()
    assert set_option_value_candidates("yate_trace_level") == ()
    assert set_option_value_candidates("nope") == ()


def test_rc_visible_spec_names_are_yateconfig_fields() -> None:
    """setattr in the loader can never hit a non-existent config field."""
    rc_names = {s.name for s in OPTION_SPECS if s.rc_visible}
    assert rc_names <= _CONFIG_FIELDS
    assert len(rc_names) == 14
    assert "large_file" in _CONFIG_FIELDS
    assert "filetype" not in rc_names
    assert "readonly" not in rc_names


def test_all_spec_names_are_unique() -> None:
    """One canonical name per spec; aliases cannot shadow another option."""
    names = tuple(s.name for s in OPTION_SPECS)
    assert len(set(names)) == len(names)
    spellings = set_option_names()
    assert len(set(spellings)) == len(spellings)


def test_option_specs_preserve_master_usage_and_error_order() -> None:
    """The two derived subsequences keep their pre-unification row order."""
    assert tuple(s.name for s in SET_OPTION_SPECS) == (
        "keymap", "theme", "shell", "terminal_height", "filetype",
        "show_hidden", "readonly", "support_mouse", "which_key",
        "which_key_auto", "wrap",
    )
    assert tuple(s.name for s in OPTION_SPECS if s.rc_visible) == (
        "keymap", "key_protocol", "theme", "tab_width", "use_spaces",
        "shell", "terminal_height", "show_hidden", "support_mouse",
        "which_key", "which_key_auto", "wrap", "yate_trace",
        "yate_trace_level",
    )


def test_keymap_and_protocol_messages_derive_from_domains() -> None:
    """Enum error templates spell out the same values as their domains."""
    keymap = next(s for s in OPTION_SPECS if s.name == "keymap")
    assert keymap.invalid_message_fmt.format(value="emacs") == (
        f"keymap must be one of {VALID_KEYMAPS}, got 'emacs'"
    )
    protocol = next(s for s in OPTION_SPECS if s.name == "key_protocol")
    assert protocol.invalid_message_fmt.format(value="x") == (
        "key_protocol must be one of ('auto', 'legacy'), got 'x'"
    )


def test_config_stays_within_size_threshold() -> None:
    """config.py stays below the 800-line architecture threshold."""
    from pathlib import Path

    source = (Path(__file__).parents[1] / "yate" / "config.py").read_text(
        encoding="utf-8"
    )
    assert len(source.splitlines()) <= 800


@pytest.mark.parametrize("value", ["ON", "Off", "1", "0", "yes", "no"])
def test_bool_set_text_is_case_insensitive(value: str) -> None:
    """The shared parse_bool spellings keep their case-insensitive rule."""
    spec = next(s for s in OPTION_SPECS if s.name == "which_key")
    assert spec.parse_set_text(value) is not None


def test_filetype_set_text_accepts_any_string_including_empty() -> None:
    """``:set filetype=`` resets to auto-detection, so any text is accepted."""
    spec = next(s for s in OPTION_SPECS if s.name == "filetype")
    assert spec.kind == "any_text"
    assert spec.parse_set_text("") == ""
    assert spec.parse_set_text("   ") == "   "
    assert spec.parse_set_text("py") == "py"


def test_option_kinds_are_a_frozen_literal_set() -> None:
    """A misspelled kind can no longer silently fall through to text."""
    assert {s.kind for s in OPTION_SPECS} == {
        "enum", "int", "bool", "text", "any_text",
    }


def test_bool_value_candidates_stay_within_the_shared_spellings() -> None:
    """The completer's bool candidates all parse through the shared bool rule."""
    from yate.config import parse_bool

    candidates = {
        "readonly": ("true", "false"),
        "show_hidden": ("on", "off"),
    }
    for values in candidates.values():
        assert all(parse_bool(value) is not None for value in values)
