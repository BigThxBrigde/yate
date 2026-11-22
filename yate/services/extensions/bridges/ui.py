"""The ``api.ui`` bridges (status bar segments + the modal canvas).

Grouping note: :class:`StatusSegment`, :class:`CanvasHandle` and
:class:`UiExtensionBridge` share this module because the bridge's public
methods construct and hand back those types, and the three aliases
(``SegmentAlign`` / ``CanvasControls`` / ``CanvasOpener``) parametrize
them -- keeping the group in one file preserves the old module-level
namespace byte-for-byte.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Literal

#: The two status bar halves a segment can attach to.
type SegmentAlign = Literal["left", "right"]

#: Raw canvas control callbacks ``(draw, set_status, close)`` the UI host
#: hands back for one open canvas.  The bridge wraps them into the
#: extension-facing :class:`CanvasHandle`, so consumers of the opener never
#: need to name the handle class (R14: the editor imports the facade, not
#: this module).
type CanvasControls = tuple[
    Callable[[str, Mapping[str, str]], None],
    Callable[[str], None],
    Callable[[], None],
]

#: Injected canvas host: ``(cols, rows, on_key, on_tick, on_close)`` builds
#: the modal canvas screen and returns the :data:`CanvasControls` triple.
#: The editor (L3) supplies the implementation; ``None`` in the bridge means
#: no UI host (headless construction in tests) and :meth:`open_canvas` raises.
type CanvasOpener = Callable[
    [int, int, Callable[[str], None], Callable[[], None], Callable[[], None]],
    CanvasControls,
]


@dataclass(frozen=True)
class StatusSegment:
    """One extension-contributed status bar segment (pull model).

    The status bar calls *provider* once per refresh pass and renders the
    returned string as the segment text; ``None`` or an empty string hides
    the segment for that pass.  *align* selects the bar half (``"left"``
    or ``"right"``); a higher *priority* sorts first within its half,
    ties keeping registration order.  The bar refreshes on every cursor
    move and mode change -- keep *provider* cheap (precompute heavier
    aggregations in event listeners instead).
    """

    id: str
    provider: Callable[[], str | None]
    align: SegmentAlign = "right"
    priority: int = 0


class CanvasHandle:
    """One open extension canvas, as handed back to the extension script.

    A pure forwarder over the three callbacks the UI host injected: the
    bridge holds no widget and knows no rendering detail.  The host owns
    the closed-after-dismiss guard -- a call that arrives after the screen
    is gone is silently ignored there, not here.
    """

    def __init__(
        self,
        draw: Callable[[str, Mapping[str, str]], None],
        set_status: Callable[[str], None],
        close: Callable[[], None],
    ) -> None:
        self._draw = draw
        self._set_status = set_status
        self._close = close

    def draw(self, grid: str, palette: Mapping[str, str]) -> None:
        """Repaint the canvas grid: *grid* is one newline-joined string.

        Each character is colored through *palette*; a blank cell keeps the
        default color.  A ``"*"`` palette entry supplies the glyph painted
        for every colored cell (solid blocks: ``{"*": "█"}``).  Rows and
        columns beyond the screen's dimensions are clipped by the UI host.
        """
        self._draw(grid, palette)

    def set_status(self, text: str) -> None:
        """Replace the status line under the grid with *text*."""
        self._set_status(text)

    def close(self) -> None:
        """Close the canvas (idempotent: the host drops repeated calls)."""
        self._close()


class UiExtensionBridge:
    """``api.ui`` -- UI elements contributed by extensions.

    Status bar segments (a pull-model registry: :meth:`add_status_segment` /
    :meth:`remove_status_segment` mutate it, and the status bar widget (L2)
    pulls an alignment-filtered, priority-sorted snapshot on every refresh,
    :meth:`segments`) plus the full-screen canvas (:meth:`open_canvas`).
    The bridge never touches widgets itself: the canvas is built by the
    injected :data:`CanvasOpener`, so the bridge stays UI-free.  Registrations
    made while a rollback scope is active are recorded through
    *record_undo*, so a failing ``setup`` also drops them (A13).
    """

    def __init__(
        self,
        record_undo: Callable[[Callable[[], None]], None],
        open_canvas: CanvasOpener | None = None,
    ) -> None:
        self._segments: dict[str, tuple[int, StatusSegment]] = {}
        self._counter = 0
        self._record_undo = record_undo
        # ``None`` = no UI host (headless construction in tests): the canvas
        # verb raises a RuntimeError instead of silently doing nothing.
        self._open_canvas = open_canvas

    def add_status_segment(self, segment: StatusSegment) -> None:
        """Register *segment* in the status bar registry.

        A duplicate id raises ``ValueError``.  Inside a rollback scope the
        registration is recorded (A13): rollback drops the segment again.
        """
        if segment.id in self._segments:
            raise ValueError(f"duplicate status segment id: {segment.id!r}")
        self._segments[segment.id] = (self._counter, segment)
        self._counter += 1

        def undo(segment: StatusSegment = segment) -> None:
            self._segments.pop(segment.id, None)

        self._record_undo(undo)

    def add_segment(
        self,
        id: str,
        provider: Callable[[], str | None],
        align: SegmentAlign = "right",
        priority: int = 0,
    ) -> None:
        """Build a :class:`StatusSegment` from plain arguments and register it.

        Convenience factory for the scripting bridges (Lua cannot construct
        a frozen dataclass): ``add_segment(id, provider, align, priority)``
        is equivalent to building the segment and calling
        :meth:`add_status_segment` -- duplicate ids raise ``ValueError`` and
        rollback-scope recording (A13) behaves the same.
        """
        self.add_status_segment(
            StatusSegment(id=id, provider=provider, align=align, priority=priority)
        )

    def remove_status_segment(self, segment_id: str) -> None:
        """Drop the segment *segment_id* (``KeyError`` when unknown).

        Inside a rollback scope the removal is recorded (A13): rollback
        restores the removed entry with its original ordering.
        """
        entry = self._segments.pop(segment_id)

        def undo(
            segment_id: str = segment_id,
            entry: tuple[int, StatusSegment] = entry,
        ) -> None:
            self._segments[segment_id] = entry

        self._record_undo(undo)

    def segments(self, align: SegmentAlign) -> list[StatusSegment]:
        """Snapshot for bar half *align* (``"left"`` / ``"right"``).

        Sorted by descending priority, ties keeping registration order.
        The returned list is fresh (safe for the caller to hold); the
        segments themselves are frozen dataclasses.
        """
        entries = [
            (seq, segment)
            for seq, segment in self._segments.values()
            if segment.align == align
        ]
        entries.sort(key=lambda entry: (-entry[1].priority, entry[0]))
        return [segment for _seq, segment in entries]

    def open_canvas(
        self,
        cols: int,
        rows: int,
        on_key: Callable[[str], None],
        on_tick: Callable[[], None],
        on_close: Callable[[], None],
    ) -> CanvasHandle:
        """Open a modal *cols* x *rows* canvas driven by extension callbacks.

        *on_key* receives Textual key names (``left`` / ``space`` / ...),
        *on_tick* fires on the screen's own clock, and *on_close* runs once
        the screen is gone.  Returns the :class:`CanvasHandle` the script
        draws through.  ``RuntimeError`` when the host injected no opener
        (headless construction: no screen can be pushed).
        """
        if self._open_canvas is None:
            raise RuntimeError("open_canvas: no UI host attached")
        draw, set_status, close = self._open_canvas(
            cols, rows, on_key, on_tick, on_close
        )
        return CanvasHandle(draw, set_status, close)
