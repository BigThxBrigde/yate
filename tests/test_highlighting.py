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
from textual.widget import Widget

from conftest import wait_until
from yate.editor_core.buffer import TextBuffer
from yate.editor_core.document import Document
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
