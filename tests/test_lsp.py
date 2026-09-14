"""Tests for the LSP core: framing, client over a loopback fake server,
and the UI-independent manager (registry, document sync, completion,
diagnostics).  No real language server is required."""

from __future__ import annotations

import asyncio
import gc
import json
import sys
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, cast

import pytest

from yate.editor_core.document import Document
from yate.editor_lsp import LspManager, ServerState
from yate.editor_lsp import protocol
from yate.editor_lsp.client import (
    LspClient,
    LspError,
    LspResponseError,
    ServerConfig,
)

PY_CONFIG = ServerConfig(
    name="python",
    command="fake-pylsp",
    args=["--stdio"],
    filetypes=["py"],
    language_ids={"py": "python"},
)


# --------------------------------------------------------------------- framing


class FakeReader:
    """Minimal readline/readexactly stream over a fixed byte buffer."""

    def __init__(self, data: bytes) -> None:
        self._data = data
        self._pos = 0

    async def readline(self) -> bytes:
        start = self._pos
        nl = self._data.find(b"\n", start)
        if nl == -1:
            self._pos = len(self._data)
            return self._data[start:]
        self._pos = nl + 1
        return self._data[start : self._pos]

    async def readexactly(self, n: int) -> bytes:
        chunk = self._data[self._pos : self._pos + n]
        if len(chunk) != n:
            raise asyncio.IncompleteReadError(chunk, n)
        self._pos += n
        return chunk


def frame(payload: dict[str, Any], extra_headers: str = "") -> bytes:
    body = json.dumps(payload).encode("utf-8")
    head = f"Content-Length: {len(body)}\r\n".encode("ascii")
    if extra_headers:
        head += f"{extra_headers}\r\n".encode("ascii")
    return head + b"\r\n" + body


def test_roundtrip_and_extra_headers() -> None:
    async def scenario() -> None:
        payload = {"jsonrpc": "2.0", "id": 1, "method": "ping",
                   "params": {"x": "ä"}}
        raw = protocol.encode_message(payload)
        assert raw.startswith(b"Content-Length: ")
        msg = await protocol.read_message(FakeReader(raw))
        assert msg == payload

        with_extra = frame(payload, extra_headers="Content-Type: application/json")
        msg2 = await protocol.read_message(FakeReader(with_extra))
        assert msg2 == payload

    asyncio.run(scenario())


def test_two_messages_back_to_back() -> None:
    async def scenario() -> None:
        a = frame({"jsonrpc": "2.0", "id": 1, "result": {"ok": True}})
        b = frame({"jsonrpc": "2.0", "id": 2, "result": [1, 2, 3]})
        reader = FakeReader(a + b)
        first = await protocol.read_message(reader)
        second = await protocol.read_message(reader)
        assert first is not None and second is not None
        assert first["id"] == 1
        assert second["id"] == 2
        assert await protocol.read_message(FakeReader(b"")) is None

    asyncio.run(scenario())


def test_header_errors() -> None:
    with pytest.raises(protocol.LspProtocolError):
        protocol.parse_headers(b"Content-Type: text\r\n\r\n")
    with pytest.raises(protocol.LspProtocolError):
        protocol.parse_headers(b"Content-Length: abc\r\n\r\n")
    with pytest.raises(protocol.LspProtocolError):
        protocol.parse_headers(
            f"Content-Length: {protocol.MAX_MESSAGE_BYTES + 1}\r\n\r\n".encode()
        )
    with pytest.raises(protocol.LspProtocolError):
        protocol.parse_headers(b"garbage\r\n\r\n")


def test_invalid_body() -> None:
    with pytest.raises(protocol.LspProtocolError):
        protocol.decode_body(b"not json")
    with pytest.raises(protocol.LspProtocolError):
        protocol.decode_body(b"[1,2]")  # body must be an object


