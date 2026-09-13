"""Headless tests for the command line entry point (yate.cli).

Argument parsing plus the pre-TUI startup path (config + custom theme
loading).  Launching the real TUI needs a terminal, so ``main()`` is run
with ``yate.app.YateApp`` replaced by a fake that records its kwargs and
never enters Textual.
"""

from __future__ import annotations

import io
import os
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from unittest.mock import MagicMock, patch

import yate
from yate.cli import build_parser, main

_CUSTOM_THEME_SRC = """\
from dataclasses import replace

from yate.editor_view.theme import THEMES, register_theme

register_theme(replace(
    THEMES["mocha"], name="cli-custom", label="CLI Custom", accent="#ff0000"
))
"""


class _FakeApp:
    """Records constructor kwargs instead of launching the TUI."""

    last_kwargs: dict[str, object] | None = None
    last_instance: "_FakeApp | None" = None

    def __init__(self, **kwargs: object) -> None:
        type(self).last_kwargs = kwargs
        type(self).last_instance = self
        self.load_startup_services_called = False

    def load_startup_services(self) -> None:
        self.load_startup_services_called = True

    def run(self) -> None:
        return None


class CliParserTests(unittest.TestCase):
    def test_extension_dests_default_to_empty_lists(self) -> None:
        args = build_parser().parse_args([])
        self.assertEqual(args.ext_files, [])
        self.assertEqual(args.ext_dirs, [])

    def test_ext_flags_are_repeatable_into_expected_dests(self) -> None:
        args = build_parser().parse_args(
            ["--ext", "a.py", "--ext", "b.py", "--ext-dir", "exts", "--ext-dir", "more"]
        )
        self.assertEqual(args.ext_files, ["a.py", "b.py"])
        self.assertEqual(args.ext_dirs, ["exts", "more"])

    def test_theme_dir_flag_repeatable_into_expected_dest(self) -> None:
        self.assertEqual(build_parser().parse_args([]).theme_dirs, [])
        args = build_parser().parse_args(
            ["--theme-dir", "themes", "--theme-dir", "extra"]
        )
        self.assertEqual(args.theme_dirs, ["themes", "extra"])

    def test_theme_flag(self) -> None:
        self.assertIsNone(build_parser().parse_args([]).theme)
        self.assertEqual(
            build_parser().parse_args(["--theme", "latte"]).theme, "latte"
        )

    def test_keymap_flag_and_alias(self) -> None:
        self.assertEqual(build_parser().parse_args(["--keymap", "vim"]).keymap, "vim")
        # "normal" is the documented vsc alias and must parse without error.
        self.assertEqual(build_parser().parse_args(["--keymap", "normal"]).keymap, "normal")

    def test_yaterc_none_and_path(self) -> None:
        self.assertEqual(build_parser().parse_args(["-u", "NONE"]).yaterc, "NONE")
        self.assertEqual(build_parser().parse_args(["-u", "rc.py"]).yaterc, "rc.py")

    def test_positional_path(self) -> None:
        self.assertEqual(build_parser().parse_args(["some/file.txt"]).path, "some/file.txt")
        self.assertIsNone(build_parser().parse_args([]).path)

    def test_version_flag_is_store_true(self) -> None:
        self.assertFalse(build_parser().parse_args([]).version)
        self.assertTrue(build_parser().parse_args(["--version"]).version)

    def test_diag_flag_is_store_true(self) -> None:
        self.assertFalse(build_parser().parse_args([]).diag)
        self.assertTrue(build_parser().parse_args(["--diag"]).diag)

    def test_changelog_flag_defaults_to_en(self) -> None:
        self.assertIsNone(build_parser().parse_args([]).changelog)
        self.assertEqual(build_parser().parse_args(["--changelog"]).changelog, "en")
        self.assertEqual(
            build_parser().parse_args(["--changelog", "zh"]).changelog, "zh"
        )
        with self.assertRaises(SystemExit):
            build_parser().parse_args(["--changelog", "fr"])


