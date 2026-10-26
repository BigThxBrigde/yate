"""Tests for yate.editor_view.hexview (HexView widget + HexScreen overlay).

Rendering tests mount the view in a minimal host app (Lightweight-test
anchor, whichkey-panel precedent) and call the line API directly; the
chunked data source is built over a real tmp file so the block-read
semantics stay honest.  The screen test pushes :class:`HexScreen` and
verifies the ``q`` / ``escape`` dismissal.
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

from yate.editor_core.chunked import ChunkedBinaryFile
from yate.editor_view import theme
from yate.editor_view.hexview import (
    _CONTENT_WIDTH,
    HexScreen,
    HexView,
    MAX_UNDO_STEPS,
    parse_hex_address,
)
from yate.editor_view.scrollbars import SlimScrollBarRender
from yate.flows.overlay_flows import OverlayFlows

# "Hello, hex view!" -- exactly 16 bytes, so line 0 is a full row.
_FULL_LINE_DATA = b"Hello, hex view!"
_FULL_LINE_TEXT = "00000000: 48656c6c6f2c2068  6578207669657721  Hello, hex view!"


def _make_source(tmp_path: Path, data: bytes) -> ChunkedBinaryFile:
    """Build a chunked source over *data* written into *tmp_path*."""
    path = tmp_path / "sample.bin"
    path.write_bytes(data)
    return ChunkedBinaryFile(path, len(data), 0.0)


def _segment_hex(segment: Segment) -> str:
    """Truecolor hex of a segment's foreground color (empty when default)."""
    style = segment.style
    if style is None or style.color is None:
        return ""
    return style.color.get_truecolor().hex


class _ViewHost(App[None]):
    """Minimal host mounting one HexView over the given chunked source."""

    def __init__(self, source: ChunkedBinaryFile) -> None:
        super().__init__()
        self._source = source

    @override
    def compose(self) -> ComposeResult:
        yield HexView(self._source.path, self._source)


def test_hex_view_renders_offset_hex_ascii(tmp_path: Path) -> None:
    """A full 16-byte line renders as offset + two hex groups + ASCII."""

    async def _scenario() -> None:
        app = _ViewHost(_make_source(tmp_path, _FULL_LINE_DATA))
        async with app.run_test(size=(100, 30)):
            view = app.query_one(HexView)
            assert view.render_line(0).text.rstrip() == _FULL_LINE_TEXT

    asyncio.run(_scenario())


def test_hex_view_handles_partial_last_line(tmp_path: Path) -> None:
    """A short final row pads the hex group but keeps the column layout."""

    async def _scenario() -> None:
        app = _ViewHost(_make_source(tmp_path, b"ab"))
        async with app.run_test(size=(100, 30)):
            view = app.query_one(HexView)
            expected = f"00000000: {'6162'.ljust(16)}  ab"
            assert view.render_line(0).text.rstrip() == expected

    asyncio.run(_scenario())


def test_hex_view_ascii_column_replaces_nonprintable(tmp_path: Path) -> None:
    """Non-printable bytes (0x00-0x1f, 0x7f-0xff) render as dots."""

    async def _scenario() -> None:
        app = _ViewHost(
            _make_source(
                tmp_path, bytes([0x00, 0x01, 0x1F, 0x20, 0x41, 0x7E, 0x7F, 0xFF])
            )
        )
        async with app.run_test(size=(100, 30)):
            view = app.query_one(HexView)
            line = view.render_line(0).text.rstrip()
            assert line.endswith("... A~..")
            assert line.startswith("00000000: 00011f20417e7fff")

    asyncio.run(_scenario())


def test_hex_view_render_line_segments_are_classified(tmp_path: Path) -> None:
    """Offset and each byte class render in their theme-token color (hexyl)."""

    async def _scenario() -> None:
        app = _ViewHost(_make_source(tmp_path, bytes([0x00, 0x20, 0x41, 0x7F, 0x80])))
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


