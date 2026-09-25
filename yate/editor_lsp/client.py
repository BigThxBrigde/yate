"""A single language server process speaking JSON-RPC over stdio.

The client is intentionally small and UI independent.  It owns:

* the server subprocess (created lazily by :meth:`LspClient.start`);
* the ``initialize`` / ``initialized`` handshake;
* correlation of request ids with futures;
* a single reader task dispatching responses, server requests and
  notifications (``textDocument/publishDiagnostics`` ...);
* a best-effort ``shutdown`` / ``exit`` / terminate teardown.

Document synchronization, completion parsing and diagnostics storage live in
:mod:`yate.editor_lsp.manager`.  The transport factory can be replaced, which
lets the test suite drive the client over in-memory streams instead of
spawning a real language server.
"""

from __future__ import annotations

import asyncio
import enum
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

from collections.abc import Awaitable, Callable

from yate.logs import tracing

from . import protocol

#: Trace logger ("yate.editor_lsp.client"); silent unless yate_trace is on.
log = tracing.get_logger(__name__)

#: Type of the async transport factory: returns (reader, writer, process).
ConnectFn = Callable[[], Awaitable[tuple[Any, Any, Any]]]
NotificationFn = Callable[[str, dict[str, Any]], None]

#: LSP error codes we care about.
ERR_METHOD_NOT_FOUND = -32601
ERR_REQUEST_CANCELLED = -32800

DEFAULT_ROOT_MARKERS = (
    ".git",
    "pyproject.toml",
    "setup.py",
    "package.json",
    "Cargo.toml",
    "go.mod",
)


class ServerState(str, enum.Enum):
    CONFIGURED = "configured"
    STARTING = "starting"
    READY = "ready"
    FAILED = "failed"
    STOPPED = "stopped"


class LspError(RuntimeError):
    """Base class for client side LSP failures."""


class LspResponseError(LspError):
    """The server answered a request with a JSON-RPC ``error`` object."""

    def __init__(self, code: int, message: str, data: Any = None) -> None:
        super().__init__(f"LSP error {code}: {message}")
        self.code = code
        self.message = message
        self.data = data


class LspConnectionError(LspError):
    """The transport broke (EOF, crash, timeout) before an answer arrived."""


@dataclass
class ServerConfig:
    """Everything needed to spawn and identify one language server.

    ``filetypes`` lists editor file types (file suffix without the dot) the
    server handles, e.g. ``["py"]``.  ``language_ids`` maps a file type to
    the LSP ``languageId`` when they differ; identity is used by default.
    """

    name: str
    command: str
    args: list[str] = field(default_factory=list[str])
    filetypes: list[str] = field(default_factory=list[str])
    language_ids: dict[str, str] = field(default_factory=dict[str, str])
    initialization_options: Any = None
    settings: Any = None
    env: dict[str, str] | None = None
    root_markers: list[str] = field(default_factory=lambda: list(DEFAULT_ROOT_MARKERS))

    def language_id(self, filetype: str) -> str:
        return self.language_ids.get(filetype, filetype)

    def handles(self, filetype: str) -> bool:
        return filetype in self.filetypes


@dataclass
class Completion:
    """One normalized completion item offered in the popup.

    ``range_*`` positions are half-open character positions in the buffer;
    when absent the caller replaces the identifier prefix under the cursor.
    """

    label: str
    insert_text: str
    detail: str = ""
    kind: int = 0
    sort_text: str = ""
    range_start_row: int | None = None
    range_start_col: int | None = None
    range_end_row: int | None = None
    range_end_col: int | None = None

    def has_range(self) -> bool:
        return (
            self.range_start_row is not None
            and self.range_start_col is not None
            and self.range_end_row is not None
            and self.range_end_col is not None
        )


@dataclass
class Diagnostic:
    """A normalized textDocument/publishDiagnostics entry."""

    start_row: int
    start_col: int
    end_row: int
    end_col: int
    severity: int
    message: str
    source: str = ""

    @property
    def is_error(self) -> bool:
        return self.severity == DiagnosticSeverity.ERROR

    @property
    def is_warning(self) -> bool:
        return self.severity == DiagnosticSeverity.WARNING


class DiagnosticSeverity(enum.IntEnum):
    ERROR = 1
    WARNING = 2
    INFORMATION = 3
    HINT = 4


