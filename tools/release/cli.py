"""Command line interface: ``python -m tools.release <version>``.

One-command release: bump the version, commit the bump, regenerate the
bilingual changelog, commit it, run the changelog gate and the version
tests, then create the annotated tag and push.

Pre-flight guards refuse to start -- before the first mutation -- unless
the version files are clean, the checked-out branch matches the push
target (``--branch`` or the ``origin/HEAD`` default), the local branch is
not behind its remote counterpart, and ``v<version>`` is free both locally
and on origin.

A mid-run failure rolls the release back automatically: the created tag is
deleted, the branch is reset to the pre-run HEAD and every touched file is
restored from a byte-exact snapshot.  Once the branch push has succeeded
the commits are public, so only manual recovery instructions are printed.

All git access goes through :func:`tools.changelog.gitdata.run_git` (the
single git gateway); changelog generation/gating reuses
:func:`tools.changelog.cli.generate` / :func:`tools.changelog.cli.check`.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from ..changelog import gitdata
from ..changelog.cli import check, generate

#: File carrying the version; bumped and committed first.  The package
#: ``__version__`` is the single dynamic source (pyproject reads it; the
#: former static assertion in test_theme_palettes.py was removed upstream).
_VERSION_FILES = ("yate/__init__.py",)
#: Files written by the changelog generator; committed in the second commit.
_CHANGELOG_FILES = (
    "CHANGELOG.md",
    "CHANGELOG.zh.md",
    "yate/resources/changelog.en.md",
    "yate/resources/changelog.zh.md",
)

_SEMVER_RE = re.compile(r"\d+\.\d+\.\d+$")
# MULTILINE: the package __init__ opens with a module docstring, so the
# __version__ line is never at position 0.
_INIT_VERSION_RE = re.compile(r'^(__version__\s*=\s*")([^"]+)(")', re.MULTILINE)


@dataclass
class _RunState:
    """Mutation flags a pipeline run sets as it progresses.

    The rollback path reads them to decide how far the release got: a
    created tag must be deleted, while an already-pushed branch forbids a
    destructive rollback.
    """

    tag_created: bool = False
    branch_pushed: bool = False


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
    """Return the paths among ``files`` that have uncommitted changes.

    Parses ``git status --porcelain -z`` (NUL-separated records, paths shown
    verbatim without C-style quoting), so names containing spaces, quotes or
    non-ASCII characters survive exactly; rename/copy entries put the new
    path first and the source path in a second NUL-terminated field, which
    is consumed and ignored.
    """
    out = gitdata.run_git(["status", "--porcelain", "-z", "--", *files], repo=repo)
    dirty: list[str] = []
    records = out.split("\0")
    i = 0
    while i < len(records):
        record = records[i]
        i += 1
        if not record:
            continue
        # -z record: two status chars, a space, then the verbatim path.
        path = record[3:]
        status = record[:2]
        if ("R" in status or "C" in status) and i < len(records):
            i += 1  # rename/copy: the source path is a second NUL field
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


def _default_branch(repo: Path) -> str | None:
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


def current_branch(repo: Path) -> str:
    """The checked-out branch name (empty string on a detached HEAD)."""
    return gitdata.current_branch(repo)


def assert_in_sync(repo: Path, branch: str) -> None:
    """Refuse when the local ``branch`` is behind ``origin/<branch>``.

    Fetches the branch first so the comparison sees the current remote
    state; a fetch failure (offline, unknown remote branch) surfaces as
    :class:`~tools.changelog.gitdata.GitError` and aborts the release.
    """
    gitdata.run_git(["fetch", "origin", branch], repo=repo)
    behind = gitdata.run_git(
        ["rev-list", "--count", f"HEAD..origin/{branch}"], repo=repo
    ).strip()
    if behind and behind != "0":
        raise RuntimeError(
            f"refusing to release: local {branch} is {behind} commit(s) "
            f"behind origin/{branch}; pull or rebase first"
        )


def _local_tag_exists(repo: Path, tag: str) -> bool:
    """Whether ``refs/tags/<tag>`` resolves locally."""
    try:
        gitdata.run_git(
            ["rev-parse", "-q", "--verify", f"refs/tags/{tag}"], repo=repo
        )
    except gitdata.GitError:
        return False
    return True


def assert_tag_available(repo: Path, version: str) -> None:
    """Refuse when ``v<version>`` already exists locally or on ``origin``."""
    tag = f"v{version}"
    if _local_tag_exists(repo, tag):
        raise RuntimeError(f"refusing to release: tag {tag} already exists locally")
    out = gitdata.run_git(
        ["ls-remote", "--tags", "origin", f"refs/tags/{tag}"], repo=repo
    )
    if out.strip():
        raise RuntimeError(f"refusing to release: tag {tag} already exists on origin")


def _snapshot_texts(repo: Path, files: Sequence[str]) -> dict[str, str | None]:
    """Pre-run content of *files*; ``None`` marks a not-yet-existing file."""
    snapshots: dict[str, str | None] = {}
    for rel in files:
        path = repo / rel
        snapshots[rel] = path.read_text(encoding="utf-8") if path.exists() else None
    return snapshots


def _run_steps(
    repo: Path,
    version: str,
    push_branch: str,
    *,
    no_push: bool,
    dry_run: bool,
    state: _RunState | None = None,
) -> None:
    """The mutating pipeline: bump, changelog, gates, tag, push.

    *state* records how far the run got (tag created / branch pushed) so
    the rollback path knows what to undo; it is ``None`` for dry-runs.
    """
    bump_init_py(repo, version, dry_run=dry_run)
    git_add(repo, _VERSION_FILES, dry_run=dry_run)
    git_commit(repo, f"chore(release): v{version}", dry_run=dry_run)

    generate_changelog(repo, dry_run=dry_run)
    git_add(repo, _CHANGELOG_FILES, dry_run=dry_run)
    git_commit(
        repo,
        f"docs(changelog): release v{version} bilingual changelog",
        dry_run=dry_run,
    )

    if gate_check(repo) != 0:
        raise RuntimeError("changelog gate failed")
    if run_version_tests(repo) != 0:
        raise RuntimeError("version tests failed")

    git_tag(repo, version, dry_run=dry_run)
    if state is not None:
        state.tag_created = not dry_run
    if no_push:
        print("skip push (--no-push)")
        return
    git_push(repo, push_branch, dry_run=dry_run)
    if state is not None:
        state.branch_pushed = True
    git_push(repo, f"v{version}", dry_run=dry_run)


def _abort_with_rollback(
    repo: Path,
    exc: RuntimeError,
    version: str,
    push_branch: str,
    orig_head: str,
    snapshots: dict[str, str | None],
    state: _RunState,
) -> int:
    """Report the failure, undo the partial release, return exit code 1.

    ``git reset --mixed`` restores the branch pointer and the index without
    touching the worktree; the snapshots then put every file back
    byte-for-byte (a ``None`` snapshot deletes a file the run created).
    Any pre-existing staged changes elsewhere end up unstaged -- their
    content survives.  Rollback is skipped once the branch push succeeded:
    the commits are already public, so only instructions are printed.
    """
    print(f"error: {exc}", file=sys.stderr)
    if state.branch_pushed:
        print(
            f"rollback skipped: release commits are already on "
            f"origin/{push_branch}; recover manually -- retry "
            f"`git push origin v{version}`, or abandon the release with "
            f"`git tag -d v{version}` plus a reset to origin/{push_branch}.",
            file=sys.stderr,
        )
        return 1
    if state.tag_created:
        gitdata.run_git(["tag", "-d", f"v{version}"], repo=repo)
    gitdata.run_git(["reset", "--mixed", orig_head], repo=repo)
    for rel, text in snapshots.items():
        path = repo / rel
        if text is None:
            path.unlink(missing_ok=True)
        else:
            path.write_text(text, encoding="utf-8")
    print(
        f"rolled back: tag removed, branch reset to {orig_head[:7]}, "
        "files restored",
        file=sys.stderr,
    )
    return 1


def release(
    version: str,
    *,
    dry_run: bool = False,
    no_push: bool = False,
    branch: str | None = None,
) -> int:
    """Run the full release pipeline; returns the process exit code.

    *branch* names the branch pushed to ``origin``; when omitted the remote
    default branch is detected from ``origin/HEAD``
    (see :func:`_default_branch`).  The pre-flight guards refuse to start
    when the checked-out branch differs from the push target, when the
    local branch is behind its remote counterpart, or when ``v<version>``
    already exists locally or on origin; a mid-run failure rolls the
    release back (see :func:`_abort_with_rollback`).
    """
    repo = discover_repo_root()
    current = read_current_version(repo)
    validate_version(version, current)
    print(
        f"release v{current} -> v{version}"
        + (" (dry-run)" if dry_run else "")
    )

    # Step 0: pre-flight guards -- read-only, so a refusal leaves the tree,
    # the history and the tags untouched.
    dirty = files_dirty(repo, _VERSION_FILES)
    if dirty and not dry_run:
        raise RuntimeError(f"refusing to release: uncommitted changes in {dirty}")
    push_branch = branch or _default_branch(repo)
    if push_branch is None:
        raise RuntimeError("cannot determine the default branch; pass --branch")
    if not dry_run:
        checked_out = current_branch(repo)
        if checked_out != push_branch:
            raise RuntimeError(
                f"refusing to release: checked out on {checked_out!r} but "
                f"the push target is {push_branch!r}; switch branches or "
                f"pass --branch {checked_out!r}"
            )
        assert_in_sync(repo, push_branch)
        assert_tag_available(repo, version)

    if dry_run:
        _run_steps(repo, version, push_branch, no_push=no_push, dry_run=True)
        return 0

    # Rollback journal: byte-exact pre-run content of every file the
    # pipeline may write (``None`` = file did not exist yet) plus the HEAD
    # sha, taken before the first mutation.
    snapshots = _snapshot_texts(repo, (*_VERSION_FILES, *_CHANGELOG_FILES))
    orig_head = gitdata.head_sha(repo)
    state = _RunState()
    try:
        _run_steps(
            repo, version, push_branch, no_push=no_push, dry_run=False,
            state=state,
        )
    except RuntimeError as exc:
        # GitError subclasses RuntimeError, so fetch/push failures land here.
        return _abort_with_rollback(
            repo, exc, version, push_branch, orig_head, snapshots, state
        )
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