def test_builders() -> None:
    req = protocol.build_request(7, "m", {"a": 1})
    assert req["id"] == 7
    assert "params" not in protocol.build_request(1, "m")
    notif = protocol.build_notification("n")
    assert "id" not in notif
    assert protocol.build_response(2, None)["result"] is None
    assert protocol.build_error(3, -1, "x")["error"]["code"] == -1


def test_uri_roundtrip() -> None:
    p = Path("foo bar/baz.py").resolve()
    uri = protocol.path_to_uri(p)
    assert uri.startswith("file:///")
    assert protocol.uri_to_path(uri) == p
    assert protocol.uri_file_name(uri) == "baz.py"


# ---------------------------------------------------------- loopback fake server


class FakeProc:
    def __init__(self) -> None:
        self.returncode: Optional[int] = None
        self.terminated = False

    def terminate(self) -> None:
        self.terminated = True
        self.returncode = -15


class ServerHarness:
    """A loopback TCP server speaking enough JSON-RPC for client tests."""

    def __init__(self, *, completion_result: Any = None) -> None:
        self.completion_result: Any = (
            completion_result
            if completion_result is not None
            else [{"label": "abc", "kind": 3}]
        )
        self.messages: list[dict[str, Any]] = []
        self.init_params: dict[str, Any] = {}
        self.cancelled: list[Any] = []
        self.shutdown_seen = False
        self.exit_seen = False
        self.server: Optional[asyncio.base_events.Server] = None
        self.proc = FakeProc()

    async def start(self) -> LspClient:
        async def serve(
            reader: asyncio.StreamReader, writer: asyncio.StreamWriter
        ) -> None:
            try:
                init = await protocol.read_message(reader)
                if init is None:
                    return
                self.init_params = init
                writer.write(protocol.encode_message(protocol.build_response(
                    init["id"],
                    {"capabilities": {
                        "completionProvider": {"triggerCharacters": [".", "["]},
                    }},
                )))
                await writer.drain()
                while True:
                    msg = await protocol.read_message(reader)
                    if msg is None:
                        return
                    self.messages.append(msg)
                    method = msg.get("method", "")
                    if method == "shutdown" and "id" in msg:
                        self.shutdown_seen = True
                        writer.write(protocol.encode_message(
                            protocol.build_response(msg["id"], None)))
                        await writer.drain()
                    elif method == "exit":
                        self.exit_seen = True
                    elif method == "$/cancelRequest":
                        self.cancelled.append(msg.get("params", {}).get("id"))
                    elif method == "textDocument/completion":
                        writer.write(protocol.encode_message(
                            protocol.build_response(msg["id"], self.completion_result)))
                        await writer.drain()
                    elif method == "boom" and "id" in msg:
                        writer.write(protocol.encode_message(
                            protocol.build_error(msg["id"], -32603, "boom")))
                        await writer.drain()
                    elif "id" in msg:
                        writer.write(protocol.encode_message(
                            protocol.build_error(msg["id"], -32601, "no")))
                        await writer.drain()
            except (asyncio.IncompleteReadError, ConnectionResetError):
                pass
            finally:
                writer.close()
                try:
                    await writer.wait_closed()
                except (ConnectionError, OSError):
                    pass

        self.server = await asyncio.start_server(serve, "127.0.0.1", 0)
        sockets = self.server.sockets
        assert sockets is not None
        port = list(sockets)[0].getsockname()[1]

        async def connect() -> tuple[Any, Any, Any]:
            reader, writer = await asyncio.open_connection("127.0.0.1", port)
            return reader, writer, self.proc

        client = LspClient(PY_CONFIG, Path.cwd(), connect=connect, init_timeout=2.0)
        await client.start()
        return client

    async def close(self) -> None:
        if self.server is not None:
            self.server.close()
            await self.server.wait_closed()


