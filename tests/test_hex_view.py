"""Tests for yate.editor_view.hexview (HexView widget + HexScreen overlay).

Rendering tests mount the view in a minimal host app (Lightweight-test
anchor, whichkey-panel precedent) and call the line API directly; the
screen test pushes :class:`HexScreen` and verifies the ``q`` / ``escape``
dismissal.
"""

# tests legitimately poke at view internals (subscription hook):
# pyright: reportPrivateUsage=false

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import override

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Static

from yate.editor_view import theme
from yate.editor_view.hexview import HexScreen, HexView

# "Hello, hex view!" -- exactly 16 bytes, so line 0 is a full row.
_FULL_LINE_DATA = b"Hello, hex view!"
_FULL_LINE_TEXT = "00000000: 48656c6c6f2c2068  6578207669657721  Hello, hex view!"


class _ViewHost(App[None]):
    """Minimal host mounting one HexView of the given data."""

    def __init__(self, data: bytes) -> None:
        super().__init__()
        self._data = data

    @override
    def compose(self) -> ComposeResult:
        yield HexView(Path("sample.bin"), self._data)


def test_hex_view_renders_offset_hex_ascii() -> None:
    """A full 16-byte line renders as offset + two hex groups + ASCII."""

    async def _scenario() -> None:
        app = _ViewHost(_FULL_LINE_DATA)
        async with app.run_test(size=(100, 30)):
            view = app.query_one(HexView)
            assert view.render_line(0).text.rstrip() == _FULL_LINE_TEXT

    asyncio.run(_scenario())


def test_hex_view_handles_partial_last_line() -> None:
    """A short final row pads the hex group but keeps the column layout."""

    async def _scenario() -> None:
        app = _ViewHost(b"ab")
        async with app.run_test(size=(100, 30)):
            view = app.query_one(HexView)
            expected = f"00000000: {'6162'.ljust(16)}  ab"
            assert view.render_line(0).text.rstrip() == expected

    asyncio.run(_scenario())


def test_hex_view_ascii_column_replaces_nonprintable() -> None:
    """Non-printable bytes (0x00-0x1f, 0x7f-0xff) render as dots."""

    async def _scenario() -> None:
        app = _ViewHost(bytes([0x00, 0x01, 0x1F, 0x20, 0x41, 0x7E, 0x7F, 0xFF]))
        async with app.run_test(size=(100, 30)):
            view = app.query_one(HexView)
            line = view.render_line(0).text.rstrip()
            assert line.endswith("... A~..")
            assert line.startswith("00000000: 00011f20417e7fff")

    asyncio.run(_scenario())


def test_hex_view_theme_subscription(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mounting subscribes to theme broadcasts; a broadcast repaints."""

    async def _scenario() -> None:
        app = _ViewHost(_FULL_LINE_DATA)
        async with app.run_test(size=(100, 30)):
            view = app.query_one(HexView)
            assert view._theme_unsubscribe is not None
            refreshes: list[bool] = []

            def _spy(*args: object, **kwargs: object) -> bool:
                refreshes.append(True)
                return True

            monkeypatch.setattr(view, "refresh", _spy)
            theme.set_theme("latte")
            assert refreshes, "theme broadcast must repaint the view"

    try:
        asyncio.run(_scenario())
    finally:
        theme.set_theme("mocha")


def test_hex_view_virtual_size_matches_line_count() -> None:
    """virtual_size.height is the padded line count of the payload."""
    view = HexView(Path("sample.bin"), b"x" * 33)
    assert view.virtual_size.height == 3  # (33 + 15) // 16
    assert HexView(Path("sample.bin"), b"").virtual_size.height == 0


class _ScreenHost(App[None]):
    """Minimal host used to push a HexScreen."""

    @override
    def compose(self) -> ComposeResult:
        yield Static("")


def test_hex_screen_dismisses_on_q() -> None:
    """``q`` and ``escape`` dismiss the screen."""

    async def _scenario() -> None:
        app = _ScreenHost()
        async with app.run_test(size=(100, 30)) as pilot:
            screen = HexScreen(Path("sample.bin"), _FULL_LINE_DATA)
            app.push_screen(screen)
            await pilot.pause()
            assert app.screen is screen

            await pilot.press("q")
            await pilot.pause()
            assert app.screen is not screen

            app.push_screen(HexScreen(Path("sample.bin"), _FULL_LINE_DATA))
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()
            assert app.screen is not screen

    asyncio.run(_scenario())
