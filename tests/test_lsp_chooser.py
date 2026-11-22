"""Pilot tests for the generic LSP chooser screen (plan c, wave 2).

Drives the real screen through a minimal host App (the empty-screen
palette pattern from ``tests/test_marks_palette.py``): rows render with
label, detail and ``file:line`` location, enter hands the selected row
to the ``on_pick`` callback and dismisses, up/down wrap and stop the
event (R10), empty rows paint a placeholder and ignore enter, and the
screen subscribes / unsubscribes to the theme broadcast exactly once
(R13).
"""

from __future__ import annotations

import asyncio
from typing import cast

from textual.app import App
from textual.events import Key
from textual.widgets import Static

from yate.editor_components import theme
from yate.editor_components.lsp_chooser import LspChooserScreen, LspRow

from conftest import plain_text, wait_until


def _row(label: str, detail: str, uri: str, row: int) -> LspRow:
    """Build a minimal :class:`LspRow` (end positions unused here)."""
    return LspRow(
        label=label, detail=detail, uri=uri, row=row, col=0,
        end_row=row, end_col=5, kind="reference",
    )


class _StubKey:
    """A stand-in for ``textual.events.Key`` recording consumption."""

    def __init__(self, key: str) -> None:
        self.key = key
        self.stop_called = False
        self.prevent_default_called = False

    def stop(self) -> None:
        """Mirror ``Message.stop``."""
        self.stop_called = True

    def prevent_default(self) -> None:
        """Mirror ``Message.prevent_default``."""
        self.prevent_default_called = True


class _Host(App[None]):
    """Minimal host app that pushes the chooser screen under test."""

    def __init__(self, screen: LspChooserScreen) -> None:
        super().__init__()
        self._screen = screen

    def on_mount(self) -> None:
        self.push_screen(self._screen)


def _body_text(screen: LspChooserScreen) -> str:
    """The chooser body as plain text, as painted into ``#overlay-body``."""
    return plain_text(screen.query_one("#overlay-body", Static).content)


def test_lsp_chooser_renders_label_detail_and_location() -> None:
    """Two rows paint with labels, details and their ``file:line`` locations."""
    async def scenario() -> None:
        picked: list[LspRow] = []
        screen = LspChooserScreen(
            [
                _row("alpha ref", "module-level", "file:///d/work/a.py", 2),
                _row("beta def", "class member", "file:///d/work/b.py", 6),
            ],
            "DEFINITIONS",
            picked.append,
        )
        app = _Host(screen)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            body = _body_text(screen)
            assert "DEFINITIONS" in body
            assert "alpha ref" in body
            assert "beta def" in body
            assert "a.py:3" in body
            assert "b.py:7" in body
            # the first row carries the selection caret, the second not
            lines = body.splitlines()
            caret_lines = [line for line in lines if line.startswith(" > ")]
            assert len(caret_lines) == 1
            assert "alpha ref" in caret_lines[0]

    asyncio.run(scenario())


def test_lsp_chooser_enter_calls_on_pick_with_selected_row() -> None:
    """Down + enter hands the second row to the callback and dismisses."""
    async def scenario() -> None:
        rows = [
            _row("alpha ref", "module-level", "file:///d/work/a.py", 2),
            _row("beta def", "class member", "file:///d/work/b.py", 6),
        ]
        picked: list[LspRow] = []
        screen = LspChooserScreen(rows, "REFERENCES", picked.append)
        app = _Host(screen)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            await pilot.press("down")
            await pilot.pause()
            assert screen.selected_row is rows[1]
            await pilot.press("enter")
            assert await wait_until(pilot, lambda: app.screen is not screen)
            assert picked == [rows[1]]

    asyncio.run(scenario())


def test_lsp_chooser_up_down_wraps_and_stops_event() -> None:
    """From row 0, up wraps to the last row and the event is consumed."""
    async def scenario() -> None:
        rows = [
            _row("one", "d1", "file:///d/work/a.py", 0),
            _row("two", "d2", "file:///d/work/a.py", 1),
            _row("three", "d3", "file:///d/work/a.py", 2),
        ]
        screen = LspChooserScreen(rows, "REFERENCES", lambda _row: None)
        app = _Host(screen)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            assert screen.selected_row is rows[0]
            # a raw stubbed Key: consumption flags are observable directly
            stub = _StubKey("up")
            screen.on_key(cast(Key, cast(object, stub)))
            assert screen.selected_row is rows[2]
            assert stub.stop_called
            assert stub.prevent_default_called
            # down from the last row wraps back to the first
            stub_down = _StubKey("down")
            screen.on_key(cast(Key, cast(object, stub_down)))
            assert screen.selected_row is rows[0]
            assert stub_down.stop_called
            assert stub_down.prevent_default_called

    asyncio.run(scenario())


def test_lsp_chooser_empty_rows_show_placeholder_and_ignore_enter() -> None:
    """No rows paint "(no results)" and enter neither picks nor closes."""
    async def scenario() -> None:
        picked: list[LspRow] = []
        screen = LspChooserScreen([], "DEFINITIONS", picked.append)
        app = _Host(screen)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            assert "(no results)" in _body_text(screen)
            assert screen.selected_row is None
            await pilot.press("enter")
            await pilot.pause()
            assert picked == []
            # enter is a no-op on empty rows: the screen stays open
            assert app.screen is screen
            await pilot.press("escape")
            assert await wait_until(pilot, lambda: app.screen is not screen)

    asyncio.run(scenario())


def test_lsp_chooser_uses_theme_attach_detach() -> None:
    """Mount subscribes to the theme broadcast once; unmount unsubscribes."""
    async def scenario() -> None:
        attached: list[tuple[object, object]] = []
        detached: list[object] = []
        monkey_target = theme
        original_attach = theme.attach
        original_detach = theme.detach

        def _fake_attach(widget: object, repaint: object) -> None:
            attached.append((widget, repaint))

        def _fake_detach(widget: object) -> None:
            detached.append(widget)

        # patch the module-level helpers the screen calls (R13 wiring)
        monkey_target.attach = _fake_attach  # type: ignore[assignment]
        monkey_target.detach = _fake_detach  # type: ignore[assignment]
        try:
            screen = LspChooserScreen(
                [_row("one", "d1", "file:///d/work/a.py", 0)],
                "DEFINITIONS",
                lambda _row: None,
            )
            app = _Host(screen)
            async with app.run_test(size=(100, 30)) as pilot:
                await pilot.pause()
                # the screen itself subscribes exactly once (the shared
                # OverlayScroll base separately subscribes for its scrollbars)
                screen_attaches = [a for a in attached if a[0] is screen]
                assert len(screen_attaches) == 1
            # leaving the run_test context unmounts the screen
            assert detached.count(screen) == 1
        finally:
            monkey_target.attach = original_attach
            monkey_target.detach = original_detach

    asyncio.run(scenario())
