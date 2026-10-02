"""UI-side LSP glue: keeps the servers in sync with the documents.

Extracted from :mod:`yate.editor` (review 20260926 #5).  The worker
dispatch (didClose / didOpen), the repaint-on-manager-event callback, the
diagnostic echo on the message line and the ``:diagnostics`` overlay are
one flow that only needs the collaborators given to :class:`LspSync` --
no editor state beyond them.  Like :class:`~yate.completion.CompletionFlows`
this module is constructed by the editor and never imports upward.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import partial
from typing import Any

from textual.screen import Screen
from textual.worker import Worker

from yate.editor_core import Document
from yate.editor_lsp import LspManager
from yate.editor_view.commandline import PromptBar
from yate.editor_view.modals import OutputScreen
from yate.editor_view.panes import PaneManager
from yate.editor_view.statusbar import StatusBar
from yate.session import EditorSession


class LspSync:
    """Drives the LSP manager from editor events and reports diagnostics."""

    def __init__(  # noqa: Any - push_overlay accepts any Textual Screen type
        self,
        spawn: Callable[..., Worker[object]],
        lsp: LspManager,
        session: EditorSession,
        panes: PaneManager,
        status_bar: StatusBar,
        prompt: PromptBar,
        message: Callable[[str, str], None],
        mounted: Callable[[], bool],
        push_overlay: Callable[[Screen[Any]], None],
    ) -> None:
        # Bound ``App.run_worker``: the background-work verb injected by the
        # editor (this module never holds the App handle itself).
        self._spawn = spawn
        self.lsp = lsp
        self.session = session
        self.panes = panes
        self.status_bar = status_bar
        self.prompt = prompt
        self._message = message
        self._mounted = mounted
        self._push_overlay = push_overlay

    def documents_closed(self, closed: list[Document]) -> None:
        """Session hook: tell the servers the documents were closed.

        Hand the worker the *bound coroutine function*, never the coroutine:
        an eagerly built coroutine lives outside the worker's lifecycle, so a
        worker that never starts (quit cancels the "lsp-sync" group) drops
        the didClose and leaks "coroutine was never awaited".
        """
        for doc in closed:
            self._spawn(
                partial(self.lsp.on_document_closed, doc),
                group="lsp-sync", exclusive=False, exit_on_error=False,
            )

    def doc_shown_later(self) -> None:
        """Open the active document on its server once a server is registered."""
        doc = self.session.doc
        if not self.lsp.supports(doc) or self.lsp.is_open(doc):
            return
        self._spawn(
            partial(self.lsp.on_document_shown, doc),
            group="lsp-sync", exclusive=False, exit_on_error=False,
        )

    def on_event(self, event: str) -> None:
        """Manager callback (event loop thread): repaint after LSP updates."""
        if not self._mounted():
            return
        for view in self.panes.all_views():
            view.refresh()
        self.status_bar.refresh_status()
        if event == "diagnostics":
            self.update_echo()

    def update_echo(self) -> None:
        """Show the diagnostic under the cursor on the message line."""
        prompt = self.prompt
        if prompt.active_mode is not None:
            return
        buf = self.session.buffer
        diag = self.lsp.diagnostic_at(self.session.doc, buf.row, buf.col)
        if diag is not None:
            glyph = "✖" if diag.is_error else ("▲" if diag.is_warning else "●")
            source = f"{diag.source}: " if diag.source else ""
            prompt.write(
                f"{glyph} {source}{diag.message}",
                kind="error" if diag.is_error else "warn",
                owner="lsp",
            )
        elif prompt.owner == "lsp":
            prompt.idle()

    def show_diagnostics(self) -> None:
        """``:diagnostics`` -- list the active document's LSP diagnostics."""
        doc = self.session.doc
        diags = self.lsp.diagnostics_for(doc)
        if not diags:
            self._message("no diagnostics", "ok")
            return
        labels = {1: "error", 2: "warning", 3: "info", 4: "hint"}
        lines = [
            f"L{d.start_row + 1}:{d.start_col + 1}  "
            f"{labels.get(d.severity, str(d.severity)).upper():7}  "
            f"{('[' + d.source + '] ') if d.source else ''}{d.message}"
            for d in diags
        ]
        errors, warnings = self.lsp.counts_for(doc)
        title = f"diagnostics — {errors} error(s), {warnings} warning(s)"
        self._push_overlay(OutputScreen(title, "\n".join(lines), 0))
