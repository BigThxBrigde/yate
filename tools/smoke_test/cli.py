"""Argument parsing and the three subcommands (``run`` / ``snapshot`` /
``compare``).

Exit codes: ``0`` everything passed, ``1`` at least one check failed (or a
baseline drifted), ``2`` no baselines are available for ``compare``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from collections.abc import Sequence

from . import baselines
from .harness import (
    Coverage,
    DEFAULT_SCENARIO_TIMEOUT_S,
    RunOptions,
    Scenario,
    ScenarioResult,
    run_scenarios,
    select_scenarios,
    set_seed,
    track_coverage,
)
from .report import Reporter
from .scenarios import SCENARIOS

__all__ = ["build_parser", "main"]


# ------------------------------------------------------------------ helpers


def _add_common_filters(p: argparse.ArgumentParser) -> None:
    p.add_argument("--scenario", action="append", metavar="NAME",
                   help="scenario name (repeatable; default: all)")
    p.add_argument("--tag", action="append", metavar="TAG",
                   help="only scenarios carrying TAG (repeatable)")
    p.add_argument("--skip-slow", action="store_true",
                   help="skip P2 (slow / platform dependent) scenarios")


def _add_report_options(p: argparse.ArgumentParser) -> None:
    p.add_argument("--no-color", action="store_true",
                   help="disable ANSI color (useful in CI logs)")
    p.add_argument("--width", type=int, default=None,
                   help="force the report width (default: terminal)")
    p.add_argument("--quiet", action="store_true",
                   help="only the summary (no tables)")
    p.add_argument("--verbose", action="store_true",
                   help="also list passing checks")
    p.add_argument("--fail-only", action="store_true",
                   help="only list failing scenarios in the tables")
    p.add_argument("--svg", action="store_true",
                   help="capture and show the rendered SVG text rows")
    p.add_argument("--svg-rows", type=int, default=6,
                   help="how many SVG rows to show (default: 6)")
    p.add_argument("--with-svg", action="store_true",
                   help="also put the SVG rows in the baseline / compare them "
                        "(they embed absolute paths, so they drift between "
                        "machines -- off by default)")
    p.add_argument("--json", metavar="PATH", default=None,
                   help="also write a machine readable JSON report")
    p.add_argument("--report", metavar="PATH", default=None,
                   help="export the colored report as standalone HTML")
    p.add_argument("--no-invariant", action="store_true",
                   help="skip the automatic per-scenario invariant sweep")
    p.add_argument("--timeout", type=float, default=DEFAULT_SCENARIO_TIMEOUT_S,
                   metavar="S",
                   help="per-scenario wall clock budget in seconds; a "
                        "scenario exceeding it is cancelled and fails "
                        f"(default: {DEFAULT_SCENARIO_TIMEOUT_S:g})")
    p.add_argument("--repeat", type=int, default=1, metavar="N",
                   help="run the selection N times (flake hunting)")
    p.add_argument("--seed", type=int, default=None,
                   help="seed for the randomized (fuzz) scenarios")


def _reporter(args: argparse.Namespace) -> Reporter:
    return Reporter(
        color=not args.no_color,
        width=args.width,
        quiet=args.quiet,
        verbose=args.verbose,
        fail_only=args.fail_only,
        svg_rows=args.svg_rows,
        html_path=args.report,
    )


def _write_json(path: str, results: Sequence[ScenarioResult],
                cov: Coverage | None) -> None:
    payload: dict[str, Any] = {
        "scenarios": [
            {
                "name": r.name,
                "tags": list(r.tags),
                "duration": round(r.duration, 4),
                "error": r.error,
                "ok": r.fail_count == 0 and r.error is None,
                "checks": [
                    {
                        "label": c.label,
                        "expected": c.expected,
                        "actual": c.actual,
                        "ok": c.ok,
                        "invariant": c.invariant,
                    }
                    for c in r.checks
                ],
            }
            for r in results
        ],
        "totals": {
            "ok": sum(r.ok_count for r in results),
            "fail": sum(r.fail_count for r in results),
            "scenarios": len(results),
            "passed": sum(1 for r in results
                          if r.fail_count == 0 and r.error is None),
        },
    }
    if cov is not None:
        (c_hit, c_total, c_missing), (a_hit, a_total, a_missing) = cov.report()
        payload["coverage"] = {
            "commands": {"hit": c_hit, "total": c_total, "missing": c_missing},
            "actions": {"hit": a_hit, "total": a_total, "missing": a_missing},
        }
    Path(path).write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def _worse(candidate: ScenarioResult, incumbent: ScenarioResult) -> bool:
    """Whether *candidate* is a worse run than *incumbent*.

    ``--repeat`` reports the worst iteration: an error (crash or timeout)
    outranks any run without one, otherwise more failing checks lose.
    """
    if (candidate.error is not None) != (incumbent.error is not None):
        return candidate.error is not None
    return candidate.fail_count > incumbent.fail_count


def _execute(
    selected: list[Scenario], tmp_root: Path, options: RunOptions,
    *, repeat: int,
) -> tuple[list[ScenarioResult], Coverage]:
    """Run *selected* ``repeat`` times; keep the worst result per scenario.

    ``--repeat`` is a flake detector: a scenario counts as failed when *any*
    iteration failed, and the reported result is that (worst) run so the
    failure detail is the interesting one.
    """
    best: dict[str, ScenarioResult] = {}
    with track_coverage() as cov:
        for _ in range(max(1, repeat)):
            for result in run_scenarios(selected, tmp_root, options):
                previous = best.get(result.name)
                if previous is None or _worse(result, previous):
                    best[result.name] = result
    # Selection order, with the worst run of each scenario reported.
    return [best[s.name] for s in selected], cov


# ------------------------------------------------------------- subcommands


def cmd_run(args: argparse.Namespace) -> int:
    selected = select_scenarios(
        SCENARIOS, names=args.scenario, tags=args.tag,
        skip_slow=args.skip_slow,
    )
    if not selected:
        print("no scenario matches the given filters")
        return 2
    if args.seed is not None:
        set_seed(args.seed)
    reporter = _reporter(args)
    if not args.quiet:
        reporter.header(
            selected=selected, tags=args.tag or [], command="run",
            seed=args.seed, repeat=args.repeat,
        )
    options = RunOptions(
        svg=args.svg,
        invariants=not args.no_invariant,
        timeout=args.timeout,
        progress=reporter.progress,
    )
    with TemporaryDirectory() as td:
        results, cov = _execute(
            selected, Path(td), options, repeat=args.repeat
        )
    if not args.quiet:
        reporter.results(results)
        if args.svg:
            reporter.svg(results)
        if args.coverage:
            reporter.coverage(cov)
    exit_code = 0 if all(
        r.fail_count == 0 and r.error is None for r in results
    ) else 1
    reporter.summary(results, exit_code=exit_code)
    if args.json:
        _write_json(args.json, results, cov)
        reporter.json_written(Path(args.json))
    return exit_code


def cmd_snapshot(args: argparse.Namespace) -> int:
    selected = select_scenarios(
        SCENARIOS, names=args.scenario, tags=args.tag,
        skip_slow=args.skip_slow,
    )
    if not selected:
        print("no scenario matches the given filters")
        return 2
    if args.seed is not None:
        set_seed(args.seed)
    outdir = Path(args.outdir) if args.outdir else baselines.default_baseline_dir()
    reporter = _reporter(args)
    if not args.quiet:
        reporter.header(
            selected=selected, tags=args.tag or [], command="snapshot",
            seed=args.seed, repeat=args.repeat,
        )
    options = RunOptions(
        svg=args.with_svg, invariants=not args.no_invariant,
        timeout=args.timeout, progress=reporter.progress,
    )
    with TemporaryDirectory() as td:
        results, cov = _execute(
            selected, Path(td), options, repeat=args.repeat
        )
    count = baselines.write_baselines(results, outdir)
    if not args.quiet:
        reporter.results(results)
        if args.coverage:
            reporter.coverage(cov)
    exit_code = 0 if all(
        r.fail_count == 0 and r.error is None for r in results
    ) else 1
    reporter.summary(results, exit_code=exit_code)
    reporter.note(f"wrote {count} baselines to {outdir}")
    if args.json:
        _write_json(args.json, results, cov)
        reporter.json_written(Path(args.json))
    return exit_code


def cmd_compare(args: argparse.Namespace) -> int:
    baseline_dir = (
        Path(args.baseline) if args.baseline
        else baselines.default_baseline_dir()
    )
    reporter = _reporter(args)
    if not baseline_dir.exists():
        reporter.summary([], exit_code=2)
        reporter.note(
            f"no baselines at {baseline_dir}; run `snapshot` first",
            style="yellow",
        )
        return 2
    selected = select_scenarios(
        SCENARIOS, names=args.scenario, tags=args.tag,
        skip_slow=args.skip_slow,
    )
    if not selected:
        print("no scenario matches the given filters")
        return 2
    if args.seed is not None:
        set_seed(args.seed)
    if not args.quiet:
        reporter.header(
            selected=selected, tags=args.tag or [], command="compare",
            seed=args.seed, repeat=args.repeat,
        )
    options = RunOptions(
        svg=args.with_svg, invariants=not args.no_invariant,
        timeout=args.timeout, progress=reporter.progress,
    )
    with TemporaryDirectory() as td:
        results, cov = _execute(
            selected, Path(td), options, repeat=args.repeat
        )
    exit_code = 0
    if not args.quiet:
        reporter.note("compare")
    for r in results:
        base = baseline_dir / f"{r.name}.json"
        if not base.exists():
            reporter.compare(r.name, "SKIP")
            continue
        expected = baselines.load_baseline(base)
        actual = baselines.serialize(r)
        if not args.with_svg:
            # The rendered rows embed absolute paths (breadcrumbs, tab
            # titles, "saved <path>" messages), so they are only part of
            # the contract when the baseline was taken with --with-svg.
            expected.pop("svg_rows", None)
            actual.pop("svg_rows", None)
        if expected == actual:
            reporter.compare(r.name, "MATCH")
            continue
        exit_code = 1
        reporter.compare(
            r.name, "DRIFT", baselines.diff_baseline(expected, actual)
        )
    if not args.quiet and args.coverage:
        reporter.coverage(cov)
    reporter.summary(results, exit_code=exit_code)
    if args.json:
        _write_json(args.json, results, cov)
        reporter.json_written(Path(args.json))
    return exit_code


# ----------------------------------------------------------------- parser


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="tools.smoke_test",
        description="yate headless smoke harness",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    pr = sub.add_parser("run", help="run scenarios and print PASS/FAIL")
    _add_common_filters(pr)
    _add_report_options(pr)
    pr.add_argument("--coverage", action="store_true",
                    help="report :command / action coverage")
    pr.set_defaults(func=cmd_run)

    ps = sub.add_parser("snapshot", help="write JSON baselines")
    _add_common_filters(ps)
    _add_report_options(ps)
    ps.add_argument("--coverage", action="store_true",
                    help="report :command / action coverage")
    ps.add_argument(
        "--outdir",
        help=f"baseline dir (default: {baselines.default_baseline_dir()})",
    )
    ps.set_defaults(func=cmd_snapshot)

    pc = sub.add_parser("compare", help="run and diff against baselines")
    _add_common_filters(pc)
    _add_report_options(pc)
    pc.add_argument("--coverage", action="store_true",
                    help="report :command / action coverage")
    pc.add_argument(
        "--baseline",
        help=f"baseline dir (default: {baselines.default_baseline_dir()})",
    )
    pc.set_defaults(func=cmd_compare)

    return p


def main(argv: list[str] | None = None) -> int:
    p = build_parser()
    args = p.parse_args(argv)
    return int(args.func(args))
