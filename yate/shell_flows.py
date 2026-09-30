"""Shell and font flows: run commands with editor UI feedback.

Extracted from :mod:`yate.editor` (review 20260926 #5).  The synchronous
runner (extension API), the worker-based async runner, the output overlay
and the ``:font`` installer are one flow that only needs the collaborators
given to :class:`ShellFlows`.  Like :class:`~yate.completion.CompletionFlows`
this module is constructed by the editor and never imports upward.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from functools import partial
from pathlib import Path
from typing import Any

from textual.screen import Screen
from textual.worker import Worker

from yate.editor_view.commandline import PromptBar
from yate.editor_view.modals import OutputScreen
from yate.services import fonts
from yate.services.shell import ShellResult, run_shell, shell_name
from yate.services.workspace import Workspace
from yate.session import EditorSession


class ShellFlows:
    """Runs shell commands and the font installer, reporting on the UI."""

    def __init__(
        self,
        spawn: Callable[..., Worker[object]],
        session: EditorSession,
        workspace: Workspace,
        prompt: PromptBar,
        message: Callable[[str, str], None],
        mounted: Callable[[], bool],
        focus_editor: Callable[[], None],
        refresh: Callable[[], None],
        push_overlay: Callable[[Screen[Any]], None],
    ) -> None:
        # Bound ``App.run_worker``: the background-work verb injected by the
        # editor (this module never holds the App handle itself).
        self._spawn = spawn
        self.session = session
        self.workspace = workspace
        self.prompt = prompt
        self._message = message
        self._mounted = mounted
        self._focus_editor = focus_editor
        self._refresh = refresh
        self._push_overlay = push_overlay

    def run(self, command: str, show_output: bool = True) -> ShellResult | None:
        """Run a shell command synchronously and capture its output.

        Blocking: used by the (synchronous) extension API.  Interactive
        callers go through :meth:`run_later` so the TUI stays responsive
        while the command runs.
        """
        command = command.strip()
        if not command:
            return None
        cwd = self._cwd()
        result = run_shell(command, cwd=cwd)
        if show_output and self._mounted():
            self._show_result(command, result, cwd)
        return result

    def run_later(self, command: str) -> None:
        """Schedule a non-blocking shell run from a sync handler."""
        command = command.strip()
        if not command:
            return
        # the prompt bar stays in its active mode until a command messages
        # back; the background job only reports when it finishes, so close
        # the prompt up front (otherwise focus vanishes when it hides)
        if self.prompt.active_mode in ("shell", "command"):
            self.prompt.idle()
            self._focus_editor()
            self._refresh()
        self._spawn(
            partial(self.run_async, command),
            group="shell", exclusive=False, exit_on_error=False,
        )

    def open_prompt(self) -> None:
        """Open the shell prompt (``:!`` / F2)."""
        self.prompt.activate(
            "shell", placeholder="shell command", on_submit=self.run_later,
        )

    async def run_async(
        self, command: str, show_output: bool = True
    ) -> ShellResult | None:
        """Run a shell command in a worker thread (UI keeps responding)."""
        command = command.strip()
        if not command:
            return None
        cwd = self._cwd()
        self._message(f"running: {command}", "info")
        result = await asyncio.to_thread(run_shell, command, cwd=cwd)
        if show_output and self._mounted():
            self._show_result(command, result, cwd)
        return result

    def _cwd(self) -> Path:
        """The working directory for shell commands (workspace / file / cwd)."""
        doc = self.session.doc
        return (
            self.workspace.root
            or (doc.path.parent if doc.path is not None else None)
            or Path.cwd()
        )

    def _show_result(self, command: str, result: ShellResult, cwd: Path) -> None:
        """Show a finished command's output on the full-screen overlay."""
        body = (
            f"(cwd: {cwd} · {shell_name()})\n\n"
            f"{result.output or '(no output)'}"
        )
        self._push_overlay(OutputScreen(f"$ {command}", body, result.returncode))

    def install_font(self) -> None:
        """``:font``: install the bundled Nerd Font (off the event loop)."""
        # registry lookups / font registration touch subprocess and would
        # freeze the TUI on some systems; run off the event loop
        self._message("checking Nerd Font…", "info")
        self._spawn(
            self._font_async, group="font",
            exclusive=True, exit_on_error=False,
        )

    async def _font_async(self) -> None:
        """Install the font in a worker thread, then report the outcome."""
        status = await asyncio.to_thread(fonts.ensure_font)
        if self._mounted():
            self._message(
                status.detail or ("Nerd Font ready" if status.has_nerd_font
                                  else "font setup failed"),
                "ok" if status.has_nerd_font else "error",
            )
