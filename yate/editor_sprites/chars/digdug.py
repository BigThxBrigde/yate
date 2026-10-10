"""Dig Dug screensaver sprite: 2 frames, 12x12 px (original approximation)."""

from __future__ import annotations

from yate.editor_sprites.render import Frame, Palette

from yate.editor_sprites.chars._shared import SHARED

FRAMES: tuple[Frame, ...] = (
    (
        "...WWWWWW...",
        "..WWWWWWWW..",
        "..WBBWWBBW..",
        "..WWWWWWWW..",
        "..RRRRRRRR..",
        ".WRRRRRRRRW.",
        ".WRRRRRRRRW.",
        "..RRRRRRRR..",
        "..WWWWWWWW..",
        "...WW..WW...",
        "...BB..BB...",
        "..BBB..BBB..",
    ),
    (
        "...WWWWWW...",
        "..WWWWWWWW..",
        "..WBBWWBBW..",
        "..WWWWWWWW..",
        "..RRRRRRRR..",
        ".WRRRRRRRRW.",
        ".WRRRRRRRRW.",
        "..RRRRRRRR..",
        "..WWWWWWWW..",
        "..WW....WW..",
        "..BB....BB..",
        ".BBB....BBB.",
    ),
)

PALETTE: Palette = SHARED