class CliChangelogTests(unittest.TestCase):
    """--changelog prints the bundled changelog and exits before the TUI."""

    def _run(self, argv: list[str]) -> tuple[int, str]:
        buf = io.StringIO()
        with patch("yate.app.YateApp") as fake_app, \
                patch("yate.config.load_config") as load_config, \
                patch("yate.crash.install"):
            with redirect_stdout(buf):
                rc = main(argv)
        fake_app.assert_not_called()
        load_config.assert_not_called()
        return rc, buf.getvalue()

    def test_changelog_prints_bundled_content_and_exits_zero(self) -> None:
        rc, out = self._run(["--changelog"])
        self.assertEqual(rc, 0)
        self.assertTrue(out.startswith("# Changelog"))

    def test_changelog_lang_selects_edition(self) -> None:
        rc, out = self._run(["--changelog", "zh"])
        self.assertEqual(rc, 0)
        self.assertTrue(out.startswith("# 变更日志"))

    def test_changelog_missing_resource_degrades_without_raising(self) -> None:
        placeholder = "# Changelog\n\nNo changelog is shipped with this build."
        with patch("yate.editor_view.manual.load_changelog_markdown",
                   return_value=placeholder):
            rc, out = self._run(["--changelog"])
        self.assertEqual(rc, 0)
        self.assertIn("No changelog is shipped", out)


class CliVersionDiagTests(unittest.TestCase):
    """--version and --diag exit before the TUI runs."""

    def test_version_prints_basic_info_and_exits_zero(self) -> None:
        buf = io.StringIO()
        with patch("yate.app.YateApp") as fake_app, \
                patch("yate.config.load_config") as load_config, \
                patch("yate.crash.install"):
            with redirect_stdout(buf):
                rc = main(["--version"])
        self.assertEqual(rc, 0)
        out = buf.getvalue()
        self.assertIn(f"yate {yate.__version__}", out)
        # the description is part of the first line
        self.assertIn("yet another terminal editor", out.splitlines()[0])
        self.assertIn("Python", out)
        # platform string is present on the third line
        self.assertGreater(len(out.splitlines()), 2)
        # --version must not construct the app or read any config
        fake_app.assert_not_called()
        load_config.assert_not_called()

    def test_diag_prints_report_without_running_tui(self) -> None:
        sentinel = "DIAG-REPORT-SENTINEL"
        buf = io.StringIO()
        with patch("yate.app.YateApp", _FakeApp), \
                patch("yate.diagnostics.format_report", return_value=sentinel) as fmt, \
                patch("yate.crash.install"):
            with redirect_stdout(buf):
                rc = main(["-u", "NONE", "--diag"])
        self.assertEqual(rc, 0)
        self.assertIn(sentinel, buf.getvalue())
        # format_report was called with the constructed app
        self.assertEqual(fmt.call_count, 1)
        app_arg = fmt.call_args.args[0]
        self.assertIsInstance(app_arg, _FakeApp)
        # startup services were loaded so the report reflects real state
        self.assertTrue(app_arg.load_startup_services_called)

    def test_diag_with_none_yaterc_reports_no_rc_loaded(self) -> None:
        """-u NONE --diag must report that no yaterc was loaded."""
        buf = io.StringIO()
        with patch("yate.crash.install"):
            with redirect_stdout(buf):
                rc = main(["-u", "NONE", "--diag"])
        self.assertEqual(rc, 0)
        out = buf.getvalue()
        self.assertIn("[yaterc]", out)
        self.assertIn("no yaterc loaded", out)


