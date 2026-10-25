"""Hex view flow tests: binary opens, toggle guards and the CLI boot flag.

Covers the hex flow wiring: :meth:`OverlayFlows.open_hex_view` /
:meth:`OverlayFlows.toggle_hex_view` (screen push/pop, stat precheck and
source-construction refusals, unsaved-buffer guard), the
:class:`DocumentFlows` callback injection on the binary-open branch
(bound opener vs deferred pending target) and the end-to-end binary
startup target flowing into a
:class:`~yate.editor_view.hexview.HexScreen`.
"""

# tests legitimately poke at flow/screen internals:
# pyright: reportPrivateUsage=false

from __future__ import annotations

import asyncio
import builtins
import os
from pathlib import Path
from typing import Any, cast

import pytest
from textual.screen import Screen

from yate.app import YateApp
from yate.config import YateConfig
from yate.editor_core.chunked import ChunkedBinaryFile
from yate.editor_view.hexview import HexScreen, HexView
from yate.flows.document_flows import DocumentFlows
from yate.flows.overlay_flows import OverlayFlows
from yate.session import EditorSession

_BINARY_BYTES = b"MZ\x90\x00\x01\x02binary!\x00\x00"


class _FakePromptBar:
    """Minimal PromptBar stand-in: OverlayFlows.push idles it."""

    def idle(self) -> None:
        """Accept the overlay idle notification (no-op)."""


class _FakeApp:
    """Screen-stack stand-in for the App verbs OverlayFlows consumes."""

    def __init__(self, *, screen: Screen[None] | None = None) -> None:
        self.screen: Screen[None] | None = screen
        self.pushed: list[object] = []
        self.pops: int = 0

    def push_screen(self, screen: object, callback: object = None) -> None:
        """Record the pushed screen like the real app."""
        self.pushed.append(screen)
        self.screen = cast(Screen[None], screen)

    def pop_screen(self) -> None:
        """Record the pop like the real app."""
        self.pops += 1
        self.screen = None


def _make_flows(
    app: _FakeApp,
    messages: list[tuple[str, str]],
    *,
    mounted: bool = True,
    session: EditorSession | None = None,
) -> OverlayFlows:
    """An OverlayFlows wired to *app* with recorded messages (changelog
    precedent: collaborators untouched on the hex path are stubbed)."""
    return OverlayFlows(
        push_screen=app.push_screen,
        pop_screen=app.pop_screen,
        current_screen=lambda: cast(Screen[None], app.screen),
        config=cast(Any, None),
        keymaps=cast(Any, None),
        commands=cast(Any, None),
        actions=cast(Any, None),
        session=cast(Any, session),
        workspace=cast(Any, None),
        prompt=cast(Any, _FakePromptBar()),
        message=lambda text, kind: messages.append((text, kind)),
        mounted=lambda: mounted,
        open_path=lambda path: None,
        reveal_match=lambda path, row, col: None,
        readonly_notice=lambda: None,
        focus_editor=lambda: None,
        execute_action=lambda name: True,
        run_command=lambda text: None,
        refresh=lambda: None,
    )


def test_open_hex_view_pushes_hex_screen(tmp_path: Path) -> None:
    """A readable binary file pushes a HexScreen carrying its bytes."""
    binary = tmp_path / "thing.bin"
    binary.write_bytes(_BINARY_BYTES)
    app = _FakeApp()
    messages: list[tuple[str, str]] = []
    flows = _make_flows(app, messages)

    flows.open_hex_view(binary)

    assert len(app.pushed) == 1
    screen = app.pushed[0]
    assert isinstance(screen, HexScreen)
    assert screen._source.size == len(_BINARY_BYTES)
    assert screen._source.read(0, len(_BINARY_BYTES)) == _BINARY_BYTES
    assert screen._path == binary
    assert messages == []


