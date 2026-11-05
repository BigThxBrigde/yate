"""Wiki lint pass: the mdlint fix fan-out over the shared process pool.

Holds :class:`WikiError` (the coded abort type for the whole subpackage),
the lazily cached mdlint engines, the run's single process pool
(:class:`_LintPool`), the per-pass progress bar (:class:`_LintBar`) and
the batched fix entry point :func:`_lint_texts`.

Every name the test suite patches on the facade
(``tools.pack.wiki._get_lint_engine``, ``PARALLEL_LINT_MIN_CHARS``,
``Progress``) is read here through the late-bound facade module object
(``_wiki_facade.<name>``), so ``monkeypatch.setattr(wiki, ...)`` keeps
working after the single-file-to-subpackage split.
"""

from __future__ import annotations

import functools
import os
import time
from collections.abc import Callable, Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from typing import Final

import tools.pack.wiki as _wiki_facade
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)

from tools.pack import errors
from tools.pack.errors import Code, PackError

# The shared surface of this submodule: the facade re-exports it and the
# sibling submodules consume it, so every name below is intentionally
# public within the subpackage (a leading underscore only keeps it out of
# the generator's documented plugin-facing API).
__all__ = [
    "BATCH_SIZE",
    "PARALLEL_LINT_MIN_CHARS",
    "PARALLEL_LINT_MIN_TEXTS",
    "WikiError",
    "_LintBar",
    "_LintPool",
    "_LintRequest",
    "_decode_page_text",
    "_get_lint_engine",
    "_lint_page_text",
    "_lint_texts",
    "_lint_texts_in_pool",
    "_linted_bytes",
    "_require_lint_engine",
    "cpu_count",
    "reset_lint_engine_cache",
]

#: Documents per translation task.  A task is the unit handed to a pool
#: worker, so a pool failure costs at most this many translations.
BATCH_SIZE: Final[int] = 10

#: In-memory documents below this count are linted in this process.  A fresh
#: process pool costs ~0.5 s to start (spawn plus the pymarkdown import)
#: while one page costs ~75 ms, so the pool only pays off past the break-even
#: of roughly seven pages; twice that keeps a small run off the spawn path.
PARALLEL_LINT_MIN_TEXTS: Final[int] = 2 * BATCH_SIZE

#: Text floor that overrides :data:`PARALLEL_LINT_MIN_TEXTS`.  The count alone
#: is a poor proxy: the fix pass is superlinear in document size (a 78 KiB
#: manual costs ~67 s), so a handful of big pages can burn minutes serially
#: while the pool would have paid for its start-up many times over.
PARALLEL_LINT_MIN_CHARS: Final[int] = 128 * 1024


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


@functools.cache
def _get_lint_engine(lang: str):
    """Return the process-wide cached mdlint engine for *lang*.

    The import is deferred so that wiki runs work in environments without
    the optional ``pymarkdownlnt`` dev dependency until the first page is
    actually linted; the return type is inferred as
    :class:`tools.mdlint.lint.LintEngine` -- a module-level annotation
    would defeat the lazy import.

    The cache needs no lock: the parent-side lint calls all happen on the
    main thread (the pool's workers build their own engines in their own
    processes), and :func:`_lint_texts` uses this copy only to validate the
    environment before a pool starts.
    """
    from tools.mdlint.lint import LintEngine

    return LintEngine(lang)


def _require_lint_engine(lang: str):
    """Return the engine for *lang*, reporting a broken backend as ``WIKI-0109``.

    Engine construction covers the pymarkdownlnt import and every plugin
    load; both are environment breakages worth a coded abort instead of
    silently publishing unlinted pages.
    """
    try:
        return _wiki_facade._get_lint_engine(lang)
    except Exception as exc:  # noqa: BLE001 - lint engine construction failure
        raise WikiError(
            f"markdown lint engine unavailable: {exc}",
            code=Code.WIKI_LINT_FAILED,
            hint="install the dev extras (pip install -e .[dev])",
        ) from exc


