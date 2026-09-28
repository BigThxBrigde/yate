"""Ice Climber screensaver sprite: 2 frames, 12x11 px (original approximation)."""

from __future__ import annotations

from yate.editor_sprites.render import Frame, Palette

from ._shared import SHARED

FRAMES: tuple[Frame, ...] = (
    (
        "...AAAAAA...",
        "..AAAAAAAA..",
        "..ASSSSSSA..",
        "..ASVSSVSA..",
        "..ASSSSSSA..",
        "...AAAAAA...",
        "..AAAAAAA...",
        ".AAAAAAAAA..",
        ".AAAAAAAAA..",
        "..AAAAAA....",
        "..QQ..QQ....",
    ),
    (
        "...AAAAAA...",
        "..AAAAAAAA..",
        "..ASSSSSSA..",
        "..ASVSSVSA..",
        "..ASSSSSSA..",
        "...AAAAAA...",
        "..AAAAAAA...",
        ".AAAAAAAAA..",
        ".AAAAAAAAA..",
        "..AAAA......",
        "..QQ..QQ....",
    ),
)

PALETTE: Palette = SHARED
