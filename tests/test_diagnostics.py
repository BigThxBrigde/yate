"""Tests for yate.diagnostics: version info and the --diag report.

Uses real headless ``YateApp`` instances (no terminal needed) so the report
reflects the same extension/LSP loading path a real run would take.
"""

from __future__ import annotations

import importlib.metadata
import io
import re
import sys
from pathlib import Path
from typing import Any, override
from unittest.mock import patch

import pytest

from yate import diagnostics
from yate.app import YateApp
from yate.config import load_config
from yate.editor_lsp.client import ServerConfig

_ALL_SECTIONS: tuple[str, ...] = (
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
    app.editor.extension_flows.load_extensions()
    app.editor.extension_flows.register_configured_servers()
    return app


# --- report structure -------------------------------------------------------


def test_report_contains_all_twelve_sections() -> None:
    report = diagnostics.format_report(_build_app().editor)
    for title in _ALL_SECTIONS:
        assert f"[{title}]" in report, f"missing section [{title}]"


def test_report_has_header_and_divider() -> None:
    report = diagnostics.format_report(_build_app().editor)
    assert report.startswith("yate ")
    assert "diagnostics" in report.splitlines()[0]


# --- config rendering -------------------------------------------------------


def test_yaterc_option_appears_in_config_section(tmp_path: Path) -> None:
    rc = tmp_path / "yaterc"
    rc.write_text("tab_width = 2\nkeymap = 'vim'\n", encoding="utf-8")
    report = diagnostics.format_report(_build_app(yaterc=str(rc)).editor)
    assert "tab_width          : 2" in report
    assert "keymap             : vim" in report


def test_kv_separator_is_colon_everywhere() -> None:
    """Old ``key = value`` / ``key : value`` styles are gone: every
    key-value line uses the single ``key: value`` shape."""
    report = diagnostics.format_report(_build_app().editor)
    for line in report.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("[", "-", "==")):
            continue  # titles, bullets, divider, bare labels
        if ": " in stripped and not stripped.endswith(":"):
            key = stripped.split(": ", 1)[0]
            assert " = " not in stripped and "= " not in key, (
                f"non-uniform separator in line: {line!r}"
            )


# --- extensions section -----------------------------------------------------


def test_broken_extension_shows_error_reason(tmp_path: Path) -> None:
    bad = tmp_path / "broken_ext.py"
    # A script with no setup(api) function fails to load.
    bad.write_text("# no setup function here\n", encoding="utf-8")
    report = diagnostics.format_report(_build_app(ext_files=[bad]).editor)
    assert "[error]" in report
    assert "broken_ext" in report
    assert "no setup" in report


# --- lsp section ------------------------------------------------------------


def test_lsp_env_keys_are_shown_but_values_are_masked() -> None:
    app = _build_app()
    app.editor.lsp.register_server(ServerConfig(
        name="secret-server",
        command="my-lsp",
        filetypes=["py"],
        env={"API_TOKEN": "secret123", "API_KEY": "hunter2"},
    ))
    report = diagnostics.format_report(app.editor)
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
        report = diagnostics.format_report(app.editor)
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
    report = diagnostics.format_report(_build_app().editor)
    assert "\x1b[" not in report


def test_colored_report_keeps_text_and_masks_secrets() -> None:
    app = _build_app()
    app.editor.lsp.register_server(ServerConfig(
        name="secret-server",
        command="my-lsp",
        filetypes=["py"],
        env={"API_TOKEN": "secret123"},
    ))
    colored = diagnostics.format_report(app.editor, color=True)
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
    diagnostics.print_report(_build_app().editor)
    out = capsys.readouterr().out
    assert "[system]" in out
    assert "\x1b[" not in out


class _TtyStream(io.StringIO):
    """stdout stand-in that claims to be a terminal."""

    @override
    def isatty(self) -> bool:
        """Claim to be a terminal so the report is rendered in color."""
        return True


def test_print_report_colors_on_a_terminal(monkeypatch: pytest.MonkeyPatch) -> None:
    """A tty stdout switches the report to ANSI styling."""
    stream = _TtyStream()
    monkeypatch.setattr(sys, "stdout", stream)

    diagnostics.print_report(_build_app().editor)

    written = stream.getvalue()
    assert "[system]" in written
    assert "\x1b[" in written


