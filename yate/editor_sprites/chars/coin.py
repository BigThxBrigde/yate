"""Spinning coin screensaver sprite: 4 frames, 10x8 px (original approximation)."""

from __future__ import annotations

from yate.editor_sprites.render import Frame, Palette

from yate.editor_sprites.chars._shared import SHARED

FRAMES: tuple[Frame, ...] = (
    (
        "..YYYYYY..",
        ".YYYYYYYY.",
        ".YYYWWYYY.",
        ".YYYWWYYY.",
        ".YYYWWYYY.",
        ".YYYWWYYY.",
        ".YYYYYYYY.",
        "..YYYYYY..",
    ),
    (
        "...YYYY...",
        "...YYYY...",
        "...YWYY...",
        "...YWYY...",
        "...YWYY...",
        "...YWYY...",
        "...YYYY...",
        "...YYYY...",
    ),
    (
        "....YY....",
        "....YY....",
        "....YY....",
        "....YY....",
        "....YY....",
        "....YY....",
        "....YY....",
        "....YY....",
    ),
    (
        "...YYYY...",
        "...YYYY...",
        "...YWYY...",
        "...YWYY...",
        "...YWYY...",
        "...YWYY...",
        "...YYYY...",
        "...YYYY...",
    ),
)

PALETTE: Palette = SHARED
