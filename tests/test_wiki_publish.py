"""Regression tests for the wiki publisher's "nothing to commit" probe (m18).

``tests/test_pack_wiki.py`` owns the general wiki coverage; this module pins
review finding m18 only: a clean worktree is detected via
``git status --porcelain`` (locale independent), never by matching the
English commit-output text.
"""

# run_git is patched through the documented facade seam (see publish.py's
# module docstring).
# pyright: reportPrivateUsage=false

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from tools.pack import wiki


def _rc(
    args: tuple[str, ...], code: int, out: str = "", err: str = ""
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args, code, out, err)


def test_push_wiki_clean_tree_skips_commit_and_succeeds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """An empty porcelain status means "nothing to commit" -- whatever locale."""
    calls: list[tuple[str, ...]] = []

    def fake_git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        if args[:1] == ("status",):
            return _rc(args, 0, "", "")
        return _rc(args, 0)

    monkeypatch.setattr(wiki, "run_git", fake_git)

    assert wiki.push_wiki(tmp_path, github_url="") == 0

    assert ("add", "-A") in calls
    assert ("status", "--porcelain") in calls
    assert not any(args[:1] == ("commit",) for args in calls)
    assert ("push", "origin", wiki.WIKI_BRANCH) in calls
    assert "nothing to commit" in capsys.readouterr().out


def test_push_wiki_dirty_tree_commit_failure_reports(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A real commit failure on a dirty tree is still reported, not tolerated."""
    calls: list[tuple[str, ...]] = []

    def fake_git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        if args[:1] == ("status",):
            return _rc(args, 0, " M Home.md\n", "")
        if args[:1] == ("commit",):
            # A localized "nothing to commit"-shaped failure must not be
            # matched by text: the dirty porcelain status decides.
            return _rc(args, 1, "", "Rien à valider, arbre de travail propre")
        return _rc(args, 0)

    monkeypatch.setattr(wiki, "run_git", fake_git)

    assert wiki.push_wiki(tmp_path, github_url="") == 1

    assert ("commit", "-m", wiki.COMMIT_MESSAGE) in calls
    assert ("push", "origin", wiki.WIKI_BRANCH) not in calls


def test_push_wiki_status_failure_reports(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failing ``git status`` aborts with the WIKI_GIT_FAILED path."""

    def fake_git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
        if args[:1] == ("status",):
            return _rc(args, 128, "", "fatal: not a git repository")
        return _rc(args, 0)

    monkeypatch.setattr(wiki, "run_git", fake_git)

    assert wiki.push_wiki(tmp_path, github_url="") == 1


def test_push_wiki_uses_porcelain_before_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """On a dirty tree the porcelain probe runs before the commit (call order)."""
    calls: list[tuple[str, ...]] = []

    def fake_git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        out = " M Home.md\n" if args[:1] == ("status",) else "x\n"
        return _rc(args, 0, out, "")

    monkeypatch.setattr(wiki, "run_git", fake_git)
    wiki.push_wiki(tmp_path, github_url="")

    assert ("status", "--porcelain") in calls
    assert ("commit", "-m", wiki.COMMIT_MESSAGE) in calls
    assert calls.index(("status", "--porcelain")) < calls.index(
        ("commit", "-m", wiki.COMMIT_MESSAGE)
    )