def test_colored_report_styles_the_error_lines(tmp_path: Path) -> None:
    """Extension load errors are rendered with the error colour."""
    bad = tmp_path / "broken_ext.py"
    bad.write_text("# no setup function here\n", encoding="utf-8")

    report = diagnostics.format_report(
        _build_app(ext_files=[bad]).editor, color=True
    )

    assert "[error]" in report
    assert "\x1b[" in report


# --- section edge cases -----------------------------------------------------


def test_empty_section_body_renders_none() -> None:
    """A section that produces no lines is still shown, with a marker."""
    app = _build_app()
    with patch("yate.diagnostics._section_fonts", return_value=[]):
        report = diagnostics.format_report(app.editor)
    assert "[fonts]" in report
    assert "  (none)" in report


def test_recent_crash_reports_are_listed() -> None:
    """Previous crash files are listed in the paths section."""
    from yate.logs import crash_data_dir

    data = crash_data_dir()
    data.mkdir(parents=True, exist_ok=True)
    crash_file = data / "crash-20240101-000000.err"
    crash_file.write_text("boom\n", encoding="utf-8")

    report = diagnostics.format_report(_build_app().editor)

    assert "recent crash reports:" in report
    assert crash_file.name in report


def test_yaterc_load_errors_are_listed(tmp_path: Path) -> None:
    """Options the yaterc got wrong are reported, not silently dropped."""
    rc = tmp_path / "yaterc"
    rc.write_text('tab_width = "wide"\n', encoding="utf-8")

    report = diagnostics.format_report(_build_app(yaterc=str(rc)).editor)

    assert "load errors:" in report
    assert "tab_width" in report


def test_missing_extension_file_is_flagged(tmp_path: Path) -> None:
    """A ``--ext`` path that does not exist is reported as missing."""
    missing = tmp_path / "nope.py"

    report = diagnostics.format_report(_build_app(ext_files=[missing]).editor)

    assert f"ext-file: {missing} (missing)" in report


def test_rc_and_ext_dir_candidates_are_listed(tmp_path: Path) -> None:
    """rc-declared and ``--ext-dir`` candidates appear with their script count."""
    rc_dir = tmp_path / "rc-ext"
    rc_dir.mkdir()
    (rc_dir / "one.py").write_text("def setup(api): pass\n", encoding="utf-8")
    ext_dir = tmp_path / "cli-ext"
    ext_dir.mkdir()

    app = YateApp(config=load_config([]), ext_dirs=[ext_dir])
    app.editor.config.extension_paths.append(rc_dir)
    app.editor.extension_flows.load_extensions()
    app.editor.extension_flows.register_configured_servers()

    report = diagnostics.format_report(app.editor)

    assert f"rc      : {rc_dir} (1 script(s))" in report
    assert f"ext-dir : {ext_dir} (0 script(s))" in report


def test_no_loaded_extensions_renders_a_placeholder() -> None:
    """An empty extension list shows the placeholder instead of a blank."""
    app = _build_app()
    with patch.object(app.editor.extension_loader, "loaded", []):
        report = diagnostics.format_report(app.editor)
    assert "  loaded:" in report
    assert "    (none)" in report


def test_no_lsp_servers_registered() -> None:
    """The LSP section explains itself when nothing was registered."""
    app = _build_app()
    with patch.object(app.editor.lsp, "configs", return_value=[]):
        report = diagnostics.format_report(app.editor)
    assert "(no LSP servers registered)" in report


def test_syntax_section_without_tree_sitter() -> None:
    """Without the optional backend the syntax section says so."""
    app = _build_app()
    with patch("yate.editor_syntax.ts_backend.ts_available", return_value=False):
        report = diagnostics.format_report(app.editor)
    assert "not available (tree_sitter not installed)" in report


