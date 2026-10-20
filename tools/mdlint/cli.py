"""Command line interface for the mdlint tool.

Exit codes: 0 = clean (or all fixable in ``--fix`` mode), 1 = remaining
violations, 2 = usage error or lint backend failure.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from tools.mdlint.lint import LintEngine, LintViolation
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
        help="Markdown files to process",
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
        help="Suppress per-file output, only summary",
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


def _run_check(
    engine: LintEngine, paths: Sequence[Path], *, quiet: bool
) -> tuple[int, int]:
    """Scan every path; return ``(violations, files_that_could_not_be_linted)``.

    The backend is pure Python and trips on pathological documents (its own
    assertions and plugin errors surface as exceptions); one bad file must
    not abort the run or the commit that triggered it, so it is reported and
    counted instead.
    """
    total = 0
    failed = 0
    for path in paths:
        try:
            violations = engine.scan_file(path)
        except Exception as exc:  # noqa: BLE001 - one bad file must not abort
            print(f"error: cannot lint {path}: {exc}", file=sys.stderr)
            failed += 1
            continue
        total += len(violations)
        if not quiet:
            for violation in violations:
                print(_format_violation(path, violation))
    if not quiet:
        _print_summary("check", paths, total)
    return total, failed


def _run_fix(
    engine: LintEngine, paths: Sequence[Path], *, quiet: bool
) -> tuple[int, int]:
    """Fix every path in place; return ``(remaining, failed)``."""
    total = 0
    failed = 0
    for path in paths:
        try:
            was_fixed, remaining = engine.fix_file(path)
        except Exception as exc:  # noqa: BLE001 - one bad file must not abort
            print(f"error: cannot lint {path}: {exc}", file=sys.stderr)
            failed += 1
            continue
        total += len(remaining)
        if not quiet:
            if was_fixed:
                print(f"fixed: {path}")
            for violation in remaining:
                print(_format_violation(path, violation))
    if not quiet:
        _print_summary("fix", paths, total)
    return total, failed


def _list_rules(engine: LintEngine) -> int:
    """Print the enabled rule IDs, sorted; always exit 0."""
    for rule_id in engine.enabled_rule_ids():
        print(rule_id)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point; return the process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.lang is not None and args.auto_lang:
        parser.error("--lang and --auto-lang are mutually exclusive")

    if args.list_rules:
        return _list_rules(LintEngine(args.lang or "en"))

    if not args.paths:
        parser.error("at least one PATH is required")

    for path in args.paths:
        if not path.is_file():
            print(f"error: not a file: {path}", file=sys.stderr)
            return 2

    groups: dict[str, list[Path]] = {}
    for path in args.paths:
        if args.lang is not None:
            lang = args.lang
        elif args.auto_lang:
            lang = lang_for_path(str(path))
        else:
            lang = "en"
        groups.setdefault(lang, []).append(path)

    engines: dict[str, LintEngine] = {}
    try:
        for lang in groups:
            engines[lang] = LintEngine(lang)
    except Exception as exc:  # backend failure: plugin load, config, etc.
        print(f"error: lint backend failure: {exc}", file=sys.stderr)
        return 2

    total_remaining = 0
    total_failed = 0
    for lang in sorted(engines):
        engine = engines[lang]
        if args.fix:
            remaining, failed = _run_fix(engine, groups[lang], quiet=args.quiet)
        else:
            remaining, failed = _run_check(engine, groups[lang], quiet=args.quiet)
        total_remaining += remaining
        total_failed += failed
    # Violations win over failures: a file the backend choked on must not
    # mask the findings of the files it did lint.
    if total_remaining:
        return 1
    return 2 if total_failed else 0
