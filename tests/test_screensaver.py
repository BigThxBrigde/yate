"""Pilot tests for the full-terminal screensaver (plan fancy_sym / plan_D)."""

from __future__ import annotations

import asyncio
from pathlib import Path

from yate import config as cfg
from yate.app import YateApp
from yate.editor_view.screensaver import TICKS_PER_SECOND, ScreensaverScreen
from yate.services.idle_tracker import IdleTracker


class _CountingTracker(IdleTracker):
    """Idle tracker that counts pokes (test probe for ``on_event``)."""

    def __init__(self) -> None:
        super().__init__(clock=lambda: 0.0)
        self.pokes = 0

    def poke(self) -> None:
        self.pokes += 1
        super().poke()


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


def test_parade_spawns_distinct_names_on_distinct_rows(tmp_path: Path) -> None:
    """Successors differ from every active walker and never share rows.

    Driving ticks by hand keeps the test deterministic: names on screen
    stay unique and row bands ([row, row + rows)) stay disjoint while the
    parade grows past a single walker.
    """

    async def scenario() -> None:
        app = YateApp(target=_doc(tmp_path))
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            app.editor.execute_action("toggle_screensaver")
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, ScreensaverScreen)
            saw_two = False
            for _ in range(600):
                screen.advance_tick()
                walkers = screen.walkers
                if len(walkers) >= 2:
                    saw_two = True
                names = [w.name for w in walkers]
                assert len(names) == len(set(names))
                spans = sorted((w.row, w.row + w.rows) for w in walkers)
                for (_, a_end), (b_start, _) in zip(spans, spans[1:]):
                    assert a_end <= b_start
            assert saw_two

    asyncio.run(scenario())


def test_successor_spawns_between_quarter_and_half_journey(tmp_path: Path) -> None:
    """With ``switch = 0`` the hand-off point is 25-50% of the walk."""

    async def scenario() -> None:
        app = YateApp(target=_doc(tmp_path))
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            app.editor.execute_action("toggle_screensaver")
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, ScreensaverScreen)
            assert len(screen.walkers) == 1
            walker = screen.walkers[0]
            travel = 80 + walker.sprite_w
            assert walker.spawn_at >= int(0.25 * travel)
            assert walker.spawn_at <= int(0.5 * travel)

    asyncio.run(scenario())


def test_switch_option_floors_the_spawn_delay(tmp_path: Path) -> None:
    """``switch`` seconds delay the successor beyond the random point."""

    async def scenario() -> None:
        app = YateApp(target=_doc(tmp_path))
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            await app.push_screen(ScreensaverScreen((), 5))
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, ScreensaverScreen)
            assert screen.walkers[0].spawn_at >= 5 * TICKS_PER_SECOND

    asyncio.run(scenario())


def test_no_spawn_while_the_only_name_is_walking(tmp_path: Path) -> None:
    """A one-name roster keeps exactly one walker: names must differ."""

    async def scenario() -> None:
        app = YateApp(target=_doc(tmp_path))
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            await app.push_screen(ScreensaverScreen(("mario",), 0))
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, ScreensaverScreen)
            for _ in range(300):
                screen.advance_tick()
                assert len(screen.walkers) == 1
                assert screen.walkers[0].name == "mario"

    asyncio.run(scenario())


def test_no_spawn_when_all_rows_are_taken(tmp_path: Path) -> None:
    """A 3-row terminal is filled by any sprite, so no successor spawns.

    The shortest roster sprite is 7 pixels tall (4 text rows), so on a
    3-row screen every spawn clips at row 0 and occupies every row; the
    parade stays at exactly one walker yet never empties out.
    """

    async def scenario() -> None:
        app = YateApp(target=_doc(tmp_path))
        async with app.run_test(size=(80, 3)) as pilot:
            await pilot.pause()
            app.editor.execute_action("toggle_screensaver")
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, ScreensaverScreen)
            for _ in range(300):
                screen.advance_tick()
                assert len(screen.walkers) == 1


# --- idle auto-trigger wiring (YateApp.on_event poke + _check_idle poll) ----


