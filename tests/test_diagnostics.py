"""Tests for yate.diagnostics: version info and the --diag report.

Uses real headless ``YateApp`` instances (no terminal needed) so the report
reflects the same extension/LSP loading path a real run would take.
"""

from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

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


class VersionLinesTests(unittest.TestCase):
    def test_version_lines_contains_description_and_three_lines(self) -> None:
        text = diagnostics.version_lines()
        lines = text.splitlines()
        self.assertEqual(len(lines), 3)
        self.assertTrue(lines[0].startswith("yate "))
        # the description is part of the first line
        self.assertIn("yet another terminal editor", lines[0])
        self.assertIn("Python", lines[1])
        # platform line is non-empty and comes from platform.platform()
        self.assertTrue(lines[2])


class ReportStructureTests(unittest.TestCase):
    def test_report_contains_all_twelve_sections(self) -> None:
        app = _build_app()
        report = diagnostics.format_report(app)
        for title in _ALL_SECTIONS:
            self.assertIn(f"[{title}]", report, f"missing section [{title}]")

    def test_report_has_header_and_divider(self) -> None:
        app = _build_app()
        report = diagnostics.format_report(app)
        self.assertTrue(report.startswith("yate "))
        self.assertIn("diagnostics", report.splitlines()[0])


class ReportConfigTests(unittest.TestCase):
    def test_yaterc_option_appears_in_config_section(self) -> None:
        with TemporaryDirectory() as tmp:
            rc = Path(tmp) / "yaterc"
            rc.write_text("tab_width = 2\nkeymap = 'vim'\n", encoding="utf-8")
            app = _build_app(yaterc=str(rc))
        report = diagnostics.format_report(app)
        self.assertIn("tab_width          : 2", report)
        self.assertIn("keymap             : vim", report)

    def test_kv_separator_is_colon_everywhere(self) -> None:
        """Old ``key = value`` / ``key : value`` styles are gone: every
        key-value line uses the single ``key: value`` shape."""
        app = _build_app()
        report = diagnostics.format_report(app)
        for line in report.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith(("[", "-", "==")):
                continue  # titles, bullets, divider, bare labels
            if ": " in stripped and not stripped.endswith(":"):
                key = stripped.split(": ", 1)[0]
                self.assertFalse(
                    " = " in stripped or "= " in key,
                    f"non-uniform separator in line: {line!r}",
                )


class ReportExtensionsTests(unittest.TestCase):
    def test_broken_extension_shows_error_reason(self) -> None:
        with TemporaryDirectory() as tmp:
            bad = Path(tmp) / "broken_ext.py"
            # A script with no setup(api) function fails to load.
            bad.write_text("# no setup function here\n", encoding="utf-8")
            app = _build_app(ext_files=[bad])
        report = diagnostics.format_report(app)
        self.assertIn("[error]", report)
        self.assertIn("broken_ext", report)
        self.assertIn("no setup", report)


class ReportLspMaskingTests(unittest.TestCase):
    def test_lsp_env_keys_are_shown_but_values_are_masked(self) -> None:
        app = _build_app()
        app.lsp.register_server(ServerConfig(
            name="secret-server",
            command="my-lsp",
            filetypes=["py"],
            env={"API_TOKEN": "secret123", "API_KEY": "hunter2"},
        ))
        report = diagnostics.format_report(app)
        # env key names appear
        self.assertIn("API_TOKEN", report)
        self.assertIn("API_KEY", report)
        # but the secret values must never leak
        self.assertNotIn("secret123", report)
        self.assertNotIn("hunter2", report)


class ReportBestEffortTests(unittest.TestCase):
    def test_failing_section_does_not_abort_report(self) -> None:
        app = _build_app()
        # Force the fonts section to blow up; every other section must still
        # render and the failing one must show a downgrade notice.
        with patch("yate.diagnostics._section_fonts", side_effect=RuntimeError("boom")):
            report = diagnostics.format_report(app)
        # other sections are intact
        self.assertIn("[system]", report)
        self.assertIn("[config]", report)
        self.assertIn("[lsp]", report)
        # the broken section is reported, not silently dropped
        self.assertIn("[fonts]", report)
        self.assertIn("<probe failed:", report)
        self.assertIn("RuntimeError: boom", report)


class ReportColorTests(unittest.TestCase):
    def test_plain_report_has_no_ansi_escapes(self) -> None:
        report = diagnostics.format_report(_build_app())
        self.assertNotIn("\x1b[", report)

    def test_colored_report_keeps_text_and_masks_secrets(self) -> None:
        app = _build_app()
        app.lsp.register_server(ServerConfig(
            name="secret-server",
            command="my-lsp",
            filetypes=["py"],
            env={"API_TOKEN": "secret123"},
        ))
        colored = diagnostics.format_report(app, color=True)
        # ANSI styling present
        self.assertIn("\x1b[", colored)
        # text content survives (only styles were added)
        self.assertIn("[system]", colored)
        self.assertIn("secret-server", colored)
        # secret values still masked in colored output
        self.assertNotIn("secret123", colored)

    def test_print_report_writes_plain_text_to_stdout(self) -> None:
        # StringIO.isatty() is False -> plain text, like a redirected run.
        buf = io.StringIO()
        with redirect_stdout(buf):
            diagnostics.print_report(_build_app())
        out = buf.getvalue()
        self.assertIn("[system]", out)
        self.assertNotIn("\x1b[", out)


if __name__ == "__main__":
    unittest.main()
