"""The integrated terminal dock (Textual widgets over the PTY/emulator core).

The panel sits at the bottom of the screen, VS Code style: a one-line header
with the shell name/title and the :class:`TerminalView` that paints the VT
grid, forwards keystrokes to the PTY and manages scrollback.
"""

from __future__ import annotations

import asyncio
import contextlib
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from rich.segment import Segment
from rich.style import Style
from textual.containers import Vertical
from textual.events import Key, MouseScrollDown, MouseScrollUp, Paste, Resize
from textual.strip import Strip
from textual.widget import Widget
from textual.widgets import Static

from yate.editor_term import (
    PtyProcess,
    TerminalEmulator,
    key_to_terminal,
    shell_label,
)

from . import theme

if TYPE_CHECKING:
    from yate.app import YateApp

#: Names Textual gives Ctrl+grave across platforms:
#: - "ctrl+`" / "ctrl+grave": friendly/pilot names;
#: - "ctrl+grave_accent": kitty keyboard protocol terminals (`chr(96)`
#:   is named "grave_accent");
#: - "ctrl+@": Windows conhost and legacy xterm -- Ctrl+grave translates
#:   to the NUL byte there (ToUnicodeEx yields no character), which
#:   Textual names ctrl+@. Kept so the panel can be CLOSED from the
#:   keyboard while it is focused. The NUL byte is the same one
#:   Ctrl+Space sends there, so elsewhere (editor/app) ctrl+@ never
#:   opens the panel -- Ctrl+Space means manual completion instead.
TOGGLE_KEYS = frozenset({
    "ctrl+`", "ctrl+grave", "ctrl+grave_accent", "ctrl+@",
})


def _hex(rgb: Optional[tuple[int, int, int]]) -> Optional[str]:
    if rgb is None:
        return None
    return "#%02x%02x%02x" % rgb


