"""Link screensaver sprite: 2 frames, 12x12 px (original approximation)."""

from __future__ import annotations

from yate.editor_sprites.render import Frame, Palette

from ._shared import SHARED

FRAMES: tuple[Frame, ...] = (
    (
        "....GGG.....",
        "...GGGGG....",
        "...SSSSS....",
        "...SVSVS....",
        "...SSSSS....",
        "..GGGGGGG...",
        ".SGGGGGGGS..",
        ".SGGGGGGGS..",
        "..GGGGGGG...",
        "..GGGGGGG...",
        "...SS.SS....",
        "...NN.NN....",
    ),
    (
        "....GGG.....",
        "...GGGGG....",
        "...SSSSS....",
        "...SVSVS....",
        "...SSSSS....",
        "..GGGGGGG...",
        ".SGGGGGGGS..",
        ".SGGGGGGGS..",
        "..GGGGGGG...",
        "..GGGGGGG...",
        "..SS...SS...",
        ".NN.....NN..",
    ),
)

PALETTE: Palette = SHARED
