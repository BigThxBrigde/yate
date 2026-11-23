"""LSP navigation orchestration: definition / references / outline / rename.

The editor owns the concrete collaborators (session, panes, hover popup,
prompt bar) and injects them here; this module only sequences the verbs:
snapshot the cursor, run the bounded LSP request in a worker, discard
stale replies (AC7) and drive the chooser screen / popup / workspace
edit.  No App handle is held (capability injection, issue IKJB0Q); the
prompt seam is :meth:`PromptBar.activate` (``PromptFlows`` has no
``prompt_text`` method) and the open seam is the sync
``DocumentFlows.open_path`` (returns ``None``).
"""

from __future__ import annotations

from collections.abc import Callable
from functools import partial
from pathlib import Path

from textual.screen import Screen

from yate.editor_components.commandline import PromptBar
from yate.editor_components.hover_popup import HoverPopup
from yate.editor_components.lsp_chooser import LspChooserScreen, LspRow
from yate.editor_components.panes import PaneManager
from yate.editor_core import Document
from yate.editor_core.buffer import Pos, TextBuffer
from yate.editor_lsp.manager import LspManager
from yate.editor_lsp.navigation import (
    REASON_NO_READY_SERVER,
    LspCodeAction,
    LspFeatureUnavailable,
    LspLocation,
    LspTextEdit,
    WorkspaceEdit,
)
from yate.editor_lsp.protocol import uri_file_name, uri_to_path
from yate.flows import MessageFn, SpawnFn
from yate.logs import tracing
from yate.session import EditorSession

log = tracing.get_logger(__name__)

#: Message kind of the jump confirmation line.
NAV_JUMP_KIND: str = "info"

#: Text shown when no READY server serves the document at all.
NO_READY_SERVER_TEXT: str = "language server is not ready"


def _check_edit_range(buf: TextBuffer, edit: LspTextEdit) -> None:
    """Raise ``ValueError`` when *edit* cannot be applied safely to *buf*.

    The buffer primitives do not guard against out-of-range positions, and
    a failed mutation corrupts the undo pending region -- so the flow
    validates every range up front and never touches the buffer on a bad
    workspace edit.  Locked (chunked) buffers silently ignore mutations and
    read-only buffers raise, so both are rejected here: otherwise a rename
    reports success although no text changed.  An inverted range is rejected
    for the same reason (``_delete_range`` raises only after earlier edits in
    the batch have already been applied).
    """
    if buf.locked:
        raise ValueError("cannot rename in a locked (chunked) buffer")
    if buf.read_only:
        raise ValueError("cannot rename in a read-only buffer")
    if (edit.start_row, edit.start_col) > (edit.end_row, edit.end_col):
        raise ValueError(f"invalid edit range: {edit!r}")
    line_count = buf.line_count
    for row, col in (
        (edit.start_row, edit.start_col),
        (edit.end_row, edit.end_col),
    ):
        if row >= line_count or col > len(buf.lines[row]):
            raise ValueError(f"edit range out of bounds: {edit!r}")


