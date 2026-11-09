"""Tests for the hover docs popup (plan e).

Geometry and state run without a Textual app (the widget's ``show`` /
``close`` only touch their own state until a body is mounted); mounting,
theme subscription and scrollbar wiring use ``app.run_test()`` pilots with
theme snapshots -- no real sleeps.
"""

from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path
from typing import Callable, cast, override

import pytest
from rich.markdown import Markdown
from textual.app import App, ComposeResult
from textual.color import Color
from textual.widgets import Static
from textual.widget import Widget

from yate.editor_components import hover_popup, theme
from yate.editor_components.hover_popup import HoverPopup

REPO_ROOT = Path(__file__).resolve().parent.parent


def _popup() -> HoverPopup:
    """A popup in its post-mount state (no app needed for these paths)."""
    widget = HoverPopup()
    widget.on_mount()
    return widget


def _origin(popup: HoverPopup) -> tuple[float, float]:
    """The popup's (x, y) offset in cells, as ``show`` left it."""
    return popup.styles.offset.x.value, popup.styles.offset.y.value


def _box_size(popup: HoverPopup) -> tuple[float, float]:
    """The popup's (width, height) in cells, as ``show`` left it."""
    width = popup.styles.width
    height = popup.styles.height
    assert width is not None and height is not None
    return width.value, height.value


def _popup_text(popup: HoverPopup) -> str:
    """The docs string the popup currently holds (private attr, test seam)."""
    return cast(str, getattr(popup, "_text"))


def _popup_repaint(popup: HoverPopup) -> Callable[[], None]:
    """The popup's private repaint callback (private attr, test seam)."""
    return cast(Callable[[], None], getattr(popup, "_apply_theme"))


# --- spy recorders (module-level, fully annotated; cleared per test) -----------

_slim_calls: list[Widget] = []
_scrollbar_calls: list[Widget] = []
_attach_calls: list[tuple[Widget, Callable[[], None]]] = []
_detach_calls: list[Widget] = []


def _reset_spies() -> None:
    """Empty every spy recorder before a test installs its patches."""
    _slim_calls.clear()
    _scrollbar_calls.clear()
    _attach_calls.clear()
    _detach_calls.clear()


def _record_slim_scrollbars(widget: Widget) -> None:
    """Spy for :func:`apply_slim_scrollbars`."""
    _slim_calls.append(widget)


def _record_scrollbar_theme(widget: Widget) -> None:
    """Spy for :func:`apply_scrollbar_theme`."""
    _scrollbar_calls.append(widget)


def _record_theme_attach(widget: Widget, repaint: Callable[[], None]) -> None:
    """Spy for :func:`yate.editor_components.theme.attach`."""
    _attach_calls.append((widget, repaint))


def _record_theme_detach(widget: Widget) -> None:
    """Spy for :func:`yate.editor_components.theme.detach`."""
    _detach_calls.append(widget)


class _Host(App[None]):
    """A minimal app mounting one hover popup (id frozen by R9)."""

    @override
    def compose(self) -> ComposeResult:
        yield HoverPopup(id="hover-docs")


# --- empty / whitespace docs -------------------------------------------------


@pytest.mark.parametrize("text", ["", "  \n "], ids=["empty", "whitespace"])
def test_show_with_empty_or_whitespace_text_closes_card(text: str) -> None:
    """Blank docs hide the card instead of an empty box (AC5 defence 2)."""
    popup = _popup()
    popup.show(text, (0, 0), (80, 24), 2)
    assert popup.is_open is False
    assert popup.display is False


# --- geometry (no-App construction) ------------------------------------------


def test_show_positions_card_below_anchor() -> None:
    """A card with room below opens one row under the cursor column."""
    popup = _popup()
    popup.show("alpha docs", (10, 5), (80, 24), 6, origin_y=2)
    assert _origin(popup) == (16, 8)


def test_show_flips_above_when_bottom_overflows() -> None:
    """A card with no room below opens above the anchor, inside the editor."""
    popup = _popup()
    text = "\n\n".join(f"para {i}" for i in range(10))
    popup.show(text, (5, 22), (80, 24), 2)
    _x, y = _origin(popup)
    height = _box_size(popup)[1]
    assert y < 22  # above the anchor row
    assert y >= 0  # never above the editor top
    assert y + height <= 0 + 24  # fully inside the editor


def test_show_clamps_x_when_card_would_overflow_right_edge() -> None:
    """A card wider than the room right of the cursor is pulled back inside."""
    popup = _popup()
    popup.show("alpha docs", (78, 3), (80, 24), 2)
    x, _y = _origin(popup)
    assert x == 80 - _box_size(popup)[0]
    assert x >= 0


