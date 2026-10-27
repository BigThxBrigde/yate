"""Real-server integration: incremental didChange sync against pyright-langserver.

Spawns ``pyright-langserver --stdio`` through the production
:class:`~yate.editor_lsp.client.LspClient` path, negotiates the sync kind,
opens a real Python file, applies several buffered edits and asserts that
only range patches leave the client.  Diagnostics arriving from the server
double as indirect evidence that the server-side document state did not
drift.  Skipped when pyright-langserver is not installed or cannot start
(e.g. no node runtime), so CI without pyright stays green.
"""

from __future__ import annotations

import asyncio
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import pytest

from yate.editor_core.document import Document
from yate.editor_lsp import ServerState
from yate.editor_lsp.client import SYNC_INCREMENTAL, LspClient, ServerConfig
from yate.editor_lsp.manager import LspManager

from test_lsp_diff import apply_changes

pytestmark = pytest.mark.skipif(
    shutil.which("pyright-langserver") is None,
    reason="pyright-langserver is not on PATH",
)

#: The server subprocess must come up (and answer initialize) within this.
_SPAWN_TIMEOUT_S = 60.0

#: Upper bound for didChange flushes / first pyright diagnostics.
_POLL_TIMEOUT_S = 30.0

#: Document with a type error so pyright must report a diagnostic for it.
_FILE_TEXT = 'def add(a: int, b: int) -> int:\n    return a + "x"\n'

#: Edits applied through the buffer between debounce windows.
_EDITS: tuple[str, ...] = ("X", "Y\n", "Z")


class _WireRecorder:
    """Records notifications crossing the client boundary both ways."""

    def __init__(self, manager: LspManager) -> None:
        self.sent: list[tuple[str, dict[str, Any]]] = []
        self.received: list[tuple[str, dict[str, Any]]] = []
        self._manager = manager

    def on_notification(self, method: str, params: dict[str, Any]) -> None:
        """Record the notification, then forward to the manager sink."""
        self.received.append((method, params))
        self._manager.handle_notification(method, params)


def _did_change_params(recorder: _WireRecorder) -> list[dict[str, Any]]:
    """The params of every didChange notification the client sent."""
    return [
        params
        for method, params in recorder.sent
        if method == "textDocument/didChange"
    ]


async def _wait_until(predicate: Callable[[], object], timeout: float) -> None:
    """Poll *predicate* until it is truthy or *timeout* elapses."""
    async with asyncio.timeout(timeout):
        while not predicate():
            await asyncio.sleep(0.05)


def test_real_pyright_negotiates_incremental_and_receives_range_patches(
    tmp_path: Path,
) -> None:
    """pyright negotiates sync kind 2; every didChange is a range patch and
    the server's diagnostics prove its document state tracked the edits."""

    async def scenario() -> None:
        command = shutil.which("pyright-langserver")
        assert command is not None

        path = tmp_path / "mod.py"
        path.write_text(_FILE_TEXT, encoding="utf-8")

        mgr = LspManager(workspace_root=lambda: tmp_path)
        recorder = _WireRecorder(mgr)
        clients: list[LspClient] = []

        def factory(config: ServerConfig, root: Path) -> LspClient:
            """Build a real client, wrapping notify to record the wire."""
            client = LspClient(
                config, root, on_notification=recorder.on_notification
            )
            inner = client.notify

            async def recording_notify(
                method: str, params: dict[str, Any] | None
            ) -> None:
                if isinstance(params, dict):
                    recorder.sent.append((method, params))
                await inner(method, params)

            # noqa: Any - test seam: intercept the client wire boundary.
            cast(Any, client).notify = recording_notify
            clients.append(client)
            return client

        mgr.set_client_factory(factory)
        mgr.register_server(
            ServerConfig(
                name="pyright",
                command=command,
                args=["--stdio"],
                filetypes=["py"],
            )
        )
        doc = Document.open(path)

        try:
            try:
                await asyncio.wait_for(
                    mgr.on_document_shown(doc), timeout=_SPAWN_TIMEOUT_S
                )
            except (asyncio.TimeoutError, OSError) as exc:
                pytest.skip(f"pyright-langserver failed to start: {exc}")
            client = clients[0]
            if client.state is not ServerState.READY:
                pytest.skip(
                    "pyright-langserver did not reach READY"
                    " (missing node runtime?);"
                    f" state={client.state.value} error={client.error!r}"
                )

            # (c) Negotiation on real server capabilities data.
            assert client.sync_kind == SYNC_INCREMENTAL
            assert client.server_capabilities
            # Leave a diagnostic breadcrumb: which sync kind was actually
            # negotiated and how the server declared textDocumentSync.
            print(
                f"negotiated sync_kind={client.sync_kind} "
                f"from {client.server_capabilities.get('textDocumentSync')!r}"
            )

            # didOpen + multi-step buffered edits; each step must produce
            # exactly one more didChange notification.
            seen = 0
            for edit in _EDITS:
                doc.buffer.insert_text(edit)
                mgr.notify_edit(doc)
                await _wait_until(
                    lambda: len(_did_change_params(recorder)) == seen + 1,
                    _POLL_TIMEOUT_S,
                )
                seen += 1

            # (a) Everything sent is a range patch, never the full text.
            params_list = _did_change_params(recorder)
            changes = [
                cast(dict[str, Any], change)
                for params in params_list
                for change in params["contentChanges"]
            ]
            assert len(changes) == len(_EDITS)
            for change in changes:
                assert "range" in change
                assert change["text"] != _FILE_TEXT

            # Client-side no-drift guard: replay the patches the way a
            # spec-compliant server would and land on the buffer text.
            server_lines = _FILE_TEXT.split("\n")
            for params in params_list:
                server_lines = apply_changes(
                    server_lines, params["contentChanges"]
                )
            assert "\n".join(server_lines) == doc.buffer.get_text()

            # (b) Diagnostics arrive: the server parsed the synced document.
            # Polled on the received wire instead of the manager's per-URI
            # store, which pyright's echoed (drive-escaped) URI does not key.
            await _wait_until(
                lambda: any(
                    cast(dict[str, Any], diagnostic).get("severity") == 1
                    for method, params in recorder.received
                    if method == "textDocument/publishDiagnostics"
                    for diagnostic in params.get("diagnostics", [])
                ),
                _POLL_TIMEOUT_S,
            )
        finally:
            await mgr.shutdown_all()

    asyncio.run(scenario())