class CliThemeStartupTests(unittest.TestCase):
    """main() auto-loads --theme-dir entries and forwards --theme."""

    def tearDown(self) -> None:
        from yate.editor_view import theme as theme_mod

        theme_mod.THEMES.pop("cli-custom", None)
        theme_mod.set_theme("mocha")

    def _run_main(self, argv: list[str], home: Path | None = None) -> dict[str, object]:
        saved = {key: os.environ.get(key) for key in ("USERPROFILE", "HOME")}
        try:
            if home is not None:
                os.environ["USERPROFILE"] = str(home)
                os.environ["HOME"] = str(home)
            with patch("yate.app.YateApp", _FakeApp), \
                    patch("yate.crash.install") as install_crash:
                rc = main(argv)
            self.assertEqual(rc, 0)
            # diagnostics are armed before anything else in main()
            install_crash.assert_called_once_with()
        finally:
            for key, value in saved.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
        self.assertIsNotNone(_FakeApp.last_kwargs)
        assert _FakeApp.last_kwargs is not None
        return _FakeApp.last_kwargs

    def test_theme_dir_auto_loads_and_theme_selects_custom_theme(self) -> None:
        from yate.editor_view import theme as theme_mod

        with TemporaryDirectory() as tmp:
            folder = Path(tmp) / "mythemes"
            folder.mkdir()
            (folder / "custom.py").write_text(_CUSTOM_THEME_SRC, encoding="utf-8")
            kwargs = self._run_main(
                ["-u", "NONE", "--theme-dir", str(folder), "--theme", "cli-custom"]
            )
            # the custom theme was registered before the app was built...
            self.assertIn("cli-custom", theme_mod.available())
            self.assertEqual(kwargs["theme_name"], "cli-custom")
            # ...and the real constructor selects it as the process theme
            from yate.app import YateApp

            YateApp(theme_name="cli-custom")
            self.assertEqual(theme_mod.active().name, "cli-custom")

    def test_theme_dir_tilde_is_expanded(self) -> None:
        """PowerShell/cmd pass '~' literally; main() must expand it."""
        from yate.editor_view import theme as theme_mod

        with TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            folder = home / "mythemes"
            folder.mkdir(parents=True)
            (folder / "custom.py").write_text(_CUSTOM_THEME_SRC, encoding="utf-8")
            kwargs = self._run_main(
                ["-u", "NONE", "--theme-dir", "~/mythemes",
                 "--theme", "cli-custom"],
                home=home,
            )
            self.assertIn("cli-custom", theme_mod.available())
            self.assertEqual(kwargs["theme_name"], "cli-custom")

    def test_unknown_theme_override_is_recorded_as_config_error(self) -> None:
        from yate.app import YateApp

        app = YateApp(theme_name="definitely-not-a-theme")
        self.assertTrue(
            any("unknown theme" in err for err in app.config.errors),
            app.config.errors,
        )

    def test_theme_name_defaults_to_none_when_flag_absent(self) -> None:
        with TemporaryDirectory() as tmp:
            kwargs = self._run_main(["-u", "NONE"], home=Path(tmp))
            self.assertIsNone(kwargs["theme_name"])


