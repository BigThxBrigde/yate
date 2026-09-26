"""The integrated terminal dock (Textual widgets over the PTY/emulator core).

The panel sits at the bottom of the screen, VS Code style: a one-line header
with the shell name/title and the :class:`TerminalView` that paints the VT
grid, forwards keystrokes to the PTY and manages scrollback.
"""

from __future__ import annotations

import asyncio
import contextlib
from pathlib import Path
from typing import Any, override

from collections.abc import Callable

from rich.segment import Segment
from rich.style import Style
from textual.containers import Vertical
from textual.events import Key, MouseScrollDown, MouseScrollUp, Paste, Resize
from textual.strip import Strip
from textual.widget import Widget
from textual.widgets import Static

from yate.config import YateConfig
from yate.editor_term import (
    PtyProcess,
    PtyProcessError,
    TerminalEmulator,
    key_to_terminal,
    resolve_shell,
    shell_label,
)
from yate.services.workspace import Workspace

from . import theme
from .commandline import PromptBar

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

#: Hands focus back to the editor while the terminal is focused (the
#: terminal counterpart of the editor's own ctrl+1 chord).  Consumed by
#: :meth:`TerminalView.on_key`, so the shell input stream never sees it.
FOCUS_EDITOR_KEY = "ctrl+1"


def _hex(rgb: tuple[int, int, int] | None) -> str | None:
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

    def __init__(self, panel: TerminalPanel, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.panel = panel
        self.emulator = TerminalEmulator(80, 24, on_response=self._respond)
        self.proc: PtyProcess | None = None
        self.shell_argv: list[str] = []
        self._scroll = 0
        self._starting = False
        self.dead = False
        self._exit_code: int | None = None
        self._last_title = ""

    # ------------------------------------------------------------- lifecycle

    @property
    def started(self) -> bool:
        return self.proc is not None and not self.dead

    async def start(
        self,
        argv: list[str],
        cwd: Path,
        factory: Any | None = None,  # noqa: Any - fake PTY factory for tests; no stub.
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
            make: Any = factory or PtyProcess  # noqa: Any - fake PTY factory from tests; no stub.
            proc: PtyProcess = make(argv, cwd, cols, rows)
            self.proc = proc
            self.shell_argv = list(argv)
            try:
                await proc.start(self._on_output, self._on_exit)
            except Exception:  # noqa: BLE001 - re-raised; reset state first
                # A failed spawn must not leave a phantom ``started`` shell:
                # with proc set and dead False the revive path (any key /
                # open()) would never fire again.  Cancellation is not caught
                # on purpose -- the spawn thread may still have created the
                # child, so shutdown() must keep the reference to reap it.
                self.proc = None
                self.dead = True
                raise
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

    def _on_exit(self, code: int | None) -> None:
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
            self.panel.toggle()
            return
        if event.key == FOCUS_EDITOR_KEY:
            # Focus change only: never reaches the shell, and must not
            # revive a dead shell either.
            event.stop()
            event.prevent_default()
            self.panel.focus_editor()
            return
        event.stop()
        event.prevent_default()
        if not self.started or self.dead:
            # Any key revives a dead shell.
            self.panel.open()
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

    @override
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
        current: Style | None = None
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
            text_parts.append(cell.char)
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
    """Header line plus the terminal view, docked at the bottom.

    The panel owns its whole lifecycle (show / hide / spawn the shell): the
    editor only calls :meth:`toggle`, :meth:`open`, :meth:`close` and
    :meth:`apply_height`.  ``view_factory`` is the fake-PTY hook the test
    suite injects (``None`` in production).
    """

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

    def __init__(
        self,
        config: YateConfig,
        workspace: Workspace,
        prompt: PromptBar,
        *,
        focus_editor: Callable[[], None],
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.config = config
        self.workspace = workspace
        self.prompt = prompt
        self.focus_editor = focus_editor
        #: Fake-PTY hook injected by the test-suite (``None`` in production).
        self.view_factory: Callable[..., object] | None = None
        self.header = Static("", id="terminal-title")
        self.view = TerminalView(self)
        self._cached_header = ""
        self._visible = False
        self._starting = False

    @override
    def compose(self) -> Any:
        yield self.header
        yield self.view

    def on_mount(self) -> None:
        t = theme.active()
        self.header.styles.background = t.panel
        self.header.styles.color = t.fg_dim
        self.view.styles.background = t.bg
        self.refresh_header()

    # ----------------------------------------------------------- lifecycle

    @property
    def is_visible(self) -> bool:
        """Whether the panel is currently shown."""
        return self._visible

    def toggle(self) -> None:
        """Show/focus or hide the integrated terminal (Ctrl+`)."""
        if self._visible:
            self.close()
        else:
            self.open()

    def open(self) -> None:
        """Reveal the bottom terminal and focus it, spawning the shell."""
        was_hidden = not self._visible
        if was_hidden:
            self.apply_height(self.config.terminal_height)
            self.display = True
            self._visible = True
        self.view.focus()
        if not self.view.started:
            self.spawn_shell()
        if was_hidden:
            self.prompt.write("terminal shown", kind="ok")

    def close(self) -> None:
        """Hide the panel; the shell process itself stays alive."""
        if not self._visible:
            self.prompt.write("terminal already hidden", kind="warn")
            return
        self.display = False
        self._visible = False
        self.focus_editor()
        self.prompt.write("terminal hidden", kind="ok")

    def apply_height(self, height: int) -> None:
        """Resize the panel when it is currently visible."""
        if self._visible:
            self.styles.height = height

    # ---------------------------------------------------------- shell spawn

    def spawn_shell(self) -> None:
        """Start the shell process once (idempotent while starting)."""
        if self._starting:
            return
        self._starting = True
        argv = resolve_shell(self.config.shell)
        cwd = self.workspace.root or Path.cwd()

        async def _start() -> None:
            try:
                await self.view.start(argv, cwd, factory=self.view_factory)
            except PtyProcessError as exc:
                self.prompt.write(f"terminal: {exc}", kind="warn")
            except OSError as exc:
                self.prompt.write(f"terminal: {exc}", kind="warn")
            finally:
                self._starting = False
            if self._visible:
                self.view.focus()

        # Hand the worker the coroutine *function*: an eagerly built coroutine
        # would live outside the worker's lifecycle and leak "never awaited"
        # if the worker never starts (app quitting).
        self.run_worker(_start, group="terminal", exit_on_error=False)

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
