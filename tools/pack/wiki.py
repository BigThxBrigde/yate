"""Bilingual wiki generator: ``python -m tools.pack wiki``.

Collects project markdown sources and publishes them as paired
``*.zh.md`` / ``*.en.md`` pages into the ``<repo>.wiki`` repository that
sits next to the main checkout (gitee/github wiki layout).

Sources (markdown only):

* ``.trae/<collection>/**`` except ``agents`` / ``rules`` / ``skills`` --
  files at depth 1 land in the wiki root, deeper files keep their
  subdirectory structure;
* ``yate/docs/*.zh.md`` (+ their ``*.en.md`` twins) and
  ``yate/resources/manual.*.md`` -- already bilingual, copied as-is
  (``changelog.*`` is excluded);
* ``Home`` / ``_Sidebar`` navigation is generated in both languages.

English pages for Chinese-only sources are maintained as ordinary files
inside the wiki repo -- they are the cache: the generator rebuilds every
Chinese page from its source but never overwrites a non-empty English
page unless ``--force`` re-translates a stale one.  Missing pages can be
filled by an external command via ``--translate-cmd`` (Chinese markdown
on stdin, English markdown on stdout).  Staleness is tracked by the
sha256 of the Chinese source, recorded in ``.translation-manifest.json``
at the wiki root; English pages written by other means (manual or agent
translation) are adopted on the next run.

``--check`` turns missing/stale English pages into exit code 1 (merge
gate); ``--push`` commits the wiki repo and pushes it to ``origin``
(gitee) and ``github`` (the remote is added when missing).
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from itertools import islice
from pathlib import Path
from typing import Final, cast

from rich.console import Console
from rich.markup import escape
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)

GITHUB_WIKI_URL: Final[str] = "https://github.com/BigThxBrigde/yate.wiki.git"

#: Name of the translation manifest written at the wiki repo root.
MANIFEST_NAME: Final[str] = ".translation-manifest.json"

WIKI_BRANCH: Final[str] = "master"

COMMIT_MESSAGE: Final[str] = "docs: regenerate wiki from sources"

#: Top-level ``.trae`` members that are never published.
EXCLUDED_TRAE_DIRS: Final[frozenset[str]] = frozenset({"agents", "rules", "skills"})

_ZH_SUFFIX: Final[str] = ".zh.md"
_EN_SUFFIX: Final[str] = ".en.md"
_MD_SUFFIX: Final[str] = ".md"

SECTION_GUIDES: Final[str] = "guides"
SECTION_NOTES: Final[str] = "notes"
SECTION_PLANS: Final[str] = "plans"
SECTION_SETS: Final[str] = "sets"
SECTION_REVIEWS: Final[str] = "reviews"

#: Navigation sections in their fixed sidebar/home order.
_SECTION_ORDER: Final[tuple[str, ...]] = (
    SECTION_GUIDES,
    SECTION_NOTES,
    SECTION_PLANS,
    SECTION_SETS,
    SECTION_REVIEWS,
)

_ZH_SECTION_LABELS: Final[dict[str, str]] = {
    SECTION_GUIDES: "指南",
    SECTION_NOTES: "架构与笔记",
    SECTION_PLANS: "重构计划",
    SECTION_SETS: "计划集",
    SECTION_REVIEWS: "评审记录",
}

_EN_SECTION_LABELS: Final[dict[str, str]] = {
    SECTION_GUIDES: "Guides",
    SECTION_NOTES: "Architecture notes",
    SECTION_PLANS: "Refactoring plans",
    SECTION_SETS: "Plan sets",
    SECTION_REVIEWS: "Review records",
}


@dataclass(frozen=True)
class WikiPage:
    """One published page: its zh/en wiki targets and the zh source.

    ``en_source`` is set only for already-bilingual sources (``yate/docs``
    topic pairs and the manual) whose English page is copied verbatim;
    for every other page the English counterpart is maintained in the
    wiki repo itself (cache / translation store).
    """

    zh_target: str
    en_target: str
    zh_source: Path
    en_source: Path | None
    section: str
    group: str | None


def _strip_md(name: str) -> str:
    """Return *name* without its trailing ``.md`` suffix (if any)."""
    return name[: -len(_MD_SUFFIX)] if name.endswith(_MD_SUFFIX) else name


def _collect_trae_dir(collection: Path) -> list[WikiPage]:
    """Collect one ``.trae`` subdirectory into wiki pages.

    Depth-1 files land in the wiki root; deeper files keep their
    subdirectory structure.  ``documents`` splits its depth-1 files
    (plain refactoring plans) from the nested plan sets, which get their
    own section and are grouped by their first directory component.
    """
    if collection.name == "documents":
        plain_section = SECTION_PLANS
    elif collection.name == "reviews":
        plain_section = SECTION_REVIEWS
    else:
        plain_section = SECTION_NOTES
    pages: list[WikiPage] = []
    for src in sorted(collection.rglob("*.md")):
        rel_parts = src.relative_to(collection).parts
        sub = "/".join(rel_parts[:-1])
        if collection.name == "documents" and len(rel_parts) > 1:
            section, group = SECTION_SETS, rel_parts[0]
        else:
            section, group = plain_section, None
        base = _strip_md(src.name)
        pages.append(
            WikiPage(
                zh_target=f"{sub}/{base}{_ZH_SUFFIX}" if sub else f"{base}{_ZH_SUFFIX}",
                en_target=f"{sub}/{base}{_EN_SUFFIX}" if sub else f"{base}{_EN_SUFFIX}",
                zh_source=src,
                en_source=None,
                section=section,
                group=group,
            )
        )
    return pages


def _collect_bilingual(base: Path) -> list[WikiPage]:
    """Collect ``*.zh.md``/``*.en.md`` pairs from *base* (guides section).

    A ``*.zh.md`` file without its English twin is still collected; it
    simply becomes a translation target like any other Chinese page.
    ``changelog.*`` files are excluded by requirement.
    """
    pages: list[WikiPage] = []
    if not base.is_dir():
        return pages
    for zh_src in sorted(base.glob(f"*{_ZH_SUFFIX}")):
        if zh_src.name.startswith("changelog."):
            continue
        stem = zh_src.name[: -len(_ZH_SUFFIX)]
        en_src = base / f"{stem}{_EN_SUFFIX}"
        pages.append(
            WikiPage(
                zh_target=f"{stem}{_ZH_SUFFIX}",
                en_target=f"{stem}{_EN_SUFFIX}",
                zh_source=zh_src,
                en_source=en_src if en_src.exists() else None,
                section=SECTION_GUIDES,
                group=None,
            )
        )
    return pages


def _assert_unique(pages: list[WikiPage]) -> None:
    """Raise :class:`ValueError` when two sources map to the same page."""
    seen: dict[str, str] = {}
    for page in pages:
        for target in (page.zh_target, page.en_target):
            if target in seen:
                raise ValueError(
                    f"wiki target collision on {target!r}: "
                    f"{seen[target]!r} vs {page.zh_source.name!r}"
                )
            seen[target] = page.zh_source.name


def collect_sources(repo_root: Path) -> list[WikiPage]:
    """Collect every publishable markdown source below *repo_root*.

    Walks ``.trae`` (excluding :data:`EXCLUDED_TRAE_DIRS`), the bilingual
    manuals under ``yate/docs`` and ``yate/resources``, and returns the
    page list in a stable (sorted) order with collision checking applied.
    """
    pages: list[WikiPage] = []
    trae = repo_root / ".trae"
    if trae.is_dir():
        members = sorted(
            p for p in trae.iterdir() if p.is_dir() and p.name not in EXCLUDED_TRAE_DIRS
        )
        for member in members:
            pages.extend(_collect_trae_dir(member))
    pages.extend(_collect_bilingual(repo_root / "yate" / "docs"))
    pages.extend(_collect_bilingual(repo_root / "yate" / "resources"))
    _assert_unique(pages)
    return pages


def _page_base(page: WikiPage) -> str:
    """Return the ASCII base name of a page (stem without language suffix)."""
    name = page.zh_target.rsplit("/", 1)[-1]
    return name[: -len(_ZH_SUFFIX)] if name.endswith(_ZH_SUFFIX) else name


def _page_title(source: Path) -> str:
    """Return the first ``# `` heading of *source* (fallback: file stem)."""
    with source.open(encoding="utf-8", errors="replace") as fh:
        for line in islice(fh, 30):
            if line.startswith("# "):
                return line[2:].strip()
    return source.stem


