"""``:saveas`` flow tests: LSP retarget spawn, failure safety, prompt path.

Covers plan-c of the IKSFS7 fix: a successful ``:saveas`` asks the LSP
manager to rebind the document (``on_document_retargeted`` with the
pre-save path), a failed write schedules nothing, and a plain ``:w``
still uses the ``notify_saved`` path.
"""

from __future__ import annotations

import functools
from pathlib import Path
from typing import Any, cast

import pytest

from yate.config import YateConfig
from yate.editor_core.document import Document
from yate.flows.document_flows import DocumentFlows
from yate.session import EditorSession


class _StubWorkspace:
    """Workspace stand-in: only ``root`` and ``set_root`` are needed."""

    def __init__(self) -> None:
        self.root: Path | None = None

    def set_root(self, path: Path) -> None:
        """Record the new workspace root."""
        self.root = path


class _StubExplorerTree:
    """Explorer stand-in recording refresh calls."""

    def __init__(self) -> None:
        self.refreshed = 0

    def refresh_tree(self) -> None:
        """Count one explorer refresh."""
        self.refreshed += 1


class _StubPromptBar:
    """PromptBar stand-in recording ``activate`` calls."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def activate(self, mode: str, **kwargs: Any) -> None:
        """Record one prompt activation."""
        self.calls.append((mode, kwargs))


class _StubEvents:
    """EventHub stand-in recording ``emit`` calls."""

    def __init__(self) -> None:
        self.emitted: list[tuple[Any, Any]] = []

    def emit(self, event: Any, payload: Any) -> None:
        """Record one emitted event."""
        self.emitted.append((event, payload))


class _StubLsp:
    """LspManager stand-in recording async collaborator calls."""

    def __init__(self) -> None:
        self.retargeted: list[tuple[Document, Path | None]] = []
        self.saved: list[Document] = []

    async def on_document_retargeted(
        self, doc: Document, previous_path: Path | None
    ) -> None:
        """Record one retarget request."""
        self.retargeted.append((doc, previous_path))

    async def notify_saved(self, doc: Document) -> None:
        """Record one saved notification."""
        self.saved.append(doc)


class _Recorder:
    """Spawn + refresh_ui recorders shared by every test."""

    def __init__(self) -> None:
        self.spawned: list[tuple[Any, dict[str, Any]]] = []
        self.refresh_ui_calls = 0

    def spawn(self, work: Any, **kwargs: Any) -> None:
        """Record one spawned worker (the work itself is never run)."""
        self.spawned.append((work, kwargs))

    def refresh_ui(self) -> None:
        """Count one UI repaint."""
        self.refresh_ui_calls += 1


class _Fixture:
    """DocumentFlows wired with a real session and recording stand-ins."""

    def __init__(self) -> None:
        self.session = EditorSession(YateConfig())
        self.session.new_buffer()
        self.workspace = _StubWorkspace()
        self.explorer = _StubExplorerTree()
        self.prompt_bar = _StubPromptBar()
        self.events = _StubEvents()
        self.lsp = _StubLsp()
        self.recorder = _Recorder()
        self.messages: list[tuple[str, str]] = []
        self.flows = DocumentFlows(
            spawn=cast(Any, self.recorder.spawn),
            session=self.session,
            workspace=cast(Any, self.workspace),
            lsp=cast(Any, self.lsp),
            explorer_tree=cast(Any, self.explorer),
            prompt_bar=cast(Any, self.prompt_bar),
            events=cast(Any, self.events),
            message=lambda text, kind: self.messages.append((text, kind)),
            report=lambda text, kind: self.messages.append((text, kind)),
            refresh_ui=self.recorder.refresh_ui,
            mounted=lambda: True,
            reveal_explorer=lambda: None,
            startup_readonly=False,
        )

    def has_message(self, needle: str, kind: str) -> bool:
        """Whether a recorded message contains *needle* with *kind*."""
        return any(
            kind == msg_kind and needle in text
            for text, msg_kind in self.messages
        )


# --- retarget on success ------------------------------------------------------


def test_save_as_on_unnamed_buffer_spawns_retarget_with_none_previous_path(
    tmp_path: Path,
) -> None:
    """A successful ``:saveas`` from an unnamed buffer retargets with None."""
    fx = _Fixture()
    fx.session.doc.buffer.insert_text("print(1)\n")
    dest = tmp_path / "new.py"

    fx.flows.save_as(str(dest))

    assert dest.read_text(encoding="utf-8") == "print(1)\n"
    doc = fx.session.doc
    assert doc.path == dest
    assert doc.name == "new.py"
    assert len(fx.recorder.spawned) == 1
    work, kwargs = fx.recorder.spawned[0]
    assert isinstance(work, functools.partial)
    assert work.func.__name__ == "on_document_retargeted"
    assert work.args == (doc, None)
    assert kwargs["group"] == "lsp-sync"
    assert fx.recorder.refresh_ui_calls == 1
    assert fx.has_message("saved", "ok")


def test_save_as_on_named_buffer_passes_previous_path(tmp_path: Path) -> None:
    """A retarget after renaming a named document passes the old path."""
    fx = _Fixture()
    source = tmp_path / "old.py"
    source.write_text("seed", encoding="utf-8")
    opened = fx.session.open(source)
    assert opened is not None
    renamed = tmp_path / "renamed.py"

    fx.flows.save_as(str(renamed))

    doc = fx.session.doc
    assert len(fx.recorder.spawned) == 1
    work = fx.recorder.spawned[0][0]
    assert work.func.__name__ == "on_document_retargeted"
    assert work.args == (doc, source)
    assert doc.path == renamed
    assert source.read_text(encoding="utf-8") == "seed"
    assert renamed.read_text(encoding="utf-8") == "seed"


def test_save_as_failure_spawns_no_retarget_and_keeps_previous_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed write schedules nothing and keeps the document unnamed."""

    def boom(self: Document, path: Path | str | None = None) -> Path:
        """Simulate a disk failure during save."""
        raise OSError("disk full")

    monkeypatch.setattr(Document, "save", boom)
    fx = _Fixture()
    dest = tmp_path / "never.py"

    fx.flows.save_as(str(dest))

    assert fx.recorder.spawned == []
    assert fx.session.doc.path is None
    assert fx.recorder.refresh_ui_calls == 1
    assert fx.has_message("save failed", "error")


