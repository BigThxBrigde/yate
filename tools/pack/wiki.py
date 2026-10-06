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

Translation runs through a thread pool: pending pages are split into
tasks of at most :data:`BATCH_SIZE` documents and at most
``cpu_count() * 2`` tasks run concurrently (issue IKJPEK).  The live
progress advances page by page -- one row per batch naming the page in
flight, plus the overall row with its own ``pages done / batches queued /
workers`` text -- and a permanent line is printed per finished batch and
per failed page.  ``--jobs`` lowers that ceiling (it can never raise it),
and up to ``jobs * 10`` translators may therefore run at the same time.
Every failure carries a stable ``WIKI-*`` code from
:mod:`tools.pack.errors` -- a vanished Chinese source aborts the run with
``error[WIKI-0102]`` instead of a traceback.
"""

from __future__ import annotations

import hashlib
import json
import os
import queue
import subprocess
import sys
import threading
import time
from collections.abc import Sequence
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from enum import StrEnum
from itertools import islice
from pathlib import Path
from typing import Final, cast

from rich.console import Console
from rich.markup import escape
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)

from .. import _util
from . import errors
from .errors import Code, PackError

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

#: Wall clock budget for one git command (a first ``git push`` of a large
#: wiki repo included): a hung git must not block the run forever.
GIT_TIMEOUT_S: Final[float] = 120.0

#: Wall clock budget for one page translation.
TRANSLATE_TIMEOUT_S: Final[float] = 900.0

#: Exit codes that mean "the console interrupted this child", not "the
#: translation failed".  A ``Ctrl+C`` in the wiki run is broadcast to the
#: whole process group, so every translator dies of it; Windows reports
#: that as ``STATUS_CONTROL_C_EXIT`` (``0xC000013A``), POSIX as
#: ``-SIGINT``, and :mod:`tools.translate` maps a cleanly handled
#: interrupt to 130.  The signed form of ``0xC000013A`` is listed too
#: because a shell reports it either way depending on how it is invoked.
_INTERRUPT_EXIT_CODES: Final[frozenset[int]] = frozenset(
    {130, 0xC000013A, 0xC000013A - 0x100000000, -2}
)

#: Documents per translation task.  A task is the unit handed to a pool
#: worker, so a pool failure costs at most this many translations.
BATCH_SIZE: Final[int] = 10

#: Sentinel hook for :func:`needs_translation`: the preview is only asked
#: when a translator is wired up, so any non-``None`` value says "present".
_PREVIEW_TRANSLATE_HOOK: Final[str] = "<preview-hook>"


class WikiError(PackError):
    """A wiki operation failed and the run must abort.

    A :class:`tools.pack.errors.PackError` carrying a ``WIKI-*`` code: raised
    by library code (never ``sys.exit``); the CLI layer
    (:mod:`tools.pack.cli`) catches it, renders ``error[<code>]: <message>``
    on stderr and maps it to exit code 1 -- mirroring
    :class:`tools.translate.runner.TranslateError`.
    """

    def __init__(
        self,
        message: str,
        *,
        code: Code = Code.WIKI_SOURCE_UNREADABLE,
        hint: str | None = None,
    ) -> None:
        super().__init__(code, message, hint=hint)


_EN_SECTION_LABELS: Final[dict[str, str]] = {
    SECTION_GUIDES: "Guides",
    SECTION_NOTES: "Architecture notes",
    SECTION_PLANS: "Refactoring plans",
    SECTION_SETS: "Plan sets",
    SECTION_REVIEWS: "Review records",
}


def _read_source_bytes(path: Path, *, code: Code = Code.WIKI_ZH_SOURCE_MISSING) -> bytes:
    """Read a collected source file, reporting absence as a coded error.

    Sources can disappear between collection and use (issue IKJPEK: a plan
    renamed mid-run); a bare ``FileNotFoundError`` used to escape as a full
    traceback, so the run now aborts with ``error[WIKI-0102]`` instead.

    Any other :class:`OSError` -- permissions, a spinning disk, a network
    share -- reports ``WIKI-0103`` instead: it means "unreadable", and
    calling it "vanished" sent the reader after a rename that never
    happened (review R-04).
    """
    try:
        return path.read_bytes()
    except FileNotFoundError as exc:
        raise WikiError(
            f"Chinese source vanished: {path.name}",
            code=code,
            hint="re-run once the source tree is complete",
        ) from exc
    except OSError as exc:
        raise WikiError(
            f"cannot read source {path.name}: {exc}",
            code=Code.WIKI_SOURCE_UNREADABLE,
            hint="check file permissions and disk availability",
        ) from exc


def _write_page_bytes(path: Path, data: bytes) -> None:
    """Write a generated page, reporting failures as ``error[WIKI-0106]``."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    except OSError as exc:
        raise WikiError(f"cannot write page {path.name}: {exc}", code=Code.WIKI_PAGE_WRITE) from exc