def _link(target: str) -> str:
    """Convert a wiki page target into a gitee/github wiki link (no .md)."""
    return target[: -len(_MD_SUFFIX)]


def run_git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run a git command inside *cwd*, capturing output as text."""
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def default_target(repo_root: Path) -> Path:
    """Derive the wiki repo path from the origin remote URL.

    ``https://gitee.com/<user>/yate.git`` next to the checkout yields
    ``<parent>/yate.wiki`` -- correct in worktrees too, whose directory
    name differs from the canonical repo name.  Without an origin
    remote, falls back to the checkout directory name.
    """
    proc = run_git(repo_root, "remote", "get-url", "origin")
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
        print("wiki: manifest corrupt, starting fresh", file=sys.stderr)
        return {}
    except OSError as exc:
        # A read error (permissions, disk trouble) must not silently reset
        # the sha256 records: the next store_manifest() would overwrite the
        # file and every stale marker would be lost.  Abort instead.
        print(f"wiki: manifest read error: {exc}", file=sys.stderr)
        sys.exit(1)
    if not isinstance(raw, dict):
        print("wiki: manifest is not an object, starting fresh", file=sys.stderr)
        return {}
    data = cast("dict[str, object]", raw)
    return {str(k): str(v) for k, v in data.items()}


def store_manifest(target: Path, manifest: dict[str, str]) -> None:
    """Write the sha256 manifest to *target* (sorted, stable diffs)."""
    text = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True)
    (target / MANIFEST_NAME).write_text(f"{text}\n", encoding="utf-8")


def prune_orphan_pages(target: Path, keep: set[str]) -> int:
    """Delete generated wiki pages whose source document no longer exists.

    *keep* holds the ``zh``/``en`` target names produced by this run.  Every
    other ``*.md`` file in *target* is a dead link left behind by a source
    that was renamed or deleted, so it is removed -- except the generated
    ``Home`` / ``_Sidebar`` navigation and anything inside ``.git``.  Returns
    the number of removed files.
    """
    protected = {"Home.md", "_Sidebar.md", "Home.en.md", "_Sidebar.en.md"}
    removed = 0
    for existing in target.rglob("*.md"):
        rel = existing.relative_to(target)
        if ".git" in rel.parts or rel.as_posix() in keep or existing.name in protected:
            continue
        existing.unlink()
        removed += 1
    return removed


def translate_via_cmd(text: str, translate_cmd: str) -> str | None:
    """Pipe Chinese markdown through the external translator command.

    Returns the translated text, or ``None`` when the command fails,
    times out, or produces empty output (the failure is reported on
    stderr).

    *translate_cmd* is executed through the shell so pipelines and
    redirections work; it must therefore come from a trusted source
    (the local CLI invocation / yaterc), never from untrusted input.
    """
    try:
        proc = subprocess.run(
            translate_cmd,
            shell=True,
            input=text,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=900,
        )
    except subprocess.TimeoutExpired:
        print("wiki: translate-cmd timed out after 900s", file=sys.stderr)
        return None
    if proc.returncode != 0 or not proc.stdout.strip():
        detail = (proc.stderr or proc.stdout).strip()
        print(f"wiki: translate-cmd failed (rc={proc.returncode}): {detail}", file=sys.stderr)
        return None
    return proc.stdout


def needs_translation(
    page: WikiPage,
    target: Path,
    manifest: dict[str, str],
    translate_all: bool,
) -> bool:
    """Return whether the main loop would translate *page*.

    Mirrors the in-loop decision for the pre-loop preview count.  Pages
    with an ``en_source`` twin are copied verbatim, never translated.  A
    missing or empty English page is pending; an adopted (no manifest
    record) or fresh page is pending only under *translate_all*; a stale
    page is always pending.

    Known edge: an ``en_source`` file deleted after collection (TOCTOU)
    counts as copied here while the main loop takes the translation path
    -- acceptable skew for a preview counter.
    """
    if page.en_source is not None:
        return False
    en_path = target / page.en_target
    if not en_path.exists() or en_path.stat().st_size == 0:
        return True
    digest = hashlib.sha256(page.zh_source.read_bytes()).hexdigest()
    recorded = manifest.get(page.zh_target)
    if recorded is None or recorded == digest:
        # Adopted (externally maintained) or fresh: pending only when
        # --translate-all re-translates every page.
        return translate_all
    return True


def push_wiki(target: Path) -> int:
    """Commit *target* and push it to both remotes; 0 on full success.

    An empty commit is tolerated (nothing to commit).  The ``github``
    remote is added on first use.
    """
    added = run_git(target, "add", "-A")
    if added.returncode != 0:
        detail = (added.stderr or added.stdout).strip()
        print(f"wiki: git add failed: {detail}", file=sys.stderr)
        return 1
    commit = run_git(target, "commit", "-m", COMMIT_MESSAGE)
    if commit.returncode != 0:
        out = f"{commit.stdout}{commit.stderr}".strip()
        if "nothing to commit" not in out and "nothing added to commit" not in out:
            print(f"wiki: commit failed: {out}", file=sys.stderr)
            return 1
        print(f"wiki: commit: {out}")
    if run_git(target, "remote", "get-url", "github").returncode != 0:
        run_git(target, "remote", "add", "github", GITHUB_WIKI_URL)
    failures = 0
    for remote in ("origin", "github"):
        pushed = run_git(target, "push", remote, WIKI_BRANCH)
        if pushed.returncode != 0:
            failures += 1
            detail = (pushed.stderr or pushed.stdout).strip()
            print(f"wiki: push {remote} failed: {detail}", file=sys.stderr)
    return 1 if failures else 0


def _nav_documents(pages: list[WikiPage]) -> tuple[str, str, str, str]:
    """Render Home and _Sidebar in both languages.

    Returns ``(home_zh, sidebar_zh, home_en, sidebar_en)``.  Guides
    entries carry an inline EN twin link; plan sets are grouped under
    their directory name in Home and collapsed to a single overview line
    in the sidebar.
    """
    by_section: dict[str, list[WikiPage]] = {section: [] for section in _SECTION_ORDER}
    for page in pages:
        by_section[page.section].append(page)
    for bucket in by_section.values():
        bucket.sort(key=lambda p: p.zh_target)
    groups = sorted(
        {p.group for p in by_section[SECTION_SETS] if p.group is not None},
        key=str.lower,
    )

    def zh_entry(page: WikiPage, with_en: bool) -> str:
        line = f"- [{_page_title(page.zh_source)}]({_link(page.zh_target)})"
        return f"{line} · [EN]({_link(page.en_target)})" if with_en else line

    def en_entry(page: WikiPage) -> str:
        return f"- [{_page_base(page)}]({_link(page.en_target)})"

    home_zh: list[str] = []
    sidebar_zh: list[str] = []
    home_en: list[str] = []
    sidebar_en: list[str] = []
    for section in _SECTION_ORDER:
        bucket = by_section[section]
        if not bucket:
            continue
        home_zh.append(f"## {_ZH_SECTION_LABELS[section]}")
        home_en.append(f"## {_EN_SECTION_LABELS[section]}")
        sidebar_zh.append(f"- **{_ZH_SECTION_LABELS[section]}**")
        sidebar_en.append(f"- **{_EN_SECTION_LABELS[section]}**")
        if section == SECTION_SETS:
            for group in groups:
                members = [p for p in bucket if p.group == group]
                home_zh.append(f"### {group}")
                home_en.append(f"### {group}")
                home_zh.extend(zh_entry(p, False) for p in members)
                home_en.extend(en_entry(p) for p in members)
                overview = next(
                    (p for p in members if p.zh_target == f"{group}/overview{_ZH_SUFFIX}"),
                    None,
                )
                head = f"  - **{group}**"
                tail = f"（{len(members)} 篇）"
                if overview is not None:
                    sidebar_zh.append(f"{head} — [总纲]({_link(overview.zh_target)}){tail}")
                    sidebar_en.append(
                        f"  - **{group}** — [overview]({_link(overview.en_target)})"
                        f" ({len(members)} pages)"
                    )
                else:
                    sidebar_zh.append(f"{head}{tail}")
                    sidebar_en.append(f"  - **{group}** ({len(members)} pages)")
        else:
            with_en = section == SECTION_GUIDES
            home_zh.extend(zh_entry(p, with_en) for p in bucket)
            home_en.extend(en_entry(p) for p in bucket)
            sidebar_zh.extend(("  " + zh_entry(p, with_en)) for p in bucket)
            sidebar_en.extend(("  " + en_entry(p)) for p in bucket)
        home_zh.append("")
        home_en.append("")

    home_zh_doc = "\n".join(
        [
            "# yate Wiki",
            "",
            "yate（yet another terminal editor）项目的文档 Wiki，由"
            " `python -m tools.pack wiki` 从仓库源文档生成：中文页自源文档重建，"
            "英文页为对应译本。",
            "",
            *home_zh,
            "",
        ]
    )
    home_en_doc = "\n".join(
        [
            "# yate Wiki",
            "",
            "Documentation wiki for yate, yet another terminal editor built on"
            " Textual. Generated by `python -m tools.pack wiki` from the repo"
            " sources: Chinese pages are rebuilt from the sources and English"
            " pages are their translations.",
            "",
            *home_en,
            "",
        ]
    )
    sidebar_zh_doc = "\n".join([*sidebar_zh, ""])
    sidebar_en_doc = "\n".join([*sidebar_en, ""])
    return home_zh_doc, sidebar_zh_doc, home_en_doc, sidebar_en_doc


def run(
    target: Path,
    translate_cmd: str | None,
    *,
    force: bool = False,
    translate_all: bool = False,
    check: bool = False,
    push: bool = False,
    repo_root: Path | None = None,
) -> int:
    """Generate the wiki into *target* and return the process exit code.

    Chinese pages are always rebuilt from their sources.  With
    *translate_cmd* set, pages whose English page is missing or stale
    (Chinese source changed) are (re-)translated through it; fresh pages
    are kept as-is.  Pass *translate_all* to also re-translate fresh
    pages, overwriting their existing English pages.  Without a hook,
    missing/stale pages are reported instead of translated.  *force* is
    accepted for backward compatibility only and no longer changes the
    outcome.  With *check* the exit code is 1 while any English page is
    missing or stale; with *push* the wiki repo is committed and pushed
    (skipped when the check fails).
    """
    root = repo_root if repo_root is not None else Path(__file__).resolve().parents[2]
    pages = collect_sources(root)
    target.mkdir(parents=True, exist_ok=True)
    # The manifest carries over across runs: stale pages keep their old
    # recorded hash so a later --force run still sees them as stale instead
    # of adopting the outdated English page as externally maintained.
    manifest = dict(load_manifest(target))
    if translate_all and translate_cmd is None:
        print(
            "wiki: --translate-all has no effect without --translate-cmd",
            file=sys.stderr,
        )
    console = Console(file=sys.stderr)
    run_started = time.monotonic()
    pending = 0
    if translate_cmd is not None:
        pending = sum(
            1
            for page in pages
            if needs_translation(page, target, manifest, translate_all)
        )
        if pending:
            console.print(f"wiki: {pending} page(s) to translate", markup=False)
        else:
            console.print(
                f"wiki: nothing to translate ({len(pages)} pages up to date)",
                markup=False,
            )
    kept = 0
    translated = 0
    missing: list[str] = []
    stale: list[str] = []
    progress = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console,
    )
    overall = progress.add_task("translating", total=pending)
    active = pending > 0
    if active:
        progress.start()
    try:
        attempted = 0
        for page in pages:
            zh_bytes = page.zh_source.read_bytes()
            zh_path = target / page.zh_target
            zh_path.parent.mkdir(parents=True, exist_ok=True)
            zh_path.write_bytes(zh_bytes)
            digest = hashlib.sha256(zh_bytes).hexdigest()
            en_path = target / page.en_target
            en_path.parent.mkdir(parents=True, exist_ok=True)
            en_bytes: bytes | None = None
            if page.en_source is not None:
                # TOCTOU: _collect_bilingual verified en_source with exists()
                # at collection time, but the file may be deleted before this
                # read; treat the failure as a missing page (translation path
                # below) instead of crashing the whole run.
                try:
                    en_bytes = page.en_source.read_bytes()
                except OSError:
                    en_bytes = None
            if en_bytes is not None:
                en_path.write_bytes(en_bytes)
                manifest.pop(page.zh_target, None)
                kept += 1
                continue
            recorded = manifest.get(page.zh_target)
            has_en = en_path.exists() and en_path.stat().st_size > 0
            is_stale = has_en and recorded is not None and recorded != digest
            if has_en and not is_stale:
                # Fresh or externally maintained (e.g. agent-translated).
                if translate_cmd is None or not translate_all:
                    manifest[page.zh_target] = digest
                    kept += 1
                    continue
                # --translate-all re-translates even fresh pages through the
                # hook, overwriting their English pages.  The digest is only
                # recorded after a successful re-translation below, so a failed
                # one does not silently bless an outdated English page.
            elif translate_cmd is None:
                # No translator available: report the gap so --check gates on it.
                if not has_en:
                    missing.append(page.en_target)
                else:
                    stale.append(page.en_target)
                continue
            progress.update(
                overall, description=f"translating {escape(page.en_target)}"
            )
            started = time.monotonic()
            attempted += 1
            english = translate_via_cmd(
                zh_bytes.decode("utf-8", errors="replace"), translate_cmd
            )
            if english is None:
                # An existing page whose re-translation failed is still stale,
                # not missing -- report it under the right heading.
                elapsed = time.monotonic() - started
                console.print(
                    f"wiki: [{attempted}/{pending}] {page.en_target} failed"
                    f" ({elapsed:.1f}s)",
                    markup=False,
                )
                if has_en:
                    stale.append(page.en_target)
                else:
                    missing.append(page.en_target)
                progress.advance(overall)
                continue
            en_path.write_text(english, encoding="utf-8")
            manifest[page.zh_target] = digest
            translated += 1
            progress.advance(overall)
    finally:
        if active:
            progress.stop()
    collected = {page.zh_target for page in pages}
    manifest = {key: value for key, value in manifest.items() if key in collected}
    # Sources that vanished must not leave dead links behind in the wiki.
    expected = {page.zh_target for page in pages} | {page.en_target for page in pages}
    orphans = prune_orphan_pages(target, expected)
    if orphans:
        print(f"wiki: removed {orphans} orphan page(s) with no source document")

    home_zh, sidebar_zh, home_en, sidebar_en = _nav_documents(pages)
    (target / "Home.md").write_text(home_zh, encoding="utf-8")
    (target / "_Sidebar.md").write_text(sidebar_zh, encoding="utf-8")
    (target / "Home.en.md").write_text(home_en, encoding="utf-8")
    (target / "_Sidebar.en.md").write_text(sidebar_en, encoding="utf-8")
    store_manifest(target, manifest)

    print(
        f"wiki: {len(pages)} pages -> {target} "
        f"(en kept {kept} / translated {translated} / "
        f"missing {len(missing)} / stale {len(stale)}) in {time.monotonic() - run_started:.1f}s"
    )
    for name in missing:
        print(f"  missing en: {name}")
    for name in stale:
        print(f"  stale en: {name}")
    exit_code = 0
    if missing or stale:
        exit_code = 1 if check else 0
    if push:
        if exit_code == 0:
            exit_code = push_wiki(target)
        else:
            print("wiki: push skipped (--check found missing/stale pages)", file=sys.stderr)
    return exit_code