def _lint_page_text(text: str, lang: str, *, label: str) -> str:
    """Run the mdlint fix pass on *text* and return the cleaned version.

    Remaining violations (not auto-fixable) are logged as warnings capped
    at five per page; they never abort the wiki run.  A document the linter
    chokes on publishes as-is: pymarkdown's own assertions fire on a few
    pathological inputs, and a single odd page must not fail the whole
    publish.  This is the one-document path (the navigation pages); page
    bodies go through :func:`_lint_texts`, which batches them in parallel.
    """
    engine = _require_lint_engine(lang)
    try:
        fixed, remaining = engine.fix(text)
    except Exception as exc:  # noqa: BLE001 - one odd page must not fail the run
        from tools.mdlint.lint import error_message

        errors.log.warning(
            "wiki lint: %s could not be linted (%s); published as-is",
            label,
            error_message(exc),
        )
        return text
    for violation in remaining[:5]:
        errors.log.warning(
            "wiki lint: %s:%d:%d %s %s",
            label,
            violation.line,
            violation.column,
            violation.rule_id,
            violation.message,
        )
    return fixed


def _decode_page_text(data: bytes, *, label: str) -> str | None:
    """Decode page bytes as UTF-8; undecodable bytes warn and return ``None``.

    A lossy ``errors="replace"`` round-trip would silently corrupt page
    content, so such a page is published untouched and never linted.
    """
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        errors.log.warning("wiki lint: %s is not UTF-8 (%s); skipped", label, exc)
        return None


@dataclass(frozen=True)
class _LintRequest:
    """One in-memory document waiting for the mdlint fix pass.

    *label* is the wiki target name the warnings are reported under, so a
    reader can map a warning back to the page it concerns.  Labels are
    unique across a run (every zh and en target appears once), which is what
    lets :func:`_lint_texts` hand the cleaned texts back as a mapping.
    """

    label: str
    lang: str
    text: str


@dataclass
class _LintPool:
    """The run's single mdlint process pool, created on first pooled lint.

    One pool serves every lint pass of a run (the page pass in
    :func:`_prepare_pages` and the publish pass in
    :func:`_publish_translations`): the workers pay the pymarkdown import
    once and stay warm for the whole run.  Creating the pool object spawns
    nothing -- workers start lazily on the first submitted task -- so small
    in-process runs never pay for it, and :meth:`shutdown` in :func:`run`'s
    teardown is a no-op for them.
    """

    pool: ProcessPoolExecutor | None = None

    def ensure(self) -> ProcessPoolExecutor:
        """Create the pool on first use; its workers ignore ``Ctrl+C``."""
        if self.pool is None:
            from tools.mdlint.batch import worker_initializer

            self.pool = ProcessPoolExecutor(
                max_workers=cpu_count(), initializer=worker_initializer
            )
        return self.pool

    def shutdown(self) -> None:
        """Cancel queued lint jobs and release the workers, if any."""
        if self.pool is not None:
            # ``wait=False``: idle workers exit through the sentinels within
            # milliseconds on the clean path, and an interrupted run must not
            # drain its queue (the same guard as the translation pool).
            self.pool.shutdown(wait=False, cancel_futures=True)


@dataclass
class _LintBar:
    """One lint pass's live bar; a no-op off a terminal (like the tool's).

    The standalone ``mdlint`` CLI shows a rich progress bar on interactive
    runs and plain report lines otherwise; the publisher mirrors that on its
    stderr console.  The serial path advances page by page from its own
    loop (:meth:`step`); the pool path replays the completion count that
    :func:`tools.mdlint.batch.fix_texts` reports (:meth:`advance`).
    """

    progress: Progress | None
    task: TaskID | None

    @classmethod
    def start(cls, console: Console, total: int) -> _LintBar:
        """Start a live bar, or return the inert one for piped output."""
        if not console.is_terminal:
            return cls(None, None)
        progress = _wiki_facade.Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=console,
        )
        task = progress.add_task(f"linting {total} page(s)", total=total)
        progress.start()
        return cls(progress, task)

    @classmethod
    def off(cls) -> _LintBar:
        """The inert bar (piped output, or a nested pass that must not
        fight the caller's live bar for the console)."""
        return cls(None, None)

    def step(self) -> None:
        """Advance one page (serial path)."""
        if self.progress is not None and self.task is not None:
            self.progress.update(self.task, advance=1)

    def advance(self, done: int, total: int) -> None:
        """Replay the pool path's completion count (one call per page)."""
        del total
        if self.progress is not None and self.task is not None:
            self.progress.update(self.task, completed=done)

    def stop(self) -> None:
        """Take the bar down (a no-op when it never started)."""
        if self.progress is not None:
            self.progress.stop()