class CliSetupDefaultsTests(unittest.TestCase):
    """--setup-defaults / --cleanup-defaults run and exit before the TUI."""

    def _run(
        self,
        argv: list[str],
        *,
        setup: MagicMock | None = None,
        cleanup: MagicMock | None = None,
    ) -> tuple[int, str, MagicMock, MagicMock]:
        from yate.services import user_setup

        if setup is None:
            setup = MagicMock()
        if cleanup is None:
            cleanup = MagicMock()
        buf = io.StringIO()
        with patch("yate.app.YateApp") as fake_app, \
                patch("yate.config.load_config") as load_config, \
                patch("yate.crash.install"), \
                patch.object(user_setup, "setup_defaults", setup) as s, \
                patch.object(user_setup, "cleanup_defaults", cleanup) as c:
            with redirect_stdout(buf):
                rc = main(argv)
        fake_app.assert_not_called()
        load_config.assert_not_called()
        return rc, buf.getvalue(), s, c

    @staticmethod
    def _setup_report(**kwargs: Any) -> object:
        from yate.services.user_setup import SetupReport

        return SetupReport(base_dir=Path.home() / ".yate", **kwargs)

    @staticmethod
    def _cleanup_report(**kwargs: Any) -> object:
        from yate.services.user_setup import CleanupReport

        return CleanupReport(base_dir=Path.home() / ".yate", **kwargs)

    def test_parser_flags_and_mutual_exclusion(self) -> None:
        parser = build_parser()
        args = parser.parse_args([])
        self.assertFalse(args.setup_defaults)
        self.assertFalse(args.cleanup_defaults)
        self.assertFalse(args.force)
        self.assertFalse(args.include_data)
        self.assertTrue(parser.parse_args(["--setup-defaults"]).setup_defaults)
        self.assertTrue(parser.parse_args(["--cleanup-defaults"]).cleanup_defaults)
        self.assertTrue(
            parser.parse_args(["--cleanup-defaults", "--force",
                               "--include-data"]).include_data
        )
        with self.assertRaises(SystemExit) as ctx:
            parser.parse_args(["--setup-defaults", "--cleanup-defaults"])
        self.assertEqual(ctx.exception.code, 2)

    def test_help_text_lists_both_options(self) -> None:
        help_text = build_parser().format_help()
        self.assertIn("--setup-defaults", help_text)
        self.assertIn("--cleanup-defaults", help_text)
        self.assertIn("--include-data", help_text)

    def test_setup_defaults_invokes_service_and_exits_zero(self) -> None:
        setup = MagicMock(return_value=self._setup_report())
        rc, out, s, _ = self._run(["--setup-defaults"], setup=setup)
        self.assertEqual(rc, 0)
        s.assert_called_once_with(force=False)
        self.assertIn("yate user directory", out)

    def test_setup_defaults_force_passthrough_and_error_exit_code(self) -> None:
        ok = MagicMock(return_value=self._setup_report())
        rc, _, s, _ = self._run(["--setup-defaults", "--force"], setup=ok)
        self.assertEqual(rc, 0)
        s.assert_called_once_with(force=True)

        failed = MagicMock(
            return_value=self._setup_report(errors=["yaterc: disk full"])
        )
        rc, out, _, _ = self._run(["--setup-defaults"], setup=failed)
        self.assertEqual(rc, 1)
        self.assertIn("disk full", out)

    def test_cleanup_defaults_passes_force_and_include_data(self) -> None:
        cleanup = MagicMock(return_value=self._cleanup_report())
        with patch("yate.crash.uninstall") as uninstall:
            rc, _, _, c = self._run(
                ["--cleanup-defaults", "--force", "--include-data"],
                cleanup=cleanup,
            )
        self.assertEqual(rc, 0)
        c.assert_called_once_with(force=True, include_data=True)
        # The open crash report handle must be released first so data/ can
        # actually be removed (notably on Windows).
        uninstall.assert_called_once_with()

    def test_cleanup_without_include_data_keeps_crash_handle(self) -> None:
        cleanup = MagicMock(return_value=self._cleanup_report())
        with patch("yate.crash.uninstall") as uninstall:
            rc, _, _, _ = self._run(
                ["--cleanup-defaults", "--force"], cleanup=cleanup
            )
        self.assertEqual(rc, 0)
        uninstall.assert_not_called()

    def test_cleanup_cancelled_still_exits_zero(self) -> None:
        cleanup = MagicMock(
            return_value=self._cleanup_report(cancelled=True)
        )
        rc, out, _, _ = self._run(["--cleanup-defaults", "--force"],
                                  cleanup=cleanup)
        self.assertEqual(rc, 0)
        self.assertIn("cancelled", out)

    def test_cleanup_confirmation_required_exits_two(self) -> None:
        from yate.services.user_setup import ConfirmationRequiredError

        cleanup = MagicMock(side_effect=ConfirmationRequiredError("non-tty"))
        rc, out, _, _ = self._run(["--cleanup-defaults"], cleanup=cleanup)
        self.assertEqual(rc, 2)
        self.assertIn("non-tty", out)


if __name__ == "__main__":
    unittest.main()
