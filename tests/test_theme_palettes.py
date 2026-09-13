# pyright: reportPrivateUsage=false
"""Tests for the built-in theme palettes and the shipped theme templates.

Covers:

* every built-in theme (8): complete fields, hex format, registry/name
  consistency, syntax colors for every token kind;
* ``set_theme`` switching and the unknown-theme error listing all built-ins;
* the ``*.example`` templates under ``yate/resources/theme_examples``:
  they exec under exactly the namespace the real loader injects, register the
  advertised themes, are ignored in place (glob ``*.py``), and work end to
  end once copied to ``*.py`` inside a scanned directory;
* the version bump (single-source dynamic version).
"""

from __future__ import annotations

import re
import shutil
import tempfile
import unittest
from dataclasses import fields
from importlib.resources import files
from pathlib import Path

import yate
from yate.editor_syntax.tokens import SYNTAX_KINDS
from yate.editor_view import theme
from yate.editor_view.theme import (
    DEFAULT_THEME,
    THEMES,
    Theme,
    load_theme_paths,
    set_theme,
)

HEX = re.compile(r"^#[0-9a-fA-F]{6}$")

BUILTIN_THEMES = [
    "frappe",
    "gruvbox-dark",
    "gruvbox-light",
    "latte",
    "macchiato",
    "mocha",
    "onedark",
    "onelight",
]
_BUILTIN_THEME_SET = set(BUILTIN_THEMES)

TEMPLATE_FILES = ["dracula_theme.example", "ayu_theme.example"]
TEMPLATE_THEMES = ["dracula", "ayu-dark", "ayu-mirage", "ayu-light"]

#: Theme fields that must hold a hex color (everything except identity/extra).
COLOR_FIELDS = [
    f.name
    for f in fields(Theme)
    if f.name not in ("name", "label", "dark", "extra")
]


def _examples_dir() -> Path:
    resource = files("yate.resources").joinpath("theme_examples")
    return Path(str(resource))


def _assert_well_formed(testcase: unittest.TestCase, t: Theme) -> None:
    """All color fields populated with valid hex and types correct."""
    testcase.assertIsInstance(t.dark, bool)
    testcase.assertIsInstance(t.name, str)
    testcase.assertTrue(t.label)
    for field_name in COLOR_FIELDS:
        value = getattr(t, field_name)
        testcase.assertIsInstance(value, str, field_name)
        testcase.assertRegex(value, HEX, f"{t.name}.{field_name}={value!r}")


class BuiltinThemeTests(unittest.TestCase):
    def setUp(self) -> None:
        # The registry is process-global; other test modules may register
        # throwaway themes, so pin the built-in baseline for these tests and
        # restore whatever was registered afterwards.
        self._extra = {
            name: THEMES.pop(name)
            for name in list(THEMES)
            if name not in _BUILTIN_THEME_SET
        }
        self.addCleanup(self._extra.clear)
        self.addCleanup(THEMES.update, self._extra)
        self.addCleanup(set_theme, DEFAULT_THEME)

    def test_registry_has_exactly_eight_builtin_themes(self) -> None:
        self.assertEqual(sorted(THEMES), BUILTIN_THEMES)

    def test_default_theme_is_registered(self) -> None:
        self.assertEqual(DEFAULT_THEME, "mocha")
        self.assertIn(DEFAULT_THEME, THEMES)

    def test_every_builtin_theme_is_well_formed(self) -> None:
        for name in BUILTIN_THEMES:
            t = THEMES[name]
            self.assertEqual(t.name, name)
            _assert_well_formed(self, t)

    def test_syntax_colors_cover_every_token_kind(self) -> None:
        for name in BUILTIN_THEMES:
            t = THEMES[name]
            for kind in SYNTAX_KINDS:
                color = t.syntax_color(kind)
                assert color is not None, f"{name}: no color for {kind}"
                self.assertRegex(color, HEX, f"{name}.{kind}={color!r}")

    def test_comments_render_italic_in_their_own_color(self) -> None:
        from rich.color import Color

        for name in BUILTIN_THEMES:
            t = THEMES[name]
            style = t.syntax_style("comment")
            self.assertTrue(style.italic, name)
            color = style.color
            assert color is not None, name
            self.assertEqual(
                color.triplet, Color.parse(t.syn_comment).triplet, name
            )

    def test_set_theme_switches_and_unknown_theme_lists_builtins(self) -> None:
        self.addCleanup(set_theme, DEFAULT_THEME)
        self.assertIs(set_theme("onedark"), THEMES["onedark"])
        self.assertIs(theme.active(), THEMES["onedark"])
        with self.assertRaises(KeyError) as ctx:
            set_theme("no-such-theme")
        message = str(ctx.exception)
        for name in BUILTIN_THEMES:
            self.assertIn(name, message)


