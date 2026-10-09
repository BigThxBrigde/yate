"""Character geometry helpers: terminal cell widths, truncation and tabs.

Theme independent by design -- this module depends on the standard library
(:mod:`unicodedata`) only.  Split from :mod:`yate.editor_view.theme`
(big-module-split wave d); consumers may import through the
:mod:`yate.editor_view.theme` facade or directly from here.

Cell model: a combining mark / format character occupies 0 cells, a wide
East-Asian glyph or emoji occupies 2, everything else 1.  A ``\\t`` counts as
one cell in :func:`cell_len` / :func:`cell_width` and is expanded to the
next tab stop in :func:`char_to_cell` / :func:`cell_to_char` /
:func:`expand_char`.
"""

from __future__ import annotations

import unicodedata

__all__ = [
    "cell_len",
    "cell_to_char",
    "cell_width",
    "char_to_cell",
    "expand_char",
    "truncate_to_cells",
]


def cell_width(ch: str) -> int:
    """Terminal cell width of *ch* (0 combining, 2 wide CJK/emoji, 1 else)."""
    if ch == "\t":
        return 1
    if unicodedata.combining(ch) or unicodedata.category(ch) in ("Mn", "Me", "Cf"):
        return 0
    if unicodedata.east_asian_width(ch) in ("W", "F"):
        return 2
    return 1


def cell_len(text: str) -> int:
    """Display cell length of *text* (wide glyphs count 2, combining 0)."""
    return sum(1 if ch == "\t" else cell_width(ch) for ch in text)


def truncate_to_cells(text: str, max_cells: int) -> str:
    """Truncate *text* to at most *max_cells* display cells."""
    if max_cells <= 0:
        return ""
    out: list[str] = []
    cells = 0
    for ch in text:
        w = 1 if ch == "\t" else cell_width(ch)
        if cells + w > max_cells:
            break
        out.append(ch)
        cells += w
    return "".join(out)


def char_to_cell(line: str, char_index: int, tab_width: int = 4) -> int:
    """Map a character index to its display cell column."""
    cells = 0
    for i, ch in enumerate(line):
        if i >= char_index:
            break
        if ch == "\t":
            cells += tab_width - (cells % tab_width)
        else:
            cells += max(1, cell_width(ch))
    return cells


def cell_to_char(line: str, cell: int, tab_width: int = 4) -> int:
    """Map a display *cell* column back to a character index."""
    cells = 0
    for i, ch in enumerate(line):
        if cells >= cell:
            return i
        if ch == "\t":
            cells += tab_width - (cells % tab_width)
        else:
            cells += max(1, cell_width(ch))
    return len(line)


def expand_char(ch: str, cells: list[str], tab_width: int) -> None:
    """Append *ch* to *cells* with tabs expanded / wide glyphs doubled."""
    if ch == "\t":
        cells.extend([" "] * (tab_width - (len(cells) % tab_width)))
        return
    w = cell_width(ch)
    if w == 0 and cells:  # combining mark attaches to previous cell
        cells[-1] += ch
    elif w == 2:
        cells.append(ch)
        cells.append("")
    else:
        cells.append(ch)
