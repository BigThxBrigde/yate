"""Snake screensaver sprite: 2 frames, 25x7 px (original approximation)."""

from __future__ import annotations

from yate.editor_sprites.render import Frame, Palette

from ._shared import SHARED

FRAMES: tuple[Frame, ...] = (
    (
        "....GGGGG................",
        "...GGGGGGG...............",
        "..GG.....GG...GGGGG......",
        ".GG.......GG.GGGGGGG.....",
        "GG.........GGG.....GG....",
        "............G.......GGG..",
        "......................GT.",
    ),
    (
        "....GGGGG................",
        "...GGGGGGG...............",
        "..GG.....GG....GGGGG.....",
        ".GG.......GG..GGGGGGG....",
        "GG.........GG.G......GG..",
        ".............GG.......GT.",
        ".........................",
    ),
)

PALETTE: Palette = SHARED
