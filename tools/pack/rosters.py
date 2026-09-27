"""Render the sprite roster preview SVG from the product sprite pack.

Single source of truth: reads the character registry
(:mod:`yate.editor_sprites.characters` -- the same bitmaps the screensaver
walks) and writes a self-contained SVG with one enlarged pixel-grid
section per character (1 sprite pixel = one square) plus frame-count
annotations.  Transparent pixels show as a checkerboard.

Regenerate after touching any bitmap::

    python -m tools.pack rosters
"""

from __future__ import annotations

from pathlib import Path

from yate.editor_sprites import characters
from yate.editor_sprites.render import Frame, Palette

from .icon import repo_root

#: Default output path (repository root, untracked).
DEFAULT_OUTPUT = repo_root() / "roster.svg"

#: SVG canvas background.
_BG = "#1e1e2e"
#: Checkerboard fills marking transparent sprite pixels.
_CHECKER_A = "#2a2a3c"
_CHECKER_B = "#222232"
#: Heading / annotation text colors.
_TITLE = "#cdd6f4"
_LABEL = "#a6adc8"

#: Enlarged-grid scale: screen pixels drawn per sprite pixel.
_ZOOM = 10
#: Horizontal gap between adjacent frames in a section.
_GAP = 46
#: Left padding of every section.
_PAD_X = 24
#: Canvas width -- the widest section (mario, 3 frames) fits comfortably.
_WIDTH = 760


def _label(x: float, y: float, text: str, size: int = 22,
           fill: str = _LABEL) -> str:
    """One monospace annotation line."""
    return (f'<text x="{x:g}" y="{y:g}" fill="{fill}" '
            f'font-family="monospace" font-size="{size}">{text}</text>')


def _sprite_rects(
    frame: Frame, palette: Palette, ox: float, oy: float
) -> list[str]:
    """One frame as enlarged ``<rect>`` squares; transparency checkerboarded."""
    parts: list[str] = []
    for y, row in enumerate(frame):
        for x, key in enumerate(row):
            fill = palette.get(key)
            if fill is None:
                fill = _CHECKER_A if (x + y) % 2 == 0 else _CHECKER_B
            parts.append(
                f'<rect x="{ox + x * _ZOOM:g}" y="{oy + y * _ZOOM:g}" '
                f'width="{_ZOOM}" height="{_ZOOM}" fill="{fill}"/>'
            )
    return parts


def render_roster_svg(output: Path = DEFAULT_OUTPUT) -> Path:
    """Write the roster preview SVG to *output* and return the path."""
    sections: list[str] = []
    y = 40.0
    sections.append(_label(_PAD_X, y, "yate screensaver roster -- "
                           f"{len(characters.CHARACTERS)} characters "
                           "(product bitmaps)", 28, _TITLE))
    y += 56.0

    for name, sprite in characters.CHARACTERS.items():
        frames = sprite.frames
        width, height = len(frames[0][0]), len(frames[0])
        label = name.replace("_", " ")
        sections.append(_label(_PAD_X, y,
                               f"{label}  ({width}x{height} px, "
                               f"{len(frames)} frames)"))
        y += 30.0
        x = 40.0
        for fid, frame in enumerate(frames):
            sections.append(_label(x, y + 16, f"f{fid + 1}", 18))
            sections.extend(_sprite_rects(frame, sprite.palette, x, y + 24))
            x += len(frame[0]) * _ZOOM + _GAP
        y += height * _ZOOM + 44.0

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{_WIDTH}" '
        f'height="{y:g}" viewBox="0 0 {_WIDTH} {y:g}">\n'
        f'<rect width="100%" height="100%" fill="{_BG}"/>\n'
        + "\n".join(sections)
        + "\n</svg>\n"
    )
    output.write_text(svg, encoding="utf-8")
    return output
