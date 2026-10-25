"""Headless tests for chunked documents (buffer locking, fills, promotion).

Covers the plan-b wiring of :mod:`yate.editor_core.chunked` into
:class:`~yate.editor_core.document.Document` /
:class:`~yate.editor_core.buffer.TextBuffer` /
:class:`~yate.flows.chunked_flows.ChunkedFlows`: locked buffers reject
every user-facing edit, fills progress the watermark without counting
edits, promotion restores a fully editable buffer and the EditorView render
path asks the flows for visible rows.
"""

# tests legitimately poke at widget internals:
# pyright: reportPrivateUsage=false

from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest
from textual.worker import Worker

from yate.app import YateApp
from yate.editor_core.buffer import TextBuffer
from yate.editor_core.chunked import ChunkedFallback, ChunkedTextFile
from yate.editor_core.document import Document
from yate.flows.chunked_flows import ChunkedFlows


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def _lines(count: int) -> str:
    return "\n".join(f"line {i}" for i in range(count))


def _run_inline(fn: Callable[..., object]) -> object:
    """Drive a spawned callable inline (awaiting an async worker body)."""
    result = fn()
    if asyncio.iscoroutine(result):
        asyncio.run(result)
    return result


def _stub_flows(doc: Document) -> ChunkedFlows:
    """A ChunkedFlows wired to inert stubs (the scan worker runs inline)."""

    def _spawn(fn: Callable[..., object], **kwargs: object) -> object:
        return _run_inline(fn)

    return ChunkedFlows(
        ensure_view_refresh=lambda: None,
        message=lambda text, kind="info": None,
        spawn=cast(Callable[..., Worker[object]], _spawn),
        active_doc=lambda: doc,
        mounted=lambda: True,
    )


# --- Document.open_chunked / ChunkedFlows ------------------------------------


def test_open_chunked_fills_first_chunk_and_locks(tmp_path: Path) -> None:
    """A chunked document opens locked and its first chunk is filled."""
    path = _write(tmp_path / "big.txt", _lines(400))
    doc = Document.open_chunked(path, chunk_size=64)
    assert doc.chunked is not None
    assert doc.buffer.locked is True
    _stub_flows(doc).attach(doc)
    assert doc.chunked is not None
    chunked = doc.chunked
    first_chunk_rows = (
        chunked.chunk_start_rows[1]
        if len(chunked.chunk_start_rows) > 1
        else chunked.total_lines
    )
    assert first_chunk_rows > 0
    assert doc.buffer.rows_loaded(0, first_chunk_rows)
    assert not doc.buffer.rows_loaded(first_chunk_rows, 1)
    assert doc.buffer.get_text().split("\n")[0] == "line 0"


def test_fill_lines_progresses_watermark_without_edits(tmp_path: Path) -> None:
    """Chunked fills never count as user edits and advance monotonically."""
    path = _write(tmp_path / "big.txt", _lines(200))
    doc = Document.open_chunked(path, chunk_size=64)
    buf = doc.buffer
    assert buf.content_edits == 0
    edits = buf.content_edits
    for start in range(0, 200, 50):
        assert not buf.rows_loaded(start, 1)
        buf.fill_lines(start, [f"line {i}" for i in range(start, start + 50)])
        assert buf.rows_loaded(start, 50)
    assert buf.content_edits == edits
    assert doc.modified is False
    assert buf.get_text() == _lines(200)


def test_locked_buffer_rejects_all_edits() -> None:
    """Every user-facing mutation on a locked buffer is a silent no-op."""
    buf = TextBuffer("alpha\nbeta\ngamma")
    buf.locked = True
    buf.set_text("nope")
    buf.type_char("x")
    buf.insert_newline()
    buf.delete_lines()
    buf.insert_at_points("nope")
    buf.delete_at_points()
    buf.delete_forward_at_points()
    assert buf.lines == ["alpha", "beta", "gamma"]
    assert buf.cursor == (0, 0)
    assert buf.content_edits == 0


def test_promote_to_full_restores_editing(tmp_path: Path) -> None:
    """Promotion re-reads the file whole and unlocks the buffer."""
    text = _lines(300)
    path = _write(tmp_path / "big.txt", text)
    doc = Document.open_chunked(path, chunk_size=64)
    _stub_flows(doc).attach(doc)
    doc.promote_to_full()
    assert doc.chunked is None
    assert doc.buffer.locked is False
    assert doc.buffer.get_text() == text
    assert doc.modified is False
    doc.buffer.move_line_end()
    doc.buffer.type_char("!")
    assert doc.buffer.lines[0] == "line 0!"
    assert doc.modified is True


def test_promote_to_full_keeps_indentation_options(tmp_path: Path) -> None:
    """The locked buffer's indentation options carry over to the full one."""
    path = _write(tmp_path / "big.txt", _lines(50))
    doc = Document.open_chunked(path, chunk_size=32)
    doc.buffer.tab_width = 2
    doc.buffer.use_spaces = False
    doc.promote_to_full()
    assert doc.buffer.tab_width == 2
    assert doc.buffer.use_spaces is False


