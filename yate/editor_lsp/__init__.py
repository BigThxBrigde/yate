"""editor_lsp -- a minimal, dependency-free Language Server Protocol client.

The package speaks LSP 3.17 over stdio using only the standard library
(``asyncio`` subprocess transport with ``Content-Length`` framed JSON-RPC).
It is deliberately UI independent:

* :mod:`yate.editor_lsp.protocol` -- message framing and URI helpers
* :mod:`yate.editor_lsp.client`   -- one language server process
* :mod:`yate.editor_lsp.manager`  -- registration, per-document sync,
  completion requests and diagnostics storage

Language servers are registered by extensions through
``api.lsp.register_server(...)``; the core editor ships no servers itself.
"""

from yate.editor_lsp.client import (
    Completion,
    Diagnostic,
    DiagnosticSeverity,
    LspClient,
    ServerConfig,
    ServerState,
)
from yate.editor_lsp.manager import LspManager

__all__ = [
    "Completion",
    "Diagnostic",
    "DiagnosticSeverity",
    "LspClient",
    "LspManager",
    "ServerConfig",
    "ServerState",
]
