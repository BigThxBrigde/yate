"""Provider convergence tests (quickfix-nav plan d).

Covers the three AC providers publishing into the shared quickfix list:
``:diagnostics`` entries, the find & replace mirror with its T3 jump
closure, and the references dual publish (chooser + quickfix) with the
single ``push_jump`` contract.  Fakes follow the test_lsp_navigation_flows
harness shape; no Textual App is mounted here.
"""

# pyright: reportPrivateUsage=false

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, cast
from unittest.mock import MagicMock

import pytest

from yate.config import YateConfig
from yate.editor_components.find_replace import FindReplaceScreen
from yate.editor_core import Document
from yate.editor_core.project_search import FileMatch, LineMatch
from yate.editor_lsp.client import Diagnostic
from yate.editor_lsp.manager import LspManager
from yate.flows.lsp_navigation_flows import LspNavigationFlows
from yate.flows.lsp_sync import LspSync
from yate.editor_compose import _file_match_entries
from yate.session import EditorSession, QuickFixEntry

import test_lsp_navigation_flows as base
from test_lsp_navigation_flows import (
    _FakeLsp,
    _FakePopup,
    _FakePanes,
    _FakePrompt,
    _FakeView,
    _location,
    _spawn_shim,
    wait_until,
)


# ------------------------------------------------------------- diagnostics


def _diag_session(tmp_path: Path) -> tuple[EditorSession, Document]:
    """A real session whose active document is a real temp file."""
    session = EditorSession(YateConfig())
    session.new_buffer()
    source = tmp_path / "doc.py"
    source.write_text("line0\nline1\n", encoding="utf-8")
    doc = Document.open(source)
    session.docs[session.index] = doc
    return session, doc


