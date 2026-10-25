"""Headless tests for the chunked file access helpers (L0 editor_core).

Covers :mod:`yate.editor_core.chunked`: multi-chunk row reads, scan
progression, LRU eviction, CRLF / BOM / CR-only handling, bisect row lookup
and the block-cached binary reader with dirty edits.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest

from yate.editor_core.chunked import (
    MAX_CACHED_CHUNKS,
    ChunkedBinaryFile,
    ChunkedFallback,
    ChunkedTextFile,
)


def _write_bytes(tmp_path: Path, name: str, data: bytes) -> Path:
    """Write *data* under *tmp_path* and return the file path."""
    path = tmp_path / name
    path.write_bytes(data)
    return path


def _sample_lines(count: int) -> list[str]:
    """Deterministic row content: ``line 0`` .. ``line <count - 1>``."""
    return [f"line {i}" for i in range(count)]


def _sample_text(count: int) -> str:
    """The sample rows joined by newlines (no trailing newline)."""
    return "\n".join(_sample_lines(count))


# --- ChunkedTextFile ---------------------------------------------------------


def test_chunked_text_reads_rows_across_chunks(tmp_path: Path) -> None:
    """A multi-chunk read reproduces ``text.split("\\n")`` exactly."""
    text = _sample_text(1000)
    path = _write_bytes(tmp_path, "sample.txt", text.encode("utf-8"))
    chunked = ChunkedTextFile(path, chunk_size=64)
    rows = chunked.read_rows(0, chunked.row_count())
    assert rows == text.split("\n")


def test_chunked_text_scan_progression(tmp_path: Path) -> None:
    """scan_next_batch grows scanned_chunks monotonically to the chunk count."""
    text = _sample_text(1000)
    path = _write_bytes(tmp_path, "sample.txt", text.encode("utf-8"))
    chunked = ChunkedTextFile(path, chunk_size=64)
    seen: list[int] = []
    while chunked.scan_next_batch():
        seen.append(chunked.scanned_chunks)
    seen.append(chunked.scanned_chunks)
    assert seen == sorted(seen)
    assert chunked.scanned_chunks > 1
    assert chunked.total_lines == 1000
    assert chunked.chunk_start_rows[0] == 0


def test_chunked_text_lru_evicts_old_chunks(tmp_path: Path) -> None:
    """Reading more chunks than the cache holds evicts, and re-reads stay right."""
    text = _sample_text(1000)
    path = _write_bytes(tmp_path, "sample.txt", text.encode("utf-8"))
    chunked = ChunkedTextFile(path, chunk_size=64)
    rows = chunked.read_rows(0, chunked.row_count())
    assert rows == text.split("\n")
    cache = cast(Any, chunked)._cache
    assert len(cache) <= MAX_CACHED_CHUNKS
    # The first chunks were evicted by the later ones; re-reading reloads
    # them from disk with correct content.
    assert chunked.read_rows(0, 10) == text.split("\n")[:10]


def test_chunked_text_handles_crlf(tmp_path: Path) -> None:
    """CRLF rows come back without carriage returns, boundaries intact."""
    lines = _sample_lines(200)
    text = "\r\n".join(lines)
    path = _write_bytes(tmp_path, "crlf.txt", text.encode("utf-8"))
    chunked = ChunkedTextFile(path, chunk_size=64)
    rows = chunked.read_rows(0, chunked.row_count())
    assert all("\r" not in row for row in rows)
    assert rows == lines


def test_chunked_text_strips_utf8_bom(tmp_path: Path) -> None:
    """A UTF-8 BOM is skipped: the first row has no U+FEFF."""
    text = _sample_text(50)
    path = _write_bytes(tmp_path, "bom.txt", b"\xef\xbb\xbf" + text.encode("utf-8"))
    chunked = ChunkedTextFile(path, chunk_size=64)
    first = chunked.read_rows(0, 1)
    assert first == ["line 0"]
    assert "\ufeff" not in first[0]
    assert chunked.encoding == "utf-8-sig"


def test_chunked_text_falls_back_on_cr_only(tmp_path: Path) -> None:
    """A CR-only file raises ChunkedFallback at construction."""
    path = _write_bytes(tmp_path, "cr.txt", b"alpha\rbeta\rgamma")
    with pytest.raises(ChunkedFallback):
        ChunkedTextFile(path, chunk_size=64)


def test_chunked_text_chunk_for_row_bisect(tmp_path: Path) -> None:
    """chunk_for_row bisects correctly and clamps out-of-range rows."""
    text = _sample_text(1000)
    path = _write_bytes(tmp_path, "sample.txt", text.encode("utf-8"))
    chunked = ChunkedTextFile(path, chunk_size=64)
    assert chunked.row_count() == 1000
    starts = chunked.chunk_start_rows
    assert chunked.chunk_for_row(0) == 0
    assert chunked.chunk_for_row(-5) == 0
    indices = [chunked.chunk_for_row(row) for row in (0, 1, 250, 500, 999, 1000)]
    assert indices == sorted(indices)
    for row in (250, 500, 999):
        index = chunked.chunk_for_row(row)
        assert starts[index] <= row
        assert index + 1 >= len(starts) or starts[index + 1] > row
    last = len(starts) - 1
    assert chunked.chunk_for_row(1000) == last
    assert chunked.chunk_for_row(5000) == last


def test_chunked_text_partial_final_chunk(tmp_path: Path) -> None:
    """A final chunk without a trailing newline keeps its last row intact."""
    lines = _sample_lines(37)
    text = "\n".join(lines)
    path = _write_bytes(tmp_path, "partial.txt", text.encode("utf-8"))
    chunked = ChunkedTextFile(path, chunk_size=64)
    assert chunked.row_count() == 37
    rows = chunked.read_rows(0, chunked.row_count())
    assert rows == lines
    assert rows[-1] == lines[-1]


# --- ChunkedBinaryFile -------------------------------------------------------


def test_chunked_binary_read_random_offsets(tmp_path: Path) -> None:
    """Random-offset reads across blocks match the original bytes."""
    data = bytes(range(256)) * 4
    path = _write_bytes(tmp_path, "blob.bin", data)
    binary = ChunkedBinaryFile(path, size=len(data), mtime=0.0, block_size=256)
    for offset, length in (
        (0, 1),
        (0, 1024),
        (100, 300),
        (255, 10),
        (512, 512),
        (767, 257),
        (1023, 1),
    ):
        assert binary.read(offset, length) == data[offset : offset + length]


def test_chunked_binary_dirty_edits_applied_on_read(tmp_path: Path) -> None:
    """Dirty byte edits are reflected in reads and reported by dirty_edits."""
    data = bytes(range(256)) * 4
    path = _write_bytes(tmp_path, "blob.bin", data)
    binary = ChunkedBinaryFile(path, size=len(data), mtime=0.0, block_size=256)
    binary.apply_edit(5, 0xFF)
    binary.apply_edit(300, 0x00)
    assert binary.dirty_edits() == {5: 0xFF, 300: 0x00}
    assert binary.read(0, 16) == data[:5] + b"\xff" + data[6:16]
    assert binary.read(295, 10) == data[295:300] + b"\x00" + data[301:305]


def test_chunked_binary_block_cache_limits_reads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A repeated read of the same region hits the cache: zero disk reads."""
    data = bytes(range(256)) * 4
    path = _write_bytes(tmp_path, "blob.bin", data)
    binary = ChunkedBinaryFile(path, size=len(data), mtime=0.0, block_size=256)
    original = cast(Any, binary)._read_block_from_disk
    calls: list[int] = []

    def counting(index: int) -> bytes:
        calls.append(index)
        return original(index)

    monkeypatch.setattr(binary, "_read_block_from_disk", counting)
    first = binary.read(100, 400)
    second = binary.read(100, 400)
    assert first == data[100:500]
    assert second == first
    # Blocks 0 and 1 were loaded once each; the second read was all hits.
    assert len(calls) == 2


def test_chunked_binary_out_of_range_raises(tmp_path: Path) -> None:
    """Reading past the end of the file raises ValueError."""
    data = bytes(range(256)) * 4
    path = _write_bytes(tmp_path, "blob.bin", data)
    binary = ChunkedBinaryFile(path, size=len(data), mtime=0.0, block_size=256)
    with pytest.raises(ValueError):
        binary.read(len(data) + 1, 1)
