"""Tests for the yaterc configuration system (yate.config)."""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from yate import config as cfg
from yate.editor_view import theme as themes


def _write(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


class ConfigDefaultsTests(unittest.TestCase):
    def test_builtin_defaults(self) -> None:
        config = cfg.YateConfig()
        self.assertEqual(config.keymap, "vsc")
        self.assertEqual(config.theme, "mocha")
        self.assertEqual(config.tab_width, 4)
        self.assertTrue(config.use_spaces)
        self.assertEqual(config.sources, [])
        self.assertEqual(config.errors, [])

    def test_load_no_files_returns_defaults(self) -> None:
        config = cfg.load_config([])
        self.assertEqual(config.keymap, "vsc")
        self.assertEqual(config.tab_width, 4)
        self.assertEqual(config.sources, [])


class ConfigLoadTests(unittest.TestCase):
    def test_loads_all_options(self) -> None:
        with TemporaryDirectory() as tmp:
            rc = _write(
                Path(tmp) / "yaterc",
                'keymap = "vim"\n'
                'theme = "latte"\n'
                "tab_width = 2\n"
                "use_spaces = False\n",
            )
            config = cfg.load_config([rc])
            self.assertEqual(config.keymap, "vim")
            self.assertEqual(config.theme, "latte")
            self.assertEqual(config.tab_width, 2)
            self.assertFalse(config.use_spaces)
            self.assertEqual(config.sources, [rc])
            self.assertEqual(config.errors, [])

    def test_partial_options_keep_other_defaults(self) -> None:
        with TemporaryDirectory() as tmp:
            rc = _write(Path(tmp) / "yaterc", "tab_width = 8\n")
            config = cfg.load_config([rc])
            self.assertEqual(config.tab_width, 8)
            self.assertEqual(config.keymap, "vsc")
            self.assertTrue(config.use_spaces)

    def test_unknown_options_are_ignored(self) -> None:
        with TemporaryDirectory() as tmp:
            rc = _write(
                Path(tmp) / "yaterc",
                "some_future_option = 99\n"
                "def helper():\n    return 1\n",
            )
            config = cfg.load_config([rc])
            self.assertEqual(config.errors, [])
            self.assertEqual(config.tab_width, 4)

    def test_project_rc_overrides_user_rc(self) -> None:
        with TemporaryDirectory() as tmp:
            user = _write(Path(tmp) / "user_yaterc", 'keymap = "vsc"\ntab_width = 2\n')
            project = _write(Path(tmp) / "project_yaterc", "tab_width = 8\n")
            config = cfg.load_config([user, project])
            # later file wins; earlier values survive where not overridden
            self.assertEqual(config.tab_width, 8)
            self.assertEqual(config.keymap, "vsc")
            self.assertEqual(config.sources, [user, project])

    def test_missing_file_is_an_error(self) -> None:
        config = cfg.load_config([Path("/nonexistent/yaterc")])
        self.assertEqual(len(config.errors), 1)
        self.assertEqual(config.sources, [])
        self.assertEqual(config.tab_width, 4)

    def test_runtime_error_in_rc_is_caught(self) -> None:
        with TemporaryDirectory() as tmp:
            bad = _write(Path(tmp) / "bad", 'raise RuntimeError("boom")\n')
            good = _write(Path(tmp) / "good", "tab_width = 3\n")
            config = cfg.load_config([bad, good])
            self.assertTrue(any("boom" in e for e in config.errors))
            # later files still load
            self.assertEqual(config.tab_width, 3)
            self.assertEqual(config.sources, [good])

    def test_syntax_error_in_rc_is_caught(self) -> None:
        with TemporaryDirectory() as tmp:
            bad = _write(Path(tmp) / "bad", "keymap = \n")
            config = cfg.load_config([bad])
            self.assertEqual(len(config.errors), 1)
            self.assertEqual(config.keymap, "vsc")


class ConfigValidationTests(unittest.TestCase):
    def _load(self, body: str) -> cfg.YateConfig:
        with TemporaryDirectory() as tmp:
            rc = _write(Path(tmp) / "yaterc", body)
            return cfg.load_config([rc])

    def test_invalid_keymap(self) -> None:
        config = self._load('keymap = "emacs"\n')
        self.assertEqual(config.keymap, "vsc")
        self.assertTrue(any("keymap" in e for e in config.errors))

    def test_invalid_tab_width_values(self) -> None:
        for value in ('"wide"', "0", "17", "True", "3.5"):
            config = self._load(f"tab_width = {value}\n")
            self.assertEqual(config.tab_width, 4, value)
            self.assertTrue(config.errors, value)

    def test_valid_tab_width_bounds(self) -> None:
        self.assertEqual(self._load("tab_width = 1\n").tab_width, 1)
        self.assertEqual(self._load("tab_width = 16\n").tab_width, 16)

    def test_invalid_use_spaces(self) -> None:
        config = self._load("use_spaces = 1\n")
        self.assertTrue(config.use_spaces)
        self.assertTrue(any("use_spaces" in e for e in config.errors))

    def test_invalid_theme(self) -> None:
        config = self._load("theme = 123\n")
        self.assertTrue(any("theme" in e for e in config.errors))


class ProjectConfigDiscoveryTests(unittest.TestCase):
    def test_find_project_config_walks_up(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            rc = _write(root / "yaterc", "tab_width = 2\n")
            deep = root / "a" / "b" / "c"
            deep.mkdir(parents=True)
            found = cfg.find_project_config(deep)
            self.assertEqual(found, rc)

    def test_find_project_config_none(self) -> None:
        with TemporaryDirectory() as tmp:
            self.assertIsNone(cfg.find_project_config(Path(tmp)))

    def test_find_project_config_from_file_path(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root / "yaterc", 'keymap = "vim"\n')
            file_in_subdir = root / "src" / "main.py"
            (root / "src").mkdir()
            file_in_subdir.write_text("", encoding="utf-8")
            found = cfg.find_project_config(file_in_subdir)
            self.assertEqual(found, root / "yaterc")

    def test_default_rc_paths_user_then_project(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            user_rc = root / "user_yaterc"
            _write(user_rc, "")
            project_rc = _write(root / "yaterc", "")
            with patch("yate.config.user_config_path", return_value=user_rc):
                paths = cfg.default_rc_paths(root)
            self.assertEqual(paths, [user_rc, project_rc])

    def test_default_rc_paths_dedupes(self) -> None:
        with TemporaryDirectory() as tmp:
            rc = _write(Path(tmp) / "yaterc", "")
            with patch("yate.config.user_config_path", return_value=rc):
                paths = cfg.default_rc_paths(Path(tmp))
            self.assertEqual(paths, [rc])


class ExtensionPathTests(unittest.TestCase):
    def test_relative_paths_resolve_against_rc_dir(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            ext_file = _write(root / "tool.py", "def setup(api):\n    pass\n")
            ext_dir = root / "exts"
            ext_dir.mkdir()
            rc = _write(
                root / "yaterc",
                'extensions = ["tool.py", "exts"]\n',
            )
            config = cfg.load_config([rc])
            self.assertEqual(config.errors, [])
            self.assertEqual(config.extension_paths, [ext_file.resolve(), ext_dir.resolve()])

    def test_extension_accepts_single_string(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            ext_file = _write(root / "tool.py", "def setup(api):\n    pass\n")
            rc = _write(root / "yaterc", 'extensions = "tool.py"\n')
            config = cfg.load_config([rc])
            self.assertEqual(config.extension_paths, [ext_file.resolve()])

    def test_tilde_expanded(self) -> None:
        import os

        with TemporaryDirectory() as tmp:
            home = Path(tmp)
            ext_file = _write(home / "tool.py", "def setup(api):\n    pass\n")
            rc = _write(home / "yaterc", 'extensions = "~/tool.py"\n')
            # expanduser() reads HOME (POSIX) / USERPROFILE (Windows) directly.
            with patch.dict(
                os.environ,
                {"HOME": str(home), "USERPROFILE": str(home)},
            ):
                config = cfg.load_config([rc])
            self.assertEqual(config.errors, [])
            self.assertEqual(config.extension_paths, [ext_file.resolve()])

    def test_nonexistent_path_reported(self) -> None:
        with TemporaryDirectory() as tmp:
            rc = _write(Path(tmp) / "yaterc", 'extensions = ["missing.py"]\n')
            config = cfg.load_config([rc])
            self.assertEqual(config.extension_paths, [])
            self.assertTrue(any("does not exist" in err for err in config.errors))

    def test_bad_types_reported(self) -> None:
        with TemporaryDirectory() as tmp:
            rc = _write(Path(tmp) / "yaterc", "extensions = 42\n")
            config = cfg.load_config([rc])
            self.assertEqual(config.extension_paths, [])
            self.assertTrue(any("extensions" in err for err in config.errors))

            rc2 = _write(Path(tmp) / "yaterc2", 'extensions = ["ok_missing", 7]\n')
            config2 = cfg.load_config([rc2])
            self.assertTrue(any("non-empty strings" in err for err in config2.errors))

    def test_accumulates_across_rc_files_and_dedupes(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            a = _write(root / "a.py", "def setup(api):\n    pass\n")
            b = _write(root / "b.py", "def setup(api):\n    pass\n")
            user_rc = _write(root / "user_rc", 'extensions = ["./a.py"]\n')
            project_rc = _write(
                root / "project_rc",
                'extensions = ["a.py", "b.py"]\n',
            )
            config = cfg.load_config([user_rc, project_rc])
            self.assertEqual(config.errors, [])
            # a.py appears in both rc files but is loaded only once
            self.assertEqual(config.extension_paths, [a.resolve(), b.resolve()])


class ExampleRcTests(unittest.TestCase):
    def test_shipped_example_loads_cleanly(self) -> None:
        example = Path(__file__).parent.parent / "yaterc.example"
        self.assertTrue(example.is_file(), "yaterc.example must ship at repo root")
        config = cfg.load_config([example])
        self.assertEqual(config.errors, [])
        self.assertEqual(config.sources, [example])
        # the example's active options are the documented defaults
        self.assertEqual(config.keymap, "vsc")
        self.assertEqual(config.theme, "mocha")
        self.assertEqual(config.tab_width, 4)
        self.assertTrue(config.use_spaces)


class CustomThemeTests(unittest.TestCase):
    def test_register_theme_from_rc(self) -> None:
        body = (
            "from dataclasses import replace\n"
            "from yate.editor_view.theme import THEMES\n"
            "register_theme(replace(THEMES['mocha'], name='yate_test_theme'))\n"
            'theme = "yate_test_theme"\n'
        )
        with TemporaryDirectory() as tmp:
            rc = _write(Path(tmp) / "yaterc", body)
            config = cfg.load_config([rc])
            self.assertEqual(config.errors, [])
            self.assertEqual(config.theme, "yate_test_theme")
            activated = themes.set_theme("yate_test_theme")
            self.assertEqual(activated.name, "yate_test_theme")
            # mocha palette copied through
            self.assertEqual(activated.bg, themes.THEMES["mocha"].bg)
        themes.set_theme("mocha")  # restore global default


class AppIntegrationTests(unittest.TestCase):
    def test_app_applies_config(self) -> None:
        from yate.app import YateApp

        config = cfg.YateConfig(
            keymap="vim",
            theme="latte",
            tab_width=2,
            use_spaces=False,
        )
        try:
            app = YateApp(config=config)
            self.assertEqual(app.keymap_name, "vim")
            self.assertEqual(themes.active().name, "latte")
            self.assertEqual(app.buffer.tab_width, 2)
            self.assertFalse(app.buffer.use_spaces)
            # buffers created afterwards inherit the options too
            app.new_buffer(show=False)
            self.assertEqual(app.buffer.tab_width, 2)
        finally:
            themes.set_theme("mocha")

    def test_app_unknown_theme_records_error(self) -> None:
        from yate.app import YateApp

        config = cfg.YateConfig(theme="no-such-theme")
        try:
            app = YateApp(config=config)
            self.assertTrue(any("unknown theme" in e for e in app.config.errors))
        finally:
            themes.set_theme("mocha")


if __name__ == "__main__":
    unittest.main()
