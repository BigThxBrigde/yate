"""Unit tests for yate.yaterc_options: yaterc option extraction/validation.

The ``_extract_*`` helpers pull recognized option variables out of an
exec'd yaterc namespace (a plain dict here stands in for the exec'd rc
globals) and fold them into a :class:`YateConfig`; malformed values are
appended to ``config.errors`` and that option keeps its default while the
rest still apply.  ``rc_dir`` is ``tmp_path`` and the autouse
``isolated_home`` fixture keeps ``~`` expansion away from the real user
home.
"""

# _-prefixed names are the module's __all__ surface (wave-a private-registry
# precedent, same as tests/test_diagnostics.py).
# pyright: reportPrivateUsage=false

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from yate.config import LanguageServerSpec, YateConfig
from yate.yaterc_options import (
    _extract_disabled_extensions,
    _extract_file_preview,
    _extract_language_servers,
    _extract_options,
    _extract_path_list,
    _extract_screen_saver,
    _parse_journey_fraction,
)


@pytest.fixture()
def config() -> YateConfig:
    """A fresh default config per test (errors accumulate on it)."""
    return YateConfig()


# --- path-list options (extensions / theme_dirs) -----------------------------


def test_extract_path_list_resolves_relative_entries_against_rc_dir(
    config: YateConfig, tmp_path: Path,
) -> None:
    """Relative entries resolve against *rc_dir*, not the process cwd."""
    script = tmp_path / "ext" / "a.py"
    script.parent.mkdir()
    script.write_text("# extension stub\n", encoding="utf-8")

    _extract_path_list(
        {"extensions": ["ext/a.py"]},
        config, tmp_path, "extensions", config.extension_paths,
    )

    assert config.extension_paths == [(tmp_path / "ext" / "a.py").resolve()]
    assert config.errors == []


def test_extract_path_list_expands_user_home_entry(
    config: YateConfig, tmp_path: Path,
) -> None:
    """A ``~`` entry expands to the (isolated) user home directory."""
    exts = Path.home() / "exts"
    exts.mkdir()

    _extract_path_list(
        {"theme_dirs": ["~/exts"]},
        config, tmp_path, "theme_dirs", config.theme_dirs,
    )

    assert config.theme_dirs == [exts.resolve()]


def test_extract_path_list_missing_entry_appends_error_and_keeps_default(
    config: YateConfig, tmp_path: Path,
) -> None:
    """A nonexistent path is reported and never enters the target list."""
    _extract_path_list(
        {"extensions": ["nope"]},
        config, tmp_path, "extensions", config.extension_paths,
    )

    assert any("path does not exist" in error for error in config.errors)
    assert config.extension_paths == []


def test_extract_path_list_rejects_non_string_entry(
    config: YateConfig, tmp_path: Path,
) -> None:
    _extract_path_list(
        {"extensions": [1]},
        config, tmp_path, "extensions", config.extension_paths,
    )

    assert any(
        "must be non-empty strings" in error for error in config.errors
    )
    assert config.extension_paths == []


def test_extract_path_list_rejects_scalar_value(
    config: YateConfig, tmp_path: Path,
) -> None:
    _extract_path_list(
        {"extensions": 5},
        config, tmp_path, "extensions", config.extension_paths,
    )

    assert any(
        "must be a path string or a list" in error for error in config.errors
    )
    assert config.extension_paths == []


def test_extract_path_list_dedupes_resolved_entries(
    config: YateConfig, tmp_path: Path,
) -> None:
    """The same file spelled relative and absolutely lands once."""
    script = tmp_path / "ext" / "a.py"
    script.parent.mkdir()
    script.write_text("# extension stub\n", encoding="utf-8")

    _extract_path_list(
        {"extensions": ["ext/a.py", str(script)]},
        config, tmp_path, "extensions", config.extension_paths,
    )

    assert len(config.extension_paths) == 1


def test_extract_disabled_extensions_accumulates_names(config: YateConfig) -> None:
    """Bundled-extension stems accumulate (and de-duplicate) into the config."""
    _extract_disabled_extensions({"disabled_extensions": ["x", "y"]}, config)

    assert config.disabled_extensions == ["x", "y"]
    assert config.errors == []


# --- scalar option table -----------------------------------------------------


def test_extract_options_assigns_known_scalar_and_rejects_bad_value(
    config: YateConfig,
) -> None:
    """A KNOWN_OPTIONS scalar lands on the config; an out-of-range value is
    reported and the option keeps its default (``_extract_options`` only
    reads KNOWN_OPTIONS names -- unknown rc variables are not its concern)."""
    _extract_options({"tab_width": 8}, config)
    assert config.tab_width == 8
    assert config.errors == []

    _extract_options({"tab_width": 99}, config)
    assert config.errors, "out-of-range value must be reported"
    assert config.tab_width == 8


# --- dict options ------------------------------------------------------------


def test_extract_screen_saver_maps_keys_and_reports_unknown(
    config: YateConfig,
) -> None:
    """Recognized keys land on ``config.screen_saver``; unknown keys are
    reported individually."""
    values: dict[str, Any] = {"enable": False, "interval": 60, "bogus": 1}

    _extract_screen_saver({"screen_saver": values}, config)

    assert config.screen_saver.enable is False
    assert config.screen_saver.interval == 60
    assert any(
        "unknown keys" in error and "bogus" in error for error in config.errors
    )


def test_extract_file_preview_maps_keys_and_reports_unknown(
    config: YateConfig,
) -> None:
    """Same contract as ``screen_saver``: valid keys apply, unknown keys
    are reported."""
    values: dict[str, Any] = {"position": "left", "size": 40, "nope": True}

    _extract_file_preview({"file_preview": values}, config)

    assert config.file_preview.position == "left"
    assert config.file_preview.size == 40
    assert any(
        "unknown keys" in error and "nope" in error for error in config.errors
    )


# --- declarative language_servers --------------------------------------------


def test_extract_language_servers_builds_spec_and_reports_malformed(
    config: YateConfig,
) -> None:
    """Valid entries build LanguageServerSpec records; malformed ones are
    reported while the remaining entries of the same list still apply."""
    valid: dict[str, Any] = {
        "name": "pylsp",
        "command": "pylsp",
        "filetypes": [".py"],
        "args": ["-v"],
        "root_markers": ["pyproject.toml"],
        "language_ids": {"python": "python"},
        "env": {"X": "1"},
    }

    _extract_language_servers(
        {"language_servers": [{"name": 42}, valid]}, config
    )

    assert config.errors, "the malformed entry must be reported"
    assert [spec.name for spec in config.language_servers] == ["pylsp"]
    spec = config.language_servers[0]
    assert isinstance(spec, LanguageServerSpec)
    assert spec.filetypes == ["py"]  # the leading dot is stripped
    assert spec.root_markers == ["pyproject.toml"]


# --- journey fraction parsing -------------------------------------------------


def test_parse_journey_fraction_accepts_fraction_rejects_rest(
    config: YateConfig,
) -> None:
    """Floats and ``"p/q"`` fraction strings in (0, 1) parse; everything
    else takes the error path and returns None."""
    assert _parse_journey_fraction(0.25, "dist_lower_bound", config) == 0.25
    assert _parse_journey_fraction("1/8", "dist_lower_bound", config) == 0.125
    assert config.errors == []

    assert _parse_journey_fraction(1.5, "dist_lower_bound", config) is None
    assert config.errors, "an out-of-range bound must be reported"
