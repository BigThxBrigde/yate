"""Headless smoke harness for the yate Textual UI.

Run with: ``python -m tools.smoke_test``

Subcommands:

* ``run [--scenario NAME] [--tag TAG] [--svg] [--coverage] ...``
  Run scenarios and print a colored PASS/FAIL report of state assertions;
  with ``--svg`` also capture and show the top SVG text rows.

* ``snapshot [--scenario NAME] [--outdir DIR]``
  Run scenarios and write JSON baselines (checks + extracted SVG rows)
  under ``tools/smoke_baselines/`` for later comparison.

* ``compare [--scenario NAME] [--baseline DIR]``
  Run scenarios and diff against the stored baselines, reporting
  ``MATCH`` / ``DRIFT`` and exiting non-zero on drift.

The harness drives ``YateApp`` under ``pilot.run_test()`` exactly like
``tests/test_app_textual.py``; it never touches the real terminal.

This module is the historical entry point (``from .testsuite import main``).
The implementation now lives in :mod:`tools.smoke_test.cli` (arguments),
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