def test_syntax_section_handles_missing_grammars_and_short_lists() -> None:
    """A grammar that cannot be resolved is skipped; a short list is not cut."""
    app = _build_app()
    with (
        patch("yate.editor_syntax.ts_backend.ts_available", return_value=True),
        patch("yate.editor_syntax.resolve_filetype", return_value=None),
        patch("yate.editor_syntax.available_filetypes", return_value=["py"]),
    ):
        report = diagnostics.format_report(app.editor)
    assert "regex languages" in report
    assert "py" in report


def test_missing_packages_are_reported_as_not_installed() -> None:
    """An uninstalled optional package degrades to a readable note."""
    app = _build_app()
    with patch(
        "yate.diagnostics.importlib_metadata.version",
        side_effect=importlib.metadata.PackageNotFoundError("nope"),
    ):
        report = diagnostics.format_report(app.editor)
    assert "not installed" in report


# --- packages section -------------------------------------------------------


def _private(name: str) -> Any:
    """Reach a diagnostics module-private on purpose (they carry the logic)."""
    return getattr(diagnostics, name)


#: Extra-group marker in a Requires-Dist string; kept as an independent
#: oracle here instead of reusing ``dist_meta._REQ_EXTRA_RE``.
_EXTRA_MARKER_RE: re.Pattern[str] = re.compile(r"\bextra\s*==\s*['\"]([^'\"]+)['\"]")


def _group_slices(lines: list[str]) -> dict[str, list[str]]:
    """Split ``_section_packages()`` output into ``{group: [detail rows]}``.

    Label lines carry a two-space indent (``  ts:``) and detail rows a
    four-space one, so the indent width tells the two kinds apart.
    """
    slices: dict[str, list[str]] = {}
    current = ""
    for line in lines:
        if line.startswith("  ") and not line.startswith("    "):
            current = line.strip().removesuffix(":")
            slices[current] = []
        else:
            slices[current].append(line)
    return slices


def test_packages_section_derives_core_dependencies_from_metadata() -> None:
    """Real dist metadata drives the inventory: core deps are complete.

    The issue's root cause was a hand-kept name list missing ``pyperclip``;
    deriving from Requires-Dist keeps the report in sync with pyproject.toml.
    """
    lines: list[str] = _private("_section_packages")()
    assert "  core:" in lines
    core_rows = _group_slices(lines)["core"]
    for name in ("pyperclip", "textual"):
        rows = [row for row in core_rows if name in row]
        assert rows, f"missing core row for {name}"
        assert ": " in rows[0]
        assert "not installed" not in rows[0]


def test_packages_section_lists_declared_feature_extras_and_skips_tooling() -> None:
    """Declared feature extras each get a group; dev/build tooling stays out."""
    lines: list[str] = _private("_section_packages")()
    raw = importlib.metadata.requires("yate") or []
    declared = {
        match.group(1)
        for req in raw
        if (match := _EXTRA_MARKER_RE.search(req)) is not None
    }
    skipped: frozenset[str] = _private("_SKIPPED_EXTRAS")
    shown = sorted(declared - skipped)
    assert shown, "expected the ts feature extra to be declared in pyproject"
    for extra in shown:
        assert f"  {extra}:" in lines
    for extra in sorted(declared & skipped):
        assert f"  {extra}:" not in lines
    assert "  dev:" not in lines
    assert "  build:" not in lines
    for tool in ("pyright", "pytest", "pyinstaller", "pillow"):
        assert not any(tool in line for line in lines), tool
    core_index = lines.index("  core:")
    extra_indexes = [lines.index(f"  {extra}:") for extra in shown]
    assert all(core_index < index for index in extra_indexes)
    ts_rows = _group_slices(lines).get("ts", [])
    assert any("tree-sitter" in row for row in ts_rows)


