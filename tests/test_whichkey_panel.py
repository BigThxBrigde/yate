"""Runtime tests for the which-key panel (WhichKeyPanel renderer).

Pilot-driven (headless Textual): a minimal host app mounts the panel, the
tests push entries through ``show_entries`` / ``clear`` and assert on the
rendered text, the truncation hint, the theme repaint path (R13) and the
R10 guarantee that the panel never consumes a key event.
"""

from __future__ import annotations

import asyncio
from typing import Any, override

from textual.app import App, ComposeResult
from textual.events import Key
from textual.widgets import Static

from yate.editor_view import theme
from yate.editor_view.whichkey import MAX_ROWS, ChordEntry, WhichKeyPanel

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


class _Host(App[None]):
    """Minimal host app mounting the panel plus the key probe."""

    def __init__(self) -> None:
        super().__init__()
        self.panel = WhichKeyPanel()
        self.probe = _KeyProbe()

    @override
    def compose(self) -> ComposeResult:
        yield self.panel
        yield self.probe


def test_show_entries_renders_header_and_grid() -> None:
    """show_entries reveals the panel and paints header plus grid rows."""

    async def scenario() -> None:
        host = _Host()
        async with host.run_test(size=(80, 24)):
            host.panel.show_entries(
                "2d",
                [
                    ChordEntry("dd", "Delete line"),
                    ChordEntry("{motion}", "Delete over motion"),
                ],
            )
            assert host.panel.display is True
            text = plain_text(host.panel.render())
            assert "2d" in text
            assert "dd" in text
            assert "Delete line" in text
            assert "{motion}" in text

    asyncio.run(scenario())


def test_clear_hides_panel() -> None:
    """clear() blanks the content and hides the panel again."""

    async def scenario() -> None:
        host = _Host()
        async with host.run_test(size=(80, 24)):
            host.panel.show_entries("2d", [ChordEntry("dd", "Delete line")])
            host.panel.clear()
            assert host.panel.display is False
            assert plain_text(host.panel.render()) == ""

    asyncio.run(scenario())


def test_entries_over_max_rows_truncate_with_hint() -> None:
    """Beyond MAX_ROWS the grid truncates and the F1 hint line appears."""

    async def scenario() -> None:
        entries = [ChordEntry(f"k{i:02d}", f"desc {i}") for i in range(20)]
        host = _Host()
        async with host.run_test(size=(80, 24)):
            host.panel.show_entries("", entries)
            text = plain_text(host.panel.render())
            rows = [line for line in text.splitlines() if "desc" in line]
            assert len(rows) <= MAX_ROWS
            assert "more" in text
            assert "F1" in text

    asyncio.run(scenario())


def test_empty_entries_with_header_keeps_header() -> None:
    """A count-only state (header, no entries) still renders the header."""

    async def scenario() -> None:
        host = _Host()
        async with host.run_test(size=(80, 24)):
            host.panel.show_entries('"', [])
            text = plain_text(host.panel.render())
            assert host.panel.display is True
            assert '"' in text
            assert text.strip() == '"'  # header only, no key column rows

    asyncio.run(scenario())


def test_theme_change_repaints_panel() -> None:
    """A theme broadcast repaints the mounted panel without raising."""

    async def scenario() -> None:
        host = _Host()
        async with host.run_test(size=(80, 24)):
            host.panel.show_entries("2d", [ChordEntry("dd", "Delete line")])
            theme.set_theme("latte")
            assert host.panel.display is True
            assert "2d" in plain_text(host.panel.render())

    try:
        asyncio.run(scenario())
    finally:
        theme.set_theme("mocha")


def test_panel_never_consumes_key_events() -> None:
    """A key press reaches the focused widget un-stopped (R10 guard)."""

    async def scenario() -> None:
        host = _Host()
        async with host.run_test(size=(80, 24)) as pilot:
            host.panel.show_entries("2d", [ChordEntry("dd", "Delete line")])
            host.probe.focus()
            await pilot.pause()
            await pilot.press("x")
            # the key arrived at its focus target: no sibling ate it
            assert host.probe.seen == ["x"]
            assert host.panel.has_focus is False

    asyncio.run(scenario())
