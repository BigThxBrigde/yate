"""Runtime evidence that zero-argument callbacks are still dispatched.

These tests pin the framework contract used by the unused-symbol cleanup:
Textual's ``invoke_watcher`` and ``_invoke`` support 0/1/2-parameter
callbacks, so removing the unused ``_theme`` parameter from
``YateApp.watch_theme`` must keep theme-change repaints working.
"""

from __future__ import annotations

import asyncio
from typing import override

from textual.app import App, ComposeResult
from textual.color import Color
from textual.reactive import reactive
from textual.widgets import Static

from conftest import wait_until

from yate.app import YateApp
from yate.editor_components import theme as yate_theme


def test_zero_arg_watcher_fires_on_reactive_change() -> None:
    """A 0-arg ``watch_*`` method fires on construction and on assignment."""

    class WatcherApp(App[None]):
        marker: reactive[str] = reactive("before")

        def __init__(self) -> None:
            super().__init__()
            self.watch_calls: list[str] = []

        @override
        def compose(self) -> ComposeResult:
            yield Static("hello")

        def watch_marker(self) -> None:
            self.watch_calls.append("fired")

    async def scenario() -> None:
        app = WatcherApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            app.marker = "after"
            await pilot.pause()
        assert app.watch_calls == ["fired", "fired"]

    asyncio.run(scenario())


def test_zero_arg_resize_handler_is_invoked_by_framework() -> None:
    """A 0-arg ``on_resize`` handler is called with the event argument trimmed."""

    class ResizeWidget(Static):
        def __init__(self) -> None:
            super().__init__("resize me")
            self.resize_calls: int = 0

        def on_resize(self) -> None:
            self.resize_calls += 1

    class ResizeApp(App[None]):
        @override
        def compose(self) -> ComposeResult:
            yield ResizeWidget()

    async def scenario() -> None:
        app = ResizeApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            widget = app.query_one(ResizeWidget)
            baseline: int = widget.resize_calls
            await pilot.resize_terminal(120, 40)
            # Repaint is asynchronous under a loaded worker pool; poll the
            # predicate instead of asserting on a single frame.
            assert await wait_until(
                pilot, lambda: widget.resize_calls > baseline
            )

    asyncio.run(scenario())


def test_yate_app_watch_theme_repaints_on_theme_change() -> None:
    """The trimmed ``YateApp.watch_theme`` still repaints on theme switch."""

    async def scenario() -> None:
        app = YateApp()
        try:
            async with app.run_test(size=(100, 30)) as pilot:
                await pilot.pause()
                before: Color = app.screen.styles.background
                app.editor.run_command("set theme=latte")
                await pilot.pause()
                await pilot.pause()
                after: Color = app.screen.styles.background
                assert after == Color.parse(yate_theme.active().bg)
                assert after != before
        finally:
            # restore the default theme even on failure so the state never
            # leaks into later theme-sensitive tests
            yate_theme.set_theme("mocha")

    asyncio.run(scenario())
