"""Wiki publishing: git plumbing, the manifest store, pruning and the
write-back of translated pages.

Holds :func:`run_git` (bounded, synthetic-timeout git runs), the target
derivation (:func:`default_target`), the ``.translation-manifest.json``
store (:func:`load_manifest` / :func:`store_manifest`), the orphan-page
prune (:func:`prune_orphan_pages`, guarded by :func:`_assert_prune_safe`)
and the push path (:func:`push_wiki` via :func:`_github_wiki_url`), plus
the landing/publish half of the translation stage
(:func:`_publish_translations` and its salvage path).

The ``subprocess`` module and :func:`run_git` are read through the
late-bound facade (``_wiki_facade.<name>``): the test suite replaces
``wiki.subprocess`` wholesale and patches ``wiki.run_git``, so a plain
module-level binding would keep using the pre-patch object.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, cast

import tools.pack.wiki as _wiki_facade
from rich.console import Console

from tools.pack import errors
from tools.pack.errors import Code, PackError
from tools.pack.wiki.lint import _LintPool, _LintRequest, _lint_texts, WikiError
from tools.pack.wiki.report import _PageOutcome
from tools.pack.wiki.sources import (
    _EN_SUFFIX,
    _write_page_text,
    WikiPage,
)

# The shared surface of this submodule: the facade re-exports it and the
# sibling submodules consume it, so every name below is intentionally
# public within the subpackage (a leading underscore only keeps it out of
# the generator's documented plugin-facing API).
__all__ = [
    "COMMIT_MESSAGE",
    "GITHUB_WIKI_URL",
    "GIT_TIMEOUT_S",
    "MANIFEST_NAME",
    "WIKI_BRANCH",
    "_GITHUB_HTTPS_RE",
    "_GITHUB_SCP_RE",
    "_GITHUB_SSH_RE",
    "_LandedPage",
    "_assert_prune_safe",
    "_github_wiki_url",
    "_landed_pages",
    "_publish_translations",
    "_salvage_landed",
    "default_target",
    "load_manifest",
    "prune_orphan_pages",
    "push_wiki",
    "run_git",
    "store_manifest",
]

GITHUB_WIKI_URL: Final[str] = "https://github.com/BigThxBrigde/yate.wiki.git"

#: Name of the translation manifest written at the wiki repo root.
MANIFEST_NAME: Final[str] = ".translation-manifest.json"

WIKI_BRANCH: Final[str] = "master"

COMMIT_MESSAGE: Final[str] = "docs: regenerate wiki from sources"

#: Wall clock budget for one git command (a first ``git push`` of a large
#: wiki repo included): a hung git must not block the run forever.
GIT_TIMEOUT_S: Final[float] = 120.0


def run_git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run a git command inside *cwd*, capturing output as text.

    The command is bounded by :data:`GIT_TIMEOUT_S`; on timeout the child is
    killed and a synthetic failed ``CompletedProcess`` (exit code 124, the
    ``timeout(1)`` convention) is returned, so every caller reports a clean
    stderr error instead of hanging forever -- mirroring
    :func:`tools.changelog.gitdata.run_git`.
    """
    try:
        return _wiki_facade.subprocess.run(
            ["git", "-C", str(cwd), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=GIT_TIMEOUT_S,
        )
    except FileNotFoundError as exc:
        raise WikiError(
            "git executable not found on PATH",
            code=Code.GIT_MISSING,
            hint="install git or run without --push",
        ) from exc
    except _wiki_facade.subprocess.TimeoutExpired:
        detail = f"git timed out after {GIT_TIMEOUT_S:g}s: git {' '.join(args)}"
        return _wiki_facade.subprocess.CompletedProcess(args, 124, "", detail)


def default_target(repo_root: Path) -> Path:
    """Derive the wiki repo path from the origin remote URL.

    ``https://gitee.com/<user>/yate.git`` next to the checkout yields
    ``<parent>/yate.wiki`` -- correct in worktrees too, whose directory
    name differs from the canonical repo name.  Without an origin
    remote, falls back to the checkout directory name.
    """
    proc = _wiki_facade.run_git(repo_root, "remote", "get-url", "origin")
    url = proc.stdout.strip() if proc.returncode == 0 else ""
    if url:
        name = url.rstrip("/").rsplit("/", 1)[-1]
        if name.endswith(".git"):
            name = name[: -len(".git")]
    else:
        name = repo_root.name
    return repo_root.parent / f"{name}.wiki"


def load_manifest(target: Path) -> dict[str, str]:
    """Load the sha256 manifest from *target*.

    A missing file yields an empty manifest; a truncated or malformed one
    is reported on stderr and treated as empty so the generator can start
    over instead of crashing on leftover partial state.
    """
    path = target / MANIFEST_NAME
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        errors.report(
            PackError(
                Code.WIKI_MANIFEST_READ, "manifest corrupt, starting fresh"
            )
        )
        return {}
    except OSError as exc:
        # A read error (permissions, disk trouble) must not silently reset
        # the sha256 records: the next store_manifest() would overwrite the
        # file and every stale marker would be lost.  Abort via WikiError so
        # the CLI layer reports it and exits 1 (library code never sys.exit).
        raise WikiError(f"manifest read error: {exc}", code=Code.WIKI_MANIFEST_READ) from exc
    if not isinstance(raw, dict):
        errors.report(
            PackError(
                Code.WIKI_MANIFEST_READ, "manifest is not an object, starting fresh"
            )
        )
        return {}
    data = cast("dict[str, object]", raw)
    return {str(k): str(v) for k, v in data.items()}


def store_manifest(target: Path, manifest: dict[str, str]) -> None:
    """Write the sha256 manifest to *target* (sorted, stable diffs)."""
    text = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True)
    _write_page_text(target / MANIFEST_NAME, f"{text}\n", code=Code.WIKI_MANIFEST_WRITE)


