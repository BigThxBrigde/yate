"""Wiki run: the ``run()`` entry point and the page preparation stage.

Holds :func:`run` (the CLI-facing generator loop: collect, prepare,
translate, prune, navigate, manifest, push) and its rebuild half
:func:`_prepare_pages` (rebuild Chinese pages, copy bilingual twins, plan
what needs translating).

``collect_sources`` is read through the late-bound facade
(``_wiki_facade.collect_sources``): the test suite replaces it, so a plain
module-level binding would keep using the pre-patch object.
"""

from __future__ import annotations

import hashlib
import sys
import time
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path

import tools.pack.wiki as _wiki_facade
from rich.console import Console

from tools import _util
from tools.pack.errors import Code
from tools.pack.wiki.lint import (
    _LintPool,
    _LintRequest,
    _decode_page_text,
    _lint_page_text,
    _lint_texts,
    _linted_bytes,
    WikiError,
)
from tools.pack.wiki.publish import (
    _assert_prune_safe,
    _github_wiki_url,
    load_manifest,
    prune_orphan_pages,
    push_wiki,
    store_manifest,
)
from tools.pack.wiki.report import _PagePlan, _nav_documents
from tools.pack.wiki.sources import (
    _read_source_bytes,
    _write_page_bytes,
    _write_page_text,
    WikiPage,
)
from tools.pack.wiki.translate import (
    _PageState,
    _has_english_page,
    _translation_state,
    _translate_pending,
)

# The shared surface of this submodule: the facade re-exports it and the
# sibling submodules consume it, so every name below is intentionally
# public within the subpackage (a leading underscore only keeps it out of
# the generator's documented plugin-facing API).
__all__ = [
    "_PreparedPage",
    "_lint_requests",
    "_prepare_pages",
    "run",
]


@dataclass(frozen=True)
class _PreparedPage:
    """One page whose sources are read and whose lint jobs are decided."""

    page: WikiPage
    digest: str
    zh_bytes: bytes
    en_bytes: bytes | None


def _lint_requests(
    page: WikiPage, zh_bytes: bytes, en_bytes: bytes | None
) -> Iterator[_LintRequest]:
    """The lint jobs one page contributes: its zh text, plus its en twin."""
    zh_text = _decode_page_text(zh_bytes, label=page.zh_target)
    if zh_text is not None:
        yield _LintRequest(page.zh_target, "zh", zh_text)
    if en_bytes is not None:
        en_text = _decode_page_text(en_bytes, label=page.en_target)
        if en_text is not None:
            yield _LintRequest(page.en_target, "en", en_text)


