"""Full-screen character canvas driven by an extension script.

A :class:`~textual.screen.ModalScreen` that renders a fixed ``cols`` x
``rows`` character grid plus one status line, and turns terminal input into
callbacks: every key is stopped here and forwarded to *on_key* as its
Textual key name (``left`` / ``right`` / ``space`` / ``r`` ...), while
``escape`` is consumed by the screen itself and dismisses it (exit).  A
self-owned interval clock (``TICKS_PER_SECOND``) calls *on_tick*, so the
extension drives its own timing without knowing about Textual.

The screen owns rendering and the key semantics only; the game state lives
in the extension (R13: the component paints itself, the scheduler passes
callbacks).  Callbacks arrive as injected callables, which keeps this widget
free of any dependency on the extension machinery.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import override

from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Static

from yate.logs import tracing
from yate.paths import load_tcss

#: Trace logger ("yate.editor_view.canvas_screen"); silent unless yate_trace is on.
log = tracing.get_logger(__name__)

#: Clock rate handed to extensions (ticks per second).  Game rules never
#: live here: a faster game is a smaller tick divisor on the script side.
TICKS_PER_SECOND: int = 15

#: Key that closes the canvas: the modal game screen owns its own exit.
EXIT_KEY: str = "escape"

#: Hint line shown under the status row.
HINT_TEXT: str = " escape exits "


class CanvasScreen(ModalScreen[None]):
    """Modal character grid with a status line, driven by callbacks.

    *cols* / *rows* are the grid dimensions the extension draws into; a
    terminal that cannot fit them clips on the right and bottom, and a
    larger terminal leaves the grid at its requested size, centered.  The
    callbacks are: *on_key* (Textual key name), *on_tick* (one clock tick)
    and *on_close* (once, after the screen is gone -- reached through the
    push callback so a self ``dismiss()`` and an external pop both hit it).
    """

    #: Stylesheet, a bundled resource (see :func:`yate.paths.load_tcss`) --
    #: component-owned theming, theme values come from CSS variables (R13).
    DEFAULT_CSS = load_tcss("canvas.tcss")

    def __init__(
        self,
        cols: int,
        rows: int,
        on_key: Callable[[str], None],
        on_tick: Callable[[], None],
        on_close: Callable[[], None],
    ) -> None:
        self._cols = max(1, cols)
        self._rows = max(1, rows)
        # Names carry a ``key_sink``/``tick_sink`` suffix: ``_on_key`` would
        # collide with Textual's message-handler naming convention
        # (``_on_key`` is the private dispatcher for ``on_key``).
        self._key_sink = on_key
        self._tick_sink = on_tick
        self._close_sink = on_close
        self._grid = Static("", classes="grid")
        self._status = Static("", classes="status")
        self._hint = Static(HINT_TEXT, classes="hint")
        #: Last grid passed to :meth:`draw` (test/telemetry view).
        self._drawn: tuple[str, ...] = ()
        super().__init__()

    @override
    def compose(self) -> ComposeResult:
        """Stack the grid, the status line and the exit hint."""
        yield self._grid
        yield self._status
        yield self._hint

    def on_mount(self) -> None:
        """Start the extension clock and paint the empty canvas once.

        Textual delivers the ``Mount`` message to ``on_mount`` without a
        base-class declaration, so no ``@override`` marker applies here
        (same as :class:`~yate.editor_view.screensaver.ScreensaverScreen`).
        """
        self.set_interval(1 / TICKS_PER_SECOND, self._tick)
        self._paint()

    @property
    def cols(self) -> int:
        """Grid width in characters."""
        return self._cols

    @property
    def rows(self) -> int:
        """Grid height in characters."""
        return self._rows

    @property
    def drawn(self) -> tuple[str, ...]:
        """The grid rows last handed to :meth:`draw` (clipped, if any)."""
        return self._drawn

    # -------------------------------------------------------------- rendering

    def draw(self, rows: Sequence[str], palette: Mapping[str, str]) -> None:
        """Render *rows* colored through *palette*.

        One string per grid row; each character is looked up in *palette*
        (``{"#": "#e57373"}``) and painted in that color.  A blank cell and
        any character missing from *palette* keep the default color.  Rows
        and columns beyond the configured grid are clipped, and every row is
        padded to the grid width so the box stays aligned.
        """
        self._drawn = tuple(
            row[: self._cols].ljust(self._cols) for row in rows[: self._rows]
        )
        self._paint(palette)

    def set_status(self, text: str) -> None:
        """Replace the status line under the grid."""
        self._status.update(Text(text))

    def _paint(self, palette: Mapping[str, str] | None = None) -> None:
        """Repaint the grid from the last drawn rows.

        *palette* is the one the caller passed to :meth:`draw`; the initial
        mount paint passes ``None`` (everything in the default color).
        """
        colors: Mapping[str, str] = palette if palette is not None else {}
        text = Text()
        for index in range(self._rows):
            row = self._drawn[index] if index < len(self._drawn) else ""
            if index:
                text.append("\n")
            for char in row.ljust(self._cols):
                text.append(char, style=colors.get(char) if char != " " else None)
        self._grid.update(text)

    def on_key(self, event: events.Key) -> None:
        """Forward every key to the extension; ``escape`` exits.

        Consumption mirrors the screensaver's modal contract (R10 does not
        apply to a modal screen): the key never reaches the editor
        underneath.  ``escape`` is the canvas' own verb -- it dismisses the
        screen, and the close callback fires through the push callback.
        """
        event.stop()
        event.prevent_default()
        if event.key == EXIT_KEY:
            self.dismiss()
            return
        self._key_sink(event.key)

    def _tick(self) -> None:
        """Run one extension clock tick, reporting a raising callback."""
        try:
            self._tick_sink()
        except Exception:  # noqa: BLE001 - extension code, never crash the app
            log.exception("canvas tick callback failed")
            self._status.update(Text("tick callback failed -- escape exits"))
