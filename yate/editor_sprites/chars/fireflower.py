"""Fire flower screensaver sprite: 2 frames, 12x10 px (original approximation)."""

from __future__ import annotations

from yate.editor_sprites.render import Frame, Palette

from yate.editor_sprites.chars._shared import SHARED

FRAMES: tuple[Frame, ...] = (
    (
        "...RRRRRR...",
        "..RRYYYYRR..",
        "..RRYYYYRR..",
        "...RRRRRR...",
        ".....GG.....",
        ".G..GGG..G..",
        ".GG.GGG.GG..",
        "..GGGGGGG...",
        "...GGGGG....",
        "....GGG.....",
    ),
    (
        "...OOOOOO...",
        "..OOYYYYOO..",
        "..OOYYYYOO..",
        "...OOOOOO...",
        ".....GG.....",
        ".G..GGG..G..",
        ".GG.GGG.GG..",
        "..GGGGGGG...",
        "...GGGGG....",
        "....GGG.....",
    ),
)

PALETTE: Palette = SHARED