def test_long_text_caps_card_height() -> None:
    """Many rows never grow the card past MAX_ROWS (+ border rows)."""
    popup = _popup()
    text = "\n\n".join(f"line {i}" for i in range(40))
    popup.show(text, (0, 0), (80, 40), 0)
    assert popup.styles.height is not None
    assert popup.styles.height.value <= HoverPopup.MAX_ROWS


def test_card_never_grabs_focus() -> None:
    """The hover card stays non-focusable at class and instance level."""
    popup = _popup()
    assert HoverPopup.can_focus is False
    assert popup.can_focus is False


# --- markdown body (mounted) --------------------------------------------------


def test_show_renders_markdown_source_in_body() -> None:
    """The body Static holds a ``Markdown`` renderable of the raw source."""

    async def scenario() -> None:
        app = _Host()
        async with app.run_test() as pilot:
            await pilot.pause()
            popup = app.query_one(HoverPopup)
            text = "**f()** docs"
            popup.show(text, (0, 0), (80, 24), 2)
            await pilot.pause()
            body = popup.query_one("#hover-docs-body", Static)
            assert isinstance(body.content, Markdown)
            assert body.content.markup == text
            assert popup.is_open is True

    asyncio.run(scenario())


def test_close_hides_card_and_clears_body() -> None:
    """Closing hides the card, drops the docs and empties the body."""

    async def scenario() -> None:
        app = _Host()
        async with app.run_test() as pilot:
            await pilot.pause()
            popup = app.query_one(HoverPopup)
            popup.show("docs here", (0, 0), (80, 24), 2)
            await pilot.pause()
            popup.close()
            await pilot.pause()
            assert popup.display is False
            assert _popup_text(popup) == ""
            body = popup.query_one("#hover-docs-body", Static)
            assert body.content == ""

    asyncio.run(scenario())


# --- mount / theme / unmount wiring (R13 / R15) -------------------------------


def test_mount_applies_scrollbar_pair_and_theme_subscription(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mount wires the slim scrollbar pair and subscribes to the theme."""
    _reset_spies()
    monkeypatch.setattr(
        hover_popup, "apply_slim_scrollbars", _record_slim_scrollbars
    )
    monkeypatch.setattr(
        hover_popup, "apply_scrollbar_theme", _record_scrollbar_theme
    )
    monkeypatch.setattr(theme, "attach", _record_theme_attach)

    async def scenario() -> None:
        app = _Host()
        async with app.run_test() as pilot:
            await pilot.pause()
            popup = app.query_one(HoverPopup)
            assert _slim_calls == [popup]
            assert _scrollbar_calls == [popup]
            assert _attach_calls == [(popup, _popup_repaint(popup))]

    asyncio.run(scenario())


def test_theme_change_repaints_scrollbar_theme(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A repaint repaints the scrollbar palette from the active theme."""
    _reset_spies()
    monkeypatch.setattr(
        hover_popup, "apply_scrollbar_theme", _record_scrollbar_theme
    )

    async def scenario() -> None:
        app = _Host()
        async with app.run_test() as pilot:
            await pilot.pause()
            popup = app.query_one(HoverPopup)
            assert _scrollbar_calls == [popup]  # painted on mount
            _popup_repaint(popup)()
            await pilot.pause()
            assert len(_scrollbar_calls) == 2
            assert popup.styles.background == Color.parse(
                theme.active().panel
            )

    asyncio.run(scenario())


def test_unmount_detaches_theme_listener(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unmount unsubscribes the popup from theme broadcasts."""
    _reset_spies()
    monkeypatch.setattr(theme, "detach", _record_theme_detach)

    async def scenario() -> None:
        app = _Host()
        async with app.run_test() as pilot:
            await pilot.pause()
            popup = app.query_one(HoverPopup)
            assert _detach_calls == []
            await popup.remove()
            await pilot.pause()
            assert _detach_calls == [popup]

    asyncio.run(scenario())


# --- R15 architecture guard ----------------------------------------------------


def test_architecture_scrollbar_pair_guard_covers_new_widget() -> None:
    """The architecture suite's R15 scan passes with the new widget present.

    Loads ``tests/test_architecture.py`` in-process and runs its
    ``test_scrollable_widgets_apply_theme_scrollbar_pair`` guard directly --
    no nested pytest subprocess (which interferes with pytest-cov + xdist
    in the outer run).
    """
    spec = importlib.util.spec_from_file_location(
        "test_architecture_guard",
        REPO_ROOT / "tests" / "test_architecture.py",
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    guard = getattr(
        module, "test_scrollable_widgets_apply_theme_scrollbar_pair"
    )
    cast(Callable[[], None], guard)()
