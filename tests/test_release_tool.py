"""Tests for the tools/release automation CLI.

Guard and rollback behaviour runs against real throwaway git repositories
(bare ``origin`` + clones, skipped when git is unavailable); branch
detection and the remaining edge cases run on stubbed collaborators.
"""

# pyright: reportPrivateUsage=false

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest

from tools.release import cli


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True
    )


def _seed_repo(path: Path, *, branch: str | None = None) -> None:
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

    def fake_default_branch(repo: Path) -> str | None:
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
    calls: list[tuple[str, str | None]] = []

    def fake_release(
        version: str,
        *,
        dry_run: bool = False,
        no_push: bool = False,
        branch: str | None = None,
    ) -> int:
        calls.append((version, branch))
        return 0

    monkeypatch.setattr(cli, "release", fake_release)
    assert cli.main(["999.0.0", "--branch", "custom"]) == 0
    assert calls == [("999.0.0", "custom")]
    calls.clear()
    assert cli.main(["999.0.0"]) == 0
    assert calls == [("999.0.0", None)]


# --- pre-flight guards against real repositories -----------------------------


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


def _clone_upstream(tmp_path: Path) -> Path:
    """A second clone of the shared bare origin, configured for commits."""
    upstream = tmp_path / "upstream"
    _git(tmp_path, "clone", str(tmp_path / "origin"), str(upstream))
    _git(upstream, "config", "user.name", "tester")
    _git(upstream, "config", "user.email", "tester@example.com")
    return upstream


def _commit_count(repo: Path) -> int:
    return int(cli.gitdata.run_git(["rev-list", "--count", "HEAD"], repo=repo))


def _tag_names(repo: Path) -> list[str]:
    return cli.gitdata.run_git(["tag", "--list"], repo=repo).split()


def _point_release_at(monkeypatch: pytest.MonkeyPatch, repo: Path) -> None:
    """Make ``discover_repo_root`` return the throwaway repo under test."""
    monkeypatch.setattr(cli, "discover_repo_root", lambda: repo)


@pytest.mark.skipif(shutil.which("git") is None, reason="git executable not available")
def test_release_refuses_on_wrong_branch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    _seed_release_repo(repo, branch="master")
    _git(repo, "checkout", "-b", "dev")
    _point_release_at(monkeypatch, repo)
    before = _commit_count(repo)
    with pytest.raises(RuntimeError, match="checked out on 'dev'"):
        cli.release("999.0.0", branch="master")
    assert _commit_count(repo) == before
    assert _tag_names(repo) == []


@pytest.mark.skipif(shutil.which("git") is None, reason="git executable not available")
def test_release_refuses_when_local_branch_behind_origin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    work = _seed_origin_and_clone(tmp_path)
    upstream = _clone_upstream(tmp_path)
    (upstream / "ahead.txt").write_text("ahead\n", encoding="utf-8")
    _git(upstream, "add", "-A")
    _git(upstream, "commit", "-m", "advance origin")
    _git(upstream, "push", "origin", "master")
    _point_release_at(monkeypatch, work)
    before = _commit_count(work)
    with pytest.raises(RuntimeError, match="behind origin"):
        cli.release("999.0.0", branch="master")
    assert _commit_count(work) == before
    assert _tag_names(work) == []


@pytest.mark.skipif(shutil.which("git") is None, reason="git executable not available")
def test_release_refuses_when_tag_exists_locally(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    work = _seed_origin_and_clone(tmp_path)
    _git(work, "tag", "-a", "v999.0.0", "-m", "pre-existing")
    _point_release_at(monkeypatch, work)
    before = _commit_count(work)
    with pytest.raises(RuntimeError, match="already exists locally"):
        cli.release("999.0.0", branch="master")
    assert _commit_count(work) == before
    assert "v999.0.0" in _tag_names(work)


@pytest.mark.skipif(shutil.which("git") is None, reason="git executable not available")
def test_release_refuses_when_tag_exists_on_origin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    work = _seed_origin_and_clone(tmp_path)
    upstream = _clone_upstream(tmp_path)
    _git(upstream, "tag", "-a", "v999.0.0", "-m", "remote side")
    _git(upstream, "push", "origin", "v999.0.0")
    _point_release_at(monkeypatch, work)
    before = _commit_count(work)
    with pytest.raises(RuntimeError, match="already exists on origin"):
        cli.release("999.0.0", branch="master")
    assert _commit_count(work) == before
    assert _tag_names(work) == []


# --- rollback on mid-run failure against real repositories --------------------


def _stub_pipeline(
    monkeypatch: pytest.MonkeyPatch,
    *,
    gate_rc: int,
    version_test_rc: int,
) -> None:
    """Deterministic changelog/gate stubs for the mutating pipeline.

    ``generate_changelog`` writes the four changelog files (so the rollback
    snapshot-restore of created files is exercised for real) and no-ops on
    dry-runs; the two gates return the configured exit codes.
    """

    def fake_generate_changelog(repo: Path, *, dry_run: bool = False) -> None:
        if dry_run:
            return
        for rel in cli._CHANGELOG_FILES:
            path = repo / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"changelog stub: {rel}\n", encoding="utf-8")

    def fake_gate_check(repo: Path) -> int:
        return gate_rc

    def fake_version_tests(repo: Path) -> int:
        return version_test_rc

    monkeypatch.setattr(cli, "generate_changelog", fake_generate_changelog)
    monkeypatch.setattr(cli, "gate_check", fake_gate_check)
    monkeypatch.setattr(cli, "run_version_tests", fake_version_tests)


