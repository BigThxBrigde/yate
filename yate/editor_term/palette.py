"""The xterm 256-color palette: ANSI-16 base table and index resolution.

Pure data plus a pure function -- no emulator state, no project-internal
imports.  The VT parser resolves SGR color codes through
:func:`palette_color`; the 16-color table is the classic xterm palette.
"""

from __future__ import annotations

#: An RGB color as a ``(red, green, blue)`` triple of 0-255 components.
type RGB = tuple[int, int, int]

#: Classic xterm 16-color palette.
_ANSI_16: tuple[str, ...] = (
    "#000000", "#cc0000", "#4e9a06", "#c4a000",
    "#3465a4", "#75507b", "#06989a", "#d3d7cf",
    "#555753", "#ef2929", "#8ae234", "#fce94f",
    "#729fcf", "#ad7fa8", "#34e2e2", "#eeeeec",
)


def _hex_rgb(value: str) -> RGB:
    """Parse a ``#rrggbb`` hex string into an :obj:`RGB` triple."""
    value = value.lstrip("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


#: Pre-resolved 16-color table.
ANSI_16_RGB: tuple[RGB, ...] = tuple(_hex_rgb(c) for c in _ANSI_16)


def palette_color(index: int) -> RGB:
    """Resolve an xterm 256-color index to an RGB triple."""
    index = max(0, min(255, index))
    if index < 16:
        return ANSI_16_RGB[index]
    if index < 232:
        n = index - 16
        if n == 0:
            return (0, 0, 0)
        levels = (0, 95, 135, 175, 215, 255)
        r = levels[(n // 36) % 6]
        g = levels[(n // 6) % 6]
        b = levels[n % 6]
        return (r, g, b)
    gray = 8 + (index - 232) * 10
    return (gray, gray, gray)
