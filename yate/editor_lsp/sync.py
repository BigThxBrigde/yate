"""didChange send orchestration for the LSP manager.

Split out of :mod:`yate.editor_lsp.manager` (F1 blocker-1, same precedent
as the wave-f ``parsing.py`` extraction): this module owns the two wire
paths of ``textDocument/didChange`` -- Full (the row snapshot joined into
one text payload) and incremental (:func:`build_content_changes` patches)
-- plus the shared "re-check the document is still open, then advance the
sync state only after a successful notify" tail that both paths used to
duplicate in the manager.  The per-uri serialization lock travels with
the dispatch: a second send for a uri already in flight waits on the
same ``asyncio.Lock`` and then re-diffs against the advanced
``last_synced_lines``, so edits made while the first send hung are
flushed as a follow-up patch instead of being dropped (review R2: the
former skip-gate lost them) and an equal patch is never applied twice.

No I/O ownership and no Textual imports: ``editor_lsp`` is an L0 leaf
package.  Everything the orchestration needs is injected by
:mod:`yate.editor_lsp.manager` as plain arguments (client, open-document
table, shutdown probe, per-uri change locks); no protocol types, no
callback registries, no class hierarchy.
"""

from __future__ import annotations

import asyncio
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
    change_locks: dict[str, asyncio.Lock],
    client: LspClient,
    uri: str,
    state: OpenDocState,
    new_lines: Sequence[str],
    buffer_version: int,
) -> None:
    """Send one pending didChange through the negotiated sync kind.

    Incremental servers (:data:`SYNC_INCREMENTAL`) get row-snapshot diff
    patches; every other negotiated kind is Full, which resends the whole
    buffer (the only path that joins the document text).  Both paths
    advance state only after a successful notify.  Sends for one uri are
    serialized on a shared ``asyncio.Lock`` (get-or-create in
    *change_locks*): a concurrent flush path (the ``request_completion``
    fallback) waits for the in-flight send, then re-diffs against the
    advanced ``last_synced_lines`` -- no lost edits, no duplicated patch
    (review R2 blocker: the former skip-gate dropped in-window edits).
    The wire ``version`` is allocated inside the lock, so senders that
    queued behind a hung notify always put strictly increasing numbers
    on the wire (review R3: a caller-computed version could repeat).

    *open_docs* is the manager's live ``_open`` table and
    *is_shutting_down* its shutdown probe; both are re-consulted before
    the notify and again after it so a document closed mid-flight never
    advances stale state.  The lock entry is dropped once its uri no
    longer maps to this *state* (closed or reopened), so the table
    cannot grow without bound and a reopened document never reuses a
    stale lock (review R3 N5).
    """
    lock = change_locks.get(uri)
    if lock is None:
        lock = asyncio.Lock()
        change_locks[uri] = lock
    async with lock:
        await _send_change(
            open_docs, is_shutting_down, client, uri, state,
            new_lines, buffer_version,
        )
        if open_docs.get(uri) is not state:
            change_locks.pop(uri, None)


async def _send_change(
    open_docs: dict[str, OpenDocState],
    is_shutting_down: Callable[[], bool],
    client: LspClient,
    uri: str,
    state: OpenDocState,
    new_lines: Sequence[str],
    buffer_version: int,
) -> None:
    """Send a single didChange and advance *state* only after success.

    ``buffer_version`` is the ``buffer.content_version`` snapshot taken
    when *new_lines* was materialized.  The wire ``version`` is computed
    here under the per-uri lock (``state.version + 1``) so queued senders
    allocate strictly increasing numbers against the already-advanced
    state.  A failed notify leaves the snapshot stale so the next
    :meth:`LspManager.notify_edit` retries naturally; a successful one
    sets ``version``, ``last_synced_lines`` and ``last_synced_version``
    in one place (the tail both former manager send paths duplicated).
    """
    lines = tuple(new_lines)
    content_changes: list[dict[str, Any]]  # noqa: Any - wire payloads mirror the LSP JSON schema
    if client.sync_kind == SYNC_INCREMENTAL:
        content_changes = build_content_changes(state.last_synced_lines, lines)
    else:
        content_changes = [{"text": "\n".join(lines)}]
    if not content_changes:
        # Empty patch: a waiter woke up after the in-flight send already
        # flushed its snapshot, and nothing changed since -- the norm for
        # serialized sends with no further edits.
        return
    # Re-check the document is still open before going on the wire.
    if open_docs.get(uri) is not state or is_shutting_down():
        return
    version = state.version + 1
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
