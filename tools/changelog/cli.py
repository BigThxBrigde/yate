"""Command line interface: ``python -m tools.changelog``.

Subcommands:

* ``generate [--online] [--limit N] [--check] [--require-zh]`` — render and
  write ``CHANGELOG.md`` / ``CHANGELOG.zh.md`` at the repository root
  (``--check`` only compares against disk and exits non-zero on drift);
* ``check [--online] [--require-zh]`` — CI gate: exit 1 when the generated
  files are stale; ``--require-zh`` additionally fails when any entry lacks a
  Chinese translation (gradual translation is the default policy);
* ``zh-commit <hash> <summary> [<detail>]`` — upsert one Chinese translation
  into ``tools/changelog/zh_overrides.json``.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from . import gitee, gitdata, render, segments, translations
from .classify import classify_commit, is_changelog_entry
from .model import Commit, ReleaseSegment
from .translations import OverrideEntry

_EN_FILE = "CHANGELOG.md"
_ZH_FILE = "CHANGELOG.zh.md"


def discover_repo_root() -> Path:
    """The repository root is two levels above this package."""
    return Path(__file__).resolve().parents[2]


def _resolve_remote(repo: Path) -> gitee.RemoteInfo | None:
    try:
        url = gitdata.remote_url(repo)
    except gitdata.GitError:
        print("warning: no 'origin' remote — rendering entries without links")
        return None
    remote = gitee.parse_remote(url)
    if remote is None:
        print(f"warning: cannot parse remote URL {url!r} — entries without links")
    return remote


def _build_segments(
    repo: Path, *, limit: int | None
) -> tuple[list[ReleaseSegment], list[Commit]]:
    """Collect git data and slice it into release segments.

    Returns the segments (newest first) and all classified entries.
    """
    full = gitdata.read_commits(repo, include_merges=True, limit=limit)
    raw_entries = gitdata.read_commits(repo, include_merges=False, limit=limit)
    tags = gitdata.read_tags(repo)
    bumps = gitdata.read_version_bumps(repo)
    current_version = gitdata.read_current_version(repo)

    entries = [c for c in map(classify_commit, raw_entries) if is_changelog_entry(c)]
    boundaries = segments.build_boundaries(
        tags, bumps, full, current_version=current_version
    )
    release_segments = segments.build_segments(
        full, entries, boundaries, current_version=current_version
    )
    return release_segments, entries


def _missing_zh(
    entries: Sequence[Commit], overrides: dict[str, OverrideEntry]
) -> list[str]:
    return [c.short_sha for c in entries if c.short_sha not in overrides]


def generate(
    repo: Path,
    *,
    online: bool = False,
    limit: int | None = None,
    check: bool = False,
    require_zh: bool = False,
    overrides_path: Path = translations.DEFAULT_OVERRIDES_PATH,
) -> int:
    """Render and write (or verify) both changelog files; returns exit code."""
    remote = _resolve_remote(repo)
    release_segments, entries = _build_segments(repo, limit=limit)
    overrides = translations.load_overrides(overrides_path)

    pushed: dict[str, bool] = {}
    if online and remote is not None:
        lookup = {c.short_sha: c.sha for c in entries}
        pushed = gitee.pushed_flags(remote, lookup)
        unpushed = [sha for sha, ok in pushed.items() if not ok]
        if unpushed:
            print(f"warning: {len(unpushed)} commit(s) not found on Gitee")

    en_doc = render.render_document(
        release_segments, lang="en", remote=remote, overrides=overrides, pushed=pushed
    )
    zh_doc = render.render_document(
        release_segments, lang="zh", remote=remote, overrides=overrides, pushed=pushed
    )

    en_path = repo / _EN_FILE
    zh_path = repo / _ZH_FILE
    if check:
        problems: list[str] = []
        for name, path, doc in (
            (_EN_FILE, en_path, en_doc),
            (_ZH_FILE, zh_path, zh_doc),
        ):
            try:
                current = path.read_text(encoding="utf-8")
            except OSError:
                problems.append(name)
                continue
            if current != doc:
                problems.append(name)
        if problems:
            print(f"stale changelog files: {', '.join(problems)} — run generate")
            return 1
        print("changelog files are up to date")
    else:
        en_path.write_text(en_doc, encoding="utf-8")
        zh_path.write_text(zh_doc, encoding="utf-8")
        print(f"wrote {_EN_FILE} and {_ZH_FILE}")

    missing = _missing_zh(entries, overrides)
    versions = [s.version for s in release_segments if s.version is not None]
    print(
        f"stats: {len(release_segments)} segment(s), "
        f"{len(versions)} version(s), {len(entries)} entry/entries, "
        f"{len(missing)} missing zh translation(s)"
    )
    if missing:
        print("missing zh: " + ", ".join(missing))
    if require_zh and missing:
        print("check failed: missing zh translations (--require-zh)")
        return 1
    return 0


def check(
    repo: Path,
    *,
    online: bool = False,
    require_zh: bool = False,
    overrides_path: Path = translations.DEFAULT_OVERRIDES_PATH,
) -> int:
    """CI gate — equivalent to ``generate --check`` (plus ``--require-zh``)."""
    return generate(
        repo, online=online, check=True, require_zh=require_zh,
        overrides_path=overrides_path,
    )


def zh_commit(
    repo: Path,
    hash_prefix: str,
    summary: str,
    detail: str | None = None,
    *,
    overrides_path: Path = translations.DEFAULT_OVERRIDES_PATH,
) -> int:
    """Upsert one Chinese translation keyed by the 7-char short hash."""
    try:
        full_sha = gitdata.resolve_commit_sha(repo, hash_prefix)
    except gitdata.GitError as exc:
        print(f"error: unknown commit {hash_prefix!r} ({exc})")
        return 1
    short_sha = full_sha[:7]
    english = gitdata.commit_subject(repo, full_sha)
    overrides = translations.load_overrides(overrides_path)
    changed = translations.upsert_override(overrides, short_sha, summary, detail)
    if not changed:
        print(f"unchanged: {short_sha} already has this translation")
        return 0
    translations.save_overrides(overrides, overrides_path)
    print(f"saved zh override for {short_sha}")
    print(f"  en: {english}")
    print(f"  zh: {summary}" + (f"\n  detail: {detail}" if detail else ""))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m tools.changelog",
        description="Maintain the bilingual CHANGELOG.md / CHANGELOG.zh.md.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    gen = subparsers.add_parser("generate", help="render and write both files")
    gen.add_argument("--online", action="store_true", help="verify commits on Gitee")
    gen.add_argument("--limit", type=int, default=None, help="only newest N commits")
    gen.add_argument(
        "--check", action="store_true", help="compare against disk, do not write"
    )
    gen.add_argument(
        "--require-zh", action="store_true", help="fail when zh translations miss"
    )

    chk = subparsers.add_parser("check", help="CI gate: fail on stale files")
    chk.add_argument("--online", action="store_true", help="verify commits on Gitee")
    chk.add_argument(
        "--require-zh", action="store_true", help="fail when zh translations miss"
    )

    zc = subparsers.add_parser(
        "zh-commit", help="upsert a Chinese translation into zh_overrides.json"
    )
    zc.add_argument("hash", help="commit hash (short or full)")
    zc.add_argument("summary", help="Chinese summary")
    zc.add_argument("detail", nargs="?", default=None, help="optional Chinese detail")

    args = parser.parse_args(argv)
    repo = discover_repo_root()
    if args.command == "generate":
        return generate(
            repo,
            online=args.online,
            limit=args.limit,
            check=args.check,
            require_zh=args.require_zh,
        )
    if args.command == "check":
        return check(repo, online=args.online, require_zh=args.require_zh)
    if args.command == "zh-commit":
        return zh_commit(repo, args.hash, args.summary, args.detail)
    parser.error(f"unknown command {args.command!r}")
    return 2
