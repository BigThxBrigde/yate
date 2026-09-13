"""Runtime display of the bundled changelog: loader, wiring, commands.

Covers ``load_changelog_markdown`` / ``load_doc_markdown`` (degradation,
language fallback), the ``app_features.docs`` wiring (overlay push guards,
theme switch/restore), the app facade delegation and the ``:changelog``
command registration.
"""

# pyright: reportPrivateUsage=false, reportArgumentType=false

from __future__ import annotations

import unittest
from unittest.mock import patch

from yate.app_features import docs
from yate.app_features.commands import CommandRegistry
from yate.editor_view.manual import (
    MarkdownDocScreen,
    load_changelog_markdown,
    load_doc_markdown,
    load_manual_markdown,
)


class _FakeScreen:
    """Stand-in for whatever screen the app currently shows."""


class _FakeApp:
    """Enough app surface for docs.show_doc: guards, theme, overlays."""

    def __init__(self, *, mounted: bool = True, screen: object | None = None):
        self.mounted = mounted
        self.screen: object = _FakeScreen() if screen is None else screen
        self.theme = "textual-dark"
        self._prev_doc_theme: str | None = None
        self.pushed: list[tuple[MarkdownDocScreen, object]] = []

    def _push_overlay(
        self, screen: MarkdownDocScreen, callback: object = None
    ) -> None:
        self.pushed.append((screen, callback))


class LoadDocMarkdownTests(unittest.TestCase):
    def test_changelog_resources_are_bundled(self) -> None:
        en = load_changelog_markdown("en")
        zh = load_changelog_markdown("zh")
        self.assertTrue(en.startswith("# Changelog"))
        self.assertTrue(zh.startswith("# 变更日志"))
        # shipped copies are end-user documents: no maintainer wording
        self.assertNotIn("do not edit", en)
        self.assertNotIn("请勿手工编辑", zh)

    def test_unknown_lang_falls_back_to_en(self) -> None:
        self.assertEqual(load_changelog_markdown("fr"),
                         load_changelog_markdown("en"))

    def test_missing_resource_returns_placeholder_without_raising(self) -> None:
        from typing import Any

        class _Missing:
            """Resource stand-in where nothing exists."""

            def is_file(self) -> bool:
                return False

            def read_text(self, encoding: str = "utf-8") -> str:
                raise FileNotFoundError("changelog.<lang>.md")

        class _MissingFiles:
            def joinpath(self, *_parts: str) -> Any:
                return _Missing()

        with patch("yate.editor_view.manual.files", return_value=_MissingFiles()):
            for lang in ("en", "zh"):
                with self.subTest(lang=lang):
                    text = load_changelog_markdown(lang)
                    expected = (
                        "No changelog is shipped" if lang == "en"
                        else "此构建未包含变更日志"
                    )
                    self.assertIn(expected, text)
            self.assertIn("No manual", load_doc_markdown("manual", "en"))

    def test_load_manual_markdown_keeps_behaviour(self) -> None:
        # thin wrapper: identical output to the generalized loader
        for lang in ("en", "zh"):
            with self.subTest(lang=lang):
                self.assertEqual(
                    load_manual_markdown(lang), load_doc_markdown("manual", lang)
                )


class DocsWiringTests(unittest.TestCase):
    def test_show_changelog_pushes_doc_screen_and_switches_theme(self) -> None:
        app = _FakeApp()
        docs.show_changelog(app, "zh")
        self.assertEqual(len(app.pushed), 1)
        screen, callback = app.pushed[0]
        self.assertIsInstance(screen, MarkdownDocScreen)
        self.assertEqual(screen._kind, "changelog")
        self.assertEqual(screen._lang, "zh")
        self.assertEqual(screen._title, "changelog")
        # theme switched before the push, restored by the close callback
        self.assertEqual(app.theme, "catppuccin-mocha")
        assert callable(callback)
        callback(None)
        self.assertEqual(app.theme, "textual-dark")
        self.assertIsNone(app._prev_doc_theme)

    def test_show_manual_keeps_facade_contract(self) -> None:
        app = _FakeApp()
        docs.show_manual(app, "en")
        screen, _callback = app.pushed[0]
        self.assertIsInstance(screen, MarkdownDocScreen)
        self.assertEqual(screen._kind, "manual")
        self.assertEqual(screen._title, "user manual")

    def test_not_mounted_does_not_push(self) -> None:
        app = _FakeApp(mounted=False)
        docs.show_changelog(app)
        self.assertEqual(app.pushed, [])
        self.assertEqual(app.theme, "textual-dark")

    def test_already_on_doc_screen_does_not_stack(self) -> None:
        app = _FakeApp(screen=MarkdownDocScreen(None, kind="manual", lang="en",
                                               title="user manual"))
        docs.show_changelog(app)
        self.assertEqual(app.pushed, [])


class FacadeDelegationTests(unittest.TestCase):
    def test_app_facade_forwards_to_docs(self) -> None:
        from yate.app import YateApp

        with patch.object(docs, "show_manual") as show_manual, \
                patch.object(docs, "show_changelog") as show_changelog:
            YateApp.show_manual(object.__new__(YateApp), "zh")  # type: ignore[arg-type]
            YateApp.show_changelog(object.__new__(YateApp), "zh")  # type: ignore[arg-type]
        show_manual.assert_called_once()
        show_changelog.assert_called_once()


class CommandRegistrationTests(unittest.TestCase):
    def test_changelog_command_registered(self) -> None:
        from yate.app_features.commands import register_commands

        registry = CommandRegistry()
        forwarded: list[str] = []

        class StubApp:
            commands = registry

            @staticmethod
            def show_changelog(lang: str = "en") -> None:
                forwarded.append(lang)

        register_commands(StubApp())  # type: ignore[arg-type]
        self.assertIn("changelog", registry.names())
        entry = registry.get("changelog")
        assert entry is not None
        self.assertIn("changelog", entry[1])
        entry[0]("zh")
        self.assertEqual(forwarded, ["zh"])


if __name__ == "__main__":
    unittest.main()
