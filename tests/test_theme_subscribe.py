"""Tests for theme change subscription (widgets own their theme painting)."""

from __future__ import annotations

import asyncio

from collections.abc import Callable
from typing import cast

from textual.color import Color
from textual.content import Content

from yate.editor_view import theme
from yate.editor_view.commandline import OWNER_LSP, PromptBar


def _message_content(bar: PromptBar) -> Content:
    """The prompt bar's message line as Textual ``Content`` (typed for pyright)."""
    return cast(Content, bar.message.render())


def test_subscribe_listener_notified_on_set_theme() -> None:
    """A subscribed listener runs after every successful set_theme."""
    calls: list[str] = []
    unsubscribe: Callable[[], None] = theme.subscribe(lambda: calls.append("hit"))
    try:
        theme.set_theme("latte")
        theme.set_theme("mocha")
        assert calls == ["hit", "hit"]
    finally:
        unsubscribe()
        theme.set_theme("mocha")


def test_unsubscribe_stops_notifications_and_is_idempotent() -> None:
    """After unsubscribing (twice) the listener is never called again."""
    calls: list[str] = []
    hit = lambda: calls.append("hit")  # noqa: E731 - trivial test double
    unsubscribe = theme.subscribe(hit)
    unsubscribe()
    unsubscribe()  # second removal must be a no-op, not ValueError
    try:
        theme.set_theme("latte")
        assert calls == []
    finally:
        theme.set_theme("mocha")


def test_failing_listener_does_not_block_broadcast() -> None:
    """A raising subscriber is isolated; later subscribers still run."""
    calls: list[str] = []

    def bad() -> None:
        raise RuntimeError("boom")

    unsubscribe_bad = theme.subscribe(bad)
    unsubscribe_good = theme.subscribe(lambda: calls.append("after"))
    try:
        theme.set_theme("latte")
        assert calls == ["after"]
    finally:
        unsubscribe_bad()
        unsubscribe_good()
        theme.set_theme("mocha")


def test_failed_set_theme_does_not_notify() -> None:
    """An unknown theme raises KeyError without touching subscribers."""
    calls: list[str] = []
    unsubscribe = theme.subscribe(lambda: calls.append("hit"))
    try:
        try:
            theme.set_theme("no-such-theme")
        except KeyError:
            pass
        else:
            raise AssertionError("set_theme must raise KeyError for unknown names")
        assert calls == []
    finally:
        unsubscribe()


def test_terminal_panel_follows_theme_change() -> None:
    """A theme switch repaints the terminal dock's header and view."""
    from yate.app import YateApp

    async def _scenario() -> None:
        app = YateApp()
        async with app.run_test(size=(80, 24)):
            panel = app.editor.terminal_panel
            theme.set_theme("latte")
            t = theme.active()
            assert panel.header.styles.background == Color.parse(t.panel)
            assert panel.header.styles.color == Color.parse(t.fg_dim)
            assert panel.view.styles.background == Color.parse(t.bg)

    try:
        asyncio.run(_scenario())
    finally:
        theme.set_theme("mocha")


def test_terminal_panel_unsubscribes_on_unmount() -> None:
    """Unmounting the dock detaches it from the broadcast (no more repaints)."""
    from yate.app import YateApp

    async def _scenario() -> None:
        app = YateApp()
        async with app.run_test(size=(80, 24)):
            panel = app.editor.terminal_panel
            theme.set_theme("latte")
            await panel.remove()  # explicit unmount, not app-shutdown driven
        header_bg = panel.header.styles.background
        theme.set_theme("mocha")
        # unmounted: the broadcast must no longer touch the dock
        assert panel.header.styles.background == header_bg

    asyncio.run(_scenario())


def test_promptbar_prompt_color_follows_theme_change() -> None:
    """An open prompt's prefix color is re-derived on a theme switch."""
    from yate.app import YateApp

    async def _scenario() -> None:
        app = YateApp()
        async with app.run_test(size=(80, 24)):
            bar = app.editor.prompt_bar
            assert bar.activate("find") is True
            theme.set_theme("latte")
            t = theme.active()
            assert bar.prompt.styles.color == Color.parse(t.accent)
            assert bar.active_mode == "find"  # prompt state untouched

    try:
        asyncio.run(_scenario())
    finally:
        theme.set_theme("mocha")


def test_promptbar_message_rerendered_on_theme_change() -> None:
    """A shown message is re-rendered with the new palette's color."""
    from yate.app import YateApp

    async def _scenario() -> None:
        app = YateApp()
        async with app.run_test(size=(80, 24)):
            bar = app.editor.prompt_bar
            bar.write("hello", kind="warn")
            assert "#f9e2af" in _message_content(bar).markup  # mocha yellow
            theme.set_theme("latte")
            markup = _message_content(bar).markup
            assert "#df8e1d" in markup  # latte yellow after the switch
            assert "hello" in markup

    try:
        asyncio.run(_scenario())
    finally:
        theme.set_theme("mocha")


def test_promptbar_message_owner_survives_theme_change() -> None:
    """Re-rendering a message never disturbs its ``owner`` semantics."""
    from yate.app import YateApp

    async def _scenario() -> None:
        app = YateApp()
        async with app.run_test(size=(80, 24)):
            bar = app.editor.prompt_bar
            bar.write("diag", kind="info", owner=OWNER_LSP)
            theme.set_theme("latte")
            assert bar.owner == OWNER_LSP
            assert "diag" in _message_content(bar).plain
            assert bar.message.display is True

    try:
        asyncio.run(_scenario())
    finally:
        theme.set_theme("mocha")
