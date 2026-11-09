"""Tests for ``LspManager.request_hover``: a passive, bounded hover request.

The hover path must never start a server, never send didOpen/didChange and
never raise to the UI: every failure degrades to an empty string.
"""

# pyright: reportPrivateUsage=false

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, cast

import pytest

from yate.editor_core.document import Document
from yate.editor_lsp.manager import LspManager
from yate.editor_lsp.client import (
    LspResponseError,
    ServerConfig,
    ServerState,
)
from yate.editor_lsp.parsing import _to_utf16
from yate.editor_lsp.sync import OpenDocState

PY_CONFIG: ServerConfig = ServerConfig(
    name="python",
    command="fake-pylsp",
    args=["--stdio"],
    filetypes=["py"],
    language_ids={"py": "python"},
)


class _FakeClient:
    """Stand-in for LspClient: records start_request / settle_request."""

    def __init__(
        self,
        config: ServerConfig,
        root: Path,
        *,
        result: Any = None,
        exception: BaseException | None = None,
        never_settles: bool = False,
    ) -> None:
        self.config = config
        self.root = root
        self.state: ServerState = ServerState.READY
        self.error = ""
        self.calls: list[tuple[str, Any]] = []
        self.settled: list[int] = []
        self._result = result
        self._exception = exception
        self._never_settles = never_settles

    async def start_request(
        self, method: str, params: dict[str, Any] | None
    ) -> tuple[int, asyncio.Future[Any]]:
        """Record the call and hand back a scripted (id, future) pair."""
        self.calls.append((method, params))
        future: asyncio.Future[Any] = (
            asyncio.get_running_loop().create_future()
        )
        if not self._never_settles:
            if self._exception is not None:
                future.set_exception(self._exception)
            else:
                future.set_result(self._result)
        return 1, future

    def settle_request(self, request_id: int) -> None:
        """Record the cleanup call."""
        self.settled.append(request_id)


def _make_doc(tmp_path: Path, text: str) -> Document:
    """Write *text* to a Python file under *tmp_path* and open it."""
    path = tmp_path / "mod.py"
    path.write_text(text, encoding="utf-8")
    return Document.open(path)


class _Harness:
    """A manager with one registered server and an injected fake client."""

    def __init__(
        self,
        tmp_path: Path,
        text: str = "x = 1\n",
        *,
        state: ServerState = ServerState.READY,
        opened: bool = True,
        result: Any = None,
        exception: BaseException | None = None,
        never_settles: bool = False,
    ) -> None:
        self.mgr = LspManager()
        self.mgr.register_server(PY_CONFIG)
        self.doc = _make_doc(tmp_path, text)
        cfg = self.mgr.config_for("py")
        assert cfg is not None
        root = self.mgr.root_for(cfg, self.doc)
        self.client = _FakeClient(
            cfg, root, result=result, exception=exception,
            never_settles=never_settles,
        )
        self.client.state = state
        self.mgr._clients[(cfg.name, str(root))] = cast(Any, self.client)
        if opened:
            self.mgr._open[self.mgr._uri(self.doc)] = OpenDocState(
                uri=self.mgr._uri(self.doc),
                config_name=cfg.name,
                client_key=(cfg.name, str(root)),
                language_id="python",
                version=1,
                last_synced_lines=tuple(self.doc.buffer.lines),
                last_synced_version=1,
                doc=self.doc,
            )


