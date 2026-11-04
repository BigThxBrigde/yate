"""Facade for the wiki generator subpackage: ``python -m tools.pack wiki``.

The former single-file module ``tools.pack.wiki`` (2149 lines) split into
this package; the public import path is unchanged and ``tools.pack.cli``
still calls ``wiki.run(...)`` through this facade.

Re-export exception note (coding conventions: package roots are lazy and
UI/service packages do not re-export): this facade intentionally
re-exports its submodules' names, private ones included, because the test
suite couples to the module global surface of the former single file
(``monkeypatch.setattr(wiki, ...)`` / ``wiki.<attr>``) -- the facade
attribute set is the frozen compatibility surface.  Submodules reference
each other by absolute import and read every patched name through the
late-bound facade module object (``import tools.pack.wiki as
_wiki_facade`` + ``_wiki_facade.<name>`` at call time), so a test patch
on the facade reaches the production read sites; a direct
``import tools.pack.wiki.<submodule>`` first-thing may therefore hit the
intentional import cycle (import this package first).

Split layout: ``lint`` (WikiError + the mdlint pass), ``sources``
(page collection + page file primitives), ``report`` (navigation +
page plans + progress board), ``publish`` (git/manifest/prune/push +
translation write-back), ``translate`` (the translator command + the
parallel stage) and ``run`` (the ``run()`` entry point).
"""

from __future__ import annotations

import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from rich.console import Console
from rich.progress import Progress

from tools.pack.errors import Code

from tools.pack.wiki.lint import (
    BATCH_SIZE,
    PARALLEL_LINT_MIN_CHARS,
    PARALLEL_LINT_MIN_TEXTS,
    WikiError,
    _get_lint_engine as _get_lint_engine,
    _LintPool as _LintPool,
    reset_lint_engine_cache,
)
from tools.pack.wiki.publish import (
    COMMIT_MESSAGE,
    GITHUB_WIKI_URL,
    MANIFEST_NAME,
    WIKI_BRANCH,
    _github_wiki_url as _github_wiki_url,
    default_target,
    load_manifest,
    prune_orphan_pages,
    push_wiki,
    run_git,
    store_manifest,
)
from tools.pack.wiki.report import chunk_pages, job_ceiling, resolve_jobs
from tools.pack.wiki.run import run
from tools.pack.wiki.sources import (
    SECTION_GUIDES,
    SECTION_NOTES,
    SECTION_PLANS,
    SECTION_REVIEWS,
    SECTION_SETS,
    WikiPage,
    _read_source_bytes as _read_source_bytes,
    collect_sources,
)
from tools.pack.wiki.translate import (
    TRANSLATE_TIMEOUT_S,
    _COLLECTED_FAILURES as _COLLECTED_FAILURES,
    _STOP_POLL_S as _STOP_POLL_S,
    _TERMINATE_WAIT_S as _TERMINATE_WAIT_S,
    _drain_collected_failures as _drain_collected_failures,
    _emit_mode as _emit_mode,
    _emit_translate_failure as _emit_translate_failure,
    _feed_stdin as _feed_stdin,
    _run_translate as _run_translate,
    _stage_local as _stage_local,
    _translate_pending as _translate_pending,
    needs_translation,
    translate_via_cmd,
)

__all__ = [
    "BATCH_SIZE",
    "COMMIT_MESSAGE",
    "Code",
    "Console",
    "GITHUB_WIKI_URL",
    "MANIFEST_NAME",
    "PARALLEL_LINT_MIN_CHARS",
    "PARALLEL_LINT_MIN_TEXTS",
    "Progress",
    "SECTION_GUIDES",
    "SECTION_NOTES",
    "SECTION_PLANS",
    "SECTION_REVIEWS",
    "SECTION_SETS",
    "TRANSLATE_TIMEOUT_S",
    "ThreadPoolExecutor",
    "WIKI_BRANCH",
    "WikiError",
    "WikiPage",
    "_COLLECTED_FAILURES",
    "_STOP_POLL_S",
    "_TERMINATE_WAIT_S",
    "_drain_collected_failures",
    "_emit_mode",
    "_emit_translate_failure",
    "_feed_stdin",
    "_get_lint_engine",
    "_github_wiki_url",
    "_LintPool",
    "_read_source_bytes",
    "_run_translate",
    "_stage_local",
    "_translate_pending",
    "as_completed",
    "chunk_pages",
    "collect_sources",
    "default_target",
    "job_ceiling",
    "load_manifest",
    "needs_translation",
    "prune_orphan_pages",
    "push_wiki",
    "reset_lint_engine_cache",
    "resolve_jobs",
    "run",
    "run_git",
    "store_manifest",
    "subprocess",
    "translate_via_cmd",
]