def test_open_hex_view_read_only_disables_writer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A read-only file opens for browsing without the writer callback."""
    binary = tmp_path / "ro.bin"
    binary.write_bytes(_BINARY_BYTES)

    def _deny_access(path: object, mode: int) -> bool:
        return False

    monkeypatch.setattr("yate.flows.overlay_flows.os.access", _deny_access)
    app = _FakeApp()
    messages: list[tuple[str, str]] = []
    flows = _make_flows(app, messages)

    flows.open_hex_view(binary)

    assert len(app.pushed) == 1
    screen = app.pushed[0]
    assert isinstance(screen, HexScreen)
    assert screen._write_bytes is None
    assert messages
    assert "file read-only" in messages[0][0]
    assert messages[0][1] == "info"


def test_open_hex_view_read_failure_reports(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A read-probe failure past the stat gate reports ``cannot read``."""

    def boom(self: ChunkedBinaryFile, offset: int, length: int) -> bytes:
        raise OSError("read error")

    binary = tmp_path / "locked.bin"
    binary.write_bytes(_BINARY_BYTES)
    monkeypatch.setattr(ChunkedBinaryFile, "read", boom)
    app = _FakeApp()
    messages: list[tuple[str, str]] = []
    flows = _make_flows(app, messages)

    flows.open_hex_view(binary)

    assert app.pushed == []
    assert messages
    assert messages[0][0].startswith("cannot read")
    assert messages[0][0].startswith("cannot read locked.bin")
    assert messages[0][1] == "warn"


