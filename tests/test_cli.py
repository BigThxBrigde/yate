"""Headless tests for the command line entry point (yate.cli).

Argument parsing plus the pre-TUI startup path (config + custom theme
loading).  Launching the real TUI needs a terminal, so ``main()`` is run
with ``yate.app.YateApp`` replaced by a fake that records its kwargs and
never enters Textual.
"""

from __future__ import annotations

import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

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

    def __init__(self, **kwargs: object) -> None:
        type(self).last_kwargs = kwargs

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


class CliThemeStartupTests(unittest.TestCase):
    """main() auto-loads --theme-dir entries and forwards --theme."""

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


if __name__ == "__main__":
    unittest.main()
