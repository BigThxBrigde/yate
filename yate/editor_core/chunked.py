"""Chunked file access for very large files.

Provides :class:`ChunkedTextFile`, a row-oriented reader that splits a file
into newline-aligned chunks backed by an LRU cache, and
:class:`ChunkedBinaryFile`, a block-cached random-access reader with dirty
byte edits for the hex view.  Both are pure stdlib L0 leaves: no imports from
upper layers, no logging and no UI dependencies.

Row model: rows are the newline-delimited segments of the decoded file with
one trailing carriage return stripped (CRLF files read back as LF rows).
Chunk boundaries always coincide with row boundaries; a line longer than the
chunk size forms an oversized chunk.  Files whose first block contains a
carriage return but no newline (CR-only line endings) cannot be chunk-aligned
and raise :class:`ChunkedFallback`.

Threading discipline: :meth:`ChunkedTextFile.scan_next_batch` is called from
a worker thread while the row accessors run on the UI thread; a
:class:`threading.Lock` guards the scanned prefix metadata.  The row content
cache is only touched on the UI-thread read path and needs no lock.
"""

from __future__ import annotations

import locale
import threading
from bisect import bisect_right
from collections import deque
from collections.abc import Iterable
from pathlib import Path

#: Target size per text chunk (256 KiB).
CHUNK_SIZE: int = 262_144

#: Chunks processed per :meth:`ChunkedTextFile.scan_next_batch` call.
SCAN_BATCH_CHUNKS: int = 4

#: Maximum chunks/blocks kept resident in the LRU caches
#: (about 8 MiB of text or 2 MiB of binary data).
MAX_CACHED_CHUNKS: int = 32

#: Block size for the hex view (64 KiB).
HEX_BLOCK_SIZE: int = 65_536

#: Bytes read from the file head to probe the encoding (64 KiB).
_PROBE_BYTES: int = 65_536


class ChunkedFallback(Exception):
    """File shape cannot be chunk-aligned (CR-only line endings)."""


def _decode_probe(raw: bytes) -> tuple[str, int]:
    """Probe the encoding of *raw* and return ``(encoding, bom_offset)``.

    Mirrors the ``Document._decode`` semantics: a valid UTF-8 BOM selects
    ``utf-8-sig`` (with a 3-byte offset the first chunk must skip), then
    ``utf-8``, the preferred locale encoding and ``cp1252`` are tried in
    order; everything else decodes as ``utf-8`` with replacements.
    """
    if raw.startswith(b"\xef\xbb\xbf"):
        try:
            raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            pass
        else:
            return "utf-8-sig", 3
    for encoding in ("utf-8", locale.getpreferredencoding(False), "cp1252"):
        if not encoding:
            continue
        try:
            raw.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
        return encoding, 0
    return "utf-8", 0


def _split_rows(text: str, *, is_last: bool) -> list[str]:
    """Split decoded chunk *text* into rows.

    Rows are the newline-delimited segments with one trailing carriage
    return stripped.  Unless *is_last* marks the final chunk, the segment
    after the trailing newline belongs to the next chunk and is dropped
    here, so row counts stay consistent across chunk boundaries.
    """
    segments = text.split("\n")
    if not is_last:
        segments = segments[:-1]
    return [
        segment[:-1] if segment.endswith("\r") else segment for segment in segments
    ]