def _prepare_pages(
    pages: Sequence[WikiPage],
    target: Path,
    manifest: dict[str, str],
    *,
    translate_cmd: str | None,
    translate_all: bool,
    lint_pool: _LintPool,
    console: Console,
) -> tuple[int, list[_PagePlan], list[str], list[str]]:
    """Rebuild Chinese pages and decide what still needs translating.

    Returns ``(kept, plans, missing, stale)``.  Mirrors
    :func:`needs_translation` for the preview count, but performs the work:
    every Chinese page is rewritten from its source, bilingual twins are
    copied verbatim, and only the pages that really need a translator are
    planned.  *manifest* is updated in place for kept pages: bilingual
    copies also record the digest of the en bytes this tool wrote, while
    adopted English pages are never recorded; translations are recorded by
    the caller once they actually succeed.

    Every source is read first and every page text is linted in one pass
    (:func:`_lint_texts`, which fans out over the mdlint process pool)
    before anything is written: linting is the CPU-bound half of this stage
    and reading a few hundred files costs far less than linting them.
    """
    prepared: list[_PreparedPage] = []
    requests: list[_LintRequest] = []
    for page in pages:
        zh_bytes = _read_source_bytes(page.zh_source)
        en_bytes: bytes | None = None
        if page.en_source is not None:
            # TOCTOU: _collect_bilingual verified en_source with exists()
            # at collection time, but the file may be deleted before this
            # read; treat the failure as a missing page (translation path)
            # instead of crashing the whole run.
            try:
                en_bytes = page.en_source.read_bytes()
            except OSError:
                en_bytes = None
        prepared.append(
            _PreparedPage(
                page=page,
                digest=hashlib.sha256(zh_bytes).hexdigest(),
                zh_bytes=zh_bytes,
                en_bytes=en_bytes,
            )
        )
        requests.extend(_lint_requests(page, zh_bytes, en_bytes))
    fixed = _lint_texts(requests, lint_pool=lint_pool, console=console)
    kept = 0
    plans: list[_PagePlan] = []
    missing: list[str] = []
    stale: list[str] = []
    for item in prepared:
        page = item.page
        zh_bytes = _linted_bytes(item.zh_bytes, fixed, page.zh_target)
        _write_page_bytes(target / page.zh_target, zh_bytes)
        en_path = target / page.en_target
        if item.en_bytes is not None:
            en_bytes = _linted_bytes(item.en_bytes, fixed, page.en_target)
            _write_page_bytes(en_path, en_bytes)
            # This tool wrote the en copy (en_bytes is exactly what landed
            # on disk), so it is recorded for prune: a page the tool never
            # wrote stays unrecorded and survives pruning.
            manifest[page.en_target] = hashlib.sha256(en_bytes).hexdigest()
            manifest.pop(page.zh_target, None)
            kept += 1
            continue
        recorded = manifest.get(page.zh_target)
        has_en = _has_english_page(en_path)
        state = _translation_state(
            has_en=has_en,
            recorded=recorded,
            digest=item.digest,
            translate_cmd=translate_cmd,
            translate_all=translate_all,
        )
        if state is _PageState.FRESH:
            # Fresh or externally maintained (e.g. agent-translated).
            manifest[page.zh_target] = item.digest
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
                digest=item.digest,
                text=zh_bytes.decode("utf-8", errors="replace"),
                has_en=has_en,
            )
        )
    return kept, plans, missing, stale


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
    pages = _wiki_facade.collect_sources(root)
    # The prune stage deletes generated pages, so the one target that could
    # eat the sources -- the repository root itself or a parent -- is
    # refused before anything is written (review B-3).
    _assert_prune_safe(target, root)
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
    # The prune stage must know which pages a previous run of this tool
    # wrote (review B-3): the mapping is captured before the run filters
    # the manifest down to the still-collected pages below.  A manifest
    # key is a zh target (source digest) or an en target this tool itself
    # wrote (digest of the bytes on disk); an en page the tool merely
    # adopted is never recorded, so it survives pruning even after its
    # zh source vanishes.
    recorded = dict(manifest)
    if translate_all and translate_cmd is None:
        print(
            "wiki: --translate-all has no effect without --translate-cmd",
            file=sys.stderr,
        )
    console = Console(file=sys.stderr)
    run_started = time.monotonic()
    # One lazy pool serves every lint pass of this run (rebuild, salvage,
    # publish).  It is created on the first submit -- small serial runs never
    # pay for it -- and torn down once here, after the last pass.  Workers
    # ignore ``Ctrl+C``; the parent owns the interrupt and cancels queued
    # batches, so a cancelled run does not wait for workers to drain.
    lint_pool = _LintPool()
    try:
        kept, plans, missing, stale = _prepare_pages(
            pages,
            target,
            manifest,
            translate_cmd=translate_cmd,
            translate_all=translate_all,
            lint_pool=lint_pool,
            console=console,
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
                    plans,
                    translate_cmd,
                    target=target,
                    jobs=jobs,
                    console=console,
                    lint_pool=lint_pool,
                )
                # Only a translation that really landed is blessed in the manifest.
                manifest.update(outcome.digests)
                translated = outcome.translated
                missing.extend(outcome.missing)
                stale.extend(outcome.stale)
        collected = {page.zh_target for page in pages}
        generated = {page.en_target for page in pages}
        # Keep both zh records and the en records this tool wrote for the
        # still-collected pages; dropping an en key here would make the next
        # run treat its page as never-written (adopted) and keep it forever.
        manifest = {
            key: value
            for key, value in manifest.items()
            if key in collected or key in generated
        }
        # Sources that vanished must not leave dead links behind in the wiki.
        expected = {page.zh_target for page in pages} | {page.en_target for page in pages}
        orphans = prune_orphan_pages(target, expected, recorded)
        if orphans:
            print(f"wiki: removed {orphans} orphan page(s) with no source document")

        home_zh, sidebar_zh, home_en, sidebar_en = _nav_documents(pages)
        _write_page_text(
            target / "Home.md", _lint_page_text(home_zh, "zh", label="Home.md")
        )
        _write_page_text(
            target / "_Sidebar.md", _lint_page_text(sidebar_zh, "zh", label="_Sidebar.md")
        )
        _write_page_text(
            target / "Home.en.md", _lint_page_text(home_en, "en", label="Home.en.md")
        )
        _write_page_text(
            target / "_Sidebar.en.md",
            _lint_page_text(sidebar_en, "en", label="_Sidebar.en.md"),
        )
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
                exit_code = push_wiki(target, github_url=_github_wiki_url(root))
            else:
                print("wiki: push skipped (--check found missing/stale pages)", file=sys.stderr)
        return exit_code
    finally:
        lint_pool.shutdown()
