"""Regression tests for the repository's merge gates.

The gates are *configuration*, not code: ``pyproject.toml`` decides whether the
coverage threshold still exists and whether ``--cov`` stays opt-in, and
``.github/workflows/test.yml`` decides whether CI runs the coverage gate and the
Textual smoke suite at all.  Nothing else in the suite goes red when one of those
files quietly loses a threshold or a job, so the configuration itself is asserted
here -- the cheapest possible place to notice a bypass before it merges.
"""

from __future__ import annotations

import ast
import re
import tomllib
from pathlib import Path
from typing import cast

PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
PYPROJECT: Path = PROJECT_ROOT / "pyproject.toml"
WORKFLOW: Path = PROJECT_ROOT / ".github" / "workflows" / "test.yml"
#: The Gitee pipeline: a second CI front with its own copy of the commands.
GITEE_WORKFLOW: Path = PROJECT_ROOT / ".workflow" / "test.yml"
SMOKE_PACKAGE: Path = PROJECT_ROOT / "tools" / "smoke_test"
SCENARIO_DIR: Path = SMOKE_PACKAGE / "scenarios"

#: The coverage gate threshold.  Single source of truth:
#: ``[tool.coverage.report] fail_under`` in ``pyproject.toml``; the CI command
#: line must not repeat it, so lowering it here is impossible without editing
#: the configuration and failing these tests.
EXPECTED_FAIL_UNDER: int = 75

#: Modules of the scenarios package that are plumbing, not scenario groups: the
#: shared helpers and the aggregator which concatenates every group's list.
SCENARIO_PACKAGE_MODULES: frozenset[str] = frozenset({"__init__.py", "_base.py"})

#: Measured 2026-10-18: ``scenarios/*.py`` holds 21 files, i.e. 19 scenario
#: modules plus the two package modules above (the harness runs 112 scenarios).
#: The floor exists so that deleting or renaming the whole directory is caught
#: even though nothing imports it from pytest.
MIN_SCENARIO_MODULES: int = 19

#: How many lines around a hit still count as "the same step" when checking that
#: the smoke command lives in a ``run:`` block rather than in a comment.
RUN_STEP_WINDOW: int = 5


def _read_pyproject() -> dict[str, object]:
    """Parse ``pyproject.toml`` into nested plain dicts."""
    return tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))


def _config(data: dict[str, object], *keys: str) -> object:
    """Walk *keys* down nested config tables and return the value found there."""
    current: dict[str, object] = data
    for key in keys[:-1]:
        assert key in current, f"missing config key: {'.'.join(keys)}"
        current = cast("dict[str, object]", current[key])
    last = keys[-1]
    assert last in current, f"missing config key: {'.'.join(keys)}"
    return current[last]


