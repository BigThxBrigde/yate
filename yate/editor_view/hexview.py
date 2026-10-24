"""Read-only hex dump viewer: an xxd-style byte view for binary files.

The view renders 16 bytes per line -- offset, two hex groups and an ASCII
echo -- into a scrolling :class:`textual.widget.ScrollView` (line API).  The
data is handed in pre-read by the flow layer (:mod:`yate.flows.overlay_flows`
owns the size gate); the widget itself is presentation-only: it never touches
the filesystem and holds no editor state (R3).

Theme ownership follows R13: the view subscribes on mount and repaints on
broadcast.  Key handling follows R10: the screen consumes only ``q`` /
``escape``; every other key falls through.
"""

from __future__ import annotations

from pathlib import Path
from typing import override

from rich.segment import Segment
from rich.style import Style
from textual.app import ComposeResult
from textual.events import Key
from textual.geometry import Size
from textual.screen import ModalScreen
from textual.scroll_view import ScrollView
from textual.strip import Strip

from yate.logs import tracing
from yate.paths import load_tcss

from yate.editor_view import theme
from yate.editor_view.scrollbars import apply_slim_scrollbars, apply_scrollbar_theme

log = tracing.get_logger(__name__)

#: Hard upper bound for hex view payloads; the flow layer refuses to push a
#: :class:`HexScreen` for larger files (100 MB read in one shot).
MAX_HEX_VIEW_SIZE: int = 100 * 1024 * 1024

#: Bytes rendered per line (the xxd convention).
_BYTES_PER_LINE: int = 16

#: Fixed content width of a full line: 8 offset digits + ``:`` + space +
#: 2 groups of 8 bytes (16 hex chars each, 2 spaces between groups,
#: total 34 chars) + 2 spaces + 16 ASCII chars.
_CONTENT_WIDTH: int = 9 + 1 + (2 * _BYTES_PER_LINE + 2) + 2 + _BYTES_PER_LINE


def _classify_byte(b: int) -> str:
    """Classify *b* into a hexyl-style byte category name.

    Boundaries follow hexyl's default classification: ``0x00`` is ``null``,
    ``0x09-0x0d`` and ``0x20`` are ``whitespace``, ``0x21-0x7e`` is
    ``printable``, the remaining ASCII bytes (``0x01-0x08``, ``0x0e-0x1f``,
    ``0x7f``) are ``ascii_other`` and ``0x80-0xff`` is ``non_ascii``.
    """
    if b == 0x00:
        return "null"
    if 0x09 <= b <= 0x0D or b == 0x20:
        return "whitespace"
    if 0x21 <= b <= 0x7E:
        return "printable"
    if b <= 0x7F:
        return "ascii_other"
    return "non_ascii"


def _theme_style(category: str) -> Style:
    """Map a byte category to a Rich style from the active theme.

    The hexyl palette maps onto existing :class:`Theme` tokens (zero new
    tokens, so themes are followed automatically): ``null`` -> ``fg_dim``,
    ``printable`` -> ``accent``, ``whitespace`` -> ``green``,
    ``ascii_other`` -> ``accent2``, ``non_ascii`` -> ``yellow``.
    """
    t = theme.active()
    if category == "null":
        return Style(color=t.fg_dim)
    if category == "printable":
        return Style(color=t.accent)
    if category == "whitespace":
        return Style(color=t.green)
    if category == "ascii_other":
        return Style(color=t.accent2)
    return Style(color=t.yellow)


def _hex_segments(chunk: bytes) -> list[Segment]:
    """Render *chunk* as two 8-byte hex groups, one segment per byte.

    Each byte contributes its two hex characters in its classified color;
    a short final group is padded to 16 chars with default-style spaces,
    mirroring the plain-text xxd layout byte for byte.
    """
    segments: list[Segment] = []
    for i in range(0, len(chunk), 8):
        if i:
            segments.append(Segment("  "))
        group = chunk[i : i + 8]
        for b in group:
            segments.append(Segment(f"{b:02x}", _theme_style(_classify_byte(b))))
        # Pad to 16 chars if last group is short.
        pad = 16 - 2 * len(group)
        if pad:
            segments.append(Segment(" " * pad))
    return segments


