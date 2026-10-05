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

import threading
import time
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

import pytest

from tools.pack import cli, wiki

#: Documents per batch the issue mandates; the constant itself is asserted
#: by ``test_batch_size_is_ten_documents``, this is the fixture default.
PAGE_COUNT: int = 25


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
