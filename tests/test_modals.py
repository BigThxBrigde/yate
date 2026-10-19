"""Tests for yate.editor_view.modals (overlay screens and their scrollbar).

Both overlay screens -- the F1 help reference and the shell-command output --
share ``_OverlayScreen``, whose scrolling body is ``_OverlayScroll``.  These
guards pin the three parts of the explorer's scrollbar look on every overlay:
the slim renderer (sliver thumb), the theme thumb color and the fully
transparent track.  A regression to a bare ``VerticalScroll`` would restore
Textual's opaque track and full-cell bright-magenta thumb.
"""

from __future__ import annotations

import asyncio

from yate.editor_view import theme
from yate.editor_view.modals import HelpScreen, OutputScreen
from yate.editor_view.scrollbars import SlimScrollBarRender


def _assert_slim_scrollbar_overlay(screen: HelpScreen | OutputScreen) -> None:
    """Assert *screen*'s ``#overlay`` scrollbar carries the slim painting."""
    overlay = screen.query_one("#overlay")
    assert overlay.vertical_scrollbar.renderer is SlimScrollBarRender
    styles = overlay.styles
    assert styles.scrollbar_color is not None
    assert styles.scrollbar_color.hex.lower() == theme.active().border.lower()
    assert styles.scrollbar_background is not None
    assert styles.scrollbar_background.a == 0


def test_help_screen_overlay_scrollbar_uses_slim_renderer() -> None:
    """F1 help paints the slim thumb in the theme color over a clear track."""
    from yate.app import YateApp

    async def _scenario() -> None:
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.press("f1")
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, HelpScreen)
            _assert_slim_scrollbar_overlay(screen)

    asyncio.run(_scenario())


def test_output_screen_overlay_scrollbar_matches_explorer_palette() -> None:
    """The command-output overlay shares the base-class scrollbar painting."""
    from yate.app import YateApp

    async def _scenario() -> None:
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            app.push_screen(OutputScreen("echo hi", "hi\n", 0))
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, OutputScreen)
            _assert_slim_scrollbar_overlay(screen)

    asyncio.run(_scenario())
