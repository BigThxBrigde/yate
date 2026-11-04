"""Wiki translation: the external translator command and the parallel stage.

Holds the subprocess plumbing around ``--translate-cmd``
(:func:`translate_via_cmd` / :func:`_run_translate` / :func:`_feed_stdin`
/ :func:`_terminate`), the worker-safe failure reporting channel
(:data:`_emit_mode` / :data:`_COLLECTED_FAILURES` /
:func:`_emit_translate_failure`), the page-verdict preview
(:func:`needs_translation`) and the bounded thread-pool orchestration
(:func:`_run_batch` / :func:`_translate_pending`).

Every name the test suite patches on the facade (``translate_via_cmd``,
``_run_translate``, ``as_completed``, ``ThreadPoolExecutor``,
``Progress``, ``subprocess``, ``TRANSLATE_TIMEOUT_S``, ``_STOP_POLL_S``,
``job_ceiling``, ``_drain_collected_failures`` and ``_emit_mode``) is read
here through the late-bound facade module object
(``_wiki_facade.<name>``), so ``monkeypatch.setattr(wiki, ...)`` keeps
working after the single-file-to-subpackage split.  ``_emit_mode`` is
written through the facade too: the queueing policy is a single
process-global fact and the facade attribute is its one home.
"""

from __future__ import annotations

import hashlib
import queue
import subprocess
import sys
import threading
import time
from collections.abc import Sequence
from concurrent.futures import Future, ThreadPoolExecutor
from enum import StrEnum
from pathlib import Path
from typing import IO, Final

import tools.pack.wiki as _wiki_facade
from rich.console import Console
from rich.progress import (
    BarColumn,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)

from tools.pack.errors import Code
from tools.pack.wiki.lint import BATCH_SIZE, _LintPool
from tools.pack.wiki.publish import _publish_translations, _salvage_landed
from tools.pack.wiki.report import (
    _PageOutcome,
    _PagePlan,
    _ProgressBoard,
    _TranslationReport,
    chunk_pages,
    resolve_jobs,
)
from tools.pack.wiki.sources import _read_source_bytes, WikiPage

# The shared surface of this submodule: the facade re-exports it and the
# sibling submodules consume it, so every name below is intentionally
# public within the subpackage (a leading underscore only keeps it out of
# the generator's documented plugin-facing API).
__all__ = [
    "TRANSLATE_TIMEOUT_S",
    "_PageState",
    "_INTERRUPT_EXIT_CODES",
    "_PREVIEW_TRANSLATE_HOOK",
    "_COLLECTED_FAILURES",
    "_STOP_POLL_S",
    "_TERMINATE_WAIT_S",
    "_drain_collected_failures",
    "_emit_mode",
    "_emit_translate_failure",
    "_feed_stdin",
    "_run_batch",
    "_run_translate",
    "_stage_local",
    "_stage_stop_requested",
    "_has_english_page",
    "_terminate",
    "_translation_state",
    "_translate_pending",
    "needs_translation",
    "translate_via_cmd",
]

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

