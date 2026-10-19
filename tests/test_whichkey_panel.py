"""Runtime tests for the which-key panel (WhichKeyPanel renderer).

Pilot-driven (headless Textual): a minimal host app mounts the panel in
a container that declares the ``whichkey`` layer (Textual 8.2.8
guarantees layer ordering only when the parent declares the name),
the tests push entries through ``show_entries`` / ``clear`` and assert
on the border-title / on the rendered text, the truncation, the theme
repaint path (R13) and the R10 guarantee that the panel never consumes
a key event.

Layout note (Lightweight-test anchor): the panel is absolute-positioned
inside a parent of known size; ``on_resize`` re-anchors it, the tests
let the layout settle before checking the offset.
"""

from __future__ import annotations

import asyncio
from typing import Any, override

from textual.app import App, ComposeResult
from textual.events import Key
from textual.widget import Widget
from textual.widgets import Static

from yate.editor_view import theme
from yate.editor_view.whichkey import (
    MAX_ROWS,
    ChordEntry,
    EditorColumn,
    WhichKeyPanel,
)

from conftest import plain_text


class _KeyProbe(Static):
    """Focusable witness recording every key it receives (R10 proof).

    The probe deliberately does not stop the event either: recording the
    key un-stopped shows the press flowed through instead of being eaten
    by the panel.
    """

    can_focus = True

    def __init__(self, **kwargs: Any) -> None:
        super().__init__("", **kwargs)
        self.seen: list[str] = []

    def on_key(self, event: Key) -> None:
        """Record *event* without stopping its propagation."""
        self.seen.append(event.key)


class _LayerHost(App[None]):
    """Minimal host: an EditorColumn declaring the whichkey layer.

    The container tracks the terminal size (100% x 100%), exactly like
    ``#editor-col`` in production, so ``pilot.resize_terminal`` drives the
    real ``EditorColumn.on_resize`` forwarding path.  The panel is yielded
    inside the container, exactly like ``Editor.compose`` does.
    """

    DEFAULT_CSS = """
    Screen { layout: vertical; }
    #layer-box { width: 100%; height: 100%; layers: default whichkey; }
    WhichKeyPanel { layer: whichkey; }
    """

    def __init__(self) -> None:
        super().__init__()
        self.panel = WhichKeyPanel()
        self.probe = _KeyProbe()

    @override
    def compose(self) -> ComposeResult:
        with EditorColumn(id="layer-box"):
            yield self.panel
            yield self.probe


def test_show_entries_renders_header_and_grid() -> None:
    """show_entries reveals the panel and paints header plus grid rows."""

    async def scenario() -> None:
        host = _LayerHost()
        async with host.run_test(size=(80, 24)):
            host.panel.show_entries(
                "2d",
                [
                    ChordEntry("dd", "Delete line"),
                    ChordEntry("{motion}", "Delete over motion"),
                ],
            )
            assert host.panel.display is True
            assert host.panel.border_title == "2d"
            text = plain_text(host.panel.render())
            assert "dd" in text
            assert "Delete line" in text
            assert "{motion}" in text

    asyncio.run(scenario())


def test_clear_hides_panel() -> None:
    """clear() blanks the content and the title and hides the panel again."""

    async def scenario() -> None:
        host = _LayerHost()
        async with host.run_test(size=(80, 24)):
            host.panel.show_entries("2d", [ChordEntry("dd", "Delete line")])
            host.panel.clear()
            assert host.panel.display is False
            assert host.panel.border_title == ""
            assert plain_text(host.panel.render()) == ""

    asyncio.run(scenario())


def test_entries_over_max_rows_truncate_with_hint() -> None:
    """Beyond MAX_ROWS the grid truncates and the F1 hint line appears."""

    async def scenario() -> None:
        entries = [ChordEntry(f"k{i:02d}", f"desc {i}") for i in range(20)]
        host = _LayerHost()
        async with host.run_test(size=(80, 24)):
            host.panel.show_entries("", entries)
            text = plain_text(host.panel.render())
            rows = [line for line in text.splitlines() if "desc" in line]
            assert len(rows) <= MAX_ROWS
            assert "more" in text
            assert "F1" in text

    asyncio.run(scenario())


