# pyright: reportPrivateUsage=false
"""Unit tests for ``yate.editor_view.highlighting`` (token cache + passes).

Drives a minimal host widget (``Widget`` combined with ``HighlightMixin``,
Widget first so the real Textual ``refresh`` / ``set_timer`` / ``run_worker``
implementations win the MRO) inside ``App.run_test()`` -- the mixin needs a
mounted Textual context for its worker scheduling.  Covers the public
``tokens_for`` accessor (tokenize, cache hit, edit resync, out-of-range row,
empty document) and the ``highlight_probe`` snapshot.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import override

from textual.app import App
from textual.pilot import Pilot
from textual.widget import Widget

from conftest import wait_until
from yate.editor_core.buffer import TextBuffer
from yate.editor_core.document import Document
from yate.editor_syntax.engine import (
    tokenize_document_with_states,
    tokenize_line_sync,
)
from yate.editor_view.highlighting import HighlightMixin, HighlightProbe


class _HostWidget(Widget, HighlightMixin):
    """Minimal host: real Textual widget surface + the highlight mixin."""

    def __init__(self, document: Document) -> None:
        super().__init__()
        self._document = document
        self._init_highlight_state()

    @property
    @override
    def doc(self) -> Document:
        return self._document


async def _mounted_host(app: App[None], doc: Document) -> _HostWidget:
    """Mount a host widget for *doc* and return it once the app runs."""
    host = _HostWidget(doc)
    await app.mount(host)
    return host


def test_tokens_for_tokenizes_rows_with_active_spec(tmp_path: Path) -> None:
    async def scenario() -> None:
        doc = Document(tmp_path / "sample.py", TextBuffer('x = "hi"\ny = 2'))
        app: App[None] = App()
        async with app.run_test() as pilot:
            host = await _mounted_host(app, doc)
            await pilot.pause()
            # first lookup schedules the background pass and stays plain
            assert host.tokens_for(0) == []
            assert await wait_until(
                pilot, lambda: host.highlight_probe().tokens is not None
            )
            tokens = host.tokens_for(0)
            assert tokens
            assert any(tok.kind == "string" for tok in tokens)

    asyncio.run(scenario())


def test_tokens_for_second_call_returns_cached_list(tmp_path: Path) -> None:
    async def scenario() -> None:
        doc = Document(tmp_path / "sample.py", TextBuffer('x = "hi"\ny = 2'))
        app: App[None] = App()
        async with app.run_test() as pilot:
            host = await _mounted_host(app, doc)
            await pilot.pause()
            host.tokens_for(0)
            assert await wait_until(
                pilot, lambda: host.highlight_probe().tokens is not None
            )
            first = host.tokens_for(0)
            assert host.tokens_for(0) is first

    asyncio.run(scenario())


def test_tokens_for_after_buffer_edit_rebuilds_row(tmp_path: Path) -> None:
    async def scenario() -> None:
        doc = Document(tmp_path / "sample.py", TextBuffer('x = "hi"\ny = 2'))
        app: App[None] = App()
        async with app.run_test() as pilot:
            host = await _mounted_host(app, doc)
            await pilot.pause()
            host.tokens_for(0)
            assert await wait_until(
                pilot, lambda: host.highlight_probe().tokens is not None
            )
            first = host.tokens_for(0)
            assert first
            # version bump through the public buffer API: the stale tokens
            # hold for one debounce window while the edited row resyncs
            # synchronously (old string literal spans end=8, new one 11)
            doc.buffer.set_text('x = "hello"\ny = 2')
            rebuilt = host.tokens_for(0)
            assert rebuilt is not first
            assert any(
                tok.kind == "string" and tok.end >= 11 for tok in rebuilt
            )

    asyncio.run(scenario())


def test_tokens_for_row_beyond_document_returns_empty(tmp_path: Path) -> None:
    async def scenario() -> None:
        doc = Document(tmp_path / "sample.py", TextBuffer('x = "hi"\ny = 2'))
        app: App[None] = App()
        async with app.run_test() as pilot:
            host = await _mounted_host(app, doc)
            await pilot.pause()
            host.tokens_for(0)
            assert await wait_until(
                pilot, lambda: host.highlight_probe().tokens is not None
            )
            assert host.tokens_for(999) == []

    asyncio.run(scenario())


def test_highlight_probe_reports_state_consistent_with_doc(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        doc = Document(tmp_path / "sample.py", TextBuffer('x = "hi"\ny = 2'))
        app: App[None] = App()
        async with app.run_test() as pilot:
            host = await _mounted_host(app, doc)
            await pilot.pause()
            host.tokens_for(0)
            assert await wait_until(
                pilot, lambda: host.highlight_probe().tokens is not None
            )
            probe = host.highlight_probe()
            assert isinstance(probe, HighlightProbe)
            assert probe.doc is doc
            assert probe.version == doc.buffer.content_version
            assert probe.filetype == doc.filetype
            assert probe.tokens is not None
            assert len(probe.tokens) == doc.buffer.line_count

    asyncio.run(scenario())


def test_tokens_for_empty_document_returns_empty() -> None:
    async def scenario() -> None:
        doc = Document(None, TextBuffer(""))
        app: App[None] = App()
        async with app.run_test() as pilot:
            host = await _mounted_host(app, doc)
            await pilot.pause()
            # nothing tokenized yet: plain row
            assert host.tokens_for(0) == []
            assert await wait_until(
                pilot, lambda: host.highlight_probe().tokens is not None
            )
            # the single empty plaintext row tokenizes to no tokens at all
            assert host.tokens_for(0) == []

    asyncio.run(scenario())


async def _seeded_host(
    app: App[None], pilot: Pilot[None], text: str, tmp_path: Path
) -> tuple[_HostWidget, Document]:
    """Mount a host for a document, wait for the initial worker pass."""
    doc = Document(tmp_path / "sample.py", TextBuffer(text))
    host = await _mounted_host(app, doc)
    host.tokens_for(0)
    assert await wait_until(
        pilot, lambda: host.highlight_probe().tokens is not None
    )
    return host, doc


def _assert_row_synced(
    host: _HostWidget, doc: Document, row: int
) -> None:
    """Assert a sync-resynced row matches a fresh regex single-line pass.

    Note: ``tokenize_line_sync`` and the combined full-document pass emit
    slightly different token streams for some rows (pre-existing engine
    asymmetry, e.g. an ``operator`` token on ``x = "hi"``), so re-tokenized
    rows are compared against the sync backend while reused rows are checked
    for verbatim identity against the worker's full pass.
    """
    tokens = host.highlight_probe().tokens
    assert tokens is not None
    expected, _state = tokenize_line_sync(
        doc.buffer.lines[row], doc.filetype, 0
    )
    assert tokens[row] == expected


def _assert_rows_reused(
    host: _HostWidget, doc: Document, rows: list[int]
) -> None:
    """Assert untouched rows match the full-pass token streams exactly."""
    tokens = host.highlight_probe().tokens
    assert tokens is not None
    full, _states = tokenize_document_with_states(
        doc.buffer.lines, doc.filetype
    )
    for row in rows:
        assert tokens[row] == full[row]


def test_sync_resync_matches_full_diff_after_single_row_edit(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        app: App[None] = App()
        async with app.run_test() as pilot:
            host, doc = await _seeded_host(
                app, pilot, 'x = "hi"\ny = 2\nz = 3', tmp_path
            )
            # narrow single-row edit through the undoable buffer API
            doc.buffer.cursor = (0, 7)
            doc.buffer.insert_text("ello")
            host.tokens_for(0)
            _assert_row_synced(host, doc, 0)
            _assert_rows_reused(host, doc, [1, 2])

    asyncio.run(scenario())


def test_sync_resync_reuses_shifted_rows_after_line_insert(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        app: App[None] = App()
        async with app.run_test() as pilot:
            host, doc = await _seeded_host(
                app, pilot, 'x = "hi"\ny = 2\nz = 3', tmp_path
            )
            before = host.highlight_probe().tokens
            assert before is not None
            old_row1 = before[1]
            doc.buffer.cursor = (1, 0)
            doc.buffer.insert_text("\n")
            host.tokens_for(0)
            # rows whose text shifted but content is unchanged reuse the
            # cached token lists verbatim (shift-aware O(1) reuse)
            after = host.highlight_probe().tokens
            assert after is not None
            assert after[2] is old_row1

    asyncio.run(scenario())


def test_sync_resync_after_undo_matches_full_pass(tmp_path: Path) -> None:
    async def scenario() -> None:
        app: App[None] = App()
        async with app.run_test() as pilot:
            host, doc = await _seeded_host(
                app, pilot, 'x = "hi"\ny = 2', tmp_path
            )
            doc.buffer.cursor = (0, 7)
            doc.buffer.insert_text("ello")
            host.tokens_for(0)
            assert doc.buffer.undo()
            host.tokens_for(0)
            _assert_row_synced(host, doc, 0)
            _assert_rows_reused(host, doc, [1])

    asyncio.run(scenario())


    asyncio.run(scenario())
