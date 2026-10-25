"""Chunked document flows: background scan, on-demand fills and promotion.

Orchestrates the progressive loading of a chunked
:class:`~yate.editor_core.document.Document`: a background worker advances
the chunk index and grows the placeholder rows (so the virtual scroll size
tracks the file), the EditorView render path requests individual rows via
:meth:`ensure_row`, and ``:fullload`` promotes the document to a fully
loaded editable buffer via :meth:`promote_to_full`.

Constructed by the editor with explicit collaborators and callbacks; no
upward imports and no App handle (architecture-boundaries section 3.8).
Content is only ever read on the UI thread (:meth:`ensure_row` and the
synchronous first-chunk fill in :meth:`attach`); the worker thread only
advances the index and appends placeholder rows, mirroring the threading
discipline of :mod:`yate.editor_core.chunked`.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import partial

from yate.editor_core.buffer import TextBuffer
from yate.editor_core.chunked import ChunkedTextFile
from yate.editor_core.document import Document
from yate.flows import MessageFn, SpawnFn, StateQuery


class ChunkedFlows:
    """Owns the progressive loading lifecycle of chunked documents."""

    def __init__(
        self,
        ensure_view_refresh: Callable[[], None],
        message: MessageFn,
        spawn: SpawnFn,
        active_doc: Callable[[], Document],
        mounted: StateQuery,
    ) -> None:
        self._ensure_view_refresh = ensure_view_refresh
        self._message = message
        self._spawn = spawn
        self._active_doc = active_doc
        self._mounted = mounted
        #: Documents whose background scan worker has been spawned (by
        #: document uid -- :meth:`start_scan` is idempotent, and the
        #: pre-mount flush in ``Editor.on_mount`` re-runs it safely).
        self._scan_started: set[int] = set()

    # ---------------------------------------------------------------- attach

    def attach(self, doc: Document) -> None:
        """Bind a freshly opened chunked document and fill its first chunk.

        The first chunk is read synchronously so the first paint shows real
        content; the background scan worker starts immediately when the
        editor is already mounted, otherwise ``Editor.on_mount`` flushes it
        (the startup document opens before the widget tree exists).
        """
        chunked = doc.chunked
        if chunked is None:
            return
        rows = chunked.read_rows(0, self._first_chunk_rows(chunked))
        if rows:
            doc.buffer.fill_lines(0, rows)
        if self._mounted():
            self.start_scan(doc)

    def start_scan(self, doc: Document) -> None:
        """Spawn the background scan worker for *doc* (idempotent)."""
        if doc.chunked is None or doc.uid in self._scan_started:
            return
        self._scan_started.add(doc.uid)
        self._spawn(
            partial(self._scan_worker, doc),
            group="chunked-scan", exclusive=False, exit_on_error=False,
        )

    # ------------------------------------------------------------ row access

    def ensure_row(self, doc: Document, row: int) -> None:
        """Fill the content for a rendered row of a chunked document.

        Called from the EditorView render path.  Loaded rows return
        immediately (a watermark comparison); otherwise the rows from the
        first placeholder through the end of the chunk owning *row* are
        read and filled (contiguous advancement, so the buffer's
        ``rows_loaded`` contract holds).  Rows the scan has not reached
        yet are skipped -- the placeholder extension and the next render
        pass pick them up.
        """
        chunked = doc.chunked
        if chunked is None or row < 0:
            return
        buf = doc.buffer
        if buf.rows_loaded(row, 1):
            return
        starts = chunked.chunk_start_rows
        index = chunked.chunk_for_row(row)
        if index >= len(starts):
            return
        chunk_end = (
            starts[index + 1] if index + 1 < len(starts) else chunked.total_lines
        )
        start = buf.filled_rows
        rows = chunked.read_rows(start, chunk_end - start)
        if rows:
            buf.fill_lines(start, rows)

    # -------------------------------------------------------------- fullload

    def promote_to_full(self) -> None:
        """``:fullload``: promote the active chunked document to a full buffer.

        A plain (non-chunked) active document is a no-op with a notice.
        """
        doc = self._active_doc()
        if doc.chunked is None:
            self._message("buffer is fully loaded already", "info")
            return
        doc.promote_to_full()
        self._message("buffer fully loaded", "ok")
        self._ensure_view_refresh()

    # ------------------------------------------------------------- internals

    @staticmethod
    def _first_chunk_rows(chunked: ChunkedTextFile) -> int:
        """Row count of the first chunk (scanning ahead until it is known)."""
        while len(chunked.chunk_start_rows) < 2 and chunked.scan_next_batch():
            pass
        if len(chunked.chunk_start_rows) >= 2:
            return chunked.chunk_start_rows[1]
        return chunked.total_lines

    def _scan_worker(self, doc: Document) -> None:
        """Advance the chunk index off-loop and grow the placeholder rows.

        Index-only: no content is read here (memory stays bounded by the
        on-demand fills); a promotion (:fullload) while scanning stops the
        loop early.
        """
        chunked = doc.chunked
        if chunked is None:
            return
        buf = doc.buffer
        while chunked.scan_next_batch():
            if doc.chunked is not chunked:
                return
            self._extend_placeholders(chunked, buf)
        self._extend_placeholders(chunked, buf)
        self._ensure_view_refresh()

    @staticmethod
    def _extend_placeholders(chunked: ChunkedTextFile, buf: TextBuffer) -> None:
        """Grow the placeholder rows to the scanned prefix (worker thread)."""
        buf.extend_placeholders(chunked.total_lines - len(buf.lines))
