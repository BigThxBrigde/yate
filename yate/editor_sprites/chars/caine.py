"""Caine screensaver sprite: 2 frames, 16x16 px (original approximation)."""

from __future__ import annotations

from yate.editor_sprites.render import Frame, Palette

from ._shared import SHARED

FRAMES: tuple[Frame, ...] = (
    (
        ".....KKKKKK.....",
        ".....KKKKKK.....",
        "..KKKKKKKKKKKK..",
        "....PPPPPPPP....",
        "...WWKWWWWKWW...",
        "...WWWWWWWWWW...",
        "...WWVWWVWWVW...",
        "...WWWWWWWWWW...",
        "..KKKKKKKKKKKK..",
        "...RRRRRRRRRR...",
        "..RRRRRRRRRRRR..",
        ".LLRRRRRRRRRRLL.",
        "..RRRRRRRRRRRR..",
        "..RRR......RRR..",
        "..RR........RR..",
        "..KK........KK..",
    ),
    (
        ".....KKKKKK.....",
        ".....KKKKKK.....",
        "..KKKKKKKKKKKK..",
        "....PPPPPPPP....",
        "...WKWWWWWWKW...",
        "...WWWWWWWWWW...",
        "...WWVWWVWWVW...",
        "...WWWWWWWWWW...",
        "..KKKKKKKKKKKK..",
        "...RRRRRRRRRR...",
        "..RRRRRRRRRRRR..",
        ".LLRRRRRRRRRRLL.",
        "..RRRRRRRRRRRR..",
        "..RRR......RRR..",
        "..RR........RR..",
        "..KK........KK..",
    ),
)

PALETTE: Palette = SHARED
