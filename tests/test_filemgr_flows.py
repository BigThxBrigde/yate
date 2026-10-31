# pyright: reportPrivateUsage=false
"""Headless tests for the file manager flows (FileManagerFlows).

Drives :class:`yate.flows.filemanager_flows.FileManagerFlows` with
recording stand-ins for the session / workspace / document-flow
collaborators (no Textual app is started).  Covered: the Q1 dirty gate
that refuses a switch, closing the old workspace down to the scratch
buffer, the Q2 first-directory rule for mixed selections, the pure-file
open sequence, the fullscreen exit binding and the no-App-handle rule.
"""

from __future__ import annotations

from pathlib import Path
from typing import cast

from yate.config import YateConfig
from yate.editor_view.commandline import PromptBar
from yate.editor_view.explorer import ExplorerTree
from yate.editor_view.filemgr import FileManagerScreen
from yate.flows import SpawnFn
from yate.flows.document_flows import DocumentFlows
from yate.flows.filemanager_flows import FileManagerFlows
from yate.services.workspace import Workspace
from yate.session import EditorSession


class _StubDoc:
    """Session-document stand-in: dirty flag plus path (or ``None``)."""

    def __init__(self, path: Path | None, *, modified: bool = False) -> None:
        self.path = path
        self.modified = modified


class _StubSession:
    """EditorSession stand-in: tab list plus a real-semantics close_active.

    ``close_active`` mirrors the session contract: it pops the active tab
    and appends a fresh pathless scratch buffer when the last tab closes.
    """

    def __init__(self, docs: list[_StubDoc]) -> None:
        self.docs = docs
        self.index = 0
        self.close_calls = 0

    def close_active(self) -> tuple[_StubDoc, _StubDoc]:
        """Pop the active tab; keep the session non-empty (scratch fallback)."""
        self.close_calls += 1
        closed = self.docs.pop(self.index)
        if not self.docs:
            self.docs.append(_StubDoc(None))
        self.index = 0
        return closed, self.docs[self.index]


class _StubDocuments:
    """DocumentFlows stand-in: records every open_path target in order."""

    def __init__(self) -> None:
        self.open_paths: list[Path] = []

    def open_path(self, path: Path) -> None:
        self.open_paths.append(path)


class _StubWorkspace:
    """Workspace stand-in: root plus an invalidate counter (cache drops)."""

    def __init__(self) -> None:
        self.root: Path | None = None
        self.invalidated = 0

    def invalidate(self) -> None:
        self.invalidated += 1


class _PromptStub:
    """Prompt-bar stand-in: counts idle resets (stale-message hygiene)."""

    def __init__(self) -> None:
        self.idled = 0

    def idle(self) -> None:
        self.idled += 1


class _PushRecorder:
    """Records every pushed screen (overlay pusher stand-in)."""

    def __init__(self) -> None:
        self.screens: list[object] = []

    def __call__(self, screen: object) -> None:
        self.screens.append(screen)


def _record_spawn(*args: object, **kwargs: object) -> object:
    """Spawn-verb stand-in: records nothing, returns like run_worker would."""
    return None


class _FlowsFixture:
    """Bundle of the flows plus every recorder a test may want to inspect."""

    def __init__(self, docs: list[_StubDoc] | None = None) -> None:
        self.session = _StubSession(docs if docs is not None else [_StubDoc(None)])
        self.documents = _StubDocuments()
        self.workspace = _StubWorkspace()
        self.prompt = _PromptStub()
        self.push = _PushRecorder()
        self.pops: list[int] = []
        self.focus_calls: list[int] = []
        self.refresh_calls: list[int] = []
        self.messages: list[tuple[str, str]] = []
        self.mounted_state: dict[str, bool] = {"value": True}
        self.flows = FileManagerFlows(
            spawn=cast(SpawnFn, _record_spawn),
            push_screen=self.push,
            pop_screen=lambda: self.pops.append(1),
            session=cast(EditorSession, self.session),
            workspace=cast(Workspace, self.workspace),
            explorer_tree=cast(ExplorerTree, object()),
            documents=cast(DocumentFlows, self.documents),
            prompt_bar=cast(PromptBar, self.prompt),
            message=lambda text, kind: self.messages.append((text, kind)),
            report=lambda text, kind: self.messages.append((text, kind)),
            refresh_ui=lambda: self.refresh_calls.append(1),
            mounted=lambda: self.mounted_state["value"],
            focus_editor=lambda: self.focus_calls.append(1),
            config=YateConfig(),
        )


