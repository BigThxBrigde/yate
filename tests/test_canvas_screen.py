"""Pilot tests for the extension canvas screen (plan lua-tetris-game, Step 5).

A minimal host app pushes :class:`CanvasScreen` exactly like the editor does
(``push_screen(screen, callback=on_close)``), then the tests drive it through
real key events, the screen's own clock and its public draw/status surface.
The canvas is modal: a key it handles must never reach the app underneath.
"""

# the tests legitimately inspect the grid Static and the screen's clock timer:
# pyright: reportPrivateUsage=false

from __future__ import annotations

import asyncio
from typing import cast

from textual import events
from textual.app import App
from textual.content import Content
from textual.style import Style
from textual.widgets import Static

from yate.editor_view.canvas_screen import TICKS_PER_SECOND, CanvasScreen

from conftest import wait_until


class _Host(App[None]):
    """Minimal host that pushes the canvas with the close callback wired.

    Mirrors the editor's ``_open_canvas`` wiring: the constructor's
    ``on_close`` and the push callback are kept apart so the test can pin
    which path actually reports the close.
    """

    ENABLE_COMMAND_PALETTE = False

    def __init__(self, cols: int = 4, rows: int = 3) -> None:
        super().__init__()
        self._cols = cols
        self._rows = rows
        self.canvas: CanvasScreen | None = None
        #: Keys the canvas forwarded to its ``on_key`` sink.
        self.forwarded: list[str] = []
        #: Keys that reached the app -- empty while the modal canvas is up.
        self.leaked: list[str] = []
        #: ``on_tick`` invocations driven by the screen's own interval clock.
        self.ticks: int = 0
        #: Closes reported through the push callback (the real wiring).
        self.closed_via_push: int = 0
        #: Closes reported through the constructor hook (not the wiring).
        self.closed_via_screen: int = 0

    def on_mount(self) -> None:
        self.canvas = CanvasScreen(
            self._cols,
            self._rows,
            self.forwarded.append,
            self._tick,
            self._close_screen,
        )
        self.push_screen(self.canvas, callback=self._close_push)

    def _tick(self) -> None:
        self.ticks += 1

    def _close_screen(self) -> None:
        self.closed_via_screen += 1

    def _close_push(self, _result: None) -> None:
        self.closed_via_push += 1

    def on_key(self, event: events.Key) -> None:
        """Record keys that bubble up to the app."""
        self.leaked.append(event.key)


def _grid_content(screen: CanvasScreen) -> Content:
    """The grid Static's normalized visual (what ``_paint`` last set)."""
    return cast(Content, screen.query_one(".grid", Static).visual)


def _status_text(screen: CanvasScreen) -> str:
    """The status Static's plain text."""
    return cast(Content, screen.query_one(".status", Static).visual).plain


def test_draw_paints_palette_colors_and_aligns_the_grid() -> None:
    """``draw`` colors palette characters, clips the overflow and pads rows.

    The palette also maps ``" "``: the blank-cell rule must win over it, so
    no space ever carries a color span.
    """

    async def scenario() -> None:
        app = _Host(cols=4, rows=3)
        async with app.run_test(size=(40, 12)) as pilot:
            await pilot.pause()
            canvas = app.canvas
            assert canvas is not None

            # five wide and five tall: columns clip at 4, the extra row drops
            canvas.draw(
                "abcde\nxy\n\nzz\nhidden",
                {"a": "#ff0000", "x": "#00ff00", " ": "#0000ff"},
            )
            await pilot.pause()

            assert canvas.drawn == ("abcd", "xy  ", "    ")
            content = _grid_content(canvas)
            assert content.plain == "abcd\nxy  \n    "
            # only the two palette characters carry a style, in their color
            spans = [(span.start, span.end, span.style) for span in content.spans]
            assert (0, 1, Style.parse("#ff0000")) in spans
            assert (5, 6, Style.parse("#00ff00")) in spans
            assert len(spans) == 2
            assert all(
                content.plain[start:end] != " " for start, end, _style in spans
            )

    asyncio.run(scenario())


