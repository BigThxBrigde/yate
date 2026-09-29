"""Half-block pixel rendering for screensaver sprites (pure logic).

A sprite frame is a grid of palette-key characters (``.`` = transparent).
The renderer maps pixels to terminal text rows two pixel rows per cell:
the upper pixel becomes the foreground of ``▀``, the lower pixel its
background -- the same mechanism bisqwit's editor uses for its status-bar
mascot and the highest-fidelity mapping a text cell allows without
terminal graphics protocols.

This module is UI-free: callers turn the returned ``(glyph, style)``
columns into text segments themselves (see
:mod:`yate.editor_view.screensaver`).
"""

from __future__ import annotations

#: A sprite frame: rows of palette-key characters (``.`` = transparent).
type Frame = tuple[str, ...]

#: A palette maps a frame's key characters to hex color strings.
type Palette = dict[str, str]


def render_rows(frame: Frame, palette: Palette) -> list[list[tuple[str, str]]]:
    """Convert one sprite frame to half-block text rows.

    Returns ``ceil(len(frame) / 2)`` rows, each a list of
    ``(glyph, style)`` columns: glyph is ``█`` / ``▀`` / ``▄`` / space and
    style is a rich color string such as ``#e52521`` or
    ``#e52521 on #2b53d6`` (empty string for transparent, so the caller's
    background shows through).  Text row *i* covers pixel rows ``2i``
    (upper half) and ``2i + 1`` (lower half).
    """
    width = max(len(row) for row in frame)
    out: list[list[tuple[str, str]]] = []
    for top in range(0, len(frame), 2):
        upper = frame[top]
        lower = frame[top + 1] if top + 1 < len(frame) else ""
        cells: list[tuple[str, str]] = []
        for x in range(width):
            fu = palette.get(upper[x]) if x < len(upper) else None
            fl = palette.get(lower[x]) if x < len(lower) else None
            if fu is not None and fl is not None:
                if fu == fl:
                    cells.append(("█", fu))
                else:
                    cells.append(("▀", f"{fu} on {fl}"))
            elif fu is not None:
                cells.append(("▀", fu))
            elif fl is not None:
                cells.append(("▄", fl))
            else:
                cells.append((" ", ""))
        out.append(cells)
    return out


def walk_x(tick: int, width: int, sprite_w: int) -> int:
    """Column of a left-to-right walking sprite's left edge.

    The sprite starts fully off-screen left (``-sprite_w``), advances one
    column per tick and wraps back after fully exiting on the right
    (``width``).  *tick* counts monotonically from 0; the caller decides
    how often a tick happens and may step several columns per animation
    frame by scaling the tick before calling.
    """
    travel = width + sprite_w
    return (tick % travel) - sprite_w