def test_hex_view_theme_subscription(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mounting subscribes to theme broadcasts; a broadcast repaints."""

    async def _scenario() -> None:
        app = _ViewHost(_make_source(tmp_path, _FULL_LINE_DATA))
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


def test_hex_view_scrollbar_uses_slim_renderer(tmp_path: Path) -> None:
    """Both scrollbars render through the slim partial-block renderer (R15)."""

    async def _scenario() -> None:
        app = _ViewHost(_make_source(tmp_path, _FULL_LINE_DATA))
        async with app.run_test(size=(100, 30)):
            view = app.query_one(HexView)
            assert view.vertical_scrollbar.renderer is SlimScrollBarRender
            assert view.horizontal_scrollbar.renderer is SlimScrollBarRender

    asyncio.run(_scenario())


def test_hex_view_scrollbar_theme_follows_active(tmp_path: Path) -> None:
    """The scrollbar palette tracks the active theme (R15)."""

    async def _scenario() -> None:
        app = _ViewHost(_make_source(tmp_path, _FULL_LINE_DATA))
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


def test_hex_view_virtual_size_matches_line_count(tmp_path: Path) -> None:
    """virtual_size.height is the padded line count of the payload."""
    view = HexView(tmp_path / "sample.bin", _make_source(tmp_path, b"x" * 33))
    assert view.virtual_size.height == 3  # (33 + 15) // 16
    empty = HexView(tmp_path / "sample.bin", _make_source(tmp_path, b""))
    assert empty.virtual_size.height == 0


def test_hex_view_renders_from_chunked_source_without_full_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Rendering the first screen reads at most 2 blocks, whatever the size.

    A 1 MiB file is opened through the chunked source (64 KiB blocks);
    the block-fetch seam is counted via monkeypatch and must stay within
    two blocks -- first-screen rendering is independent of the file size.
    """
    source = _make_source(tmp_path, b"\x00" * (1024 * 1024))
    reads: list[int] = []
    original = ChunkedBinaryFile._read_block_from_disk

    def counting(self: ChunkedBinaryFile, index: int) -> bytes:
        reads.append(index)
        return original(self, index)

    monkeypatch.setattr(ChunkedBinaryFile, "_read_block_from_disk", counting)

    async def _scenario() -> None:
        app = _ViewHost(source)
        async with app.run_test(size=(100, 30)):
            view = app.query_one(HexView)
            view.render_line(0)

    asyncio.run(_scenario())
    assert len(reads) <= 2


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


def test_hex_screen_dismisses_on_q(tmp_path: Path) -> None:
    """``q`` and ``escape`` dismiss the screen."""
    source = _make_source(tmp_path, _FULL_LINE_DATA)

    async def _scenario() -> None:
        app = _ScreenHost()
        async with app.run_test(size=(100, 30)) as pilot:
            screen = HexScreen(source.path, source)
            app.push_screen(screen)
            await pilot.pause()
            assert app.screen is screen

            await pilot.press("q")
            await pilot.pause()
            assert app.screen is not screen

            app.push_screen(HexScreen(source.path, source))
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()
            assert app.screen is not screen

    asyncio.run(_scenario())


def test_hex_screen_goto_input_shows_on_g(tmp_path: Path) -> None:
    """``g`` reveals and focuses the goto-address input."""

    async def _scenario() -> None:
        app = _ScreenHost()
        async with app.run_test(size=(100, 30)) as pilot:
            screen = HexScreen(
                tmp_path / "sample.bin", _make_source(tmp_path, _FULL_LINE_DATA)
            )
            app.push_screen(screen)
            await pilot.pause()
            await pilot.press("g")
            await pilot.pause()
            goto_input = screen.query_one("#hex-goto-input", Input)
            assert goto_input.display is True
            assert goto_input.has_focus

    asyncio.run(_scenario())


def test_hex_screen_goto_input_submits_and_scrolls(tmp_path: Path) -> None:
    """Submitting a valid address scrolls the hex view to the target line."""

    async def _scenario() -> None:
        app = _ScreenHost()
        async with app.run_test(size=(100, 30)) as pilot:
            screen = HexScreen(
                tmp_path / "sample.bin", _make_source(tmp_path, b"\x00" * 1024)
            )
            app.push_screen(screen)
            await pilot.pause()
            await pilot.press("g")
            await pilot.press("0", "x", "1", "0")
            await pilot.press("enter")
            await pilot.pause()
            assert screen.query_one("#hex-view", HexView).scroll_offset.y == 1
            assert screen.query_one("#hex-goto-input", Input).display is False

    asyncio.run(_scenario())


def test_hex_screen_goto_input_escapes_without_jump(tmp_path: Path) -> None:
    """``escape`` with the input open hides it without jumping or dismissing."""

    async def _scenario() -> None:
        app = _ScreenHost()
        async with app.run_test(size=(100, 30)) as pilot:
            screen = HexScreen(
                tmp_path / "sample.bin", _make_source(tmp_path, b"\x00" * 1024)
            )
            app.push_screen(screen)
            await pilot.pause()
            await pilot.press("g")
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()
            assert screen.query_one("#hex-goto-input", Input).display is False
            assert screen.query_one("#hex-view", HexView).scroll_offset.y == 0

    asyncio.run(_scenario())


def test_hex_view_cursor_move(tmp_path: Path) -> None:
    """``move_cursor`` walks the payload and clamps at both edges."""

    async def _scenario() -> None:
        app = _ViewHost(_make_source(tmp_path, b"x" * 32))
        async with app.run_test(size=(100, 30)):
            view = app.query_one(HexView)
            view.move_cursor(5)
            assert view._cursor_pos == 5
            view.move_cursor(1000)
            assert view._cursor_pos == 31  # clamped to the last byte

    asyncio.run(_scenario())


def test_hex_view_edit_mode_toggle(tmp_path: Path) -> None:
    """``enter_edit_mode`` / ``exit_edit_mode`` flip the edit flag."""

    async def _scenario() -> None:
        app = _ViewHost(_make_source(tmp_path, b"x" * 32))
        async with app.run_test(size=(100, 30)):
            view = app.query_one(HexView)
            view.enter_edit_mode()
            assert view._edit_mode is True
            view.exit_edit_mode()
            assert view._edit_mode is False

    asyncio.run(_scenario())


def test_hex_view_edit_nibble(tmp_path: Path) -> None:
    """Two nibble presses merge into the cursor byte (high then low)."""

    async def _scenario() -> None:
        app = _ViewHost(_make_source(tmp_path, b"\x00\x00"))
        async with app.run_test(size=(100, 30)):
            view = app.query_one(HexView)
            view._cursor_pos = 0
            view._edit_mode = True
            view.edit_nibble("a")
            view.edit_nibble("b")
            assert view._source.read(0, 1) == b"\xab"

    asyncio.run(_scenario())


def test_hex_view_undo(tmp_path: Path) -> None:
    """``undo`` pops the stack and restores the overwritten byte."""

    async def _scenario() -> None:
        app = _ViewHost(_make_source(tmp_path, b"\x00"))
        async with app.run_test(size=(100, 30)):
            view = app.query_one(HexView)
            view._cursor_pos = 0
            view.edit_nibble("f")
            assert view._source.read(0, 1) == b"\xf0"
            view.undo()
            assert view._source.read(0, 1) == b"\x00"

    asyncio.run(_scenario())


def test_hex_view_ascii_sync(tmp_path: Path) -> None:
    """Editing a byte updates the ASCII echo column on the same row."""

    async def _scenario() -> None:
        app = _ViewHost(_make_source(tmp_path, b"\x00"))
        async with app.run_test(size=(100, 30)):
            view = app.query_one(HexView)
            view._cursor_pos = 0
            view.edit_nibble("4")
            view.edit_nibble("1")
            line = view.render_line(0).text.rstrip()
            assert line.endswith("A")

    asyncio.run(_scenario())


def test_hex_view_edit_undo_roundtrip_chunked(tmp_path: Path) -> None:
    """Edit then undo reads back the original byte (source-backed roundtrip)."""

    async def _scenario() -> None:
        app = _ViewHost(_make_source(tmp_path, b"\x42"))
        async with app.run_test(size=(100, 30)):
            view = app.query_one(HexView)
            view.enter_edit_mode()
            view.edit_nibble("a")
            view.edit_nibble("b")  # byte 0 -> 0xAB
            assert view._source.read(0, 1) == b"\xab"
            # one (offset, old_byte) record per nibble press
            assert view._undo_stack == [(0, 0x42), (0, 0xA2)]
            view.undo()
            assert view._source.read(0, 1) == b"\xa2"  # high-nibble state back
            view.undo()
            assert view._source.read(0, 1) == b"\x42"  # original byte back
            assert view._cursor_pos == 0  # undo parks the cursor on the byte

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
    """``save`` hands the dirty edits to the injected writer callback."""
    path = tmp_path / "test.bin"
    path.write_bytes(b"\x00" * 16)
    stat = path.stat()
    calls: list[tuple[Path, dict[int, int], float, int]] = []

    def spy(
        write_path: Path,
        write_edits: dict[int, int],
        write_mtime: float,
        write_size: int,
    ) -> None:
        calls.append((write_path, write_edits, write_mtime, write_size))

    source = ChunkedBinaryFile(path, stat.st_size, stat.st_mtime)
    screen = HexScreen(path, source, write_bytes=spy)
    screen.save()
    assert calls
    assert calls[0][0] == path
    assert calls[0][1] == {}  # no edits pending: the map is empty
    assert calls[0][2] == stat.st_mtime
    assert calls[0][3] == stat.st_size
    assert path.read_bytes() == b"\x00" * 16


def test_hex_screen_save_writes_only_dirty_bytes_inplace(tmp_path: Path) -> None:
    """A save rewrites exactly the edited bytes; the rest stays untouched."""
    original = bytes(range(256)) * 4  # 1 KiB
    path = tmp_path / "edits.bin"
    path.write_bytes(original)
    messages: list[tuple[str, str]] = []
    flows = _make_flows(messages, session=_FakeSession(None))
    source = ChunkedBinaryFile(path, len(original), path.stat().st_mtime)
    screen = HexScreen(
        path,
        source,
        message=lambda text, kind: messages.append((text, kind)),
        write_bytes=flows.write_hex_edits,
    )
    source.apply_edit(0, 0xFF)
    source.apply_edit(1000, 0xEE)

    screen.save()

    after = path.read_bytes()
    assert [i for i in range(len(original)) if after[i] != original[i]] == [0, 1000]
    assert after[0] == 0xFF
    assert after[1000] == 0xEE
    fresh = path.stat()
    assert screen._mtime == fresh.st_mtime  # new fingerprint returned
    assert screen._load_size == fresh.st_size == len(original)
    assert source.dirty_edits() == {}  # dirty set cleared after the save
    assert any(text == "saved" for text, _ in messages)


def test_hex_screen_save_gates_unchanged(tmp_path: Path) -> None:
    """The conflict and external-modification gates refuse the write-back."""
    original = b"\x00" * 16
    path = tmp_path / "gates.bin"
    path.write_bytes(original)
    messages: list[tuple[str, str]] = []

    # conflict gate: the path is open as a text document
    conflict_flows = _make_flows(messages, session=_FakeSession(path))
    conflict_source = ChunkedBinaryFile(path, 16, path.stat().st_mtime)
    conflict_source.apply_edit(0, 0x41)
    conflict_screen = HexScreen(
        path,
        conflict_source,
        message=lambda text, kind: messages.append((text, kind)),
        write_bytes=conflict_flows.write_hex_edits,
    )
    conflict_screen.save()
    assert "open in text editor" in messages[0][0]
    assert path.read_bytes() == original  # untouched

    # external-modification gate: the recorded fingerprint is stale
    messages.clear()
    modified_flows = _make_flows(messages, session=_FakeSession(None))
    stale_source = ChunkedBinaryFile(path, 16, path.stat().st_mtime + 1.0)
    stale_source.apply_edit(0, 0x41)
    stale_screen = HexScreen(
        path,
        stale_source,
        message=lambda text, kind: messages.append((text, kind)),
        write_bytes=modified_flows.write_hex_edits,
    )
    stale_screen.save()
    assert "modified externally" in messages[0][0]
    assert path.read_bytes() == original  # untouched


def test_hex_screen_save_refuses_conflict(tmp_path: Path) -> None:
    """The write-back refuses while the path is open as a text document."""
    path = tmp_path / "test.bin"
    path.write_bytes(b"\x00" * 16)
    messages: list[tuple[str, str]] = []
    flows = _make_flows(messages, session=_FakeSession(path))
    source = ChunkedBinaryFile(path, 16, path.stat().st_mtime)
    source.apply_edit(0, 0x41)  # a pending edit is needed to reach the gate
    screen = HexScreen(
        path,
        source,
        write_bytes=flows.write_hex_edits,
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
    source = ChunkedBinaryFile(path, 16, path.stat().st_mtime + 1.0)
    source.apply_edit(0, 0x41)  # a pending edit is needed to reach the gate
    screen = HexScreen(
        path,
        source,
        write_bytes=flows.write_hex_edits,
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
        ChunkedBinaryFile(tmp_path / "test.bin", 16, 0.0),
        message=lambda text, kind: messages.append((text, kind)),
        write_bytes=None,
    )
    screen.save()
    assert messages
    assert "not available" in messages[0][0]
    assert messages[0][1] == "warn"


def test_hex_screen_edit_mode_key_routing(tmp_path: Path) -> None:
    """Edit-mode key routing end to end (pilot driven).

    ``e`` enters edit mode, two digit presses merge one byte (advancing
    the cursor), the arrow keys move the byte cursor instead of
    scrolling, ``u`` restores the overwritten bytes and ``escape``
    leaves edit mode.
    """

    async def _scenario() -> None:
        app = _ScreenHost()
        async with app.run_test(size=(100, 30)) as pilot:
            screen = HexScreen(
                tmp_path / "sample.bin", _make_source(tmp_path, b"\x00" * 32)
            )
            app.push_screen(screen)
            await pilot.pause()
            view = screen.query_one("#hex-view", HexView)
            assert view.is_editing() is False

            # a non-editing key falls through untouched (R10)
            await pilot.press("x")
            await pilot.pause()
            assert view.is_editing() is False
            assert view._cursor_pos == 0

            await pilot.press("e")
            await pilot.pause()
            assert view.is_editing() is True

            # two nibble presses merge into the cursor byte (0xAB)
            await pilot.press("a")
            await pilot.press("b")
            await pilot.pause()
            assert view._source.read(0, 1)[0] == 0xAB
            assert view._cursor_pos == 1  # advanced after the low half

            # arrow keys move the byte cursor, not the scroll
            await pilot.press("right")
            await pilot.pause()
            assert view._cursor_pos == 2
            await pilot.press("up")
            await pilot.pause()
            assert view._cursor_pos == 0  # 2 - 16 clamps to the first byte

            # undo pops the two nibble records back to the original byte
            await pilot.press("u")
            await pilot.press("u")
            await pilot.pause()
            assert view._source.read(0, 1)[0] == 0x00

            # vim keys reach the screen's edit branch (only the arrows are
            # intercepted by the view itself) and ``w`` hits save()
            await pilot.press("l")
            await pilot.pause()
            assert view._cursor_pos == 1
            await pilot.press("h")
            await pilot.pause()
            assert view._cursor_pos == 0
            await pilot.press("w")  # no writer injected: silently refused
            await pilot.pause()
            assert view.is_editing() is True

            # any other key falls through in edit mode (R10)
            await pilot.press("z")
            await pilot.pause()
            assert view.is_editing() is True
            assert view._source.read(0, 1)[0] == 0x00

            await pilot.press("escape")
            await pilot.pause()
            assert view.is_editing() is False

    asyncio.run(_scenario())


def test_hex_screen_edit_mode_q_dismisses(tmp_path: Path) -> None:
    """``q`` dismisses the screen even in edit mode (current behavior).

    The dismiss branch precedes the edit branches, so ``q`` is not
    consumed as an editing key -- locked here as the documented semantic.
    """

    async def _scenario() -> None:
        app = _ScreenHost()
        async with app.run_test(size=(100, 30)) as pilot:
            screen = HexScreen(
                tmp_path / "sample.bin", _make_source(tmp_path, b"\x00" * 32)
            )
            app.push_screen(screen)
            await pilot.pause()
            view = screen.query_one("#hex-view", HexView)
            await pilot.press("e")
            await pilot.pause()
            assert view.is_editing() is True
            await pilot.press("q")
            await pilot.pause()
            assert app.screen is not screen

    asyncio.run(_scenario())


def test_hex_view_undo_stack_capped(tmp_path: Path) -> None:
    """The undo stack keeps at most MAX_UNDO_STEPS entries, oldest dropped."""

    async def _scenario() -> None:
        app = _ViewHost(_make_source(tmp_path, b"\x00"))
        async with app.run_test(size=(100, 30)):
            view = app.query_one(HexView)
            view._cursor_pos = 0
            for _ in range(1001):
                view.edit_nibble("f")
            assert len(view._undo_stack) == MAX_UNDO_STEPS

    asyncio.run(_scenario())


def test_hex_view_edit_nibble_ignores_invalid(tmp_path: Path) -> None:
    """Non-hex-digit arguments (bad char, bad length) leave data untouched."""

    async def _scenario() -> None:
        app = _ViewHost(_make_source(tmp_path, b"\x00\x00"))
        async with app.run_test(size=(100, 30)):
            view = app.query_one(HexView)
            view._cursor_pos = 0
            view.edit_nibble("z")
            view.edit_nibble("zz")
            assert view._source.read(0, 2) == b"\x00\x00"
            assert view._undo_stack == []

    asyncio.run(_scenario())


def test_hex_view_undo_empty_stack_noop(tmp_path: Path) -> None:
    """Undo on an empty stack is a no-op (no crash, no data change)."""

    async def _scenario() -> None:
        app = _ViewHost(_make_source(tmp_path, b"\x42"))
        async with app.run_test(size=(100, 30)):
            view = app.query_one(HexView)
            view.undo()
            assert view._source.read(0, 1) == b"\x42"

    asyncio.run(_scenario())


def test_hex_view_dirty_edits_returns_copy(tmp_path: Path) -> None:
    """dirty_edits returns a snapshot copy; mutating it leaves data intact."""

    async def _scenario() -> None:
        app = _ViewHost(_make_source(tmp_path, b"\x01\x02"))
        async with app.run_test(size=(100, 30)):
            view = app.query_one(HexView)
            view._cursor_pos = 0
            view.edit_nibble("f")
            snapshot = view.dirty_edits()
            assert isinstance(snapshot, dict)
            snapshot[0] = 0xFF
            assert view.dirty_edits() == {0: 0xF1}  # internal edits intact
            assert view._source.read(0, 1) == b"\xf1"

    asyncio.run(_scenario())


def test_hex_view_edit_cursor_reversed_render(tmp_path: Path) -> None:
    """In edit mode the cursor byte renders reversed (on_accent on accent)."""

    async def _scenario() -> None:
        app = _ViewHost(_make_source(tmp_path, b"\x00\x00"))
        async with app.run_test(size=(100, 30)):
            view = app.query_one(HexView)
            view.enter_edit_mode()  # cursor defaults to byte 0
            segments = list(view.render_line(0))
            t = theme.active()
            first = segments[1]
            assert first.text == "00"
            assert first.style is not None
            assert first.style.color is not None
            assert first.style.color.get_truecolor().hex == t.on_accent
            assert first.style.bgcolor is not None
            assert first.style.bgcolor.get_truecolor().hex == t.accent
            # the neighbour byte keeps its plain classification color
            assert _segment_hex(segments[2]) == t.fg_dim

    asyncio.run(_scenario())


def test_hex_screen_save_failure_reports(tmp_path: Path) -> None:
    """A writer raising OSError is reported as ``save failed`` on the line."""
    messages: list[tuple[str, str]] = []

    def boom(
        write_path: Path,
        write_edits: dict[int, int],
        write_mtime: float,
        write_size: int,
    ) -> tuple[float, int] | None:
        raise OSError("disk full")

    screen = HexScreen(
        tmp_path / "test.bin",
        ChunkedBinaryFile(tmp_path / "test.bin", 16, 0.0),
        message=lambda text, kind: messages.append((text, kind)),
        write_bytes=boom,
    )
    screen.save()
    assert messages
    assert messages[0][0].startswith("save failed")
    assert messages[0][1] == "warn"


def test_hex_screen_save_silent_without_message_callback(tmp_path: Path) -> None:
    """save() stays quiet when no message callback is injected.

    Covers the three ``message is None`` arms: no writer (refused), a
    failing writer and a successful writer returning the fingerprint --
    the last one still refreshes the baseline.
    """
    refused = HexScreen(
        tmp_path / "a.bin", ChunkedBinaryFile(tmp_path / "a.bin", 16, 0.0)
    )
    refused.save()  # write not available, silent
    assert refused._mtime == 0.0  # untouched

    def boom(
        write_path: Path,
        write_edits: dict[int, int],
        write_mtime: float,
        write_size: int,
    ) -> tuple[float, int] | None:
        raise OSError("disk full")

    failed = HexScreen(
        tmp_path / "b.bin",
        ChunkedBinaryFile(tmp_path / "b.bin", 16, 0.0),
        write_bytes=boom,
    )
    failed.save()  # save failed, silent
    assert failed._mtime == 0.0  # untouched

    path = tmp_path / "c.bin"
    path.write_bytes(b"\x00" * 16)
    load_mtime = path.stat().st_mtime

    def writer(
        write_path: Path,
        write_edits: dict[int, int],
        write_mtime: float,
        write_size: int,
    ) -> tuple[float, int] | None:
        return (write_mtime + 1.0, write_size)

    saved = HexScreen(
        path,
        ChunkedBinaryFile(path, 16, load_mtime),
        write_bytes=writer,
    )
    saved.save()  # success, silent -- the fingerprint still refreshes
    assert saved._mtime == load_mtime + 1.0  # writer's value rode back in
    assert saved._load_size == 16


def test_hex_screen_save_refreshes_fingerprint_for_resave(tmp_path: Path) -> None:
    """A successful save refreshes the stat fingerprint (W-1 regression lock).

    Wired to the real ``OverlayFlows.write_hex_edits``: after the first
    save the file's post-write stat rides back into the screen baseline,
    so an immediate second save on the same screen is not refused as
    ``modified externally`` and lands the second edit on disk.
    """

    async def _scenario() -> None:
        path = tmp_path / "test.bin"
        path.write_bytes(b"\x00" * 16)
        messages: list[tuple[str, str]] = []
        flows = _make_flows(messages, session=_FakeSession(None))
        app = _ScreenHost()
        async with app.run_test(size=(100, 30)) as pilot:
            screen = HexScreen(
                path,
                ChunkedBinaryFile(path, 16, path.stat().st_mtime),
                message=lambda text, kind: messages.append((text, kind)),
                write_bytes=flows.write_hex_edits,
            )
            app.push_screen(screen)
            await pilot.pause()
            view = screen.query_one("#hex-view", HexView)

            view.enter_edit_mode()
            view.edit_nibble("4")
            view.edit_nibble("1")  # byte 0 -> 0x41 ('A')
            screen.save()
            await pilot.pause()
            assert path.read_bytes() == b"A" + b"\x00" * 15
            fresh = path.stat()
            assert screen._mtime == fresh.st_mtime
            assert screen._load_size == fresh.st_size == 16
            assert any(text == "saved" for text, _ in messages)
            assert not any("modified externally" in text for text, _ in messages)

            # second edit + save on the same screen must still succeed
            view.edit_nibble("5")  # byte 1 high half
            view.edit_nibble("6")  # byte 1 -> 0x56 ('V')
            screen.save()
            await pilot.pause()
            assert path.read_bytes() == b"AV" + b"\x00" * 14
            assert not any("modified externally" in text for text, _ in messages)
            assert sum(1 for text, _ in messages if text == "saved") == 2

    asyncio.run(_scenario())
