"""Command line interface: ``python -m tools.changelog``.

Subcommands:

* ``generate [--online] [--limit N] [--check] [--require-zh]
  [--root-only|--bundle-only]`` — render and write the bilingual changelog
  to up to four targets: ``CHANGELOG.md`` / ``CHANGELOG.zh.md`` at the
  repository root and the end-user copies ``yate/resources/changelog.*.md``
  (``--check`` only compares released sections against disk and exits
  non-zero on drift; ``[Unreleased]`` may lag freely);
* ``check [--online] [--require-zh]`` — CI gate: exit 1 when a released
  section is missing or drifted on disk; prints ``SKIP`` (exit 0) when no
  git history is available; ``--require-zh`` additionally fails when any
  entry lacks a Chinese translation (gradual translation is the default);
* ``zh-commit <hash> <summary> [<detail>]`` — upsert one Chinese translation
  into ``tools/changelog/zh_overrides.json``.
"""

from __future__ import annotations

import argparse
import datetime
from collections.abc import Sequence
from pathlib import Path

from . import gitee, gitdata, render, segments, translations
from .classify import classify_commit, is_changelog_entry
from .model import Commit, ReleaseSegment
from .translations import OverrideEntry

_ROOT_FILES: dict[str, str] = {"en": "CHANGELOG.md", "zh": "CHANGELOG.zh.md"}
_BUNDLE_FILES: dict[str, str] = {
    "en": "yate/resources/changelog.en.md",
    "zh": "yate/resources/changelog.zh.md",
}
_LANGS = ("en", "zh")


def discover_repo_root() -> Path:
    """The repository root is two levels above this package."""
    return Path(__file__).resolve().parents[2]


def _output_paths(repo: Path, target: str) -> dict[str, Path]:
    files = _ROOT_FILES if target == "root" else _BUNDLE_FILES
    return {lang: repo / files[lang] for lang in _LANGS}


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
) -> tuple[list[ReleaseSegment], list[Commit], str]:
    """Collect git data and slice it into release segments.

    Returns the segments (newest first), all classified entries and the
    current ``__version__`` (the single version source).
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
    return release_segments, entries, current_version


def _missing_zh(
    entries: Sequence[Commit], overrides: dict[str, OverrideEntry]
) -> list[str]:
    return [c.short_sha for c in entries if c.short_sha not in overrides]


def _generated_notes(version: str) -> dict[str, str]:
    today = datetime.date.today().isoformat()
    return {
        "en": f"Generated from the git history on {today} · yate {version}",
        "zh": f"由 git 历史自动生成于 {today} · yate {version}",
    }


def generate(
    repo: Path,
    *,
    online: bool = False,
    limit: int | None = None,
    check: bool = False,
    require_zh: bool = False,
    targets: Sequence[str] = ("root", "bundle"),
    overrides_path: Path = translations.DEFAULT_OVERRIDES_PATH,
) -> int:
    """Render and write (or verify) the changelog files; returns exit code."""
    try:
        remote = _resolve_remote(repo)
        release_segments, entries, version = _build_segments(repo, limit=limit)
    except gitdata.GitError as exc:
        if check:
            # sdist unpack / source archive: nothing to gate against
            print(f"SKIP: no git history ({exc})")
            return 0
        print(f"error: {exc}")
        return 1

    overrides = translations.load_overrides(overrides_path)

    pushed: dict[str, bool] = {}
    if online and remote is not None:
        lookup = {c.short_sha: c.sha for c in entries}
        pushed = gitee.pushed_flags(remote, lookup)
        unpushed = [sha for sha, ok in pushed.items() if not ok]
        if unpushed:
            print(f"warning: {len(unpushed)} commit(s) not found on Gitee")

    notes = _generated_notes(version)
    docs: dict[tuple[str, str], str] = {}
    for target in targets:
        for lang in _LANGS:
            docs[(target, lang)] = render.render_document(
                release_segments,
                lang=lang,
                remote=remote,
                overrides=overrides,
                pushed=pushed,
                target=target,
                generated=notes[lang],
            )

    if check:
        problems: list[str] = []
        for target in targets:
            for lang in _LANGS:
                name = _BUNDLE_FILES[lang] if target == "bundle" else _ROOT_FILES[lang]
                path = _output_paths(repo, target)[lang]
                try:
                    current = path.read_text(encoding="utf-8")
                except OSError:
                    problems.append(f"{name}: missing on disk")
                    continue
                doc = docs[(target, lang)]
                # Only released sections gate freshness; [Unreleased] is a
                # moving window refreshed wholesale at each release.
                stale = render.released_sections_diff(current, doc)
                if stale:
                    problems.append(f"{name}: {', '.join(stale)}")
                lag = render.unreleased_lag(current, doc)
                if lag:
                    print(f"unreleased: {name} lags {lag} commit(s) "
                          "(refreshed at release)")
        if problems:
            print("stale changelog files — run generate:")
            for problem in problems:
                print(f"  - {problem}")
            return 1
        print("released changelog sections are up to date")
    else:
        written: list[str] = []
        for target in targets:
            for lang in _LANGS:
                path = _output_paths(repo, target)[lang]
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(docs[(target, lang)], encoding="utf-8")
                name = (
                    _BUNDLE_FILES[lang] if target == "bundle" else _ROOT_FILES[lang]
                )
                written.append(name)
        print(f"wrote {', '.join(written)}")

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
    group = gen.add_mutually_exclusive_group()
    group.add_argument(
        "--root-only", action="store_true",
        help="write only CHANGELOG.md / CHANGELOG.zh.md",
    )
    group.add_argument(
        "--bundle-only", action="store_true",
        help="write only yate/resources/changelog.*.md",
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
        targets: tuple[str, ...] = ("root", "bundle")
        if getattr(args, "root_only", False):
            targets = ("root",)
        elif getattr(args, "bundle_only", False):
            targets = ("bundle",)
        return generate(
            repo,
            online=args.online,
            limit=args.limit,
            check=args.check,
            require_zh=args.require_zh,
            targets=targets,
        )
    if args.command == "check":
        return check(repo, online=args.online, require_zh=args.require_zh)
    if args.command == "zh-commit":
        return zh_commit(repo, args.hash, args.summary, args.detail)
    parser.error(f"unknown command {args.command!r}")
    return 2
