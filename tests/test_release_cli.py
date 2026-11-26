"""Regression tests for the release rollback exception coverage (review M4).

``tests/test_release_tool.py`` owns the general release CLI coverage; this
module pins the M4 fix only: a mid-run failure that is *not* a
``RuntimeError`` (``OSError`` from the changelog write, or ``Ctrl+C`` /
``KeyboardInterrupt``) must trigger the same rollback as a git failure
instead of escaping with the bumped version committed.
"""

# _CHANGELOG_FILES and _stub-style collaborators are module-private but are
# the pipeline contract under test (same convention tests/test_release_tool.py
# uses).
# pyright: reportPrivateUsage=false

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest
from tools.release import cli


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _seed_release_repo(path: Path, *, branch: str | None = None) -> None:
    """A committed repo whose ``yate/__init__.py`` carries a version line."""
    path.mkdir(parents=True)
    _git(path, "init")
    if branch is not None:
        _git(path, "symbolic-ref", "HEAD", f"refs/heads/{branch}")
    _git(path, "config", "user.name", "tester")
    _git(path, "config", "user.email", "tester@example.com")
    pkg = path / "yate"
    pkg.mkdir()
    (pkg / "__init__.py").write_text('__version__ = "0.1.0"\n', encoding="utf-8")
    _git(path, "add", "-A")
    _git(path, "commit", "-m", "seed")


def _seed_origin_and_clone(tmp_path: Path) -> Path:
    """Bare ``origin`` plus an up-to-date ``master`` clone; returns the clone."""
    seed = tmp_path / "seed"
    _seed_release_repo(seed, branch="master")
    _git(tmp_path, "clone", "--bare", str(seed), str(tmp_path / "origin"))
    work = tmp_path / "work"
    _git(tmp_path, "clone", str(tmp_path / "origin"), str(work))
    _git(work, "config", "user.name", "tester")
    _git(work, "config", "user.email", "tester@example.com")
    return work


def _commit_count(repo: Path) -> int:
    return int(cli.gitdata.run_git(["rev-list", "--count", "HEAD"], repo=repo))


def _tag_names(repo: Path) -> list[str]:
    return cli.gitdata.run_git(["tag", "--list"], repo=repo).split()


def _point_release_at(monkeypatch: pytest.MonkeyPatch, repo: Path) -> None:
    """Make ``discover_repo_root`` return the throwaway repo under test."""
    monkeypatch.setattr(cli, "discover_repo_root", lambda: repo)


def _stub_pipeline(
    monkeypatch: pytest.MonkeyPatch,
    failure: OSError | KeyboardInterrupt,
) -> None:
    """Changelog stub that writes the files and then raises *failure*.

    The write happens before the raise so the rollback's byte-exact restore
    of created files is exercised for real; the two gates would pass if the
    pipeline ever got there.
    """

    def fake_generate_changelog(repo: Path, *, dry_run: bool = False) -> None:
        if dry_run:
            return
        for rel in cli._CHANGELOG_FILES:
            path = repo / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"changelog stub: {rel}\n", encoding="utf-8")
        raise failure

    monkeypatch.setattr(cli, "generate_changelog", fake_generate_changelog)
    monkeypatch.setattr(cli, "gate_check", lambda repo: 0)
    monkeypatch.setattr(cli, "run_version_tests", lambda repo: 0)


@pytest.mark.skipif(shutil.which("git") is None, reason="git executable not available")
@pytest.mark.parametrize(
    "failure",
    [
        OSError("disk full during changelog write"),
        KeyboardInterrupt(),
    ],
    ids=["oserror", "keyboard-interrupt"],
)
def test_release_rolls_back_on_non_runtime_error_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    failure: OSError | KeyboardInterrupt,
) -> None:
    """An OSError / KeyboardInterrupt mid-run rolls the release back (M4)."""
    work = _seed_origin_and_clone(tmp_path)
    _stub_pipeline(monkeypatch, failure)
    _point_release_at(monkeypatch, work)
    commits_before = _commit_count(work)

    assert cli.release("999.0.0", branch="master") == 1

    err = capsys.readouterr().err
    assert "rolled back" in err
    assert _tag_names(work) == []
    assert _commit_count(work) == commits_before
    # The version file is restored byte-for-byte and the created changelog
    # files are removed again; the worktree is left clean.
    assert '__version__ = "0.1.0"' in (work / "yate" / "__init__.py").read_text(
        encoding="utf-8"
    )
    for rel in cli._CHANGELOG_FILES:
        assert not (work / rel).exists()
    assert cli.gitdata.run_git(["status", "--porcelain"], repo=work) == ""
