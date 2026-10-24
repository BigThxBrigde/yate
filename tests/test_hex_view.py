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
from typing import Any, cast, override

import pytest
from rich.segment import Segment
from textual.app import App, ComposeResult
from textual.color import Color as TextualColor
from textual.screen import Screen
from textual.widgets import Input, Static

from yate.editor_view import theme
from yate.editor_view.hexview import (
    _CONTENT_WIDTH,
    HexScreen,
    HexView,
    parse_hex_address,
)
from yate.editor_view.scrollbars import SlimScrollBarRender
from yate.flows.overlay_flows import OverlayFlows

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


def test_parse_hex_address_valid_hex() -> None:
    """A 0x-prefixed hexadecimal string parses to its byte offset."""
    assert parse_hex_address("0x1a", 100) == 26


def test_parse_hex_address_valid_decimal() -> None:
    """A pure-digit string parses as decimal (42, not 0x42)."""
    assert parse_hex_address("42", 100) == 42


def test_parse_hex_address_out_of_bounds() -> None:
    """An address at or beyond the file size raises ValueError."""
    with pytest.raises(ValueError, match="out of bounds"):
        parse_hex_address("0xff", 100)


def test_parse_hex_address_invalid_format() -> None:
    """Text matching neither accepted form raises ValueError."""
    with pytest.raises(ValueError, match="invalid format"):
        parse_hex_address("xyz", 100)


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


def test_hex_screen_goto_input_shows_on_g() -> None:
    """``g`` reveals and focuses the goto-address input."""

    async def _scenario() -> None:
        app = _ScreenHost()
        async with app.run_test(size=(100, 30)) as pilot:
            screen = HexScreen(Path("sample.bin"), _FULL_LINE_DATA)
            app.push_screen(screen)
            await pilot.pause()
            await pilot.press("g")
            await pilot.pause()
            goto_input = screen.query_one("#hex-goto-input", Input)
            assert goto_input.display is True
            assert goto_input.has_focus

    asyncio.run(_scenario())


def test_hex_screen_goto_input_submits_and_scrolls() -> None:
    """Submitting a valid address scrolls the hex view to the target line."""

    async def _scenario() -> None:
        app = _ScreenHost()
        async with app.run_test(size=(100, 30)) as pilot:
            screen = HexScreen(Path("sample.bin"), b"\x00" * 1024)  # 64 lines
            app.push_screen(screen)
            await pilot.pause()
            await pilot.press("g")
            await pilot.press("0", "x", "1", "0")
            await pilot.press("enter")
            await pilot.pause()
            assert screen.query_one("#hex-view", HexView).scroll_offset.y == 1
            assert screen.query_one("#hex-goto-input", Input).display is False

    asyncio.run(_scenario())


def test_hex_screen_goto_input_escapes_without_jump() -> None:
    """``escape`` with the input open hides it without jumping or dismissing."""

    async def _scenario() -> None:
        app = _ScreenHost()
        async with app.run_test(size=(100, 30)) as pilot:
            screen = HexScreen(Path("sample.bin"), b"\x00" * 1024)
            app.push_screen(screen)
            await pilot.pause()
            await pilot.press("g")
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()
            assert screen.query_one("#hex-goto-input", Input).display is False
            assert screen.query_one("#hex-view", HexView).scroll_offset.y == 0

    asyncio.run(_scenario())


def test_hex_view_cursor_move() -> None:
    """``move_cursor`` walks the payload and clamps at both edges."""

    async def _scenario() -> None:
        app = _ViewHost(b"x" * 32)
        async with app.run_test(size=(100, 30)):
            view = app.query_one(HexView)
            view.move_cursor(5)
            assert view._cursor_pos == 5
            view.move_cursor(1000)
            assert view._cursor_pos == 31  # clamped to the last byte

    asyncio.run(_scenario())


def test_hex_view_edit_mode_toggle() -> None:
    """``enter_edit_mode`` / ``exit_edit_mode`` flip the edit flag."""

    async def _scenario() -> None:
        app = _ViewHost(b"x" * 32)
        async with app.run_test(size=(100, 30)):
            view = app.query_one(HexView)
            view.enter_edit_mode()
            assert view._edit_mode is True
            view.exit_edit_mode()
            assert view._edit_mode is False

    asyncio.run(_scenario())


def test_hex_view_edit_nibble() -> None:
    """Two nibble presses merge into the cursor byte (high then low)."""

    async def _scenario() -> None:
        app = _ViewHost(b"\x00\x00")
        async with app.run_test(size=(100, 30)):
            view = app.query_one(HexView)
            view._cursor_pos = 0
            view._edit_mode = True
            view.edit_nibble("a")
            view.edit_nibble("b")
            assert view._data[0] == 0xAB

    asyncio.run(_scenario())


def test_hex_view_undo() -> None:
    """``undo`` pops the stack and restores the overwritten byte."""

    async def _scenario() -> None:
        app = _ViewHost(b"\x00")
        async with app.run_test(size=(100, 30)):
            view = app.query_one(HexView)
            view._cursor_pos = 0
            view.edit_nibble("f")
            assert view._data[0] == 0xF0
            view.undo()
            assert view._data[0] == 0x00

    asyncio.run(_scenario())


