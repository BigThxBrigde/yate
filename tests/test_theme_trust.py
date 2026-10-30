"""Tests for the workspace-theme trust gate in ``theme_files``.

``theme_files.default_theme_dirs`` resolves the default theme scan dirs:
the workspace ``./themes`` directory auto-loads only in workspaces trusted
via ``:trust`` (mirroring ``./extensions``), while the user-level
``~/.yate/themes`` always loads.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from yate.editor_view import themes
from yate.editor_view.theme_files import default_theme_dirs, load_theme_paths
from yate.services import trust

#: Content of the probe theme file: registers "trust-probe" when executed.
PROBE_THEME = """\
from dataclasses import replace

from yate.editor_view.themes import THEMES

register_theme(replace(THEMES["mocha"], name="trust-probe"))
"""


def _make_workspace(tmp_path: Path) -> Path:
    """Create a temp workspace containing ``themes/probe.py``."""
    ws = tmp_path / "ws"
    (ws / "themes").mkdir(parents=True)
    (ws / "themes" / "probe.py").write_text(PROBE_THEME, encoding="utf-8")
    return ws


@pytest.fixture
def trust_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect the trust store to a per-test file.

    ``trust.TRUST_FILE`` is bound at import time, so tests patch the
    module attribute before any trust decision is made.
    """
    store = tmp_path / "trusted_workspaces"
    monkeypatch.setattr(trust, "TRUST_FILE", store)
    return store


def test_workspace_themes_skipped_when_untrusted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, trust_store: Path
) -> None:
    """An untrusted workspace's ``./themes`` is left out and a skip note
    pointing at ``:trust`` is reported."""
    ws = _make_workspace(tmp_path)
    monkeypatch.chdir(ws)
    errors: list[str] = []
    dirs = default_theme_dirs(errors)
    # Resolved spelling on both sides: a casing/join variant of the same
    # directory must not slip through an exact string comparison (F8).
    assert (ws / "themes").resolve() not in {d.resolve() for d in dirs}
    assert any(
        "themes: skipped untrusted" in e and "restart yate" in e for e in errors
    )


def test_workspace_themes_loaded_when_trusted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, trust_store: Path
) -> None:
    """A trusted workspace's ``./themes`` comes first (later dirs win on
    name collisions) and no skip note is reported."""
    ws = _make_workspace(tmp_path)
    monkeypatch.chdir(ws)
    assert trust.trust_workspace(ws.resolve()) is True
    errors: list[str] = []
    dirs = default_theme_dirs(errors)
    assert dirs[0] == ws / "themes"
    assert errors == []


def test_home_themes_always_loaded_without_trust(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, trust_store: Path
) -> None:
    """The user-level ``~/.yate/themes`` is unconditional: it loads with
    no trust decision and no workspace themes around."""
    monkeypatch.chdir(tmp_path)
    errors: list[str] = []
    dirs = default_theme_dirs(errors)
    assert dirs == [Path.home() / ".yate" / "themes"]
    assert errors == []


def test_no_themes_directory_appends_no_note(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, trust_store: Path
) -> None:
    """A workspace without a ``themes/`` directory produces neither an
    entry nor a note."""
    ws = tmp_path / "plain"
    ws.mkdir()
    monkeypatch.chdir(ws)
    errors: list[str] = []
    dirs = default_theme_dirs(errors)
    assert dirs == [Path.home() / ".yate" / "themes"]
    assert errors == []


def test_default_theme_dirs_feed_load_theme_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, trust_store: Path
) -> None:
    """End to end: in a trusted workspace the probe theme file reached
    through ``default_theme_dirs`` registers "trust-probe"."""
    ws = _make_workspace(tmp_path)
    monkeypatch.chdir(ws)
    # Keep the process-global registry clean: register into a per-test copy.
    monkeypatch.setattr(themes, "THEMES", dict(themes.THEMES))
    assert trust.trust_workspace(ws.resolve()) is True
    errors: list[str] = []
    load_theme_paths(default_theme_dirs(errors), errors)
    assert errors == []
    assert "trust-probe" in themes.available()
