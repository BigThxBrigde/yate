"""Unit tests for ``yate.editor_view.theme_files`` (custom theme loader).

Covers exec'ing a user ``*.py`` theme file into the global registry, the
never-raise error string for broken files, the process-wide resolved-path
idempotence cache and the directory scan (underscore skip, silent missing
path, error collection with a path prefix).

``THEMES`` and ``_loaded_theme_files`` are process-global; the autouse
fixture swaps in private copies so registrations and the resolved-path
cache never leak between tests.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from yate.editor_view import theme_files, themes
from yate.editor_view.theme_files import load_theme_file, load_theme_paths

_THEME_SOURCE = """register_theme(Theme(
    name="{name}", label="RT Probe", dark=True,
    bg="#1e1e2e", panel="#181825", surface="#313244",
    gutter_bg="#11111b", border="#45475a",
    selection_bg="#585b70", match_bg="#f9e2af",
    match_active_bg="#fab387", on_accent="#11111b",
    fg="#cdd6f4", fg_dim="#6c7086", fg_muted="#9399b2",
    fg_bright="#bac2de",
    accent="#89b4fa", accent2="#cba6f7", green="#a6e3a1",
    yellow="#f9e2af", red="#f38ba8", orange="#fab387",
    mode_normal_bg="#89b4fa", mode_insert_bg="#a6e3a1",
    mode_visual_bg="#cba6f7", mode_command_bg="#fab387",
    syn_keyword="#cba6f7", syn_string="#a6e3a1",
    syn_number="#fab387", syn_comment="#6c7086",
    syn_function="#89b4fa", syn_type="#f9e2af",
    syn_constant="#fab387", syn_builtin="#f38ba8",
    syn_decorator="#f5c2e7", syn_operator="#89dceb",
    syn_property="#b4befe",
))
"""


@pytest.fixture(autouse=True)
def restore_themes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Isolate the process-global theme registry and loader cache."""
    monkeypatch.setattr(themes, "THEMES", dict(themes.THEMES))
    monkeypatch.setattr(theme_files, "_loaded_theme_files", set[Path]())


def _write_theme_file(path: Path, name: str) -> None:
    """A valid user theme file registering a single probe theme."""
    path.write_text(_THEME_SOURCE.format(name=name), encoding="utf-8")


# --- load_theme_file -----------------------------------------------------------


def test_load_theme_file_registers_theme_from_user_py(tmp_path: Path) -> None:
    path = tmp_path / "probe_theme.py"
    _write_theme_file(path, "rt_probe")
    assert load_theme_file(path) is None
    assert "rt_probe" in themes.THEMES


def test_load_theme_file_broken_file_returns_error_string(
    tmp_path: Path,
) -> None:
    path = tmp_path / "broken.py"
    path.write_text("x =", encoding="utf-8")
    problem = load_theme_file(path)
    assert problem is not None
    assert problem.startswith("SyntaxError")


def test_load_theme_file_second_load_is_noop(tmp_path: Path) -> None:
    path = tmp_path / "probe_theme.py"
    _write_theme_file(path, "rt_probe")
    assert load_theme_file(path) is None
    assert load_theme_file(path) is None
    # overwrite with a file that would fail to exec: the resolved-path
    # cache short-circuits before the broken source is read again
    path.write_text("x =", encoding="utf-8")
    assert load_theme_file(path) is None
    assert "rt_probe" in themes.THEMES


# --- load_theme_paths ----------------------------------------------------------


def test_load_theme_paths_directory_skips_underscore_files(
    tmp_path: Path,
) -> None:
    (tmp_path / "_bad.py").write_text("x =", encoding="utf-8")
    _write_theme_file(tmp_path / "good.py", "good_theme")
    errors: list[str] = []
    load_theme_paths([tmp_path], errors)
    assert errors == []
    assert "good_theme" in themes.THEMES


def test_load_theme_paths_missing_path_is_silent(tmp_path: Path) -> None:
    errors: list[str] = []
    load_theme_paths([tmp_path / "nope"], errors)
    assert errors == []


def test_load_theme_paths_collects_errors_with_path_prefix(
    tmp_path: Path,
) -> None:
    bad = tmp_path / "bad.py"
    bad.write_text("x =", encoding="utf-8")
    errors: list[str] = []
    load_theme_paths([tmp_path], errors)
    assert len(errors) == 1
    assert errors[0].startswith(str(bad))
    assert ": SyntaxError" in errors[0]
