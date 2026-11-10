"""Tests for the client capability payload declared in ``initialize``.

Verifies the hover client capability declaration, the completion
``documentationFormat`` fill, and that all pre-existing capability
blocks stay unchanged.  No language server process is started."""

# pyright: reportPrivateUsage=false

from __future__ import annotations

from pathlib import Path
from typing import cast

from yate.editor_lsp.client import DOCUMENTATION_FORMATS, LspClient, ServerConfig

PY_CONFIG: ServerConfig = ServerConfig(
    name="python",
    command="fake-pylsp",
    args=["--stdio"],
    filetypes=["py"],
    language_ids={"py": "python"},
)

BASELINE_TEXT_DOCUMENT_SYNC = {
    "openClose": True,
    "change": 2,
    "save": True,
}
BASELINE_SYNCHRONIZATION = {
    "didSave": True,
    "dynamicRegistration": False,
}
BASELINE_COMPLETION: dict[str, object] = {
    "dynamicRegistration": False,
    "completionItem": {
        "snippetSupport": False,
        "documentationFormat": ["markdown", "plaintext"],
        "resolveSupport": {"properties": []},
    },
    "contextSupport": False,
}
BASELINE_PUBLISH_DIAGNOSTICS = {
    "relatedInformation": False,
    "versionSupport": True,
}
BASELINE_WORKSPACE = {
    "configuration": True,
    "workspaceFolders": True,
}
BASELINE_WINDOW = {"workDoneProgress": True}


def _make_client(tmp_path: Path) -> LspClient:
    """Build an unstarted :class:`LspClient` rooted at ``tmp_path``."""
    return LspClient(config=PY_CONFIG, root_path=tmp_path)


def _capabilities(tmp_path: Path) -> dict[str, object]:
    """Return the top-level ``capabilities`` dict of the initialize payload."""
    client = _make_client(tmp_path)
    payload = client._initialize_params()
    return cast(dict[str, object], payload["capabilities"])


def _text_document(tmp_path: Path) -> dict[str, object]:
    """Return the ``capabilities.textDocument`` sub-dict of the payload."""
    caps = _capabilities(tmp_path)
    return cast(dict[str, object], caps["textDocument"])


def test_initialize_params_declares_hover_content_format(tmp_path: Path) -> None:
    """The hover client capability block declares the two markup kinds."""
    hover = cast(dict[str, object], _text_document(tmp_path)["hover"])
    assert hover == {
        "dynamicRegistration": False,
        "contentFormat": ["markdown", "plaintext"],
    }


def test_initialize_params_declares_completion_documentation_format(
    tmp_path: Path,
) -> None:
    """completionItem.documentationFormat lists markdown then plaintext."""
    completion = cast(dict[str, object], _text_document(tmp_path)["completion"])
    completion_item = cast(dict[str, object], completion["completionItem"])
    assert completion_item["documentationFormat"] == ["markdown", "plaintext"]


def test_initialize_params_does_not_declare_server_side_hover_provider(
    tmp_path: Path,
) -> None:
    """hoverProvider is a server capability and must not be declared."""
    caps = _capabilities(tmp_path)
    text_document = _text_document(tmp_path)
    assert "hoverProvider" not in text_document
    assert "hoverProvider" not in caps


def test_initialize_params_keeps_existing_capabilities_unchanged(
    tmp_path: Path,
) -> None:
    """All pre-existing capability blocks keep their baseline values."""
    caps = _capabilities(tmp_path)
    text_document = _text_document(tmp_path)
    assert caps["textDocumentSync"] == BASELINE_TEXT_DOCUMENT_SYNC
    assert text_document["synchronization"] == BASELINE_SYNCHRONIZATION
    assert text_document["completion"] == BASELINE_COMPLETION
    assert text_document["publishDiagnostics"] == BASELINE_PUBLISH_DIAGNOSTICS
    assert caps["workspace"] == BASELINE_WORKSPACE
    assert caps["window"] == BASELINE_WINDOW


def test_documentation_formats_constant_is_shared_by_both_declarations(
    tmp_path: Path,
) -> None:
    """Both format lists come from the single DOCUMENTATION_FORMATS constant."""
    expected = list(DOCUMENTATION_FORMATS)
    text_document = _text_document(tmp_path)
    hover = cast(dict[str, object], text_document["hover"])
    completion = cast(dict[str, object], text_document["completion"])
    completion_item = cast(dict[str, object], completion["completionItem"])
    assert hover["contentFormat"] == expected
    assert completion_item["documentationFormat"] == expected


def test_initialize_params_hover_declaration_has_no_dynamic_registration(
    tmp_path: Path,
) -> None:
    """Hover dynamicRegistration is False: no new server requests at runtime."""
    hover = cast(dict[str, object], _text_document(tmp_path)["hover"])
    assert hover["dynamicRegistration"] is False
