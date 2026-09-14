"""Tests for yate.diagnostics: version info and the --diag report.

Uses real headless ``YateApp`` instances (no terminal needed) so the report
reflects the same extension/LSP loading path a real run would take.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from yate import diagnostics
from yate.app import YateApp
from yate.config import load_config
from yate.editor_lsp.client import ServerConfig

_ALL_SECTIONS = (
    "system", "terminal", "shell", "paths", "yaterc", "config",
    "themes", "syntax", "extensions", "lsp", "fonts", "packages",
)


def _build_app(*, yaterc: str | None = None, ext_files: list[str | Path] | None = None) -> YateApp:
    """Construct a headless YateApp, optionally loading a yaterc / extensions."""
    if yaterc is not None:
        config = load_config([Path(yaterc)])
    else:
        config = load_config([])
    app = YateApp(config=config, ext_files=ext_files or [])
    app.load_startup_services()
    return app


# --- version lines ----------------------------------------------------------


def test_version_lines_contains_description_and_three_lines() -> None:
    text = diagnostics.version_lines()
    lines = text.splitlines()
    assert len(lines) == 3
    assert lines[0].startswith("yate ")
    # the description is part of the first line
    assert "yet another terminal editor" in lines[0]
    assert "Python" in lines[1]
    # platform line is non-empty and comes from platform.platform()
    assert lines[2]


# --- report structure -------------------------------------------------------


def test_report_contains_all_twelve_sections() -> None:
    report = diagnostics.format_report(_build_app())
    for title in _ALL_SECTIONS:
        assert f"[{title}]" in report, f"missing section [{title}]"


def test_report_has_header_and_divider() -> None:
    report = diagnostics.format_report(_build_app())
    assert report.startswith("yate ")
    assert "diagnostics" in report.splitlines()[0]


# --- config rendering -------------------------------------------------------


def test_yaterc_option_appears_in_config_section(tmp_path: Path) -> None:
    rc = tmp_path / "yaterc"
    rc.write_text("tab_width = 2\nkeymap = 'vim'\n", encoding="utf-8")
    report = diagnostics.format_report(_build_app(yaterc=str(rc)))
    assert "tab_width          : 2" in report
    assert "keymap             : vim" in report


def test_kv_separator_is_colon_everywhere() -> None:
    """Old ``key = value`` / ``key : value`` styles are gone: every
    key-value line uses the single ``key: value`` shape."""
    report = diagnostics.format_report(_build_app())
    for line in report.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("[", "-", "==")):
            continue  # titles, bullets, divider, bare labels
        if ": " in stripped and not stripped.endswith(":"):
            key = stripped.split(": ", 1)[0]
            assert " = " not in stripped and "= " not in key, \
                f"non-uniform separator in line: {line!r}"


# --- extensions section -----------------------------------------------------


def test_broken_extension_shows_error_reason(tmp_path: Path) -> None:
    bad = tmp_path / "broken_ext.py"
    # A script with no setup(api) function fails to load.
    bad.write_text("# no setup function here\n", encoding="utf-8")
    report = diagnostics.format_report(_build_app(ext_files=[bad]))
    assert "[error]" in report
    assert "broken_ext" in report
    assert "no setup" in report


# --- lsp section ------------------------------------------------------------


def test_lsp_env_keys_are_shown_but_values_are_masked() -> None:
    app = _build_app()
    app.lsp.register_server(ServerConfig(
        name="secret-server",
        command="my-lsp",
        filetypes=["py"],
        env={"API_TOKEN": "secret123", "API_KEY": "hunter2"},
    ))
    report = diagnostics.format_report(app)
    # env key names appear
    assert "API_TOKEN" in report
    assert "API_KEY" in report
    # but the secret values must never leak
    assert "secret123" not in report
    assert "hunter2" not in report


# --- best-effort sections ---------------------------------------------------


def test_failing_section_does_not_abort_report() -> None:
    app = _build_app()
    # Force the fonts section to blow up; every other section must still
    # render and the failing one must show a downgrade notice.
    with patch("yate.diagnostics._section_fonts", side_effect=RuntimeError("boom")):
        report = diagnostics.format_report(app)
    # other sections are intact
    assert "[system]" in report
    assert "[config]" in report
    assert "[lsp]" in report
    # the broken section is reported, not silently dropped
    assert "[fonts]" in report
    assert "<probe failed:" in report
    assert "RuntimeError: boom" in report


# --- color handling ---------------------------------------------------------


def test_plain_report_has_no_ansi_escapes() -> None:
    report = diagnostics.format_report(_build_app())
    assert "\x1b[" not in report


def test_colored_report_keeps_text_and_masks_secrets() -> None:
    app = _build_app()
    app.lsp.register_server(ServerConfig(
        name="secret-server",
        command="my-lsp",
        filetypes=["py"],
        env={"API_TOKEN": "secret123"},
    ))
    colored = diagnostics.format_report(app, color=True)
    # ANSI styling present
    assert "\x1b[" in colored
    # text content survives (only styles were added)
    assert "[system]" in colored
    assert "secret-server" in colored
    # secret values still masked in colored output
    assert "secret123" not in colored


def test_print_report_writes_plain_text_to_stdout(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # capsys's stream isatty() is False -> plain text, like a redirected run.
    diagnostics.print_report(_build_app())
    out = capsys.readouterr().out
    assert "[system]" in out
    assert "\x1b[" not in out
