"""Tests for the tools/release automation CLI.

``_default_branch`` runs against real throwaway git repositories (skipped
when git is unavailable); the ``release`` / ``main`` branch handling runs on
stubbed collaborators, so it needs no git at all.
"""

# pyright: reportPrivateUsage=false

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Optional

import pytest

from tools.release import cli


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True
    )


def _seed_repo(path: Path, *, branch: Optional[str] = None) -> None:
    path.mkdir(parents=True)
    _git(path, "init")
    if branch is not None:
        _git(path, "symbolic-ref", "HEAD", f"refs/heads/{branch}")
    _git(path, "config", "user.name", "tester")
    _git(path, "config", "user.email", "tester@example.com")
    (path / "seed.txt").write_text("seed\n", encoding="utf-8")
    _git(path, "add", "-A")
    _git(path, "commit", "-m", "seed")


# --- _default_branch against real git repositories --------------------------


@pytest.mark.skipif(shutil.which("git") is None, reason="git executable not available")
def test_default_branch_detected_from_origin_head(tmp_path: Path) -> None:
    _seed_repo(tmp_path / "origin", branch="main")
    clone = tmp_path / "clone"
    _git(tmp_path, "clone", str(tmp_path / "origin"), str(clone))
    # git clone always wires refs/remotes/origin/HEAD to the remote's HEAD
    assert cli._default_branch(clone) == "main"


@pytest.mark.skipif(shutil.which("git") is None, reason="git executable not available")
def test_default_branch_is_none_without_origin(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _seed_repo(repo)
    assert cli._default_branch(repo) is None


# --- files_dirty parses ``status --porcelain -z`` verbatim (S27) -------------


@pytest.mark.skipif(shutil.which("git") is None, reason="git executable not available")
def test_files_dirty_returns_verbatim_paths_from_a_real_repo(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    _seed_repo(repo)
    # leading / inner spaces and non-ASCII: the names git would C-quote (and
    # the old line[3:].strip().strip('"') parser would mangle) come back as-is
    names = [" leading.txt", "my file.txt", "中文 文件.txt"]
    for name in names:
        (repo / name).write_text("dirty\n", encoding="utf-8")
    assert sorted(cli.files_dirty(repo, names)) == sorted(names)


def test_files_dirty_consumes_z_rename_records_and_keeps_quotes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Windows cannot host '"' in filenames, so the quote case is fed as
    # canned -z output; rename records put the NEW path first (measured).
    out = (
        ' M my "quoted" file.txt\0'
        "R  new name.txt\0old name.txt\0"
        "?? last.txt\0"
    )
    captured: list[list[str]] = []

    def fake_run_git(args: list[str], *, repo: Path) -> str:
        captured.append(args)
        return out

    monkeypatch.setattr(cli.gitdata, "run_git", fake_run_git)
    dirty = cli.files_dirty(Path("repo"), ["."])
    assert "--porcelain" in captured[0] and "-z" in captured[0]
    assert dirty == ['my "quoted" file.txt', "new name.txt", "last.txt"]


# --- release aborts before pushing when no branch can be determined ---------


def test_release_aborts_without_detectable_branch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "yate").mkdir()
    (tmp_path / "yate" / "__init__.py").write_text(
        '__version__ = "0.1.0"\n', encoding="utf-8"
    )
    pushes: list[str] = []

    def fake_discover() -> Path:
        return tmp_path

    def fake_files_dirty(repo: Path, files: Sequence[str]) -> list[str]:
        return []

    def fake_gate_check(repo: Path) -> int:
        return 0

    def fake_version_tests(repo: Path) -> int:
        return 0

    def fake_default_branch(repo: Path) -> Optional[str]:
        return None

    def fake_git_push(
        repo: Path, refspec: str, *, dry_run: bool = False
    ) -> None:
        pushes.append(refspec)

    monkeypatch.setattr(cli, "discover_repo_root", fake_discover)
    monkeypatch.setattr(cli, "files_dirty", fake_files_dirty)
    monkeypatch.setattr(cli, "gate_check", fake_gate_check)
    monkeypatch.setattr(cli, "run_version_tests", fake_version_tests)
    monkeypatch.setattr(cli, "_default_branch", fake_default_branch)
    monkeypatch.setattr(cli, "git_push", fake_git_push)

    with pytest.raises(
        RuntimeError, match="cannot determine the default branch"
    ):
        cli.release("999.0.0", dry_run=True)
    assert pushes == []


# --- main passes --branch through to release --------------------------------


def test_main_passes_branch_through_to_release(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, Optional[str]]] = []

    def fake_release(
        version: str,
        *,
        dry_run: bool = False,
        no_push: bool = False,
        branch: Optional[str] = None,
    ) -> int:
        calls.append((version, branch))
        return 0

    monkeypatch.setattr(cli, "release", fake_release)
    assert cli.main(["999.0.0", "--branch", "custom"]) == 0
    assert calls == [("999.0.0", "custom")]
    calls.clear()
    assert cli.main(["999.0.0"]) == 0
    assert calls == [("999.0.0", None)]