def test_handshake_triggers_and_stops() -> None:
    async def scenario() -> None:
        harness = ServerHarness()
        client = await harness.start()
        # start() is idempotent once READY
        await client.start()
        assert client.state is ServerState.READY
        assert client.trigger_characters == (".", "[")
        assert str(client.root_path) == str(Path.cwd())
        await client.notify("workspace/didChangeConfiguration", {"settings": {}})
        # bare array result survives transport without coercion
        result = await client.request("textDocument/completion", {})
        assert isinstance(result, list)
        assert result[0]["label"] == "abc"
        # error responses surface as LspResponseError
        with pytest.raises(LspResponseError):
            await client.request("boom", None)
        methods = [m.get("method") for m in harness.messages]
        assert "initialized" in methods
        await client.stop()
        assert harness.shutdown_seen
        assert harness.exit_seen
        assert client.state is ServerState.STOPPED
        await harness.close()

    asyncio.run(scenario())


def test_server_request_and_publish_notification() -> None:
    """Server->client workspace/configuration is answered and
    publishDiagnostics reaches the manager notification callback."""

    async def scenario() -> None:
        events: list[tuple[str, dict[str, Any]]] = []
        answer: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

        async def serve(
            reader: asyncio.StreamReader, writer: asyncio.StreamWriter
        ) -> None:
            try:
                init = await protocol.read_message(reader)
                assert init is not None
                writer.write(protocol.encode_message(protocol.build_response(
                    init["id"], {"capabilities": {}})))
                await writer.drain()
                writer.write(protocol.encode_message(protocol.build_request(
                    90, "workspace/configuration", {"items": []})))
                writer.write(protocol.encode_message(protocol.build_notification(
                    "textDocument/publishDiagnostics",
                    {"uri": "file:///x.py", "diagnostics": []})))
                await writer.drain()
                while True:
                    msg = await protocol.read_message(reader)
                    if msg is None:
                        return
                    if msg.get("id") == 90:
                        assert msg.get("result") == [{}]
                        await answer.put(msg)
                        return
            except (asyncio.IncompleteReadError, ConnectionResetError):
                pass
            finally:
                writer.close()
                try:
                    await writer.wait_closed()
                except (ConnectionError, OSError):
                    pass

        server = await asyncio.start_server(serve, "127.0.0.1", 0)
        sockets = server.sockets
        assert sockets is not None
        port = list(sockets)[0].getsockname()[1]

        async def connect() -> tuple[Any, Any, Any]:
            reader, writer = await asyncio.open_connection("127.0.0.1", port)
            return reader, writer, FakeProc()

        client = LspClient(
            PY_CONFIG, Path.cwd(), connect=connect,
            on_notification=lambda method, params: events.append((method, params)),
            init_timeout=2.0,
        )
        await client.start()
        assert client.state == ServerState.READY
        responded = await asyncio.wait_for(answer.get(), timeout=2.0)
        assert responded["id"] == 90
        assert any(
            m == "textDocument/publishDiagnostics" for m, _ in events)
        await client.stop()
        server.close()
        await server.wait_closed()

    asyncio.run(scenario())


def test_initialize_timeout_marks_failed() -> None:
    async def scenario() -> None:
        async def serve(
            reader: asyncio.StreamReader, writer: asyncio.StreamWriter
        ) -> None:
            try:
                await protocol.read_message(reader)  # swallow initialize
                await asyncio.sleep(1.0)
            finally:
                writer.close()
                try:
                    await writer.wait_closed()
                except (ConnectionError, OSError):
                    pass

        server = await asyncio.start_server(serve, "127.0.0.1", 0)
        sockets = server.sockets
        assert sockets is not None
        port = list(sockets)[0].getsockname()[1]

        async def connect() -> tuple[Any, Any, Any]:
            reader, writer = await asyncio.open_connection("127.0.0.1", port)
            return reader, writer, FakeProc()

        client = LspClient(PY_CONFIG, Path.cwd(), connect=connect, init_timeout=0.2)
        with pytest.raises(asyncio.TimeoutError):
            await client.start()
        assert client.state is ServerState.FAILED
        assert client.error
        server.close()
        await server.wait_closed()

    asyncio.run(scenario())


