"""Command line interface for the mdlint tool.

Exit codes: 0 = clean (or all fixable in ``--fix`` mode), 1 = remaining
violations, 2 = usage error or lint backend failure, 130 = interrupted.

The CLI is the boundary where a traceback must never reach the terminal
(the wiki publisher draws the same line): backend and pool failures print
one ``error: ...`` line with the backend's own summary, ``--quiet`` silences
per-file output, and an interactive run shows a live progress bar.
"""

from __future__ import annotations

import argparse
import functools
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
)

from tools.mdlint.batch import (
    FileOutcome,
    collect_markdown,
    iter_batches,
)
from tools.mdlint.lint import LintEngine, LintViolation, error_message
from tools.mdlint.rules import LANGS, lang_for_path


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for ``python -m tools.mdlint``."""
    parser = argparse.ArgumentParser(
        prog="python -m tools.mdlint",
        description="Markdown lint tool backed by pymarkdownlnt.",
    )
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        metavar="PATH",
        help="Markdown files or directories (directories are searched for *.md)",
    )
    parser.add_argument(
        "--lang",
        choices=LANGS,
        default=None,
        help="Rule profile to apply to every file (default: en)",
    )
    parser.add_argument(
        "--auto-lang",
        action="store_true",
        help="Pick the rule profile per file from its path "
        "(*.zh.md -> zh, *.en.md -> en, .trae/** -> zh, otherwise en)",
    )
    parser.add_argument(
        "--parallel",
        action="store_true",
        help="Lint directory PATHs in parallel batches (process pool); "
        "a PATH list without a directory runs sequentially",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--check",
        action="store_true",
        help="Scan and report violations (default mode)",
    )
    mode.add_argument(
        "--fix",
        action="store_true",
        help="Auto-fix what is fixable, then report remaining",
    )
    parser.add_argument(
        "--list-rules",
        action="store_true",
        help="Print enabled rules and exit",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress per-file output and the progress bar, only summary",
    )
    return parser


def _format_violation(path: Path, violation: LintViolation) -> str:
    """Format one violation as ``path:line:col: rule_id message``."""
    return (
        f"{path}:{violation.line}:{violation.column}: "
        f"{violation.rule_id} {violation.message}"
    )


def _print_summary(mode: str, paths: Sequence[Path], total: int) -> None:
    """Print a one-line summary for a run over *paths*."""
    files = "file" if len(paths) == 1 else "files"
    print(f"{mode}: {total} violation(s) in {len(paths)} {files}")


def _emit(progress: Progress | None, text: str) -> None:
    """Print one report line above the live bar (or straight to stdout)."""
    if progress is None:
        print(text)
        return
    progress.console.print(text, markup=False, highlight=False)


def _advance(progress: Progress | None, task: TaskID | None) -> None:
    """Advance the live bar by one file, if one is running."""
    if progress is not None and task is not None:
        progress.update(task, advance=1)


def _start_progress(
    total: int, description: str, *, quiet: bool
) -> tuple[Progress, TaskID] | None:
    """Start a live bar for interactive runs.

    Piped or captured output (the tests) and ``--quiet`` get no bar at all:
    control sequences must never end up in a log or an assertion.
    """
    if quiet or total == 0 or not sys.stdout.isatty():
        return None
    progress = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
    )
    progress.start()
    return progress, progress.add_task(description, total=total)


def _lint_path(
    engine: LintEngine,
    path: Path,
    *,
    fix: bool,
    quiet: bool,
    emit: Callable[[str], None],
) -> tuple[int, int]:
    """Lint one path; return ``(violations, files_that_could_not_be_linted)``.

    The backend trips on pathological documents (its own assertions and
    plugin errors surface as exceptions); one bad file is reported as a
    single line and counted instead of aborting the run.
    """
    try:
        if fix:
            was_fixed, violations = engine.fix_file(path)
        else:
            was_fixed = False
            violations = engine.scan_file(path)
    except Exception as exc:  # noqa: BLE001 - one bad file must not abort
        print(
            f"error: cannot lint {path}: {error_message(exc)}",
            file=sys.stderr,
        )
        return 0, 1
    if not quiet:
        if was_fixed:
            emit(f"fixed: {path}")
        for violation in violations:
            emit(_format_violation(path, violation))
    return len(violations), 0


def _list_rules(engine: LintEngine) -> int:
    """Print the enabled rule IDs, sorted; always exit 0."""
    for rule_id in engine.enabled_rule_ids():
        print(rule_id)
    return 0


def _lang_for(path: Path, *, lang: str | None, auto: bool) -> str:
    """Resolve the profile for one file following the CLI precedence."""
    if lang is not None:
        return lang
    if auto:
        return lang_for_path(str(path))
    return "en"


def _report_outcome(
    outcome: FileOutcome, *, quiet: bool, emit: Callable[[str], None]
) -> tuple[int, int]:
    """Print one pooled result; return ``(violations, failed)``."""
    if outcome.error is not None:
        print(
            f"error: cannot lint {outcome.path}: {outcome.error}",
            file=sys.stderr,
        )
        return 0, 1
    if not quiet:
        if outcome.was_fixed:
            emit(f"fixed: {outcome.path}")
        for violation in outcome.violations:
            emit(_format_violation(Path(outcome.path), violation))
    return len(outcome.violations), 0


def _run_parallel(
    files: Sequence[Path],
    args: argparse.Namespace,
    *,
    emit: Callable[[str], None],
    advance: Callable[[], None],
) -> tuple[int, int]:
    """Lint *files* through the process pool, reporting in input order."""
    items = [
        (str(path), _lang_for(path, lang=args.lang, auto=args.auto_lang))
        for path in files
    ]
    # Validate the backend once in the parent: a missing dependency must
    # report a single message instead of one failure per pooled file.
    try:
        for lang in sorted({lang for _, lang in items}):
            LintEngine(lang)
    except Exception as exc:  # backend failure: plugin load, config, etc.
        print(f"error: {error_message(exc)}", file=sys.stderr)
        return 0, 1
    total = 0
    failed = 0
    try:
        for outcome in iter_batches(items, fix=args.fix):
            violations, broken = _report_outcome(outcome, quiet=args.quiet, emit=emit)
            total += violations
            failed += broken
            advance()
    except Exception as exc:  # pool start-up failure: interpreter, plugins
        print(f"error: {error_message(exc)}", file=sys.stderr)
        return total, failed + 1
    return total, failed


def _dispatch(argv: Sequence[str] | None) -> int:
    """Parse arguments, expand PATHs and run the selected mode."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.lang is not None and args.auto_lang:
        parser.error("--lang and --auto-lang are mutually exclusive")

    if args.list_rules:
        return _list_rules(LintEngine(args.lang or "en"))

    if not args.paths:
        parser.error("at least one PATH is required")

    files: list[Path] = []
    saw_directory = False
    for path in args.paths:
        if path.is_dir():
            saw_directory = True
            files.extend(collect_markdown(path))
        elif path.is_file():
            files.append(path)
        else:
            print(f"error: not a file or directory: {path}", file=sys.stderr)
            return 2
    # Overlapping directories can name the same file twice; lint it once.
    files = list(dict.fromkeys(files))

    parallel = args.parallel
    if parallel and not saw_directory:
        print(
            "mdlint: --parallel needs a directory PATH; running sequentially",
            file=sys.stderr,
        )
        parallel = False

    mode = "fix" if args.fix else "check"
    started = _start_progress(len(files), f"linting {mode}", quiet=args.quiet)
    progress = started[0] if started is not None else None
    task = started[1] if started is not None else None
    emit = functools.partial(_emit, progress)
    advance = functools.partial(_advance, progress, task)
    total_remaining = 0
    total_failed = 0
    try:
        if parallel:
            total_remaining, total_failed = _run_parallel(
                files, args, emit=emit, advance=advance
            )
        else:
            total_remaining, total_failed = _run_sequential(
                files, args, emit=emit, advance=advance
            )
    finally:
        if progress is not None:
            progress.stop()
    # --quiet keeps the summary; only the per-file report and bar are gone.
    _print_summary(mode, files, total_remaining)
    # Violations win over failures: a file the backend choked on must not
    # mask the findings of the files it did lint.
    if total_remaining:
        return 1
    return 2 if total_failed else 0


