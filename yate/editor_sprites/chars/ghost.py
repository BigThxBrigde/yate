"""Pac-man ghost template: one body shape recolored per ghost (16x10 px, original approximation)."""

from __future__ import annotations

from yate.editor_sprites.render import Frame, Palette

from ._shared import SHARED

FRAMES: tuple[Frame, ...] = (
    (
        "....CCCCCCCC....",
        "..CCCCCCCCCCCC..",
        ".CCWWKCCCCKWWCC.",
        ".CCWWKCCCCKWWCC.",
        ".CCCCCCCCCCCCCC.",
        ".CCCCCCCCCCCCCC.",
        ".CCCCCCCCCCCCCC.",
        ".CCCCCCCCCCCCCC.",
        ".CC.CC.CC.CC.CC.",
        ".CC.CC.CC.CC.CC.",
    ),
    (
        "....CCCCCCCC....",
        "..CCCCCCCCCCCC..",
        ".CCKWWCCCCKWWCC.",
        ".CCKWWCCCCKWWCC.",
        ".CCCCCCCCCCCCCC.",
        ".CCCCCCCCCCCCCC.",
        ".CCCCCCCCCCCCCC.",
        ".CCCCCCCCCCCCCC.",
        ".CC.CC.CC.CC.CC.",
        "..C.CC.CC.CC.CC.",
    ),
)

def palette(color: str) -> Palette:
    """Build one ghost's palette: body recolored to *color*."""
    return {"C": color, "W": SHARED["W"], "K": SHARED["K"]}
