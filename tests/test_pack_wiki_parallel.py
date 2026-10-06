"""Parallel translation tests for the bilingual wiki generator.

Covers the batch splitting (:func:`tools.pack.wiki.chunk_pages`), the
``--jobs`` ceiling (:func:`tools.pack.wiki.resolve_jobs` /
:func:`tools.pack.wiki.job_ceiling`), the live progress reporting, the peak
concurrency of the translation pool and the ``Ctrl+C`` path of issue
IKJPEK.

The external translator is never really invoked: every test replaces
:func:`tools.pack.wiki.translate_via_cmd` with a fake that keeps a
lock-protected concurrency counter, so the assertions observe the pool
without spawning a single subprocess.  Concurrency is proved with a
:mod:`threading` ``Barrier`` instead of a sleep race wherever a lower
bound is asserted, so the tests do not jitter.
"""

from __future__ import annotations

import io
import re
import sys
import threading
import time
import types
from collections.abc import Callable, Generator
from contextlib import contextmanager
from io import StringIO
from pathlib import Path

import pytest
import subprocess
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)

from tools.pack import cli, wiki

#: Documents per batch the issue mandates; the constant itself is asserted
#: by ``test_batch_size_is_ten_documents``, this is the fixture default.
PAGE_COUNT: int = 25

#: Per-page fake latency for the timing-sensitive interrupt test; long enough
#: that a drained pool is measurable, short enough to keep the suite quick.
PAGE_DELAY_S: float = 0.2


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    """A fake checkout with :data:`PAGE_COUNT` pages that all need a translator.

    Every document needs a translation, so a run over a pristine target
    plans exactly :data:`PAGE_COUNT` pages, i.e. three batches at
    :data:`tools.pack.wiki.BATCH_SIZE` of ten.
    """
    root = tmp_path / "repo"
    for index in range(1, PAGE_COUNT + 1):
        stem = f"page{index:02d}"
        _touch(root, f".trae/documents/{stem}.md", f"# {stem}\n\n中文正文 {stem}\n")
    return root


def _touch(root: Path, rel: str, text: str) -> Path:
    """Write *text* to *rel* below *root*, creating the parent directories."""
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _english_for(text: str) -> str:
    """Return the deterministic English twin of one Chinese page body.

    The result embeds the Chinese heading, so a test can prove that the
    English page on disk belongs to the source it claims to translate --
    a page written by another page's translation is caught immediately.
    """
    return f"# en of {text.splitlines()[0].removeprefix('# ')}\n"


class _PeakTracker:
    """Thread-safe record of the highest number of simultaneous calls.

    The counter is guarded by a lock because the translation pool runs the
    fake on several worker threads at once; the peak is therefore an
    exact observation, never a sampling guess.
    """

    def __init__(self) -> None:
        """Start with no caller inside and a peak of zero."""
        self._lock = threading.Lock()
        self._current = 0
        self._peak = 0

    @contextmanager
    def slot(self) -> Generator[None]:
        """Count one in-flight call for the duration of the ``with`` body."""
        with self._lock:
            self._current += 1
            self._peak = max(self._peak, self._current)
        try:
            yield
        finally:
            with self._lock:
                self._current -= 1

    @property
    def peak(self) -> int:
        """Return the highest number of calls that overlapped."""
        return self._peak


def test_batch_size_is_ten_documents() -> None:
    """The batch constant must stay at the ten documents the issue demands."""
    assert wiki.BATCH_SIZE == 10


def test_chunk_pages_splits_23_items_into_batches_of_at_most_ten() -> None:
    """Twenty-three items become three batches of 10/10/3, order preserved."""
    items = list(range(23))
    chunks = wiki.chunk_pages(items)
    assert [len(chunk) for chunk in chunks] == [10, 10, 3]
    assert all(len(chunk) <= wiki.BATCH_SIZE for chunk in chunks)
    # Consecutive slicing: every item exactly once, in its original order.
    assert [item for chunk in chunks for item in chunk] == items


