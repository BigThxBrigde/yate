"""Integrated terminal panel lifecycle: show / hide / spawn the shell.

Extracted from :class:`yate.app.YateApp` as a self-contained feature: the
visibility / startup state lives here.  The application supplies the panel
primitives, the spawn primitive and the small configuration surface through
:class:`TerminalHost`; the terminal widget drives the feature through
:class:`TerminalOps`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Awaitable, Callable, Optional, Protocol

from yate.editor_term import PtyProcessError, resolve_shell


class TerminalOps(Protocol):
    """The terminal panel operations the UI triggers (Ctrl+` / revive)."""

    def toggle_terminal(self) -> None: ...

    def open_terminal(self) -> None: ...


class TerminalPanelOps(Protocol):
    """The panel widget surface :class:`TerminalFeature` drives."""

    def set_height(self, height: int) -> None: ...

    def show_panel(self) -> None: ...

    def hide_panel(self) -> None: ...

    def focus_view(self) -> None: ...

    def view_started(self) -> bool: ...

    async def start_view(
        self,
        argv: list[str],
        cwd: Path,
        factory: Optional[Callable[..., object]],
    ) -> None: ...


class TerminalHost(Protocol):
    """What :class:`TerminalFeature` needs from the application."""

    @property
    def terminal_height(self) -> int: ...

    @property
    def shell_command(self) -> str: ...

    @property
    def terminal_factory(self) -> Optional[Callable[..., object]]: ...

    @property
    def terminal_panel(self) -> Optional[TerminalPanelOps]: ...

    def terminal_cwd(self) -> Path: ...

    def message(self, text: str, kind: str = "info") -> None: ...

    def focus_editor(self) -> None: ...

    def spawn(self, work: Callable[[], Awaitable[None]], *, group: str,
              exclusive: bool = False, exit_on_error: bool = True) -> None: ...


class TerminalFeature:
    """Show / hide / spawn the integrated terminal panel."""

    def __init__(self, host: TerminalHost) -> None:
        self._host = host
        self._visible = False
        self._starting = False

    @property
    def is_visible(self) -> bool:
        """Whether the panel is currently shown."""
        return self._visible

    # ----------------------------------------------------------- TerminalOps

    def toggle_terminal(self) -> None:
        """Show/focus or hide the integrated terminal (Ctrl+`)."""
        if self._visible:
            self.close_terminal()
        else:
            self.open_terminal()

    def open_terminal(self) -> None:
        """Reveal the bottom terminal and focus it, spawning the shell."""
        panel = self._host.terminal_panel
        if panel is None:
            return
        was_hidden = not self._visible
        if was_hidden:
            panel.set_height(self._host.terminal_height)
            panel.show_panel()
            self._visible = True
        panel.focus_view()
        if not panel.view_started():
            self.spawn_shell()
        if was_hidden:
            self._host.message("terminal shown", kind="ok")

    def close_terminal(self) -> None:
        """Hide the panel; the shell process itself stays alive."""
        panel = self._host.terminal_panel
        if panel is None or not self._visible:
            self._host.message("terminal already hidden", kind="warn")
            return
        panel.hide_panel()
        self._visible = False
        self._host.focus_editor()
        self._host.message("terminal hidden", kind="ok")

    # ----------------------------------------------------------------- spawn

    def spawn_shell(self) -> None:
        """Start the shell process once (idempotent while starting)."""
        if self._starting:
            return
        panel = self._host.terminal_panel
        if panel is None:
            return
        self._starting = True
        argv = resolve_shell(self._host.shell_command)
        cwd = self._host.terminal_cwd()

        async def _start() -> None:
            try:
                await panel.start_view(argv, cwd, self._host.terminal_factory)
            except PtyProcessError as exc:
                self._host.message(f"terminal: {exc}", kind="warn")
            except OSError as exc:
                self._host.message(f"terminal: {exc}", kind="warn")
            finally:
                self._starting = False
            if self._visible:
                panel.focus_view()

        self._host.spawn(_start, group="terminal", exit_on_error=False)