@pytest.mark.skipif(shutil.which("git") is None, reason="git executable not available")
def test_release_rolls_back_when_changelog_gate_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    work = _seed_origin_and_clone(tmp_path)
    _stub_pipeline(monkeypatch, gate_rc=1, version_test_rc=0)
    _point_release_at(monkeypatch, work)
    init_before = (work / "yate" / "__init__.py").read_text(encoding="utf-8")
    head_before = cli.gitdata.head_sha(work)
    commits_before = _commit_count(work)

    assert cli.release("999.0.0", branch="master") == 1

    assert "rolled back" in capsys.readouterr().err
    assert _commit_count(work) == commits_before
    assert cli.gitdata.head_sha(work) == head_before
    assert (work / "yate" / "__init__.py").read_text(encoding="utf-8") == init_before
    for rel in cli._CHANGELOG_FILES:
        assert not (work / rel).exists()
    assert _tag_names(work) == []
    assert cli.gitdata.run_git(["status", "--porcelain"], repo=work) == ""


@pytest.mark.skipif(shutil.which("git") is None, reason="git executable not available")
def test_release_rolls_back_when_version_tests_fail(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    work = _seed_origin_and_clone(tmp_path)
    _stub_pipeline(monkeypatch, gate_rc=0, version_test_rc=1)
    _point_release_at(monkeypatch, work)
    init_before = (work / "yate" / "__init__.py").read_text(encoding="utf-8")
    head_before = cli.gitdata.head_sha(work)
    commits_before = _commit_count(work)

    assert cli.release("999.0.0", branch="master") == 1

    assert "rolled back" in capsys.readouterr().err
    assert _commit_count(work) == commits_before
    assert cli.gitdata.head_sha(work) == head_before
    assert (work / "yate" / "__init__.py").read_text(encoding="utf-8") == init_before
    for rel in cli._CHANGELOG_FILES:
        assert not (work / rel).exists()
    assert _tag_names(work) == []
    assert cli.gitdata.run_git(["status", "--porcelain"], repo=work) == ""


@pytest.mark.skipif(shutil.which("git") is None, reason="git executable not available")
def test_release_skips_rollback_after_branch_push(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    work = _seed_origin_and_clone(tmp_path)
    _stub_pipeline(monkeypatch, gate_rc=0, version_test_rc=0)
    _point_release_at(monkeypatch, work)
    pushes: list[str] = []

    def fake_git_push(repo: Path, refspec: str, *, dry_run: bool = False) -> None:
        if refspec == "master":
            pushes.append(refspec)
            return
        raise RuntimeError("network down")

    monkeypatch.setattr(cli, "git_push", fake_git_push)
    commits_before = _commit_count(work)

    assert cli.release("999.0.0", branch="master") == 1

    assert "recover manually" in capsys.readouterr().err
    assert pushes == ["master"]
    assert _commit_count(work) == commits_before + 2
    assert "v999.0.0" in _tag_names(work)
    for rel in cli._CHANGELOG_FILES:
        assert (work / rel).exists()


# --- dry-run performs zero mutation -------------------------------------------


@pytest.mark.skipif(shutil.which("git") is None, reason="git executable not available")
def test_release_dry_run_mutates_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    work = _seed_origin_and_clone(tmp_path)
    _stub_pipeline(monkeypatch, gate_rc=0, version_test_rc=0)
    _point_release_at(monkeypatch, work)
    init_before = (work / "yate" / "__init__.py").read_text(encoding="utf-8")
    head_before = cli.gitdata.head_sha(work)

    assert cli.release("999.0.0", branch="master", dry_run=True) == 0

    assert cli.gitdata.head_sha(work) == head_before
    assert _commit_count(work) == 1
    assert _tag_names(work) == []
    assert (work / "yate" / "__init__.py").read_text(encoding="utf-8") == init_before
    for rel in cli._CHANGELOG_FILES:
        assert not (work / rel).exists()