def test_cancel_request_sends_notification() -> None:
    async def scenario() -> None:
        harness = ServerHarness()
        client = await harness.start()
        request_id, future = await client.start_request(
            "textDocument/completion", {})
        await client.send_cancel(request_id)
        await future
        assert request_id in harness.cancelled
        await client.stop()
        await harness.close()

    asyncio.run(scenario())


def test_stop_during_starting_skips_shutdown_and_terminates() -> None:
    """Quit while initialize is pending: no polite shutdown request,
    no 3s stall, process terminated and the start task settled."""

    async def scenario() -> None:
        methods: list[Any] = []

        async def serve(
            reader: asyncio.StreamReader, writer: asyncio.StreamWriter
        ) -> None:
            try:
                while True:
                    msg = await protocol.read_message(reader)
                    if msg is None:
                        return
                    methods.append(msg.get("method"))
            except (asyncio.IncompleteReadError, ConnectionResetError):
                pass
            finally:
                writer.close()
                try:
                    await writer.wait_closed()
                except (ConnectionError, OSError):
                    pass

        server = await asyncio.start_server(serve, "127.0.0.1", 0)
        sockets = server.sockets
        assert sockets is not None
        port = list(sockets)[0].getsockname()[1]

        class SlowProc:
            def __init__(self) -> None:
                self.returncode: Optional[int] = None
                self.terminated = False
                self.waited = False

            def terminate(self) -> None:
                self.terminated = True

            async def wait(self) -> int:
                self.waited = True
                self.returncode = -15
                return -15

        proc = SlowProc()

        async def connect() -> tuple[Any, Any, Any]:
            reader, writer = await asyncio.open_connection("127.0.0.1", port)
            return reader, writer, proc

        client = LspClient(PY_CONFIG, Path.cwd(), connect=connect,
                           init_timeout=20.0)
        start_task = asyncio.ensure_future(client.start())
        try:
            for _ in range(50):
                if client.state is ServerState.STARTING:
                    break
                await asyncio.sleep(0.02)
            assert client.state is ServerState.STARTING
            loop = asyncio.get_running_loop()
            began = loop.time()
            await client.stop()
            assert loop.time() - began < 1.0
            assert proc.terminated
            assert proc.waited
            # A server that never finished initialize must not receive a
            # shutdown request it could not answer (that caused the 3s stall).
            assert "shutdown" not in methods
            with pytest.raises(LspError):
                await start_task
            assert client.state is ServerState.STOPPED
        finally:
            if not start_task.done():
                start_task.cancel()
                await asyncio.gather(start_task, return_exceptions=True)
            server.close()
            await server.wait_closed()

    asyncio.run(scenario())


# ------------------------------------------------------------------ fake client


class FakeClient:
    """Stand-in for LspClient used by manager tests (never spawns)."""

    def __init__(
        self,
        config: ServerConfig,
        root: Path,
        *,
        on_notification: Any = None,
        completion: Any = None,
    ) -> None:
        self.config = config
        self.root = root
        self.state = ServerState.READY
        self.error = ""
        self.trigger_characters: tuple[str, ...] = (".",)
        self.sent: list[tuple[str, Any]] = []
        self.started = False
        self.stopped = False
        self._on_notification = on_notification
        self._completion: Any = completion if completion is not None else []

    async def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        self.stopped = True
        self.state = ServerState.STOPPED

    async def notify(self, method: str, params: Any) -> None:
        self.sent.append((method, params))

    async def request(self, method: str, params: Any) -> Any:
        self.sent.append((method, params))
        return self._completion

    async def start_request(self, method: str, params: Any) -> tuple[int, Any]:
        self.sent.append((method, params))
        future: asyncio.Future[Any] = asyncio.get_running_loop().create_future()
        future.set_result(self._completion)
        return 1, future

    async def send_cancel(self, request_id: int) -> None:
        self.sent.append(("$/cancelRequest", request_id))

    def publish(self, params: dict[str, Any]) -> None:
        if self._on_notification is not None:
            self._on_notification("textDocument/publishDiagnostics", params)