def _run_sequential(
    files: Sequence[Path],
    args: argparse.Namespace,
    *,
    emit: Callable[[str], None],
    advance: Callable[[], None],
) -> tuple[int, int]:
    """Lint *files* in this process, reporting in input order."""
    langs = {
        _lang_for(path, lang=args.lang, auto=args.auto_lang) for path in files
    }
    engines: dict[str, LintEngine] = {}
    try:
        for lang in sorted(langs):
            engines[lang] = LintEngine(lang)
    except Exception as exc:  # backend failure: plugin load, config, etc.
        print(f"error: {error_message(exc)}", file=sys.stderr)
        return 0, 1

    total_remaining = 0
    total_failed = 0
    for path in files:
        lang = _lang_for(path, lang=args.lang, auto=args.auto_lang)
        remaining, failed = _lint_path(
            engines[lang], path, fix=args.fix, quiet=args.quiet, emit=emit
        )
        total_remaining += remaining
        total_failed += failed
        advance()
    return total_remaining, total_failed


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point; return the process exit code, never a traceback."""
    try:
        return _dispatch(argv)
    except KeyboardInterrupt:
        print("\nmdlint: interrupted", file=sys.stderr)
        return 130
    except Exception as exc:  # noqa: BLE001 - CLI boundary, no tracebacks
        print(f"error: {error_message(exc)}", file=sys.stderr)
        return 2