#: Sentinel hook for :func:`needs_translation`: the preview is only asked
#: when a translator is wired up, so any non-``None`` value says "present".
_PREVIEW_TRANSLATE_HOOK: Final[str] = "<preview-hook>"

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
    same line during the run does not (review R-22).  Only the text is
    identical: the rich route wraps at ``Console.width``, so a long failure
    message (one embedding a child's stderr) can render with different
    line breaks on the two routes (review 2026-10-06 #59 O-3, accepted).
    """
    if _wiki_facade._emit_mode == "collect":
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


#: Per-thread handle on the translation stage that owns the current call.
#: Set by :func:`_run_batch` for the duration of a batch, so a translator
#: reads *its own* stage's stop signal (review R-15, second pass): a
#: process-global signal was either read too late (the stage restores its
#: routing policy on the way out) or read by an unrelated direct call, which
#: must not be cancellable at all.
_stage_local = threading.local()

#: How often a running translator checks for the stop signal.  Small enough
#: that an interrupt is honoured promptly, large enough to stay cheap.
_STOP_POLL_S: Final[float] = 0.2


def _stage_stop_requested() -> bool:
    """Return whether the owning stage asked its translators to stop."""
    stage: threading.Event | None = getattr(_stage_local, "stop", None)
    return stage is not None and stage.is_set()


def _feed_stdin(stream: IO[str] | None, text: str) -> None:
    """Write *text* into the child's stdin, then close it, from a helper thread.

    A dedicated writer is what keeps this deadlock-free: the main thread
    stays in :meth:`~subprocess.Popen.communicate`, which drains stdout and
    stderr while the page goes in.  Writing first and reading afterwards
    blocks as soon as the child answers before it has read everything --
    reproduced at 64 KB in and 64 KB out, and the repository's largest page
    is 72 KB.

    The stream is handed over rather than read back from the process object:
    :meth:`~subprocess.Popen.communicate` closes ``stdin`` on its first call
    when it is given no input (Windows ``_stdin_write(None)``, POSIX
    ``_communicate``), and a pipe must have exactly one owner.  Today the
    buffered writer's lock happens to serialise that close behind the write
    (measured: a 224 KB page arrives whole), which is an implementation
    detail of :mod:`io` rather than a promise.

    :class:`BrokenPipeError` means the child exited early (a mistyped
    command, a failed login).  That is not an error of ours: the real exit
    code arrives through ``communicate`` and is reported from there.
    """
    if stream is None:
        return
    try:
        stream.write(text)
        stream.close()
    except OSError as exc:
        # Includes BrokenPipeError: the child is gone, its exit code tells
        # the story -- but the write failure itself is never swallowed
        # silently (review m-23).  This runs in a helper thread, so it goes
        # through the failure channel the main thread drains: a worker never
        # writes to the terminal (review M-4 of the wave-e re-review).
        _emit_translate_failure(f"wiki: cannot feed the translator: {exc}")


#: Wall clock budget for reaping a killed translator.  ``kill`` is not a
#: promise on every platform -- a child stuck in an uninterruptible wait may
#: never report back -- and the caller is a pool worker that has to be able to
#: return, so the reap is bounded (review I1).
_TERMINATE_WAIT_S: Final[float] = 5.0


def _terminate(proc: subprocess.Popen[str]) -> str | None:
    """Kill and reap *proc*; return a note when the child outlived the kill.

    The wait is bounded by :data:`_TERMINATE_WAIT_S`: a child stuck in an
    uninterruptible state must not pin the pool worker, which is exactly what
    the cancel-signal work set out to achieve.  The note is returned rather
    than printed -- a worker never writes to the terminal (only the main
    thread does, see :func:`_emit_translate_failure`), so the caller folds it
    into the failure message it is already reporting.
    """
    note: str | None = None
    try:
        proc.kill()
    except OSError as exc:  # pragma: no cover - the child died in the meantime
        note = f"cannot terminate the translator: {exc}"
    try:
        proc.wait(timeout=_TERMINATE_WAIT_S)
    except _wiki_facade.subprocess.TimeoutExpired:
        stuck = f"pid {proc.pid} ignored the kill after {_TERMINATE_WAIT_S:g}s"
        return f"{note}; {stuck}" if note is not None else stuck
    return note


def _run_translate(text: str, translate_cmd: str) -> tuple[str | None, str | None]:
    """Run the external translator; returns ``(english, failure_message)``.

    The shell, the stdin/stdout protocol and :data:`TRANSLATE_TIMEOUT_S` are
    unchanged -- only the reporting is factored out so the caller decides
    where the message goes.  The page goes in from a helper thread
    (:func:`_feed_stdin`) while this thread polls ``communicate``, which is
    what keeps a page larger than the pipe buffer moving.

    Raises :exc:`KeyboardInterrupt` when the child died *because* the
    console was interrupted (see :data:`_INTERRUPT_EXIT_CODES`), and when
    the stage tore down while this child was still alive -- a translator
    that ignores the console event would otherwise keep the process alive
    for the rest of its page.
    """
    started = time.monotonic()
    try:
        proc = _wiki_facade.subprocess.Popen(
            translate_cmd,
            shell=True,
            stdin=_wiki_facade.subprocess.PIPE,
            stdout=_wiki_facade.subprocess.PIPE,
            stderr=_wiki_facade.subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError as exc:
        # Only reachable when the shell itself cannot start; a missing
        # command still comes back as a non-zero exit code.
        return None, (
            f"error[{Code.WIKI_TRANSLATE_FAILED}]: cannot start translate-cmd ({exc})"
        )
    # Hand the pipe to the writer and detach it from the process object: the
    # polling ``communicate`` below closes ``stdin`` on its first call, and
    # the writer owns that stream (review R-29).
    stdin = proc.stdin
    proc.stdin = None
    feeder = threading.Thread(
        target=_feed_stdin,
        args=(stdin, text),
        name="wiki-translate-stdin",
        daemon=True,
    )
    feeder.start()
    try:
        output: tuple[str | None, str | None] = ("", "")
        while True:
            try:
                output = proc.communicate(timeout=_wiki_facade._STOP_POLL_S)
                break
            except _wiki_facade.subprocess.TimeoutExpired:
                if _stage_stop_requested():
                    raise KeyboardInterrupt from None
                if (
                    time.monotonic() - started
                    >= _wiki_facade.TRANSLATE_TIMEOUT_S
                ):
                    raise _wiki_facade.subprocess.TimeoutExpired(
                        cmd=translate_cmd,
                        timeout=_wiki_facade.TRANSLATE_TIMEOUT_S,
                    ) from None
    except _wiki_facade.subprocess.TimeoutExpired:
        leftover = _terminate(proc)
        detail = f" ({leftover})" if leftover is not None else ""
        return None, (
            f"error[{Code.WIKI_TRANSLATE_TIMEOUT}]: translate-cmd timed out"
            f" after {_wiki_facade.TRANSLATE_TIMEOUT_S:g}s{detail}"
        )
    except BaseException:
        # Interrupt path (review 2026-10-06 #59-r2 M1): the _terminate
        # anti-kill note is deliberately dropped here -- a KeyboardInterrupt
        # must propagate unchanged, and queueing the note would violate the
        # R-05 "post-drain messages print directly" invariant.  The process
        # is still reaped below; only the diagnostic note is lost.
        _terminate(proc)
        raise
    finally:
        # Wait up to one poll interval for the writer, then leave it be: on
        # the kill paths the pipe is broken and it returns on its own, and a
        # healthy child has drained stdin long before this.  A writer still
        # alive here keeps its own pipe handle -- it is the child's stdin, so
        # it can still reach the child -- but it is a daemon thread over a
        # stream this module no longer touches (the pipe was detached from
        # the process object above), and it dies with the process.  The old
        # comment promised more than the join delivered (review I3).
        feeder.join(timeout=_wiki_facade._STOP_POLL_S)
    stdout, stderr = output
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
    english, failure = _wiki_facade._run_translate(text, translate_cmd)
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
    page of every queued batch.  The same signal is published to this
    thread for the duration of the batch (:data:`_stage_local`), which is
    what lets a translator abandon its child while it waits: the main thread
    restores the serial emit policy on its way out, so a policy test could
    not tell a worker that the stage is gone (review R-28).

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
    # Publish the owning stage's stop signal to this worker thread: the
    # translator polls it while waiting for its child, and only the stage
    # that owns this batch may cancel it (review R-15, second pass).
    _stage_local.stop = stop
    try:
        for plan in plans:
            if stop.is_set():
                break
            started = time.monotonic()
            try:
                board.page_started(index, plan.page)
                english: str | None = _wiki_facade.translate_via_cmd(
                    plan.text, translate_cmd
                )
                board.page_done(index)
                outcomes.append(
                    _PageOutcome(plan, english, None, time.monotonic() - started)
                )
            except BaseException as exc:  # noqa: BLE001 - must never escape
                stop.set()
                outcomes.append(
                    _PageOutcome(plan, None, exc, time.monotonic() - started)
                )
                break
    finally:
        _stage_local.stop = None
    return outcomes


def _translate_pending(
    plans: Sequence[_PagePlan],
    translate_cmd: str,
    *,
    target: Path,
    jobs: int | None,
    console: Console,
    lint_pool: _LintPool,
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

    Translated pages are written after the pool is drained, not page by
    page: :func:`_publish_translations` lints the whole landed set in one
    pass (parallel processes, see :func:`_lint_texts`), which costs far less
    than starting a pool per page.  An interrupt publishes the pages that
    already landed before it propagates, so a cancelled run never throws
    finished translations away.
    """
    if not plans:
        # ``min(resolve_jobs(...), 0)`` would hand ``max_workers=0`` to the
        # pool, which raises; ``run()`` filters this out, the function
        # itself should not depend on its caller to (review R-07).
        return _TranslationReport(0, {}, [], [])
    batches = chunk_pages(plans)
    ceiling = _wiki_facade.job_ceiling()
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
    missing: list[str] = []
    stale: list[str] = []
    landed: list[_PageOutcome] = []
    progress = _wiki_facade.Progress(
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
    stop = threading.Event()
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
    pool: ThreadPoolExecutor | None = None
    try:
        # Every fallible step lives inside the protected region (review
        # R-21).  The collect policy is process-global: an exception between
        # installing it and entering the try left it installed forever, and
        # every later translation failure in the process was then queued for
        # a reader that never came -- silent error reporting.
        _wiki_facade._emit_mode = "collect"
        # Drain anything a previous run left behind before collecting into
        # the same queue: ownership belongs to the run that produced it.
        # Both drains render identically (review R-22, second half found by
        # the PR !59 review: the entry drain had dropped ``highlight=False``).
        for message in _wiki_facade._drain_collected_failures():
            console.print(message, markup=False, highlight=False)
        progress.start()
        pool = _wiki_facade.ThreadPoolExecutor(
            max_workers=workers, thread_name_prefix="wiki-translate"
        )
        futures: dict[Future[list[_PageOutcome]], int] = {
            pool.submit(
                _run_batch, batches[index - 1], translate_cmd, stop, index, board
            ): index
            for index in batch_tasks
        }
        for future in _wiki_facade.as_completed(futures):
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
                landed.append(outcome)
            board.batch_finished()
            console.print(
                f"wiki: batch {index}/{len(batches)} done"
                f" ({len(batch) - failed_here}/{len(batch)} ok,"
                f" {failed_here} failed)",
                markup=False,
            )
    except BaseException:
        # A failed worker or a direct ``Ctrl+C`` in the main thread: publish
        # what already landed before the exception leaves (best effort; a
        # second ``Ctrl+C`` during the salvage aborts it immediately).  The
        # lint pass runs without its own bar -- the translation bar above is
        # still live on this console.
        _salvage_landed(landed, target, lint_pool=lint_pool, console=console)
        raise
    finally:
        # The main thread stops waiting -- queued batches are cancelled and
        # the in-flight translators are told to stop: a child that ignores
        # the console event is killed by its own worker within one poll
        # interval, so the process no longer lingers until interpreter
        # teardown joins the pool (review R-15).
        stop.set()
        if pool is not None:
            pool.shutdown(wait=False, cancel_futures=True)
        progress.stop()
        # Restore the serial policy *before* draining: a worker that fails
        # after this point then writes its own line instead of queueing it
        # into a queue nobody will read again (review R-05, second half).
        _wiki_facade._emit_mode = "print"
        for message in _wiki_facade._drain_collected_failures():
            console.print(message, markup=False, highlight=False)
    # The publish pass runs after the translation bar came down: its lint
    # pass then owns the console and shows the same live bar as the page
    # pass (a second live ``Progress`` on one console would fight the first).
    translated, digests = _publish_translations(
        landed, target, lint_pool=lint_pool, console=console, show_bar=True
    )
    return _TranslationReport(translated, digests, missing, stale)
