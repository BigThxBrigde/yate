"""Pilot tests for the full-terminal screensaver (plan fancy_sym / plan_D)."""

from __future__ import annotations

import asyncio
from pathlib import Path

from yate import config as cfg
from yate.app import YateApp
from yate.editor_view.screensaver import ScreensaverScreen


def _doc(tmp_path: Path) -> Path:
    doc = tmp_path / "note.txt"
    doc.write_text("hello\n", encoding="utf-8")
    return doc


def test_toggle_pushes_and_any_key_pops_without_leaking(tmp_path: Path) -> None:
    """The action opens the screensaver; a key dismisses it, unconsumed.

    The pressed key must not reach the editor: the screen stops it (R10),
    so the buffer text is untouched by whatever key dismissed the show.
    """

    async def scenario() -> None:
        app = YateApp(target=_doc(tmp_path))
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            before = app.editor.session.buffer.get_text()
            app.editor.execute_action("toggle_screensaver")
            await pilot.pause()
            assert isinstance(app.screen, ScreensaverScreen)
            await pilot.press("x")
            await pilot.pause()
            assert not isinstance(app.screen, ScreensaverScreen)
            assert app.editor.session.buffer.get_text() == before

    asyncio.run(scenario())


def test_toggle_twice_returns_to_the_editor(tmp_path: Path) -> None:
    """The registered action toggles: second invocation pops the overlay."""

    async def scenario() -> None:
        app = YateApp(target=_doc(tmp_path))
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            app.editor.execute_action("toggle_screensaver")
            await pilot.pause()
            assert isinstance(app.screen, ScreensaverScreen)
            app.editor.execute_action("toggle_screensaver")
            await pilot.pause()
            assert not isinstance(app.screen, ScreensaverScreen)

    asyncio.run(scenario())


def test_disabled_config_only_reports(tmp_path: Path) -> None:
    """With ``enable = False`` the action reports instead of pushing."""

    async def scenario() -> None:
        rc = tmp_path / "yaterc"
        rc.write_text('screen_saver = {"enable": False}\n', encoding="utf-8")
        config = cfg.load_config([rc])
        app = YateApp(target=_doc(tmp_path), config=config)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            app.editor.execute_action("toggle_screensaver")
            await pilot.pause()
            assert not isinstance(app.screen, ScreensaverScreen)

    asyncio.run(scenario())


def test_unknown_whitelist_name_is_reported(tmp_path: Path) -> None:
    """rc character names outside the roster land in config.errors."""

    async def scenario() -> None:
        rc = tmp_path / "yaterc"
        rc.write_text(
            'screen_saver = {"characters": ["mario", "nope"]}\n',
            encoding="utf-8",
        )
        config = cfg.load_config([rc])
        app = YateApp(target=_doc(tmp_path), config=config)
        assert "unknown screensaver character: 'nope'" in app.config.errors

    asyncio.run(scenario())


def test_narrow_terminal_pushes_without_raising(tmp_path: Path) -> None:
    """A 20x6 terminal is smaller than some sprites; nothing blows up."""

    async def scenario() -> None:
        app = YateApp(target=_doc(tmp_path))
        async with app.run_test(size=(20, 6)) as pilot:
            await pilot.pause()
            app.editor.execute_action("toggle_screensaver")
            await pilot.pause()
            assert isinstance(app.screen, ScreensaverScreen)
            await pilot.pause(0.3)
            assert isinstance(app.screen, ScreensaverScreen)

    asyncio.run(scenario())
