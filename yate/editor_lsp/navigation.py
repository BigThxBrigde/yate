"""L0 request layer for LSP navigation features: capability checks, bounded
requests and defensive wire-payload parsers.

Every request goes through :func:`request` (a bounded ``start_request`` +
``wait_for`` wrapper that cancels and settles the pending entry on timeout)
and every server payload goes through a total ``parse_*`` function that
never raises on malformed shapes.  Flows turn :class:`LspFeatureUnavailable`
(a missing/false server capability) and :class:`LspFeatureFailed` (a request
error, timeout or transport failure) into user-facing messages.

Only stdlib and local (``yate.editor_lsp``) imports are allowed here: this
module sits at L0 next to :mod:`yate.editor_lsp.parsing` and
:mod:`yate.editor_lsp.manager`.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, cast

from yate.editor_lsp.client import LspError
from yate.logs import tracing

#: Trace logger ("yate.editor_lsp.navigation"); silent unless yate_trace is on.
log = tracing.get_logger(__name__)

#: Reason spellings carried by :class:`LspFeatureUnavailable`.
REASON_NO_READY_SERVER: str = "no-ready-server"
REASON_UNSUPPORTED: str = "unsupported"

#: Bounded wait for a navigation response.  Mirrors ``HOVER_TIMEOUT_S``:
#: a hung server must degrade to "feature unavailable" instead of stalling
#: the UI worker that fired the request.
NAV_TIMEOUT_S: float = 3.0


class LspFeatureUnavailable(Exception):
    """The server does not advertise (or declares false) the capability.

    ``reason`` distinguishes *why* the feature is unusable:
    :data:`REASON_NO_READY_SERVER` when no READY client serves the document
    at all, and :data:`REASON_UNSUPPORTED` (the default) when a ready
    server's capabilities do not declare the feature.
    """

    def __init__(self, feature: str, reason: str = REASON_UNSUPPORTED) -> None:
        super().__init__(feature)
        self.feature = feature
        self.reason = reason


class LspFeatureFailed(Exception):
    """A request failed: error response, timeout or transport error.

    Carries the LSP method name so flows can point at the feature.
    """


# --------------------------------------------------------------- data types


@dataclass(frozen=True)
class LspLocation:
    """One jump target: a URI plus a buffer row/col range."""

    uri: str
    row: int
    col: int
    end_row: int
    end_col: int


@dataclass(frozen=True)
class LspSymbol:
    """One flattened document symbol (depth grows with nesting)."""

    name: str
    kind: int
    detail: str
    uri: str
    row: int
    col: int
    end_row: int
    end_col: int
    depth: int


@dataclass(frozen=True)
class LspTextEdit:
    """One replacement range + text (buffer rows/cols, UTF-16 clamped)."""

    start_row: int
    start_col: int
    end_row: int
    end_col: int
    text: str


@dataclass(frozen=True)
class WorkspaceEdit:
    """A parsed ``WorkspaceEdit``: per-URI edits, or ``unsupported``.

    ``unsupported`` is set when the server answered with file operations
    (``CreateFile`` / ``DeleteFile`` / ``RenameFile``) that we cannot apply.
    """

    changes: dict[str, tuple[LspTextEdit, ...]]
    unsupported: bool


@dataclass(frozen=True)
class LspCodeAction:
    """One quickfix / refactor / source action (or a bare command)."""

    title: str
    kind: str
    edit: WorkspaceEdit | None
    command: str | None
    arguments: tuple[object, ...]


@dataclass(frozen=True)
class LspSignature:
    """One signature-help card: rendered markdown + active parameter."""

    text: str
    active_parameter: int


# ------------------------------------------------------------ capability gate


def supports_feature(caps: dict[str, object], feature: str) -> bool:
    """Whether a server's ``capabilities`` dict declares *feature* usable.

    Missing, ``False`` and ``None`` are unavailable; ``True`` and any
    dict/list form (the object-shaped ``renameProvider`` /
    ``codeActionProvider``) are available.  Never raises.
    """
    value = caps.get(feature)
    if value is None or value is False:
        return False
    if value is True:
        return True
    if isinstance(value, (dict, list)):
        return True
    return False


# ------------------------------------------------------------- request layer


async def request(
    client: Any,  # noqa: Any - duck-typed LspClient (start_request/settle_request/send_cancel)
    method: str,
    params: dict[str, object],
) -> object:
    """Send one LSP request with a bounded wait and settle the pending entry.

    On timeout the pending request is cancelled via ``send_cancel``;
    ``settle_request`` always runs (success, error, timeout or
    cancellation).  :class:`asyncio.CancelledError` is re-raised as
    control flow; ``LspError`` / ``OSError`` / ``TimeoutError`` are
    wrapped into :class:`LspFeatureFailed` carrying *method*.
    """
    request_id, future = await client.start_request(method, params)
    try:
        raw = await asyncio.wait_for(future, NAV_TIMEOUT_S)
    except asyncio.CancelledError:
        raise
    except TimeoutError:
        # Best-effort cancel: a failed $/cancelRequest must not mask the
        # timeout itself, so the send failure is logged (never raised).
        try:
            await client.send_cancel(request_id)
        except (LspError, OSError) as exc:
            log.debug("send_cancel failed for %s: %s", method, exc)
        raise LspFeatureFailed(method) from None
    except (LspError, OSError) as exc:
        raise LspFeatureFailed(f"{method}: {exc}") from exc
    finally:
        # Drop the pending entry once the future settles so the response
        # payload does not stay referenced until teardown (manager seam).
        client.settle_request(request_id)
    return raw


# ------------------------------------------------------------------- parsers


def _pos_from(raw: object) -> tuple[int, int]:
    """Defensive (line, character) read from a Position dict (0/0 fallback)."""
    if not isinstance(raw, dict):
        return (0, 0)
    pos = cast(dict[str, object], raw)
    line = pos.get("line", 0)
    character = pos.get("character", 0)
    row = line if isinstance(line, int) and not isinstance(line, bool) else 0
    col = (
        character
        if isinstance(character, int) and not isinstance(character, bool)
        else 0
    )
    return (max(0, row), max(0, col))


def _range_from(raw: object) -> tuple[int, int, int, int]:
    """Defensive (start_row, start_col, end_row, end_col) read from a Range.

    Rows/columns clamp at 0 (the lower half of the clamp mirrors
    ``parsing._range_to_buffer_cols``; the upper half clamps against the
    real document and is applied by the manager once the buffer is known).
    """
    if not isinstance(raw, dict):
        return (0, 0, 0, 0)
    rng = cast(dict[str, object], raw)
    r0, c0 = _pos_from(rng.get("start"))
    r1, c1 = _pos_from(rng.get("end"))
    return (r0, c0, r1, c1)


def parse_locations(raw: object) -> list[LspLocation]:
    """Parse a Location[] / LocationLink[] / Location / null response.

    Accepts full ``Location`` dicts (``uri`` + ``range``), ``LocationLink``
    dicts (``targetUri`` + ``targetRange``) and ``None`` entries (skipped).
    Malformed shapes are skipped, never raised.  Columns stay UTF-16
    code-unit clamped-at-zero; the manager converts to buffer columns.
    """
    if raw is None:
        return []
    if isinstance(raw, dict):
        items: list[object] = [raw]
    elif isinstance(raw, list):
        items = list(cast(list[object], raw))
    else:
        return []
    result: list[LspLocation] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        entry = cast(dict[str, object], item)
        uri = entry.get("targetUri") if "targetUri" in entry else entry.get("uri")
        if not isinstance(uri, str) or not uri:
            continue
        range_key = "targetRange" if "targetUri" in entry else "range"
        r0, c0, r1, c1 = _range_from(entry.get(range_key))
        result.append(LspLocation(uri=uri, row=r0, col=c0, end_row=r1, end_col=c1))
    return result


def parse_symbols(raw: object) -> list[LspSymbol]:
    """Flatten a DocumentSymbol[] or SymbolInformation[] response.

    ``DocumentSymbol`` entries recurse into ``children`` with an
    increasing ``depth`` and jump from ``selectionRange``;
    ``SymbolInformation`` entries (no ``selectionRange`` / ``children``)
    jump from ``location.uri`` + ``location.range``.  Malformed entries
    are skipped, never raised.
    """
    if not isinstance(raw, list):
        return []
    result: list[LspSymbol] = []
    _parse_symbol_list(cast(list[object], raw), depth=0, result=result)
    return result


def _parse_symbol_list(
    items: list[object], depth: int, result: list[LspSymbol]
) -> None:
    """Recursive worker for :func:`parse_symbols`."""
    for item in items:
        if not isinstance(item, dict):
            continue
        entry = cast(dict[str, object], item)
        name = entry.get("name")
        if not isinstance(name, str) or not name:
            continue
        kind = entry.get("kind")
        kind_num = kind if isinstance(kind, int) and not isinstance(kind, bool) else 0
        detail = entry.get("detail")
        uri = ""
        rng: tuple[int, int, int, int]
        children: list[object] = []
        if isinstance(entry.get("selectionRange"), dict):
            # DocumentSymbol shape: jump from selectionRange.
            rng = _range_from(entry.get("selectionRange"))
            location = entry.get("location")
            if isinstance(location, dict):
                loc_uri = cast(dict[str, object], location).get("uri")
                if isinstance(loc_uri, str):
                    uri = loc_uri
            raw_children = entry.get("children")
            if isinstance(raw_children, list):
                children = list(cast(list[object], raw_children))
        else:
            # SymbolInformation shape: jump from location.uri + location.range.
            location = entry.get("location")
            if not isinstance(location, dict):
                continue
            loc = cast(dict[str, object], location)
            loc_uri = loc.get("uri")
            if not isinstance(loc_uri, str) or not loc_uri:
                continue
            uri = loc_uri
            rng = _range_from(loc.get("range"))
        result.append(LspSymbol(
            name=name,
            kind=kind_num,
            detail=detail if isinstance(detail, str) else "",
            uri=uri,
            row=rng[0],
            col=rng[1],
            end_row=rng[2],
            end_col=rng[3],
            depth=depth,
        ))
        if children:
            _parse_symbol_list(children, depth + 1, result)


def parse_workspace_edit(raw: object) -> WorkspaceEdit:
    """Parse a WorkspaceEdit; file operations mark the whole edit unsupported.

    Supports ``changes: dict[uri, TextEdit[]]`` and ``documentChanges``
    entries with an ``edits`` list.  When any ``CreateFile`` /
    ``DeleteFile`` / ``RenameFile`` operation appears, ``unsupported`` is
    set and no partial changes are returned (an edit we can only half
    apply must not be applied at all).
    """
    if not isinstance(raw, dict):
        return WorkspaceEdit(changes={}, unsupported=False)
    payload = cast(dict[str, object], raw)
    if _has_file_operation(payload):
        return WorkspaceEdit(changes={}, unsupported=True)
    changes: dict[str, tuple[LspTextEdit, ...]] = {}
    raw_changes = payload.get("changes")
    if isinstance(raw_changes, dict):
        # dict keys are already str: only validate the edits list shape.
        for uri_raw, edits_raw in cast(dict[str, object], raw_changes).items():
            if not isinstance(edits_raw, list):
                continue
            parsed = _parse_text_edits(cast(list[object], edits_raw))
            if parsed:
                changes[uri_raw] = parsed
    raw_document_changes = payload.get("documentChanges")
    if isinstance(raw_document_changes, list):
        for item in cast(list[object], raw_document_changes):
            if not isinstance(item, dict):
                continue
            entry = cast(dict[str, object], item)
            text_document = entry.get("textDocument")
            uri = (
                cast(dict[str, object], text_document).get("uri")
                if isinstance(text_document, dict)
                else None
            )
            edits = entry.get("edits")
            if (
                not isinstance(uri, str)
                or not isinstance(edits, list)
                or _is_file_operation(entry)
            ):
                continue
            parsed = _parse_text_edits(cast(list[object], edits))
            if parsed:
                changes[uri] = changes.get(uri, ()) + parsed
    return WorkspaceEdit(changes=changes, unsupported=False)


def _has_file_operation(payload: dict[str, object]) -> bool:
    """Whether a WorkspaceEdit payload contains any file operation entry."""
    raw_document_changes = payload.get("documentChanges")
    if isinstance(raw_document_changes, list):
        for item in cast(list[object], raw_document_changes):
            if isinstance(item, dict) and _is_file_operation(
                cast(dict[str, object], item)
            ):
                return True
    return False


def _is_file_operation(entry: dict[str, object]) -> bool:
    """Whether one ``documentChanges`` entry is Create/Delete/RenameFile."""
    return any(key in entry for key in ("kind", "create", "delete", "rename"))


def _parse_text_edits(items: list[object]) -> tuple[LspTextEdit, ...]:
    """Parse a TextEdit[] into LspTextEdit tuples (malformed entries skip)."""
    result: list[LspTextEdit] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        entry = cast(dict[str, object], item)
        text = entry.get("newText")
        if not isinstance(text, str):
            continue
        r0, c0, r1, c1 = _range_from(entry.get("range"))
        result.append(LspTextEdit(
            start_row=r0, start_col=c0, end_row=r1, end_col=c1, text=text,
        ))
    return tuple(result)


def parse_code_actions(raw: object) -> list[LspCodeAction]:
    """Parse a CodeAction[] / Command[] response.

    Accepts ``CodeAction`` dicts (``title`` / ``kind`` / ``edit`` /
    ``command``) and bare ``Command`` dicts (``title`` / ``command`` /
    ``arguments``).  Malformed entries are skipped, never raised.
    """
    if not isinstance(raw, list):
        return []
    result: list[LspCodeAction] = []
    for item in cast(list[object], raw):
        if not isinstance(item, dict):
            continue
        entry = cast(dict[str, object], item)
        title = entry.get("title")
        if not isinstance(title, str) or not title:
            continue
        kind = entry.get("kind")
        edit = (
            parse_workspace_edit(entry.get("edit"))
            if isinstance(entry.get("edit"), dict)
            else None
        )
        command_name: str | None = None
        arguments: tuple[object, ...] = ()
        raw_command = entry.get("command")
        if isinstance(raw_command, str):
            command_name = raw_command
        elif isinstance(raw_command, dict):
            command_entry = cast(dict[str, object], raw_command)
            name = command_entry.get("command")
            if isinstance(name, str):
                command_name = name
            raw_args = command_entry.get("arguments")
            if isinstance(raw_args, list):
                arguments = tuple(cast(list[object], raw_args))
        result.append(LspCodeAction(
            title=title,
            kind=kind if isinstance(kind, str) else "",
            edit=edit,
            command=command_name,
            arguments=arguments,
        ))
    return result


def parse_signature_help(raw: object) -> LspSignature | None:
    """Parse a SignatureHelp into a markdown card with bold active parameter.

    Picks ``activeSignature`` (default 0) then ``activeParameter``
    (default 0) and renders the signature ``label`` with the active
    parameter's label marked bold.  ``None`` / malformed / empty payloads
    return ``None``; the function never raises.
    """
    if not isinstance(raw, dict):
        return None
    payload = cast(dict[str, object], raw)
    signatures_raw = payload.get("signatures")
    if not isinstance(signatures_raw, list) or not signatures_raw:
        return None
    signatures = [
        cast(dict[str, object], s)
        for s in cast(list[object], signatures_raw)
        if isinstance(s, dict)
    ]
    if not signatures:
        return None
    active_sig_raw = payload.get("activeSignature", 0)
    active_sig = (
        active_sig_raw
        if isinstance(active_sig_raw, int)
        and not isinstance(active_sig_raw, bool)
        and 0 <= active_sig_raw < len(signatures)
        else 0
    )
    signature = signatures[active_sig]
    label = signature.get("label")
    if not isinstance(label, str):
        return None
    active_param_raw = payload.get("activeParameter", 0)
    active_param = (
        active_param_raw
        if isinstance(active_param_raw, int) and not isinstance(active_param_raw, bool)
        else 0
    )
    card = _format_signature_card(signature, label, active_param)
    return LspSignature(text=card, active_parameter=active_param)


def _format_signature_card(
    signature: dict[str, object], label: str, active_param: int
) -> str:
    """Render one signature as markdown, bolding the active parameter.

    The active parameter's label is located either from the
    ``SignatureInformation.parameters[*].label`` string form or from the
    ``[start, end]`` offset pair into the signature label.  An
    unresolvable active parameter renders the plain label.
    """
    parameters_raw = signature.get("parameters")
    marker: str | None = None
    if isinstance(parameters_raw, list):
        params = [
            cast(dict[str, object], p)
            for p in cast(list[object], parameters_raw)
            if isinstance(p, dict)
        ]
        if 0 <= active_param < len(params):
            param_label = params[active_param].get("label")
            if isinstance(param_label, str) and param_label:
                marker = param_label
            elif (
                isinstance(param_label, list)
                and len(cast(list[object], param_label)) == 2
                and all(
                    isinstance(x, int) and not isinstance(x, bool)
                    for x in cast(list[object], param_label)
                )
            ):
                start, end = cast(list[int], param_label)
                if 0 <= start <= end <= len(label):
                    marker = label[start:end]
    if not marker:
        return label
    return label.replace(marker, f"**{marker}**", 1)
