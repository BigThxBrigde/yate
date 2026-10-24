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
from textual.app import ComposeResult
from textual.events import Key
from textual.geometry import Size
from textual.screen import ModalScreen
from textual.scroll_view import ScrollView
from textual.strip import Strip

from yate.logs import tracing
from yate.paths import load_tcss

from yate.editor_view import theme

log = tracing.get_logger(__name__)

#: Hard upper bound for hex view payloads; the flow layer refuses to push a
#: :class:`HexScreen` for larger files (100 MB read in one shot).
MAX_HEX_VIEW_SIZE: int = 100 * 1024 * 1024

#: Bytes rendered per line (the xxd convention).
_BYTES_PER_LINE: int = 16

#: Fixed content width of a full line: 8 offset digits + ``:`` + space +
#: 2 groups of 8 bytes (16 hex chars each, 2 spaces between groups) +
#: 2 spaces + 16 ASCII chars.
_CONTENT_WIDTH: int = 9 + 1 + 2 * (2 * _BYTES_PER_LINE) + 2 + _BYTES_PER_LINE


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
        """Subscribe to theme broadcasts (R13)."""
        super().on_mount()
        theme.attach(self, self._on_theme_changed)

    def on_unmount(self) -> None:
        """Detach from the theme broadcast."""
        theme.detach(self)

    def _on_theme_changed(self) -> None:
        """Repaint on theme broadcast (ThemeListener = Callable[[], None])."""
        self.refresh()

    @override
    def render_line(self, y: int) -> Strip:
        """Render one line of hex dump (offset + hex + ASCII).

        *y* is a viewport row; the content row is ``y + scroll_offset.y``
        (DiffPane precedent for the line API on this Textual version).
        """
        offset = (y + self.scroll_offset.y) * _BYTES_PER_LINE
        chunk = self._data[offset : offset + _BYTES_PER_LINE]
        if not chunk:
            return Strip.blank(self.size.width)
        hex_part = self._format_hex(chunk)
        ascii_part = self._format_ascii(chunk)
        line = f"{offset:08x}: {hex_part}  {ascii_part}"
        return Strip([Segment(line)]).extend_cell_length(self.size.width)

    def _format_hex(self, chunk: bytes) -> str:
        """Format *chunk* as 2 groups of 8 bytes (xxd-style)."""
        groups: list[str] = []
        for i in range(0, len(chunk), 8):
            group = chunk[i : i + 8]
            hex_str = "".join(f"{b:02x}" for b in group)
            # Pad to 16 chars if last group is short.
            groups.append(hex_str.ljust(16))
        return "  ".join(groups)

    def _format_ascii(self, chunk: bytes) -> str:
        """Format *chunk* as ASCII (printable 0x20-0x7e, else ``.``)."""
        return "".join(chr(b) if 0x20 <= b <= 0x7E else "." for b in chunk)


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