class ChunkedTextFile:
    """Chunk-aligned row reader over a text file with an LRU chunk cache.

    The file is cut into chunks of *chunk_size* bytes whose boundaries are
    extended to the next newline, so every chunk boundary coincides with a
    row boundary and rows never span two chunks.  The scanned prefix
    metadata (``chunk_start_rows`` / ``scanned_chunks`` / ``total_lines``)
    is guarded by a lock because scanning runs on a worker thread while row
    access runs on the UI thread.

    Encoding note: the encoding is probed from the first 64 KiB only, so a
    file whose later part decodes differently (e.g. a mostly-ASCII log with
    a few legacy-encoded lines) may show replacement characters where a
    whole-file decode would have succeeded -- the trade keeps opening a
    multi-gigabyte file O(1).
    """

    def __init__(self, path: Path, chunk_size: int = CHUNK_SIZE) -> None:
        self.path: Path = path
        self.total_bytes: int = path.stat().st_size
        self._chunk_size: int = chunk_size
        self._lock = threading.Lock()
        # Scanned prefix metadata -- guarded by ``self._lock``.
        self.chunk_start_rows: list[int] = []
        self.scanned_chunks: int = 0
        self.total_lines: int = 0
        self._chunk_offsets: list[int] = []
        self._scan_complete: bool = False
        # Row content cache -- UI-thread read path only, no lock needed.
        self._cache: dict[int, list[str]] = {}
        self._cache_order: deque[int] = deque()
        probe = self._read_probe()
        encoding, bom_offset = _decode_probe(probe)
        self.encoding: str = encoding
        self._bom_offset: int = bom_offset
        self._scan_complete = self.total_bytes <= bom_offset
        if b"\r" in probe and b"\n" not in probe:
            raise ChunkedFallback(
                f"{path}: CR-only line endings cannot be chunk-aligned"
            )

    # ------------------------------------------------------------- scanning

    def scan_next_batch(self, batches: int = SCAN_BATCH_CHUNKS) -> bool:
        """Scan up to *batches* more chunk boundaries from a worker thread.

        Returns ``True`` while scanning is still incomplete and ``False``
        once the whole file has been scanned.
        """
        with self._lock:
            for _ in range(batches):
                if self._scan_complete:
                    return False
                self._advance_boundary_locked()
            return not self._scan_complete

    def row_count(self) -> int:
        """Return the number of rows, scanning the remainder on demand."""
        with self._lock:
            while not self._scan_complete:
                self._advance_boundary_locked()
            return self.total_lines

    # ----------------------------------------------------------- row access

    def chunk_for_row(self, row: int) -> int:
        """Return the chunk index holding *row* by bisecting prefix sums.

        *row* is clamped to the known row range the same way
        :meth:`TextBuffer.line` clamps its row argument.
        """
        with self._lock:
            if not self.chunk_start_rows:
                return 0
            clamped = max(0, min(row, self.total_lines - 1))
            return max(0, bisect_right(self.chunk_start_rows, clamped) - 1)

    def read_rows(self, start: int, count: int) -> list[str]:
        """Return up to *count* rows beginning at *start*, caching chunks.

        Chunks are loaded on demand; *start* is clamped to zero and a
        *start* at or past the end of the file yields an empty list.
        """
        if count <= 0:
            return []
        rows: list[str] = []
        pos = max(0, start)
        remaining = count
        while remaining > 0:
            located = self._locate_row(pos)
            if located is None:
                break
            index, chunk_first = located
            lines = self._read_chunk_lines(index)
            offset = pos - chunk_first
            take = lines[offset : offset + remaining]
            if not take:
                break
            rows.extend(take)
            remaining -= len(take)
            pos += len(take)
        return rows

    # ------------------------------------------------------------ internals

    def _locate_row(self, row: int) -> tuple[int, int] | None:
        """Locate the chunk holding *row* as ``(index, first row of chunk)``.

        Advances the boundary scan on demand; returns ``None`` when *row*
        lies at or past the end of the file.
        """
        with self._lock:
            while not self._scan_complete and self.total_lines <= row:
                self._advance_boundary_locked()
            if not self.chunk_start_rows or row >= self.total_lines:
                return None
            index = max(0, bisect_right(self.chunk_start_rows, row) - 1)
            return index, self.chunk_start_rows[index]

    def _read_chunk_lines(self, index: int) -> list[str]:
        """Return the rows of chunk *index*, filling the LRU chunk cache."""
        cached = self._cache.get(index)
        if cached is not None:
            self._cache_order.remove(index)
            self._cache_order.append(index)
            return cached
        with self._lock:
            start = self._chunk_offsets[index - 1] if index else self._bom_offset
            end = self._chunk_offsets[index]
        with self.path.open("rb") as handle:
            handle.seek(start)
            data = handle.read(end - start)
        rows = _split_rows(self._decode_bytes(data), is_last=end >= self.total_bytes)
        self._cache[index] = rows
        self._cache_order.append(index)
        while len(self._cache_order) > MAX_CACHED_CHUNKS:
            evicted = self._cache_order.popleft()
            self._cache.pop(evicted, None)
        return rows

    def _advance_boundary_locked(self) -> None:
        """Scan and register the next chunk boundary (lock held)."""
        start = self._chunk_offsets[-1] if self._chunk_offsets else self._bom_offset
        data = self._read_raw_chunk(start)
        end = start + len(data)
        if end <= start:
            # The file shrank below the scanned prefix (external
            # truncation): reading returns nothing new, so marking the scan
            # complete is the only way to avoid a no-progress spin that
            # would also grow the boundary index without bound.
            self._scan_complete = True
            return
        rows = _split_rows(self._decode_bytes(data), is_last=end >= self.total_bytes)
        self.chunk_start_rows.append(self.total_lines)
        self.total_lines += len(rows)
        self.scanned_chunks += 1
        self._chunk_offsets.append(end)
        if end >= self.total_bytes:
            self._scan_complete = True

    def _read_raw_chunk(self, start: int) -> bytes:
        """Read up to one chunk of raw bytes from *start*.

        When the read stops short of both a newline and the end of the file,
        it is extended through the next newline so chunk boundaries stay row
        boundaries (a line longer than the chunk size forms an oversized
        chunk).
        """
        with self.path.open("rb") as handle:
            handle.seek(start)
            data = handle.read(self._chunk_size)
            if data and not data.endswith(b"\n") and start + len(data) < self.total_bytes:
                data += handle.readline()
        return data

    def _read_probe(self) -> bytes:
        """Return the file head used for the encoding probe and CR guard."""
        with self.path.open("rb") as handle:
            return handle.read(_PROBE_BYTES)

    def _decode_bytes(self, data: bytes) -> str:
        """Decode one chunk's bytes with the probed file encoding."""
        encoding = "utf-8" if self.encoding == "utf-8-sig" else self.encoding
        return data.decode(encoding, errors="replace")


