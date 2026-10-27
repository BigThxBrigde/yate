"""didChange send orchestration for the LSP manager.

Split out of :mod:`yate.editor_lsp.manager` (F1 blocker-1, same precedent
as the wave-f ``parsing.py`` extraction): this module owns the two wire
paths of ``textDocument/didChange`` -- Full (the row snapshot joined into
one text payload) and incremental (:func:`build_content_changes` patches)
-- plus the shared "re-check the document is still open, then advance the
sync state only after a successful notify" tail that both paths used to
duplicate in the manager.  The per-uri in-flight gate travels with the
dispatch: a uri already sending is skipped outright so the completion
fallback cannot push the same patch twice.

No I/O ownership and no Textual imports: ``editor_lsp`` is an L0 leaf
package.  Everything the orchestration needs is injected by
:mod:`yate.editor_lsp.manager` as plain arguments (client, open-document
table, shutdown probe, in-flight gate set); no protocol types, no
callback registries, no class hierarchy.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from yate.editor_core.document import Document

from yate.editor_lsp.client import SYNC_INCREMENTAL, LspClient, LspError
from yate.editor_lsp.diff import build_content_changes


@dataclass
class OpenDocState:
    """State of one text document currently open with a server.

    ``version``/``last_synced_lines`` advance only after a successful
    didChange notify; pushes whose lines match ``last_synced_lines`` are
    skipped.  ``last_synced_version`` mirrors ``buffer.content_version``
    at the moment the lines were last sent, giving
    :meth:`yate.editor_lsp.manager.LspManager.notify_edit` an O(1) gate
    that avoids materializing the full document text on every key.
    """

    uri: str
    config_name: str
    client_key: tuple[str, str]
    language_id: str
    version: int
    #: Row snapshot of the buffer as of the last successful didChange /
    #: didOpen; the diff basis for incremental sends.
    last_synced_lines: tuple[str, ...]
    last_synced_version: int
    #: The open document, kept so incoming server positions (UTF-16 code
    #: units) can be converted back to buffer columns (code points).
    doc: Document


async def dispatch_change(
    open_docs: dict[str, OpenDocState],
    is_shutting_down: Callable[[], bool],
    inflight_changes: set[str],
    client: LspClient,
    uri: str,
    state: OpenDocState,
    version: int,
    new_lines: Sequence[str],
    buffer_version: int,
) -> None:
    """Send one pending didChange through the negotiated sync kind.

    Incremental servers (:data:`SYNC_INCREMENTAL`) get row-snapshot diff
    patches; every other negotiated kind is Full, which resends the whole
    buffer (the only path that joins the document text).  Both paths
    advance state only after a successful notify.  A uri already in
    flight is skipped outright -- the in-flight send was built from the
    same ``last_synced_lines`` snapshot, so a second send would apply the
    identical patch twice (review R1 blocker: patch drift).

    *open_docs* is the manager's live ``_open`` table and
    *is_shutting_down* its shutdown probe; both are re-consulted after
    the await so a document closed mid-flight never advances stale state.
    """
    if uri in inflight_changes:
        return
    inflight_changes.add(uri)
    try:
        await _send_change(
            open_docs, is_shutting_down, client, uri, state,
            version, new_lines, buffer_version,
        )
    finally:
        inflight_changes.discard(uri)


async def _send_change(
    open_docs: dict[str, OpenDocState],
    is_shutting_down: Callable[[], bool],
    client: LspClient,
    uri: str,
    state: OpenDocState,
    version: int,
    new_lines: Sequence[str],
    buffer_version: int,
) -> None:
    """Send a single didChange and advance *state* only after success.

    ``buffer_version`` is the ``buffer.content_version`` snapshot taken
    when *new_lines* was materialized.  A failed notify leaves the
    snapshot stale so the next :meth:`LspManager.notify_edit` retries
    naturally; a successful one sets ``version``, ``last_synced_lines``
    and ``last_synced_version`` in one place (the tail both former
    manager send paths duplicated).
    """
    lines = tuple(new_lines)
    content_changes: list[dict[str, Any]]
    if client.sync_kind == SYNC_INCREMENTAL:
        content_changes = build_content_changes(state.last_synced_lines, lines)
    else:
        content_changes = [{"text": "\n".join(lines)}]
    try:
        await client.notify("textDocument/didChange", {
            "textDocument": {"uri": uri, "version": version},
            "contentChanges": content_changes,
        })
    except (LspError, OSError):
        return
    # Re-check the document hasn't been closed while we awaited.
    if open_docs.get(uri) is state and not is_shutting_down():
        state.version = version
        state.last_synced_lines = lines
        state.last_synced_version = buffer_version
