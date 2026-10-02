"""Pilot tests for the full-terminal screensaver (plan fancy_sym / plan_D)."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import cast, override

import pytest

from yate import config as cfg
from yate.app import YateApp
from yate.editor_sprites.render import walk_x
from yate.editor_view.screensaver import TICKS_PER_SECOND, ScreensaverScreen
from yate.services.idle_tracker import IdleTracker


class _CountingTracker(IdleTracker):
    """Idle tracker that counts pokes (test probe for ``on_event``)."""

    def __init__(self) -> None:
        super().__init__(clock=lambda: 0.0)
        self.pokes = 0

    @override
    def poke(self) -> None:
        """Count the poke, then apply the real idle reset."""
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


def test_parade_keeps_names_distinct_and_sprites_never_overlap(
    tmp_path: Path,
) -> None:
    """Successors differ from every active walker and pixels never collide.

    Driving ticks by hand keeps the test deterministic: names on screen
    stay unique, and sprites whose row bands intersect stay horizontally
    spaced beyond ``dist_upper_bound`` of the journey -- a band may host
    several walkers, but overlap is never allowed.
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
            tick = 0
            for _ in range(600):
                screen.advance_tick()
                tick += 1
                walkers = screen.walkers
                if len(walkers) >= 2:
                    saw_two = True
                names = [w.name for w in walkers]
                assert len(names) == len(set(names))
                for i, a in enumerate(walkers):
                    for b in walkers[i + 1 :]:
                        if not (
                            a.row < b.row + b.rows and b.row < a.row + a.rows
                        ):
                            continue  # vertically apart: no shared row
                        ax = walk_x(tick - a.spawn_tick, 80, a.sprite_w)
                        bx = walk_x(tick - b.spawn_tick, 80, b.sprite_w)
                        behind = a if ax < bx else b
                        gap = max(ax, bx) - (min(ax, bx) + behind.sprite_w)
                        # the trailing walker's spawn enforced the floor and
                        # equal speeds keep the spacing constant forever
                        assert gap > (1 / 3) * (80 + behind.sprite_w)
            assert saw_two

    asyncio.run(scenario())


def test_successor_spawns_between_eighth_and_third_journey(tmp_path: Path) -> None:
    """With ``switch = 0`` the hand-off point is 1/8-1/3 of the walk."""

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
            assert walker.spawn_at >= int((1 / 8) * travel)
            assert walker.spawn_at <= int((1 / 3) * travel)

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


def test_dist_bounds_pin_the_spawn_point_and_ignore_switch(
    tmp_path: Path,
) -> None:
    """Explicit ``dist_bounds`` replace the timing rule entirely."""

    async def scenario() -> None:
        app = YateApp(target=_doc(tmp_path))
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            # switch = 10 would floor the spawn at 100 ticks; the window
            # (0.5, 0.75) of a ~90 tick walk can never reach that floor.
            await app.push_screen(ScreensaverScreen((), 10, (0.5, 0.75)))
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, ScreensaverScreen)
            walker = screen.walkers[0]
            travel = 80 + walker.sprite_w
            assert walker.spawn_at >= int(0.5 * travel)
            assert walker.spawn_at <= int(0.75 * travel)
            assert walker.spawn_at < 10 * TICKS_PER_SECOND

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


def test_same_band_spawn_once_the_gap_exceeds_the_upper_bound(
    tmp_path: Path,
) -> None:
    """A busy band is reusable once its walker is ``dist_upper_bound`` ahead.

    On a 3-row terminal every sprite clips into the single band, so a
    successor can only appear by sharing it.  A large ``switch`` delays
    the hand-off far past the random window, so when it fires the walker
    ahead is guaranteed to be beyond the distance floor.
    """

    async def scenario() -> None:
        app = YateApp(target=_doc(tmp_path))
        async with app.run_test(size=(80, 3)) as pilot:
            await pilot.pause()
            await app.push_screen(ScreensaverScreen((), 8))
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, ScreensaverScreen)
            initial = screen.walkers
            assert len(initial) == 1
            for _ in range(8 * TICKS_PER_SECOND):
                screen.advance_tick()
            live = screen.walkers
            assert len(live) == 2
            ahead, behind = live[0], live[1]
            # both sprites occupy the one band there is
            assert ahead.row < behind.row + behind.rows
            assert behind.row < ahead.row + ahead.rows
            # the successor spawns at column 0 (right edge), so the gap to
            # the walker ahead is its elapsed distance minus its own width
            gap = 8 * TICKS_PER_SECOND - ahead.sprite_w
            assert gap > (1 / 3) * (80 + behind.sprite_w)
            # one more tick repaints the canvas with both on the same band
            screen.advance_tick()
            live = screen.walkers
            assert len(live) == 2
            xs = [walk_x(81 - w.spawn_tick, 80, w.sprite_w) for w in live]
            left = live[xs.index(min(xs))]
            assert max(xs) - (min(xs) + left.sprite_w) > 0

    asyncio.run(scenario())


def test_no_spawn_while_the_band_is_within_the_distance_floor(
    tmp_path: Path,
) -> None:
    """A saturated band stays closed while its walker is inside the floor.

    On a 3-row terminal every sprite clips into the single band, so any
    successor would have to share it -- but at the one-shot hand-off the
    triggering walker's tail is still inside the distance floor (the
    random window can never push it beyond ``dist_upper_bound`` of the
    successor's journey), so the spawn is refused and the parade keeps
    exactly one walker per lap.
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

    asyncio.run(scenario())


# --- idle auto-trigger wiring (YateApp.on_event poke + check_idle poll) -----


def test_idle_poll_auto_starts_screensaver(tmp_path: Path) -> None:
    """A due tracker plus the poll opens the screensaver on its own.

    With ``interval = 1`` the real tracker becomes due after about a
    second of silence, so one synchronous ``check_idle()`` call exercises
    the exact code path the app's interval timer drives.
    """

    async def scenario() -> None:
        rc = tmp_path / "yaterc"
        rc.write_text('screen_saver = {"interval": 1}\n', encoding="utf-8")
        app = YateApp(target=_doc(tmp_path), config=cfg.load_config([rc]))
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            await pilot.pause(1.1)
            app.poll_idle()
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
        rc = tmp_path / "yaterc"
        rc.write_text('screen_saver = {"interval": 1}\n', encoding="utf-8")
        app = YateApp(target=_doc(tmp_path), config=cfg.load_config([rc]))
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            await pilot.pause(1.1)
            app.poll_idle()
            await pilot.pause()
            assert isinstance(app.screen, ScreensaverScreen)
            depth = len(app.screen_stack)
            for _ in range(5):
                app.poll_idle()
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
            await pilot.pause(1.1)
            app.poll_idle()
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
            assert app.idle_tracker is None
            app.poll_idle()
            await pilot.pause()
            assert not isinstance(app.screen, ScreensaverScreen)

    asyncio.run(scenario())


def test_on_event_pokes_idle_tracker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every input event pokes the tracker through ``App.on_event``.

    Swapping the class before construction routes the app's own tracker
    through the counting probe; the press then must have poked it.
    """

    async def scenario() -> None:
        monkeypatch.setattr("yate.app.IdleTracker", _CountingTracker)
        app = YateApp(target=_doc(tmp_path))
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            tracker = cast(_CountingTracker, app.idle_tracker)
            assert tracker is not None
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