def test_chunk_pages_with_size_one_yields_singletons() -> None:
    """An explicit size of one degenerates into one chunk per item."""
    assert wiki.chunk_pages([1, 2, 3], 1) == [[1], [2], [3]]


def test_chunk_pages_with_empty_input_yields_no_batches() -> None:
    """No items means no task at all, not a single empty batch."""
    assert wiki.chunk_pages([]) == []


def test_chunk_pages_with_size_zero_raises_value_error() -> None:
    """A non-positive batch size is rejected instead of looping forever."""
    with pytest.raises(ValueError, match="chunk size"):
        wiki.chunk_pages([1, 2, 3], 0)


def test_resolve_jobs_defaults_to_twice_the_core_count() -> None:
    """``--jobs`` omitted means the ceiling, i.e. cores times two."""
    assert wiki.resolve_jobs(None, cores=4) == 8


def test_resolve_jobs_keeps_a_downward_override() -> None:
    """A value below the ceiling is honoured as given."""
    assert wiki.resolve_jobs(3, cores=4) == 3


def test_resolve_jobs_clamps_above_the_ceiling() -> None:
    """A value above the ceiling is clamped to cores times two."""
    assert wiki.resolve_jobs(99, cores=4) == 8


def test_resolve_jobs_clamps_below_one() -> None:
    """Zero or negative values fall back to a single worker, never none."""
    assert wiki.resolve_jobs(0, cores=4) == 1
    assert wiki.resolve_jobs(-5, cores=4) == 1


def test_job_ceiling_with_one_core_is_two() -> None:
    """The hard ceiling is cores times two, with a floor of two workers."""
    assert wiki.job_ceiling(cores=1) == 2


