"""Duck screensaver sprite: 2 frames, 18x12 px (original approximation)."""

from __future__ import annotations

from yate.editor_sprites.render import Frame, Palette

from yate.editor_sprites.chars._shared import SHARED

FRAMES: tuple[Frame, ...] = (
    (
        "......LLLL........",
        ".....LLLLLL.......",
        ".....LKLLLL.OOO...",
        ".....LLLLLL.O.....",
        ".....LLLLLL.......",
        "LL...LLLLL........",
        ".LLLLLLLLLLLLL....",
        "..LLLLLLLLLLLLL...",
        "...LLLLLLLLLL.....",
        "....LLLLLL........",
        ".....OO..OO.......",
        ".....OO..OO.......",
    ),
    (
        "......LLLL........",
        ".....LLLLLL.......",
        ".....LKLLLL.OOO...",
        ".....LLLLLL.O.....",
        ".....LLLLLL.......",
        "LL...LLLLL........",
        ".LLLLLLLLLLLLL....",
        "..LLLLLLLLLLLLL...",
        "...LLLLLLLLLL.....",
        "....LLLLLL........",
        "....OOO...OOO.....",
        "....OO....OO......",
    ),
)

PALETTE: Palette = SHARED