def test_packages_section_parses_controlled_requirements() -> None:
    """Controlled metadata: grouping, dedup, canonical keys, display shape."""
    requirements = [
        "textual>=8.0",
        "pyperclip>=1.8.2; extra == 'ts'",
        "pyperclip>=1.8.2; extra == 'ts'",  # duplicate canonical -> one row
        "Foo_Bar>=1.0; extra == 'ts'",      # canonical foo-bar, display kept
        "pyright>=1.1.400; extra == 'dev'", # skipped group -> not rendered
    ]

    def fake_version(name: str) -> str:
        if name == "Foo_Bar":
            return "9.9"
        raise importlib.metadata.PackageNotFoundError(name)

    with (
        patch("yate.dist_meta.importlib_metadata.requires", return_value=requirements),
        patch("yate.diagnostics.importlib_metadata.version", side_effect=fake_version),
    ):
        lines: list[str] = _private("_section_packages")()

    groups = _group_slices(lines)
    assert list(groups) == ["core", "ts"]  # dev filtered out entirely
    assert len(groups["core"]) == 1 and "textual" in groups["core"][0]
    assert len(groups["ts"]) == 2
    pyperclip_rows = [row for row in groups["ts"] if "pyperclip" in row]
    assert len(pyperclip_rows) == 1 and "not installed" in pyperclip_rows[0]
    foo_rows = [row for row in groups["ts"] if "Foo_Bar" in row]
    assert len(foo_rows) == 1 and ": 9.9" in foo_rows[0]
    assert not any("pyright" in line for line in lines)
    # label lines indent 2, detail rows 4 -- and each kind matches only its
    # own colorizer regex, so coloring stays unambiguous.
    label_re: re.Pattern[str] = _private("_LABEL_LINE_RE")
    kv_re: re.Pattern[str] = _private("_KV_LINE_RE")
    for line in lines:
        if line.endswith(":"):
            assert line.startswith("  ") and not line.startswith("    ")
            assert label_re.match(line) is not None
            assert kv_re.match(line) is None
        else:
            assert line.startswith("    ")
            assert kv_re.match(line) is not None
            assert label_re.match(line) is None


def test_packages_section_column_alignment_uses_display_names() -> None:
    """The ``[packages]`` column width comes from rendered display names.

    ``Foo__Bar`` canonicalizes to ``foo-bar`` (7 chars) while the rendered
    display name keeps 8, so deriving the width from the canonical keys
    shifts that row's ``": "`` right of the others (PR #47 AI review,
    improvement 1) -- the width must be taken from the display values.
    """
    requirements = [
        "textual>=8.0",
        "Foo__Bar>=1.0; extra == 'ts'",
    ]

    def fake_version(name: str) -> str:
        raise importlib.metadata.PackageNotFoundError(name)

    with (
        patch("yate.dist_meta.importlib_metadata.requires", return_value=requirements),
        patch("yate.diagnostics.importlib_metadata.version", side_effect=fake_version),
    ):
        lines: list[str] = _private("_section_packages")()

    detail_rows = [line for line in lines if line.startswith("    ")]
    assert detail_rows, "expected at least one detail row"
    columns = {row.index(": ") for row in detail_rows}
    assert len(columns) == 1, f"misaligned detail rows: {sorted(detail_rows)}"


def test_packages_section_without_requires_metadata_is_empty() -> None:
    """``requires()`` returning ``None`` renders an empty inventory."""
    with patch("yate.dist_meta.importlib_metadata.requires", return_value=None):
        assert _private("_section_packages")() == []


def test_packages_section_without_core_requirements_renders_extras_only() -> None:
    """Every requirement carrying an extra marker still renders, coreless.

    Regression guard: "core" leads ``ordered`` unconditionally, so an empty
    core group must be dropped instead of raising ``KeyError`` (review round
    1) -- here all requirements are extra-marked and the report shows the
    ``ts`` group only.
    """
    requirements = [
        "tree-sitter>=0.24,<0.26; extra == 'ts'",
        "tree-sitter-python>=0.23; extra == 'ts'",
    ]

    def fake_version(name: str) -> str:
        raise importlib.metadata.PackageNotFoundError(name)

    with (
        patch("yate.dist_meta.importlib_metadata.requires", return_value=requirements),
        patch("yate.diagnostics.importlib_metadata.version", side_effect=fake_version),
    ):
        lines: list[str] = _private("_section_packages")()

    assert lines  # the ts group renders despite the empty core group
    assert "  core:" not in lines
    groups = _group_slices(lines)
    assert list(groups) == ["ts"]
    assert all("not installed" in row for row in groups["ts"])
