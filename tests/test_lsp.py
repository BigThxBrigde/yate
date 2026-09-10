"""Tests for the LSP core: framing, client over a loopback fake server,
and the UI-independent manager (registry, document sync, completion,
diagnostics).  No real language server is required."""

from __future__ import annotations

import asyncio
import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Optional, cast
from unittest.mock import patch

from yate.editor_core.document import Document
from yate.editor_lsp import LspManager, ServerState
from yate.editor_lsp import protocol
from yate.editor_lsp.client import (
    LspClient,
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


class ProtocolTests(unittest.IsolatedAsyncioTestCase):
    async def test_roundtrip_and_extra_headers(self):
        payload = {"jsonrpc": "2.0", "id": 1, "method": "ping",
                   "params": {"x": "ä"}}
        raw = protocol.encode_message(payload)
        self.assertTrue(raw.startswith(b"Content-Length: "))
        msg = await protocol.read_message(FakeReader(raw))
        self.assertEqual(msg, payload)

        with_extra = frame(payload, extra_headers="Content-Type: application/json")
        msg2 = await protocol.read_message(FakeReader(with_extra))
        self.assertEqual(msg2, payload)

    async def test_two_messages_back_to_back(self):
        a = frame({"jsonrpc": "2.0", "id": 1, "result": {"ok": True}})
        b = frame({"jsonrpc": "2.0", "id": 2, "result": [1, 2, 3]})
        reader = FakeReader(a + b)
        first = await protocol.read_message(reader)
        second = await protocol.read_message(reader)
        assert first is not None and second is not None
        self.assertEqual(first["id"], 1)
        self.assertEqual(second["id"], 2)
        self.assertIsNone(await protocol.read_message(FakeReader(b"")))

    def test_header_errors(self):
        with self.assertRaises(protocol.LspProtocolError):
            protocol.parse_headers(b"Content-Type: text\r\n\r\n")
        with self.assertRaises(protocol.LspProtocolError):
            protocol.parse_headers(b"Content-Length: abc\r\n\r\n")
        with self.assertRaises(protocol.LspProtocolError):
            protocol.parse_headers(
                f"Content-Length: {protocol.MAX_MESSAGE_BYTES + 1}\r\n\r\n".encode()
            )
        with self.assertRaises(protocol.LspProtocolError):
            protocol.parse_headers(b"garbage\r\n\r\n")

    def test_invalid_body(self):
        with self.assertRaises(protocol.LspProtocolError):
            protocol.decode_body(b"not json")
        with self.assertRaises(protocol.LspProtocolError):
            protocol.decode_body(b"[1,2]")  # body must be an object

    def test_builders(self):
        req = protocol.build_request(7, "m", {"a": 1})
        self.assertEqual(req["id"], 7)
        self.assertNotIn("params", protocol.build_request(1, "m"))
        notif = protocol.build_notification("n")
        self.assertNotIn("id", notif)
        self.assertEqual(protocol.build_response(2, None)["result"], None)
        self.assertEqual(protocol.build_error(3, -1, "x")["error"]["code"], -1)

    def test_uri_roundtrip(self):
        p = Path("foo bar/baz.py").resolve()
        uri = protocol.path_to_uri(p)
        self.assertTrue(uri.startswith("file:///"))
        self.assertEqual(protocol.uri_to_path(uri), p)
        self.assertEqual(protocol.uri_file_name(uri), "baz.py")


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


class LspClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_handshake_triggers_and_stops(self):
        harness = ServerHarness()
        client = await harness.start()
        # start() is idempotent once READY
        await client.start()
        self.assertIs(client.state, ServerState.READY)
        self.assertEqual(client.trigger_characters, (".", "["))
        self.assertEqual(str(client.root_path), str(Path.cwd()))
        await client.notify("workspace/didChangeConfiguration", {"settings": {}})
        # bare array result survives transport without coercion
        result = await client.request("textDocument/completion", {})
        self.assertIsInstance(result, list)
        self.assertEqual(result[0]["label"], "abc")
        # error responses surface as LspResponseError
        with self.assertRaises(LspResponseError):
            await client.request("boom", None)
        methods = [m.get("method") for m in harness.messages]
        self.assertIn("initialized", methods)
        await client.stop()
        self.assertTrue(harness.shutdown_seen)
        self.assertTrue(harness.exit_seen)
        self.assertIs(client.state, ServerState.STOPPED)
        await harness.close()

    async def test_server_request_and_publish_notification(self):
        """Server->client workspace/configuration is answered and
        publishDiagnostics reaches the manager notification callback."""
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
                        self.assertEqual(msg.get("result"), [{}])
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
        self.assertEqual(client.state, ServerState.READY)
        responded = await asyncio.wait_for(answer.get(), timeout=2.0)
        self.assertEqual(responded["id"], 90)
        self.assertTrue(
            any(m == "textDocument/publishDiagnostics" for m, _ in events))
        await client.stop()
        server.close()
        await server.wait_closed()

    async def test_initialize_timeout_marks_failed(self):
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
        with self.assertRaises(asyncio.TimeoutError):
            await client.start()
        self.assertIs(client.state, ServerState.FAILED)
        self.assertTrue(client.error)
        server.close()
        await server.wait_closed()

    async def test_cancel_request_sends_notification(self):
        harness = ServerHarness()
        client = await harness.start()
        request_id, future = await client.start_request(
            "textDocument/completion", {})
        await client.send_cancel(request_id)
        await future
        self.assertIn(request_id, harness.cancelled)
        await client.stop()
        await harness.close()


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


class ManagerRegistryTests(unittest.TestCase):
    def test_register_index_and_replace(self):
        mgr = LspManager()
        mgr.register_server(PY_CONFIG)
        self.assertEqual(mgr.config_names(), ["python"])
        self.assertTrue(mgr.supports(Document(Path("a.py"))))
        self.assertFalse(mgr.supports(Document(Path("a.txt"))))
        self.assertEqual(mgr.config_for("py"), PY_CONFIG)
        other = ServerConfig(name="python", command="x", filetypes=["py", "pyi"])
        mgr.register_server(other)
        self.assertEqual(mgr.config_names(), ["python"])
        self.assertEqual(mgr.config_for("pyi"), other)

    def test_root_marker_discovery(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".git").mkdir()
            pkg = root / "pkg" / "deep"
            pkg.mkdir(parents=True)
            doc = Document(pkg / "m.py")
            mgr = LspManager(workspace_root=lambda: None)
            mgr.register_server(PY_CONFIG)
            cfg = mgr.config_for("py")
            assert cfg is not None
            self.assertEqual(mgr.root_for(cfg, doc), root)
            mgr2 = LspManager(workspace_root=lambda: root)
            mgr2.register_server(PY_CONFIG)
            self.assertEqual(mgr2.root_for(cfg, doc), root)


class ManagerSessionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self.events: list[str] = []
        self.fakes: list[FakeClient] = []

        def factory(config: ServerConfig, path: Path) -> FakeClient:
            # The factory is responsible for wiring the manager notification
            # sink, just like the real LspClient constructor does.
            def on_notification(method: str, params: dict[str, Any]) -> None:
                self.mgr.handle_notification(method, params)

            fake = FakeClient(config, path, on_notification=on_notification)
            self.fakes.append(fake)
            return fake

        self.mgr = LspManager(
            workspace_root=lambda: root,
            on_event=lambda event: self.events.append(event),
            client_factory=cast(Any, factory),
        )
        self.mgr.register_server(PY_CONFIG)
        self.doc = make_python_doc(self._tmp.name, "value = 1\n")

    def _client(self) -> FakeClient:
        self.assertEqual(len(self.fakes), 1)
        return self.fakes[0]

    async def test_open_sync_change_close_lifecycle(self):
        await self.mgr.on_document_shown(self.doc)
        self.assertTrue(self.mgr.is_open(self.doc))
        client = self._client()
        self.assertTrue(client.started)
        opened = [m for m, _ in client.sent if m == "textDocument/didOpen"]
        self.assertEqual(len(opened), 1)
        params = client.sent[0][1]["textDocument"]
        self.assertEqual(params["languageId"], "python")
        self.assertEqual(params["text"], "value = 1\n")

        # unchanged text schedules nothing
        self.mgr.notify_edit(self.doc)
        # mutate, then flush under a tiny debounce constant
        self.doc.buffer.insert_text("x")
        with patch("yate.editor_lsp.manager.CHANGE_DEBOUNCE_S", 0.01):
            self.mgr.notify_edit(self.doc)
            await asyncio.sleep(0.1)
        changed = [p for m, p in client.sent if m == "textDocument/didChange"]
        self.assertEqual(len(changed), 1)
        self.assertIn("text", changed[0]["contentChanges"][0])

        await self.mgr.notify_saved(self.doc)
        self.assertIn("textDocument/didSave", [m for m, _ in client.sent])

        await self.mgr.on_document_closed(self.doc)
        self.assertFalse(self.mgr.is_open(self.doc))
        self.assertIn("textDocument/didClose", [m for m, _ in client.sent])
        await self.mgr.shutdown_all()
        self.assertTrue(client.stopped)

    async def test_completion_parsing_shapes(self):
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
        doc = make_python_doc(self._tmp.name, "ab\n")
        await mgr.on_document_shown(doc)
        result = await mgr.request_completion(
            doc, 0, 2, prefix_start_col=0, trigger_kind=2, trigger_character=".")
        labels = [c.label for c in result]
        self.assertEqual(labels, ["alpha", "beta"])
        alpha = result[0]
        self.assertTrue(alpha.has_range())
        self.assertEqual((alpha.range_start_col, alpha.range_end_col), (0, 2))
        self.assertEqual(alpha.insert_text, "alpha()")
        beta = result[1]
        self.assertEqual(beta.insert_text, "beta")  # snippet fallback
        self.assertEqual(beta.range_start_col, 1)  # from itemDefaults
        self.assertIn(".", mgr.trigger_characters_for(doc))
        await mgr.shutdown_all()
        self.assertTrue(fakes[0].stopped)

    async def test_bare_array_completion_with_prefix_fallback_range(self):
        items = [{"label": "plain"}]
        fakes: list[FakeClient] = []

        def factory(config: ServerConfig, path: Path) -> FakeClient:
            fake = FakeClient(config, path, completion=items)
            fakes.append(fake)
            return fake

        mgr = LspManager(client_factory=cast(Any, factory))
        mgr.register_server(PY_CONFIG)
        doc = make_python_doc(self._tmp.name, "pla\n")
        await mgr.on_document_shown(doc)
        result = await mgr.request_completion(doc, 0, 3, prefix_start_col=0)
        self.assertEqual(len(result), 1)
        self.assertEqual(
            (result[0].range_start_col, result[0].range_end_col), (0, 3))
        await mgr.shutdown_all()

    async def test_diagnostics_delivery_and_queries(self):
        await self.mgr.on_document_shown(self.doc)
        client = self._client()
        assert self.doc.path is not None
        uri = protocol.path_to_uri(self.doc.path)
        client.publish({"uri": uri, "diagnostics": [
            {"range": {"start": {"line": 0, "character": 0},
                       "end": {"line": 0, "character": 5}},
             "severity": 1, "message": "bad", "source": "pyright"},
            {"range": {"start": {"line": 0, "character": 7},
                       "end": {"line": 0, "character": 8}},
             "severity": 2, "message": "meh"},
        ]})
        self.assertIn("diagnostics", self.events)
        diags = self.mgr.diagnostics_for(self.doc)
        self.assertEqual(len(diags), 2)
        self.assertTrue(diags[0].is_error)
        self.assertEqual(self.mgr.counts_for(self.doc), (1, 1))
        self.assertIsNotNone(self.mgr.diagnostic_at(self.doc, 0, 2))
        self.assertIsNone(self.mgr.diagnostic_at(self.doc, 1, 0))
        self.assertEqual(len(self.mgr.diagnostics_on_line(self.doc, 0)), 2)
        self.assertEqual(self.mgr.diagnostics_on_line(self.doc, 9), [])
        # clearing diagnostics republishes an empty list
        client.publish({"uri": uri, "diagnostics": []})
        self.assertEqual(self.mgr.diagnostics_for(self.doc), [])
        await self.mgr.shutdown_all()

    async def test_missing_executable_is_failed_not_raised(self):
        mgr = LspManager()
        mgr.register_server(ServerConfig(name="none", command="", filetypes=["py"]))
        doc = make_python_doc(self._tmp.name)
        client = await mgr.ensure_client(doc)
        self.assertIsNone(client)
        self.assertIs(mgr.state_for_doc(doc), ServerState.FAILED)
        self.assertTrue(mgr.error_for("none"))
        # lifecycle calls stay harmless in the FAILED state
        await mgr.on_document_shown(doc)
        self.assertEqual(
            await mgr.request_completion(doc, 0, 0, prefix_start_col=0), [])
        await mgr.on_document_closed(doc)
        await mgr.shutdown_all()


class PythonExtensionDiscoveryTests(unittest.TestCase):
    def test_no_server_on_path_registers_empty_command(self):
        from extensions import python_lsp

        os.environ.pop("YATE_PYTHON_LSP", None)
        with patch.object(python_lsp.shutil, "which", return_value=None):
            command, args = python_lsp.discover_command()
        self.assertEqual(command, "")
        self.assertEqual(args, [])

    def test_env_override_is_shell_split(self):
        from extensions import python_lsp

        with patch.dict(
            "os.environ",
            {"YATE_PYTHON_LSP": 'my-langserver --stdio "x y"'},
        ):
            command, args = python_lsp.discover_command()
        self.assertEqual(command, "my-langserver")
        self.assertEqual(args, ["--stdio", "x y"])

    def test_prefers_pyright_over_pylsp(self):
        from extensions import python_lsp

        os.environ.pop("YATE_PYTHON_LSP", None)

        def fake_which(name: str) -> Optional[str]:
            return f"/usr/bin/{name}" if name == "pyright-langserver" else None

        with patch.object(python_lsp.shutil, "which", side_effect=fake_which):
            command, args = python_lsp.discover_command()
        self.assertTrue(command.endswith("pyright-langserver"))
        self.assertEqual(args, ["--stdio"])

    def test_explicit_opt_out_disables_even_with_server_on_path(self):
        from extensions import python_lsp

        with patch.dict("os.environ", {"YATE_PYTHON_LSP": "off"}):
            with patch.object(
                python_lsp.shutil, "which",
                return_value="/usr/bin/pylsp",
            ):
                command, args = python_lsp.discover_command()
        self.assertEqual(command, "")
        self.assertEqual(args, [])


if __name__ == "__main__":
    unittest.main()
