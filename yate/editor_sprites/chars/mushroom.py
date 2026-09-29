"""Super mushroom screensaver sprite: 2 frames, 14x11 px (original approximation)."""

from __future__ import annotations

from yate.editor_sprites.render import Frame, Palette

from ._shared import SHARED

FRAMES: tuple[Frame, ...] = (
    (
        "....RRRRRR....",
        "..RRWWRRRRWW..",
        ".RWWWWRRRWWWR.",
        ".RWWWWRRRWWWR.",
        "RRWWRRRRRRWWRR",
        "RRRRRRRRRRRRRR",
        ".CCCCCCCCCCCC.",
        ".CCKKCCCCKKCC.",
        ".CCKKCCCCKKCC.",
        "..CCCCCCCCCC..",
        "...CCCCCCCC...",
    ),
    (
        "....WWWWWW....",
        "..WWRRWWWWRR..",
        ".WRRRRWWWRRRR.",
        ".WRRRRWWWRRRR.",
        "WWRRWWWWWWRRWW",
        "WWWWWWWWWWWWWW",
        ".CCCCCCCCCCCC.",
        ".CCKKCCCCKKCC.",
        ".CCKKCCCCKKCC.",
        "..CCCCCCCCCC..",
        "...CCCCCCCC...",
    ),
)

PALETTE: Palette = SHARED
