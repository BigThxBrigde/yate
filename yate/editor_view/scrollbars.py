"""Slim scrollbar rendering: thumbs drawn as partial-block slivers.

Textual paints scrollbar thumbs as reversed spaces -- a solid full cell,
i.e. a one-row band for horizontal bars and a one-column strip for vertical
ones.  Issue IKINF3 asks for something visually lighter: this renderer keeps
the one-cell scrollbar geometry (hit targets and scrolling behavior are
untouched) but paints the thumb with an anchored partial-block glyph, so it
reads as a sliver only a fraction of a cell thick.

Installed app-wide via :func:`install_slim_scrollbars`, using Textual's
documented :attr:`ScrollBar.renderer` hook.
"""

from __future__ import annotations

from math import ceil
from typing import ClassVar, override

from rich.color import Color
from rich.segment import Segment, Segments
from rich.style import Style

from textual.scrollbar import ScrollBar, ScrollBarRender


class SlimScrollBarRender(ScrollBarRender):
    """Scrollbar renderer that paints the thumb as a thin partial block."""

    #: Bottom-anchored glyph for horizontal thumbs -- a quarter-cell line.
    HORIZONTAL_THUMB: ClassVar[str] = "\u2582"  # ▂

    #: Right-anchored glyph for vertical thumbs -- a half-cell column.
    VERTICAL_THUMB: ClassVar[str] = "\u2590"  # ▐

    @override
    @classmethod
    def render_bar(
        cls,
        size: int = 25,
        virtual_size: float = 50,
        window_size: float = 20,
        position: float = 0,
        thickness: int = 1,
        vertical: bool = True,
        back_color: Color = Color.parse("#555555"),
        bar_color: Color = Color.parse("bright_magenta"),
    ) -> Segments:
        """Render a scrollbar strip with a thin partial-block thumb.

        Mirrors :meth:`ScrollBarRender.render_bar` -- segment layout, mouse
        metadata and the 1/8-cell position granularity -- but paints the
        thumb body with the class' partial-block glyph instead of a reversed
        space, so the thumb covers only a fraction of the cell.
        """
        thumb = cls.VERTICAL_THUMB if vertical else cls.HORIZONTAL_THUMB
        width = thickness if vertical else 1
        back = Style(bgcolor=back_color)
        grab = Style(
            color=bar_color, bgcolor=back_color, meta={"@mouse.down": "grab"}
        )

        segments: list[Segment]
        if (
            not (window_size and size and virtual_size)
            or window_size >= virtual_size
        ):
            # Nothing to scroll: a bare track, no thumb.
            segments = [Segment(" " * width, back)] * size
        else:
            upper = Style(bgcolor=back_color, meta={"@mouse.down": "scroll_up"})
            lower = Style(bgcolor=back_color, meta={"@mouse.down": "scroll_down"})
            segments = [Segment(" " * width, upper)] * size

            bar_ratio = virtual_size / size
            thumb_size = max(1, window_size / bar_ratio)
            position_ratio = position / (virtual_size - window_size)
            start = int((size - thumb_size) * position_ratio * 8)
            end = start + ceil(thumb_size * 8)
            start_index = max(0, start) // 8
            end_index = max(0, end) // 8

            segments[end_index:] = [Segment(" " * width, lower)] * (size - end_index)
            segments[start_index:end_index] = [Segment(thumb * width, grab)] * (
                end_index - start_index
            )
        if vertical:
            return Segments(segments, new_lines=True)
        return Segments((segments + [Segment.line()]) * thickness, new_lines=False)


def install_slim_scrollbars() -> None:
    """Point every Textual scrollbar at the slim renderer.

    Idempotent; called once from :class:`yate.app.YateApp`.  Only the
    painted glyph changes -- grabbing, hovering and click-to-scroll keep
    working because the mouse metadata on each segment is preserved.
    """
    ScrollBar.renderer = SlimScrollBarRender
