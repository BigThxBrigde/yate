"""Tests for yate.editor_view.scrollbars (slim scrollbar renderer)."""

from __future__ import annotations

from rich.color import Color
from rich.segment import Segments

from textual.scrollbar import ScrollBar

from yate.editor_view.scrollbars import (
    SlimScrollBarRender,
    install_slim_scrollbars,
)

#: Track/thumb colors far apart in hue so assertions can rely on glyphs.
_BACK = Color.parse("#181825")
_BAR = Color.parse("#45475a")


def _segments_text(renderable: Segments) -> str:
    """Concatenate the raw text of a rendered segment strip."""
    return "".join(seg.text for seg in renderable.segments)


def test_horizontal_thumb_is_a_quarter_height_block() -> None:
    """A horizontal thumb paints bottom-anchored ▂ cells, not full cells."""
    strip = SlimScrollBarRender.render_bar(
        size=20,
        virtual_size=100,
        window_size=50,
        position=25,
        thickness=1,
        vertical=False,
        back_color=_BACK,
        bar_color=_BAR,
    )
    text = _segments_text(strip)
    assert "\u2582" in text  # ▂ thumb glyph present
    # half the virtual window -> thumb covers half of the 20 cells
    assert text.count("\u2582") == 10


def test_vertical_thumb_is_a_half_width_block() -> None:
    """A vertical thumb paints right-anchored ▐ cells, not full cells."""
    strip = SlimScrollBarRender.render_bar(
        size=10,
        virtual_size=100,
        window_size=50,
        position=50,
        thickness=1,
        vertical=True,
        back_color=_BACK,
        bar_color=_BAR,
    )
    text = _segments_text(strip)
    assert "\u2590" in text  # ▐ thumb glyph present
    assert text.count("\u2590") == 5


def test_no_scroll_renders_track_only() -> None:
    """Window equals virtual size: all track, no thumb glyph anywhere."""
    strip = SlimScrollBarRender.render_bar(
        size=10,
        virtual_size=50,
        window_size=50,
        position=0,
        thickness=1,
        vertical=False,
        back_color=_BACK,
        bar_color=_BAR,
    )
    text = _segments_text(strip)
    assert "\u2582" not in text and "\u2590" not in text


def test_install_points_scrollbar_renderer_at_slim() -> None:
    """install_slim_scrollbars() wires Textual's documented renderer hook."""
    install_slim_scrollbars()
    assert ScrollBar.renderer is SlimScrollBarRender