class ThemeTemplateFileTests(unittest.TestCase):
    def setUp(self) -> None:
        # Templates register through the real global registry; remove whatever
        # they add after each test so process state stays clean.
        self.addCleanup(self._drop_template_themes)

    def _drop_template_themes(self) -> None:
        for name in TEMPLATE_THEMES:
            THEMES.pop(name, None)
        set_theme(DEFAULT_THEME)

    def test_template_files_are_shipped(self) -> None:
        directory = _examples_dir()
        for filename in TEMPLATE_FILES:
            path = directory / filename
            self.assertTrue(path.is_file(), path)
            text = path.read_text(encoding="utf-8")  # UTF-8, not bytes
            self.assertIn("register_theme(", text)
            self.assertIn("Theme(", text)
            # Templates must rely solely on the injected namespace: match
            # actual import statements (the prose comments mention yate).
            self.assertIsNone(
                re.search(r"(?m)^\s*(?:from\s+yate|import\s+yate)\b", text)
            )

    def test_templates_exec_under_the_loader_namespace(self) -> None:
        directory = _examples_dir()
        registered: dict[str, Theme] = {}

        def capture(t: Theme) -> None:
            registered[t.name] = t

        # Same globals the real loader injects (load_theme_file), with the
        # registering function swapped for a capturing one.
        namespace = theme._theme_namespace()
        namespace["register_theme"] = capture
        for filename in TEMPLATE_FILES:
            exec(
                compile(
                    (directory / filename).read_text(encoding="utf-8"),
                    filename,
                    "exec",
                ),
                namespace,
            )
        self.assertEqual(set(registered), set(TEMPLATE_THEMES))
        for name, t in registered.items():
            self.assertEqual(t.name, name)
            _assert_well_formed(self, t)
            for kind in SYNTAX_KINDS:
                syn = t.syntax_color(kind)
                assert syn is not None, f"{name}: no color for {kind}"
                self.assertRegex(syn, HEX)

    def test_templates_are_inert_inside_their_resource_directory(self) -> None:
        # The loader globs *.py only; *.example files must never register,
        # even when their own directory is scanned directly.
        before = sorted(THEMES)
        errors: list[str] = []
        load_theme_paths([_examples_dir()], errors)
        self.assertEqual(errors, [])
        self.assertEqual(sorted(THEMES), before)
        for name in TEMPLATE_THEMES:
            self.assertNotIn(name, THEMES)

    def test_templates_load_end_to_end_after_copy_as_py(self) -> None:
        directory = _examples_dir()
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            shutil.copyfile(
                directory / "dracula_theme.example", tmpdir / "dracula.py"
            )
            shutil.copyfile(
                directory / "ayu_theme.example", tmpdir / "ayu.py"
            )
            errors: list[str] = []
            load_theme_paths([tmpdir], errors)
            self.assertEqual(errors, [])
            for name in TEMPLATE_THEMES:
                self.assertIn(name, THEMES)
                self.assertEqual(THEMES[name].name, name)

    def test_non_py_suffixes_are_not_loaded(self) -> None:
        directory = _examples_dir()
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            shutil.copyfile(
                directory / "dracula_theme.example", tmpdir / "dracula.txt"
            )
            shutil.copyfile(
                directory / "ayu_theme.example", tmpdir / "ayu.theme"
            )
            errors: list[str] = []
            load_theme_paths([tmpdir], errors)
            self.assertEqual(errors, [])
            for name in TEMPLATE_THEMES:
                self.assertNotIn(name, THEMES)

    def test_real_register_theme_via_template_source(self) -> None:
        # Executing with the unmodified loader namespace registers globally,
        # exactly as it does for a user-copied *.py file.
        directory = _examples_dir()
        source = (directory / "dracula_theme.example").read_text(encoding="utf-8")
        exec(compile(source, "dracula_theme.example", "exec"),
             theme._theme_namespace())
        self.assertIn("dracula", THEMES)
        self.assertEqual(THEMES["dracula"].label, "Dracula")
        self.assertTrue(THEMES["dracula"].dark)


class VersionTests(unittest.TestCase):
    def test_version_is_bumped(self) -> None:
        self.assertEqual(yate.__version__, "0.2.0")

    def test_pyproject_keeps_the_single_dynamic_version_source(self) -> None:
        pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
        text = pyproject.read_text(encoding="utf-8")
        self.assertIn('dynamic = ["version"]', text)
        self.assertIn('path = "yate/__init__.py"', text)
        # No static version = line: the package __version__ is the only source.
        self.assertNotRegex(text, r"(?m)^version\s*=")


if __name__ == "__main__":
    unittest.main()