def test_open_selected_single_file_switches_root_and_opens(tmp_path: Path) -> None:
    """A single file switches the workspace to its parent, then opens it."""
    folder = tmp_path / "sub"
    folder.mkdir()
    file = folder / "a.txt"
    file.write_text("x", encoding="utf-8")
    fx = _FlowsFixture()

    fx.flows._open_selected([file])

    assert fx.documents.open_paths == [folder, file]
    assert fx.focus_calls == [1]


def test_open_selected_collection_pure_files_opens_all(tmp_path: Path) -> None:
    """A pure file set opens every file in order, first one re-activated."""
    files: list[Path] = []
    for name in ("a.txt", "b.txt", "c.txt"):
        path = tmp_path / name
        path.write_text("x", encoding="utf-8")
        files.append(path)
    fx = _FlowsFixture()

    fx.flows._open_selected(files)

    # parent switch first, then each file in order, then the first file
    # again (re-activation: the selection must land on the first file)
    assert fx.documents.open_paths == [tmp_path, *files, files[0]]
    assert fx.focus_calls == [1]


def test_open_selected_mixed_takes_first_dir_only(tmp_path: Path) -> None:
    """A mixed set enters only the first directory and reports the drop."""
    first = tmp_path / "d1"
    second = tmp_path / "d2"
    first.mkdir()
    second.mkdir()
    stray = tmp_path / "s.txt"
    stray.write_text("x", encoding="utf-8")
    fx = _FlowsFixture()

    fx.flows._open_selected([first, stray, second])

    assert fx.documents.open_paths == [first]
    assert any("first directory" in text for text, _kind in fx.messages)
    assert fx.focus_calls == []


def test_open_selected_blocked_by_dirty_reports_and_keeps(tmp_path: Path) -> None:
    """A dirty buffer refuses the switch: warn, open nothing, close nothing."""
    file = tmp_path / "a.txt"
    file.write_text("x", encoding="utf-8")
    fx = _FlowsFixture(docs=[_StubDoc(file, modified=True)])

    fx.flows._open_selected([file])

    assert fx.documents.open_paths == []
    assert fx.session.close_calls == 0
    assert any(
        "unsaved" in text for text, kind in fx.messages if kind == "warn"
    )
    assert fx.focus_calls == []


def test_switch_workspace_closes_all_tabs_after_clean_check(tmp_path: Path) -> None:
    """A clean switch closes every tab down to the scratch, then invalidates."""
    docs = [_StubDoc(tmp_path / "a.txt"), _StubDoc(tmp_path / "b.txt")]
    fx = _FlowsFixture(docs=docs)

    switched = fx.flows._switch_workspace(tmp_path)

    assert switched is True
    assert fx.session.close_calls == 2
    assert len(fx.session.docs) == 1 and fx.session.docs[0].path is None
    assert fx.workspace.invalidated == 1
    assert fx.documents.open_paths == [tmp_path]


def test_bind_exit_wires_fullscreen_close(tmp_path: Path) -> None:
    """After bind_exit, the fullscreen screen's close callback exits the app."""
    exits: list[int] = []
    fx = _FlowsFixture()
    fx.flows.bind_exit(lambda: exits.append(1))

    fx.flows.open_fullscreen(tmp_path)

    assert len(fx.push.screens) == 1
    screen = fx.push.screens[0]
    assert isinstance(screen, FileManagerScreen)
    screen.close()
    assert exits == [1]


def test_flows_hold_no_app_handle() -> None:
    """The flows module holds no App handle (capability injection rule)."""
    fx = _FlowsFixture()

    assert hasattr(fx.flows, "app") is False
