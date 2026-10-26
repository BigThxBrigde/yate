"""Owns language server registry, document sync, completion and diagnostics.

The manager is UI independent: it never imports textual.  The application
hooks four document lifecycle moments into it:

* :meth:`on_document_shown`  -- a tab is opened or focused (didOpen)
* :meth:`notify_edit`        -- buffer text may have changed (debounced didChange)
* :meth:`notify_saved`       -- the buffer was written (didSave)
* :meth:`on_document_closed` -- a tab is closed (didClose)

and calls :meth:`request_completion` for the popup.  Incoming
``publishDiagnostics`` notifications are stored per URI; the optional
``on_event`` callback (invoked on the event loop) lets the UI repaint.

Wire-format parsing (UTF-16 <-> buffer coordinates, completion item and
diagnostics payload decoding) lives in :mod:`yate.editor_lsp.parsing`;
this module keeps the state orchestration and the test-pinned seams
(``_unwrap_completion`` / ``_parse_diagnostics`` forward to it).
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from yate.editor_core.document import Document
from yate.logs import tracing

from yate.editor_lsp import parsing, protocol
from yate.editor_lsp.client import (
    Completion,
    Diagnostic,
    LspClient,
    LspError,
    ServerConfig,
    ServerState,
)
from yate.editor_lsp.parsing import _from_utf16 as _from_utf16
from yate.editor_lsp.parsing import _to_utf16 as _to_utf16

#: TextDocumentSyncKind.Full -- resending the whole buffer on every change is
#: supported by every server and avoids fragile incremental position math.
_SYNC_FULL: int = 1

#: Debounce for didChange (keystrokes coalesce into one notification).
CHANGE_DEBOUNCE_S: float = 0.25

#: Trigger kinds for textDocument/completion.
TRIGGER_INVOKED: int = 1
TRIGGER_CHARACTER: int = 2

ClientKey = tuple[str, str]

#: Trace logger ("yate.editor_lsp.manager"); silent unless yate_trace is on.
log = tracing.get_logger(__name__)


@dataclass
class OpenDocState:
    """State of one text document currently open with a server.

    ``version``/``last_synced`` advance only after a successful didChange
    notify; pushes whose text matches ``last_synced`` are skipped.
    ``last_synced_version`` mirrors ``buffer.content_version`` at the moment
    the text was last sent, giving :meth:`LspManager.notify_edit` an O(1)
    gate that avoids materializing the full document text on every key.
    """

    uri: str
    config_name: str
    client_key: ClientKey
    language_id: str
    version: int
    last_synced: str
    last_synced_version: int
    #: The open document, kept so incoming server positions (UTF-16 code
    #: units) can be converted back to buffer columns (code points).
    doc: Document


#: ``workspace_root()`` -- the directory language servers are rooted at
#: (``None`` until the editor knows one).
type RootQuery = Callable[[], Path | None]

#: ``on_event(event, doc)`` -- the manager's outbound notification:
#: ``"state"`` whenever a server starts, stops or changes state (``doc``
#: always ``None``), ``"diagnostics"`` when a publish arrives (``doc`` is
#: the document the published diagnostics belong to, ``None`` only when the
#: uri is not an open document).  The consumer repaints from it and echoes
#: the diagnostic count (see :meth:`yate.flows.lsp_sync.LspSync.on_event`).
type EventHook = Callable[[str, Document | None], None]

#: ``client_factory(config, root)`` -- build the client for one server config;
#: replaceable after construction through :meth:`LspManager.set_client_factory`.
type ClientFactory = Callable[[ServerConfig, Path], LspClient]


class LspManager:
    """Registry of server configs plus per-document LSP session state."""

    def __init__(
        self,
        *,
        workspace_root: RootQuery | None = None,
        on_event: EventHook | None = None,
        client_factory: ClientFactory | None = None,
    ) -> None:
        self._configs: list[ServerConfig] = []
        self._by_filetype: dict[str, ServerConfig] = {}
        self._clients: dict[ClientKey, LspClient] = {}
        self._starting: dict[ClientKey, asyncio.Task[LspClient | None]] = {}
        self._open: dict[str, OpenDocState] = {}
        self._diagnostics: dict[str, list[Diagnostic]] = {}
        #: Per-row diagnostic index: ``uri -> row -> [Diagnostic]``.  Rebuilt
        # from scratch at every publish point (the single writer of
        # ``_diagnostics``) so the two can never drift apart.  Multi-row
        # diagnostics are registered on every row they cover, which makes
        # :meth:`diagnostics_on_line` an O(1) lookup per rendered line
        # instead of a full-table copy + filter per call.
        self._diagnostics_by_row: dict[str, dict[int, list[Diagnostic]]] = {}
        self._change_timers: dict[str, asyncio.TimerHandle] = {}
        #: Cache of ``path_to_uri`` results (a real filesystem call on
        #: Windows); invalidated when a document leaves the session.
        self._uri_cache: dict[Path, str] = {}
        self._bg_tasks: set[asyncio.Task[None]] = set()
        self._shutting_down = False
        self._workspace_root = workspace_root
        self._on_event = on_event
        self._client_factory = client_factory

    def set_client_factory(
        self, factory: ClientFactory | None
    ) -> None:
        """Replace the client constructor (used by tests and embedders)."""
        self._client_factory = factory

    # ------------------------------------------------------------ registry

    def register_server(self, config: ServerConfig) -> None:
        """Register (or replace) a language server configuration."""
        existing = next((c for c in self._configs if c.name == config.name), None)
        if existing is not None:
            self._configs.remove(existing)
            # A replacement invalidates cached clients (e.g. a failed
            # executable probe followed by an extension re-registering a
            # working command) and any documents opened on the old config.
            self._drop_cached_state(config.name)
        self._configs.append(config)
        self._rebuild_filetype_index()
        if existing is not None:
            # The replacement can add, remove or swap a server the UI is
            # already showing.  Fire only after the filetype index above is
            # rebuilt so synchronous repaints cannot observe the stale
            # mapping; first registration fires nothing (nothing was on
            # screen yet).
            self._fire("state")
        log.info(
            "registered server %s (command=%r filetypes=%s)%s",
            config.name, config.command, list(config.filetypes),
            " (replaced an existing registration)" if existing is not None else "",
        )

    def unregister_server(self, name: str) -> bool:
        """Remove the configuration *name*; ``False`` when it was not there.

        Used by the extension loader to roll back a failed ``setup`` (A13):
        the cached clients are stopped and the documents opened on the old
        config are forgotten, so no ghost server survives the rollback.
        """
        existing = next((c for c in self._configs if c.name == name), None)
        if existing is None:
            return False
        self._configs.remove(existing)
        self._drop_cached_state(name)
        self._rebuild_filetype_index()
        self._fire("state")
        log.info("unregistered server %s", name)
        return True

    def _drop_cached_state(self, name: str) -> None:
        """Stop and forget every cached client / document of server *name*."""
        for key in [k for k in self._clients if k[0] == name]:
            client = self._clients.pop(key, None)
            if client is not None:
                self._spawn_bg(client.stop())
        for task in [t for k, t in self._starting.items() if k[0] == name]:
            task.cancel()
        self._starting = {k: v for k, v in self._starting.items() if k[0] != name}
        stale_urls = [u for u, st in self._open.items() if st.config_name == name]
        for uri in stale_urls:
            self._open.pop(uri, None)
            self._forget_diagnostics(uri)
            self._drop_uri_cache(uri)

    def _drop_uri_cache(self, uri: str) -> None:
        """Forget the cached URI of a document leaving the session."""
        for path, cached in list(self._uri_cache.items()):
            if cached == uri:
                del self._uri_cache[path]

    def _rebuild_filetype_index(self) -> None:
        """Rebuild the filetype index; later registrations override earlier."""
        self._by_filetype.clear()
        for cfg in self._configs:
            for ft in cfg.filetypes:
                self._by_filetype[ft] = cfg

    def config_names(self) -> list[str]:
        """Registered server config names (in registration order)."""
        return [c.name for c in self._configs]

    def configs(self) -> list[ServerConfig]:
        """The registered server configs (read-only view for diagnostics and
        the status bar)."""
        return list(self._configs)

    def config_for(self, filetype: str) -> ServerConfig | None:
        """The server config claiming *filetype*, or ``None``."""
        return self._by_filetype.get(filetype)

    def supports(self, doc: Document) -> bool:
        """True when some registered server claims this document's type."""
        return doc.path is not None and self.config_for(doc.filetype) is not None

    def is_open(self, doc: Document) -> bool:
        """True when *doc* already has a live didOpen on its server."""
        return doc.path is not None and self._uri(doc) in self._open

    def states(self) -> dict[str, ServerState]:
        """One state per registered server (aggregated over its clients)."""
        result: dict[str, ServerState] = {c.name: ServerState.CONFIGURED for c in self._configs}
        # Higher wins: a live READY server dominates; FAILED must still show
        # over the baseline CONFIGURED so the user can see a broken setup.
        rank = {
            ServerState.CONFIGURED: 0,
            ServerState.STOPPED: 1,
            ServerState.FAILED: 2,
            ServerState.STARTING: 3,
            ServerState.READY: 4,
        }
        for (name, _root), client in self._clients.items():
            if rank.get(client.state, 0) > rank.get(result.get(name, ServerState.CONFIGURED), 0):
                result[name] = client.state
        return result

    def state_for_doc(self, doc: Document) -> ServerState | None:
        """Aggregated server state relevant to *doc*, for the status bar."""
        cfg = self.config_for(doc.filetype)
        return self.states().get(cfg.name) if cfg is not None else None

    def error_for(self, config_name: str) -> str:
        """The failure message of a FAILED client for *config_name* (else "")."""
        for (name, _root), client in self._clients.items():
            if name == config_name and client.state is ServerState.FAILED:
                return client.error
        return ""

    def trigger_characters_for(self, doc: Document) -> tuple[str, ...]:
        """Union of trigger characters of ready clients handling *doc*."""
        chars: set[str] = set()
        for client in self._clients.values():
            if client.state is ServerState.READY and client.config.handles(doc.filetype):
                chars.update(client.trigger_characters)
        return tuple(sorted(chars))

    # --------------------------------------------------------- root/client

    def root_for(self, config: ServerConfig, doc: Document) -> Path:
        """Resolve the workspace root to start the server in for *doc*.

        The editor workspace wins when it contains the file; otherwise the
        closest directory holding one of *config*'s root markers (searching
        from the file's own directory upward), else the file's directory.
        """
        assert doc.path is not None
        doc_dir = doc.path.parent
        ws = self._workspace_root() if self._workspace_root is not None else None
        if ws is not None:
            try:
                doc.path.resolve().relative_to(ws.resolve())
                return ws
            except ValueError:
                pass
        for directory in (doc_dir, *doc_dir.parents):
            if any((directory / marker).exists() for marker in config.root_markers):
                return directory
        return doc_dir

    def _make_client(self, config: ServerConfig, root: Path) -> LspClient:
        if self._client_factory is not None:
            return self._client_factory(config, root)
        return LspClient(
            config, root,
            on_notification=self.handle_notification,
        )

    async def ensure_client(self, doc: Document) -> LspClient | None:
        """Start (once) and return the client for *doc*, or None on failure."""
        if doc.path is None:
            return None
        config = self.config_for(doc.filetype)
        if config is None:
            return None
        root = self.root_for(config, doc)
        key: ClientKey = (config.name, str(root))
        client = self._clients.get(key)
        if client is not None:
            if client.state is ServerState.READY:
                return client
            if client.state is ServerState.FAILED:
                return None
            task = self._starting.get(key)
            if task is not None:
                return await task
            return client
        task = asyncio.create_task(self._start_client(key, config, root))
        self._starting[key] = task
        try:
            return await task
        finally:
            # Pop only while we still own the slot: register_server may
            # have cancelled this start and a newer task may occupy the
            # key -- an unconditional pop would untrack the new start and
            # let a third caller spawn a duplicate client.
            if self._starting.get(key) is task:
                self._starting.pop(key, None)

    async def _start_client(
        self, key: ClientKey, config: ServerConfig, root: Path
    ) -> LspClient | None:
        if not config.command:
            # Extension registered a server without an available executable.
            client = self._make_client(config, root)
            client.state = ServerState.FAILED
            client.error = (
                f"{config.name}: no language server executable found "
                "(install one or configure the command)"
            )
            self._clients[key] = client
            self._fire("state")
            log.warning("server %s: no executable configured", config.name)
            return None
        client = self._make_client(config, root)
        self._clients[key] = client
        try:
            await client.start()
        except (LspError, OSError) as exc:
            # Missing executable / timeout -- keep FAILED state, never crash.
            self._fire("state")
            log.warning("server %s failed to start: %s", config.name, exc)
            return None
        self._fire("state")
        log.info("server %s started (root=%s)", config.name, root)
        return client

    # ----------------------------------------------------- doc lifecycle

    async def on_document_shown(self, doc: Document) -> None:
        """Open *doc* on its server when it becomes the active document."""
        if doc.path is None or self._uri(doc) in self._open:
            return
        config = self.config_for(doc.filetype)
        if config is None:
            return
        client = await self.ensure_client(doc)
        if client is None:
            return
        root = self.root_for(config, doc)
        uri = self._uri(doc)
        text = doc.buffer.get_text()
        try:
            await client.notify("textDocument/didOpen", {
                "textDocument": {
                    "uri": uri,
                    "languageId": config.language_id(doc.filetype),
                    "version": 1,
                    "text": text,
                },
            })
        except (LspError, OSError):
            return
        self._open[uri] = OpenDocState(
            uri=uri,
            config_name=config.name,
            client_key=(config.name, str(root)),
            language_id=config.language_id(doc.filetype),
            version=1,
            last_synced=text,
            last_synced_version=doc.buffer.content_version,
            doc=doc,
        )
        # Pending diagnostics may already be stale relative to buffer content;
        # the server republishes after didOpen.
        self._forget_diagnostics(uri)

    async def on_document_closed(self, doc: Document) -> None:
        """Forget *doc*'s didOpen state and notify didClose (best effort)."""
        if doc.path is None:
            return
        uri = self._uri(doc)
        state = self._open.pop(uri, None)
        self._change_timers.pop(uri, None)
        self._drop_uri_cache(uri)
        if state is None:
            return
        client = self._clients.get(state.client_key)
        if client is not None and client.state is ServerState.READY:
            try:
                await client.notify("textDocument/didClose",
                                   {"textDocument": {"uri": uri}})
            except (LspError, OSError) as exc:
                # The document already left the session, so a lost didClose
                # only leaves the server's view stale -- logged (never
                # raised) to keep the close path total and traceable.
                log.debug("didClose failed for %s: %s", uri, exc)

    def notify_edit(self, doc: Document) -> None:
        """Schedule a debounced full-text didChange (no-op when unchanged)."""
        if doc.path is None:
            return
        uri = self._uri(doc)
        state = self._open.get(uri)
        if state is None:
            return
        # O(1) gate: an equal content_version proves the text cannot have
        # changed, so skip the O(document) ``get_text()`` on this keystroke.
        if doc.buffer.content_version == state.last_synced_version:
            return
        text = doc.buffer.get_text()
        if text == state.last_synced:
            # Double insurance: the version can advance without the text
            # changing (e.g. chunked fill) -- nothing to send then either.
            return
        timer = self._change_timers.pop(uri, None)
        if timer is not None:
            timer.cancel()
        loop = asyncio.get_running_loop()
        self._change_timers[uri] = loop.call_later(
            CHANGE_DEBOUNCE_S, self._flush_change, doc, uri
        )

    def _flush_change(self, doc: Document, uri: str) -> None:
        self._change_timers.pop(uri, None)
        state = self._open.get(uri)
        if state is None or self._shutting_down:
            return
        # Materialize the text only here (inside the debounce callback), not
        # on every keystroke; the buffer may have changed since the timer was
        # armed, which is exactly what we want to send.
        text = doc.buffer.get_text()
        buffer_version = doc.buffer.content_version
        if text == state.last_synced:
            return
        client = self._clients.get(state.client_key)
        if client is None or client.state is not ServerState.READY:
            return
        # Do NOT advance version/last_synced here: the server may be in the
        # middle of processing a previous didChange, or the notification
        # itself may fail.  We only advance after a successful notify so
        # that a subsequent edit (which calls ``notify_edit`` again with
        # the same text) won't short-circuit against a stale last_synced.
        next_version = state.version + 1
        self._spawn_bg(
            self._send_change(
                client, uri, state, next_version, text, buffer_version
            )
        )

    def _spawn_bg(self, coro: Awaitable[None]) -> None:
        """Track a fire-and-forget notification task until it settles."""
        task: asyncio.Task[None] = asyncio.ensure_future(coro)
        self._bg_tasks.add(task)
        task.add_done_callback(self._bg_tasks.discard)

    async def _send_change(
        self,
        client: LspClient,
        uri: str,
        state: OpenDocState,
        version: int,
        text: str,
        buffer_version: int,
    ) -> None:
        """Send a full-text didChange; advance state.version/last_synced only
        after a successful notify so a failed call leaves ``last_synced``
        stale and lets the next :meth:`notify_edit` retry naturally.
        ``buffer_version`` is the ``buffer.content_version`` snapshot taken
        when *text* was materialized."""
        try:
            await client.notify("textDocument/didChange", {
                "textDocument": {"uri": uri, "version": version},
                "contentChanges": [{"text": text}],
            })
        except (LspError, OSError):
            return
        # Re-check the document hasn't been closed while we awaited.
        if self._open.get(uri) is state and not self._shutting_down:
            state.version = version
            state.last_synced = text
            state.last_synced_version = buffer_version

    async def notify_saved(self, doc: Document) -> None:
        """Send didSave for *doc* when it is open on a ready client."""
        state = self._open.get(self._uri(doc)) if doc.path is not None else None
        if state is None:
            return
        client = self._clients.get(state.client_key)
        if client is not None and client.state is ServerState.READY:
            try:
                await client.notify("textDocument/didSave",
                                   {"textDocument": {"uri": state.uri}})
            except (LspError, OSError) as exc:
                # Best-effort notification: the server's failure state is
                # already surfaced by states(), so this stays at debug level.
                log.debug("didSave failed for %s: %s", state.uri, exc)

    # ---------------------------------------------------------- completion

    async def request_completion(
        self,
        doc: Document,
        row: int,
        col: int,
        *,
        prefix_start_col: int,
        trigger_kind: int = TRIGGER_INVOKED,
        trigger_character: str | None = None,
    ) -> list[Completion]:
        """Fetch completions at the cursor; empty list when unavailable."""
        client = await self.ensure_client(doc)
        if client is None or doc.path is None:
            return []
        uri = self._uri(doc)
        # Flush any pending debounced didChange so the server completes
        # against the text the cursor actually points into: the completion
        # debounce (0.12s) is shorter than the didChange one (0.25s), and
        # without this the request races ahead of the edited text.
        state = self._open.get(uri)
        timer = self._change_timers.pop(uri, None)
        if timer is not None:
            timer.cancel()
        if state is not None and client.state is ServerState.READY:
            text = doc.buffer.get_text()
            if text != state.last_synced:
                await self._send_change(
                    client, uri, state, state.version + 1, text,
                    doc.buffer.content_version,
                )
        context: dict[str, Any] = {"triggerKind": trigger_kind}
        if trigger_character is not None:
            context["triggerCharacter"] = trigger_character
        cursor_line = (
            doc.buffer.lines[row] if row < doc.buffer.line_count else ""
        )
        params: dict[str, Any] = {
            "textDocument": {"uri": uri},
            "position": {"line": row, "character": _to_utf16(cursor_line, col)},
            "context": context,
        }
        try:
            request_id, future = await client.start_request(
                "textDocument/completion", params
            )
            try:
                raw = await future
            finally:
                # Mirror ``LspClient.request``: drop the pending entry once
                # the future settles (success, error or cancellation) so the
                # response payload does not stay referenced until teardown.
                client.settle_request(request_id)
        except asyncio.CancelledError:
            # Cancellation is control flow, not "no completions": the
            # awaiting caller (Task.cancel / wait_for) must observe it.
            raise
        except (LspError, OSError):
            return []
        # A malformed server response must not kill the completion worker:
        # it runs with exit_on_error=False, so an exception here would be
        # swallowed silently.  Degrade to "no completions" instead, like a
        # failed request does above.
        try:
            items, item_defaults = self._unwrap_completion(raw)
            completions: list[Completion] = []
            for item in items:
                parsed = parsing._parse_completion_item(
                    item, item_defaults, doc, row, col, prefix_start_col
                )
                if parsed is not None:
                    completions.append(parsed)
            completions.sort(key=lambda c: (c.sort_text or c.label.lower(), c.label))
        except Exception:  # noqa: BLE001 - rationale in the comment above
            log.exception("failed to parse completion response for %s", uri)
            return []
        return completions

    @staticmethod
    def _unwrap_completion(raw: Any) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Forward to :func:`parsing._unwrap_completion`.

        Thin delegate kept on the class (main plan section 4, "keep thin
        delegates"): :mod:`tests.test_lsp` monkeypatches this seam and
        expects :meth:`request_completion` to observe the patch.
        """
        return parsing._unwrap_completion(raw)

    # ---------------------------------------------------------- diagnostics

    def handle_notification(self, method: str, params: dict[str, Any]) -> None:
        """Entry point for server-initiated notifications.

        ``publishDiagnostics`` is stored per URI and fires the
        ``diagnostics`` event; log/telemetry/progress messages are
        acknowledged but not surfaced yet.
        """
        if method == "textDocument/publishDiagnostics":
            uri = params.get("uri")
            if isinstance(uri, str):
                state = self._open.get(uri)
                lines = state.doc.buffer.lines if state is not None else None
                parsed = self._parse_diagnostics(
                    params.get("diagnostics"), lines
                )
                self._diagnostics[uri] = parsed
                self._index_diagnostics(uri, parsed)
                log.debug(
                    "diagnostics published: %s (%d item(s))",
                    uri.rsplit("/", 1)[-1], len(self._diagnostics[uri]),
                )
                # The diagnostics belong to the document the server published
                # for -- any open document, not necessarily the active one
                # (a background pane's file gets publishes too).
                self._fire("diagnostics", state.doc if state is not None else None)
        elif method in (
            "window/logMessage",
            "telemetry/event",
            "$/progress",
            "window/showMessage",
        ):
            pass  # acknowledged but not surfaced yet

    @staticmethod
    def _parse_diagnostics(
        raw: Any, lines: list[str] | None = None
    ) -> list[Diagnostic]:
        """Forward to :func:`parsing._parse_diagnostics`.

        Thin delegate kept on the class (main plan section 4, "keep thin
        delegates"): :mod:`tests.test_lsp` calls this seam directly and
        :meth:`handle_notification` routes through it.
        """
        return parsing._parse_diagnostics(raw, lines)

    def _index_diagnostics(self, uri: str, diags: list[Diagnostic]) -> None:
        """(Re)build the per-row index for *uri* from *diags*.

        The single source of truth stays ``_diagnostics``; this index is
        rebuilt from scratch on every publish so it can never go stale.
        """
        by_row: dict[int, list[Diagnostic]] = {}
        for d in diags:
            for row in range(d.start_row, d.end_row + 1):
                by_row.setdefault(row, []).append(d)
        self._diagnostics_by_row[uri] = by_row

    def _forget_diagnostics(self, uri: str) -> None:
        """Drop the stored diagnostics and the per-row index for *uri*."""
        self._diagnostics.pop(uri, None)
        self._diagnostics_by_row.pop(uri, None)

    def diagnostics_for(self, doc: Document) -> list[Diagnostic]:
        """The stored diagnostics for *doc* (a copy, sorted by position)."""
        if doc.path is None:
            return []
        return list(self._diagnostics.get(self._uri(doc), []))

    def counts_for(self, doc: Document) -> tuple[int, int]:
        """(errors, warnings) for *doc*."""
        diags = self.diagnostics_for(doc)
        errors = sum(1 for d in diags if d.is_error)
        warnings = sum(1 for d in diags if d.is_warning)
        return errors, warnings

    def diagnostic_at(self, doc: Document, row: int, col: int) -> Diagnostic | None:
        """The most severe diagnostic whose range covers (row, col)."""
        best: Diagnostic | None = None
        for d in self.diagnostics_for(doc):
            if d.start_row <= row <= d.end_row:
                if d.start_row == d.end_row:
                    covers = d.start_col <= col < max(d.end_col, d.start_col + 1)
                elif row == d.start_row:
                    covers = col >= d.start_col
                elif row == d.end_row:
                    covers = col <= d.end_col
                else:
                    covers = True
                if covers and (best is None or d.severity < best.severity):
                    best = d
        return best

    def diagnostics_on_line(self, doc: Document, row: int) -> list[Diagnostic]:
        """The stored diagnostics whose vertical range covers *row*.

        O(1) via the per-row index (rebuilt at each publish point); a copy
        is returned so callers cannot mutate the index.
        """
        if doc.path is None:
            return []
        by_row = self._diagnostics_by_row.get(self._uri(doc))
        if not by_row:
            return []
        return list(by_row.get(row, ()))

    # ------------------------------------------------------------- teardown

    async def shutdown_all(self) -> None:
        """Stop every client and cancel timers, starts and pending pushes.

        The interruption order matters: clients first (unblocks start tasks
        still waiting on their handshake), then start tasks, then in-flight
        didChange pushes -- all bounded so teardown cannot hang.
        """
        log.info("shutting down %s server client(s)", len(self._clients))
        self._shutting_down = True
        for timer in self._change_timers.values():
            timer.cancel()
        self._change_timers.clear()
        # Clients first: stopping one unblocks a ``_start_client`` task that
        # is still waiting on its initialize handshake.
        clients = list(self._clients.values())
        for client in clients:
            try:
                await client.stop()
            except Exception:  # noqa: BLE001 - one bad server must not block the rest
                log.exception("client failed to stop cleanly")
        # Let the interrupted start tasks run their cleanup instead of
        # dropping them mid-flight (orphans print "Task exception was never
        # retrieved" and can keep subprocess transports half-open).
        starting = [t for t in self._starting.values() if not t.done()]
        if starting:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*starting, return_exceptions=True),
                    timeout=2.0,
                )
            except TimeoutError:
                for task in starting:
                    task.cancel()
                await asyncio.gather(*starting, return_exceptions=True)
        # In-flight didChange notifications must not outlive the loop.
        bg_tasks = [t for t in self._bg_tasks if not t.done()]
        for task in bg_tasks:
            task.cancel()
        if bg_tasks:
            await asyncio.gather(*bg_tasks, return_exceptions=True)
        self._bg_tasks.clear()
        self._clients.clear()
        self._starting.clear()

    # -------------------------------------------------------------- helpers

    def _uri(self, doc: Document) -> str:
        assert doc.path is not None
        cached = self._uri_cache.get(doc.path)
        if cached is None:
            # ``path_to_uri`` resolves the path (a real filesystem call on
            # Windows); cache the result per document path.
            cached = protocol.path_to_uri(doc.path)
            self._uri_cache[doc.path] = cached
        return cached

    def _fire(self, event: str, doc: Document | None = None) -> None:
        if self._on_event is not None:
            self._on_event(event, doc)
