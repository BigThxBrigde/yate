"""Mario screensaver sprite: 3 frames, 14x17 px (original approximation)."""

from __future__ import annotations

from yate.editor_sprites.render import Frame, Palette

from yate.editor_sprites.chars._shared import SHARED

FRAMES: tuple[Frame, ...] = (
    (
        "....RRRRRR....",
        "...RRRRRRRRR..",
        "...HHSSSSKS...",
        "..HSSSSSSKSS..",
        "..HHSSSSSSSS..",
        "...SMMMMMMS...",
        "....SSSSSS....",
        "...RRRBBRRR...",
        "..RRRBBBBRRR..",
        "..RRBBBBBBRR..",
        ".SSRBBBBBBRSS.",
        ".SSBBBBBBBBSS.",
        "..BBBBBBBBBB..",
        "..BBBB..BBBB..",
        "..BBB....BBB..",
        "..NNN....NNN..",
        ".NNNN....NNNN.",
    ),
    (
        "....RRRRRR....",
        "...RRRRRRRRR..",
        "...HHSSSSKS...",
        "..HSSSSSSKSS..",
        "..HHSSSSSSSS..",
        "...SMMMMMMS...",
        "....SSSSSS....",
        "...RRRBBRRR...",
        "..RRRBBBBRRR..",
        "..RRBBBBBBRR..",
        ".SSRBBBBBBRSS.",
        ".SSBBBBBBBBSS.",
        "..BBBBBBBBBB..",
        "..BBBBBBBBB...",
        "...BBBBBB.....",
        "...NNNNNN.....",
        "..NNNNNN......",
    ),
    (
        "....RRRRRR....",
        "...RRRRRRRRR..",
        "...HHSSSSKS...",
        "..HSSSSSSKSS..",
        "..HHSSSSSSSS..",
        "...SMMMMMMS...",
        "....SSSSSS....",
        "...RRRBBRRR...",
        "..RRRBBBBRRR..",
        "..RRBBBBBBRR..",
        ".SSRBBBBBBRSS.",
        ".SSBBBBBBBBSS.",
        "..BBBBBBBBBB..",
        "..BBBB..BBBB..",
        "...BBB..BBB...",
        "...NNN..NNN...",
        "..NNNN..NNNN..",
    ),
)

PALETTE: Palette = SHARED
