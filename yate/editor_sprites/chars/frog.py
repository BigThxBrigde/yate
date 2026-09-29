"""Frog screensaver sprite: 2 frames, 18x10 px (original approximation)."""

from __future__ import annotations

from yate.editor_sprites.render import Frame, Palette

from ._shared import SHARED

FRAMES: tuple[Frame, ...] = (
    (
        "...FF........FF...",
        "..FFWK......KWFF..",
        "..FFFFFFFFFFFFFF..",
        ".FFFFFFFFFFFFFFFF.",
        "FFFFFFFFFFFFFFFFFF",
        "FFFFFFFFFFFFFFFFFF",
        ".FFFCFFFFFFFFFFC..",
        "..FFFFFFFFFFFFFF..",
        ".FFF.FF....FF.FFF.",
        "FFF...F....F...FFF",
    ),
    (
        "...FF........FF...",
        "..FFWK......KWFF..",
        "..FFFFFFFFFFFFFF..",
        ".FFFFFFFFFFFFFFFF.",
        "FFFFFFFFFFFFFFFFFF",
        "FFFFFFFFFFFFFFFFFF",
        ".FFFFFFFFFFFFFFFF.",
        "..FFFFFFFFFFFFFF..",
        "...FFF......FFF...",
        "...FF........FF...",
    ),
)

PALETTE: Palette = SHARED
