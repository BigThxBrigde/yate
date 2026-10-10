"""Galaga fighter screensaver sprite: 2 frames, 15x10 px (original approximation)."""

from __future__ import annotations

from yate.editor_sprites.render import Frame, Palette

from yate.editor_sprites.chars._shared import SHARED

FRAMES: tuple[Frame, ...] = (
    (
        ".......W.......",
        "......WWW......",
        "......WRW......",
        ".....WRRRW.....",
        "..W..WRRRW..W..",
        ".WWW.WRRRW.WWW.",
        ".WWWWWRRRWWWWW.",
        ".WBWWWWRWWWWBW.",
        "..WWWWWWWWWWW..",
        "...W..W.W..W...",
    ),
    (
        ".......W.......",
        "......WWW......",
        "......WRW......",
        ".....WRRRW.....",
        "..W..WRRRW..W..",
        ".WWW.WRRRW.WWW.",
        ".WWWWWRRRWWWWW.",
        ".WBWWWWRWWWWBW.",
        "..WWWWWWWWWWW..",
        "....WWWWWWW....",
    ),
)

PALETTE: Palette = SHARED
