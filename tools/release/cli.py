"""Command line interface: ``python -m tools.release <version>``.

One-command release: bump the version (two files), commit the bump,
regenerate the bilingual changelog, commit it, run the changelog gate and
the version tests, then create the annotated tag and push.

All git access goes through :func:`tools.changelog.gitdata.run_git` (the
single git gateway); changelog generation/gating reuses
:func:`tools.changelog.cli.generate` / :func:`tools.changelog.cli.check`.
Nothing is rolled back automatically — a mid-run failure raises
:class:`RuntimeError` so the operator can inspect ``git status`` /
``git log`` and recover manually.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Optional

from ..changelog import gitdata
from ..changelog.cli import check, generate

#: Files carrying the version; bumped and committed first.
_VERSION_FILES = ("yate/__init__.py", "tests/test_theme_palettes.py")
#: Files written by the changelog generator; committed in the second commit.
_CHANGELOG_FILES = (
    "CHANGELOG.md",
    "CHANGELOG.zh.md",
    "yate/resources/changelog.en.md",
    "yate/resources/changelog.zh.md",
)

_SEMVER_RE = re.compile(r"\d+\.\d+\.\d+$")
_INIT_VERSION_RE = re.compile(r'^(__version__\s*=\s*")([^"]+)(")', re.MULTILINE)
_TEST_VERSION_RE = re.compile(r'(assert yate\.__version__\s*==\s*")([^"]+)(")')


def discover_repo_root() -> Path:
    """The repository root is two levels above this package."""
    return Path(__file__).resolve().parents[2]


def read_current_version(repo: Path) -> str:
    """Read ``__version__`` from ``yate/__init__.py`` (the single source)."""
    return gitdata.read_current_version(repo)


def validate_version(version: str, current: str) -> None:
    """Validate ``X.Y.Z`` and require it to be strictly greater than current."""
    if _SEMVER_RE.fullmatch(version) is None:
        raise RuntimeError(f"invalid version {version!r}: expected X.Y.Z")
    new = tuple(int(part) for part in version.split("."))
    old = tuple(int(part) for part in current.split("."))
    if new <= old:
        raise RuntimeError(
            f"version {version} is not greater than current {current}"
        )


def files_dirty(repo: Path, files: Sequence[str]) -> list[str]:
    """Return the paths among ``files`` that have uncommitted changes."""
    out = gitdata.run_git(["status", "--porcelain", "--", *files], repo=repo)
    dirty: list[str] = []
    for line in out.splitlines():
        if not line.strip():
            continue
        # Porcelain: two status chars, a space, then the (possibly quoted) path.
        path = line[3:].strip().strip('"')
        if " -> " in path:  # rename: "old -> new"
            path = path.split(" -> ", 1)[1]
        dirty.append(path)
    return dirty


def _rewrite_version(
    repo: Path, relative: str, pattern: re.Pattern[str], version: str
) -> None:
    path = repo / relative
    text = path.read_text(encoding="utf-8")
    if pattern.search(text) is None:
        raise RuntimeError(f"no version line found in {path}")
    text = pattern.sub(
        lambda match: match.group(1) + version + match.group(3), text, count=1
    )
    path.write_text(text, encoding="utf-8")


def bump_init_py(repo: Path, version: str, *, dry_run: bool = False) -> None:
    """Set ``__version__`` in ``yate/__init__.py``."""
    if dry_run:
        print(f"[dry-run] bump {_VERSION_FILES[0]} -> {version}")
        return
    _rewrite_version(repo, _VERSION_FILES[0], _INIT_VERSION_RE, version)
    print(f"bumped {_VERSION_FILES[0]} -> {version}")


def bump_test_assertion(
    repo: Path, version: str, *, dry_run: bool = False
) -> None:
    """Set the expected version in ``test_version_is_bumped``."""
    if dry_run:
        print(f"[dry-run] bump {_VERSION_FILES[1]} -> {version}")
        return
    _rewrite_version(repo, _VERSION_FILES[1], _TEST_VERSION_RE, version)
    print(f"bumped {_VERSION_FILES[1]} -> {version}")


def git_add(repo: Path, files: Sequence[str], *, dry_run: bool = False) -> None:
    """Stage ``files``."""
    if dry_run:
        print(f"[dry-run] git add -- {' '.join(files)}")
        return
    gitdata.run_git(["add", "--", *files], repo=repo)


def git_commit(
    repo: Path, message: str, *, dry_run: bool = False
) -> None:
    """Create a commit with ``message``."""
    if dry_run:
        print(f"[dry-run] git commit -m {message!r}")
        return
    gitdata.run_git(["commit", "-m", message], repo=repo)
    print(f"committed: {message}")


def generate_changelog(repo: Path, *, dry_run: bool = False) -> None:
    """Regenerate the four bilingual changelog files."""
    if dry_run:
        print(f"[dry-run] generate changelog: {', '.join(_CHANGELOG_FILES)}")
        return
    rc = generate(repo)
    if rc != 0:
        raise RuntimeError(f"changelog generation failed (exit {rc})")


def gate_check(repo: Path) -> int:
    """Run the read-only changelog CI gate; returns its exit code."""
    return check(repo)


def run_version_tests(repo: Path) -> int:
    """Run the version tests with the current interpreter; returns exit code.

    Selects the two version guards in test_theme_palettes.py via ``-k version``
    (test_version_is_bumped + the single-source pyproject guard).
    """
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_theme_palettes.py",
            "-q",
            "-k",
            "version",
        ],
        cwd=repo,
        check=False,
    )
    return completed.returncode


def git_tag(repo: Path, version: str, *, dry_run: bool = False) -> None:
    """Create the annotated ``v<version>`` tag."""
    message = f"Release v{version}"
    if dry_run:
        print(f"[dry-run] git tag -a v{version} -m {message!r}")
        return
    gitdata.run_git(["tag", "-a", f"v{version}", "-m", message], repo=repo)
    print(f"tagged v{version}")


def git_push(repo: Path, refspec: str, *, dry_run: bool = False) -> None:
    """Push ``refspec`` to ``origin``."""
    if dry_run:
        print(f"[dry-run] git push origin {refspec}")
        return
    gitdata.run_git(["push", "origin", refspec], repo=repo)
    print(f"pushed origin {refspec}")


def _default_branch(repo: Path) -> Optional[str]:
    """Detect the branch to push from ``origin/HEAD``; ``None`` if unknown.

    Runs the read-only ``git symbolic-ref refs/remotes/origin/HEAD`` and
    returns the branch name after the last ``/``.  Any failure -- no
    ``origin`` remote, no remote HEAD, git unavailable -- returns ``None``
    (via :class:`~tools.changelog.gitdata.GitError`) so the caller aborts
    instead of guessing a branch name.
    """
    try:
        out = gitdata.run_git(
            ["symbolic-ref", "refs/remotes/origin/HEAD"], repo=repo
        )
    except gitdata.GitError:
        return None
    return out.strip().rsplit("/", 1)[-1] or None


def release(
    version: str,
    *,
    dry_run: bool = False,
    no_push: bool = False,
    branch: Optional[str] = None,
) -> int:
    """Run the full release pipeline; returns the process exit code.

    *branch* names the branch pushed to ``origin``; when omitted the remote
    default branch is detected from ``origin/HEAD``
    (see :func:`_default_branch`), and an undetectable branch aborts the
    release right before the push.
    """
    repo = discover_repo_root()
    current = read_current_version(repo)
    validate_version(version, current)
    print(
        f"release v{current} -> v{version}"
        + (" (dry-run)" if dry_run else "")
    )

    # Step 0: refuse to start with uncommitted version files.
    dirty = files_dirty(repo, _VERSION_FILES)
    if dirty and not dry_run:
        raise RuntimeError(f"refusing to release: uncommitted changes in {dirty}")

    # Step 1-2: bump the version in both files.
    bump_init_py(repo, version, dry_run=dry_run)
    bump_test_assertion(repo, version, dry_run=dry_run)

    # Step 3: commit the bump first, so the changelog generator sees the new
    # version and the new bump commit.
    git_add(repo, _VERSION_FILES, dry_run=dry_run)
    git_commit(repo, f"chore(release): v{version}", dry_run=dry_run)

    # Step 4-5: regenerate and commit the bilingual changelog.
    generate_changelog(repo, dry_run=dry_run)
    git_add(repo, _CHANGELOG_FILES, dry_run=dry_run)
    git_commit(
        repo,
        f"docs(changelog): release v{version} bilingual changelog",
        dry_run=dry_run,
    )

    # Step 6-7: read-only gates; the tag is created only after they pass.
    if gate_check(repo) != 0:
        raise RuntimeError("changelog gate failed")
    if run_version_tests(repo) != 0:
        raise RuntimeError("version tests failed")

    # Step 8: tag, then push (unless --no-push).
    git_tag(repo, version, dry_run=dry_run)
    if no_push:
        print("skip push (--no-push)")
    else:
        push_branch = branch or _default_branch(repo)
        if push_branch is None:
            raise RuntimeError(
                "cannot determine the default branch; pass --branch"
            )
        git_push(repo, push_branch, dry_run=dry_run)
        git_push(repo, f"v{version}", dry_run=dry_run)

    print(f"release v{version} complete")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m tools.release",
        description="One-command release: bump version, changelog, commit, tag, push.",
    )
    parser.add_argument(
        "version", help="target version X.Y.Z, must be greater than current"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="print planned steps, no mutation"
    )
    parser.add_argument(
        "--no-push", action="store_true", help="do everything except push"
    )
    parser.add_argument(
        "--branch",
        default=None,
        help="branch to push (default: detect from origin/HEAD, fail if unknown)",
    )
    args = parser.parse_args(argv)
    try:
        return release(
            args.version,
            dry_run=args.dry_run,
            no_push=args.no_push,
            branch=args.branch,
        )
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