def test_save_raises_on_chunked_document(tmp_path: Path) -> None:
    """A chunked document must never reach the writer."""
    path = _write(tmp_path / "big.txt", _lines(50))
    doc = Document.open_chunked(path, chunk_size=32)
    with pytest.raises(RuntimeError):
        doc.save()


def test_open_chunked_fallback_on_cr_only(tmp_path: Path) -> None:
    """CR-only files cannot be chunk-aligned and raise ChunkedFallback."""
    path = tmp_path / "cr.txt"
    path.write_bytes(b"alpha\rbeta\rgamma")
    with pytest.raises(ChunkedFallback):
        Document.open_chunked(path, chunk_size=32)


def test_chunked_flows_ensure_row_fills_requested_chunk(tmp_path: Path) -> None:
    """ensure_row loads the chunk owning the row (watermark jumps to it)."""
    path = _write(tmp_path / "big.txt", _lines(400))
    doc = Document.open_chunked(path, chunk_size=64)
    flows = _stub_flows(doc)
    flows.attach(doc)
    chunked = cast(ChunkedTextFile, doc.chunked)
    last_row = chunked.row_count() - 1
    assert doc.buffer.line_count == chunked.row_count()
    assert not doc.buffer.rows_loaded(last_row, 1)
    flows.ensure_row(doc, last_row)
    assert doc.buffer.rows_loaded(last_row, 1)
    assert doc.buffer.get_text() == _lines(400)
    # already-loaded rows are a cheap no-op
    flows.ensure_row(doc, 0)
    assert doc.buffer.get_text() == _lines(400)


def test_chunked_flows_promote_to_full_messages(tmp_path: Path) -> None:
    """The :fullload handler promotes and reports; plain docs just notice."""
    messages: list[str] = []
    refreshed: list[int] = []

    def _spawn(fn: Callable[..., object], **kwargs: object) -> object:
        return _run_inline(fn)

    plain = Document()
    flows = ChunkedFlows(
        ensure_view_refresh=lambda: refreshed.append(1),
        message=lambda text, kind="info": messages.append(text),
        spawn=cast(Callable[..., Worker[object]], _spawn),
        active_doc=lambda: plain,
        mounted=lambda: True,
    )
    flows.promote_to_full()
    assert messages == ["buffer is fully loaded already"]
    assert refreshed == []

    path = _write(tmp_path / "big.txt", _lines(50))
    doc = Document.open_chunked(path, chunk_size=32)
    flows2 = ChunkedFlows(
        ensure_view_refresh=lambda: refreshed.append(1),
        message=lambda text, kind="info": messages.append(text),
        spawn=cast(Callable[..., Worker[object]], _spawn),
        active_doc=lambda: doc,
        mounted=lambda: True,
    )
    flows2.attach(doc)
    refreshed.clear()
    flows2.promote_to_full()
    assert messages[-1] == "buffer fully loaded"
    assert doc.chunked is None
    assert refreshed == [1]


# --- EditorView render path --------------------------------------------------


def test_editor_view_ensure_row_called_for_visible_rows(tmp_path: Path) -> None:
    """render_line probes ensure_row exactly for the visible buffer rows."""

    async def scenario() -> None:
        target = _write(tmp_path / "notes.txt", _lines(200))
        app = YateApp(target=target)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            view = app.editor.panes.active_view
            assert view is not None
            seen: list[int] = []
            view._ensure_row = seen.append
            height = view.size.height or 20
            for row in range(height):
                view.render_line(row)
            top = view.scroll_offset.y
            assert seen
            assert all(top <= row < top + height for row in seen)

    asyncio.run(scenario())


def test_background_scan_advances_line_count(tmp_path: Path) -> None:
    """The spawned scan worker grows the placeholder rows off-loop."""

    async def scenario() -> None:
        from conftest import wait_until
        from yate.config import LargeFileConfig, YateConfig

        target = _write(tmp_path / "big.log", _lines(80_000))
        config = YateConfig()
        config.large_file = LargeFileConfig(threshold=64)
        app = YateApp(target=target, config=config)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            doc = app.editor.session.doc
            chunked = doc.chunked
            assert chunked is not None
            first_chunk_rows = (
                chunked.chunk_start_rows[1]
                if len(chunked.chunk_start_rows) > 1
                else chunked.total_lines
            )
            # the scan worker must push the placeholder rows past the first
            # chunk (the silent-death bug kept line_count frozen there)
            assert await wait_until(
                pilot,
                lambda: doc.buffer.line_count == chunked.row_count(),
            )
            assert doc.buffer.line_count > first_chunk_rows

    asyncio.run(scenario())