def test_idle_poll_auto_starts_screensaver(tmp_path: Path) -> None:
    """A due tracker plus the 1 s poll opens the screensaver on its own.

    The real tracker starts "now"; swapping in a clock frozen at 0.0 makes
    it permanently due, so one synchronous ``_check_idle()`` call exercises
    the exact code path the app's interval timer drives.
    """

    async def scenario() -> None:
        app = YateApp(target=_doc(tmp_path))
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            app._idle = IdleTracker(clock=lambda: 0.0)
            app._check_idle()
            await pilot.pause()
            assert isinstance(app.screen, ScreensaverScreen)

    asyncio.run(scenario())


def test_idle_poll_never_retriggers_while_active(tmp_path: Path) -> None:
    """The poll skips while the screensaver is up: no push/pop loop.

    The docstring-promised guard keeps the one-second poll from toggling
    the overlay away again; the screen stack must stay exactly as the
    single auto-start left it.
    """

    async def scenario() -> None:
        app = YateApp(target=_doc(tmp_path))
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            app._idle = IdleTracker(clock=lambda: 0.0)
            app._check_idle()
            await pilot.pause()
            assert isinstance(app.screen, ScreensaverScreen)
            depth = len(app.screen_stack)
            for _ in range(5):
                app._check_idle()
            await pilot.pause()
            assert isinstance(app.screen, ScreensaverScreen)
            assert len(app.screen_stack) == depth

    asyncio.run(scenario())


def test_idle_poll_skips_when_interval_zero(tmp_path: Path) -> None:
    """``interval = 0`` disables the automatic trigger even when due."""

    async def scenario() -> None:
        rc = tmp_path / "yaterc"
        rc.write_text('screen_saver = {"interval": 0}\n', encoding="utf-8")
        app = YateApp(target=_doc(tmp_path), config=cfg.load_config([rc]))
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            assert app._idle is not None
            app._idle = IdleTracker(clock=lambda: 0.0)
            app._check_idle()
            await pilot.pause()
            assert not isinstance(app.screen, ScreensaverScreen)

    asyncio.run(scenario())


def test_idle_poll_skips_when_disabled(tmp_path: Path) -> None:
    """``enable = False`` costs the tracker entirely: nothing polls."""

    async def scenario() -> None:
        rc = tmp_path / "yaterc"
        rc.write_text('screen_saver = {"enable": False}\n', encoding="utf-8")
        app = YateApp(target=_doc(tmp_path), config=cfg.load_config([rc]))
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            assert app._idle is None
            app._check_idle()
            await pilot.pause()
            assert not isinstance(app.screen, ScreensaverScreen)

    asyncio.run(scenario())


def test_on_event_pokes_idle_tracker(tmp_path: Path) -> None:
    """Every input event pokes the tracker through ``App.on_event``."""

    async def scenario() -> None:
        app = YateApp(target=_doc(tmp_path))
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            tracker = _CountingTracker()
            app._idle = tracker
            await pilot.press("x")
            await pilot.pause()
            assert tracker.pokes >= 1

    asyncio.run(scenario())


def test_all_invalid_whitelist_is_reported_and_refused(tmp_path: Path) -> None:
    """Every whitelist name unknown: reported at startup, refused on toggle.

    The unknown names reach ``config.errors`` before the Editor snapshots
    them, so the startup banner carries them; the toggle itself refuses
    instead of silently falling back to the whole roster.
    """

    async def scenario() -> None:
        rc = tmp_path / "yaterc"
        rc.write_text(
            'screen_saver = {"characters": ["nope1", "nope2"]}\n',
            encoding="utf-8",
        )
        app = YateApp(target=_doc(tmp_path), config=cfg.load_config([rc]))
        assert "unknown screensaver character: 'nope1'" in app.config.errors
        assert "unknown screensaver character: 'nope2'" in app.config.errors
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            app.editor.execute_action("toggle_screensaver")
            await pilot.pause()
            assert not isinstance(app.screen, ScreensaverScreen)

    asyncio.run(scenario())
