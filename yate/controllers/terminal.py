"""Integrated terminal panel lifecycle: show / hide / spawn the shell.

Extracted from :class:`yate.app.YateApp`; the panel widget and the
lifecycle flags stay on the app because the key handlers, the :set
command and the tests read them directly.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from yate.editor_term import PtyProcessError, resolve_shell

if TYPE_CHECKING:
    from yate.app import YateApp

# Extracted YateApp collaborator: touching the app's private terminal state
# (_terminal_visible/_terminal_starting/_terminal_factory) is this module's
# contract (Python has no friend classes).
# pyright: reportPrivateUsage=false


def toggle_terminal(app: "YateApp") -> None:
    """Show/focus or hide the integrated terminal (Ctrl+`)."""
    if app._terminal_visible:
        close_terminal(app)
    else:
        open_terminal(app)


def open_terminal(app: "YateApp") -> None:
    """Reveal the bottom terminal and focus it, spawning the shell."""
    panel = app.terminal_panel
    if panel is None:
        return
    was_hidden = not app._terminal_visible
    if was_hidden:
        panel.styles.height = app.config.terminal_height
        panel.display = True
        app._terminal_visible = True
    panel.view.focus()
    if not panel.view.started:
        spawn_shell(app)
    if was_hidden:
        app.message("terminal shown", kind="ok")


def close_terminal(app: "YateApp") -> None:
    """Hide the panel; the shell process itself stays alive."""
    panel = app.terminal_panel
    if panel is None or not app._terminal_visible:
        app.message("terminal already hidden", kind="warn")
        return
    panel.display = False
    app._terminal_visible = False
    app.focus_editor()
    app.message("terminal hidden", kind="ok")


def spawn_shell(app: "YateApp") -> None:
    if app._terminal_starting:
        return
    panel = app.terminal_panel
    if panel is None:
        return
    app._terminal_starting = True
    argv = resolve_shell(app.config.shell)
    cwd = app.workspace.root or Path.cwd()

    async def _start() -> None:
        try:
            await panel.view.start(argv, cwd, factory=app._terminal_factory)
        except PtyProcessError as exc:
            app.message(f"terminal: {exc}", kind="warn")
        except OSError as exc:
            app.message(f"terminal: {exc}", kind="warn")
        finally:
            app._terminal_starting = False
        if app._terminal_visible:
            panel.view.focus()

    app.run_worker(_start(), group="terminal", exit_on_error=False)