def test_empty_entries_with_header_keeps_header() -> None:
    """A count-only state (header, no entries) carries the header title."""

    async def scenario() -> None:
        host = _LayerHost()
        async with host.run_test(size=(80, 24)):
            host.panel.show_entries('"', [])
            assert host.panel.display is True
            assert host.panel.border_title == '"'
            # Content area is empty: the header lives in the border title.
            assert plain_text(host.panel.render()).strip() == ""

    asyncio.run(scenario())


def test_theme_change_repaints_panel() -> None:
    """A theme broadcast repaints the mounted panel without raising."""

    async def scenario() -> None:
        host = _LayerHost()
        async with host.run_test(size=(80, 24)):
            host.panel.show_entries("2d", [ChordEntry("dd", "Delete line")])
            theme.set_theme("latte")
            assert host.panel.display is True
            assert host.panel.border_title == "2d"

    try:
        asyncio.run(scenario())
    finally:
        theme.set_theme("mocha")


def test_panel_never_consumes_key_events() -> None:
    """A key press reaches the focused widget un-stopped (R10 guard)."""

    async def scenario() -> None:
        host = _LayerHost()
        async with host.run_test(size=(80, 24)) as pilot:
            host.panel.show_entries("2d", [ChordEntry("dd", "Delete line")])
            host.probe.focus()
            await pilot.pause()
            await pilot.press("x")
            # the key arrived at its focus target: no sibling ate it
            assert host.probe.seen == ["x"]
            assert host.panel.has_focus is False

    asyncio.run(scenario())


def test_panel_anchors_right_edge_when_shown() -> None:
    """show_entries places the panel on the parent's right edge."""

    async def scenario() -> None:
        host = _LayerHost()
        async with host.run_test(size=(80, 24)) as pilot:
            host.panel.show_entries(
                "2d",
                [
                    ChordEntry("dd", "Delete line"),
                    ChordEntry("{motion}", "Delete over motion"),
                ],
            )
            await pilot.pause()
            host.panel.call_after_refresh(lambda: None)  # settle
            await pilot.pause()
            parent = host.panel.parent
            assert isinstance(parent, Widget)
            parent_width = parent.region.width
            own_width = host.panel.region.width
            # right edge of the panel == parent right edge - margin
            offset_x, _ = host.panel.styles.offset
            assert offset_x.value == parent_width - own_width - 1
            assert host.panel.border_title == "2d"

    asyncio.run(scenario())


def test_panel_offsets_reset_to_origin_when_hidden() -> None:
    """While hidden, the offset write is skipped (no spurious offset)."""

    async def scenario() -> None:
        host = _LayerHost()
        async with host.run_test(size=(80, 24)):
            host.panel.clear()
            assert host.panel.display is False
            # When hidden, _place early-returns: offset stays at the
            # CSS default (0, 0) -- nothing pinned against the right
            # edge while invisible.
            offset_x, offset_y = host.panel.styles.offset
            assert (offset_x.value, offset_y.value) == (0, 0)

    asyncio.run(scenario())


def test_clear_blanks_border_title() -> None:
    """clear() wipes the border title (no stale 'VIM' lingering)."""

    async def scenario() -> None:
        host = _LayerHost()
        async with host.run_test(size=(80, 24)):
            host.panel.show_entries("vim", [])
            assert host.panel.border_title == "vim"
            host.panel.clear()
            assert host.panel.border_title == ""
            assert host.panel.display is False

    asyncio.run(scenario())


def test_container_resize_reanchors_panel() -> None:
    """EditorColumn.on_resize forwards to the panel (user-reported bug).

    The panel is absolutely positioned with an auto size, so a terminal
    resize never changes its own region and Textual's reflow never posts
    it a Resize event; the container's resize is the reliable signal.
    """

    async def scenario() -> None:
        host = _LayerHost()
        async with host.run_test(size=(80, 24)) as pilot:
            host.panel.show_entries("2d", [ChordEntry("dd", "Delete line")])
            await pilot.pause()
            await pilot.resize_terminal(100, 30)
            await pilot.pause()
            await pilot.pause()
            parent = host.panel.parent
            assert isinstance(parent, Widget)
            parent_width = parent.region.width
            own_width = host.panel.region.width
            offset_x, offset_y = host.panel.styles.offset
            assert offset_x.value == parent_width - own_width - 1
            assert offset_y.value >= 2

    asyncio.run(scenario())