def make_python_doc(tmp: str, text: str = "x = 1\n") -> Document:
    path = Path(tmp) / "mod.py"
    path.write_text(text, encoding="utf-8")
    return Document.open(path)


# ---------------------------------------------------------------- manager core


def test_register_index_and_replace() -> None:
    mgr = LspManager()
    mgr.register_server(PY_CONFIG)
    assert mgr.config_names() == ["python"]
    assert mgr.supports(Document(Path("a.py")))
    assert not mgr.supports(Document(Path("a.txt")))
    assert mgr.config_for("py") == PY_CONFIG
    other = ServerConfig(name="python", command="x", filetypes=["py", "pyi"])
    mgr.register_server(other)
    assert mgr.config_names() == ["python"]
    assert mgr.config_for("pyi") == other


def test_root_marker_discovery(tmp_path: Path) -> None:
    root = tmp_path
    (root / ".git").mkdir()
    pkg = root / "pkg" / "deep"
    pkg.mkdir(parents=True)
    doc = Document(pkg / "m.py")
    mgr = LspManager(workspace_root=lambda: None)
    mgr.register_server(PY_CONFIG)
    cfg = mgr.config_for("py")
    assert cfg is not None
    assert mgr.root_for(cfg, doc) == root
    mgr2 = LspManager(workspace_root=lambda: root)
    mgr2.register_server(PY_CONFIG)
    assert mgr2.root_for(cfg, doc) == root


@dataclass
class ManagerSession:
    """Bundle handed to the manager-lifecycle tests by ``session``."""

    mgr: LspManager
    doc: Document
    events: list[str]
    fakes: list[FakeClient]

    def client(self) -> FakeClient:
        assert len(self.fakes) == 1
        return self.fakes[0]


@pytest.fixture
def session(tmp_path: Path) -> ManagerSession:
    events: list[str] = []
    fakes: list[FakeClient] = []
    managers: list[LspManager] = []

    def factory(config: ServerConfig, path: Path) -> FakeClient:
        # The factory is responsible for wiring the manager notification
        # sink, just like the real LspClient constructor does.
        mgr = managers[0]

        def on_notification(method: str, params: dict[str, Any]) -> None:
            mgr.handle_notification(method, params)

        fake = FakeClient(config, path, on_notification=on_notification)
        fakes.append(fake)
        return fake

    mgr = LspManager(
        workspace_root=lambda: tmp_path,
        on_event=lambda event: events.append(event),
        client_factory=cast(Any, factory),
    )
    managers.append(mgr)
    mgr.register_server(PY_CONFIG)
    doc = make_python_doc(str(tmp_path), "value = 1\n")
    return ManagerSession(mgr=mgr, doc=doc, events=events, fakes=fakes)


