"""Super star screensaver sprite: 2 frames, 14x12 px (original approximation)."""

from __future__ import annotations

from yate.editor_sprites.render import Frame, Palette

from ._shared import SHARED

FRAMES: tuple[Frame, ...] = (
    (
        "......YY......",
        ".....YYYY.....",
        ".....YYYY.....",
        "YYYYYYYYYYYYYY",
        "YYYYYYYYYYYYYY",
        ".YYYYYYYYYYYY.",
        "..YYKYYYYKYY..",
        "...YYYYYYYY...",
        "..YYYYYYYYYY..",
        "..YYY....YYY..",
        ".YYY......YYY.",
        "YYY........YYY",
    ),
    (
        "......YY......",
        ".....YYYY.....",
        ".....YYYY.....",
        "YYYYYYYYYYYYYY",
        "YYYYYYYYYYYYYY",
        ".YYYYYYYYYYYY.",
        "..YYYYYYYYYY..",
        "...YYYYYYYY...",
        "..YYYYYYYYYY..",
        "..YYY....YYY..",
        ".YYY......YYY.",
        "YYY........YYY",
    ),
)

PALETTE: Palette = SHARED
