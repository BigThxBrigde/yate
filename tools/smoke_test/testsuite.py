"""Headless smoke harness for the yate Textual UI.

Run with: ``python -m tools.smoke_test <command>``

Commands
--------

``run``
    Run scenarios and print a colored report of state assertions.

``snapshot``
    Run scenarios and write JSON baselines (checks + rendered SVG rows)
    under ``tools/smoke_baselines/``.

``compare``
    Run scenarios and diff against the stored baselines (``MATCH`` /
    ``DRIFT``); exits non-zero on drift.

Exit codes: ``0`` all checks passed, ``1`` at least one check failed (or a
baseline drifted), ``2`` nothing matched the filters (or no baselines for
``compare``).

Selection flags (all commands)
------------------------------

``--scenario NAME``   run only NAME (repeatable; default: all)
``--tag TAG``         run only scenarios carrying TAG (repeatable)
``--skip-slow``       drop the P2 scenarios (shell / terminal / huge files)

Tags: ``edit``, ``select``, ``search``, ``files``, ``panes``, ``explorer``,
``command``, ``view``, ``integration``, ``regression``, ``stress``.

Report flags (all commands)
---------------------------

``--svg``             capture and show the rendered SVG text rows
``--svg-rows N``      how many rows to show (default 6)
``--coverage``        report how many ``:`` commands / actions were hit
``--no-invariant``    skip the automatic per-scenario invariant sweep
``--repeat N``        run the selection N times (flake hunting)
``--seed N``          seed for the randomized (fuzz) scenarios
``--json PATH``       also write a machine readable JSON report
``--report PATH``     export the colored report as standalone HTML
``--no-color``        disable ANSI color (CI logs)
``--width N``         force the report width (default: terminal)
``--quiet``           only the summary
``--verbose``         also list passing checks
``--fail-only``       only list failing scenarios in the tables

How it works
------------

The harness drives ``YateApp`` under ``pilot.run_test()`` exactly like
``tests/test_app_textual.py``; it never touches a real terminal.  Every
scenario presses real keys and asserts on *app state* (buffer lines, cursor,
``doc.modified``, pane tree, ...), never on rendered text.

After each scenario the runner appends an invariant sweep (cursor inside the
buffer, no modal left on the stack, no crash, the process-global theme
restored, a saved document matching the bytes on disk), so a scenario that
leaves the app in an impossible state fails even when its own assertions
happen to pass.

This module is the historical entry point (``from .testsuite import main``).
The implementation lives in :mod:`tools.smoke_test.cli` (arguments),
:mod:`tools.smoke_test.harness` (types + runner),
:mod:`tools.smoke_test.report` (rendering),
:mod:`tools.smoke_test.baselines` (snapshot/compare) and
:mod:`tools.smoke_test.scenarios` (the scenarios themselves); everything is
re-exported here so existing imports keep working.
"""

from __future__ import annotations

from .baselines import default_baseline_dir
from .cli import build_parser, cmd_compare, cmd_run, cmd_snapshot, main
from .harness import (
    Check,
    Coverage,
    RunOptions,
    Scenario,
    ScenarioResult,
    TAGS,
    extract_svg_rows,
    new_app,
    run_scenarios,
    select_scenarios,
    snapshot_svg,
    track_coverage,
)
from .report import Reporter
from .scenarios import SCENARIOS

__all__ = [
    "Check",
    "Coverage",
    "Reporter",
    "RunOptions",
    "SCENARIOS",
    "Scenario",
    "ScenarioResult",
    "TAGS",
    "build_parser",
    "cmd_compare",
    "cmd_run",
    "cmd_snapshot",
    "default_baseline_dir",
    "extract_svg_rows",
    "main",
    "new_app",
    "run_scenarios",
    "select_scenarios",
    "snapshot_svg",
    "track_coverage",
]