class TerminalView(Widget):
    """Paints :class:`TerminalEmulator` rows and feeds keys to the PTY."""

    can_focus = True

    DEFAULT_CSS = """
    TerminalView {
        padding: 0;
    }
    """

    def __init__(self, app: YateApp, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.yate = app
        self.emulator = TerminalEmulator(80, 24, on_response=self._respond)
        self.proc: Optional[PtyProcess] = None
        self.shell_argv: list[str] = []
        self._scroll = 0
        self._starting = False
        self.dead = False
        self._exit_code: Optional[int] = None
        self._last_title = ""

    # ------------------------------------------------------------- lifecycle

    @property
    def started(self) -> bool:
        return self.proc is not None and not self.dead

    async def start(
        self,
        argv: list[str],
        cwd: Path,
        factory: Optional[Any] = None,
    ) -> None:
        """Spawn the shell; restarted automatically after a previous exit."""
        if self._starting or self.started:
            return
        self._starting = True
        try:
            # The panel was just shown: wait until Textual has laid it out
            # so the PTY starts at the real size instead of the 80x24
            # fallback (whose first lines would be discarded when the
            # viewport shrinks to its final height).
            await self._wait_for_size()
            cols, rows = self._grid_size()
            self.emulator = TerminalEmulator(
                cols, rows, on_response=self._respond
            )
            self._scroll = 0
            self.dead = False
            self._exit_code = None
            make: Any = factory or PtyProcess
            proc: PtyProcess = make(argv, cwd, cols, rows)
            self.proc = proc
            self.shell_argv = list(argv)
            await proc.start(self._on_output, self._on_exit)
        finally:
            self._starting = False
        self._last_title = self.emulator.title
        panel = self.parent
        if isinstance(panel, TerminalPanel):
            panel.refresh_header()
        self.refresh()

    async def shutdown(self) -> None:
        """Terminate the shell (called when yate exits)."""
        proc, self.proc = self.proc, None
        if proc is None:
            return
        proc.terminate()
        try:
            await proc.wait_closed()
        except Exception:
            # Cancelled teardown (or a PTY error) must still detach the
            # process so its reader thread can never post into the closed
            # event loop after yate is gone.
            pass
        finally:
            proc.detach()

    def _respond(self, data: bytes) -> None:
        if self.proc is not None:
            self.proc.write(data)

    # ------------------------------------------------------------ PTY events

    def _on_output(self, data: bytes) -> None:
        self.emulator.feed(data)
        if self._scroll:
            self._scroll = min(self._scroll, self.emulator.max_scroll())
        self.refresh()
        if self.emulator.title != self._last_title:
            self._last_title = self.emulator.title
            panel = self.parent
            if isinstance(panel, TerminalPanel):
                panel.refresh_header()

    def _on_exit(self, code: Optional[int]) -> None:
        self.dead = True
        self._exit_code = code
        self._scroll = 0
        self.refresh()
        panel = self.parent
        if isinstance(panel, TerminalPanel):
            panel.refresh_header()

    # ---------------------------------------------------------------- layout

    async def _wait_for_size(self, timeout: float = 1.0) -> None:
        """Yield until the widget has a laid-out, non-zero size."""
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        while loop.time() < deadline:
            if self.is_attached and self.size.width and self.size.height:
                return
            await asyncio.sleep(0.02)

    def _grid_size(self) -> tuple[int, int]:
        width = int(self.size.width) if self.size.width else 80
        height = int(self.size.height) if self.size.height else 24
        return max(1, width), max(1, height)

    def on_resize(self, _event: Resize) -> None:
        cols, rows = self._grid_size()
        if (cols, rows) == (self.emulator.cols, self.emulator.rows):
            return
        self.emulator.resize(cols, rows)
        if self.proc is not None:
            self.proc.resize(cols, rows)
        self._scroll = min(self._scroll, self.emulator.max_scroll())
        self.refresh()

    # --------------------------------------------------------------- input

    def on_key(self, event: Key) -> None:
        if event.key in TOGGLE_KEYS:
            event.stop()
            event.prevent_default()
            self.yate.toggle_terminal()
            return
        event.stop()
        event.prevent_default()
        if not self.started or self.dead:
            # Any key revives a dead shell.
            self.yate.open_terminal()
            return
        sequence = key_to_terminal(event.key, event.character)
        if sequence:
            self.proc_write(sequence.encode("utf-8"))
            self._scroll = 0
        elif event.key == "shift+pageup":
            self.scroll_by(self.emulator.rows - 1)
        elif event.key == "shift+pagedown":
            self.scroll_by(-(self.emulator.rows - 1))

    def on_paste(self, event: Paste) -> None:
        if not self.started or self.dead or not event.text:
            return
        event.stop()
        event.prevent_default()
        if self.emulator.bracketed_paste:
            data = b"\x1b[200~" + event.text.encode("utf-8") + b"\x1b[201~"
        else:
            data = event.text.encode("utf-8").replace(b"\n", b"\r")
        self.proc_write(data)
        self._scroll = 0

    def on_mouse_scroll_up(self, event: MouseScrollUp) -> None:
        event.stop()
        self.scroll_by(3)

    def on_mouse_scroll_down(self, event: MouseScrollDown) -> None:
        event.stop()
        self.scroll_by(-3)

    def proc_write(self, data: bytes) -> None:
        if self.proc is not None:
            self.proc.write(data)

    def scroll_by(self, delta: int) -> None:
        maximum = self.emulator.max_scroll()
        self._scroll = max(0, min(self._scroll + delta, maximum))
        self.refresh()

    # --------------------------------------------------------------- render

    def render_line(self, y: int) -> Strip:
        t = theme.active()
        width = int(self.size.width) if self.size.width else self.emulator.cols
        lines = self.emulator.view_lines(self._scroll)
        if y >= len(lines):
            return Strip.blank(width, Style(bgcolor=t.bg))
        row_cells = lines[y]
        cursor_row, cursor_col = self.emulator.cursor
        show_cursor = (
            not self.dead
            and self._scroll == 0
            and self.emulator.cursor_visible
            and y == cursor_row
        )
        segments: list[Segment] = []
        text_parts: list[str] = []
        current: Optional[Style] = None
        x = 0

        def flush() -> None:
            if text_parts:
                segments.append(Segment("".join(text_parts), current))
                text_parts.clear()

        for cell in row_cells:
            if cell.char == "":
                # Second column of a wide glyph; Rich already advanced by 2.
                x += 1
                continue
            style = self._cell_style(cell, t)
            if show_cursor and x == cursor_col:
                style = self._cursor_style(cell, t)
            if style != current:
                flush()
                current = style
            text_parts.append(cell.char if cell.char != " " else " ")
            x += 1
        flush()

        strip = Strip(segments)
        used = strip.cell_length
        if used < width:
            # Pad so themes/painting cover the full row.
            segments.append(Segment(" " * (width - used), Style(bgcolor=t.bg)))
            strip = Strip(segments)

        if self.dead and y == min(self.emulator.rows - 1, len(lines) - 1):
            message = self._dead_message()
            strip = Strip([Segment(" " + message,
                                   Style(color=t.fg_dim, bgcolor=t.bg))])
        return strip

    def _dead_message(self) -> str:
        code = self._exit_code
        suffix = "" if code is None else f" (exit code {code})"
        return f"[shell exited{suffix}; any key restarts]"

    @staticmethod
    def _cell_style(cell: Any, t: Any) -> Style:
        fg = _hex(cell.fg)
        bg = _hex(cell.bg) or t.bg
        if cell.dim and cell.fg is None:
            fg = t.fg_dim
        if cell.reverse:
            fg, bg = bg or t.bg, fg or t.fg
        return Style(
            color=fg or t.fg,
            bgcolor=bg,
            bold=cell.bold,
            italic=cell.italic,
            underline=cell.underline,
        )

    @staticmethod
    def _cursor_style(cell: Any, t: Any) -> Style:
        fg = _hex(cell.fg) or t.fg
        bg = _hex(cell.bg) or t.bg
        if cell.reverse:
            fg, bg = bg, fg
        return Style(color=bg, bgcolor=fg, bold=cell.bold,
                     italic=cell.italic, underline=cell.underline)


class TerminalPanel(Vertical):
    """Header line plus the terminal view, docked at the bottom."""

    DEFAULT_CSS = """
    TerminalPanel {
        height: 1fr;
    }
    #terminal-title {
        height: 1;
        padding: 0 1;
    }
    TerminalView {
        height: 1fr;
    }
    """

    def __init__(self, app: YateApp, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.yate = app
        self.header = Static("", id="terminal-title")
        self.view = TerminalView(app)
        self._cached_header = ""

    def compose(self) -> Any:
        yield self.header
        yield self.view

    def on_mount(self) -> None:
        t = theme.active()
        self.header.styles.background = t.panel
        self.header.styles.color = t.fg_dim
        self.view.styles.background = t.bg
        self.refresh_header()

    def header_text(self) -> str:
        """Current header caption (name, title and shell state)."""
        return self._cached_header

    def refresh_header(self) -> None:
        name = shell_label(self.view.shell_argv) if self.view.shell_argv else "shell"
        title = self.view.emulator.title
        if self.view.dead:
            state = "exited"
        elif self.view.started:
            state = "running"
        else:
            state = "starting"
        hint = "Ctrl+` to hide"
        middle = f"{name} -- {title}" if title else name
        text = f" {middle} [{state}]    {hint}"
        if text == self._cached_header:
            return
        self._cached_header = text
        with contextlib.suppress(Exception):
            self.header.update(text)