def _assert_prune_safe(target: Path, root: Path) -> None:
    """Refuse a target that contains the source tree.

    Review B-3: ``prune_orphan_pages`` deletes generated pages, so a
    mistyped ``--target`` must not be able to point at the checkout which
    holds the sources.  Two facts bound the damage: deletion only ever
    touches pages the previous manifest recorded as written by this tool
    (English pages additionally only while their bytes still match the
    recorded digest), and a target at or above
    the repository root (``--target .``) is refused here.  Generating into
    any folder *below* the root -- ``out/``, ``<root>/.wiki`` -- or next to
    it stays allowed (review B-2: an unconditional "inside the repo"
    refusal blocked that legitimate layout).
    """
    if root.resolve().is_relative_to(target.resolve()):
        raise WikiError(
            f"refusing to use {target} as the wiki target: it contains the "
            "source repository",
            code=Code.WIKI_PRUNE_FAILED,
            hint="pass --target pointing at the <repo>.wiki checkout or an "
                "output directory",
        )


def prune_orphan_pages(target: Path, keep: set[str], recorded: dict[str, str]) -> int:
    """Delete generated wiki pages whose source document no longer exists.

    *keep* holds the ``zh``/``en`` target names produced by this run and
    *recorded* maps page names to the sha256 digest this tool recorded
    when it last wrote them (review B-3).  A ``*.md`` file outside *keep*
    is only considered for removal when it appears in *recorded*: a file
    the generator has never written (a user's own page, an older orphan
    from before the manifest existed, an adopted English page) is kept,
    so a mistyped target can at worst delete pages this tool created.
    A Chinese page is deleted while it is recorded.  An English page is
    deleted only while its current bytes still match the recorded digest:
    a hand-edited English page no longer is the generator's output and
    survives.  The generated ``Home`` / ``_Sidebar`` navigation and
    anything inside ``.git`` are always protected.  Returns the number of
    removed files.
    """
    protected = {"Home.md", "_Sidebar.md", "Home.en.md", "_Sidebar.en.md"}
    removed = 0
    for existing in target.rglob("*.md"):
        rel = existing.relative_to(target)
        posix = rel.as_posix()
        if ".git" in rel.parts or posix in keep or existing.name in protected:
            continue
        digest = recorded.get(posix)
        if digest is None:
            continue
        if posix.endswith(_EN_SUFFIX):
            try:
                current = hashlib.sha256(existing.read_bytes()).hexdigest()
            except OSError as exc:
                raise WikiError(
                    f"cannot inspect orphan page {posix}: {exc}",
                    code=Code.WIKI_PRUNE_FAILED,
                ) from exc
            if current != digest:
                # Adopted or hand-edited after this tool wrote it: no
                # longer the generator's output, so it stays.
                continue
        try:
            existing.unlink()
        except OSError as exc:
            raise WikiError(
                f"cannot remove orphan page {posix}: {exc}",
                code=Code.WIKI_PRUNE_FAILED,
            ) from exc
        removed += 1
    return removed