def test_set_status_replaces_the_status_line() -> None:
    """``set_status`` renders its text into the status Static verbatim."""

    async def scenario() -> None:
        app = _Host(cols=4, rows=3)
        async with app.run_test(size=(40, 12)) as pilot:
            await pilot.pause()
            canvas = app.canvas
            assert canvas is not None
            assert _status_text(canvas) == ""

            canvas.set_status("score 1234  lines 12  level 3  next: T")
            await pilot.pause()

            assert _status_text(canvas) == "score 1234  lines 12  level 3  next: T"

    asyncio.run(scenario())


def test_keys_are_forwarded_and_never_reach_the_app_below() -> None:
    """The modal canvas consumes a key and forwards its Textual name."""

    async def scenario() -> None:
        app = _Host(cols=4, rows=3)
        async with app.run_test(size=(40, 12)) as pilot:
            await pilot.pause()
            canvas = app.canvas
            assert canvas is not None

            await pilot.press("left")
            await pilot.pause()

            assert app.forwarded == ["left"]
            assert app.leaked == []
            assert app.screen is canvas

    asyncio.run(scenario())


def test_escape_dismisses_and_reports_the_close_once() -> None:
    """``escape`` is the canvas' own verb: dismiss, no forward, one close.

    The close callback rides the push callback (the editor's wiring); the
    constructor hook stays untouched.  After the pop the same key reaches
    the app again, which proves the leak detector is meaningful.
    """

    async def scenario() -> None:
        app = _Host(cols=4, rows=3)
        async with app.run_test(size=(40, 12)) as pilot:
            await pilot.pause()
            canvas = app.canvas
            assert canvas is not None

            await pilot.press("escape")
            await pilot.pause()

            assert app.forwarded == []
            assert app.closed_via_push == 1
            assert app.closed_via_screen == 0
            assert app.screen is not canvas
            assert app.leaked == []

            # no modal screen in front any more: the key now reaches the app
            await pilot.press("x")
            await pilot.pause()
            assert app.leaked == ["x"]

    asyncio.run(scenario())


def test_interval_clock_drives_on_tick() -> None:
    """The screen owns a ``1 / TICKS_PER_SECOND`` clock that calls ``on_tick``.

    The interval is asserted on the mounted screen's timer (deterministic),
    and the tick count is then polled instead of slept on a fixed delay, so
    a slow machine cannot turn the assertion into a timing flake.
    """

    async def scenario() -> None:
        app = _Host(cols=4, rows=3)
        async with app.run_test(size=(40, 12)) as pilot:
            await pilot.pause()
            canvas = app.canvas
            assert canvas is not None

            assert TICKS_PER_SECOND == 15
            intervals = [timer._interval for timer in canvas._timers]
            assert any(
                abs(interval - 1 / TICKS_PER_SECOND) < 1e-9
                for interval in intervals
            )

            assert await wait_until(pilot, lambda: app.ticks >= 2)

    asyncio.run(scenario())


def test_raising_key_sink_is_reported_and_keeps_the_canvas_alive() -> None:
    """A raising extension callback is reported on the status line.

    The canvas survives (extension code must never crash the app, same
    contract as the tick path), and later keys still reach the sink.
    """

    async def scenario() -> None:
        app = _Host(cols=4, rows=3)
        calls = 0

        def sink(_key: str) -> None:
            nonlocal calls
            calls += 1
            raise RuntimeError("boom")

        async with app.run_test(size=(40, 12)) as pilot:
            await pilot.pause()
            canvas = app.canvas
            assert canvas is not None
            canvas._key_sink = sink

            await pilot.press("left")
            await pilot.pause()

            assert "key callback failed" in _status_text(canvas)
            assert app.screen is canvas

            await pilot.press("right")
            await pilot.pause()

            assert calls == 2
            assert app.screen is canvas

    asyncio.run(scenario())
