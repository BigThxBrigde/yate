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
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional, cast

from yate.editor_core.document import Document

from . import protocol
from .client import (
    Completion,
    Diagnostic,
    DiagnosticSeverity,
    LspClient,
    LspError,
    ServerConfig,
    ServerState,
)

#: TextDocumentSyncKind.Full -- resending the whole buffer on every change is
#: supported by every server and avoids fragile incremental position math.
_SYNC_FULL = 1

#: Debounce for didChange (keystrokes coalesce into one notification).
CHANGE_DEBOUNCE_S = 0.25

#: Trigger kinds for textDocument/completion.
TRIGGER_INVOKED = 1
TRIGGER_CHARACTER = 2

ClientKey = tuple[str, str]


@dataclass
class OpenDocState:
    uri: str
    config_name: str
    client_key: ClientKey
    language_id: str
    version: int
    last_synced: str


class LspManager:
    """Registry of server configs plus per-document LSP session state."""

    def __init__(
        self,
        *,
        workspace_root: Optional[Callable[[], Optional[Path]]] = None,
        on_event: Optional[Callable[[str], None]] = None,
        client_factory: Optional[Callable[[ServerConfig, Path], LspClient]] = None,
    ) -> None:
        self._configs: list[ServerConfig] = []
        self._by_filetype: dict[str, ServerConfig] = {}
        self._clients: dict[ClientKey, LspClient] = {}
        self._starting: dict[ClientKey, "asyncio.Task[Optional[LspClient]]"] = {}
        self._open: dict[str, OpenDocState] = {}
        self._diagnostics: dict[str, list[Diagnostic]] = {}
        self._change_timers: dict[str, asyncio.TimerHandle] = {}
        self._bg_tasks: set["asyncio.Task[None]"] = set()
        self._shutting_down = False
        self._workspace_root = workspace_root
        self._on_event = on_event
        self._client_factory = client_factory

    def set_client_factory(
        self, factory: Optional[Callable[[ServerConfig, Path], LspClient]]
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
            for key in [k for k in self._clients if k[0] == config.name]:
                self._clients.pop(key, None)
            for task in [t for k, t in self._starting.items() if k[0] == config.name]:
                task.cancel()
            self._starting = {k: v for k, v in self._starting.items()
                              if k[0] != config.name}
            stale_urls = [u for u, st in self._open.items()
                          if st.config_name == config.name]
            for uri in stale_urls:
                self._open.pop(uri, None)
                self._diagnostics.pop(uri, None)
        self._configs.append(config)
        # Rebuild the file type index; later registrations override earlier.
        self._by_filetype.clear()
        for cfg in self._configs:
            for ft in cfg.filetypes:
                self._by_filetype[ft] = cfg

    def config_names(self) -> list[str]:
        return [c.name for c in self._configs]

    def configs(self) -> list[ServerConfig]:
        """已注册的服务器配置（只读视图，供诊断/状态栏使用）。"""
        return list(self._configs)

    def config_for(self, filetype: str) -> Optional[ServerConfig]:
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

    def state_for_doc(self, doc: Document) -> Optional[ServerState]:
        """Aggregated server state relevant to *doc*, for the status bar."""
        cfg = self.config_for(doc.filetype)
        return self.states().get(cfg.name) if cfg is not None else None

    def error_for(self, config_name: str) -> str:
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

    async def ensure_client(self, doc: Document) -> Optional[LspClient]:
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
            self._starting.pop(key, None)

    async def _start_client(
        self, key: ClientKey, config: ServerConfig, root: Path
    ) -> Optional[LspClient]:
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
            return None
        client = self._make_client(config, root)
        self._clients[key] = client
        try:
            await client.start()
        except (LspError, OSError):
            # Missing executable / timeout -- keep FAILED state, never crash.
            self._fire("state")
            return None
        self._fire("state")
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
        )
        # Pending diagnostics may already be stale relative to buffer content;
        # the server republishes after didOpen.
        self._diagnostics.pop(uri, None)

    async def on_document_closed(self, doc: Document) -> None:
        if doc.path is None:
            return
        uri = self._uri(doc)
        state = self._open.pop(uri, None)
        self._change_timers.pop(uri, None)
        if state is None:
            return
        client = self._clients.get(state.client_key)
        if client is not None and client.state is ServerState.READY:
            try:
                await client.notify("textDocument/didClose",
                                   {"textDocument": {"uri": uri}})
            except (LspError, OSError):
                pass

    def notify_edit(self, doc: Document) -> None:
        """Schedule a debounced full-text didChange (no-op when unchanged)."""
        if doc.path is None:
            return
        uri = self._uri(doc)
        state = self._open.get(uri)
        if state is None:
            return
        text = doc.buffer.get_text()
        if text == state.last_synced:
            return
        timer = self._change_timers.pop(uri, None)
        if timer is not None:
            timer.cancel()
        loop = asyncio.get_running_loop()
        self._change_timers[uri] = loop.call_later(
            CHANGE_DEBOUNCE_S, self._flush_change, doc, uri, text
        )

    def _flush_change(self, doc: Document, uri: str, text: str) -> None:
        self._change_timers.pop(uri, None)
        state = self._open.get(uri)
        if state is None or self._shutting_down:
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
            self._send_change(client, uri, state, next_version, text)
        )

    def _spawn_bg(self, coro: Awaitable[None]) -> None:
        """Track a fire-and-forget notification task until it settles."""
        task: "asyncio.Task[None]" = asyncio.ensure_future(coro)
        self._bg_tasks.add(task)
        task.add_done_callback(self._bg_tasks.discard)

    async def _send_change(
        self,
        client: LspClient,
        uri: str,
        state: OpenDocState,
        version: int,
        text: str,
    ) -> None:
        """Send a full-text didChange; advance state.version/last_synced only
        after a successful notify so a failed call leaves ``last_synced``
        stale and lets the next :meth:`notify_edit` retry naturally."""
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

    async def notify_saved(self, doc: Document) -> None:
        state = self._open.get(self._uri(doc)) if doc.path is not None else None
        if state is None:
            return
        client = self._clients.get(state.client_key)
        if client is not None and client.state is ServerState.READY:
            try:
                await client.notify("textDocument/didSave",
                                   {"textDocument": {"uri": state.uri}})
            except (LspError, OSError):
                pass

    # ---------------------------------------------------------- completion

    async def request_completion(
        self,
        doc: Document,
        row: int,
        col: int,
        *,
        prefix_start_col: int,
        trigger_kind: int = TRIGGER_INVOKED,
        trigger_character: Optional[str] = None,
    ) -> list[Completion]:
        """Fetch completions at the cursor; empty list when unavailable."""
        client = await self.ensure_client(doc)
        if client is None or doc.path is None:
            return []
        context: dict[str, Any] = {"triggerKind": trigger_kind}
        if trigger_character is not None:
            context["triggerCharacter"] = trigger_character
        params: dict[str, Any] = {
            "textDocument": {"uri": self._uri(doc)},
            "position": {"line": row, "character": col},
            "context": context,
        }
        try:
            _request_id, future = await client.start_request(
                "textDocument/completion", params
            )
            raw = await future
        except (LspError, OSError, asyncio.CancelledError):
            return []
        items, item_defaults = self._unwrap_completion(raw)
        completions: list[Completion] = []
        for item in items:
            parsed = self._parse_completion_item(
                item, item_defaults, row, col, prefix_start_col
            )
            if parsed is not None:
                completions.append(parsed)
        completions.sort(key=lambda c: (c.sort_text or c.label.lower(), c.label))
        return completions

    @staticmethod
    def _unwrap_completion(raw: Any) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        if isinstance(raw, list):
            return (
                [cast(dict[str, Any], x) for x in cast(list[Any], raw)
                 if isinstance(x, dict)],
                {},
            )
        if isinstance(raw, dict):
            payload = cast(dict[str, Any], raw)
            raw_items = payload.get("items")
            raw_defaults = payload.get("itemDefaults")
            items = (
                [cast(dict[str, Any], x) for x in cast(list[Any], raw_items)
                 if isinstance(x, dict)]
                if isinstance(raw_items, list) else []
            )
            defaults = (
                cast(dict[str, Any], raw_defaults)
                if isinstance(raw_defaults, dict) else {}
            )
            return items, defaults
        return [], {}

    @staticmethod
    def _range_from(value: Any) -> Optional[tuple[int, int, int, int]]:
        """Normalize Range | {insert,replace} into (r0,c0,r1,c1)."""
        if not isinstance(value, dict):
            return None
        candidate = cast(dict[str, Any], value)
        target_raw = candidate.get("insert") if "insert" in candidate else candidate
        if not isinstance(target_raw, dict):
            return None
        target = cast(dict[str, Any], target_raw)
        start_raw, end_raw = target.get("start"), target.get("end")
        if not isinstance(start_raw, dict) or not isinstance(end_raw, dict):
            return None
        start = cast(dict[str, Any], start_raw)
        end = cast(dict[str, Any], end_raw)
        return (
            int(start.get("line", 0)),
            int(start.get("character", 0)),
            int(end.get("line", 0)),
            int(end.get("character", 0)),
        )

    def _parse_completion_item(
        self,
        item: dict[str, Any],
        defaults: dict[str, Any],
        row: int,
        col: int,
        prefix_start_col: int,
    ) -> Optional[Completion]:
        label_raw = item.get("label")
        if not isinstance(label_raw, str) or not label_raw:
            return None
        label = label_raw

        insert_text = label
        text_format = item.get("insertTextFormat")
        text_edit = item.get("textEdit")
        rng: Optional[tuple[int, int, int, int]] = None

        if isinstance(text_edit, str):
            insert_text = text_edit
        elif isinstance(text_edit, dict) and "newText" in text_edit:
            edit = cast(dict[str, Any], text_edit)
            insert_text = str(edit["newText"])
            rng = self._range_from(edit.get("range"))
        else:
            raw_insert = item.get("insertText")
            if isinstance(raw_insert, str) and raw_insert:
                insert_text = raw_insert

        if rng is None:
            rng = self._range_from(defaults.get("editRange"))
        if rng is None:
            # No server range: replace the identifier prefix the UI computed.
            rng = (row, prefix_start_col, row, col)

        # Snippet items (format 2) use tab stops we don't support; fall back
        # to the plain label so accepting never inserts raw "$1" placeholders.
        if text_format == 2 and isinstance(text_edit, dict):
            insert_text = label
        elif text_format == 2 and not isinstance(item.get("insertText"), str):
            insert_text = label

        detail_raw = item.get("detail")
        kind_raw = item.get("kind")
        sort_raw = item.get("sortText")
        return Completion(
            label=label,
            insert_text=insert_text,
            detail=detail_raw if isinstance(detail_raw, str) else "",
            kind=kind_raw if isinstance(kind_raw, int) else 0,
            sort_text=sort_raw if isinstance(sort_raw, str) else "",
            range_start_row=rng[0],
            range_start_col=rng[1],
            range_end_row=rng[2],
            range_end_col=rng[3],
        )

    # ---------------------------------------------------------- diagnostics

    def handle_notification(self, method: str, params: dict[str, Any]) -> None:
        if method == "textDocument/publishDiagnostics":
            uri = params.get("uri")
            if isinstance(uri, str):
                self._diagnostics[uri] = self._parse_diagnostics(
                    params.get("diagnostics")
                )
                self._fire("diagnostics")
        elif method in (
            "window/logMessage",
            "telemetry/event",
            "$/progress",
            "window/showMessage",
        ):
            pass  # acknowledged but not surfaced yet

    @staticmethod
    def _parse_diagnostics(raw: Any) -> list[Diagnostic]:
        if not isinstance(raw, list):
            return []
        result: list[Diagnostic] = []
        for entry_raw in cast(list[Any], raw):
            if not isinstance(entry_raw, dict):
                continue
            entry = cast(dict[str, Any], entry_raw)
            rng_raw = entry.get("range")
            if not isinstance(rng_raw, dict):
                continue
            rng = cast(dict[str, Any], rng_raw)
            start: dict[str, Any] = {}
            end: dict[str, Any] = {}
            start_raw, end_raw = rng.get("start"), rng.get("end")
            if isinstance(start_raw, dict):
                start = cast(dict[str, Any], start_raw)
            if isinstance(end_raw, dict):
                end = cast(dict[str, Any], end_raw)
            if not start or not end:
                continue
            message = entry.get("message", "")
            source = entry.get("source", "")
            severity = entry.get("severity")
            result.append(Diagnostic(
                start_row=max(0, int(start.get("line", 0))),
                start_col=max(0, int(start.get("character", 0))),
                end_row=max(0, int(end.get("line", 0))),
                end_col=max(0, int(end.get("character", 0))),
                severity=int(severity) if isinstance(severity, int)
                else DiagnosticSeverity.ERROR,
                message=message if isinstance(message, str) else "",
                source=source if isinstance(source, str) else "",
            ))
        result.sort(key=lambda d: (d.start_row, d.start_col))
        return result

    def diagnostics_for(self, doc: Document) -> list[Diagnostic]:
        if doc.path is None:
            return []
        return list(self._diagnostics.get(self._uri(doc), []))

    def counts_for(self, doc: Document) -> tuple[int, int]:
        """(errors, warnings) for *doc*."""
        diags = self.diagnostics_for(doc)
        errors = sum(1 for d in diags if d.is_error)
        warnings = sum(1 for d in diags if d.is_warning)
        return errors, warnings

    def diagnostic_at(self, doc: Document, row: int, col: int) -> Optional[Diagnostic]:
        """The most severe diagnostic whose range covers (row, col)."""
        best: Optional[Diagnostic] = None
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
        return [d for d in self.diagnostics_for(doc) if d.start_row <= row <= d.end_row]

    # ------------------------------------------------------------- teardown

    async def shutdown_all(self) -> None:
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
            except Exception:
                pass
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
            except asyncio.TimeoutError:
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
        return protocol.path_to_uri(doc.path)

    def _fire(self, event: str) -> None:
        if self._on_event is not None:
            self._on_event(event)
