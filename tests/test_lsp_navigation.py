"""Tests for the L0 LSP navigation request layer (plan wave-1 plan a).

Covers :mod:`yate.editor_lsp.navigation` pure parsers, the
``canonical_uri`` mapping in :mod:`yate.editor_lsp.protocol` and the thin
request wrappers on :class:`yate.editor_lsp.manager.LspManager`, using the
same ``_FakeClient`` / ``_Harness`` pattern as ``tests/test_lsp_hover.py``.
"""

# pyright: reportPrivateUsage=false

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, cast

import pytest

from yate.editor_core.document import Document
from yate.editor_lsp.manager import LspManager
from yate.editor_lsp.client import Diagnostic, LspError, ServerConfig, ServerState
from yate.editor_lsp.navigation import (
    REASON_NO_READY_SERVER,
    REASON_UNSUPPORTED,
    LspCodeAction,
    LspFeatureFailed,
    LspFeatureUnavailable,
    LspSignature,
    WorkspaceEdit,
    parse_code_actions,
    parse_locations,
    parse_signature_help,
    parse_symbols,
    parse_workspace_edit,
)
from urllib.parse import urlparse

from yate.editor_lsp.protocol import canonical_uri
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
        capabilities: dict[str, object] | None = None,
        cancel_error: BaseException | None = None,
    ) -> None:
        self.config = config
        self.root = root
        self.state: ServerState = ServerState.READY
        self.error = ""
        self.server_capabilities: dict[str, object] = capabilities or {}
        self.calls: list[tuple[str, Any]] = []
        self.settled: list[int] = []
        self.cancelled: list[int] = []
        self._result = result
        self._exception = exception
        self._never_settles = never_settles
        self._cancel_error = cancel_error

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

    async def send_cancel(self, request_id: int) -> None:
        """Record the $/cancelRequest call (or fail, when scripted)."""
        self.cancelled.append(request_id)
        if self._cancel_error is not None:
            raise self._cancel_error


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
        capabilities: dict[str, object] | None = None,
        cancel_error: BaseException | None = None,
    ) -> None:
        self.mgr = LspManager()
        self.mgr.register_server(PY_CONFIG)
        self.doc = _make_doc(tmp_path, text)
        cfg = self.mgr.config_for("py")
        assert cfg is not None
        root = self.mgr.root_for(cfg, self.doc)
        self.client = _FakeClient(
            cfg, root, result=result, exception=exception,
            never_settles=never_settles, capabilities=capabilities,
            cancel_error=cancel_error,
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


# ---------------------------------------------------------------- protocol


def test_canonical_uri_maps_drive_escaped_and_plain_forms_to_one() -> None:
    """pyright's drive-escaped echo and the plain form normalize equal."""
    escaped = canonical_uri("file:///d%3A/x.py")
    plain = canonical_uri("file:///D:/x.py")
    assert escaped == plain


# ------------------------------------------------------------ pure parsers


def test_parse_locations_accepts_location_link_and_null() -> None:
    """One LocationLink + one null entry -> one clamped LspLocation."""
    raw: list[object] = [
        {"targetUri": "file:///t.py",
         "targetRange": {"start": {"line": 2, "character": 4},
                          "end": {"line": 2, "character": 9}}},
        None,
    ]
    locations = parse_locations(raw)
    assert len(locations) == 1
    loc = locations[0]
    assert loc.uri == "file:///t.py"
    assert (loc.row, loc.col, loc.end_row, loc.end_col) == (2, 4, 2, 9)


def test_parse_symbols_flattens_nested_document_symbols() -> None:
    """Parent + child DocumentSymbols -> two LspSymbols with depths 0/1."""
    raw: list[object] = [{
        "name": "Parent",
        "kind": 5,
        "detail": "",
        "selectionRange": {"start": {"line": 0, "character": 0},
                            "end": {"line": 0, "character": 6}},
        "range": {"start": {"line": 0, "character": 0},
                   "end": {"line": 5, "character": 0}},
        "children": [{
            "name": "Child",
            "kind": 6,
            "detail": "",
            "selectionRange": {"start": {"line": 2, "character": 4},
                                "end": {"line": 2, "character": 9}},
            "range": {"start": {"line": 2, "character": 4},
                       "end": {"line": 3, "character": 0}},
        }],
    }]
    symbols = parse_symbols(raw)
    assert len(symbols) == 2
    parent, child = symbols
    assert (parent.name, parent.depth) == ("Parent", 0)
    assert (child.name, child.depth) == ("Child", 1)
    assert (child.row, child.col) == (2, 4)


def test_parse_workspace_edit_rejects_file_operations() -> None:
    """A CreateFile beside a valid text edit marks the whole edit invalid."""
    raw: dict[str, object] = {
        "changes": {"file:///a.py": [{"range": {
            "start": {"line": 0, "character": 0},
            "end": {"line": 0, "character": 1},
        }, "newText": "x"}]},
        "documentChanges": [{"kind": "create", "uri": "file:///b.py"}],
    }
    edit = parse_workspace_edit(raw)
    assert edit.unsupported is True
    assert edit.changes == {}


def test_parse_code_actions_keeps_command_and_edit() -> None:
    """One bare Command action and one edit action keep their fields."""
    raw: list[object] = [
        {"title": "Run command", "kind": "quickfix",
         "command": {"command": "refactor.apply", "arguments": [1, "two"]}},
        {"title": "Fix it", "kind": "quickfix",
         "edit": {"changes": {"file:///a.py": [{"range": {
             "start": {"line": 1, "character": 0},
             "end": {"line": 1, "character": 2},
         }, "newText": "y"}]}}},
    ]
    actions = parse_code_actions(raw)
    assert len(actions) == 2
    command_action, edit_action = actions
    assert command_action.command == "refactor.apply"
    assert command_action.arguments == (1, "two")
    assert command_action.edit is None
    assert edit_action.command is None
    assert edit_action.edit is not None
    changes = edit_action.edit.changes["file:///a.py"]
    assert len(changes) == 1
    assert changes[0].text == "y"


def test_parse_signature_help_marks_active_parameter() -> None:
    """Two signatures, active 1/1 -> the second parameter renders bold."""
    raw: dict[str, object] = {
        "signatures": [
            {"label": "first(a, b)",
             "parameters": [{"label": "a"}, {"label": "b"}]},
            {"label": "second(x, y)",
             "parameters": [{"label": "x"}, {"label": "y"}]},
        ],
        "activeSignature": 1,
        "activeParameter": 1,
    }
    sig = parse_signature_help(raw)
    assert sig is not None
    assert sig.active_parameter == 1
    assert "second(x, **y**)" == sig.text


# --------------------------------------------------------- manager wrappers


def test_manager_request_definition_without_provider_raises_unavailable(
    tmp_path: Path,
) -> None:
    """Capabilities without definitionProvider -> LspFeatureUnavailable."""
    h = _Harness(tmp_path, capabilities={"referencesProvider": True})

    async def scenario() -> None:
        with pytest.raises(LspFeatureUnavailable):
            await h.mgr.request_definition(h.doc, 0, 0)
        assert h.client.calls == []

    asyncio.run(scenario())


def test_manager_request_definition_returns_locations(tmp_path: Path) -> None:
    """Two server locations -> two LspLocations via textDocument/definition."""
    h = _Harness(
        tmp_path,
        capabilities={"definitionProvider": True},
        result=[
            {"uri": "file:///a.py", "range": {
                "start": {"line": 1, "character": 0},
                "end": {"line": 1, "character": 3}}},
            {"uri": "file:///b.py", "range": {
                "start": {"line": 7, "character": 2},
                "end": {"line": 7, "character": 5}}},
        ],
    )

    async def scenario() -> None:
        locations = await h.mgr.request_definition(h.doc, 0, 0)
        assert len(locations) == 2
        assert locations[0].uri == "file:///a.py"
        assert (locations[0].row, locations[0].col) == (1, 0)
        assert locations[1].uri == "file:///b.py"
        method, params = h.client.calls[0]
        assert method == "textDocument/definition"
        assert params["textDocument"]["uri"] == h.mgr._uri(h.doc)

    asyncio.run(scenario())


def test_manager_request_references_timeout_sends_cancel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A hung server times out, cancels the request and settles the entry."""
    h = _Harness(
        tmp_path,
        capabilities={"referencesProvider": True},
        never_settles=True,
    )
    monkeypatch.setattr("yate.editor_lsp.navigation.NAV_TIMEOUT_S", 0.001)

    async def scenario() -> None:
        with pytest.raises(LspFeatureFailed):
            await h.mgr.request_references(h.doc, 0, 0)
        assert h.client.cancelled == [1]
        assert h.client.settled == [1]

    asyncio.run(scenario())


def test_manager_notification_uses_canonical_diagnostic_uri(
    tmp_path: Path,
) -> None:
    """A drive-escaped publishDiagnostics URI keys the canonical form."""
    h = _Harness(tmp_path)
    canonical = h.mgr._uri(h.doc)
    parsed = urlparse(canonical)
    # Drive-escape the actual drive letter, like pyright echoes it back.
    escaped_uri = (
        "file:///" + parsed.path[1].lower() + "%3A/" + parsed.path[3:]
    )

    h.mgr.handle_notification("textDocument/publishDiagnostics", {
        "uri": escaped_uri,
        "diagnostics": [],
    })
    assert escaped_uri not in h.mgr._diagnostics
    assert canonical in h.mgr._diagnostics


# --------------------------------------------------- M6 degradation reasons


def test_unavailable_reason_is_unsupported_when_capability_missing(
    tmp_path: Path,
) -> None:
    """A ready client without the capability -> reason "unsupported"."""
    h = _Harness(tmp_path, capabilities={"referencesProvider": True})

    async def scenario() -> None:
        with pytest.raises(LspFeatureUnavailable) as excinfo:
            await h.mgr.request_definition(h.doc, 0, 0)
        assert excinfo.value.reason == REASON_UNSUPPORTED
        assert excinfo.value.feature == "definitionProvider"
        assert h.client.calls == []

    asyncio.run(scenario())


def test_unavailable_reason_is_no_ready_server_without_client(
    tmp_path: Path,
) -> None:
    """No open document on the client -> reason "no-ready-server"."""
    h = _Harness(tmp_path, opened=True, capabilities={"definitionProvider": True})
    # Drop the open state so _ready_client_for finds no live didOpen.
    h.mgr._open.pop(h.mgr._uri(h.doc))

    async def scenario() -> None:
        with pytest.raises(LspFeatureUnavailable) as excinfo:
            await h.mgr.request_definition(h.doc, 0, 0)
        assert excinfo.value.reason == REASON_NO_READY_SERVER
        assert h.client.calls == []

    asyncio.run(scenario())


def test_unavailable_default_reason_is_unsupported() -> None:
    """The bare constructor keeps the historical "unsupported" default."""
    exc = LspFeatureUnavailable("someFeature")
    assert exc.reason == REASON_UNSUPPORTED
    assert exc.feature == "someFeature"


# ------------------------------------------------ M4 direct manager tests


def test_manager_request_document_symbols_flattens_and_clamps(
    tmp_path: Path,
) -> None:
    """Symbols in the open doc clamp to it; another URI passes through."""
    h = _Harness(
        tmp_path,
        capabilities={"documentSymbolProvider": True},
        result=[
            {"name": "Local", "kind": 12, "detail": "",
             "selectionRange": {"start": {"line": 0, "character": 0},
                                 "end": {"line": 0, "character": 1}},
              "range": {"start": {"line": 0, "character": 0},
                         "end": {"line": 0, "character": 1}}},
            {"name": "Far", "kind": 12, "detail": "",
             "location": {"uri": "file:///other.py", "range": {
                 "start": {"line": 50, "character": 99},
                 "end": {"line": 50, "character": 99}}}},
        ],
    )

    async def scenario() -> None:
        symbols = await h.mgr.request_document_symbols(h.doc)
        assert [s.name for s in symbols] == ["Local", "Far"]
        assert (symbols[0].row, symbols[0].col) == (0, 0)
        # The unopened URI's columns pass through untouched (no clamp
        # against the source document), only floored at 0.
        assert (symbols[1].row, symbols[1].col) == (50, 99)
        method, _params = h.client.calls[0]
        assert method == "textDocument/documentSymbol"

    asyncio.run(scenario())


def test_manager_request_rename_parses_document_changes(tmp_path: Path) -> None:
    """A ``documentChanges`` reply parses and converts to the open doc."""
    h = _Harness(
        tmp_path,
        capabilities={"renameProvider": True},
        result=None,
    )
    # The scripted response needs the canonical URI, which only exists
    # after the harness built it; patch it in place.
    h.client._result = {
        "documentChanges": [{
            "textDocument": {"uri": h.mgr._uri(h.doc)},
            "edits": [{
                "range": {"start": {"line": 0, "character": 0},
                           "end": {"line": 0, "character": 1}},
                "newText": "NEW",
            }],
        }],
    }
    uri = h.mgr._uri(h.doc)

    async def scenario() -> None:
        edit = await h.mgr.request_rename(h.doc, 0, 0, "NEW")
        assert isinstance(edit, WorkspaceEdit)
        assert edit.unsupported is False
        assert set(edit.changes) == {uri}
        assert edit.changes[uri][0].text == "NEW"
        method, params = h.client.calls[0]
        assert method == "textDocument/rename"
        assert params["newName"] == "NEW"

    asyncio.run(scenario())


def test_manager_rename_converts_utf16_and_clamps_per_target_uri(
    tmp_path: Path,
) -> None:
    """UTF-16 columns convert against the target URI's document, never the
    source one: the open doc converts, an unopened URI passes through."""
    # Non-BMP char: one buffer column == two UTF-16 code units.
    h = _Harness(
        tmp_path,
        text="\U0001f389\U0001f389\U0001f389\n",
        capabilities={"renameProvider": True},
        result=None,
    )
    open_uri = h.mgr._uri(h.doc)
    # The open document's second emoji starts at UTF-16 col 2 -> buffer col 1.
    h.client._result = {
        "changes": {
            open_uri: [
                {"range": {
                    "start": {"line": 0, "character": 2},
                    "end": {"line": 0, "character": 4},
                }, "newText": "X"},
            ],
            "file:///unopened.py": [
                {"range": {
                    "start": {"line": 50, "character": 99},
                    "end": {"line": 50, "character": 120},
                }, "newText": "Y"},
            ],
        },
    }

    async def scenario() -> None:
        edit = await h.mgr.request_rename(h.doc, 0, 0, "X")
        converted = edit.changes[open_uri][0]
        assert (converted.start_row, converted.start_col) == (0, 1)
        assert (converted.end_row, converted.end_col) == (0, 2)
        passthrough = edit.changes["file:///unopened.py"][0]
        assert (passthrough.start_row, passthrough.start_col) == (50, 99)
        assert (passthrough.end_row, passthrough.end_col) == (50, 120)

    asyncio.run(scenario())


def test_manager_request_code_actions_roundtrips_diagnostics_utf16(
    tmp_path: Path,
) -> None:
    """The diagnostic range converts back to UTF-16 for the wire params."""
    h = _Harness(
        tmp_path,
        text="a\U0001f389b\nx = 1\n",
        capabilities={"codeActionProvider": True},
        result=[{"title": "Fix", "kind": "quickfix"}],
    )
    diagnostic = Diagnostic(
        start_row=0, start_col=2, end_row=0, end_col=3,
        severity=1, message="boom", source="test",
    )

    async def scenario() -> None:
        actions = await h.mgr.request_code_actions(
            h.doc, 0, 2, [diagnostic]
        )
        assert isinstance(actions[0], LspCodeAction)
        assert actions[0].title == "Fix"
        _method, params = h.client.calls[0]
        context = params["context"]
        sent = context["diagnostics"][0]
        # Buffer col 2 on "a🎉b" is UTF-16 col 3 (the emoji spans two).
        assert sent["range"]["start"] == {"line": 0, "character": 3}
        assert sent["range"]["end"] == {"line": 0, "character": 4}

    asyncio.run(scenario())


def test_manager_request_signature_help_returns_card(tmp_path: Path) -> None:
    """A SignatureHelp payload parses through the manager wrapper."""
    h = _Harness(
        tmp_path,
        capabilities={"signatureHelpProvider": True},
        result={
            "signatures": [{"label": "f(x)",
                            "parameters": [{"label": "x"}]}],
            "activeSignature": 0,
            "activeParameter": 0,
        },
    )

    async def scenario() -> None:
        sig = await h.mgr.request_signature_help(h.doc, 0, 0)
        assert isinstance(sig, LspSignature)
        assert sig.text == "f(**x**)"
        assert sig.active_parameter == 0
        method, _params = h.client.calls[0]
        assert method == "textDocument/signatureHelp"

    asyncio.run(scenario())


def test_manager_execute_command_swallows_and_logs_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed executeCommand logs at debug and never raises."""
    h = _Harness(tmp_path, exception=LspError("boom"))
    records: list[str] = []

    class _Recorder:
        def debug(self, fmt: str, *args: object) -> None:
            records.append(fmt % args)

    monkeypatch.setattr(
        "yate.editor_lsp.manager.log", _Recorder(), raising=True
    )

    async def scenario() -> None:
        await h.mgr.execute_command(
            cast(Any, h.client), "server.fix", [1]
        )
        assert h.client.calls[0][0] == "workspace/executeCommand"
        assert any("executeCommand" in r for r in records)

    asyncio.run(scenario())


def test_navigation_timeout_swallows_send_cancel_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failing $/cancelRequest is logged, not raised (m3)."""
    h = _Harness(
        tmp_path,
        capabilities={"referencesProvider": True},
        never_settles=True,
        cancel_error=LspError("transport gone"),
    )
    monkeypatch.setattr("yate.editor_lsp.navigation.NAV_TIMEOUT_S", 0.001)

    async def scenario() -> None:
        with pytest.raises(LspFeatureFailed):
            await h.mgr.request_references(h.doc, 0, 0)
        assert h.client.cancelled == [1]
        assert h.client.settled == [1]

    asyncio.run(scenario())
