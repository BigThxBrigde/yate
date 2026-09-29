"""Gangle screensaver sprite: 2 frames, 14x13 px (original approximation)."""

from __future__ import annotations

from yate.editor_sprites.render import Frame, Palette

from ._shared import SHARED

FRAMES: tuple[Frame, ...] = (
    (
        "..WWWWWWWWWW..",
        ".WWWWWWWWWWWW.",
        ".WWVWWWWWWVWW.",
        ".WWWWWWWWWWWW.",
        ".WWWWWWWWWWWW.",
        ".WWWVVVVVVWWW.",
        "..WWWWWWWWWW..",
        "...TTTTTTTT...",
        "..TTTTTTTTTT..",
        ".TTTTTTTTTTTT.",
        ".TT.TTTTTT.TT.",
        ".T..TTTTTT..T.",
        "....TTTTTT....",
    ),
    (
        "..WWWWWWWWWW..",
        ".WWWWWWWWWWWW.",
        ".WWWWWWWWWWWW.",
        ".WWVWWWWWWVWW.",
        ".WWWWWWWWWWWW.",
        ".WWWVVVVVVWWW.",
        "..WWWWWWWWWW..",
        "...TTTTTTTT...",
        "..TTTTTTTTTT..",
        ".TTTTTTTTTTTT.",
        ".TT.TTTTTT.TT.",
        ".T..TTTTTT..T.",
        "....TTTTTT....",
    ),
)

PALETTE: Palette = SHARED
