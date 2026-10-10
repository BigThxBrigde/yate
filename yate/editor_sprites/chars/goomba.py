"""Goomba screensaver sprite: 2 frames, 16x11 px (original approximation)."""

from __future__ import annotations

from yate.editor_sprites.render import Frame, Palette

from yate.editor_sprites.chars._shared import SHARED

FRAMES: tuple[Frame, ...] = (
    (
        "....EEEEEEEE....",
        "...EEEEEEEEEE...",
        "..EEEEEEEEEEEE..",
        ".EEEEEEEEEEEEEE.",
        ".EWWKEEEEEEKWWE.",
        "EEWWKEEEEEEKWWEE",
        "EEEEEEEEEEEEEEEE",
        ".ECCCCCCCCCCCCE.",
        "..CCCCCCCCCCCC..",
        "..DDD......DDD..",
        ".DDDD......DDDD.",
    ),
    (
        "....EEEEEEEE....",
        "...EEEEEEEEEE...",
        "..EEEEEEEEEEEE..",
        ".EEEEEEEEEEEEEE.",
        ".EWWKEEEEEEKWWE.",
        "EEWWKEEEEEEKWWEE",
        "EEEEEEEEEEEEEEEE",
        ".ECCCCCCCCCCCCE.",
        "..CCCCCCCCCCCC..",
        "...DDD....DDD...",
        "....DDD..DDD....",
    ),
)

PALETTE: Palette = SHARED
