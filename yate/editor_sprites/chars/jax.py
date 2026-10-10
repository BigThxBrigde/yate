"""Jax screensaver sprite: 2 frames, 16x22 px (original approximation)."""

from __future__ import annotations

from yate.editor_sprites.render import Frame, Palette

from yate.editor_sprites.chars._shared import SHARED

FRAMES: tuple[Frame, ...] = (
    (
        ".JJPPJJ..JJPPJJ.",
        ".JJPPJJ..JJPPJJ.",
        ".JJPPJJ..JJPPJJ.",
        ".JJPPJJ..JJPPJJ.",
        ".JJPPJJ..JJPPJJ.",
        ".JJJJJJ..JJJJJJ.",
        "..JJJJJJJJJJJJ..",
        "..JJJJJJJJJJJJ..",
        "..JYYYYYYYYYYJ..",
        "..JYVYYYYYYVYJ..",
        "..JJJJJJJJJJJJ..",
        "...JJJJJJJJJJ...",
        "...JWWWWWWWWJ...",
        "...JWJWWWWJWJ...",
        "...JWWWWWWWWJ...",
        "...JJJJJJJJJJ...",
        "..JJJJJJJJJJJJ..",
        "..JJJJJJJJJJJJ..",
        "..JJJJJ..JJJJJ..",
        "..JJJJ...JJJJ...",
        "..JJJ......JJJ..",
        "..JJ........JJ..",
    ),
    (
        ".JJPPJJ...JJPPJJ",
        ".JJPPJJ..JJPPJJ.",
        ".JJPPJJ..JJPPJJ.",
        ".JJPPJJ..JJPPJJ.",
        ".JJPPJJ..JJPPJJ.",
        ".JJJJJJ..JJJJJJ.",
        "..JJJJJJJJJJJJ..",
        "..JJJJJJJJJJJJ..",
        "..JJJJJJJJJJJJ..",
        "..JJJJJJJJJJJJ..",
        "..JJJJJJJJJJJJ..",
        "...JJJJJJJJJJ...",
        "...JWWWWWWWWJ...",
        "...JWJWWWWJWJ...",
        "...JWWWWWWWWJ...",
        "...JJJJJJJJJJ...",
        "..JJJJJJJJJJJJ..",
        "..JJJJJJJJJJJJ..",
        "..JJJJJ..JJJJJ..",
        "..JJJJ...JJJJ...",
        "..JJJ......JJJ..",
        "..JJ........JJ..",
    ),
)

PALETTE: Palette = SHARED
