# pyright: reportPrivateUsage=false
"""Command-level tests for the ``:cd`` workspace-root switch.

Drives the ``:cd`` registration in :mod:`yate.commands` against a real
:class:`~yate.flows.document_flows.DocumentFlows` wired with recording
stand-ins (no Textual app is started), mirroring the headless pattern of
``tests/test_set_options.py``.  Covered: the root switch with tree
refresh, drive-root acceptance, the non-directory / missing-path
warnings, the bare ``:cd`` report and the directory + drive completer.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import pytest

import yate.commands
from yate.commands import register_commands
from yate.editor_components.explorer import ExplorerTree
from yate.flows.document_flows import DocumentFlows
from yate.registries import CommandRegistry
from yate.services.workspace import Entry, Workspace


class _StubWorkspace:
    """Workspace stand-in: root switching plus injectable drive entries."""

    def __init__(self) -> None:
        self.root: Path | None = None
        self.drives: list[Entry] = []

    def set_root(self, path: Path) -> None:
        """Record one root switch (the explorer-branch contract)."""
        self.root = path

    def list_drives(self) -> list[Entry]:
        """Return the injected drive entries (wave-1 contract stand-in)."""
        return self.drives


class _StubExplorerTree:
    """Explorer-tree stand-in: counts refresh and focus calls."""

    def __init__(self) -> None:
        self.refresh_calls = 0
        self.focus_calls = 0

    def refresh_tree(self) -> None:
        """Record one tree refresh (fired on a root switch)."""
        self.refresh_calls += 1

    def focus(self) -> None:
        """Record one focus handoff (fired on a root switch)."""
        self.focus_calls += 1


class _CdEditor:
    """Editor stand-in exposing the flows, workspace and message line."""

    def __init__(
        self, flows: DocumentFlows, workspace: _StubWorkspace,
        note_sink: Callable[[str, str], None],
    ) -> None:
        self.document_flows = flows
        self.workspace = workspace
        self._note_sink = note_sink

    def message(self, text: str, kind: str = "info") -> None:
        """Forward one message-line output to the fixture recorder."""
        self._note_sink(text, kind)


def _no_worker(*args: object, **kwargs: object) -> None:
    """Spawn stand-in: no background worker is ever started here."""
    return None


class _CdFixture:
    """Bundle of the registry entry plus every recorder a test inspects."""

    def __init__(self, root: Path | None) -> None:
        self.workspace = _StubWorkspace()
        self.workspace.root = root
        self.explorer = _StubExplorerTree()
        self.notes: list[tuple[str, str]] = []
        self.reveals: list[int] = []
        flows = DocumentFlows(
            spawn=cast(Any, _no_worker),
            session=cast(Any, object()),
            workspace=cast(Workspace, self.workspace),
            lsp=cast(Any, object()),
            explorer_tree=cast(ExplorerTree, self.explorer),
            prompt_bar=cast(Any, object()),
            events=cast(Any, object()),
            message=self._message,
            report=self._report,
            refresh_ui=lambda: None,
            mounted=lambda: True,
            reveal_explorer=lambda: self.reveals.append(1),
            startup_readonly=False,
        )
        editor = _CdEditor(flows, self.workspace, self._message)
        registry = CommandRegistry()
        register_commands(registry, cast(Any, editor))
        entry = registry.get("cd")
        assert entry is not None
        self.entry = entry

    def _message(self, text: str, kind: str) -> None:
        """Record one injected message."""
        self.notes.append((text, kind))

    def _report(self, text: str, kind: str) -> None:
        """Record one injected report."""
        self.notes.append((text, kind))

    def has_note(self, needle: str, kind: str) -> bool:
        """Whether a recorded note contains *needle* with *kind*."""
        return any(
            kind == note_kind and needle in text for text, note_kind in self.notes
        )


# --- switch semantics --------------------------------------------------------


def test_cd_switches_root_and_refreshes_tree(tmp_path: Path) -> None:
    """A directory target switches the root and refreshes the explorer."""
    fx = _CdFixture(tmp_path)
    sub = tmp_path / "sub"
    sub.mkdir()

    fx.entry.func(str(sub))

    assert fx.workspace.root == sub
    assert fx.explorer.refresh_calls == 1
    assert fx.explorer.focus_calls == 1
    assert fx.has_note("opened folder", "info")


@pytest.mark.skipif(sys.platform != "win32", reason="drive roots are Windows-only")
def test_cd_accepts_drive_root(tmp_path: Path) -> None:
    """A drive-root argument (``D:\\`` form) switches the root directly."""
    fx = _CdFixture(tmp_path)
    anchor = tmp_path.anchor
    assert anchor

    fx.entry.func(anchor)

    assert fx.workspace.root == Path(anchor)
    assert fx.explorer.refresh_calls == 1


@pytest.mark.skipif(sys.platform != "win32", reason="bare drives are Windows-only")
def test_cd_normalizes_bare_drive_colon(tmp_path: Path) -> None:
    """``:cd D:`` lands on the drive root, not the drive's current directory."""
    fx = _CdFixture(tmp_path)
    anchor = tmp_path.anchor
    assert anchor
    bare = anchor.rstrip("\\/")

    fx.entry.func(bare)

    assert fx.workspace.root == Path(anchor)


