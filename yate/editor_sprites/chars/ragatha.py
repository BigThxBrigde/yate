"""Ragatha screensaver sprite: 2 frames, 14x17 px (original approximation)."""

from __future__ import annotations

from yate.editor_sprites.render import Frame, Palette

from yate.editor_sprites.chars._shared import SHARED

FRAMES: tuple[Frame, ...] = (
    (
        "....OOOOOO....",
        "..OOOOOOOOOO..",
        ".OOOOOOOOOOOO.",
        ".OOOLLLLLLLLOO",
        ".OOOLLVLLVLLOO",
        ".OOOLLLLLLLLOO",
        ".OOLTLTTTTLLOO",
        ".OOOLLLLLLLLOO",
        "..OOLLLLLLLOO.",
        "...OOLLLLOOO..",
        "....BBBBBB....",
        "...BBBBBBBB...",
        "..BWBBBBWBBB..",
        "..BBBBBBBBBB..",
        "..BBBBBBBBBB..",
        "...BB....BB...",
        "...LL....LL...",
    ),
    (
        "....OOOOOO....",
        "..OOOOOOOOOO..",
        ".OOOOOOOOOOOO.",
        ".OOOLLLLLLLLOO",
        ".OOOLLLLLLLLOO",
        ".OOOLLLLLLLLOO",
        ".OOLTLTTTTLLOO",
        ".OOOLLLLLLLLOO",
        "..OOLLLLLLLOO.",
        "...OOLLLLOOO..",
        "....BBBBBB....",
        "...BBBBBBBB...",
        "..BWBBBBWBBB..",
        "..BBBBBBBBBB..",
        "..BBBBBBBBBB..",
        "...BB....BB...",
        "...LL....LL...",
    ),
)

PALETTE: Palette = SHARED