def test_diagnostics_publish_entries_including_severity_and_position(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two diagnostics become two quickfix entries; no overlay is pushed."""
    session, doc = _diag_session(tmp_path)
    lsp = LspManager()
    diags = [
        Diagnostic(
            start_row=3, start_col=5, end_row=3, end_col=10,
            severity=1, message="boom", source="ruff",
        ),
        Diagnostic(
            start_row=0, start_col=0, end_row=0, end_col=1,
            severity=2, message="meh", source="",
        ),
    ]
    def _fake_diagnostics(_doc: Document) -> list[Diagnostic]:
        return list(diags)

    monkeypatch.setattr(
        lsp, "diagnostics_for", _fake_diagnostics, raising=False
    )
    pushes: list[object] = []
    calls: list[tuple[str, list[QuickFixEntry], str]] = []
    messages: list[str] = []
    sync = LspSync(
        spawn=cast(Any, MagicMock()),
        lsp=cast(Any, lsp),
        session=session,
        panes=cast(Any, MagicMock()),
        status_bar=cast(Any, MagicMock()),
        prompt=cast(Any, MagicMock()),
        events=cast(Any, MagicMock()),
        message=lambda text, kind: messages.append(text),
        mounted=lambda: True,
        push_overlay=cast(Any, pushes.append),
        set_quickfix=lambda provider, entries, label: calls.append(
            (provider, entries, label)
        ),
    )

    sync.show_diagnostics()

    assert pushes == []
    assert len(calls) == 1
    provider, entries, label = calls[0]
    assert provider == "diagnostics"
    assert label == "diagnostics — 1 error(s), 1 warning(s)"
    assert [e.row for e in entries] == [3, 0]
    assert [e.col for e in entries] == [5, 0]
    assert [e.severity for e in entries] == ["error", "warning"]
    assert [e.detail for e in entries] == ["[ruff]", ""]
    assert [e.label for e in entries] == ["boom", "meh"]
    assert all(e.path == doc.path for e in entries)
    assert messages == []


def test_diagnostics_empty_publishes_empty_set_and_message(
    tmp_path: Path,
) -> None:
    """No diagnostics: an explicit empty set plus the message, no overlay."""
    session, _doc = _diag_session(tmp_path)
    lsp = LspManager()
    pushes: list[object] = []
    calls: list[tuple[str, list[QuickFixEntry], str]] = []
    messages: list[str] = []
    sync = LspSync(
        spawn=cast(Any, MagicMock()),
        lsp=cast(Any, lsp),
        session=session,
        panes=cast(Any, MagicMock()),
        status_bar=cast(Any, MagicMock()),
        prompt=cast(Any, MagicMock()),
        events=cast(Any, MagicMock()),
        message=lambda text, kind: messages.append(text),
        mounted=lambda: True,
        push_overlay=cast(Any, pushes.append),
        set_quickfix=lambda provider, entries, label: calls.append(
            (provider, entries, label)
        ),
    )

    sync.show_diagnostics()

    assert pushes == []
    assert messages == ["no diagnostics"]
    assert calls == [("diagnostics", [], "no diagnostics")]


# ---------------------------------------------------------- project search


def test_project_search_publishes_flat_entries_and_records_jump(
    tmp_path: Path,
) -> None:
    """A two-row FileMatch mirrors flat entries; the jump pushes once."""
    session = EditorSession(YateConfig())
    session.new_buffer()
    target = tmp_path / "hit.py"
    target.write_text("x\n", encoding="utf-8")
    fm = FileMatch(
        path=target,
        matches=[LineMatch(row=3, start=5, end=11), LineMatch(row=7, start=0, end=6)],
        hit_lines={3: "hello needle\r", 7: "needle here"},
    )
    published: list[list[FileMatch]] = []
    screen = FindReplaceScreen(
        cast(Any, MagicMock()),
        session,
        open_path=lambda _path: None,
        reveal=None,
        message=lambda _text, _kind: None,
        readonly_notice=lambda: None,
        refresh=lambda: None,
        on_results=published.append,
    )
    screen._results = [fm]
    screen._flat = [(fm.path, m) for m in fm.matches]

    screen._notify_results()

    assert published == [[fm]]
    entries = _file_match_entries(published[0])
    assert len(entries) == 2
    assert all(e.provider == "search" for e in entries)
    assert [e.row for e in entries] == [3, 7]
    assert [e.col for e in entries] == [5, 0]
    assert [e.label for e in entries] == ["hello needle", "needle here"]
    assert all(e.path == target for e in entries)

    # T3 closure: push_jump lands the origin on the back stack before the
    # reveal fires.
    reveals: list[tuple[Path, int, int]] = []
    back_at_reveal = 0

    def reveal(path: Path, row: int, col: int) -> None:
        nonlocal back_at_reveal
        reveals.append((path, row, col))
        back_at_reveal = len(session.jumps.stacks()[0])

    screen._reveal = reveal
    cast(Any, screen).dismiss = lambda: None
    screen._open_current()

    assert reveals == [(target, 3, 5)]
    assert back_at_reveal == 1


# -------------------------------------------------------------- references


class _RefHarness:
    """LspNavigationFlows wired like base._Harness plus a quickfix recorder."""

    def __init__(self, tmp_path: Path) -> None:
        self.lsp = _FakeLsp()
        self.view = _FakeView()
        self.prompt = _FakePrompt()
        self.session = EditorSession(YateConfig())
        self.session.new_buffer()
        source = tmp_path / "mod.py"
        source.write_text(base._TEXT, encoding="utf-8")
        self.doc = Document.open(source)
        self.session.docs[self.session.index] = self.doc
        self.pushes: list[Any] = []
        self.messages: list[tuple[str, str]] = []
        self.quickfix: list[tuple[str, list[QuickFixEntry], str]] = []
        self.flows = LspNavigationFlows(
            spawn=cast(Any, _spawn_shim),
            lsp=cast(Any, self.lsp),
            session=self.session,
            panes=cast(Any, _FakePanes(self.view)),
            popup=cast(Any, _FakePopup()),
            open_path=self._open_path,
            push_overlay=self.pushes.append,
            message=lambda text, kind: self.messages.append((text, kind)),
            refresh=lambda: None,
            prompt=cast(Any, self.prompt),
            has_modal_screen=lambda: False,
            set_quickfix=lambda provider, entries, label: self.quickfix.append(
                (provider, entries, label)
            ),
        )

    def _open_path(self, path: Path) -> None:
        if self.session.is_open(path) is None:
            self.session.docs.append(Document.open(path))

    def message_texts(self) -> list[str]:
        return [text for text, _kind in self.messages]


def test_references_publish_then_chooser_still_opens(tmp_path: Path) -> None:
    """Two references publish a quickfix batch and open one chooser."""
    h = _RefHarness(tmp_path)
    h.lsp.references = [
        _location(tmp_path, "mod.py", 0, 0),
        _location(tmp_path, "mod.py", 1, 4),
    ]

    async def scenario() -> None:
        h.flows.find_references()
        assert await wait_until(lambda: len(h.pushes) == 1)
        assert len(h.quickfix) == 1
        provider, entries, label = h.quickfix[0]
        assert provider == "references"
        assert label == "references"
        assert [e.row for e in entries] == [0, 1]
        assert [e.col for e in entries] == [0, 4]
        assert all(e.path == tmp_path / "mod.py" for e in entries)
        from yate.editor_components.lsp_chooser import LspChooserScreen

        screen = h.pushes[0]
        assert isinstance(screen, LspChooserScreen)
        assert len(screen.rows) == 2

    asyncio.run(scenario())


def test_references_empty_publishes_empty_and_warns(tmp_path: Path) -> None:
    """No references: an empty quickfix batch plus the explicit message."""
    h = _RefHarness(tmp_path)

    async def scenario() -> None:
        h.flows.find_references()
        assert await wait_until(
            lambda: "No references found" in h.message_texts()
        )
        assert h.pushes == []
        assert h.quickfix == [("references", [], "no references")]

    asyncio.run(scenario())


def test_chooser_jump_records_jump_once(tmp_path: Path) -> None:
    """One _jump_to_row call grows the back stack exactly once."""
    h = _RefHarness(tmp_path)
    from yate.editor_components.lsp_chooser import LspRow

    row = LspRow(
        label="mod.py", detail="line 2", uri=str(tmp_path / "mod.py"),
        row=1, col=2, end_row=1, end_col=5, kind="location",
    )

    h.flows._jump_to_row(row)

    back, _forward = h.session.jumps.stacks()
    assert len(back) == 1
    target = h.session.is_open(tmp_path / "mod.py")
    assert target is not None
    assert target.buffer.cursor == (1, 2)
