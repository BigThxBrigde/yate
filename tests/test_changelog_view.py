"""Runtime display of the bundled changelog: loader, wiring, commands.

Covers ``load_changelog_markdown`` / ``load_doc_markdown`` (degradation,
language fallback), the ``app_features.docs`` wiring (overlay push guards),
the app facade delegation and the ``:changelog`` command registration.
"""

# pyright: reportPrivateUsage=false, reportArgumentType=false

from __future__ import annotations

from typing import Any

import pytest
from unittest.mock import patch

from yate.app_features.commands import CommandRegistry
from yate.app_features.docs import DocsFeature
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
        self.theme = "yate-mocha"
        self.pushed: list[tuple[MarkdownDocScreen, object]] = []

    def push_overlay(
        self, screen: MarkdownDocScreen, callback: object = None
    ) -> None:
        self.pushed.append((screen, callback))


class _Missing:
    """Resource stand-in where nothing exists."""

    def is_file(self) -> bool:
        return False

    def read_text(self, encoding: str = "utf-8") -> str:
        raise FileNotFoundError("changelog.<lang>.md")


class _MissingFiles:
    def joinpath(self, *_parts: str) -> Any:
        return _Missing()


def _fake_files(*_parts: str) -> Any:
    """Callable stand-in for importlib.resources.files()."""
    return _MissingFiles()


# --- markdown loaders -------------------------------------------------------


def test_changelog_resources_are_bundled() -> None:
    en = load_changelog_markdown("en")
    zh = load_changelog_markdown("zh")
    assert en.startswith("# Changelog")
    assert zh.startswith("# 变更日志")
    # shipped copies are end-user documents: no maintainer wording
    assert "do not edit" not in en
    assert "请勿手工编辑" not in zh


def test_unknown_lang_falls_back_to_en() -> None:
    assert load_changelog_markdown("fr") == load_changelog_markdown("en")


@pytest.mark.parametrize(
    "lang,expected",
    [
        pytest.param("en", "No changelog is shipped", id="en"),
        pytest.param("zh", "此构建未包含变更日志", id="zh"),
    ],
)
def test_missing_changelog_resource_returns_placeholder_without_raising(
    lang: str, expected: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("yate.editor_view.manual.files", _fake_files)
    assert expected in load_changelog_markdown(lang)


def test_missing_manual_resource_returns_placeholder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("yate.editor_view.manual.files", _fake_files)
    assert "No manual" in load_doc_markdown("manual", "en")


def test_load_manual_markdown_keeps_behaviour() -> None:
    # thin wrapper: identical output to the generalized loader
    for lang in ("en", "zh"):
        assert load_manual_markdown(lang) == load_doc_markdown("manual", lang)


# --- docs wiring ------------------------------------------------------------


def test_show_changelog_pushes_doc_screen_without_changing_theme() -> None:
    app = _FakeApp()
    DocsFeature(app).show_changelog("zh")
    assert len(app.pushed) == 1
    screen, callback = app.pushed[0]
    assert isinstance(screen, MarkdownDocScreen)
    assert screen._kind == "changelog"
    assert screen._lang == "zh"
    assert screen._title == "changelog"
    # the viewer follows the active theme via the Textual bridge, so no
    # theme switch happens on push and no restore callback is installed
    assert callback is None
    assert app.theme == "yate-mocha"


def test_show_manual_keeps_facade_contract() -> None:
    app = _FakeApp()
    DocsFeature(app).show_manual("en")
    screen, _callback = app.pushed[0]
    assert isinstance(screen, MarkdownDocScreen)
    assert screen._kind == "manual"
    assert screen._title == "user manual"


def test_not_mounted_does_not_push() -> None:
    app = _FakeApp(mounted=False)
    DocsFeature(app).show_changelog()
    assert app.pushed == []
    assert app.theme == "yate-mocha"


def test_already_on_doc_screen_does_not_stack() -> None:
    app = _FakeApp(screen=MarkdownDocScreen(kind="manual", lang="en",
                                            title="user manual"))
    DocsFeature(app).show_changelog()
    assert app.pushed == []


# --- app facade delegation --------------------------------------------------


def test_app_facade_forwards_to_docs() -> None:
    from yate.app import YateApp

    app = object.__new__(YateApp)
    app.docs_feature = DocsFeature(app)  # type: ignore[arg-type]
    with patch.object(DocsFeature, "show_manual") as show_manual, \
            patch.object(DocsFeature, "show_changelog") as show_changelog:
        app.show_manual("zh")
        app.show_changelog("zh")
    show_manual.assert_called_once()
    show_changelog.assert_called_once()


# --- command registration ---------------------------------------------------


def test_changelog_command_registered() -> None:
    from yate.app_features.commands import register_commands

    registry = CommandRegistry()
    forwarded: list[str] = []

    class StubApp:
        commands = registry

        @staticmethod
        def show_changelog(lang: str = "en") -> None:
            forwarded.append(lang)

    register_commands(StubApp())  # type: ignore[arg-type]
    assert "changelog" in registry.names()
    entry = registry.get("changelog")
    assert entry is not None
    assert "changelog" in entry[1]
    entry[0]("zh")
    assert forwarded == ["zh"]