class LspNavigationFlows:
    """Own the LSP navigation verbs: jump, outline, rename and code actions.

    Every user-visible outcome goes through the injected ``message`` /
    ``push_overlay`` / ``refresh`` callables; a stale worker result is
    dropped without messages or UI changes (AC7).
    """

    def __init__(
        self,
        *,
        spawn: SpawnFn,
        lsp: LspManager,
        session: EditorSession,
        panes: PaneManager,
        popup: HoverPopup,
        open_path: Callable[[Path], None],
        push_overlay: Callable[[Screen[None]], None],
        message: MessageFn,
        refresh: Callable[[], None],
        prompt: PromptBar,
        has_modal_screen: Callable[[], bool],
    ) -> None:
        # Bound ``App.run_worker``: the background-work verb injected by the
        # editor (this module never holds the App handle itself).
        self._spawn = spawn
        self._lsp = lsp
        self._session = session
        self._panes = panes
        self._popup = popup
        self._open_path = open_path
        self._push_overlay = push_overlay
        self._message = message
        self._refresh = refresh
        self._prompt = prompt
        self._has_modal_screen = has_modal_screen
        # Invalidates every in-flight result issued before it.
        self._token: int = 0
        self._doc_path: str | None = None

    # ---------------------------------------------------------------- verbs

    def goto_definition(self) -> None:
        """Request definitions at the cursor and jump or open the chooser."""
        if self._has_modal_screen():
            return
        doc, pos, token = self._snapshot()
        self._spawn(
            partial(self._worker_definition, doc, pos, token),
            group="lsp-navigation", exclusive=True, exit_on_error=False,
        )

    def find_references(self) -> None:
        """Request references at the cursor and open the chooser."""
        if self._has_modal_screen():
            return
        doc, pos, token = self._snapshot()
        self._spawn(
            partial(self._worker_references, doc, pos, token),
            group="lsp-navigation", exclusive=True, exit_on_error=False,
        )

    def show_outline(self) -> None:
        """Request the document symbols and open the outline chooser."""
        if self._has_modal_screen():
            return
        doc, pos, token = self._snapshot()
        self._spawn(
            partial(self._worker_outline, doc, pos, token),
            group="lsp-navigation", exclusive=True, exit_on_error=False,
        )

    def rename_symbol(self) -> None:
        """Open the rename prompt; ESC-cancel is a no-op (never calls submit)."""
        if self._has_modal_screen():
            return
        self._prompt.activate(
            "lsp_rename",
            placeholder="New symbol name",
            on_submit=self._on_rename,
        )

    def show_code_actions(self) -> None:
        """Request code actions at the cursor and open the chooser."""
        if self._has_modal_screen():
            return
        doc, pos, token = self._snapshot()
        self._spawn(
            partial(self._worker_code_actions, doc, pos, token),
            group="lsp-navigation", exclusive=True, exit_on_error=False,
        )

    def show_signature_help(self) -> None:
        """Request signature help and show the hover popup at the cursor."""
        if self._has_modal_screen():
            return
        doc, pos, token = self._snapshot()
        self._spawn(
            partial(self._worker_signature, doc, pos, token),
            group="lsp-navigation", exclusive=True, exit_on_error=False,
        )

    # -------------------------------------------------------------- workers

    async def _worker_definition(
        self, doc: Document, pos: Pos, token: int
    ) -> None:
        """Query textDocument/definition and drive the jump / chooser."""
        try:
            locations = await self._lsp.request_definition(doc, pos[0], pos[1])
        except Exception as exc:  # noqa: BLE001 - degraded to a warning line
            log.debug(
                "definition request failed for %s", doc.path, exc_info=False
            )
            self._message(self._failure_text(exc, "definition"), "warn")
            return
        if self._stale(doc, pos, token):
            return
        if not locations:
            self._message("No definition found", "info")
            return
        if len(locations) == 1:
            self._jump_to_row(self._location_row(locations[0]))
            return
        self._chooser(
            [self._location_row(loc) for loc in locations], "Definitions"
        )

    async def _worker_references(
        self, doc: Document, pos: Pos, token: int
    ) -> None:
        """Query textDocument/references and open the chooser."""
        try:
            locations = await self._lsp.request_references(doc, pos[0], pos[1])
        except Exception as exc:  # noqa: BLE001 - degraded to a warning line
            log.debug(
                "references request failed for %s", doc.path, exc_info=False
            )
            self._message(self._failure_text(exc, "references"), "warn")
            return
        if self._stale(doc, pos, token):
            return
        if not locations:
            self._message("No references found", "info")
            return
        self._chooser(
            [self._location_row(loc) for loc in locations], "References"
        )

    async def _worker_outline(
        self, doc: Document, pos: Pos, token: int
    ) -> None:
        """Query textDocument/documentSymbol and open the outline chooser."""
        try:
            symbols = await self._lsp.request_document_symbols(doc)
        except Exception as exc:  # noqa: BLE001 - degraded to a warning line
            log.debug(
                "outline request failed for %s", doc.path, exc_info=False
            )
            self._message(self._failure_text(exc, "outline"), "warn")
            return
        if self._stale(doc, pos, token):
            return
        if not symbols:
            self._message("No symbols available", "info")
            return
        rows = [
            LspRow(
                label="  " * sym.depth + sym.name,
                detail=sym.detail,
                uri=sym.uri,
                row=sym.row,
                col=sym.col,
                end_row=sym.end_row,
                end_col=sym.end_col,
                kind="symbol",
            )
            for sym in symbols
        ]
        self._chooser(rows, "Outline")

    async def _worker_code_actions(
        self, doc: Document, pos: Pos, token: int
    ) -> None:
        """Query textDocument/codeAction and open the chooser."""
        try:
            actions = await self._lsp.request_code_actions(
                doc, pos[0], pos[1], self._lsp.diagnostics_on_line(doc, pos[0])
            )
        except Exception as exc:  # noqa: BLE001 - degraded to a warning line
            log.debug(
                "code actions request failed for %s", doc.path, exc_info=False
            )
            self._message(self._failure_text(exc, "code actions"), "warn")
            return
        if self._stale(doc, pos, token):
            return
        if not actions:
            self._message("No code actions available", "info")
            return
        row_for: dict[LspRow, LspCodeAction] = {}
        rows: list[LspRow] = []
        for action in actions:
            row = LspRow(
                label=action.title,
                detail=action.kind,
                uri=str(doc.path),
                row=pos[0],
                col=pos[1],
                end_row=pos[0],
                end_col=pos[1],
                kind="action",
            )
            row_for[row] = action
            rows.append(row)
        self._chooser(
            rows,
            "Code actions",
            on_pick=lambda row: self._run_action(
                row_for[row], doc, pos, token
            ),
        )

    async def _worker_signature(
        self, doc: Document, pos: Pos, token: int
    ) -> None:
        """Query textDocument/signatureHelp and drive the hover popup."""
        try:
            signature = await self._lsp.request_signature_help(
                doc, pos[0], pos[1]
            )
        except Exception as exc:  # noqa: BLE001 - degraded to a warning line
            log.debug(
                "signature help request failed for %s", doc.path,
                exc_info=False,
            )
            self._message(self._failure_text(exc, "signature help"), "warn")
            return
        if self._stale(doc, pos, token):
            # A stale result never drives the popup; drop any visible card.
            if self._popup.is_open:
                self._popup.close()
            return
        if signature is None or not signature.text.strip():
            self._message("No signature help available", "info")
            return
        view = self._panes.active_view
        if view is None:
            return
        self._popup.show(
            signature.text,
            view.screen_anchor(pos[0], pos[1]),
            (view.size.width or 80, view.size.height or 20),
            view.gutter_width(),
            origin_y=2,
        )

    async def _worker_rename(
        self, doc: Document, pos: Pos, token: int, new_name: str
    ) -> None:
        """Query textDocument/rename and apply the workspace edit."""
        try:
            edit = await self._lsp.request_rename(
                doc, pos[0], pos[1], new_name
            )
        except Exception as exc:  # noqa: BLE001 - degraded to a warning line
            log.debug(
                "rename request failed for %s", doc.path, exc_info=False
            )
            self._message(self._failure_text(exc, "rename"), "warn")
            return
        if self._stale(doc, pos, token):
            return
        if edit.unsupported:
            self._message(
                "rename: the server returned an unsupported edit", "warn"
            )
            return
        self._apply_workspace_edit(edit)

    async def _worker_apply_action(
        self, action: LspCodeAction, doc: Document, pos: Pos, token: int
    ) -> None:
        """Apply one picked code action: edit first, else executeCommand."""
        try:
            if self._stale(doc, pos, token):
                return
            if action.edit is not None:
                self._apply_workspace_edit(action.edit)
                return
            if not action.command:
                self._message("action cannot be applied", "warn")
                return
            client = await self._lsp.ensure_client(doc)
            if client is None:
                self._message(
                    "action cannot be applied: no language server", "warn"
                )
                return
            await self._lsp.execute_command(
                client, action.command, list(action.arguments)
            )
        except Exception as exc:  # noqa: BLE001 - degraded to a warning line
            log.debug(
                "code action failed for %s", doc.path, exc_info=False
            )
            self._message(f"code action failed: {exc}", "warn")

    # -------------------------------------------------------------- helpers

    def _snapshot(self) -> tuple[Document, Pos, int]:
        """Capture the cursor target and bump the staleness token."""
        doc = self._session.doc
        buf = doc.buffer
        self._doc_path = str(doc.path) if doc.path is not None else None
        self._token += 1
        return doc, (buf.row, buf.col), self._token

    def _stale(self, doc: Document, pos: Pos, token: int) -> bool:
        """True when the reply no longer matches what the user sees.

        Mirrors :meth:`HoverFlows._stale` for the keyboard path: token,
        active document identity, path and cursor must all still match;
        stale results are discarded without messages or UI changes (AC7).
        """
        path_now = str(doc.path) if doc.path is not None else None
        if (
            token != self._token
            or self._session.doc is not doc
            or path_now != self._doc_path
        ):
            return True
        buf = self._session.doc.buffer
        return (buf.row, buf.col) != pos

    def _failure_text(self, exc: Exception, feature: str) -> str:
        """Map a request failure to its explicit message text."""
        if isinstance(exc, LspFeatureUnavailable):
            if exc.reason == REASON_NO_READY_SERVER:
                return f"{feature} unavailable: {NO_READY_SERVER_TEXT}"
            return f"{feature} unavailable: server does not support {exc.feature}"
        return f"{feature} failed: {exc}"

    def _location_row(self, loc: LspLocation) -> LspRow:
        """Build one chooser row from an LSP location."""
        return LspRow(
            label=uri_file_name(loc.uri),
            detail=f"line {loc.row + 1}",
            uri=loc.uri,
            row=loc.row,
            col=loc.col,
            end_row=loc.end_row,
            end_col=loc.end_col,
            kind="location",
        )

    def _chooser(
        self,
        rows: list[LspRow],
        title: str,
        on_pick: Callable[[LspRow], None] | None = None,
    ) -> None:
        """Push the chooser overlay; the default pick verb is the jump."""
        self._push_overlay(
            LspChooserScreen(
                rows, title, on_pick if on_pick is not None else self._jump_to_row
            )
        )

    def _jump_to_row(self, row: LspRow) -> None:
        """Open the row's target document and land on its position."""
        path = uri_to_path(row.uri)
        self._open_path(path)
        doc = self._session.is_open(path)
        if doc is None:
            self._message(f"cannot jump to {row.label}", "warn")
            return
        buf = doc.buffer
        jump_row = min(row.row, buf.line_count - 1)
        jump_col = min(row.col, len(buf.lines[jump_row]))
        buf.set_cursor((jump_row, jump_col))
        buf.anchor = None
        for view in self._panes.views_for(doc):
            view.reveal_cursor()
        self._refresh()
        self._message(f"jumped to {doc.name}:{jump_row + 1}", NAV_JUMP_KIND)

    def _on_rename(self, new_name: str) -> None:
        """Prompt submit: snapshot and spawn the rename worker."""
        if self._has_modal_screen():
            return
        doc, pos, token = self._snapshot()
        self._spawn(
            partial(self._worker_rename, doc, pos, token, new_name),
            group="lsp-navigation", exclusive=True, exit_on_error=False,
        )

    def _run_action(
        self, action: LspCodeAction, doc: Document, pos: Pos, token: int
    ) -> None:
        """Spawn the worker applying one picked code action."""
        self._spawn(
            partial(self._worker_apply_action, action, doc, pos, token),
            group="lsp-navigation", exclusive=True, exit_on_error=False,
        )

    def _apply_workspace_edit(self, edit: WorkspaceEdit) -> None:
        """Apply the workspace edit in memory, rolling back on failure.

        Every URI is pre-resolved and pre-opened; text edits are applied
        per document bottom-up so earlier positions stay valid.  Any
        failure restores every affected buffer from its snapshot.  No
        disk writes happen here (the sync layer owns persistence).
        Documents the rename newly opened are tracked (M5): on failure
        the message discloses that they were left unsaved, and the
        success message always says the changes are in-memory only.
        """
        docs: dict[str, Document] = {}
        opened_names: list[str] = []
        for uri in edit.changes:
            path = uri_to_path(uri)
            if not path.is_file():
                self._message(f"rename failed: cannot open {path.name}", "warn")
                return
            doc = self._session.is_open(path)
            if doc is None:
                self._open_path(path)
                doc = self._session.is_open(path)
                if doc is not None:
                    opened_names.append(path.name)
            if doc is None:
                self._message(f"rename failed: cannot open {path.name}", "warn")
                return
            docs[uri] = doc
        # Phase 1: validate every edit against its live buffer before any
        # mutation.  A rejected edit (out of bounds / inverted / locked /
        # read-only) means nothing changed, so there is nothing to roll back --
        # and rolling back a read-only buffer would raise a second error that
        # masks the original one.
        disclosure = (
            f" (newly opened {', '.join(opened_names)} left unsaved)"
            if opened_names
            else ""
        )
        try:
            for uri, edits in edit.changes.items():
                buf = docs[uri].buffer
                try:
                    for text_edit in edits:
                        _check_edit_range(buf, text_edit)
                except ValueError as exc:
                    # Name the offending file: other failure branches above
                    # report path.name, so keep the same level of detail.
                    raise ValueError(f"{exc} ({uri_to_path(uri).name})") from exc
        except ValueError as exc:
            log.debug("workspace edit rejected: %s", exc, exc_info=False)
            self._message(f"rename failed: {exc}{disclosure}", "warn")
            return

        # Phase 2: apply.  Only now can a failure leave partial mutations, so
        # this is where the snapshot rollback applies.
        snapshots: list[tuple[Document, str, Pos]] = [
            (doc, doc.buffer.get_text(), doc.buffer.cursor)
            for doc in docs.values()
        ]
        applied = 0
        try:
            for uri, edits in edit.changes.items():
                buf = docs[uri].buffer
                ordered = sorted(
                    edits,
                    key=lambda e: (e.start_row, e.start_col),
                    reverse=True,
                )
                for text_edit in ordered:
                    buf.replace_range(
                        (text_edit.start_row, text_edit.start_col),
                        (text_edit.end_row, text_edit.end_col),
                        text_edit.text,
                    )
                applied += len(edits)
        except Exception as exc:  # noqa: BLE001 - rolled back below
            log.debug("workspace edit failed: %s", exc, exc_info=False)
            for doc, text, cursor in snapshots:
                # Replace the whole *current* content: a partially applied
                # edit can leave fewer/more rows than the snapshot had, so
                # the restore range must follow the live buffer bounds.
                buf = doc.buffer
                doc.buffer.replace_range(
                    (0, 0), (buf.line_count - 1, len(buf.lines[-1])), text
                )
                doc.buffer.set_cursor(cursor)
            self._refresh()
            self._message(f"rename failed: {exc}{disclosure}", "warn")
            return
        self._refresh()
        self._message(
            f"Renamed {applied} occurrence(s) in {len(docs)} file(s) "
            "(unsaved; save to apply)",
            "info",
        )