def test_open_sync_change_close_lifecycle(
    session: ManagerSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def scenario() -> None:
        mgr = session.mgr
        doc = session.doc
        await mgr.on_document_shown(doc)
        assert mgr.is_open(doc)
        client = session.client()
        assert client.started
        opened = [m for m, _ in client.sent if m == "textDocument/didOpen"]
        assert len(opened) == 1
        params = client.sent[0][1]["textDocument"]
        assert params["languageId"] == "python"
        assert params["text"] == "value = 1\n"

        # unchanged text schedules nothing
        mgr.notify_edit(doc)
        # mutate, then flush under a tiny debounce constant
        doc.buffer.insert_text("x")
        monkeypatch.setattr("yate.editor_lsp.manager.CHANGE_DEBOUNCE_S", 0.01)
        mgr.notify_edit(doc)
        await asyncio.sleep(0.1)
        changed = [p for m, p in client.sent if m == "textDocument/didChange"]
        assert len(changed) == 1
        assert "text" in changed[0]["contentChanges"][0]

        await mgr.notify_saved(doc)
        assert "textDocument/didSave" in [m for m, _ in client.sent]

        await mgr.on_document_closed(doc)
        assert not mgr.is_open(doc)
        assert "textDocument/didClose" in [m for m, _ in client.sent]
        await mgr.shutdown_all()
        assert client.stopped

    asyncio.run(scenario())


def test_completion_parsing_shapes(tmp_path: Path) -> None:
    async def scenario() -> None:
        # CompletionList with itemDefaults editRange plus a snippet item
        # that must fall back to its plain label.
        items = [
            {"label": "alpha", "kind": 3, "detail": "func()",
             "textEdit": {"newText": "alpha()", "range": {
                 "start": {"line": 0, "character": 0},
                 "end": {"line": 0, "character": 2}}}},
            {"label": "beta", "insertText": "beta", "insertTextFormat": 2},
        ]
        fakes: list[FakeClient] = []

        def factory(config: ServerConfig, path: Path) -> FakeClient:
            fake = FakeClient(
                config, path,
                completion={"isIncomplete": False, "items": items,
                            "itemDefaults": {"editRange": {
                                "start": {"line": 0, "character": 1},
                                "end": {"line": 0, "character": 3}}}},
            )
            fakes.append(fake)
            return fake

        mgr = LspManager(client_factory=cast(Any, factory))
        mgr.register_server(PY_CONFIG)
        doc = make_python_doc(str(tmp_path), "ab\n")
        await mgr.on_document_shown(doc)
        result = await mgr.request_completion(
            doc, 0, 2, prefix_start_col=0, trigger_kind=2, trigger_character=".")
        labels = [c.label for c in result]
        assert labels == ["alpha", "beta"]
        alpha = result[0]
        assert alpha.has_range()
        assert (alpha.range_start_col, alpha.range_end_col) == (0, 2)
        assert alpha.insert_text == "alpha()"
        beta = result[1]
        assert beta.insert_text == "beta"  # snippet fallback
        assert beta.range_start_col == 1  # from itemDefaults
        assert "." in mgr.trigger_characters_for(doc)
        await mgr.shutdown_all()
        assert fakes[0].stopped

    asyncio.run(scenario())


def test_bare_array_completion_with_prefix_fallback_range(tmp_path: Path) -> None:
    async def scenario() -> None:
        items = [{"label": "plain"}]
        fakes: list[FakeClient] = []

        def factory(config: ServerConfig, path: Path) -> FakeClient:
            fake = FakeClient(config, path, completion=items)
            fakes.append(fake)
            return fake

        mgr = LspManager(client_factory=cast(Any, factory))
        mgr.register_server(PY_CONFIG)
        doc = make_python_doc(str(tmp_path), "pla\n")
        await mgr.on_document_shown(doc)
        result = await mgr.request_completion(doc, 0, 3, prefix_start_col=0)
        assert len(result) == 1
        assert (
            result[0].range_start_col, result[0].range_end_col) == (0, 3)
        await mgr.shutdown_all()

    asyncio.run(scenario())


def test_diagnostics_delivery_and_queries(session: ManagerSession) -> None:
    async def scenario() -> None:
        mgr = session.mgr
        doc = session.doc
        await mgr.on_document_shown(doc)
        client = session.client()
        assert doc.path is not None
        uri = protocol.path_to_uri(doc.path)
        client.publish({"uri": uri, "diagnostics": [
            {"range": {"start": {"line": 0, "character": 0},
                       "end": {"line": 0, "character": 5}},
             "severity": 1, "message": "bad", "source": "pyright"},
            {"range": {"start": {"line": 0, "character": 7},
                       "end": {"line": 0, "character": 8}},
             "severity": 2, "message": "meh"},
        ]})
        assert "diagnostics" in session.events
        diags = mgr.diagnostics_for(doc)
        assert len(diags) == 2
        assert diags[0].is_error
        assert mgr.counts_for(doc) == (1, 1)
        assert mgr.diagnostic_at(doc, 0, 2) is not None
        assert mgr.diagnostic_at(doc, 1, 0) is None
        assert len(mgr.diagnostics_on_line(doc, 0)) == 2
        assert mgr.diagnostics_on_line(doc, 9) == []
        # clearing diagnostics republishes an empty list
        client.publish({"uri": uri, "diagnostics": []})
        assert mgr.diagnostics_for(doc) == []
        await mgr.shutdown_all()

    asyncio.run(scenario())


def test_missing_executable_is_failed_not_raised(
    session: ManagerSession, tmp_path: Path
) -> None:
    async def scenario() -> None:
        mgr = LspManager()
        mgr.register_server(ServerConfig(name="none", command="", filetypes=["py"]))
        doc = make_python_doc(str(tmp_path))
        client = await mgr.ensure_client(doc)
        assert client is None
        assert mgr.state_for_doc(doc) is ServerState.FAILED
        assert mgr.error_for("none")
        # lifecycle calls stay harmless in the FAILED state
        await mgr.on_document_shown(doc)
        assert (
            await mgr.request_completion(doc, 0, 0, prefix_start_col=0) == [])
        await mgr.on_document_closed(doc)
        await mgr.shutdown_all()

    asyncio.run(scenario())


def test_shutdown_reaps_starting_client_task(tmp_path: Path) -> None:
    """shutdown_all unblocks and settles a client still STARTING instead
    of orphaning its task (which warned on exit and held a transport)."""

    async def scenario() -> None:
        class SlowStartClient(FakeClient):
            def __init__(self, *a: Any, **kw: Any) -> None:
                super().__init__(*a, **kw)
                self.state = ServerState.STARTING
                self._release = asyncio.Event()

            async def start(self) -> None:
                self.started = True
                await self._release.wait()
                if not self.stopped:
                    self.state = ServerState.READY

            async def stop(self) -> None:
                await super().stop()
                self._release.set()

        mgr = LspManager()
        mgr.register_server(PY_CONFIG)
        fake = SlowStartClient(PY_CONFIG, tmp_path)
        mgr.set_client_factory(
            lambda config, root: cast(LspClient, fake))
        doc = make_python_doc(str(tmp_path))
        shown = asyncio.ensure_future(mgr.on_document_shown(doc))
        try:
            await asyncio.sleep(0.1)
            assert fake.state is ServerState.STARTING
            await mgr.shutdown_all()
            assert fake.stopped
            await asyncio.wait_for(shown, timeout=1.0)
            internals = cast(Any, mgr)
            assert internals._starting == {}
        finally:
            if not shown.done():
                shown.cancel()
                await asyncio.gather(shown, return_exceptions=True)
            await mgr.shutdown_all()

    asyncio.run(scenario())


def test_shutdown_cancels_pending_change_tasks(
    session: ManagerSession, tmp_path: Path
) -> None:
    """A didChange still in flight when yate quits is cancelled, not
    destroyed mid-flight with a pending-task warning."""

    async def scenario() -> None:
        mgr = session.mgr
        doc = make_python_doc(str(tmp_path))
        client = await mgr.ensure_client(doc)
        assert client is not None
        await mgr.on_document_shown(doc)
        doc.buffer.insert_text("more text\n")
        mgr.notify_edit(doc)
        internals = cast(Any, mgr)
        # fire the debounce timer now
        for handle in list(internals._change_timers.values()):
            handle.cancel()
        internals._flush_change(
            doc, internals._uri(doc), doc.buffer.get_text())
        await mgr.shutdown_all()
        assert [t for t in internals._bg_tasks if not t.done()] == []

    asyncio.run(scenario())


def test_real_subprocess_starting_shutdown_leaves_no_garbage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The original report: quit while a (real) server is still coming
    up.  No unraisable __del__ errors / ResourceWarning may survive."""

    async def scenario() -> None:
        unraisable: list[Any] = []
        monkeypatch.setattr(sys, "unraisablehook", unraisable.append)
        cfg = ServerConfig(
            name="sleepy",
            command=sys.executable,
            args=["-c", "import time; time.sleep(30)"],
            filetypes=["py"],
        )
        mgr = LspManager()
        mgr.register_server(cfg)
        doc = make_python_doc(str(tmp_path))
        shown = asyncio.ensure_future(mgr.on_document_shown(doc))
        try:
            clients = cast(Any, mgr)._clients
            for _ in range(100):
                if clients and next(iter(clients.values())).state \
                        is ServerState.STARTING:
                    break
                await asyncio.sleep(0.05)
            real_client = next(iter(clients.values()))
            assert real_client.state is ServerState.STARTING
            real_proc = real_client._proc
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                await mgr.shutdown_all()
                gc.collect()
                await asyncio.sleep(0.1)
                gc.collect()
            assert [u.exc_value for u in unraisable] == []
            assert [
                w for w in caught
                if issubclass(w.category, ResourceWarning)
            ] == []
            # the killed child must release its cwd before the test
            # tears tmp down (cold Windows boxes can be slow here)
            if real_proc is not None and real_proc.returncode is None:
                await asyncio.wait_for(real_proc.wait(), timeout=5.0)
        finally:
            if not shown.done():
                shown.cancel()
                await asyncio.gather(shown, return_exceptions=True)
            await mgr.shutdown_all()

    asyncio.run(scenario())


# ------------------------------------------------- python extension discovery


def _which_none(name: str) -> Optional[str]:
    return None


def _venv_none() -> Optional[str]:
    return None


def test_no_server_on_path_registers_empty_command(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    from yate.extensions import python_lsp

    monkeypatch.delenv("YATE_PYTHON_LSP", raising=False)
    monkeypatch.setattr(python_lsp.shutil, "which", _which_none)
    monkeypatch.setattr(python_lsp, "_venv_langserver", _venv_none)
    command, args = python_lsp.discover_command()
    assert command == ""
    assert args == []


def test_interpreter_adjacent_server_found_without_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # pip installs pyright-langserver into the environment's scripts
    # directory; discovery must find it even when PATH lacks it.
    from yate.extensions import python_lsp

    monkeypatch.delenv("YATE_PYTHON_LSP", raising=False)
    fake_exe = str(tmp_path / "pyright-langserver.exe")

    def fake_venv() -> Optional[str]:
        return fake_exe

    monkeypatch.setattr(python_lsp.shutil, "which", _which_none)
    monkeypatch.setattr(python_lsp, "_venv_langserver", fake_venv)
    command, args = python_lsp.discover_command()
    assert command == fake_exe
    assert args == ["--stdio"]


def test_env_override_is_shell_split(monkeypatch: pytest.MonkeyPatch) -> None:
    from yate.extensions import python_lsp

    monkeypatch.setenv("YATE_PYTHON_LSP", 'my-langserver --stdio "x y"')
    command, args = python_lsp.discover_command()
    assert command == "my-langserver"
    assert args == ["--stdio", "x y"]


def test_prefers_pyright_over_pylsp(monkeypatch: pytest.MonkeyPatch) -> None:
    from yate.extensions import python_lsp

    monkeypatch.delenv("YATE_PYTHON_LSP", raising=False)

    def fake_which(name: str) -> Optional[str]:
        return f"/usr/bin/{name}" if name == "pyright-langserver" else None

    monkeypatch.setattr(python_lsp.shutil, "which", fake_which)
    command, args = python_lsp.discover_command()
    assert command.endswith("pyright-langserver")
    assert args == ["--stdio"]


def test_explicit_opt_out_disables_even_with_server_on_path(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    from yate.extensions import python_lsp

    monkeypatch.setenv("YATE_PYTHON_LSP", "off")

    def fake_which(name: str) -> Optional[str]:
        return "/usr/bin/pylsp"

    monkeypatch.setattr(python_lsp.shutil, "which", fake_which)
    command, args = python_lsp.discover_command()
    assert command == ""
    assert args == []
