"""Runtime display of the bundled changelog: loader, editor wiring, commands.

Covers ``load_changelog_markdown`` / ``load_doc_markdown`` (degradation,
language fallback), the ``Editor`` overlay wiring (``show_changelog`` /
``show_manual`` push guards) and the ``:changelog`` command registration.
"""

# pyright: reportPrivateUsage=false, reportArgumentType=false

from __future__ import annotations

from typing import Any, cast

import pytest

from yate.editor import Editor
from yate.editor_view.manual import (
    MarkdownDocScreen,
    load_changelog_markdown,
    load_doc_markdown,
    load_manual_markdown,
)
from yate.registries import CommandRegistry


class _FakeScreen:
    """Stand-in for whatever screen the app currently shows."""


class _FakePromptBar:
    """Minimal PromptBar stand-in: Editor.push_overlay idles it."""

    def idle(self) -> None:
        pass


class _FakeApp:
    """Enough app surface for Editor._open_doc: screen + push_screen."""

    def __init__(self, *, screen: object | None = None):
        self.screen: object = _FakeScreen() if screen is None else screen
        self.theme = "yate-mocha"
        self.pushed: list[tuple[MarkdownDocScreen, object]] = []

    def push_screen(
        self, screen: MarkdownDocScreen, callback: object = None
    ) -> None:
        self.pushed.append((screen, callback))


def _make_editor(app: _FakeApp, *, mounted: bool = True) -> Editor:
    """An Editor bound to *app* without running __init__ (overlay path only)."""
    editor = object.__new__(Editor)
    editor.app = cast(Any, app)
    editor._mounted = mounted
    editor.prompt_bar = cast(Any, _FakePromptBar())
    return editor


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


# --- editor overlay wiring --------------------------------------------------


def test_show_changelog_pushes_doc_screen_without_changing_theme() -> None:
    app = _FakeApp()
    editor = _make_editor(app)
    editor.show_changelog("zh")
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


def test_show_manual_pushes_manual_screen() -> None:
    app = _FakeApp()
    editor = _make_editor(app)
    editor.show_manual("en")
    screen, _callback = app.pushed[0]
    assert isinstance(screen, MarkdownDocScreen)
    assert screen._kind == "manual"
    assert screen._title == "user manual"


def test_not_mounted_does_not_push() -> None:
    app = _FakeApp()
    editor = _make_editor(app, mounted=False)
    editor.show_changelog()
    assert app.pushed == []
    assert app.theme == "yate-mocha"


def test_already_on_doc_screen_does_not_stack() -> None:
    app = _FakeApp(screen=MarkdownDocScreen(kind="manual", lang="en",
                                            title="user manual"))
    editor = _make_editor(app)
    editor.show_changelog()
    assert app.pushed == []


# --- command registration ---------------------------------------------------


def test_changelog_command_registered() -> None:
    from yate.commands import register_commands

    registry = CommandRegistry()
    forwarded: list[str] = []

    class StubEditor:
        @staticmethod
        def show_changelog(lang: str = "en") -> None:
            forwarded.append(lang)

    register_commands(registry, cast(Any, StubEditor()))
    assert "changelog" in registry.names()
    entry = registry.get("changelog")
    assert entry is not None
    assert "changelog" in entry[1]
    entry[0]("zh")
    assert forwarded == ["zh"]