def _module_level_scenarios(path: Path) -> bool:
    """Whether *path* assigns ``SCENARIOS`` at module level.

    A module that only imports its ``SCENARIOS`` from elsewhere contributes no
    scenarios of its own, so it is a silent hole in the smoke suite.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        targets: list[ast.expr] = []
        if isinstance(node, ast.Assign):
            targets = list(node.targets)
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        for target in targets:
            if isinstance(target, ast.Name) and target.id == "SCENARIOS":
                return True
    return False


def _scenario_modules() -> list[Path]:
    """Scenario modules of the smoke package, without the package plumbing."""
    return sorted(
        path for path in SCENARIO_DIR.glob("*.py")
        if path.name not in SCENARIO_PACKAGE_MODULES
    )


def test_coverage_fail_under_is_declared_in_pyproject() -> None:
    """The coverage gate threshold is declared in pyproject.toml and is 75."""
    value = _config(_read_pyproject(), "tool", "coverage", "report", "fail_under")
    assert value == EXPECTED_FAIL_UNDER, (
        f"[tool.coverage.report] fail_under must stay {EXPECTED_FAIL_UNDER}, got {value!r}"
    )


def test_coverage_threshold_is_not_hardcoded_on_the_ci_command_line() -> None:
    """No pipeline repeats the threshold (one source of truth).

    Both CI fronts matter: GitHub Actions (``.github/workflows/test.yml``) and
    the Gitee pipeline (``.workflow/test.yml``).  Each one carrying its own
    ``--cov-fail-under=75`` is how the two silently drift apart, so the
    assertion sweeps both instead of one.

    The one allowed value is ``--cov-fail-under=0`` on the GitHub shard legs
    (2026-11-03): a shard alone covers far under the gate, so shards only
    collect data; the real threshold is enforced by the coverage job via
    ``coverage report`` reading pyproject -- see the combine guard below.
    """
    offenders: list[str] = []
    for pipeline in (WORKFLOW, GITEE_WORKFLOW):
        if not pipeline.exists():
            continue
        text = pipeline.read_text(encoding="utf-8")
        for value in re.findall(r"--cov-fail-under=(\d+)", text):
            if value != "0":
                offenders.append(f"{pipeline.relative_to(PROJECT_ROOT).as_posix()}: {value}")
    assert not offenders, (
        "a pipeline hardcodes the coverage threshold again; it belongs in "
        "[tool.coverage.report] fail_under only, otherwise changing one place "
        f"silently disagrees with the other: {offenders}"
    )


def test_ci_workflow_combines_shard_coverage_into_the_gate() -> None:
    """The shard workflow must recombine the data and report the real gate.

    The shard legs run with ``--cov-fail-under=0`` (see above), which makes
    them pure data collectors: deleting the coverage job afterwards would
    silence the 75% gate entirely, so this pins the enforcement leg to the
    workflow (``coverage combine`` + ``coverage report``, each in a real
    ``run:`` step, same style as the smoke guard below).
    """
    lines = WORKFLOW.read_text(encoding="utf-8").splitlines()
    for needle in ("python -m coverage combine", "python -m coverage report"):
        hits = [index for index, line in enumerate(lines) if needle in line]
        assert hits, f"the CI workflow no longer runs {needle!r} at all"
        in_run_step = any(
            "run:" in lines[neighbour]
            for index in hits
            for neighbour in range(
                max(0, index - RUN_STEP_WINDOW),
                min(len(lines), index + RUN_STEP_WINDOW + 1),
            )
        )
        assert in_run_step, f"{needle!r} appears in comments only, not in a run step"


def test_pytest_addopts_does_not_enable_coverage() -> None:
    """``--cov`` stays out of addopts so partial runs are never instrumented."""
    addopts = _config(_read_pyproject(), "tool", "pytest", "ini_options", "addopts")
    assert isinstance(addopts, str)
    assert "--cov" not in addopts.split(), (
        f"addopts must keep coverage opt-in, got {addopts!r}"
    )


def test_smoke_scenarios_are_discovered_by_the_harness() -> None:
    """Every scenario module exports SCENARIOS, and the CLI entry point exists."""
    modules = _scenario_modules()
    silent = [path.name for path in modules if not _module_level_scenarios(path)]
    assert not silent, f"scenario modules without a module-level SCENARIOS: {silent}"
    assert len(modules) >= MIN_SCENARIO_MODULES, (
        f"scenario modules dropped to {len(modules)}, floor is {MIN_SCENARIO_MODULES}"
    )

    cli = SMOKE_PACKAGE / "cli.py"
    assert cli.is_file(), f"the smoke CLI entry point is gone: {cli.name}"
    docstring = ast.get_docstring(ast.parse(cli.read_text(encoding="utf-8")))
    assert docstring and docstring.strip(), (
        "the smoke CLI entry point lost its module docstring"
    )


def test_ci_workflow_runs_the_ui_smoke_suite() -> None:
    """The workflow invokes the smoke suite from a real ``run:`` step."""
    lines = WORKFLOW.read_text(encoding="utf-8").splitlines()
    hits = [index for index, line in enumerate(lines) if "tools.smoke_test" in line]
    assert hits, "the CI workflow no longer calls tools.smoke_test at all"
    in_run_step = any(
        "run:" in lines[neighbour]
        for index in hits
        for neighbour in range(
            max(0, index - RUN_STEP_WINDOW),
            min(len(lines), index + RUN_STEP_WINDOW + 1),
        )
    )
    assert in_run_step, "tools.smoke_test appears in comments only, not in a run step"
