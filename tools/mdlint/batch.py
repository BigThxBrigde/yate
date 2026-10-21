"""Process-pool linting for directory runs.

``pymarkdown`` is pure Python and CPU-bound, so a thread pool cannot speed it
up: the GIL serialises the tokenizer.  The pool therefore uses processes,
shaped like the wiki publisher's batching (consecutive chunks of
:data:`BATCH_SIZE` files per task) so a worker failure costs at most one
batch.

Every worker builds its own engines lazily, one per language profile, and
keeps them for its whole lifetime; the parent only passes ``(path, lang)``
pairs and collects :class:`FileOutcome` values, which keeps the protocol
picklable and the engines out of the parent process.
"""

from __future__ import annotations

import itertools
import os
from collections.abc import Iterator, Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from tools.mdlint.lint import LintEngine, LintViolation, error_message

#: One pool task handles at most this many files (mirrors ``tools.pack.wiki``).
BATCH_SIZE: Final[int] = 10


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
    with ProcessPoolExecutor(max_workers=worker_count(len(batches))) as pool:
        grouped = pool.map(_lint_batch, batches, itertools.repeat(fix))
        for batch in grouped:
            yield from batch


def run_batches(
    items: Sequence[tuple[str, str]], *, fix: bool
) -> list[FileOutcome]:
    """Blocking variant of :func:`iter_batches` (all outcomes, input order)."""
    return list(iter_batches(items, fix=fix))