def test_run_with_jobs_translates_every_page_and_reports_batches(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A 25-page run lands every page and reports batches and progress."""
    tracker = _PeakTracker()

    def fake_translate(text: str, translate_cmd: str) -> str | None:
        with tracker.slot():
            time.sleep(0.01)
        return _english_for(text)

    monkeypatch.setattr(wiki, "translate_via_cmd", fake_translate)
    target = tmp_path / "wiki"
    assert wiki.run(target, "fake-cmd", repo_root=repo, jobs=2) == 0

    for index in range(1, PAGE_COUNT + 1):
        stem = f"page{index:02d}"
        assert (target / f"{stem}.en.md").read_text(encoding="utf-8") == _english_for(
            f"# {stem}\n\n中文正文 {stem}\n"
        )
    assert set(wiki.load_manifest(target)) == {
        f"page{index:02d}.zh.md" for index in range(1, PAGE_COUNT + 1)
    }

    err = capsys.readouterr().err
    # Batch and worker budget of the pool (permanent lines, not a progress frame).
    assert "batch 1/3" in err
    assert "worker(s) at most" in err
    # The live overall task description: pages done, batches left to start.
    assert "page(s)" in err
    assert "batch(es) queued" in err


def test_run_with_jobs_above_ceiling_reports_the_clamp(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """An oversized ``--jobs`` is clamped and the clamp is reported."""

    def fake_translate(text: str, translate_cmd: str) -> str | None:
        time.sleep(0.01)
        return _english_for(text)

    def fake_ceiling(*, cores: int | None = None) -> int:
        del cores
        return 3

    monkeypatch.setattr(wiki, "translate_via_cmd", fake_translate)
    monkeypatch.setattr(wiki, "job_ceiling", fake_ceiling)
    target = tmp_path / "wiki"
    assert wiki.run(target, "fake-cmd", repo_root=repo, jobs=99) == 0
    assert (target / "page01.en.md").exists()
    err = capsys.readouterr().err
    assert "clamped" in err
    assert "--jobs 99 clamped to the CPU ceiling 3" in err


def test_run_keeps_peak_concurrency_within_the_ceiling(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The pool never exceeds the ceiling, yet really does run in parallel.

    The lower bound is deterministic: the first two worker calls block on
    a :class:`threading.Barrier`, so the run cannot finish with a peak of
    one even if the machine is fast, while the upper bound is the exact
    observation of the lock-protected counter.
    """
    tracker = _PeakTracker()
    gate = threading.Barrier(2)
    state = {"arrivals": 0}
    lock = threading.Lock()

    def fake_translate(text: str, translate_cmd: str) -> str | None:
        with tracker.slot():
            with lock:
                state["arrivals"] += 1
                waits = state["arrivals"] <= 2
            if waits:
                # Both first callers park here until two of them are inside
                # the fake: parallelism is proved, not raced for.
                gate.wait(timeout=30)
            time.sleep(0.01)
        return _english_for(text)

    def fake_ceiling(*, cores: int | None = None) -> int:
        del cores
        return 3

    monkeypatch.setattr(wiki, "translate_via_cmd", fake_translate)
    monkeypatch.setattr(wiki, "job_ceiling", fake_ceiling)
    target = tmp_path / "wiki"
    assert wiki.run(target, "fake-cmd", repo_root=repo) == 0
    assert tracker.peak <= 3
    assert tracker.peak >= 2


def test_run_counts_a_failed_page_as_missing_and_skips_its_digest(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A page whose translation fails is reported, not blessed in the manifest."""

    def fake_translate(text: str, translate_cmd: str) -> str | None:
        time.sleep(0.01)
        return None if "page07" in text else _english_for(text)

    monkeypatch.setattr(wiki, "translate_via_cmd", fake_translate)
    target = tmp_path / "wiki"
    # Without --check a missing page is reported but the run still succeeds.
    assert wiki.run(target, "fake-cmd", repo_root=repo, jobs=2) == 0
    assert not (target / "page07.en.md").exists()
    assert (target / "page08.en.md").exists()
    manifest = wiki.load_manifest(target)
    assert "page07.zh.md" not in manifest
    assert "page08.zh.md" in manifest
    captured = capsys.readouterr()
    assert "failed" in captured.err
    assert "page07.en.md" in captured.out
    assert "missing 1" in captured.out

    # --check turns the very same gap into exit code 1.
    assert wiki.run(tmp_path / "wiki-check", "fake-cmd", check=True, repo_root=repo, jobs=2) == 1


def test_run_is_independent_of_page_completion_order(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Uneven per-page durations reorder the batches but not the result."""
    durations: dict[str, float] = {}

    def fake_translate(text: str, translate_cmd: str) -> str | None:
        stem = text.splitlines()[0].removeprefix("# ")
        # Every other page is five times slower, so batches finish in a
        # different order than they were submitted.
        durations[stem] = 0.01 if int(stem.removeprefix("page")) % 2 else 0.05
        time.sleep(durations[stem])
        return _english_for(text)

    monkeypatch.setattr(wiki, "translate_via_cmd", fake_translate)
    target = tmp_path / "wiki"
    assert wiki.run(target, "fake-cmd", repo_root=repo, jobs=3) == 0
    for index in range(1, PAGE_COUNT + 1):
        stem = f"page{index:02d}"
        assert (target / f"{stem}.en.md").read_text(encoding="utf-8") == f"# en of {stem}\n"
    assert set(wiki.load_manifest(target)) == {
        f"page{index:02d}.zh.md" for index in range(1, PAGE_COUNT + 1)
    }
    assert len(durations) == PAGE_COUNT


def test_keyboard_interrupt_inside_a_worker_maps_to_exit_130(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``Ctrl+C`` in a worker thread reaches the CLI as 130, without a traceback.

    The worker catches ``BaseException`` and carries it back as a value, so
    the main thread re-raises it instead of leaving the future pending.
    """

    def interrupted(text: str, translate_cmd: str) -> str | None:
        raise KeyboardInterrupt

    monkeypatch.setattr(wiki, "translate_via_cmd", interrupted)
    # The CLI derives the checkout itself; point it at the fixture repo so no
    # real machine path is baked into the test.
    monkeypatch.setattr("tools._util.repo_root", lambda: repo)
    argv = [
        "wiki",
        "--target",
        str(tmp_path / "wiki"),
        "--translate-cmd",
        "fake-cmd",
        "--jobs",
        "2",
    ]
    assert cli.main(argv) == 130
    err = capsys.readouterr().err
    assert "interrupted" in err
    assert "Traceback" not in err


def test_interrupt_leaves_the_queued_batches_untranslated(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A ``Ctrl+C`` must not pay for the pages that never started.

    Regression guard for the first review round: the pool used to be closed
    with ``wait=True`` while every batch was already submitted, so an
    interrupt paid for all :data:`PAGE_COUNT` translations.  Now the running
    batches see the stop signal and the queued ones are cancelled, which
    keeps the started count at a small constant instead of the page count.
    """
    started: list[str] = []
    lock = threading.Lock()

    def interrupting(text: str, translate_cmd: str) -> str | None:
        with lock:
            started.append(text)
        time.sleep(PAGE_DELAY_S)
        # Only one page aborts: every other page translates normally, so a
        # pool that is drained on interrupt shows up as a started count of
        # PAGE_COUNT and a run that takes seconds instead of milliseconds.
        if "page03" in text:
            raise KeyboardInterrupt
        return "# en\n"

    monkeypatch.setattr(wiki, "translate_via_cmd", interrupting)
    target = tmp_path / "wiki"
    # Called straight through the library, the interrupt propagates (the CLI
    # boundary is what maps it to exit code 130).
    began = time.monotonic()
    with pytest.raises(KeyboardInterrupt):
        wiki.run(target, "fake-cmd", repo_root=repo, jobs=2)
    elapsed = time.monotonic() - began
    assert len(started) < PAGE_COUNT
    # Two workers, one page each, plus the page that raised: the signal stops
    # the sibling before it can pick up a third batch.  The bound leaves room
    # for scheduling jitter while still failing if the pool is drained.
    assert len(started) <= 8
    # The real regression: closing the pool with wait=True made the run pay
    # for every submitted page (PAGE_COUNT * PAGE_DELAY_S / jobs = 2.5s),
    # so the interrupt appeared to hang.  Only the pages already in flight
    # may still be waited for -- at most two more here, i.e. ~0.4s.
    assert elapsed < 8 * PAGE_DELAY_S


class _HangingProc:
    """Stand-in for a translator that ignores the console event.

    ``communicate`` keeps timing out, exactly like a child that neither
    answers nor dies, and the process records that it was killed.  Review
    R-28 is about who does the killing: the worker that is waiting, not the
    main thread that has already walked away.
    """

    def __init__(self, polling: threading.Event) -> None:
        """Publish *polling* as soon as the first wait begins."""
        self.returncode = 0
        self.killed = False
        self.stdin = io.StringIO()
        self._polling = polling

    def communicate(self, timeout: float | None = None) -> tuple[str, str]:
        """Never answer, and announce that this process is now waiting."""
        del timeout
        self._polling.set()
        raise subprocess.TimeoutExpired(cmd="fake-cmd", timeout=0)

    def kill(self) -> None:
        """Record the termination the worker was supposed to ask for."""
        self.killed = True
        self.returncode = -9

    def wait(self) -> int:
        """Return the exit code, as a reaped child would."""
        return self.returncode


def _wait_for(predicate: Callable[[], bool], timeout: float) -> bool:
    """Return whether *predicate* holds within *timeout* seconds."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return predicate()


def test_a_torn_down_stage_kills_the_child_its_worker_is_waiting_for(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The stage's stop signal reaches a translator that waits on a child.

    Review R-28 (second pass): the main thread can only stop *waiting* -- the
    pool is closed with ``wait=False`` -- so a worker blocked on a child that
    ignores the console event used to keep the process alive until CPython
    joined it at interpreter teardown (measured 0.6 s to 3.1 s for a 3 s
    page).  The stage therefore publishes its signal to the worker, which
    kills its own child.  The publication is what this pins: with the signal
    missing, or ANDed against the emit policy the stage restores on its way
    out, the child is never killed and the last assertion fails.
    """
    real_translate = wiki.translate_via_cmd
    polling = threading.Event()
    proc = _HangingProc(polling)

    def dispatch(text: str, translate_cmd: str) -> str | None:
        if "page01" in text:
            # The real entry point, so the polling loop and the stop check
            # are the production ones.
            return real_translate(text, translate_cmd)
        # The interrupt comes from a sibling batch, but only once the first
        # worker is really waiting on its child.
        assert polling.wait(10.0), "the first worker never reached its wait loop"
        raise KeyboardInterrupt

    def fake_popen(cmd: object, **kwargs: object) -> _HangingProc:
        del cmd, kwargs
        return proc

    monkeypatch.setattr(wiki, "translate_via_cmd", dispatch)
    monkeypatch.setattr(
        wiki,
        "subprocess",
        types.SimpleNamespace(
            Popen=fake_popen,
            run=subprocess.run,
            TimeoutExpired=subprocess.TimeoutExpired,
            CompletedProcess=subprocess.CompletedProcess,
            DEVNULL=subprocess.DEVNULL,
            PIPE=subprocess.PIPE,
        ),
    )
    # Long enough that only the stop signal can end the wait, and a poll
    # interval long enough that the worker cannot happen to poll *inside* the
    # teardown window: what has to survive the stage's exit is the signal
    # itself, not a race with the moment the emit policy was restored.
    monkeypatch.setattr(wiki, "TRANSLATE_TIMEOUT_S", 900.0)
    monkeypatch.setattr(wiki, "_STOP_POLL_S", 0.2)
    with pytest.raises(KeyboardInterrupt):
        wiki.run(tmp_path / "wiki", "fake-cmd", repo_root=repo, jobs=2)
    assert _wait_for(lambda: proc.killed, 5.0)


def test_translate_failure_lines_are_printed_once_by_the_main_thread(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Every translator failure reaches the terminal exactly once.

    Workers must not write into the live region rich is repainting, so
    :func:`tools.pack.wiki.translate_via_cmd` hands the message back through
    the collect mode and the main thread prints it after stopping the
    progress display.
    """
    def failing(text: str, translate_cmd: str) -> tuple[str | None, str | None]:
        head = text.splitlines()[0]
        return None, f"error[{wiki.Code.WIKI_TRANSLATE_FAILED}]: rc=3 for {head}"

    monkeypatch.setattr(wiki, "_run_translate", failing)
    target = tmp_path / "wiki"
    assert wiki.run(target, "fake-cmd", repo_root=repo, jobs=4) == 0
    err = capsys.readouterr().err
    assert err.count(f"error[{wiki.Code.WIKI_TRANSLATE_FAILED}]") == PAGE_COUNT
    assert err.count("rc=3 for") == PAGE_COUNT
    # The serial default must be restored for the next (non-parallel) call.
    assert getattr(wiki, "_emit_mode") == "print"


def _live_display(stream: StringIO) -> Progress:
    """Build a forced-terminal display with the production column set.

    ``force_terminal`` makes rich render (and therefore parse markup) even
    though the output is an in-memory stream, and the description column --
    absent from rich's defaults -- is what carries the batch row text.
    """
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=Console(file=stream, force_terminal=True, width=120),
    )


def _install_display(monkeypatch: pytest.MonkeyPatch, display: Progress) -> None:
    """Make the generator build *display* instead of a fresh one.

    :mod:`tools.pack.wiki` resolves ``Progress`` as a module global, so
    patching that name is enough to observe the live rows -- and it keeps
    the tests on the public :func:`tools.pack.wiki.run` entry point instead
    of the module-private helpers (pyright forbids private access).
    """

    def factory(*args: object, **kwargs: object) -> Progress:
        """Return the injected display, ignoring rich's own arguments."""
        del args, kwargs
        return display

    monkeypatch.setattr(wiki, "Progress", factory)


def _shown_pages(description: str) -> int:
    """Return the page count the overall row text currently shows.

    Returns ``-1`` when the text is still the initial ``translating`` label,
    so a mismatch reports itself instead of silently comparing to zero.
    """
    match = re.search(r"translating (\d+)/(\d+)", description)
    return int(match.group(1)) if match else -1


def test_console_interrupt_stops_the_run_instead_of_failing_every_page(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """One interrupted child ends the whole run, quietly.

    The ``Ctrl+C`` that kills a translator reaches every sibling as well,
    so the failure channel is the wrong place for it: the run would print
    one ``error[WIKI-0201]`` per remaining page (traceback included) and
    keep translating after the user asked to stop.  The pool must stop,
    and the CLI boundary must turn the interrupt into exit code 130.
    """
    started: list[str] = []
    lock = threading.Lock()

    def interrupted(text: str, translate_cmd: str) -> str | None:
        del translate_cmd
        with lock:
            started.append(text)
            first = len(started) == 1
        if first:
            raise KeyboardInterrupt
        return _english_for(text)

    monkeypatch.setattr(wiki, "translate_via_cmd", interrupted)
    target = tmp_path / "wiki"
    with pytest.raises(KeyboardInterrupt):
        wiki.run(target, "fake-cmd", repo_root=repo, jobs=2)
    # Not one page per remaining document: the stop signal cut the queue.
    assert len(started) <= 4
    err = capsys.readouterr().err
    assert f"error[{wiki.Code.WIKI_TRANSLATE_FAILED}]" not in err
    assert "Traceback" not in err


class _FakeProc:
    """Stand-in for :class:`subprocess.Popen` as used by ``_run_translate``.

    The translator runs through ``Popen`` + a polling ``communicate`` so a
    tearing-down stage can kill its child (review R-15), so the interrupt
    cases stub the process rather than ``subprocess.run``.
    """

    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.killed = False
        self._result = (stdout, stderr)
        self.stdin = io.StringIO()

    def communicate(self, timeout: float | None = None) -> tuple[str, str]:
        """Return the captured output."""
        del timeout
        return self._result

    def kill(self) -> None:
        """Record that the child was terminated."""
        self.killed = True

    def wait(self) -> int:
        """Return the exit code, as a reaped child would."""
        return self.returncode


def test_console_interrupt_exit_code_reaches_the_cli_as_130(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The child's control-C exit code reaches the CLI as a clean 130.

    This is the path the user's report actually took: the console
    interrupt killed the translator, and the parent has to recognise that
    exit code -- not merely an exception raised inside the pool.  Wiring it
    end to end here means a change that breaks the recognition (or the
    130 mapping) fails a test instead of printing tracebacks again.
    """
    traceback = "Traceback (most recent call last):\nKeyboardInterrupt\n^C\n"

    def interrupted_popen(cmd: object, **kwargs: object) -> _FakeProc:
        del cmd, kwargs
        return _FakeProc(0xC000013A, "", traceback)

    # Replace the module reference rather than patching the real
    # ``subprocess``: swapping ``Popen`` process-wide would hand the fake to
    # pytest and coverage as well.
    monkeypatch.setattr(
        wiki,
        "subprocess",
        types.SimpleNamespace(
            Popen=interrupted_popen,
            run=subprocess.run,
            TimeoutExpired=subprocess.TimeoutExpired,
            CompletedProcess=subprocess.CompletedProcess,
            DEVNULL=subprocess.DEVNULL,
            PIPE=subprocess.PIPE,
        ),
    )
    monkeypatch.setattr("tools._util.repo_root", lambda: repo)
    argv = [
        "wiki",
        "--target",
        str(tmp_path / "wiki"),
        "--translate-cmd",
        "fake-cmd",
    ]
    assert cli.main(argv) == 130
    err = capsys.readouterr().err
    assert "interrupted" in err
    assert "Traceback" not in err
    assert f"error[{wiki.Code.WIKI_TRANSLATE_FAILED}]" not in err


def test_batch_progress_advances_page_by_page_while_a_batch_runs(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every finished page moves the bar, not every finished batch.

    Regression guard for the IKJPEK comment (issue note_51450440): a batch
    row used to sit at 0% until its whole batch reported back and then
    jump to 100%, which reads as "no live progress at all" on a 162-page
    run (ten pages per batch, ~20 s per page).

    ``jobs=1`` makes the observation deterministic -- page *n+1* of a batch
    starts only after page *n* returned -- so what a page sees when it
    starts must already include its finished predecessors, on the overall
    row *and* on its own batch row.  The batch-granular advance reported 0
    on both rows for every page but the last of a batch.
    """
    stream = StringIO()
    progress = _live_display(stream)
    _install_display(monkeypatch, progress)

    observed: dict[str, tuple[int, int]] = {}
    texts: dict[str, tuple[int, int]] = {}
    lock = threading.Lock()

    def fake_translate(text: str, translate_cmd: str) -> str | None:
        stem = text.splitlines()[0].removeprefix("# ")
        # Row 0 is the overall task, row 1 the first batch (the generator
        # adds the overall task before the per-batch ones).
        with lock:
            overall_row = progress.tasks[progress.task_ids[0]]
            observed[stem] = (
                int(overall_row.completed),
                int(progress.tasks[progress.task_ids[1]].completed),
            )
            texts[stem] = (
                int(overall_row.completed),
                _shown_pages(str(overall_row.description)),
            )
        return _english_for(text)

    monkeypatch.setattr(wiki, "translate_via_cmd", fake_translate)
    assert wiki.run(tmp_path / "wiki", "fake-cmd", repo_root=repo, jobs=1) == 0
    assert len(observed) == PAGE_COUNT
    # Second page of the first batch: one page must already be counted.
    assert observed["page02"] == (1, 1)
    assert observed["page10"] == (9, 9)
    # First page of the second batch: batch one is full (the snapshot always
    # reads row 1, whichever batch the page belongs to).
    assert observed["page11"] == (10, 10)
    overall_row, *batch_rows = (progress.tasks[tid] for tid in progress.task_ids)
    assert overall_row.completed == PAGE_COUNT
    assert [row.completed for row in batch_rows] == [10, 10, 5]
    # No row may run past its total (a double advance would show here).
    assert all(
        row.total is not None and row.completed <= row.total for row in batch_rows
    )
    # R-01: the row text must not lag its own bar by a page.  Sampling the
    # text at every page start makes the old argument-evaluation order fail:
    # the description was rendered before the advance it belonged to.
    assert texts["page02"][1] == texts["page02"][0]
    assert texts["page10"][1] == 9


def test_concurrent_workers_keep_the_progress_rows_consistent(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Concurrent page reports neither lose nor double-count a page.

    This is the scenario the per-page callbacks exist for: several workers
    advance the same rows at once.  The first two arrivals park on a
    :class:`threading.Barrier`, so parallelism is proved rather than raced
    for; the per-page samples then show a batch row moving mid-run.
    """
    stream = StringIO()
    progress = _live_display(stream)
    _install_display(monkeypatch, progress)
    gate = threading.Barrier(2)
    arrivals: list[int] = []
    mid_run: list[bool] = []
    arrivals_lock = threading.Lock()
    lock = threading.Lock()

    def fake_translate(text: str, translate_cmd: str) -> str | None:
        del translate_cmd
        with arrivals_lock:
            arrivals.append(1)
            waits = len(arrivals) <= 2
        if waits:
            gate.wait(timeout=30)
        with lock:
            # Some batch row must already have moved while the run is going.
            mid_run.append(
                any(
                    int(progress.tasks[tid].completed) > 0
                    for tid in progress.task_ids[1:]
                )
            )
        time.sleep(0.01)
        return _english_for(text)

    monkeypatch.setattr(wiki, "translate_via_cmd", fake_translate)
    assert wiki.run(tmp_path / "wiki", "fake-cmd", repo_root=repo, jobs=2) == 0
    overall_row, *batch_rows = (progress.tasks[tid] for tid in progress.task_ids)
    assert overall_row.completed == PAGE_COUNT
    assert sum(int(row.completed) for row in batch_rows) == PAGE_COUNT
    assert [row.completed for row in batch_rows] == [10, 10, 5]
    assert any(mid_run)


def test_failed_page_still_advances_the_progress_rows(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A page whose translation failed still counts as finished.

    Pinned because the failure branch returns normally (``None`` instead of
    raising): if it skipped the page report, the bar would stop short of
    its total and a run with failures would look like it hung.
    """
    stream = StringIO()
    progress = _live_display(stream)
    _install_display(monkeypatch, progress)

    def fake_translate(text: str, translate_cmd: str) -> str | None:
        return None if "page07" in text else _english_for(text)

    monkeypatch.setattr(wiki, "translate_via_cmd", fake_translate)
    target = tmp_path / "wiki"
    assert wiki.run(target, "fake-cmd", repo_root=repo, jobs=1) == 0
    assert not (target / "page07.en.md").exists()
    overall_row, *batch_rows = (progress.tasks[tid] for tid in progress.task_ids)
    assert overall_row.completed == PAGE_COUNT
    assert sum(int(row.completed) for row in batch_rows) == PAGE_COUNT


def test_batch_row_names_the_page_in_flight_and_escapes_markup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The batch row names the page in flight, brackets included.

    ``README.md`` promises "current page name + overall progress", and a
    Windows file name may legally contain brackets.  rich renders a
    description as markup, so an unescaped ``[name]`` is swallowed as a
    style tag (the row would read ``bracket.en.md``) and a closing-only
    ``[/x]`` even raises :class:`rich.errors.MarkupError` inside the render
    thread, freezing the display.  Escaping the page name avoids both.
    """
    stream = StringIO()
    progress = _live_display(stream)
    _install_display(monkeypatch, progress)
    root = tmp_path / "repo-brackets"
    _touch(root, ".trae/documents/plain.md", "# plain\n\n中文正文\n")
    _touch(root, ".trae/documents/bracket[name].md", "# bracket\n\n中文正文\n")

    described: list[str] = []
    rendered: list[str] = []
    lock = threading.Lock()

    def fake_translate(text: str, translate_cmd: str) -> str | None:
        del text, translate_cmd
        with lock:
            # Sorted collection puts bracket[name].md first, so the row
            # opens on it; refresh forces the markup parser to run.
            assert progress.live.is_started
            described.append(str(progress.tasks[progress.task_ids[1]].description))
            progress.refresh()
            rendered.append(stream.getvalue())
        return "# en\n"

    monkeypatch.setattr(wiki, "translate_via_cmd", fake_translate)
    assert wiki.run(tmp_path / "wiki", "fake-cmd", repo_root=root, jobs=1) == 0
    assert len(described) == 2
    assert described[0] == "batch 1/1 · bracket\\[name].en.md"
    # Rendering unescapes back to the literal page name (and never raises).
    assert "bracket[name].en.md" in rendered[0]
    assert progress.tasks[progress.task_ids[1]].description == "batch 1/1 · plain.en.md"


@pytest.mark.skipif(
    sys.platform == "win32", reason="Windows file names cannot contain a slash"
)
def test_batch_row_survives_a_closing_markup_tag_in_the_page_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A page name that looks like a closing markup tag cannot kill the run.

    ``[/x]`` is the only shape rich actually rejects (:class:`rich.errors.
    MarkupError`), and it needs a slash -- so this is reachable on POSIX
    only.  The error would surface inside rich's render thread, which has no
    guard at all, leaving a frozen display rather than a clean failure.
    """
    stream = StringIO()
    progress = _live_display(stream)
    _install_display(monkeypatch, progress)
    root = tmp_path / "repo-closing-tag"
    _touch(root, ".trae/documents/bracket[/x].md", "# bracket\n\n中文正文\n")

    def fake_translate(text: str, translate_cmd: str) -> str | None:
        del text, translate_cmd
        assert progress.live.is_started
        progress.refresh()
        return "# en\n"

    monkeypatch.setattr(wiki, "translate_via_cmd", fake_translate)
    target = tmp_path / "wiki"
    assert wiki.run(target, "fake-cmd", repo_root=root, jobs=1) == 0
    assert (target / "bracket[/x].en.md").exists()
    assert "bracket[/x].en.md" in stream.getvalue()
