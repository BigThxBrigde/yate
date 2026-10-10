"""Bomberman screensaver sprite: 2 frames, 14x14 px (original approximation)."""

from __future__ import annotations

from yate.editor_sprites.render import Frame, Palette

from yate.editor_sprites.chars._shared import SHARED

FRAMES: tuple[Frame, ...] = (
    (
        "......P.......",
        ".....PPP......",
        "...WWWWWWWW...",
        "..WWWWWWWWWW..",
        "..WVWWWWWWVW..",
        "..WWWWWWWWWW..",
        "...WWWWWWWW...",
        "..BBBBBBBBBB..",
        ".WWBBBBBBBBWW.",
        ".WWBBBBBBBBWW.",
        "..BBBBBBBBBB..",
        "..RRRRRRRRRR..",
        "...BB....BB...",
        "..PPP....PPP..",
    ),
    (
        "......P.......",
        ".....PPP......",
        "...WWWWWWWW...",
        "..WWWWWWWWWW..",
        "..WVWWWWWWVW..",
        "..WWWWWWWWWW..",
        "...WWWWWWWW...",
        "..BBBBBBBBBB..",
        ".WWBBBBBBBBWW.",
        ".WWBBBBBBBBWW.",
        "..BBBBBBBBBB..",
        "..RRRRRRRRRR..",
        "...BB..BB.....",
        "..PPP...PPP...",
    ),
)

PALETTE: Palette = SHARED