class LspClient:
    """One stdio language server connection."""

    def __init__(
        self,
        config: ServerConfig,
        root_path: Path,
        *,
        on_notification: NotificationFn | None = None,
        connect: ConnectFn | None = None,
        init_timeout: float = 20.0,
    ) -> None:
        self.config = config
        self.root_path = Path(root_path)
        self._on_notification = on_notification
        self._connect_override = connect
        self._init_timeout = init_timeout

        self.state: ServerState = ServerState.CONFIGURED
        self._stopping = False
        self.error: str = ""
        self.server_capabilities: dict[str, Any] = {}
        self.trigger_characters: tuple[str, ...] = ()

        self._reader: Any = None
        self._writer: Any = None
        self._proc: Any = None
        self._read_task: asyncio.Task[None] | None = None
        self._bg_tasks: set[asyncio.Task[None]] = set()
        self._write_lock = asyncio.Lock()
        self._next_id = 1
        self._pending: dict[int, asyncio.Future[Any]] = {}
        # Settled once _connect() returns (or raises) so stop() can wait for
        # an in-flight spawn to finish tearing its subprocess down.
        self._connecting: asyncio.Future[None] | None = None

    # ------------------------------------------------------------- lifecycle

    async def start(self) -> None:
        """Spawn the server and complete the initialize handshake."""
        if self.state is ServerState.READY:
            return
        self.state = ServerState.STARTING
        loop = asyncio.get_running_loop()
        connecting = loop.create_future()
        self._connecting = connecting
        try:
            try:
                self._reader, self._writer, self._proc = await self._connect()
            finally:
                if not connecting.done():
                    connecting.set_result(None)
                if self._connecting is connecting:
                    self._connecting = None
            self._read_task = asyncio.create_task(self._read_loop())
            result: Any = await asyncio.wait_for(
                self.request("initialize", self._initialize_params()),
                timeout=self._init_timeout,
            )
            caps_raw = (
                cast(dict[str, Any], result).get("capabilities")
                if isinstance(result, dict) else None
            )
            if isinstance(caps_raw, dict):
                caps = cast(dict[str, Any], caps_raw)
                self.server_capabilities = caps
                provider_raw = caps.get("completionProvider")
                if isinstance(provider_raw, dict):
                    provider = cast(dict[str, Any], provider_raw)
                    chars_raw = provider.get("triggerCharacters")
                    if isinstance(chars_raw, list):
                        chars = cast(list[Any], chars_raw)
                        self.trigger_characters = tuple(
                            c for c in chars if isinstance(c, str)
                        )
            await self.notify("initialized", {})
            if self.config.settings is not None:
                # Best effort: servers without pull configuration ignore it.
                await self.notify(
                    "workspace/didChangeConfiguration",
                    {"settings": self.config.settings},
                )
            self.state = ServerState.READY
        except (OSError, TimeoutError, LspError) as exc:
            # Shutdown may have torn the client down while the initialize
            # handshake was still in flight; don't resurrect a STOPPED client
            # as FAILED.
            if not self._stopping:
                self.state = ServerState.FAILED
                self.error = f"{type(exc).__name__}: {exc}"
            await self._cleanup()
            raise

    async def _connect(self) -> tuple[Any, Any, Any]:
        if self._connect_override is not None:
            reader, writer, proc = await self._connect_override()
        else:
            env: dict[str, str] | None = None
            if self.config.env is not None:
                env = dict(os.environ)
                env.update(self.config.env)
            proc = await asyncio.create_subprocess_exec(
                self.config.command,
                *self.config.args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
                cwd=str(self.root_path),
                env=env,
            )
            reader, writer = proc.stdout, proc.stdin
        if self._stopping:
            # stop()/shutdown_all() ran while the spawn was still in flight:
            # state is already STOPPED and _cleanup saw _proc is None, so
            # without this the child would linger (owning its cwd, which
            # breaks TemporaryDirectory cleanup on Windows) until its
            # natural exit.  Kill it here; start() then aborts with LspError.
            if getattr(proc, "returncode", 0) is None:
                if hasattr(proc, "terminate"):
                    proc.terminate()
                if hasattr(proc, "wait"):
                    try:
                        await asyncio.wait_for(proc.wait(), timeout=3.0)
                    except (TimeoutError, OSError):
                        pass
            if writer is not None:
                try:
                    writer.close()
                except OSError:
                    pass
            raise LspError("client stopped while connecting")
        return reader, writer, proc

    async def stop(self) -> None:
        """Shutdown the server politely, then force kill if it lingers."""
        if self.state is ServerState.STOPPED:
            return
        polite = self.state is ServerState.READY
        self._stopping = True
        self.state = ServerState.STOPPED
        # If start() is still mid-connect, let _connect() run its stopping
        # branch (which terminates the spawned process) before we clean up.
        # Without this, stop() can return while self._proc is still None and
        # the caller observes an unterminated process.
        connecting = self._connecting
        if connecting is not None and not connecting.done():
            try:
                await asyncio.wait_for(connecting, timeout=5.0)
            except TimeoutError:
                pass
        if polite and self._writer is not None:
            try:
                await asyncio.wait_for(
                    self.request("shutdown", None), timeout=3.0
                )
                await self.notify("exit", None)
            except (LspError, TimeoutError, ConnectionError):
                pass
        await self._cleanup()

    async def _cleanup(self) -> None:
        # Cancel background writers first so none touches a closing writer.
        bg_tasks = [t for t in self._bg_tasks if not t.done()]
        for task in bg_tasks:
            task.cancel()
        if bg_tasks:
            await asyncio.gather(*bg_tasks, return_exceptions=True)
        self._bg_tasks.difference_update(bg_tasks)
        if self._read_task is not None:
            read_task, self._read_task = self._read_task, None
            read_task.cancel()
            await asyncio.gather(read_task, return_exceptions=True)
        for future in self._pending.values():
            if not future.done():
                future.set_exception(LspConnectionError("connection closed"))
        self._pending.clear()
        proc = self._proc
        self._proc = None
        if proc is not None and hasattr(proc, "returncode"):
            if proc.returncode is None and hasattr(proc, "terminate"):
                proc.terminate()
            # Wait for the subprocess transport to finish closing; dropping a
            # live transport at loop teardown prints "Exception ignored in
            # BaseSubprocessTransport.__del__" / ResourceWarning on exit.
            if proc.returncode is None and hasattr(proc, "wait"):
                try:
                    await asyncio.wait_for(proc.wait(), timeout=3.0)
                except (TimeoutError, OSError):
                    pass
        writer = self._writer
        self._writer = None
        if writer is not None:
            try:
                writer.close()
                if hasattr(writer, "wait_closed"):
                    await writer.wait_closed()
            except (OSError, ConnectionError):
                pass
        self._reader = None

    def _spawn_bg(self, coro: Any) -> None:
        """Track a fire-and-forget task so teardown can cancel it."""
        task = asyncio.ensure_future(coro)
        self._bg_tasks.add(task)
        task.add_done_callback(self._bg_tasks.discard)

    # ------------------------------------------------------------ rpc layer

    async def request(
        self, method: str, params: dict[str, Any] | None
    ) -> Any:
        """Send a request and await its raw ``result`` (raises on error)."""
        request_id, future = await self.start_request(method, params)
        try:
            return await future
        finally:
            self._pending.pop(request_id, None)

    async def start_request(
        self, method: str, params: dict[str, Any] | None
    ) -> tuple[int, asyncio.Future[Any]]:
        """Send a request without awaiting it.

        Returns the JSON-RPC id and the future that resolves with the raw
        result.  Callers (the completion manager) use the id for
        ``$/cancelRequest`` when a newer request supersedes this one.

        Raises :class:`LspConnectionError` immediately when the client is
        ``FAILED`` (its read loop died) or has no transport, so callers
        never hang on a future nobody will ever settle.
        """
        if self.state is ServerState.FAILED or (
            self._writer is None and self.state is not ServerState.STARTING
        ):
            raise LspConnectionError(f"client is {self.state.value}")
        request_id = self._next_id
        self._next_id += 1
        loop = asyncio.get_running_loop()
        future: asyncio.Future[Any] = loop.create_future()
        self._pending[request_id] = future
        await self._write_raw(protocol.build_request(request_id, method, params))
        return request_id, future

    async def notify(
        self, method: str, params: dict[str, Any] | None
    ) -> None:
        if self._writer is None:
            raise LspConnectionError(f"client is {self.state.value}")
        await self._write_raw(protocol.build_notification(method, params))

    async def send_cancel(self, request_id: int) -> None:
        """Best-effort ``$/cancelRequest`` for a previous completion."""
        if self._writer is not None:
            await self._write_raw(
                protocol.build_notification(
                    "$/cancelRequest", {"id": request_id}
                )
            )

    async def _write_raw(self, payload: dict[str, Any]) -> None:
        writer = self._writer
        if writer is None:
            raise LspConnectionError("no transport")
        data = protocol.encode_message(payload)
        async with self._write_lock:
            writer.write(data)
            if hasattr(writer, "drain"):
                await writer.drain()

    # ------------------------------------------------------------- read loop

    def _fail_pending(self, exc: Exception) -> None:
        """Fail every in-flight request future: the connection is dead.

        Records the error string and settles all pending futures with a
        :class:`LspConnectionError`.  When :meth:`stop` already owns the
        client (state ``STOPPED``) its ``_cleanup`` has settled the futures
        itself and the state must not be touched.
        """
        if self.state is ServerState.STOPPED:
            return
        self.error = f"{type(exc).__name__}: {exc}"
        for future in self._pending.values():
            if not future.done():
                future.set_exception(LspConnectionError(str(exc)))
        self._pending.clear()

    async def _read_loop(self) -> None:
        try:
            while True:
                message = await protocol.read_message(self._reader)
                if message is None:
                    raise LspConnectionError("server closed stdout")
                self._dispatch(message)
        except asyncio.CancelledError:
            raise
        except (LspError, ConnectionError, EOFError) as exc:
            self._fail_pending(exc)
        except Exception as exc:  # noqa: BLE001 - transport-level backstop:
            # any unexpected framing/dispatch crash must turn into a
            # connection failure, never strand requests on dead futures.
            log.exception("LSP read loop crashed (%s)", self.config.name)
            self._fail_pending(exc)
        finally:
            # The read loop dying makes the client unusable no matter which
            # path exited; only an orderly stop() keeps its STOPPED state.
            if self.state is not ServerState.STOPPED:
                self.state = ServerState.FAILED

    def _dispatch(self, message: dict[str, Any]) -> None:
        if "id" in message and "method" in message:
            # server -> client request
            self._handle_server_request(message)
        elif "method" in message:
            method = cast(str, message["method"])
            params_raw = message.get("params")
            if isinstance(params_raw, dict) and self._on_notification is not None:
                self._on_notification(method, cast(dict[str, Any], params_raw))
        elif "id" in message:
            future = self._pending.get(message["id"])
            if future is None or future.done():
                return
            if "error" in message:
                err_raw = message["error"]
                if isinstance(err_raw, dict):
                    err = cast(dict[str, Any], err_raw)
                    future.set_exception(
                        LspResponseError(
                            int(err.get("code", 0)),
                            str(err.get("message", "")),
                            err.get("data"),
                        )
                    )
                else:  # pragma: no cover - defensive
                    future.set_exception(LspResponseError(-32603, str(err_raw)))
            else:
                # Results are intentionally NOT coerced: completion may be a
                # bare JSON array, initialize a dict, shutdown null -- callers
                # validate the shape they expect.
                future.set_result(message.get("result"))

    def _handle_server_request(self, message: dict[str, Any]) -> None:
        request_id = message["id"]
        method = str(message["method"])
        result: Any = None
        ok = True
        if method == "workspace/configuration":
            result = [self.config.settings or {}]
        elif method in (
            "window/workDoneProgress/create",
            "client/registerCapability",
        ):
            result = None
        else:
            ok = False
        self._spawn_bg(
            self._write_raw(
                protocol.build_response(request_id, result)
                if ok
                else protocol.build_error(
                    request_id, ERR_METHOD_NOT_FOUND, f"unsupported request: {method}"
                )
            )
        )

    # ------------------------------------------------------------- payloads

    def _initialize_params(self) -> dict[str, Any]:
        return {
            "processId": os.getpid(),
            "clientInfo": {"name": "yate", "version": _yate_version()},
            "locale": "en",
            "rootPath": str(self.root_path),
            "rootUri": protocol.path_to_uri(self.root_path),
            "capabilities": {
                "textDocument": {
                    "synchronization": {
                        "didSave": True,
                        "dynamicRegistration": False,
                    },
                    "completion": {
                        "dynamicRegistration": False,
                        "completionItem": {
                            "snippetSupport": False,
                            "documentationFormat": [],
                            "resolveSupport": {"properties": []},
                        },
                        "contextSupport": False,
                    },
                    "publishDiagnostics": {
                        "relatedInformation": False,
                        "versionSupport": True,
                    },
                },
                "workspace": {
                    "configuration": True,
                    "workspaceFolders": True,
                },
                "window": {"workDoneProgress": True},
            },
            "initializationOptions": self.config.initialization_options,
        }


def _yate_version() -> str:
    try:
        from yate import __version__

        return __version__
    except Exception:  # pragma: no cover - defensive
        return "0.0.0"
