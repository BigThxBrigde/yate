"""L2 behaviour of the docked quickfix panel.

The panel paints one line per entry (or a placeholder), consumes only
the four handled keys (R10), and wires the R13 theme attach/detach plus
the R15 scrollbar helper pair exactly once per mount/unmount cycle.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path
from typing import cast, override

import pytest
from textual.app import App, ComposeResult
from textual.events import Key
from textual.widget import Widget
from textual.widgets import Static

import yate.editor_components.quickfix_panel as quickfix_panel
from yate.editor_components import theme
from yate.editor_components.quickfix_panel import QuickFixPanel
from yate.session import QuickFixEntry, QuickFixList

from conftest import plain_text, wait_until


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
    """Minimal host app that mounts the panel under test."""

    def __init__(self, panel: QuickFixPanel) -> None:
        super().__init__()
        self._panel = panel

    @override
    def compose(self) -> ComposeResult:
        yield self._panel


def _entry(label: str) -> QuickFixEntry:
    """Build a minimal entry with distinct provider / severity / position."""
    return QuickFixEntry(
        provider="diagnostics", severity="error", path=Path("src/app.py"),
        row=4, col=2, label=label,
    )


def _panel(entries: QuickFixList, picked: list[int], closed: list[None]) -> QuickFixPanel:
    """Build a panel wired to recording callbacks."""
    return QuickFixPanel(entries, on_pick=picked.append, on_close=lambda: closed.append(None))


def test_panel_renders_entries_and_empty_state() -> None:
    """Entries paint with provider, severity, location and caret; empty
    lists paint the placeholder after a repaint."""
    async def scenario() -> None:
        qf = QuickFixList()
        qf.replace("diagnostics", [_entry("boom"), _entry("bang")], "diagnostics")
        panel = _panel(qf, [], [])
        app = _Host(panel)
        async with app.run_test(size=(100, 30)):
            body = panel.query_one("#quickfix-body", Static)
            text = plain_text(body.content)
            assert "diagnostics" in text
            assert "error" in text
            assert "app.py" in text
            # 1-based line and column
            assert "app.py:5:3" in text
            lines = text.splitlines()
            caret_lines = [line for line in lines if line.startswith(">")]
            assert len(caret_lines) == 1
            assert "boom" in caret_lines[0]
            qf.clear()
            panel._paint()  # pyright: ignore[reportPrivateUsage] - test seam
            assert "(no results)" in plain_text(
                panel.query_one("#quickfix-body", Static).content
            )

    asyncio.run(scenario())


def test_panel_up_down_enter_escape_consume_only_handled_keys() -> None:
    """Handled keys move the cursor / fire callbacks and are stopped; an
    unhandled key falls through untouched."""
    async def scenario() -> None:
        qf = QuickFixList()
        qf.replace("diagnostics", [_entry("one"), _entry("two"), _entry("three")], "diagnostics")
        picked: list[int] = []
        closed: list[None] = []
        panel = _panel(qf, picked, closed)
        app = _Host(panel)
        async with app.run_test(size=(100, 30)):
            # up from 0 wraps to the last entry, then down twice lands on 1
            stub_up = _StubKey("up")
            panel.on_key(cast(Key, cast(object, stub_up)))
            assert qf.selected == 2
            stub_down = _StubKey("down")
            panel.on_key(cast(Key, cast(object, stub_down)))
            panel.on_key(cast(Key, cast(object, stub_down)))
            assert qf.selected == 1
            assert stub_up.stop_called and stub_up.prevent_default_called
            assert stub_down.stop_called and stub_down.prevent_default_called
            stub_enter = _StubKey("enter")
            panel.on_key(cast(Key, cast(object, stub_enter)))
            stub_escape = _StubKey("escape")
            panel.on_key(cast(Key, cast(object, stub_escape)))
            assert stub_enter.stop_called and stub_escape.stop_called
            stub_x = _StubKey("x")
            panel.on_key(cast(Key, cast(object, stub_x)))
            assert not stub_x.stop_called
            assert not stub_x.prevent_default_called
            assert qf.selected == 1
        assert picked == [1]
        assert len(closed) == 1

    asyncio.run(scenario())


def test_narrow_viewport_renders_one_physical_line_per_entry() -> None:
    """A long entry in a narrow viewport is chopped to a single row and
    the selected entry scrolls to its own row."""
    async def scenario() -> None:
        qf = QuickFixList()
        entries = [_entry(f"e{i}") for i in range(30)]
        entries.append(_entry("x" * 200))
        qf.replace("diagnostics", entries, "diagnostics")
        qf.selected = 30
        picked: list[int] = []
        closed: list[None] = []
        panel = _panel(qf, picked, closed)
        app = _Host(panel)
        async with app.run_test(size=(40, 8)) as pilot:
            # The mount-time paint may run before layout reports a size;
            # repaint after the viewport is laid out so the scroll reveal
            # sees the real height instead of the pre-layout zero.
            await wait_until(pilot, lambda: panel.size.height > 0)
            panel.repaint()
            # The first paint fills the body; Textual learns the new
            # virtual height on the next layout pass.  Repaint once more
            # after that pass so the reveal sees a non-zero scroll range.
            await wait_until(pilot, lambda: panel.max_scroll_y > 0)
            panel.repaint()
            await pilot.pause()
            body = panel.query_one("#quickfix-body", Static)
            lines = plain_text(body.content).splitlines()
            # One entry, one physical row -- no wrapped continuation.
            assert len(lines) == 31
            assert "boom" not in " ".join(lines[1:])
            long_line = lines[30]
            assert long_line.startswith("> ")
            assert len(long_line) <= 40
            # The stored label itself is never trimmed.
            assert len(qf.entries[30].label) == 200
            # The selected (last) entry scrolled into the viewport: with
            # one physical row per entry the offset lands the selected
            # row inside the visible range (clamped to the max scroll).
            top = panel.scroll_offset.y
            assert top > 0
            assert top <= 30 < top + panel.size.height

    asyncio.run(scenario())


def test_panel_attaches_theme_and_scrollbar_helpers(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mount calls the R15 slim helper, paints (theme scrollbar) and
    subscribes (R13) in order; unmount unsubscribes exactly once."""
    calls: list[str] = []

    def _fake_attach(widget: Widget, repaint: Callable[[], None]) -> None:
        calls.append("attach")

    def _fake_detach(widget: Widget) -> None:
        calls.append("detach")

    def _fake_slim(widget: Widget) -> None:
        calls.append("slim")

    def _fake_scrollbar_theme(widget: Widget) -> None:
        calls.append("scrollbar_theme")

    monkeypatch.setattr(theme, "attach", _fake_attach)
    monkeypatch.setattr(theme, "detach", _fake_detach)
    monkeypatch.setattr(quickfix_panel, "apply_slim_scrollbars", _fake_slim)
    monkeypatch.setattr(quickfix_panel, "apply_scrollbar_theme", _fake_scrollbar_theme)

    async def scenario() -> None:
        qf = QuickFixList()
        qf.replace("diagnostics", [_entry("boom")], "diagnostics")
        panel = _panel(qf, [], [])
        app = _Host(panel)
        async with app.run_test(size=(100, 30)):
            pass
        assert calls == ["slim", "scrollbar_theme", "attach", "detach"]

    asyncio.run(scenario())
