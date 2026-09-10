"""JSON-RPC 2.0 message framing for LSP over stdio.

Every message is a JSON object wrapped in an HTTP-like header::

    Content-Length: 75\\r\\n
    Content-Type: application/vscode-jsonrpc; charset=utf-8\\r\\n
    \\r\\n
    {"jsonrpc":"2.0", ...}

Only ``Content-Length`` is required; extra header lines (servers may emit
``Content-Type``) are tolerated.  The framing functions are pure where
possible so they can be unit tested without a subprocess.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional, cast
from urllib.parse import unquote, urlparse

#: Protocol version advertised to the server.
JSONRPC = "2.0"

#: Maximum body size accepted for one message (32 MiB).  Guards against a
#: corrupt length prefix making the reader allocate forever.
MAX_MESSAGE_BYTES = 32 * 1024 * 1024


class LspProtocolError(RuntimeError):
    """Raised when a peer violates the LSP framing protocol."""


def encode_message(payload: dict[str, Any]) -> bytes:
    """Serialize *payload* with the standard LSP header."""
    body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return b"Content-Length: " + str(len(body)).encode("ascii") + b"\r\n\r\n" + body


def build_request(
    request_id: int, method: str, params: Optional[dict[str, Any]] = None
) -> dict[str, Any]:
    msg: dict[str, Any] = {"jsonrpc": JSONRPC, "id": request_id, "method": method}
    if params is not None:
        msg["params"] = params
    return msg


def build_notification(method: str, params: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    msg: dict[str, Any] = {"jsonrpc": JSONRPC, "method": method}
    if params is not None:
        msg["params"] = params
    return msg


def build_response(request_id: int, result: Any) -> dict[str, Any]:
    return {"jsonrpc": JSONRPC, "id": request_id, "result": result}


def build_error(request_id: int, code: int, message: str) -> dict[str, Any]:
    return {
        "jsonrpc": JSONRPC,
        "id": request_id,
        "error": {"code": code, "message": message},
    }


def parse_headers(header_block: bytes) -> int:
    """Extract the body length from a CRLF terminated header block."""
    length: Optional[int] = None
    for raw_line in header_block.split(b"\r\n"):
        if not raw_line:
            continue
        name, sep, value = raw_line.partition(b":")
        if not sep:
            raise LspProtocolError(f"malformed header line: {raw_line!r}")
        if name.strip().lower() == b"content-length":
            try:
                length = int(value.strip())
            except ValueError as exc:
                raise LspProtocolError("invalid Content-Length") from exc
    if length is None:
        raise LspProtocolError("missing Content-Length header")
    if length < 0 or length > MAX_MESSAGE_BYTES:
        raise LspProtocolError(f"Content-Length out of range: {length}")
    return length


def decode_body(body: bytes) -> dict[str, Any]:
    """Decode a JSON message body; LSP always uses UTF-8."""
    try:
        data: Any = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LspProtocolError(f"invalid JSON body: {exc}") from exc
    if not isinstance(data, dict):
        raise LspProtocolError("message body is not a JSON object")
    return cast(dict[str, Any], data)


async def read_message(reader: Any) -> Optional[dict[str, Any]]:
    """Read one framed message from an asyncio-style stream reader.

    Returns ``None`` on clean EOF before the next header starts.  Accepts
    anything implementing ``readline()`` and ``readexactly(n)`` (the test
    suite uses an in-memory implementation as well as real pipe streams).
    """
    header_lines = b""
    while True:
        line = await reader.readline()
        if line == b"":
            if header_lines:
                raise LspProtocolError("EOF in the middle of message headers")
            return None
        header_lines += line
        if line in (b"\r\n", b"\n"):
            break
    length = parse_headers(header_lines)
    body = await reader.readexactly(length)
    return decode_body(body)


# --------------------------------------------------------------------- URIs

def _url_path_to_pathname(url_path: str) -> str:
    """Percent-decode an URL path component and map a Windows drive prefix.

    Replaces ``urllib.request.url2pathname`` (deprecated in 3.14): turns
    ``/D:/foo`` into ``D:/foo`` on Windows and leaves POSIX paths alone.
    """
    decoded = unquote(url_path)
    if (
        os.name == "nt"
        and len(decoded) >= 3
        and decoded[0] == "/"
        and decoded[1].isascii()
        and decoded[1].isalpha()
        and decoded[2] == ":"
    ):
        decoded = decoded[1:]
    return decoded


def path_to_uri(path: Path | str) -> str:
    """Convert a filesystem path to an LSP ``file://`` URI."""
    return Path(path).resolve().as_uri()


def uri_to_path(uri: str) -> Path:
    """Convert a ``file://`` URI back to a filesystem path.

    Also tolerates servers that misuse the uri fields with a bare OS path.
    """
    parsed = urlparse(uri)
    if parsed.scheme == "file":
        # Decode percent escapes and turn /D:/foo into a Windows drive path.
        return Path(_url_path_to_pathname(parsed.path))
    if parsed.scheme == "":
        return Path(unquote(uri))
    # Unknown scheme (untitled:, ...): use the path portion when present.
    return Path(_url_path_to_pathname(parsed.path)) if parsed.path else Path(uri)


def uri_file_name(uri: str) -> str:
    """File name portion of a URI (for logs/messages)."""
    tail = uri.rstrip("/").rsplit("/", 1)[-1]
    return unquote(tail.split("?", 1)[0])
