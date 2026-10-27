"""Process-pool linting for directory runs and in-memory page batches.

``pymarkdown`` is pure Python and CPU-bound, so a thread pool cannot speed it
up: the GIL serialises the tokenizer.  The pool therefore uses processes, and
every task is small enough that a worker failure costs at most one task:
:func:`iter_batches` chunks consecutive files of :data:`BATCH_SIZE`, while
:func:`fix_texts` hands out one document per task, longest first, because the
fix pass is superlinear in document size.

Two shapes share that pool: :func:`iter_batches` hands it file paths (the
``mdlint --parallel`` directory runs) and :func:`fix_texts` hands it
``(lang, text)`` pairs (the wiki publisher lints page text before writing
it, so it cannot hand out paths).  Every worker builds its own engines
lazily, one per language profile, and keeps them for its whole lifetime; the
parent only passes plain picklable data and collects result dataclasses,
which keeps the protocol picklable and the engines out of the parent
process.

Every pool this module starts runs :func:`worker_initializer`, so a console
``Ctrl+C`` kills the parent's work -- not each worker with its own
traceback.  :func:`fix_texts` also accepts an existing pool, so a caller
that lints several times per run can share one pool instead of paying the
start-up per pass.
"""

from __future__ import annotations

import itertools
import os
import signal
from collections.abc import Callable, Iterator, Sequence
from concurrent.futures import Future, ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from tools.mdlint.lint import LintEngine, LintViolation, error_message

#: One pool task handles at most this many files (mirrors ``tools.pack.wiki``).
BATCH_SIZE: Final[int] = 10

#: Documents per task for the in-memory path.  The fix pass is superlinear in
#: document size, so one document per task is what lets the parent spread the
#: big pages across every core (see :func:`fix_texts`); a single parse is
#: milliseconds of pickling against seconds of linting.
TEXT_BATCH_SIZE: Final[int] = 1

#: Called with ``(done, total)`` after each pooled document lands.
type ProgressFn = Callable[[int, int], None]


def worker_initializer() -> None:
    """Worker entry hook: ignore ``Ctrl+C`` (the parent owns the interrupt).

    On Windows a console ``Ctrl+C`` is delivered to the whole process group,
    so every pooled worker would die with its own ``KeyboardInterrupt``
    traceback, drowning the parent's one coded ``interrupted`` line.  A
    worker that ignores the signal simply finishes its current task and
    leaves through the shutdown sentinels; the parent cancels the queue and
    tears the pool down.
    """
    signal.signal(signal.SIGINT, signal.SIG_IGN)


def collect_markdown(root: Path) -> list[Path]:
    """Every ``*.md`` file below *root*, sorted for a stable report order."""
    return sorted(path for path in root.rglob("*.md") if path.is_file())


def chunk[T](items: Sequence[T], size: int = BATCH_SIZE) -> list[list[T]]:
    """Split *items* into consecutive chunks of at most *size* entries."""
    if size < 1:
        raise ValueError(f"chunk size must be >= 1, got {size}")
    return [
        list(items[start : start + size]) for start in range(0, len(items), size)
    ]


def worker_count(batches: int) -> int:
    """How many workers to start: one per core, never more than *batches*.

    ``tools.pack.wiki`` doubles the core count because its workers block on
    an external translator; lint work is CPU-bound, so going past the core
    count only adds scheduling overhead.
    """
    cores = os.cpu_count() or 1
    return max(1, min(cores, batches))


@dataclass(frozen=True)
class FileOutcome:
    """What one file produced inside a worker: results, never exceptions."""

    path: str
    lang: str
    violations: list[LintViolation]
    was_fixed: bool = False
    error: str | None = None


_ENGINES: dict[str, LintEngine] = {}


def _engine(lang: str) -> LintEngine:
    """Return this worker's cached engine for *lang*."""
    engine = _ENGINES.get(lang)
    if engine is None:
        engine = LintEngine(lang)
        _ENGINES[lang] = engine
    return engine


def _lint_one(item: tuple[str, str], fix: bool) -> FileOutcome:
    """Lint one file in place (or scan it); failures travel as values."""
    raw_path, lang = item
    path = Path(raw_path)
    try:
        engine = _engine(lang)
        if fix:
            was_fixed, violations = engine.fix_file(path)
            return FileOutcome(raw_path, lang, violations, was_fixed)
        return FileOutcome(raw_path, lang, engine.scan_file(path))
    except Exception as exc:  # noqa: BLE001 - one bad file must not fail a pool
        return FileOutcome(raw_path, lang, [], error=error_message(exc))


def _lint_batch(batch: list[tuple[str, str]], fix: bool) -> list[FileOutcome]:
    """Worker entry point: lint one batch, never raising."""
    return [_lint_one(item, fix) for item in batch]


