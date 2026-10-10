"""Samus Aran screensaver sprite: 2 frames, 14x12 px (original approximation)."""

from __future__ import annotations

from yate.editor_sprites.render import Frame, Palette

from yate.editor_sprites.chars._shared import SHARED

FRAMES: tuple[Frame, ...] = (
    (
        "...OOOOOO.....",
        "..OOGGGGOO....",
        "..OOGGGGOO....",
        "..OOOOOOOO....",
        "...RRRRRR.....",
        ".OORRRRRROO...",
        ".OORROORROO...",
        "..OOOOOOOO....",
        "..OOO..OOO....",
        "..RRR..RRR....",
        "..RRR..RRR....",
        ".RRR....RRR...",
    ),
    (
        "...OOOOOO.....",
        "..OOGGGGOO....",
        "..OOGGGGOO....",
        "..OOOOOOOO....",
        "...RRRRRR.....",
        ".OORRRRRROO...",
        ".OORROORROO...",
        "..OOOOOOOO....",
        "..OOO..OOO....",
        ".RRR....RRR...",
        ".RR......RR...",
        ".RR......RR...",
    ),
)

PALETTE: Palette = SHARED