#: GitHub origin shapes: an ``https`` URL, an ``ssh://`` URL, or the
#: scp-like SSH form (``git@github.com:owner/repo.git``).
_GITHUB_HTTPS_RE: Final[re.Pattern[str]] = re.compile(
    r"^https?://(?:[^@/]+@)?github\.com/(?P<path>.+)$"
)
_GITHUB_SSH_RE: Final[re.Pattern[str]] = re.compile(
    r"^ssh://(?:[^@/]+@)?github\.com(?::\d+)?/(?P<path>.+)$"
)
_GITHUB_SCP_RE: Final[re.Pattern[str]] = re.compile(
    r"^(?:[^@/]+@)?github\.com:(?P<path>[^/].*)$"
)


def _github_wiki_url(repo_root: Path) -> str:
    """Resolve the GitHub wiki URL to push the mirror to (``""`` disables it).

    ``YATE_WIKI_GITHUB_URL`` wins when set; an explicitly empty value
    disables the mirror push instead of silently falling back.  Otherwise a
    ``github.com`` origin derives its own ``<owner>/<repo>.wiki.git`` (a
    fork pushes its own wiki); any other origin -- the Gitee main repo, no
    remote at all -- falls back to :data:`GITHUB_WIKI_URL`, the published
    mirror (review m-24: the constant used to be hard-wired regardless of
    the origin).

    The host is matched with anchored patterns, not a substring: a URL that
    merely embeds ``github.com/`` in its path (a Gitee mirror, a GitLab
    group) is not a GitHub origin (review M-5 of the wave-e re-review).
    """
    override = os.environ.get("YATE_WIKI_GITHUB_URL")
    if override is not None:
        return override.strip()
    proc = _wiki_facade.run_git(repo_root, "remote", "get-url", "origin")
    url = proc.stdout.strip() if proc.returncode == 0 else ""
    match = (
        _GITHUB_HTTPS_RE.match(url)
        or _GITHUB_SSH_RE.match(url)
        or _GITHUB_SCP_RE.match(url)
    )
    if match is None:
        return GITHUB_WIKI_URL
    path = match.group("path").rstrip("/").removesuffix(".git")
    segments = [part for part in path.split("/") if part]
    if len(segments) > 2 and segments[0].isdigit():
        # ``ssh://git@github.com:22/owner/repo``: the first segment is a port.
        segments = segments[1:]
    if len(segments) != 2:
        return GITHUB_WIKI_URL
    return f"https://github.com/{segments[0]}/{segments[1]}.wiki.git"


