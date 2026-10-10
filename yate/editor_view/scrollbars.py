"""Slim scrollbar rendering: thumbs drawn as partial-block slivers.

Textual paints scrollbar thumbs as reversed spaces -- a solid full cell,
i.e. a one-row band for horizontal bars and a one-column strip for vertical
ones.  Issue IKINF3 asks for something visually lighter: this renderer keeps
the one-cell scrollbar geometry (hit targets and scrolling behavior are
untouched) but paints the thumb with an anchored partial-block glyph, so it
reads as a sliver only a fraction of a cell thick.

Wired per widget via :func:`apply_slim_scrollbars` (Textual's documented
per-widget ``ScrollBar.renderer`` hook) -- no process-global patching.
"""

from __future__ import annotations

from math import ceil
from typing import ClassVar, override

from rich.color import Color
from rich.segment import Segment, Segments
from rich.style import Style
from textual.color import Color as TextualColor
from textual.scrollbar import ScrollBarRender
from textual.widget import Widget

from yate.editor_view import theme


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


def apply_slim_scrollbars(widget: Widget) -> None:
    """Point *widget*'s own scrollbars at the slim renderer.

    Per-widget injection (no process-global patch): Textual creates scrollbar
    widgets lazily on first property access, so reading ``vertical_scrollbar``
    / ``horizontal_scrollbar`` here fetches -- and creates, if needed -- the
    instances; assigning the instance attribute overrides the
    ``ScrollBar.renderer`` class default, Textual's documented hook.  Only
    the painted glyph changes -- grabbing, hovering and click-to-scroll keep
    working because the mouse metadata on each segment is preserved.
    """
    # renderer is declared ClassVar upstream (typing spec frowns on instance
    # assignment), yet per-widget override is Textual's own documented usage
    # (scrollbar.py docstring) -- setattr makes that intent explicit.
    vertical = widget.vertical_scrollbar
    horizontal = widget.horizontal_scrollbar
    setattr(vertical, "renderer", SlimScrollBarRender)
    setattr(horizontal, "renderer", SlimScrollBarRender)


def apply_scrollbar_theme(widget: Widget) -> None:
    """Paint *widget*'s scrollbar palette from the active theme.

    Shared tail of the per-component ``_apply_theme`` implementations
    (editor view, explorer, diff panes): the track is fully transparent --
    ``ScrollBar`` composites alpha<1 over the parent background -- so only
    the thin partial-block thumb shows (issue IKINF3); a faint tint
    appears on hover, the thumb brightens on drag.
    """
    t = theme.active()
    s = widget.styles
    s.scrollbar_background = TextualColor(0, 0, 0, 0)
    s.scrollbar_background_hover = TextualColor.parse(t.surface).with_alpha(0.35)
    s.scrollbar_color = t.border
    s.scrollbar_color_hover = t.fg_dim
    s.scrollbar_color_active = t.accent
    s.scrollbar_corner_color = TextualColor(0, 0, 0, 0)