class ChunkedBinaryFile:
    """Block-cached random-access reader over a binary file.

    Reads go through an LRU cache of *block_size* byte blocks; dirty byte
    edits recorded via :meth:`apply_edit` are applied on top of the cached
    content at read time, so unflushed hex-view edits stay visible without
    rewriting the file.
    """

    def __init__(
        self,
        path: Path,
        size: int,
        mtime: float,
        block_size: int = HEX_BLOCK_SIZE,
    ) -> None:
        self.path: Path = path
        self.size: int = size
        self.mtime: float = mtime
        self._block_size: int = block_size
        self._blocks: dict[int, bytes] = {}
        self._block_order: deque[int] = deque()
        self._blocks_from_disk: int = 0
        self._dirty: dict[int, int] = {}

    def read(self, offset: int, length: int) -> bytes:
        """Return *length* bytes at *offset*, applying dirty edits on top.

        The range must satisfy ``0 <= offset`` and
        ``offset + length <= size``; anything else raises ``ValueError``.
        """
        if offset < 0 or length < 0 or offset + length > self.size:
            raise ValueError(
                f"read range [{offset}, {offset + length}) exceeds file size {self.size}"
            )
        out = bytearray()
        remaining = length
        pos = offset
        while remaining > 0:
            block_index = pos // self._block_size
            block = self._block(block_index)
            within = pos - block_index * self._block_size
            take = min(remaining, self._block_size - within)
            piece = bytearray(block[within : within + take])
            for dirty_offset, byte in self._dirty.items():
                if pos <= dirty_offset < pos + take:
                    piece[dirty_offset - pos] = byte
            out += piece
            pos += take
            remaining -= take
        return bytes(out)

    def apply_edit(self, offset: int, byte: int) -> None:
        """Record a pending byte replacement at *offset*.

        The edit takes effect on subsequent :meth:`read` calls and is
        cleared once the file has been saved (see :meth:`clear_edits`).
        """
        if offset < 0 or offset >= self.size:
            raise ValueError(f"edit offset {offset} outside file size {self.size}")
        self._dirty[offset] = byte

    def dirty_edits(self) -> dict[int, int]:
        """Return a copy of the pending edits as ``offset -> new byte``."""
        return dict(self._dirty)

    def clear_edits(self, offsets: Iterable[int]) -> None:
        """Forget the pending edits at *offsets* (after a successful save).

        The cached blocks owning the cleared offsets are evicted as well:
        the blocks hold the on-disk bytes as they were before the write,
        and without the eviction a read right after saving would serve the
        stale pre-edit content instead of the freshly written bytes.
        """
        for offset in offsets:
            self._dirty.pop(offset, None)
            block_index = offset // self._block_size
            if self._blocks.pop(block_index, None) is not None:
                self._block_order.remove(block_index)

    def blocks_loaded(self) -> int:
        """Return how many blocks have been fetched from disk (observability)."""
        return self._blocks_from_disk

    def _block(self, index: int) -> bytes:
        """Return block *index* through the LRU block cache."""
        cached = self._blocks.get(index)
        if cached is not None:
            self._block_order.remove(index)
            self._block_order.append(index)
            return cached
        block = self._read_block_from_disk(index)
        self._blocks_from_disk += 1
        self._blocks[index] = block
        self._block_order.append(index)
        while len(self._block_order) > MAX_CACHED_CHUNKS:
            evicted = self._block_order.popleft()
            self._blocks.pop(evicted, None)
        return block

    def _read_block_from_disk(self, index: int) -> bytes:
        """Read block *index* straight from the file (the cache-miss seam)."""
        with self.path.open("rb") as handle:
            handle.seek(index * self._block_size)
            return handle.read(self._block_size)