def test_write_hex_bytes_write_failure_reports(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A write failure inside the flow reports ``save failed`` and None.

    The patched ``builtins.open`` is restored by the ``monkeypatch``
    fixture when the test ends.
    """
    binary = tmp_path / "test.bin"
    binary.write_bytes(b"\x00" * 16)
    real_open = builtins.open

    def boom_open(file: Any, mode: str = "r", **kwargs: Any) -> Any:
        if mode == "r+b":
            raise PermissionError("denied")
        return real_open(file, mode, **kwargs)

    monkeypatch.setattr(builtins, "open", boom_open)
    messages: list[tuple[str, str]] = []
    flows = _make_flows(
        _FakeApp(), messages, session=EditorSession(YateConfig())
    )

    result = flows.write_hex_edits(
        binary, {0: 0x41}, binary.stat().st_mtime, 16
    )

    assert result is None
    assert messages
    assert messages[0][0].startswith("save failed")
    assert messages[0][1] == "warn"
    assert binary.read_bytes() == b"\x00" * 16  # untouched


def test_write_hex_edits_coalesces_contiguous_edits(tmp_path: Path) -> None:
    """Contiguous dirty bytes land in one run; distant edits stay per-run."""
    binary = tmp_path / "runs.bin"
    binary.write_bytes(b"\x00" * 128)
    messages: list[tuple[str, str]] = []
    flows = _make_flows(
        _FakeApp(), messages, session=EditorSession(YateConfig())
    )

    result = flows.write_hex_edits(
        binary, {0: 0x41, 1: 0x42, 2: 0x43, 100: 0x44},
        binary.stat().st_mtime, 128,
    )

    assert result is not None
    assert messages == []
    data = binary.read_bytes()
    assert data[0:3] == b"ABC"
    assert data[100] == 0x44
    untouched = bytearray(b"\x00" * 128)
    untouched[0:3] = b"ABC"
    untouched[100] = 0x44
    assert data == bytes(untouched)


def test_open_hex_view_pops_when_already_hex_screen(tmp_path: Path) -> None:
    """Calling open_hex_view while a HexScreen is up pops it (toggle-off)."""
    binary = tmp_path / "thing.bin"
    binary.write_bytes(_BINARY_BYTES)
    top = HexScreen(binary, ChunkedBinaryFile(binary, len(_BINARY_BYTES), 0.0))
    app = _FakeApp(screen=top)
    messages: list[tuple[str, str]] = []
    flows = _make_flows(app, messages)

    flows.open_hex_view(binary)

    assert app.pops == 1
    assert app.pushed == []


def test_open_hex_view_accepts_large_file_without_full_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A huge file opens via the chunked source without reading it in full.

    The stat size is inflated to 100 MB while the tmp file stays a few
    bytes; the O(1) source construction must push the HexScreen with at
    most one block fetched from disk (zero, since nothing renders here).
    """
    big = tmp_path / "big.bin"
    big.write_bytes(b"x" * 8)
    reads: list[int] = []
    original = ChunkedBinaryFile._read_block_from_disk

    def counting(self: ChunkedBinaryFile, index: int) -> bytes:
        reads.append(index)
        return original(self, index)

    monkeypatch.setattr(ChunkedBinaryFile, "_read_block_from_disk", counting)

    class _BigStat:
        st_size = 100 * 1024 * 1024
        st_mtime = 0.0

    def fake_stat(self: Path) -> os.stat_result:
        return cast(os.stat_result, _BigStat())

    # class-level patch: WindowsPath rejects instance attribute assignment
    monkeypatch.setattr(Path, "stat", fake_stat)
    app = _FakeApp()
    messages: list[tuple[str, str]] = []
    flows = _make_flows(app, messages)

    flows.open_hex_view(big)

    assert len(app.pushed) == 1
    assert isinstance(app.pushed[0], HexScreen)
    assert len(reads) <= 1
    assert messages == []  # the old oversize refusal is gone


def test_open_hex_view_stat_precheck_rejects_without_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A stat failure refuses via the precheck; the source never reads."""
    big = tmp_path / "big.bin"
    big.write_bytes(b"x" * 8)

    def boom(self: Path) -> os.stat_result:
        raise OSError("stat error")

    monkeypatch.setattr(Path, "stat", boom)
    reads: list[int] = []
    original = ChunkedBinaryFile._read_block_from_disk

    def counting(self: ChunkedBinaryFile, index: int) -> bytes:
        reads.append(index)
        return original(self, index)

    monkeypatch.setattr(ChunkedBinaryFile, "_read_block_from_disk", counting)
    app = _FakeApp()
    messages: list[tuple[str, str]] = []
    flows = _make_flows(app, messages)

    flows.open_hex_view(big)

    assert app.pushed == []
    assert reads == []  # no block was ever fetched from disk
    assert messages[0][0].startswith("cannot stat big.bin")
    assert messages[0][1] == "warn"


def test_open_hex_view_unreadable_path_reports(tmp_path: Path) -> None:
    """A missing file is refused on the message line, no screen push."""
    app = _FakeApp()
    messages: list[tuple[str, str]] = []
    flows = _make_flows(app, messages)

    flows.open_hex_view(tmp_path / "nope.bin")

    assert app.pushed == []
    assert messages
    # a missing file dies at the stat precheck, before any read happens
    assert messages[0][0].startswith("cannot stat nope.bin")
    assert messages[0][1] == "warn"


def test_toggle_hex_view_opens_for_text(tmp_path: Path) -> None:
    """:hex on a text document pushes a HexScreen for the resolved path."""
    text = tmp_path / "notes.txt"
    text.write_text("hello\n", encoding="utf-8")
    session = EditorSession(YateConfig())
    session.open(text)
    assert session.doc.resolved_path == text
    app = _FakeApp()
    messages: list[tuple[str, str]] = []
    flows = _make_flows(app, messages, session=session)

    flows.toggle_hex_view()

    assert len(app.pushed) == 1
    screen = app.pushed[0]
    assert isinstance(screen, HexScreen)
    assert screen._path == text


def test_toggle_hex_view_closes_when_active() -> None:
    """:hex while the hex screen is up pops it."""
    source = ChunkedBinaryFile(Path("x.bin"), 1, 0.0)
    app = _FakeApp(screen=HexScreen(Path("x.bin"), source))
    messages: list[tuple[str, str]] = []
    flows = _make_flows(app, messages, session=EditorSession(YateConfig()))

    flows.toggle_hex_view()

    assert app.pops == 1
    assert app.pushed == []


def test_toggle_hex_view_unsaved_buffer_warns() -> None:
    """:hex on an unsaved buffer warns and does nothing else."""
    session = EditorSession(YateConfig())
    session.docs.append(
        cast(Any, type("Doc", (), {"resolved_path": None})())
    )
    session.index = 0
    app = _FakeApp()
    messages: list[tuple[str, str]] = []
    flows = _make_flows(app, messages, session=session)

    flows.toggle_hex_view()

    assert app.pushed == []
    assert app.pops == 0
    assert messages == [("cannot hex view an unsaved buffer", "warn")]


def test_toggle_hex_view_empty_session_warns() -> None:
    """:hex on an empty session (no docs) warns and does not crash."""
    session = EditorSession(YateConfig())
    assert session.docs == []
    app = _FakeApp()
    messages: list[tuple[str, str]] = []
    flows = _make_flows(app, messages, session=session)

    flows.toggle_hex_view()

    assert app.pushed == []
    assert app.pops == 0
    assert messages == [("no document open", "warn")]


# --- DocumentFlows callback injection ----------------------------------------


def _no_spawn(*args: object, **kwargs: object) -> None:
    """Spawn stand-in: the binary-open branch never spawns work."""


def _make_doc_flows(
    session: EditorSession,
    messages: list[tuple[str, str]],
    *,
    open_hex_view: Any = None,
) -> DocumentFlows:
    """A DocumentFlows wired for the binary-open branch only."""
    return DocumentFlows(
        spawn=cast(Any, _no_spawn),
        session=session,
        workspace=cast(Any, None),
        lsp=cast(Any, None),
        explorer_tree=cast(Any, None),
        prompt_bar=cast(Any, None),
        events=cast(Any, None),
        message=lambda text, kind: messages.append((text, kind)),
        report=lambda text, kind: messages.append((text, kind)),
        refresh_ui=lambda: None,
        mounted=lambda: True,
        reveal_explorer=lambda: None,
        startup_readonly=False,
        open_hex_view=open_hex_view,
    )


def test_binary_open_pushes_hex_screen(tmp_path: Path) -> None:
    """A binary open with a bound opener forwards the path to it."""
    binary = tmp_path / "thing.bin"
    binary.write_bytes(_BINARY_BYTES)
    session = EditorSession(YateConfig())
    opened: list[Path] = []
    messages: list[tuple[str, str]] = []
    flows = _make_doc_flows(
        session, messages, open_hex_view=opened.append
    )

    flows.open_document(binary)

    assert opened == [binary]
    # the old "not a text file" report is gone: the hex handoff replaces it
    assert messages == []


def test_binary_open_without_opener_defers(tmp_path: Path) -> None:
    """Without a bound opener the binary target is parked as pending."""
    binary = tmp_path / "thing.bin"
    binary.write_bytes(_BINARY_BYTES)
    session = EditorSession(YateConfig())
    messages: list[tuple[str, str]] = []
    flows = _make_doc_flows(session, messages)

    flows.open_document(binary)
    assert flows._pending_hex_path == binary

    # take_pending_hex consumes the pending target exactly once
    assert flows.take_pending_hex() == binary
    assert flows.take_pending_hex() is None


def test_binary_open_async_pushes_hex_screen(tmp_path: Path) -> None:
    """An async binary open with a bound opener forwards the path to it."""
    binary = tmp_path / "thing.bin"
    binary.write_bytes(_BINARY_BYTES)
    session = EditorSession(YateConfig())
    opened: list[Path] = []
    messages: list[tuple[str, str]] = []
    flows = _make_doc_flows(
        session, messages, open_hex_view=opened.append
    )

    async def scenario() -> bool:
        return await flows.open_path_async(binary)

    result = asyncio.run(scenario())

    assert opened == [binary]
    assert messages == []
    assert result is False  # hex handoff reports "not a document" to callers


# --- end-to-end: binary startup target ---------------------------------------


def test_startup_binary_open_flows_to_hex_screen(tmp_path: Path) -> None:
    """A binary startup target defers and opens the hex screen post-mount."""

    async def scenario() -> None:
        binary = tmp_path / "firmware.bin"
        binary.write_bytes(_BINARY_BYTES)
        app = YateApp(target=binary)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            await pilot.pause()
            assert isinstance(app.screen, HexScreen)
            view = app.screen.query_one(HexView)
            line = view.render_line(0).text
            assert line.startswith("00000000: 4d5a900001026269")

    asyncio.run(scenario())