def iter_batches(
    items: Sequence[tuple[str, str]], *, fix: bool
) -> Iterator[FileOutcome]:
    """Lint *items* across processes, yielding outcomes in input order.

    ``pool.map`` hands results back in submission order, so the caller can
    report (and advance a progress bar) without waiting for the whole run.
    """
    batches = chunk(list(items))
    if not batches:
        return
    pool = ProcessPoolExecutor(
        max_workers=worker_count(len(batches)),
        initializer=worker_initializer,
    )
    try:
        grouped = pool.map(_lint_batch, batches, itertools.repeat(fix))
        for batch in grouped:
            yield from batch
    except BaseException:
        # A ``Ctrl+C`` must not pay for the queued documents: draining the
        # queue with ``shutdown(wait=True)`` would keep the prompt away for
        # minutes on a big directory (the wiki translation pool carries the
        # same guard, review R-15).
        pool.shutdown(wait=False, cancel_futures=True)
        raise
    pool.shutdown(wait=True)


def run_batches(
    items: Sequence[tuple[str, str]], *, fix: bool
) -> list[FileOutcome]:
    """Blocking variant of :func:`iter_batches` (all outcomes, input order)."""
    return list(iter_batches(items, fix=fix))


@dataclass(frozen=True)
class TextOutcome:
    """What one in-memory document produced inside a worker: results only."""

    fixed: str
    violations: list[LintViolation]
    error: str | None = None


def _fix_text_one(item: tuple[str, str]) -> TextOutcome:
    """Fix one ``(lang, text)`` pair; failures travel as values."""
    lang, text = item
    try:
        fixed, violations = _engine(lang).fix(text)
        return TextOutcome(fixed, violations)
    except Exception as exc:  # noqa: BLE001 - one bad page must not fail a pool
        return TextOutcome(text, [], error=error_message(exc))


def _fix_text_batch(batch: list[tuple[str, str]]) -> list[TextOutcome]:
    """Worker entry point: fix one batch of in-memory documents, never raising."""
    return [_fix_text_one(item) for item in batch]


def fix_texts(
    items: Sequence[tuple[str, str]],
    *,
    pool: ProcessPoolExecutor | None = None,
    progress: ProgressFn | None = None,
) -> list[TextOutcome]:
    """Fix *items* (``(lang, text)`` pairs) across processes, in input order.

    The in-memory twin of :func:`run_batches`: the wiki publisher lints page
    text before it writes that text to disk, so the pool receives the text
    itself instead of a path.  A page that cannot be linted comes back with
    its original text plus an ``error`` -- one pathological document never
    fails the batch.

    Tasks are handed out longest document first (LPT scheduling): the fix
    pass is superlinear in document size -- a 78 KiB manual costs ~67 s while
    a small page costs tens of milliseconds -- so starting the big pages
    first keeps them off the tail of the run.  Results are restored to input
    order before they come back.

    *pool* lets a caller that already owns a pool reuse it across several
    passes (the wiki publisher lints twice per run and keeps one pool for
    both); ``None`` creates a run-local pool, which is shut down before
    returning -- cancelled first when the run is interrupted.  An injected
    pool stays running: only this call's pending tasks are cancelled on the
    way out, and shutting it down is the owner's job.

    *progress* is called with ``(done, total)`` as each document lands.
    Results are collected as they finish (not in submission order), so the
    callback tracks real completion instead of stalling on the longest
    document, which an in-order ``pool.map`` would do.
    """
    if not items:
        return []
    ordered = sorted(enumerate(items), key=lambda pair: (-len(pair[1][1]), pair[0]))
    batches = chunk([item for _, item in ordered], TEXT_BATCH_SIZE)
    owned = pool is None
    executor = pool if pool is not None else ProcessPoolExecutor(
        max_workers=worker_count(len(batches)),
        initializer=worker_initializer,
    )
    results: dict[int, list[TextOutcome]] = {}
    # Declared before the try so an interrupt that lands mid-submission (the
    # submit loop itself can raise) still cancels the futures already handed
    # to the pool instead of leaking them.
    pending: dict[Future[list[TextOutcome]], int] = {}
    done = 0
    try:
        for index, batch in enumerate(batches):
            pending[executor.submit(_fix_text_batch, batch)] = index
        for future in as_completed(pending):
            batch_outcomes = future.result()
            results[pending[future]] = batch_outcomes
            done += len(batch_outcomes)
            if progress is not None:
                progress(done, len(items))
    except BaseException:
        # Cancel this call's queue: an owned pool is closed right away (a
        # ``Ctrl+C`` must not pay for the queued documents), an injected one
        # stays with its owner -- who decides when to shut it down.
        for future in pending:
            future.cancel()
        if owned:
            executor.shutdown(wait=False, cancel_futures=True)
        raise
    if owned:
        executor.shutdown(wait=True)
    outcomes = [
        outcome for index in range(len(batches)) for outcome in results[index]
    ]
    by_index = dict(zip((index for index, _ in ordered), outcomes, strict=True))
    return [by_index[index] for index in range(len(outcomes))]