def test_hex_view_ascii_sync() -> None:
    """Editing a byte updates the ASCII echo column on the same row."""

    async def _scenario() -> None:
        app = _ViewHost(b"\x00")
        async with app.run_test(size=(100, 30)):
            view = app.query_one(HexView)
            view._cursor_pos = 0
            view.edit_nibble("4")
            view.edit_nibble("1")
            line = view.render_line(0).text.rstrip()
            assert line.endswith("A")

    asyncio.run(_scenario())


class _FakeSession:
    """EditorSession stand-in exposing only the conflict-gate query."""

    def __init__(self, open_path: Path | None) -> None:
        self._open_path = open_path

    def is_open(self, path: Path) -> object | None:
        """Non-``None`` while *path* counts as open (mock gate)."""
        if path == self._open_path:
            return object()
        return None


def _noop_push_screen(
    screen: Screen[None], callback: object | None = None
) -> None:
    """No-op push target (these tests never actually push a screen)."""


def _make_flows(
    messages: list[tuple[str, str]],
    *,
    session: object | None = None,
) -> OverlayFlows:
    """OverlayFlows wired for the hex write-back path only.

    Mirrors the ``_make_flows`` precedent in ``test_overlay_flows_hex.py``:
    collaborators untouched by these tests are stubbed out.
    """
    return OverlayFlows(
        push_screen=_noop_push_screen,
        pop_screen=lambda: None,
        current_screen=lambda: cast(Screen[None], None),
        config=cast(Any, None),
        keymaps=cast(Any, None),
        commands=cast(Any, None),
        actions=cast(Any, None),
        session=cast(Any, session),
        workspace=cast(Any, None),
        prompt=cast(Any, None),
        message=lambda text, kind: messages.append((text, kind)),
        mounted=lambda: True,
        open_path=lambda path: None,
        reveal_match=lambda path, row, col: None,
        readonly_notice=lambda: None,
        focus_editor=lambda: None,
        execute_action=lambda name: True,
        run_command=lambda text: None,
        refresh=lambda: None,
    )


def test_hex_screen_save_writes_bytes(tmp_path: Path) -> None:
    """``save`` hands the current payload to the injected writer callback."""
    path = tmp_path / "test.bin"
    path.write_bytes(b"\x00" * 16)
    stat = path.stat()
    calls: list[tuple[Path, bytes, float, int]] = []

    def spy(
        write_path: Path, write_data: bytes, write_mtime: float, write_size: int
    ) -> None:
        calls.append((write_path, write_data, write_mtime, write_size))
        write_path.write_bytes(write_data)  # mimic the real same-length write

    screen = HexScreen(
        path,
        b"\x00" * 16,
        write_bytes=spy,
        mtime=stat.st_mtime,
        size=stat.st_size,
    )
    screen.save()
    assert calls
    assert calls[0][1] == b"\x00" * 16
    assert calls[0][2] == stat.st_mtime
    assert calls[0][3] == stat.st_size
    assert path.read_bytes() == b"\x00" * 16


def test_hex_screen_save_refuses_conflict(tmp_path: Path) -> None:
    """The write-back refuses while the path is open as a text document."""
    path = tmp_path / "test.bin"
    path.write_bytes(b"\x00" * 16)
    messages: list[tuple[str, str]] = []
    flows = _make_flows(messages, session=_FakeSession(path))
    screen = HexScreen(
        path,
        b"\x00" * 16,
        write_bytes=flows._write_hex_bytes,
        mtime=path.stat().st_mtime,
        size=16,
    )
    screen.save()
    assert messages
    assert "open in text editor" in messages[0][0]
    assert messages[0][1] == "warn"
    assert path.read_bytes() == b"\x00" * 16  # untouched


def test_hex_screen_save_refuses_external_modification(tmp_path: Path) -> None:
    """A mtime/size mismatch since load refuses the write-back (TOCTOU)."""
    path = tmp_path / "test.bin"
    path.write_bytes(b"\x00" * 16)
    messages: list[tuple[str, str]] = []
    flows = _make_flows(messages, session=_FakeSession(None))
    # The recorded fingerprint is deliberately stale: the real stat cannot
    # match it, which is exactly the external-modification signal.
    screen = HexScreen(
        path,
        b"\x00" * 16,
        write_bytes=flows._write_hex_bytes,
        mtime=path.stat().st_mtime + 1.0,
        size=16,
    )
    screen.save()
    assert messages
    assert "modified externally" in messages[0][0]
    assert path.read_bytes() == b"\x00" * 16  # untouched


def test_hex_view_read_only_refuses_save(tmp_path: Path) -> None:
    """Without a writer callback (read-only file) the save is refused."""
    messages: list[tuple[str, str]] = []
    screen = HexScreen(
        tmp_path / "test.bin",
        b"\x00" * 16,
        message=lambda text, kind: messages.append((text, kind)),
        write_bytes=None,
    )
    screen.save()
    assert messages
    assert "not available" in messages[0][0]
    assert messages[0][1] == "warn"