def _ascii_segments(chunk: bytes) -> list[Segment]:
    """Render *chunk* as the ASCII echo column, one segment per byte.

    Printable bytes (``0x20-0x7e``) echo as-is, anything else as ``.`` --
    each character carries its source byte's classified color.
    """
    return [
        Segment(
            chr(b) if 0x20 <= b <= 0x7E else ".",
            _theme_style(_classify_byte(b)),
        )
        for b in chunk
    ]


class HexView(ScrollView, can_focus=True):
    """Read-only hex dump viewer (xxd-style layout).

    Each line renders 16 bytes: offset (8 hex digits + ``:``) + hex groups
    (2 groups of 8 bytes, no intra-byte spaces, 2 spaces between groups) +
    ASCII column (printable ``0x20-0x7e`` as-is, else ``.``).
    """

    DEFAULT_CSS = load_tcss("hex-view.tcss")

    #: unsubscribe hook from :func:`yate.editor_view.theme.attach`;
    #: ``None`` while not mounted (DiffPane precedent).
    _theme_unsubscribe: theme.Unsubscribe | None = None

    def __init__(
        self,
        path: Path,
        data: bytes,
        *,
        id: str | None = None,
    ) -> None:
        super().__init__(id=id)
        self._path = path
        self._data = data
        # ScrollView requires virtual_size to enable scrolling; the height is
        # the line count (last partial line included), the width the fixed
        # content width so narrow terminals get a horizontal scrollbar.
        self.virtual_size = Size(
            _CONTENT_WIDTH, (len(data) + _BYTES_PER_LINE - 1) // _BYTES_PER_LINE
        )

    @override
    def on_mount(self) -> None:
        """Wire slim scrollbars and subscribe to theme broadcasts (R13 / R15)."""
        super().on_mount()
        apply_slim_scrollbars(self)
        self._apply_theme()
        theme.attach(self, self._apply_theme)

    def on_unmount(self) -> None:
        """Detach from the theme broadcast."""
        theme.detach(self)

    def _apply_theme(self) -> None:
        """Repaint on theme broadcast (scrollbar palette, diff_pane precedent)."""
        apply_scrollbar_theme(self)
        self.refresh()

    @override
    def render_line(self, y: int) -> Strip:
        """Render one line of hex dump (offset + hex + ASCII), byte-classified.

        *y* is a viewport row; the content row is ``y + scroll_offset.y``
        (DiffPane precedent for the line API on this Textual version).  The
        rendered text is exactly the xxd layout; the per-byte classification
        colors live in the segment styles only (hexyl mapping onto theme
        tokens), so ``Strip.text`` stays a plain-text assertion surface.
        """
        offset = (y + self.scroll_offset.y) * _BYTES_PER_LINE
        chunk = self._data[offset : offset + _BYTES_PER_LINE]
        if not chunk:
            return Strip.blank(self.size.width)
        segments: list[Segment] = [
            Segment(f"{offset:08x}: ", Style(color=theme.active().fg_muted)),
            *_hex_segments(chunk),
            Segment("  "),
            *_ascii_segments(chunk),
        ]
        return Strip(segments).extend_cell_length(self.size.width)

    def _format_hex(self, chunk: bytes) -> str:
        """Format *chunk* as 2 groups of 8 bytes (xxd-style, plain text)."""
        return "".join(segment.text for segment in _hex_segments(chunk))

    def _format_ascii(self, chunk: bytes) -> str:
        """Format *chunk* as ASCII (printable 0x20-0x7e, else ``.``)."""
        return "".join(segment.text for segment in _ascii_segments(chunk))


class HexScreen(ModalScreen[None]):
    """Full-screen overlay hosting a :class:`HexView`."""

    def __init__(self, path: Path, data: bytes) -> None:
        super().__init__()
        self._path = path
        self._data = data

    @override
    def compose(self) -> ComposeResult:
        """The single HexView filling the screen."""
        yield HexView(self._path, self._data, id="hex-view")

    def on_key(self, event: Key) -> None:
        """Close on ``q`` / ``escape``; every other key falls through (R10)."""
        if event.key in ("q", "escape"):
            self.dismiss(None)
            event.stop()