def _block_spawns(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make ensure_client / on_document_shown fail loudly if called."""

    async def _fail(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("hover must not start a server or open a doc")

    monkeypatch.setattr(LspManager, "ensure_client", _fail)
    monkeypatch.setattr(LspManager, "on_document_shown", _fail)


def test_request_hover_sends_hover_method_and_uri(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _block_spawns(monkeypatch)
    h = _Harness(tmp_path)

    async def scenario() -> None:
        result = await h.mgr.request_hover(h.doc, 3, 2)
        assert result == ""
        assert len(h.client.calls) == 1
        method, params = h.client.calls[0]
        assert method == "textDocument/hover"
        assert params["textDocument"]["uri"] == h.mgr._uri(h.doc)
        assert params["position"] == {"line": 3, "character": 2}

    asyncio.run(scenario())


def test_request_hover_encodes_position_in_utf16_units(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _block_spawns(monkeypatch)
    h = _Harness(tmp_path, text="aé中x\n")

    async def scenario() -> None:
        await h.mgr.request_hover(h.doc, 0, 3)
        _, params = h.client.calls[0]
        line = "aé中x"
        assert params["position"] == {"line": 0, "character": _to_utf16(line, 3)}
        assert params["position"]["character"] == 3

    asyncio.run(scenario())


def test_request_hover_without_ready_server_returns_empty_without_starting_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _block_spawns(monkeypatch)
    h = _Harness(tmp_path)
    cfg = h.mgr.config_for("py")
    assert cfg is not None
    h.mgr._clients.clear()

    async def scenario() -> None:
        assert await h.mgr.request_hover(h.doc, 0, 0) == ""
        assert h.client.calls == []

    asyncio.run(scenario())


def test_request_hover_with_failed_server_state_returns_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _block_spawns(monkeypatch)
    h = _Harness(tmp_path, state=ServerState.FAILED)

    async def scenario() -> None:
        assert await h.mgr.request_hover(h.doc, 0, 0) == ""
        assert h.client.calls == []

    asyncio.run(scenario())


def test_request_hover_with_unopened_document_returns_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _block_spawns(monkeypatch)
    h = _Harness(tmp_path, opened=False)

    async def scenario() -> None:
        assert await h.mgr.request_hover(h.doc, 0, 0) == ""
        assert h.client.calls == []

    asyncio.run(scenario())


def test_request_hover_with_mismatched_client_key_returns_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An open URI recorded under another client key hovers nobody."""
    _block_spawns(monkeypatch)
    h = _Harness(tmp_path)
    h.mgr._open[h.mgr._uri(h.doc)].client_key = ("other", "elsewhere")

    async def scenario() -> None:
        assert await h.mgr.request_hover(h.doc, 0, 0) == ""
        assert h.client.calls == []

    asyncio.run(scenario())


def test_request_hover_does_not_flush_didChange(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _block_spawns(monkeypatch)
    h = _Harness(tmp_path, result={"contents": "hello"})
    flushes: list[Any] = []

    async def _raiser(*args: Any, **kwargs: Any) -> None:
        flushes.append(args)
        raise AssertionError("hover must not flush a debounced didChange")

    import yate.editor_lsp.manager as manager_mod

    monkeypatch.setattr(manager_mod, "dispatch_change", _raiser)

    async def scenario() -> None:
        assert await h.mgr.request_hover(h.doc, 0, 0) == "hello"
        assert flushes == []

    asyncio.run(scenario())


def test_request_hover_with_null_result_returns_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _block_spawns(monkeypatch)
    h = _Harness(tmp_path, result=None)

    async def scenario() -> None:
        assert await h.mgr.request_hover(h.doc, 0, 0) == ""

    asyncio.run(scenario())


def test_request_hover_with_error_response_returns_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _block_spawns(monkeypatch)
    h = _Harness(tmp_path, exception=LspResponseError(-32603, "boom"))

    async def scenario() -> None:
        assert await h.mgr.request_hover(h.doc, 0, 0) == ""
        assert h.client.settled == [1]

    asyncio.run(scenario())


def test_request_hover_with_timeout_returns_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _block_spawns(monkeypatch)
    h = _Harness(tmp_path, never_settles=True)
    monkeypatch.setattr("yate.editor_lsp.manager.HOVER_TIMEOUT_S", 0.001)

    async def scenario() -> None:
        assert await h.mgr.request_hover(h.doc, 0, 0) == ""
        assert h.client.settled == [1]

    asyncio.run(scenario())


def test_request_hover_with_malformed_payload_returns_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _block_spawns(monkeypatch)
    h = _Harness(tmp_path, result=object())

    async def scenario() -> None:
        assert await h.mgr.request_hover(h.doc, 0, 0) == ""

    asyncio.run(scenario())


def test_request_hover_returns_normalized_markdown_from_markup_array(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _block_spawns(monkeypatch)
    payload = {
        "contents": [
            {"language": "python", "value": "def f():"},
            {"kind": "markdown", "value": "docs"},
        ]
    }
    h = _Harness(tmp_path, result=payload)

    async def scenario() -> None:
        result = await h.mgr.request_hover(h.doc, 0, 0)
        assert "def f():" in result
        assert "docs" in result

    asyncio.run(scenario())


def test_request_hover_settles_pending_request_on_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _block_spawns(monkeypatch)
    h = _Harness(tmp_path, result={"contents": "hello"})

    async def scenario() -> None:
        assert await h.mgr.request_hover(h.doc, 0, 0) == "hello"
        assert h.client.settled == [1]

    asyncio.run(scenario())


def test_request_hover_with_cancelled_worker_reraises_cancellation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _block_spawns(monkeypatch)
    h = _Harness(tmp_path, never_settles=True)

    async def scenario() -> None:
        task = asyncio.create_task(h.mgr.request_hover(h.doc, 0, 0))
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(scenario())