def push_wiki(target: Path, *, github_url: str = GITHUB_WIKI_URL) -> int:
    """Commit *target* and push it to both remotes; 0 on full success.

    An empty commit is tolerated (nothing to commit).  The ``github``
    remote is added on first use with *github_url*, the resolved mirror
    URL (review m-24); an empty URL disables the mirror push entirely.
    """
    added = _wiki_facade.run_git(target, "add", "-A")
    if added.returncode != 0:
        detail = (added.stderr or added.stdout).strip()
        errors.report(PackError(Code.WIKI_GIT_FAILED, f"git add failed: {detail}"))
        return 1
    commit = _wiki_facade.run_git(target, "commit", "-m", COMMIT_MESSAGE)
    if commit.returncode != 0:
        out = f"{commit.stdout}{commit.stderr}".strip()
        if "nothing to commit" not in out and "nothing added to commit" not in out:
            errors.report(PackError(Code.WIKI_GIT_FAILED, f"commit failed: {out}"))
            return 1
        print(f"wiki: commit: {out}")
    remotes = ["origin"]
    if github_url:
        if _wiki_facade.run_git(target, "remote", "get-url", "github").returncode != 0:
            _wiki_facade.run_git(target, "remote", "add", "github", github_url)
        remotes.append("github")
    failures = 0
    for remote in remotes:
        pushed = _wiki_facade.run_git(target, "push", remote, WIKI_BRANCH)
        if pushed.returncode != 0:
            failures += 1
            detail = (pushed.stderr or pushed.stdout).strip()
            errors.report(
                PackError(Code.WIKI_GIT_FAILED, f"push {remote} failed: {detail}")
            )
    return 1 if failures else 0


@dataclass(frozen=True)
class _LandedPage:
    """One translation a run really produced, waiting for lint and write."""

    page: WikiPage
    digest: str
    english: str


def _publish_translations(
    outcomes: Sequence[_PageOutcome],
    target: Path,
    *,
    lint_pool: _LintPool,
    console: Console,
    show_bar: bool,
) -> tuple[int, dict[str, str]]:
    """Lint, write and digest the pages a translation run landed.

    Returns ``(translated, digests)``: the count of pages actually written
    and the manifest entries for them -- the zh digest that records the
    source the translation belongs to, and the en digest of the bytes this
    tool put on disk.  Those on-disk bytes are the ones hashed because
    ``Path.write_text`` translates newlines on Windows, so the linted text
    is not necessarily what landed.

    *show_bar* is false on the interrupt salvage path, where the
    translation run's own bar is still live on this console and a second
    rich ``Progress`` would fight it for the display.
    """
    landed = _landed_pages(outcomes)
    fixed = _lint_texts(
        [_LintRequest(item.page.en_target, "en", item.english) for item in landed],
        lint_pool=lint_pool,
        console=console,
        show_bar=show_bar,
    )
    translated = 0
    digests: dict[str, str] = {}
    for item in landed:
        page = item.page
        _write_page_text(
            target / page.en_target, fixed.get(page.en_target, item.english)
        )
        digests[page.zh_target] = item.digest
        digests[page.en_target] = hashlib.sha256(
            (target / page.en_target).read_bytes()
        ).hexdigest()
        translated += 1
    return translated, digests


def _landed_pages(outcomes: Sequence[_PageOutcome]) -> list[_LandedPage]:
    """The pages a run really landed.

    A page whose translation failed carries ``english=None``; the caller
    already reported it as missing/stale, so it is skipped here.
    """
    landed: list[_LandedPage] = []
    for outcome in outcomes:
        english = outcome.english
        if english is None:
            continue
        landed.append(
            _LandedPage(
                page=outcome.plan.page, digest=outcome.plan.digest, english=english
            )
        )
    return landed


def _salvage_landed(
    landed: Sequence[_PageOutcome],
    target: Path,
    *,
    lint_pool: _LintPool,
    console: Console,
) -> None:
    """Best-effort publish of the pages a cancelled run already translated.

    An interrupt (a failed worker, or a direct ``Ctrl+C`` in the main
    thread) must not throw finished translations away: the pages that
    landed are linted and written exactly as in a clean run before the
    exception leaves.  A salvage failure is logged, never raised -- the
    original interrupt wins.
    """
    if not landed:
        return
    console.print(
        f"wiki: publishing {len(landed)} finished page(s)"
        " before the interrupt propagates",
        markup=False,
    )
    try:
        _publish_translations(
            landed, target, lint_pool=lint_pool, console=console, show_bar=False
        )
    except Exception as exc:  # noqa: BLE001 - the interrupt wins
        errors.log.warning(
            "wiki: could not publish %d finished page(s) after the interrupt: %s",
            len(landed),
            exc,
        )