def _lint_texts(
    requests: Sequence[_LintRequest],
    *,
    lint_pool: _LintPool,
    console: Console,
    show_bar: bool = True,
) -> dict[str, str]:
    """Lint *requests* and return ``label -> cleaned text``.

    Large runs fan out over the mdlint process pool
    (:func:`tools.mdlint.batch.fix_texts`); a run stays in this process while
    it holds fewer than :data:`PARALLEL_LINT_MIN_TEXTS` documents *and* less
    than :data:`PARALLEL_LINT_MIN_CHARS` of text, where starting a pool would
    cost more than the linting itself.  Both paths report identically: a page
    the linter chokes on is published as-is with a warning, remaining
    violations warn (capped at five per page), and a backend that cannot even
    be constructed aborts with ``WIKI-0109``.

    The pass reports like the standalone tool: a live bar on a terminal
    (piped output skips it, as does ``show_bar=False``) plus one summary
    line with the page count and the elapsed time.
    """
    if not requests:
        return {}
    started = time.monotonic()
    bar = _LintBar.start(console, len(requests)) if show_bar else _LintBar.off()
    fixed: dict[str, str] = {}
    try:
        text_size = sum(len(request.text) for request in requests)
        if (
            len(requests) < _wiki_facade.PARALLEL_LINT_MIN_TEXTS
            and text_size < _wiki_facade.PARALLEL_LINT_MIN_CHARS
        ):
            for request in requests:
                fixed[request.label] = _lint_page_text(
                    request.text, request.lang, label=request.label
                )
                bar.step()
        else:
            fixed = _lint_texts_in_pool(requests, lint_pool, bar.advance)
    finally:
        bar.stop()
    console.print(
        f"wiki lint: {len(requests)} page(s) in {time.monotonic() - started:.1f}s",
        markup=False,
    )
    return fixed


def _lint_texts_in_pool(
    requests: Sequence[_LintRequest],
    lint_pool: _LintPool,
    advance: Callable[[int, int], None],
) -> dict[str, str]:
    """Lint every request through the run's mdlint process pool (input order)."""
    for lang in sorted({request.lang for request in requests}):
        # Validate the backend in the parent: a missing dependency must
        # abort once with a coded error, not once per pooled page.
        _require_lint_engine(lang)
    from tools.mdlint.batch import fix_texts

    try:
        outcomes = fix_texts(
            [(request.lang, request.text) for request in requests],
            pool=lint_pool.ensure(),
            progress=advance,
        )
    except Exception as exc:  # noqa: BLE001 - lint pool startup failure
        raise WikiError(
            f"markdown lint pool failed: {exc}",
            code=Code.WIKI_LINT_FAILED,
            hint=(
                "install the dev extras (pip install -e .[dev]); on Windows a "
                "script embedding run() needs an `if __name__ == '__main__':` "
                "guard (start the publisher with `python -m tools.pack`)"
            ),
        ) from exc
    fixed: dict[str, str] = {}
    for request, outcome in zip(requests, outcomes, strict=True):
        if outcome.error is not None:
            errors.log.warning(
                "wiki lint: %s could not be linted (%s); published as-is",
                request.label,
                outcome.error,
            )
            fixed[request.label] = request.text
            continue
        # The same capped report as the single-document path above.
        for violation in outcome.violations[:5]:
            errors.log.warning(
                "wiki lint: %s:%d:%d %s %s",
                request.label,
                violation.line,
                violation.column,
                violation.rule_id,
                violation.message,
            )
        fixed[request.label] = outcome.fixed
    return fixed


def _linted_bytes(data: bytes, fixed: dict[str, str], label: str) -> bytes:
    """Return the linted form of *data* (the raw bytes when it was not linted)."""
    text = fixed.get(label)
    return data if text is None else text.encode("utf-8")


def reset_lint_engine_cache() -> None:
    """Forget the cached lint engines (test seam for engine failure paths)."""
    _wiki_facade._get_lint_engine.cache_clear()


def cpu_count() -> int:
    """Return the usable core count (never 0)."""
    return os.cpu_count() or 1