def test_cd_strips_surrounding_quotes(tmp_path: Path) -> None:
    """A quoted target (spaces) resolves like the other path commands."""
    fx = _CdFixture(tmp_path)
    sub = tmp_path / "dir with spaces"
    sub.mkdir()

    fx.entry.func(f'"{sub}"')

    assert fx.workspace.root == sub


def test_cd_rejects_file_with_warning(tmp_path: Path) -> None:
    """A file target reports ``not a directory`` and keeps the root."""
    fx = _CdFixture(tmp_path)
    target = tmp_path / "file.txt"
    target.write_text("x", encoding="utf-8")

    fx.entry.func(str(target))

    assert fx.workspace.root == tmp_path
    assert fx.has_note("not a directory", "warn")


def test_cd_rejects_missing_path(tmp_path: Path) -> None:
    """A missing path reports a warning and keeps the root."""
    fx = _CdFixture(tmp_path)

    fx.entry.func(str(tmp_path / "missing"))

    assert fx.workspace.root == tmp_path
    assert fx.has_note("not a directory", "warn")



def test_cd_probe_oserror_degrades_to_warning(
    tmp_path: Path, monkeypatch: Any
) -> None:
    """An ``OSError`` from the directory probe reads as not-a-directory."""
    fx = _CdFixture(tmp_path)

    def _boom(self: object) -> bool:
        raise OSError("probe failed")

    monkeypatch.setattr(Path, "is_dir", _boom)

    fx.entry.func(str(tmp_path))

    assert fx.workspace.root == tmp_path
    assert fx.has_note("not a directory", "warn")


def test_cd_bare_shows_root(tmp_path: Path) -> None:
    """Bare ``:cd`` reports the current root without changing state."""
    fx = _CdFixture(tmp_path)

    fx.entry.func("")

    assert fx.workspace.root == tmp_path
    assert fx.has_note(f"workspace root: {tmp_path}", "info")


def test_cd_bare_with_no_root_reports_none() -> None:
    """Bare ``:cd`` without a workspace root reports ``(none)``."""
    fx = _CdFixture(None)

    fx.entry.func("")

    assert fx.has_note("workspace root: (none)", "info")


def test_cd_relative_resolves_against_root(tmp_path: Path) -> None:
    """A relative target resolves against the workspace root, not cwd."""
    fx = _CdFixture(tmp_path)
    sub = tmp_path / "sub"
    sub.mkdir()

    fx.entry.func("sub")

    assert fx.workspace.root == sub


# --- completion ---------------------------------------------------------------


def test_cd_completer_lists_dirs_and_drives(tmp_path: Path, monkeypatch: Any) -> None:
    """Completer candidates merge root entries with drive roots, no dupes."""
    fx = _CdFixture(tmp_path)
    (tmp_path / "alpha").mkdir()
    (tmp_path / "data").mkdir()
    # the file exists *before* any completion runs, so the dirs-only filter
    # below is actually exercised (a no-op test would never catch a leak)
    (tmp_path / "afile.txt").write_text("x", encoding="utf-8")
    drive = Entry(Path("D:\\"), "D:", True)
    monkeypatch.setattr(fx.workspace, "list_drives", lambda: [drive])
    completer = fx.entry.arg_completer
    assert completer is not None

    empty = completer("")
    partial = completer("d")
    drive_prefix = completer("D:\\")

    assert "alpha/" in empty
    assert "data/" in empty
    assert "D:\\" in empty
    # ``:cd`` is directories-only: bare file names never surface.
    assert "afile.txt" not in empty
    # partial prefixes are filtered the same way
    assert "afile.txt" not in completer("a")
    assert "data/" in partial
    assert "D:\\" in partial
    # A prefix that already *is* a drive root is deduplicated, not offered
    # back as its own candidate.
    assert "D:\\" not in drive_prefix
    for candidates in (empty, partial, drive_prefix):
        assert len(candidates) == len(set(candidates))


def test_cd_completer_rejects_quote_ending_filename(
    tmp_path: Path, monkeypatch: Any
) -> None:
    """A file candidate whose name ends with ``"`` is still filtered out.

    POSIX allows double quotes inside file names, and ``path_matches``
    appends a trailing "/" to *directory* candidates only (on every
    platform), so a ``'foo"'`` candidate -- no trailing slash -- is exactly
    such a file: the sole false-accept surface of the dirs-only filter
    (the mis-typed ``"\""`` literal historically accepted it as a
    directory).  ``path_matches`` is faked at the ``yate.commands``
    namespace (the completer's import site, read as a module global at
    call time) because Windows cannot create a quote-named file at all.
    """
    fx = _CdFixture(tmp_path)

    def _fake_matches(prefix: str, workspace: Workspace) -> list[str]:
        """Stand in for ``path_matches`` with one quote-ending file candidate."""
        return ['foo"']

    monkeypatch.setattr(yate.commands, "path_matches", _fake_matches)
    completer = fx.entry.arg_completer
    assert completer is not None

    candidates = completer("f")

    assert 'foo"' not in candidates
