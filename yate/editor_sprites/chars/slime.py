"""Slime screensaver sprite: 2 frames, 12x10 px (original approximation)."""

from __future__ import annotations

from yate.editor_sprites.render import Frame, Palette

from yate.editor_sprites.chars._shared import SHARED

FRAMES: tuple[Frame, ...] = (
    (
        ".....BB.....",
        "....BBBB....",
        "...BBBBBB...",
        "..BBBBBBBB..",
        "..BWVBBVWB..",
        "..BBBBBBBB..",
        ".BBBBBBBBBB.",
        ".BBBBBBBBBB.",
        ".BBBBBBBBBB.",
        "..BBBBBBBB..",
    ),
    (
        "............",
        "............",
        "....BBBB....",
        "...BBBBBB...",
        "..BWVBBVWB..",
        ".BBBBBBBBBB.",
        "BBBBBBBBBBBB",
        "BBBBBBBBBBBB",
        "BBBBBBBBBBBB",
        ".BBBBBBBBBB.",
    ),
)

PALETTE: Palette = SHARED
