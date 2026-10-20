"""``.githooks/pre-commit`` wiring and the ``pymarkdownlnt`` dev dependency.

Two layers:

- Unit level: the hook exists and is LF-only (Git for Windows' sh cannot
  parse CRLF), its staged-file filter keeps ``*.md`` and drops the rest, it
  delegates language routing to ``tools.mdlint --auto-lang`` instead of
  embedding a language table, and the ``dev`` dependency group pins
  ``pymarkdownlnt``.  The routing function itself is owned by the parallel
  plan_a (``tools.mdlint.rules.lang_for_path``); those cases skip until it
  lands and need a re-run afterwards.
- Integration level: a throwaway git repository points ``core.hooksPath`` at
  the hook and runs a real ``git commit``.  A controlled PATH shim (a temp
  directory whose ``python`` / ``python3`` forward to the test interpreter
  with ``PYTHONPATH`` anchored at this repo) keeps the hook away from any
  global ``python``.  Covered: a fixable violation is fixed and re-staged by
  the hook, a clean file passes untouched, an unfixable violation blocks the
  commit, and a missing interpreter degrades to a warning plus ``exit 0``.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import cast

import pytest

from tools.mdlint.rules import lang_for_path

REPO_ROOT: Path = Path(__file__).resolve().parent.parent
HOOK_PATH: Path = REPO_ROOT / ".githooks" / "pre-commit"
PYPROJECT_PATH: Path = REPO_ROOT / "pyproject.toml"

GIT_EXE: str | None = shutil.which("git")
BASH_EXE: str | None = shutil.which("bash")

requires_git = pytest.mark.skipif(GIT_EXE is None, reason="git is not on PATH")

#: Markdown with an auto-fixable pair of violations (trailing spaces, missing
#: final newline) -- the hook's fix pass must re-stage a normalized version.
#: Trailing spaces normalize to the MD009-allowed hard-break count (2), so the
#: guaranteed observable is the restored final newline plus preserved text.
_DIRTY_CONTENT = "# Dirty Doc\n\nTrailing spaces here.   \n\nMore text."
#: Fully compliant Markdown: the hook must leave it byte-for-byte alone.
_CLEAN_CONTENT = "# Clean Doc\n\nNothing to fix here.\n"
#: Two top-level headings trip the single-H1 rule, which has no auto-fix:
#: the hook's check pass must block the commit.
_BLOCKED_CONTENT = "# First Heading\n\nText.\n\n# Second Heading\n"


# --- hook file + dependency wiring ------------------------------------------


def test_githook_file_exists_and_executable() -> None:
    raw = HOOK_PATH.read_bytes()
    assert raw.startswith(b"#!/usr/bin/env bash")
    assert b"\r" not in raw, "CRLF line endings break Git for Windows' sh"


def test_githook_filters_staged_md_files_only() -> None:
    """Staged paths are read NUL-separated and filtered down to ``*.md``."""
    script = HOOK_PATH.read_text(encoding="utf-8")
    assert "--diff-filter=ACM" in script
    assert "--name-only -z" in script, "quoted/escaped paths break non-ASCII names"
    assert 'read -r -d \'\'' in script
    assert "*.md)" in script, "the filter must drop everything that is not Markdown"


def test_githook_delegates_language_routing_to_mdlint() -> None:
    script = HOOK_PATH.read_text(encoding="utf-8")
    assert "--auto-lang" in script
    assert "--lang " not in script
    assert "*.zh.md" not in script, "the hook must not embed a language table"


def test_githook_warns_instead_of_blocking_when_linting_fails() -> None:
    """A file the linter cannot process warns; only violations block."""
    script = HOOK_PATH.read_text(encoding="utf-8")
    assert "could not lint" in script
    assert "has remaining violations" in script
    assert "CODE=$?" in script, "the hook must branch on the check exit code"
    assert "--list-rules" in script, "the hook must probe the backend up front"


def test_pyproject_has_pymarkdownlnt_dep() -> None:
    with PYPROJECT_PATH.open("rb") as stream:
        raw = tomllib.load(stream)
    project = cast("dict[str, object]", raw["project"])
    optional = cast("dict[str, object]", project["optional-dependencies"])
    dev = cast("list[object]", optional["dev"])
    assert "pymarkdownlnt>=0.9.41,<1.0" in dev


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("guide.zh.md", "zh"),
        ("guide.en.md", "en"),
        (".trae/documents/mdlint-plan.md", "zh"),
        ("README.md", "en"),
    ],
)
def test_lang_for_path_routes(path: str, expected: str) -> None:
    assert lang_for_path(path) == expected


# --- integration helpers ------------------------------------------------------


def _git(
    repo: Path, *args: str, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    assert GIT_EXE is not None
    return subprocess.run(
        [GIT_EXE, *args],
        cwd=repo,
        env=env,
        capture_output=True,
        encoding="utf-8",
        check=False,
    )


def _git_bytes(repo: Path, *args: str) -> bytes:
    """Like :func:`_git` but raw bytes, so line endings stay observable."""
    assert GIT_EXE is not None
    return subprocess.run(
        [GIT_EXE, *args], cwd=repo, capture_output=True, check=False
    ).stdout


def _git_ok(repo: Path, *args: str, env: dict[str, str] | None = None) -> None:
    result = _git(repo, *args, env=env)
    assert result.returncode == 0, (
        f"git {' '.join(args)} failed:\n{result.stdout}{result.stderr}"
    )


def _write_hook(hooks_dir: Path) -> None:
    hooks_dir.mkdir(parents=True)
    target = hooks_dir / "pre-commit"
    target.write_bytes(HOOK_PATH.read_bytes())
    os.chmod(target, 0o755)


def _make_shim(shim_dir: Path, name: str, target_exe: Path, pythonpath: str | None) -> None:
    """A sh script forwarding to *target_exe*, optionally pinning PYTHONPATH."""
    shim_dir.mkdir(parents=True, exist_ok=True)
    lines = ["#!/bin/sh"]
    if pythonpath is not None:
        lines.append(f'PYTHONPATH="{pythonpath}"')
        lines.append("export PYTHONPATH")
    lines.append(f'exec "{target_exe.as_posix()}" "$@"')
    path = shim_dir / name
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    os.chmod(path, 0o755)


def _lint_env(shim_dir: Path) -> dict[str, str]:
    """PATH whose python/python3 are the controlled shim, rest inherited."""
    pythonpath = REPO_ROOT.as_posix()
    _make_shim(shim_dir, "python", Path(sys.executable), pythonpath)
    _make_shim(shim_dir, "python3", Path(sys.executable), pythonpath)
    env = dict(os.environ)
    env["PATH"] = f"{shim_dir}{os.pathsep}{env.get('PATH', '')}"
    return env


def _degraded_env(shim_dir: Path) -> dict[str, str]:
    """PATH that can run git (and grep) but resolves no python interpreter."""
    assert GIT_EXE is not None
    env = dict(os.environ)
    if os.name == "nt":
        git_dir = Path(GIT_EXE).parent
        parts = [str(git_dir)]
        usr_bin = git_dir.parent / "usr" / "bin"
        if usr_bin.is_dir():
            parts.append(str(usr_bin))
        system_root = os.environ.get("SystemRoot")
        if system_root:
            parts.append(str(Path(system_root) / "System32"))
            parts.append(system_root)
        env["PATH"] = os.pathsep.join(parts)
        return env
    assert BASH_EXE is not None, "bash is required to shim the hook's shebang on POSIX"
    grep_exe = shutil.which("grep")
    if grep_exe is None:
        pytest.skip("grep is required to shim the hook's filter on POSIX")
    shim_dir.mkdir(parents=True, exist_ok=True)
    _make_shim(shim_dir, "git", Path(GIT_EXE), None)
    _make_shim(shim_dir, "bash", Path(BASH_EXE), None)
    _make_shim(shim_dir, "grep", Path(grep_exe), None)
    env["PATH"] = str(shim_dir)
    return env


def _init_repo(tmp_path: Path) -> Path:
    """A minimal git repo: seed commit first, then the hook under .githooks."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git_ok(repo, "init")
    _git_ok(repo, "config", "user.name", "mdlint-tests")
    _git_ok(repo, "config", "user.email", "mdlint-tests@example.com")
    _git_ok(repo, "config", "core.autocrlf", "false")
    _git_ok(repo, "config", "commit.gpgsign", "false")
    (repo / "seed.txt").write_bytes(b"seed\n")
    _git_ok(repo, "add", "seed.txt")
    _git_ok(repo, "commit", "-m", "seed")
    _git_ok(repo, "config", "core.hooksPath", ".githooks")
    _write_hook(repo / ".githooks")
    return repo


