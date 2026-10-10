"""Mega Man screensaver sprite: 2 frames, 14x15 px (original approximation)."""

from __future__ import annotations

from yate.editor_sprites.render import Frame, Palette

from yate.editor_sprites.chars._shared import SHARED

FRAMES: tuple[Frame, ...] = (
    (
        "....AAAAAA....",
        "...AAAAAAAA...",
        "..AAAAAAAAAA..",
        "..AXXXXXXXA...",
        "..AXVXXVXXA...",
        "..AXXXXXXXA...",
        "...AAAAAAA....",
        "..AAAAAAAAAA..",
        ".AABBBBBBBBAA.",
        ".AABBBBBBBBAA.",
        "..BBBBBBBBBB..",
        "..BBB....BBB..",
        "..XXX....XXX..",
        ".XXXX....XXXX.",
        "..............",
    ),
    (
        "....AAAAAA....",
        "...AAAAAAAA...",
        "..AAAAAAAAAA..",
        "..AXXXXXXXA...",
        "..AXVXXVXXA...",
        "..AXXXXXXXA...",
        "...AAAAAAA....",
        "..AAAAAAAAAA..",
        ".AABBBBBBBBAA.",
        ".AABBBBBBBBAA.",
        "..BBBBBBBBBB..",
        "..BBBBBBBBB...",
        ".BBB....BBB...",
        ".XXX.....XXX..",
        "XXXX.....XXXX.",
    ),
)

PALETTE: Palette = SHARED
