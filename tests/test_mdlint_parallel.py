"""Directory PATHs and ``--parallel`` for the mdlint CLI."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.mdlint import cli
from tools.mdlint.batch import FileOutcome, chunk, collect_markdown, worker_count
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

    monkeypatch.setattr(cli, "run_batches", explode)
    assert main(["--check", "--parallel", "--lang", "en", str(docs)]) == 2
    assert "lint backend failure" in capsys.readouterr().err


def test_parallel_file_failure_is_reported(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A worker that returned an error value maps to exit 2 and one message."""
    docs = tmp_path / "docs"
    path = _write(docs, "a.md", "# A\n\nBody\n")

    def failing(items: list[tuple[str, str]], *, fix: bool) -> list[FileOutcome]:
        return [FileOutcome(str(path), "en", [], error="rehydrate index mismatch")]

    monkeypatch.setattr(cli, "run_batches", failing)
    assert main(["--check", "--parallel", "--lang", "en", str(docs)]) == 2
    assert "cannot lint" in capsys.readouterr().err
