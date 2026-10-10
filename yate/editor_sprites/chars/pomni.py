"""Pomni screensaver sprite: 2 frames, 15x16 px (original approximation)."""

from __future__ import annotations

from yate.editor_sprites.render import Frame, Palette

from yate.editor_sprites.chars._shared import SHARED

FRAMES: tuple[Frame, ...] = (
    (
        "...YR......BY..",
        "..RRRR....BBBB.",
        "..RRRRR..BBBBB.",
        "...RRRRBBBBBB..",
        "...WWWWWWWWWW..",
        "..WWWWWWWWWWWW.",
        "..WWRWWWWWWBW..",
        "..WWWWWWWWWWWW.",
        "...WWWWWWWWWW..",
        "....WWWWWWWW...",
        "...RRRBBBBRR...",
        "..RRRBBBBBBRR..",
        "..RRRBBBBBBRR..",
        "..RR..BB...BB..",
        "..RR.......BB..",
        "..NN.......NN..",
    ),
    (
        "..Y.RR....BB.Y.",
        "..RRRR....BBBB.",
        "..RRRRR..BBBBB.",
        "...RRRRBBBBBB..",
        "...WWWWWWWWWW..",
        "..WWWWWWWWWWWW.",
        "..WWWWWWWWWWWW.",
        "..WWWWWWWWWWWW.",
        "...WWWWWWWWWW..",
        "....WWWWWWWW...",
        "...RRRBBBBRR...",
        "..RRRBBBBBBRR..",
        "..RRRBBBBBBRR..",
        "..RR..BB...BB..",
        "..RR.......BB..",
        "..NN.......NN..",
    ),
)

PALETTE: Palette = SHARED
