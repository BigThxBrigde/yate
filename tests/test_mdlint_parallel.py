"""Directory PATHs and ``--parallel`` for the mdlint CLI."""

from __future__ import annotations

import signal
from concurrent.futures import Future, ProcessPoolExecutor
from pathlib import Path
from typing import cast

import pytest

from tools.mdlint import batch, cli
from tools.mdlint.batch import (
    FileOutcome,
    TextOutcome,
    chunk,
    collect_markdown,
    worker_count,
)
from tools.mdlint.cli import main


def _write(root: Path, rel: str, text: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_collect_markdown_is_recursive_and_sorted(tmp_path: Path) -> None:
    """Only ``*.md`` files are collected, in a stable order."""
    _write(tmp_path, "b.md", "# b\n")
    _write(tmp_path, "nested/a.md", "# a\n")
    _write(tmp_path, "notes.txt", "ignored\n")
    found = collect_markdown(tmp_path)
    assert found == sorted(found)
    assert {path.name for path in found} == {"a.md", "b.md"}


def test_chunk_and_worker_count_cover_the_edges() -> None:
    """Chunks tile the input and never start more workers than batches."""
    assert chunk([1, 2, 3, 4, 5], size=2) == [[1, 2], [3, 4], [5]]
    assert chunk([], size=10) == []
    assert worker_count(1) == 1
    assert worker_count(1000) >= 1
    with pytest.raises(ValueError):
        chunk([1], size=0)


def test_directory_path_is_expanded(tmp_path: Path) -> None:
    """A directory PATH lints every Markdown file below it."""
    _write(tmp_path / "docs", "bad.md", "Body\n")
    assert main(["--check", "--lang", "en", str(tmp_path / "docs")]) == 1


def test_parallel_check_reports_every_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """``--parallel`` over a directory lints all files and exits 1 on violations."""
    docs = tmp_path / "docs"
    _write(docs, "one.md", "Body\n")
    _write(docs, "nested/two.md", "# Two\n\nBody\n")
    assert main(["--check", "--parallel", "--lang", "en", str(docs)]) == 1
    out = capsys.readouterr().out
    assert "one.md" in out
    assert "two.md" not in out  # clean pages print nothing


def test_parallel_fix_rewrites_the_files(tmp_path: Path) -> None:
    """``--parallel --fix`` writes the fixes back to disk."""
    docs = tmp_path / "docs"
    dirty = _write(docs, "dirty.md", "# Title\n\n\n\nBody")
    assert main(["--fix", "--parallel", "--lang", "en", str(docs)]) == 0
    assert dirty.read_text(encoding="utf-8") == "# Title\n\nBody\n"


def test_parallel_without_a_directory_runs_sequentially(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A PATH list of files keeps ``--parallel`` inert (with a note)."""
    path = _write(tmp_path, "bad.md", "Body\n")
    assert main(["--check", "--parallel", "--lang", "en", str(path)]) == 1
    assert "--parallel needs a directory" in capsys.readouterr().err


def test_missing_path_is_a_usage_error(tmp_path: Path) -> None:
    """A PATH that is neither file nor directory exits with 2."""
    assert main(["--check", "--lang", "en", str(tmp_path / "nope")]) == 2


def test_parallel_pool_failure_exits_2(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A pool that cannot start is a backend failure, not a traceback."""
    docs = tmp_path / "docs"
    _write(docs, "a.md", "# A\n\nBody\n")

    def explode(items: list[tuple[str, str]], *, fix: bool) -> list[FileOutcome]:
        raise RuntimeError("cannot start a new process")

    monkeypatch.setattr(cli, "iter_batches", explode)
    assert main(["--check", "--parallel", "--lang", "en", str(docs)]) == 2
    assert "error: cannot start a new process" in capsys.readouterr().err


def test_parallel_file_failure_is_reported(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A worker that returned an error value maps to exit 2 and one message."""
    docs = tmp_path / "docs"
    path = _write(docs, "a.md", "# A\n\nBody\n")

    def failing(
        items: list[tuple[str, str]], *, fix: bool
    ) -> list[FileOutcome]:
        return [FileOutcome(str(path), "en", [], error="rehydrate index mismatch")]

    monkeypatch.setattr(cli, "iter_batches", failing)
    assert main(["--check", "--parallel", "--lang", "en", str(docs)]) == 2
    err = capsys.readouterr().err
    assert "cannot lint" in err
    assert "Traceback" not in err


def test_fix_texts_cancels_queued_work_when_the_pool_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A ``Ctrl+C`` inside the text pool must not drain the queue.

    ``shutdown(wait=True)`` would keep the user waiting for every queued
    document (minutes on a full wiki run), so the failure path closes the
    pool with ``cancel_futures=True`` and lets the interrupt propagate.
    """
    shutdowns: list[tuple[bool, bool]] = []

    class _FailingPool:
        def __init__(self, max_workers: int, **kwargs: object) -> None:
            self.max_workers = max_workers

        def submit(self, *args: object) -> object:
            raise KeyboardInterrupt

        def shutdown(self, wait: bool = True, cancel_futures: bool = False) -> None:
            shutdowns.append((wait, cancel_futures))

    monkeypatch.setattr(batch, "ProcessPoolExecutor", _FailingPool)
    with pytest.raises(KeyboardInterrupt):
        batch.fix_texts([("en", "# a\n")])
    assert shutdowns == [(False, True)]


def test_fix_texts_pool_ownership_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An injected pool stays running; a run-local pool is closed on exit.

    The wiki publisher shares one pool across several lint passes, so
    :func:`~tools.mdlint.batch.fix_texts` must leave a pool it did not start
    alone -- shutting it down is the owner's job.  A pool of its own is shut
    down with ``wait=True`` (all work is done) before the results return.
    """
    shutdowns: list[tuple[bool, bool]] = []

    class _InstantPool:
        def __init__(self, max_workers: int = 0, **kwargs: object) -> None:
            pass

        def submit(
            self, fn: object, batch: list[tuple[str, str]]
        ) -> Future[list[TextOutcome]]:
            future: Future[list[TextOutcome]] = Future()
            future.set_result([TextOutcome(text, []) for _lang, text in batch])
            return future

        def shutdown(self, wait: bool = True, cancel_futures: bool = False) -> None:
            shutdowns.append((wait, cancel_futures))

    items = [("en", "# a\n"), ("en", "# b\n"), ("zh", "# c\n")]
    expected = [TextOutcome(text, []) for _lang, text in items]

    injected = _InstantPool()
    assert batch.fix_texts(items, pool=cast(ProcessPoolExecutor, injected)) == expected
    assert shutdowns == []

    monkeypatch.setattr(batch, "ProcessPoolExecutor", _InstantPool)
    assert batch.fix_texts(items) == expected
    assert shutdowns == [(True, False)]


def test_progress_reports_each_landed_document(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The progress callback fires once per document, ending at ``(total, total)``.

    Results are collected as they finish, so the callback tracks real
    completion instead of stalling behind the longest document -- what an
    in-order ``pool.map`` would do on a run of mixed page sizes.
    """

    class _InstantPool:
        def __init__(self, max_workers: int = 0, **kwargs: object) -> None:
            pass

        def submit(
            self, fn: object, batch: list[tuple[str, str]]
        ) -> Future[list[TextOutcome]]:
            future: Future[list[TextOutcome]] = Future()
            future.set_result([TextOutcome(text, []) for _lang, text in batch])
            return future

        def shutdown(self, wait: bool = True, cancel_futures: bool = False) -> None:
            pass

    monkeypatch.setattr(batch, "ProcessPoolExecutor", _InstantPool)
    calls: list[tuple[int, int]] = []
    items = [("en", "# a\n"), ("en", "# b\n"), ("zh", "# c\n")]
    outcomes = batch.fix_texts(
        items, progress=lambda done, total: calls.append((done, total))
    )
    assert outcomes == [TextOutcome(text, []) for _lang, text in items]
    assert calls == [(1, 3), (2, 3), (3, 3)]


def test_worker_initializer_ignores_sigint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pool workers register ``SIG_IGN`` for ``SIGINT`` (the parent owns Ctrl+C).

    On Windows a console ``Ctrl+C`` reaches the whole process group; without
    this hook every worker would print its own ``KeyboardInterrupt``
    traceback over the parent's coded ``interrupted`` line.
    """
    registered: list[tuple[int, int]] = []

    def fake_signal(num: int, handler: int) -> None:
        registered.append((num, handler))

    monkeypatch.setattr(batch.signal, "signal", fake_signal)
    batch.worker_initializer()
    assert registered == [(signal.SIGINT, signal.SIG_IGN)]


def test_progress_bar_is_not_drawn_without_a_tty(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Captured output gets the plain report, never the live bar."""
    docs = tmp_path / "docs"
    _write(docs, "bad.md", "Body\n")
    assert main(["--check", "--parallel", "--lang", "en", str(docs)]) == 1
    out = capsys.readouterr().out
    assert "bad.md" in out
    assert "linting" not in out
