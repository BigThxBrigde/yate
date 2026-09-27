"""Pac-Man screensaver sprite: 2 frames, 14x11 px (original approximation)."""

from __future__ import annotations

from yate.editor_sprites.render import Frame, Palette

from ._shared import SHARED

FRAMES: tuple[Frame, ...] = (
    (
        "....YYYYYY....",
        "..YYYYYYYYYY..",
        ".YYYYYYYYYYYY.",
        "YYYYYYYYY.....",
        "YYYYYYYY......",
        "YYYYYY........",
        "YYYYYYYY......",
        "YYYYYYYYY.....",
        ".YYYYYYYYYYYY.",
        "..YYYYYYYYYY..",
        "....YYYYYY....",
    ),
    (
        "....YYYYYY....",
        "..YYYYYYYYYY..",
        ".YYYYYYYYYYYY.",
        "YYYYYYYYYYYYY.",
        "YYYYYYYYYYYY..",
        "YYYYYYYYY.....",
        "YYYYYYYYYYYY..",
        "YYYYYYYYYYYYY.",
        ".YYYYYYYYYYYY.",
        "..YYYYYYYYYY..",
        "....YYYYYY....",
    ),
)

PALETTE: Palette = SHARED
