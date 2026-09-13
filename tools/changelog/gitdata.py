"""Git CLI access — the ONLY module allowed to shell out to ``git``.

All commands run through ``subprocess.run`` with an explicit UTF-8 encoding so
Chinese commit messages survive Windows' GBK console code page.  Parsing
helpers are separated from the command runners so tests can feed canned
``git`` output instead of mocking the process boundary.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from .model import RawCommit, TagRef, VersionBump

#: Field separator inside one log record.
_FIELD_SEP = "\x1f"
#: Record separator between two log records.
_RECORD_SEP = "\x1e"

_LOG_FORMAT = (
    f"%H{_FIELD_SEP}%h{_FIELD_SEP}%ad{_FIELD_SEP}%s{_FIELD_SEP}%b{_RECORD_SEP}"
)

_BUMP_LINE_RE = re.compile(r'^\+__version__\s*=\s*"([^"]+)"')
_SHA_LINE_RE = re.compile(r"^[0-9a-f]{40}$")
_VERSION_LINE_RE = re.compile(r'^__version__\s*=\s*"([^"]+)"', re.MULTILINE)


class GitError(RuntimeError):
    """A git command failed or its output could not be parsed."""


def run_git(args: list[str], *, repo: Path) -> str:
    """Run a git command inside ``repo`` and return its stdout."""
    command = ["git", "-C", str(repo), *args]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
            check=False,
        )
    except FileNotFoundError as exc:
        raise GitError("git executable not found on PATH") from exc
    except subprocess.TimeoutExpired as exc:
        raise GitError(f"git timed out: git {' '.join(args)}") from exc
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise GitError(f"git {' '.join(args)} failed: {detail}")
    return completed.stdout


def parse_log_output(text: str) -> list[RawCommit]:
    """Parse the ``_LOG_FORMAT`` stream into commits (order preserved).

    The body keeps any stray field separators (``maxsplit``), so only the
    subject itself containing ``\\x1f`` could desynchronise a record.
    """
    commits: list[RawCommit] = []
    for record in text.split(_RECORD_SEP):
        stripped = record.strip("\n")
        if not stripped.strip():
            continue
        fields = stripped.split(_FIELD_SEP, 4)
        if len(fields) < 5:
            raise GitError(f"malformed git log record: {stripped[:80]!r}")
        sha, short_sha, author_date, subject, body = fields
        commits.append(
            RawCommit(
                sha=sha.strip(),
                short_sha=short_sha.strip(),
                author_date=author_date.strip(),
                subject=subject,
                body=body.strip(),
            )
        )
    return commits


def read_commits(
    repo: Path, *, include_merges: bool = False, limit: int | None = None
) -> list[RawCommit]:
    """Read commits newest-first in stable topo order (author date ignored)."""
    args = ["log", "--topo-order"]
    if not include_merges:
        args.append("--no-merges")
    if limit is not None:
        args += ["-n", str(limit)]
    args += ["--date=short", f"--pretty=format:{_LOG_FORMAT}"]
    return parse_log_output(run_git(args, repo=repo))


def read_tags(repo: Path) -> list[TagRef]:
    """Read ``v*`` tags newest-creation-date first, resolving each to a sha."""
    out = run_git(["tag", "--list", "v*", "--sort=-creatordate"], repo=repo)
    tags: list[TagRef] = []
    for name in out.splitlines():
        name = name.strip()
        if not name:
            continue
        sha = run_git(["rev-list", "-n1", name], repo=repo).strip()
        if sha:
            tags.append(TagRef(name=name, sha=sha))
    return tags


def parse_bump_patch(text: str) -> list[VersionBump]:
    """Parse ``git log -p`` output for ADDED ``__version__`` lines.

    Only lines starting with ``+`` count (removed/re-contexted lines start
    with ``-``/space), so a version line being moved around does not create a
    fake bump unless it was genuinely re-added.
    """
    bumps: list[VersionBump] = []
    for chunk in text.split(_RECORD_SEP):
        lines = chunk.splitlines()
        if not lines:
            continue
        sha = lines[0].strip()
        if not _SHA_LINE_RE.fullmatch(sha):
            continue
        for line in lines[1:]:
            match = _BUMP_LINE_RE.match(line)
            if match is not None:
                bumps.append(VersionBump(sha=sha, version=match.group(1)))
    return bumps


def read_version_bumps(repo: Path) -> list[VersionBump]:
    """Read version bumps oldest-first from the history of ``yate/__init__.py``."""
    out = run_git(
        [
            "log",
            "--topo-order",
            "--reverse",
            "-p",
            "--date=short",
            "--pretty=format:%x1e%H",
            "--",
            "yate/__init__.py",
        ],
        repo=repo,
    )
    return parse_bump_patch(out)


def remote_url(repo: Path) -> str:
    """Return the ``origin`` remote URL; raises :class:`GitError` if absent."""
    return run_git(["remote", "get-url", "origin"], repo=repo).strip()


def head_sha(repo: Path) -> str:
    return run_git(["rev-parse", "HEAD"], repo=repo).strip()


def resolve_commit_sha(repo: Path, prefix: str) -> str:
    """Expand a (short) hash prefix to the full sha; raises if unknown."""
    return run_git(["rev-parse", "--verify", f"{prefix}^{{commit}}"], repo=repo).strip()


def commit_subject(repo: Path, sha: str) -> str:
    return run_git(["log", "-1", "--pretty=%s", sha], repo=repo).strip()


def read_current_version(repo: Path) -> str:
    """Read ``__version__`` from ``yate/__init__.py`` (the single source)."""
    init_path = repo / "yate" / "__init__.py"
    try:
        text = init_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise GitError(f"cannot read {init_path}: {exc}") from exc
    match = _VERSION_LINE_RE.search(text)
    if match is None:
        raise GitError(f"no __version__ line found in {init_path}")
    return match.group(1)