def _write_page_text(path: Path, text: str, *, code: Code = Code.WIKI_PAGE_WRITE) -> None:
    """Write a generated page as UTF-8 text.

    *code* lets the manifest report its own failure (``WIKI-0105``): the
    store is read back on the next run, so a write that failed silently
    there must be distinguishable from an ordinary page write (review
    R-03 -- ``WIKI_MANIFEST_WRITE`` existed but nothing ever raised it).
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    except OSError as exc:
        raise WikiError(f"cannot write page {path.name}: {exc}", code=code) from exc


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
    """Raise :class:`WikiError` when two sources map to the same page."""
    seen: dict[str, str] = {}
    for page in pages:
        for target in (page.zh_target, page.en_target):
            if target in seen:
                raise WikiError(
                    f"wiki target collision on {target!r}: "
                    f"{seen[target]!r} vs {page.zh_source.name!r}",
                    code=Code.WIKI_TARGET_COLLISION,
                    hint="rename one of the colliding source documents",
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
    """Run a git command inside *cwd*, capturing output as text.

    The command is bounded by :data:`GIT_TIMEOUT_S`; on timeout the child is
    killed and a synthetic failed ``CompletedProcess`` (exit code 124, the
    ``timeout(1)`` convention) is returned, so every caller reports a clean
    stderr error instead of hanging forever -- mirroring
    :func:`tools.changelog.gitdata.run_git`.
    """
    try:
        return subprocess.run(
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
    except subprocess.TimeoutExpired:
        detail = f"git timed out after {GIT_TIMEOUT_S:g}s: git {' '.join(args)}"
        return subprocess.CompletedProcess(args, 124, "", detail)


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
        try:
            existing.unlink()
        except OSError as exc:
            raise WikiError(
                f"cannot remove orphan page {rel.as_posix()}: {exc}",
                code=Code.WIKI_PRUNE_FAILED,
            ) from exc
        removed += 1
    return removed


#: Terminal write policy for :func:`translate_via_cmd` failures.  ``"print"``
#: is the serial default; the parallel stage flips it to ``"collect"`` so a
#: worker never writes into the live region rich is repainting -- the main
#: thread drains the queue and prints instead.  Only the main thread mutates
#: the mode, and the queue is only ever appended to (atomic under the GIL)
#: or fully drained.
#:
#: A queue rather than a list on purpose (review R-05): a worker that
#: finishes after ``pool.shutdown(wait=False)`` used to append to a list the
#: main thread had already cleared, so the message vanished.  The queue is
#: drained once, with the serial policy restored first, so anything that
#: arrives later writes its own line instead of piling up unread.
_emit_mode: str = "print"

_COLLECTED_FAILURES: queue.SimpleQueue[str] = queue.SimpleQueue()


def _emit_translate_failure(message: str) -> None:
    """Report one translation failure honouring :data:`_emit_mode`.

    Both routes emit the same plain text: the collected one goes through a
    rich console, so it asks for no highlighting -- otherwise a failure
    printed after the run would carry ANSI styling on a terminal while the
    same line during the run does not (review R-22).
    """
    if _emit_mode == "collect":
        _COLLECTED_FAILURES.put(message)
        return
    print(message, file=sys.stderr)


def _drain_collected_failures() -> list[str]:
    """Take every queued failure message, leaving the queue empty."""
    messages: list[str] = []
    while True:
        try:
            messages.append(_COLLECTED_FAILURES.get_nowait())
        except queue.Empty:
            return messages


#: Set while a translation stage tears down, so the translators still in
#: flight terminate their child instead of running a full page (review
#: R-15).  Without it the main thread could stop waiting but the pool
#: threads kept blocking in :func:`subprocess.run`, and CPython joins them
#: at interpreter teardown -- the process lingered for up to one page per
#: running worker (measured 0.6 s to 3.1 s with a 3 s page).  Cleared by the
#: next run before it installs the collect policy.
_STOP_TRANSLATIONS: threading.Event = threading.Event()

#: How often a running translator checks for the stop signal.  Small enough
#: that an interrupt is honoured promptly, large enough to stay cheap.
_STOP_POLL_S: Final[float] = 0.2


def _run_translate(text: str, translate_cmd: str) -> tuple[str | None, str | None]:
    """Run the external translator; returns ``(english, failure_message)``.

    The shell, the stdin/stdout protocol and :data:`TRANSLATE_TIMEOUT_S` are
    unchanged -- only the reporting is factored out so the caller decides
    where the message goes.

    Raises :exc:`KeyboardInterrupt` when the child died *because* the
    console was interrupted (see :data:`_INTERRUPT_EXIT_CODES`), and also
    when the run is being torn down while this child is still alive -- a
    translator that ignores the console event would otherwise keep the
    process alive for the rest of its page.
    """
    started = time.monotonic()
    try:
        proc = subprocess.Popen(
            translate_cmd,
            shell=True,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError as exc:
        return None, (
            f"error[{Code.WIKI_TRANSLATE_FAILED}]: cannot start translate-cmd"
            f" ({exc})"
        )
    try:
        if proc.stdin is not None:
            proc.stdin.write(text)
            proc.stdin.close()
        while True:
            try:
                stdout, stderr = proc.communicate(timeout=_STOP_POLL_S)
                break
            except subprocess.TimeoutExpired:
                # Only the parallel stage listens: a direct library call
                # runs with the serial policy, where a stop left behind by
                # an earlier run must not cancel anything.
                if _STOP_TRANSLATIONS.is_set() and _emit_mode == "collect":
                    raise KeyboardInterrupt from None
                if time.monotonic() - started >= TRANSLATE_TIMEOUT_S:
                    raise subprocess.TimeoutExpired(
                        cmd=translate_cmd, timeout=TRANSLATE_TIMEOUT_S
                    ) from None
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        return None, (
            f"error[{Code.WIKI_TRANSLATE_TIMEOUT}]: translate-cmd timed out"
            f" after {TRANSLATE_TIMEOUT_S:g}s"
        )
    except BaseException:
        proc.kill()
        proc.wait()
        raise
    if proc.returncode in _INTERRUPT_EXIT_CODES:
        raise KeyboardInterrupt
    if proc.returncode != 0 or not (stdout or "").strip():
        detail = (stderr or stdout or "").strip()
        return None, (
            f"error[{Code.WIKI_TRANSLATE_FAILED}]: translate-cmd failed"
            f" (rc={proc.returncode}): {detail}"
        )
    return stdout, None


def translate_via_cmd(text: str, translate_cmd: str) -> str | None:
    """Pipe Chinese markdown through the external translator command.

    Returns the translated text, or ``None`` when the command fails,
    times out, or produces empty output (the failure is reported on
    stderr).

    *translate_cmd* is executed through the shell so pipelines and
    redirections work; it must therefore come from a trusted source
    (the local CLI invocation / yaterc), never from untrusted input.

    A per-page failure is reported as ``error[WIKI-0201]`` /
    ``error[WIKI-0202]`` and degraded to ``None`` -- one bad page never
    aborts the whole run, and ``--check`` still gates on it.  A console
    interrupt is the exception: it raises :exc:`KeyboardInterrupt` out of
    :func:`_run_translate` so the run stops instead of reporting a failed
    page per remaining document.
    """
    english, failure = _run_translate(text, translate_cmd)
    if failure is not None:
        _emit_translate_failure(failure)
    return english


class _PageState(StrEnum):
    """The one verdict about a page's English counterpart (review R-06).

    :func:`needs_translation` (the preview) and :func:`_prepare_pages` (the
    rebuild) used to spell this rule out twice, so the preview count and
    the real loop could drift apart.  Both now ask this enum.

    Only pages that reach the translator have a verdict here: a bilingual
    twin is copied verbatim before either caller gets that far, which is
    why there is no "copied" member (review R-12 -- it had no caller).
    """

    FRESH = "fresh"
    MISSING = "missing"
    STALE = "stale"
    TRANSLATE = "translate"


def _has_english_page(en_path: Path) -> bool:
    """Return whether *en_path* holds a non-empty English page."""
    return en_path.exists() and en_path.stat().st_size > 0


def _translation_state(
    *,
    has_en: bool,
    recorded: str | None,
    digest: str,
    translate_cmd: str | None,
    translate_all: bool,
) -> _PageState:
    """Classify one page from the facts both callers already know.

    The single source of truth for "fresh / missing / stale / translate".
    *translate_cmd* is ``None`` when no translator is wired up: a page
    that would need one is then reported (missing or stale) rather than
    queued.
    """
    if not has_en:
        return _PageState.MISSING
    if recorded is not None and recorded != digest:
        return _PageState.STALE
    # Fresh or adopted (no manifest record): --translate-all still re-runs
    # it, otherwise the existing English page is kept as-is.
    if translate_cmd is None or not translate_all:
        return _PageState.FRESH
    return _PageState.TRANSLATE


def needs_translation(
    page: WikiPage,
    target: Path,
    manifest: dict[str, str],
    translate_all: bool,
) -> bool:
    """Return whether the main loop would translate *page*.

    A thin preview over :func:`_translation_state`, kept because the
    decision matrix is worth stating on its own: pages with an
    ``en_source`` twin are copied verbatim, never translated; a missing or
    empty English page is pending; an adopted (no manifest record) or
    fresh page is pending only under *translate_all*; a stale page is
    always pending.

    **No production caller** (review R-14): ``run()`` prepares pages with
    :func:`_prepare_pages`, which asks the same verdict internally, so this
    function is exercised by the test suite and by any external preview.
    It stays because the matrix test is the readable statement of the
    rule -- deleting it would move those assertions onto a private helper
    without making the rule any clearer.  If a caller ever needs it, the
    sentinel below is the seam to revisit.

    *translate_cmd* is assumed to be present -- this is only ever asked
    when a hook is wired up.

    Known edge: an ``en_source`` file deleted after collection (TOCTOU)
    counts as copied here while the main loop takes the translation path
    -- acceptable skew for a preview counter.
    """
    # Same short-circuit as the original implementation: a page that is
    # already decided must not need its source read (a vanished source
    # would raise here, which the caller never had to expect).
    if page.en_source is not None:
        return False
    if not _has_english_page(target / page.en_target):
        return True
    state = _translation_state(
        has_en=True,
        recorded=manifest.get(page.zh_target),
        digest=hashlib.sha256(_read_source_bytes(page.zh_source)).hexdigest(),
        translate_cmd=_PREVIEW_TRANSLATE_HOOK,
        translate_all=translate_all,
    )
    return state is _PageState.TRANSLATE or state is _PageState.STALE


def push_wiki(target: Path) -> int:
    """Commit *target* and push it to both remotes; 0 on full success.

    An empty commit is tolerated (nothing to commit).  The ``github``
    remote is added on first use.
    """
    added = run_git(target, "add", "-A")
    if added.returncode != 0:
        detail = (added.stderr or added.stdout).strip()
        errors.report(PackError(Code.WIKI_GIT_FAILED, f"git add failed: {detail}"))
        return 1
    commit = run_git(target, "commit", "-m", COMMIT_MESSAGE)
    if commit.returncode != 0:
        out = f"{commit.stdout}{commit.stderr}".strip()
        if "nothing to commit" not in out and "nothing added to commit" not in out:
            errors.report(PackError(Code.WIKI_GIT_FAILED, f"commit failed: {out}"))
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
            errors.report(
                PackError(Code.WIKI_GIT_FAILED, f"push {remote} failed: {detail}")
            )
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


@dataclass(frozen=True)
class _PagePlan:
    """One page queued for translation, with everything a worker needs.

    The Chinese text is decoded once during preparation so workers never
    touch the filesystem: sources can vanish mid-run and that must fail
    before any translation starts (issue IKJPEK).
    """

    page: WikiPage
    digest: str
    text: str
    has_en: bool


@dataclass(frozen=True)
class _PageOutcome:
    """A worker's report for one planned page.

    *error* holds anything the worker caught (``BaseException`` included,
    see :func:`_run_batch`); the main thread re-raises it so ``Ctrl+C``
    still reaches :func:`tools.pack.cli.main` and maps to exit code 130.
    """

    plan: _PagePlan
    english: str | None
    error: BaseException | None
    elapsed: float


@dataclass(frozen=True)
class _TranslationReport:
    """Aggregated result of the parallel translation stage."""

    translated: int
    digests: dict[str, str]
    missing: list[str]
    stale: list[str]


def cpu_count() -> int:
    """Return the usable core count (never 0)."""
    return os.cpu_count() or 1


def job_ceiling(*, cores: int | None = None) -> int:
    """Return the hard concurrency ceiling: CPU cores times two (issue IKJPEK)."""
    return max(1, (cpu_count() if cores is None else cores) * 2)


def resolve_jobs(jobs: int | None, *, cores: int | None = None) -> int:
    """Clamp *jobs* into ``[1, cores * 2]``; ``None`` means the ceiling itself.

    This is the single place the concurrency cap is enforced, so neither a
    generous ``--jobs`` nor a machine with many cores can start more than
    twice the core count of translators.
    """
    limit = job_ceiling(cores=cores)
    if jobs is None:
        return limit
    return max(1, min(jobs, limit))


def chunk_pages[T](items: Sequence[T], size: int = BATCH_SIZE) -> list[list[T]]:
    """Split *items* into consecutive chunks of at most *size* entries.

    The task-pool unit: one chunk is one unit of work handed to a pool
    worker, so a worker failure or an interrupt costs at most *size*
    translations.
    """
    if size < 1:
        raise ValueError(f"chunk size must be >= 1, got {size}")
    return [list(items[start : start + size]) for start in range(0, len(items), size)]


@dataclass
class _ProgressBoard:
    """Page-level progress reporting for the translation pool.

    Every batch row and the overall row move as each page lands, and the
    overall row also carries its own description (``pages done · batches
    queued · workers``): the bar and the sentence next to it used to
    disagree for minutes, because the text was only refreshed when a whole
    batch reported back.

    Workers call :meth:`page_started` / :meth:`page_done`; the main thread
    calls :meth:`batch_finished`.  rich updates task fields under
    ``Progress._lock`` and paints frames from its own refresh thread under
    ``Live._lock``, so one frame may show a row one step ahead of another
    -- cosmetic only.  Keeping the updates on the workers is what makes the
    bar live at all; the alternative (the main thread draining the pool)
    would mean either latency or a rewrite of the interrupt path.

    *queued* is the one field the main thread mutates; every other field is
    set once at construction.
    """

    progress: Progress
    overall: TaskID
    batch_tasks: dict[int, TaskID]
    batch_count: int
    total_pages: int
    workers: int
    queued: int

    def _description(self) -> str:
        """Render the overall row text from the live counters."""
        done = int(self.progress.tasks[self.overall].completed)
        return (
            f"translating {done}/{self.total_pages} page(s)"
            f" · {self.queued} batch(es) queued · {self.workers} worker(s)"
        )

    def page_started(self, index: int, page: WikiPage) -> None:
        """Show which page batch *index* is translating right now."""
        self.progress.update(
            self.batch_tasks[index],
            description=f"batch {index}/{self.batch_count} · {escape(page.en_target)}",
        )

    def page_done(self, index: int) -> None:
        """Advance the batch row and the overall row by one finished page.

        The text is rendered *after* the advance, never as an argument of
        the same call: arguments are evaluated first, so passing it inline
        would publish the pre-advance count and leave the row permanently
        one page behind its own bar.
        """
        self.progress.advance(self.batch_tasks[index])
        self.progress.update(self.overall, advance=1)
        self.progress.update(self.overall, description=self._description())

    def batch_finished(self) -> None:
        """Note that one batch reported back: one batch less queued."""
        self.queued -= 1
        self.progress.update(self.overall, description=self._description())


def _run_batch(
    plans: Sequence[_PagePlan],
    translate_cmd: str,
    stop: threading.Event,
    index: int,
    board: _ProgressBoard,
) -> list[_PageOutcome]:
    """Translate one batch, capturing every failure as an outcome value.

    Nothing may propagate out of a pool worker: an escaping exception is
    turned into a failed ``Future`` by the pool, so the main thread would
    see it at ``future.result()`` -- outside the ``outcome.error`` branch
    below, skipping both ``stop.set()`` and the cancellation of the queued
    batches.  A ``KeyboardInterrupt`` raised in a worker must be re-raised
    by the main thread anyway.  Threads are the right primitive because the
    work is a blocking external subprocess (:func:`translate_via_cmd`),
    which holds no shared interpreter state.

    *stop* is checked before every page: once the main thread cancels the
    run (an interrupt in any worker), a batch stops instead of starting the
    next translation -- otherwise ``Ctrl+C`` would still pay for every
    page of every queued batch.

    *board* moves the progress rows for batch *index* as each page starts
    and lands, so the bar tracks single pages; a page whose translation
    failed still counts as finished.  The page that raised is *not* counted
    -- its outcome travels to the main thread, which re-raises and tears
    the display down anyway.  The reporting callbacks sit inside the same
    ``try`` as the translation: they only touch rich's in-memory task
    fields, and their keys come from :attr:`_ProgressBoard.batch_tasks`,
    the same mapping the pool submits from, so a failure here means a bug
    in rich rather than a mismatch of batch indices.
    """
    outcomes: list[_PageOutcome] = []
    for plan in plans:
        if stop.is_set():
            break
        started = time.monotonic()
        try:
            board.page_started(index, plan.page)
            english: str | None = translate_via_cmd(plan.text, translate_cmd)
            board.page_done(index)
            outcomes.append(
                _PageOutcome(plan, english, None, time.monotonic() - started)
            )
        except BaseException as exc:  # noqa: BLE001 - a worker must never escape
            stop.set()
            outcomes.append(_PageOutcome(plan, None, exc, time.monotonic() - started))
            break
    return outcomes


def _prepare_pages(
    pages: Sequence[WikiPage],
    target: Path,
    manifest: dict[str, str],
    *,
    translate_cmd: str | None,
    translate_all: bool,
) -> tuple[int, list[_PagePlan], list[str], list[str]]:
    """Rebuild Chinese pages and decide what still needs translating.

    Returns ``(kept, plans, missing, stale)``.  Mirrors
    :func:`needs_translation` for the preview count, but performs the work:
    every Chinese page is rewritten from its source, bilingual twins are
    copied verbatim, and only the pages that really need a translator are
    planned.  *manifest* is updated in place for kept pages; translations
    are recorded by the caller once they actually succeed.
    """
    kept = 0
    plans: list[_PagePlan] = []
    missing: list[str] = []
    stale: list[str] = []
    for page in pages:
        zh_bytes = _read_source_bytes(page.zh_source)
        digest = hashlib.sha256(zh_bytes).hexdigest()
        _write_page_bytes(target / page.zh_target, zh_bytes)
        en_path = target / page.en_target
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
            _write_page_bytes(en_path, en_bytes)
            manifest.pop(page.zh_target, None)
            kept += 1
            continue
        recorded = manifest.get(page.zh_target)
        has_en = _has_english_page(en_path)
        state = _translation_state(
            has_en=has_en,
            recorded=recorded,
            digest=digest,
            translate_cmd=translate_cmd,
            translate_all=translate_all,
        )
        if state is _PageState.FRESH:
            # Fresh or externally maintained (e.g. agent-translated).
            manifest[page.zh_target] = digest
            kept += 1
            continue
        if translate_cmd is None and state in (_PageState.MISSING, _PageState.STALE):
            # No translator available: report the gap so --check gates on it.
            if state is _PageState.MISSING:
                missing.append(page.en_target)
            else:
                stale.append(page.en_target)
            continue
        # TRANSLATE -- or MISSING/STALE with a hook wired up.  A stale page
        # keeps its old digest out of the manifest until the new
        # translation lands, so a failed re-translation never blesses an
        # outdated English page.
        plans.append(
            _PagePlan(
                page=page,
                digest=digest,
                text=zh_bytes.decode("utf-8", errors="replace"),
                has_en=has_en,
            )
        )
    return kept, plans, missing, stale


def _translate_pending(
    plans: Sequence[_PagePlan],
    translate_cmd: str,
    *,
    target: Path,
    jobs: int | None,
    console: Console,
) -> _TranslationReport:
    """Translate *plans* through a bounded thread pool, writing into *target*.

    The plans are split into :data:`BATCH_SIZE`-sized tasks; at most
    :func:`resolve_jobs` of them run at once and every state transition is
    reported live: one overall task (pages done / batches queued / worker
    count), one task per batch that advances page by page, a permanent line
    per finished batch and one per failed page.  Only the main thread touches
    the terminal or the filesystem -- a worker merely runs the external
    command, hands failure messages back through
    :func:`_emit_translate_failure` and nudges the progress rows (which rich
    serialises internally) -- so no lock is needed and page completion order
    is irrelevant (every page owns its target path and manifest key).
    """
    if not plans:
        # ``min(resolve_jobs(...), 0)`` would hand ``max_workers=0`` to the
        # pool, which raises; ``run()`` filters this out, the function
        # itself should not depend on its caller to (review R-07).
        return _TranslationReport(0, {}, [], [])
    batches = chunk_pages(plans)
    ceiling = job_ceiling()
    workers = min(resolve_jobs(jobs), len(batches))
    if jobs is not None and jobs > ceiling:
        console.print(
            f"wiki: --jobs {jobs} clamped to the CPU ceiling {ceiling}"
            f" (cores x 2, {BATCH_SIZE} documents per task)",
            markup=False,
        )
    elif jobs is not None and jobs < 1:
        console.print(
            f"wiki: --jobs {jobs} raised to the minimum of 1 task", markup=False
        )
    console.print(
        f"wiki: {len(plans)} page(s) in {len(batches)} batch(es),"
        f" {workers} worker(s) at most ({BATCH_SIZE} documents per task)",
        markup=False,
    )
    translated = 0
    digests: dict[str, str] = {}
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
    overall = progress.add_task("translating", total=len(plans))
    batch_tasks = {
        index: progress.add_task(f"batch {index}/{len(batches)}", total=len(batch))
        for index, batch in enumerate(batches, start=1)
    }
    board = _ProgressBoard(
        progress=progress,
        overall=overall,
        batch_tasks=batch_tasks,
        batch_count=len(batches),
        total_pages=len(plans),
        workers=workers,
        queued=len(batches),
    )
    done = 0
    stop = threading.Event()
    global _emit_mode
    pool: ThreadPoolExecutor | None = None
    try:
        # Every fallible step lives inside the protected region (review
        # R-21).  The collect policy is process-global: an exception between
        # installing it and entering the try left it installed forever, and
        # every later translation failure in the process was then queued for
        # a reader that never came -- silent error reporting.
        _emit_mode = "collect"
        _STOP_TRANSLATIONS.clear()
        # Drain anything a previous run left behind before collecting into
        # the same queue: ownership belongs to the run that produced it.
        for message in _drain_collected_failures():
            console.print(message, markup=False)
        progress.start()
        pool = ThreadPoolExecutor(
            max_workers=workers, thread_name_prefix="wiki-translate"
        )
        futures: dict[Future[list[_PageOutcome]], int] = {
            pool.submit(
                _run_batch, batches[index - 1], translate_cmd, stop, index, board
            ): index
            for index in batch_tasks
        }
        for future in as_completed(futures):
            index = futures[future]
            batch = batches[index - 1]
            failed_here = 0
            for outcome in future.result():
                if outcome.error is not None:
                    # Ctrl+C (or a genuine bug) in a worker: signal every
                    # batch to stop, drop the queued work and leave without
                    # waiting for translations the user just cancelled.
                    stop.set()
                    for queued_future in futures:
                        queued_future.cancel()
                    raise outcome.error
                done += 1
                page = outcome.plan.page
                if outcome.english is None:
                    failed_here += 1
                    # An existing page whose re-translation failed is
                    # still stale, not missing -- report under that heading.
                    console.print(
                        f"wiki: [{done}/{len(plans)}] {page.en_target} failed"
                        f" ({outcome.elapsed:.1f}s)",
                        markup=False,
                    )
                    if outcome.plan.has_en:
                        stale.append(page.en_target)
                    else:
                        missing.append(page.en_target)
                    continue
                _write_page_text(target / page.en_target, outcome.english)
                digests[page.zh_target] = outcome.plan.digest
                translated += 1
            board.batch_finished()
            console.print(
                f"wiki: batch {index}/{len(batches)} done"
                f" ({len(batch) - failed_here}/{len(batch)} ok,"
                f" {failed_here} failed)",
                markup=False,
            )
    finally:
        # The main thread stops waiting -- queued batches are cancelled and
        # the in-flight translators are told to stop: a child that ignores
        # the console event is killed by its own worker within one poll
        # interval, so the process no longer lingers until interpreter
        # teardown joins the pool (review R-15).
        stop.set()
        _STOP_TRANSLATIONS.set()
        if pool is not None:
            pool.shutdown(wait=False, cancel_futures=True)
        progress.stop()
        # Restore the serial policy *before* draining: a worker that fails
        # after this point then writes its own line instead of queueing it
        # into a queue nobody will read again (review R-05, second half).
        _emit_mode = "print"
        for message in _drain_collected_failures():
            console.print(message, markup=False, highlight=False)
    return _TranslationReport(translated, digests, missing, stale)


def run(
    target: Path,
    translate_cmd: str | None,
    *,
    force: bool = False,
    translate_all: bool = False,
    check: bool = False,
    push: bool = False,
    repo_root: Path | None = None,
    jobs: int | None = None,
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

    *jobs* caps concurrent translations; ``None`` means the machine's
    ceiling (see :func:`resolve_jobs`) and any value is clamped into it.
    """
    root = repo_root if repo_root is not None else _util.repo_root()
    pages = collect_sources(root)
    try:
        target.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise WikiError(
            f"cannot create the wiki repo directory {target}: {exc}",
            code=Code.WIKI_PAGE_WRITE,
            hint="pass --target with a writable directory",
        ) from exc
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
    kept, plans, missing, stale = _prepare_pages(
        pages,
        target,
        manifest,
        translate_cmd=translate_cmd,
        translate_all=translate_all,
    )
    translated = 0
    if translate_cmd is not None:
        if plans:
            console.print(f"wiki: {len(plans)} page(s) to translate", markup=False)
        else:
            console.print(
                f"wiki: nothing to translate ({len(pages)} pages up to date)",
                markup=False,
            )
        if plans:
            outcome = _translate_pending(
                plans, translate_cmd, target=target, jobs=jobs, console=console
            )
            # Only a translation that really landed is blessed in the manifest.
            manifest.update(outcome.digests)
            translated = outcome.translated
            missing.extend(outcome.missing)
            stale.extend(outcome.stale)
    collected = {page.zh_target for page in pages}
    manifest = {key: value for key, value in manifest.items() if key in collected}
    # Sources that vanished must not leave dead links behind in the wiki.
    expected = {page.zh_target for page in pages} | {page.en_target for page in pages}
    orphans = prune_orphan_pages(target, expected)
    if orphans:
        print(f"wiki: removed {orphans} orphan page(s) with no source document")

    home_zh, sidebar_zh, home_en, sidebar_en = _nav_documents(pages)
    _write_page_text(target / "Home.md", home_zh)
    _write_page_text(target / "_Sidebar.md", sidebar_zh)
    _write_page_text(target / "Home.en.md", home_en)
    _write_page_text(target / "_Sidebar.en.md", sidebar_en)
    store_manifest(target, manifest)

    print(
        f"wiki: {len(pages)} pages -> {target} "
        f"(en kept {kept} / translated {translated} / "
        f"missing {len(missing)} / stale {len(stale)}) in {time.monotonic() - run_started:.1f}s"
    )
    for name in sorted(missing):
        print(f"  missing en: {name}")
    for name in sorted(stale):
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