# --- integration: a real git commit drives the hook ---------------------------


@requires_git
def test_pre_commit_fixes_and_restages_dirty_markdown(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    (repo / "dirty.md").write_bytes(_DIRTY_CONTENT.encode("utf-8"))
    (repo / "clean.md").write_bytes(_CLEAN_CONTENT.encode("utf-8"))
    _git_ok(repo, "add", "dirty.md", "clean.md")

    result = _git(
        repo, "commit", "-m", "add markdown", env=_lint_env(tmp_path / "shim")
    )

    assert result.returncode == 0, f"{result.stdout}{result.stderr}"
    stored = _git_bytes(repo, "show", "HEAD:dirty.md")
    assert b"\r" not in stored, "the fix pass must not normalize LF to CRLF"
    dirty = stored.decode("utf-8")
    assert dirty != _DIRTY_CONTENT, "the fix pass left the staged content untouched"
    assert dirty.endswith("\n"), "missing final newline survived the fix pass"
    assert [line.strip() for line in dirty.splitlines()] == [
        line.strip() for line in _DIRTY_CONTENT.splitlines()
    ]
    clean = _git(repo, "show", "HEAD:clean.md").stdout
    assert clean == _CLEAN_CONTENT
    status = _git(repo, "status", "--porcelain", "--untracked-files=no")
    assert status.stdout == ""


@requires_git
def test_pre_commit_blocks_commit_with_remaining_violations(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    seed_head = _git(repo, "rev-parse", "HEAD").stdout.strip()
    (repo / "blocked.md").write_bytes(_BLOCKED_CONTENT.encode("utf-8"))
    _git_ok(repo, "add", "blocked.md")

    result = _git(
        repo, "commit", "-m", "blocked markdown", env=_lint_env(tmp_path / "shim")
    )

    assert result.returncode != 0
    assert "mdlint" in result.stdout + result.stderr
    assert _git(repo, "rev-parse", "HEAD").stdout.strip() == seed_head


@requires_git
def test_pre_commit_degrades_without_interpreter(tmp_path: Path) -> None:
    """No python on PATH: the hook warns and lets the commit pass."""
    repo = _init_repo(tmp_path)
    (repo / "clean.md").write_bytes(_CLEAN_CONTENT.encode("utf-8"))
    _git_ok(repo, "add", "clean.md")

    result = _git(
        repo, "commit", "-m", "no interpreter", env=_degraded_env(tmp_path / "shim")
    )

    assert result.returncode == 0, f"{result.stdout}{result.stderr}"
    combined = result.stdout + result.stderr
    assert "mdlint" in combined, "the hook's no-interpreter warning is missing"
    assert _git(repo, "show", "HEAD:clean.md").stdout == _CLEAN_CONTENT
