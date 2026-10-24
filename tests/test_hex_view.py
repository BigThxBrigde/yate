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
from rich.segment import Segment
from textual.app import App, ComposeResult
from textual.color import Color as TextualColor
from textual.widgets import Static

from yate.editor_view import theme
from yate.editor_view.hexview import _CONTENT_WIDTH, HexScreen, HexView
from yate.editor_view.scrollbars import SlimScrollBarRender

# "Hello, hex view!" -- exactly 16 bytes, so line 0 is a full row.
_FULL_LINE_DATA = b"Hello, hex view!"
_FULL_LINE_TEXT = "00000000: 48656c6c6f2c2068  6578207669657721  Hello, hex view!"


def _segment_hex(segment: Segment) -> str:
    """Truecolor hex of a segment's foreground color (empty when default)."""
    style = segment.style
    if style is None or style.color is None:
        return ""
    return style.color.get_truecolor().hex


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


def test_hex_view_render_line_segments_are_classified() -> None:
    """Offset and each byte class render in their theme-token color (hexyl)."""

    async def _scenario() -> None:
        app = _ViewHost(bytes([0x00, 0x20, 0x41, 0x7F, 0x80]))
        async with app.run_test(size=(100, 30)):
            view = app.query_one(HexView)
            segments = list(view.render_line(0))
            t = theme.active()
            # Layout: [offset][hex pair x 5][pad]["  " separator][ascii x 5].
            assert [s.text for s in segments[1:6]] == ["00", "20", "41", "7f", "80"]
            assert _segment_hex(segments[0]) == t.fg_muted  # offset
            assert _segment_hex(segments[1]) == t.fg_dim  # 0x00 null
            assert _segment_hex(segments[2]) == t.green  # 0x20 whitespace
            assert _segment_hex(segments[3]) == t.accent  # 0x41 printable
            assert _segment_hex(segments[4]) == t.accent2  # 0x7F ascii_other
            assert _segment_hex(segments[5]) == t.yellow  # 0x80 non_ascii

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


def test_hex_view_scrollbar_uses_slim_renderer() -> None:
    """Both scrollbars render through the slim partial-block renderer (R15)."""

    async def _scenario() -> None:
        app = _ViewHost(_FULL_LINE_DATA)
        async with app.run_test(size=(100, 30)):
            view = app.query_one(HexView)
            assert view.vertical_scrollbar.renderer is SlimScrollBarRender
            assert view.horizontal_scrollbar.renderer is SlimScrollBarRender

    asyncio.run(_scenario())


def test_hex_view_scrollbar_theme_follows_active() -> None:
    """The scrollbar palette tracks the active theme (R15)."""

    async def _scenario() -> None:
        app = _ViewHost(_FULL_LINE_DATA)
        async with app.run_test(size=(100, 30)):
            view = app.query_one(HexView)
            theme.set_theme("latte")
            try:
                assert view.styles.scrollbar_color == TextualColor.parse(
                    theme.active().border
                )
            finally:
                theme.set_theme("mocha")

    asyncio.run(_scenario())


def test_hex_view_virtual_size_matches_line_count() -> None:
    """virtual_size.height is the padded line count of the payload."""
    view = HexView(Path("sample.bin"), b"x" * 33)
    assert view.virtual_size.height == 3  # (33 + 15) // 16
    assert HexView(Path("sample.bin"), b"").virtual_size.height == 0


def test_hex_view_full_line_width_is_62() -> None:
    """A full 16-byte line renders exactly 62 columns (offset + hex + ASCII)."""
    assert _CONTENT_WIDTH == 62


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
