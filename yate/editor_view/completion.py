"""The LSP completion popup: a small non-focusable floating widget.

The popup never takes focus -- the editor keeps receiving keys while it is
open and :class:`~yate.editor_view.editor.EditorView` interprets
Tab/Enter/Up/Down/Esc against it.  Rendering is hand-drawn (Rich segments and
a manual box) so the size/position stay under exact control; positioning is
computed by the application and pushed in via :meth:`CompletionPopup.show`.

The same popup also shows buffer-based completions (words collected from the
open buffers plus filesystem paths) when no language server is active for the
current document -- see :func:`buffer_completions`.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Optional

from rich.segment import Segment
from rich.style import Style
from textual.css.scalar import ScalarOffset
from textual.strip import Strip
from textual.widget import Widget

from yate.editor_core.buffer import TextBuffer
from yate.editor_lsp.client import Completion
from yate.interfaces import AppProtocol

from . import theme

#: Maximum number of completion rows visible at once.
MAX_VISIBLE = 8

#: Completion item kinds reused from the LSP item kind table.
_KIND_TEXT = 0          # plain word / unknown
_KIND_FILE = 17         # "D" glyph, used for path entries here

#: Characters that count as part of an identifier prefix when completing.
_IDENT_RE = re.compile(r"[A-Za-z0-9_]")

#: A "word" in the buffer is a run of identifier characters; shorter runs are
#: noise and skipped.
_WORD_RE = re.compile(r"[A-Za-z_]\w{1,}")

#: Kind -> (letter, theme color attribute), mirroring the VS Code item kinds.
_KIND_GLYPHS: dict[int, tuple[str, str]] = {
    1: ("T", "fg"),
    2: ("m", "syn_function"),
    3: ("f", "syn_function"),
    4: ("c", "syn_type"),
    5: ("F", "syn_property"),
    6: ("v", "syn_property"),
    7: ("C", "syn_type"),
    8: ("I", "syn_type"),
    9: ("M", "syn_keyword"),
    10: ("p", "syn_property"),
    11: ("u", "syn_constant"),
    12: ("v", "syn_property"),
    13: ("E", "syn_type"),
    14: ("k", "syn_keyword"),
    15: ("s", "syn_string"),
    16: ("#", "syn_constant"),
    17: ("D", "syn_constant"),
    18: ("R", "syn_constant"),
    19: ("d", "syn_constant"),
    20: ("e", "syn_type"),
    21: ("N", "syn_constant"),
    22: ("S", "syn_type"),
    23: ("x", "syn_keyword"),
    24: ("o", "syn_operator"),
    25: ("t", "syn_type"),
}


class CompletionPopup(Widget):
    """Floating completion list rendered above the editor (no focus grab)."""

    can_focus = False

    DEFAULT_CSS = """
    CompletionPopup {
        layer: lsp-popup;
        position: absolute;
        height: 0;
        width: 0;
        padding: 0;
        margin: 0;
    }
    """

    def __init__(self, yate: AppProtocol, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.yate = yate
        self.items: list[Completion] = []
        self.index = 0
        self.prefix = ""
        self._anchor: Optional[tuple[int, int]] = None

    def on_mount(self) -> None:
        self.display = False

    # -------------------------------------------------------------- state

    @property
    def is_open(self) -> bool:
        return bool(self.display) and bool(self.items)

    @property
    def item_count(self) -> int:
        return len(self.items)

    def selected(self) -> Optional[Completion]:
        if not self.items:
            return None
        return self.items[self.index]

    def show(
        self,
        items: list[Completion],
        prefix: str,
        anchor: tuple[int, int],
        inner_size: tuple[int, int],
        gutter: int,
        origin_y: int = 0,
    ) -> None:
        """Display *items* near the cursor.

        *anchor* is the cursor cell (col, row) relative to the editor's text
        area; *inner_size* is the editor's (width, height) in cells; *gutter*
        is the gutter width in cells; *origin_y* is the offset of the editor
        inside the popup's parent (tab bar + breadcrumbs rows).
        """
        if not items:
            self.close()
            return
        self.items = items
        self.index = 0
        self.prefix = prefix
        self._anchor = anchor

        visible = min(len(items), MAX_VISIBLE)
        box_w = self._compute_width()
        box_h = visible + 2

        # Horizontal: prefer starting at the cursor column, flip left if it
        # would overflow the editor's right edge.
        x = min(gutter + anchor[0], max(0, inner_size[0] - box_w))
        x = max(0, x)
        # Vertical: open below the cursor unless there is not enough room;
        # then open above it.
        top_limit = origin_y + inner_size[1]
        below = origin_y + anchor[1] + 1
        if below + box_h <= top_limit:
            y = below
        else:
            y = max(origin_y, origin_y + anchor[1] - box_h + 1)

        self.styles.width = box_w
        self.styles.height = box_h
        self.styles.offset = ScalarOffset.from_offset((x, y))
        self.display = True
        self.refresh()

    def close(self) -> None:
        self.items = []
        self.index = 0
        self.prefix = ""
        self._anchor = None
        self.display = False

    def select_next(self) -> None:
        if self.items:
            self.index = (self.index + 1) % len(self.items)
            self.refresh()

    def select_prev(self) -> None:
        if self.items:
            self.index = (self.index - 1) % len(self.items)
            self.refresh()

    # ------------------------------------------------------------- render

    def _compute_width(self) -> int:
        widest = 0
        for item in self.items:
            label_cells = theme.cell_len(item.label)
            detail_cells = theme.cell_len(item.detail) if item.detail else 0
            total = 1 + 1 + 1 + label_cells + (2 + detail_cells if detail_cells else 0) + 1
            widest = max(widest, total)
        return max(24, min(60, widest))

    def render_line(self, y: int) -> Strip:
        t = theme.active()
        width = int(self.styles.width.value) if self.styles.width is not None else 40
        height = int(self.styles.height.value) if self.styles.height is not None else 0
        segments: list[Segment] = []
        if y == 0:
            segments.append(Segment(" " + " " * (width - 2) + " ",
                                    Style(bgcolor=t.panel)))
            return Strip(segments)
        if y == height - 1:
            segments.append(Segment(" " + " " * (width - 2) + " ",
                                    Style(bgcolor=t.panel)))
            return Strip(segments)

        idx = y - 1
        if idx >= len(self.items):
            return Strip([Segment(" " * width, Style(bgcolor=t.panel))])
        item = self.items[idx]
        selected = idx == self.index
        bg = t.selection_bg if selected else t.panel
        glyph, color_attr = _KIND_GLYPHS.get(item.kind, (" ", "fg_dim"))
        glyph_color = getattr(t, color_attr, t.fg)

        cells = 1  # leading space
        segments.append(Segment(" ", Style(bgcolor=bg)))
        segments.append(Segment(glyph, Style(color=glyph_color, bgcolor=bg, bold=True)))
        segments.append(Segment(" ", Style(bgcolor=bg)))
        cells += 2

        label_budget = width - cells - 1
        if item.detail:
            label_budget -= min(26, theme.cell_len(item.detail) + 2)
        label = item.label
        if theme.cell_len(label) > label_budget:
            label = theme.truncate_to_cells(label, max(4, label_budget - 1)) + "…"
        label_style = Style(
            color=t.fg_bright if selected else t.fg,
            bgcolor=bg,
            bold=selected,
        )
        segments.append(Segment(label, label_style))
        cells += theme.cell_len(label)

        if item.detail:
            gap = max(1, width - cells - theme.cell_len(item.detail) - 2)
            segments.append(Segment(" " * gap, Style(bgcolor=bg)))
            cells += gap
            detail_budget = width - cells - 1
            detail = item.detail
            if theme.cell_len(detail) > detail_budget:
                detail = theme.truncate_to_cells(detail, max(4, detail_budget - 1)) + "…"
            segments.append(Segment(detail, Style(color=t.fg_dim, bgcolor=bg)))
            cells += theme.cell_len(detail)

        if cells < width:
            segments.append(Segment(" " * (width - cells), Style(bgcolor=bg)))
        return Strip(segments)


# ------------------------------------------------------- buffer completion

def _ident_prefix(line: str, col: int) -> tuple[str, int]:
    """Identifier prefix ending at *col* and its start column.

    A prefix is a run of ``[A-Za-z0-9_]`` immediately left of the cursor.
    Paths containing ``/``, ``\\`` or ``~`` are also treated as a prefix so
    filesystem completions can kick in.
    """
    col = min(col, len(line))
    i = col
    while i > 0:
        ch = line[i - 1]
        if _IDENT_RE.match(ch) or ch in "/\\~":
            i -= 1
        else:
            break
    return line[i:col], i


def _words_from_buffer(buf: TextBuffer, exclude_row: int) -> set[str]:
    """All identifier-like words in *buf* (skipping the cursor row)."""
    words: set[str] = set()
    for r, line in enumerate(buf.lines):
        if r == exclude_row:
            continue
        words.update(_WORD_RE.findall(line))
    return words


def _path_completions(prefix: str, base_dir: Optional[Path] = None) -> list[str]:
    """Filesystem entries matching a path *prefix*.

    Relative prefixes resolve against *base_dir* (the workspace root) when
    given, otherwise against the process cwd.  Returns candidate strings
    that extend the prefix; directories get a trailing slash.
    """
    expanded = Path(prefix).expanduser()
    try:
        parent = expanded.parent if expanded.name else expanded
        base = expanded.name
    except ValueError:
        return []
    if not parent.is_absolute() and base_dir is not None:
        parent = base_dir / parent
    if not parent.exists() or not parent.is_dir():
        return []
    try:
        entries = sorted(parent.iterdir(), key=lambda p: p.name.lower())
    except OSError:
        return []
    needle = base.lower()
    results: list[str] = []
    for entry in entries:
        name = entry.name
        if not name.lower().startswith(needle):
            continue
        dir_part = prefix[: len(prefix) - len(base)] if base else prefix
        candidate = dir_part + name
        if entry.is_dir():
            candidate += "/"
        results.append(candidate)
    return results


def buffer_completions(
    buf: TextBuffer,
    row: int,
    col: int,
    extra_buffers: Optional[list[TextBuffer]] = None,
    base_dir: Optional[Path] = None,
) -> tuple[list[Completion], str, int]:
    """Build completion items from the open buffers (+ filesystem paths).

    Returns ``(items, prefix, prefix_start_col)``.  The popup caller uses
    *prefix* and the start column to position and (on accept) replace the
    typed prefix.  Words are taken from every open buffer (the current row
    excluded so the half-typed word itself does not compete); when the
    prefix contains a path separator, filesystem entries are offered too.
    """
    line = buf.lines[row] if row < buf.line_count else ""
    prefix, start_col = _ident_prefix(line, col)
    items: list[Completion] = []

    if not prefix:
        return items, prefix, start_col

    is_path = any(ch in prefix for ch in "/\\~")
    needle = prefix.lower()

    # 1) words from the current buffer and any extra open buffers
    seen: set[str] = set()
    for word in _words_from_buffer(buf, row):
        if word.lower().startswith(needle) and word != prefix:
            seen.add(word)
    if extra_buffers:
        for other in extra_buffers:
            for word in _words_from_buffer(other, -1):
                if word.lower().startswith(needle) and word != prefix:
                    seen.add(word)
    for word in sorted(seen):
        items.append(
            Completion(
                label=word,
                insert_text=word,
                detail="word",
                kind=_KIND_TEXT,
                range_start_row=row,
                range_start_col=start_col,
                range_end_row=row,
                range_end_col=col,
            )
        )

    # 2) filesystem entries (only when the prefix looks like a path)
    if is_path:
        for candidate in _path_completions(prefix, base_dir):
            if candidate == prefix:
                continue
            items.append(
                Completion(
                    label=Path(candidate).name + ("/" if candidate.endswith("/") else ""),
                    insert_text=candidate,
                    detail="path",
                    kind=_KIND_FILE,
                    range_start_row=row,
                    range_start_col=start_col,
                    range_end_row=row,
                    range_end_col=col,
                )
            )

    # trim to a sane limit (the popup caps visible rows anyway)
    return items[:64], prefix, start_col