def test_save_as_prompt_path_uses_the_same_retarget_path(
    tmp_path: Path,
) -> None:
    """``save_as(None)`` prompts, and the submit path retargets the same way."""
    fx = _Fixture()
    dest = tmp_path / "prompted.py"

    fx.flows.save_as(None)

    assert len(fx.prompt_bar.calls) == 1
    mode, kwargs = fx.prompt_bar.calls[0]
    assert mode == "save"
    assert "on_submit" in kwargs

    # ``_submit_save_as`` is private but is the plan-pinned submit entry;
    # the cast keeps pyright's reportPrivateUsage quiet in a test context.
    cast(Any, fx.flows)._submit_save_as(str(dest))

    doc = fx.session.doc
    assert len(fx.recorder.spawned) == 1
    work = fx.recorder.spawned[0][0]
    assert work.func.__name__ == "on_document_retargeted"
    assert work.args == (doc, None)
    assert doc.path == dest


def test_write_on_named_buffer_still_spawns_notify_saved(
    tmp_path: Path,
) -> None:
    """A plain ``:w`` keeps using ``notify_saved`` and never retargets."""
    fx = _Fixture()
    source = tmp_path / "plain.py"
    source.write_text("", encoding="utf-8")
    opened = fx.session.open(source)
    assert opened is not None
    fx.session.doc.buffer.insert_text("x")

    fx.flows.save_document()

    assert len(fx.recorder.spawned) == 1
    work = fx.recorder.spawned[0][0]
    assert work.func.__name__ == "notify_saved"
    assert source.read_text(encoding="utf-8") == "x"
    assert fx.recorder.refresh_ui_calls == 1
