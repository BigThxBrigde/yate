"""Argument parsing, exit codes and the JSON report of ``tools/smoke_test/cli.py``.

Covers the three subcommands' surface (``run`` / ``snapshot`` / ``compare``,
the repeatable ``--scenario`` / ``--tag`` filters and the per-subcommand
directory options), the ``--repeat`` tie-break rule in :func:`_worse`, the
machine-readable report :func:`_write_json` produces, and the three exit codes
of :func:`main`: ``0`` all green, ``2`` for "the filters matched nothing" and
"there is no baseline to compare against".

Not covered: the rendering of the report (that is ``tests/test_smoke_tool.py``)
and the scenario bodies themselves -- only one cheap shipped scenario is
actually executed, to prove the ``exit 0`` path end to end.
"""

# _worse / _write_json are module-private but part of the exit-code and report
# contract under test, so the private-usage rule is relaxed file-wide (the same
# convention tests/test_app_textual.py and 15 other modules use).
# pyright: reportPrivateUsage=false

from __future__ import annotations

import inspect
import json
from collections.abc import Awaitable, Iterator
from pathlib import Path
from typing import cast

import pytest
from tools.smoke_test import harness
from tools.smoke_test.cli import _worse, _write_json, build_parser, main
from tools.smoke_test.harness import (
    Check,
    Coverage,
    RunOptions,
    Scenario,
    ScenarioResult,
)
from yate.app import YateApp
from yate.editor_components import theme

#: A shipped scenario that builds no file palette and no screenshot, so the
#: one real ``main(["run", ...])`` call in this module stays well under a second.
_LIGHT_SCENARIO: str = "keymap_toggle"


@pytest.fixture(autouse=True)
def restore_theme() -> Iterator[None]:
    """Undo the process-global theme change the scenario's ``YateApp`` makes.

    Only the end-to-end ``main`` run touches this global: it goes through
    ``run_scenarios`` -> ``keymap_toggle`` -> ``new_app()``, and a mounted
    ``YateApp`` applies its configured palette via ``theme.set_theme``
    (process-global, ``yate/app.py``).  The parser / ``_worse`` / ``_write_json``
    cases and the two early-exit ``main`` paths (no scenario matches, absent
    baseline dir) never mount an app and touch no other process global -- the
    fuzz seed stays read-only (no ``--seed`` is passed, so ``set_seed`` never
    runs) and the keymap is per-``Editor`` state.
    """
    before = theme.active().name
    yield
    theme.set_theme(before)


# --- build_parser ------------------------------------------------------------


@pytest.mark.parametrize("command", ["run", "snapshot", "compare"])
def test_build_parser_accepts_every_subcommand(command: str) -> None:
    args = build_parser().parse_args([command])
    assert args.cmd == command
    assert callable(args.func)


def test_build_parser_collects_repeated_scenario_and_tag_filters() -> None:
    args = build_parser().parse_args(
        ["run", "--scenario", "alpha", "--scenario", "beta", "--tag", "edit",
         "--tag", "files"]
    )
    assert args.scenario == ["alpha", "beta"]
    assert args.tag == ["edit", "files"]


def test_build_parser_defaults_filters_to_empty_lists() -> None:
    args = build_parser().parse_args(["run"])
    assert args.scenario is None
    assert args.tag is None
    assert args.skip_slow is False


def test_build_parser_defaults_jobs_to_the_serial_runner() -> None:
    args = build_parser().parse_args(["run"])
    assert args.jobs == 1


def test_build_parser_collects_the_jobs_option() -> None:
    args = build_parser().parse_args(["run", "--jobs", "4"])
    assert args.jobs == 4


def test_build_parser_gives_snapshot_an_outdir_option() -> None:
    args = build_parser().parse_args(["snapshot", "--outdir", "somewhere"])
    assert args.outdir == "somewhere"


def test_build_parser_gives_compare_a_baseline_option() -> None:
    args = build_parser().parse_args(["compare", "--baseline", "elsewhere"])
    assert args.baseline == "elsewhere"


def test_build_parser_without_a_subcommand_exits() -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args([])


# --- _worse (the --repeat tie-break) -----------------------------------------


def test_worse_prefers_a_candidate_that_raised_over_a_clean_one() -> None:
    clean = ScenarioResult("s", checks=[Check("a", 1, 2)])
    crashed = ScenarioResult("s", error="TimeoutError: x")
    assert _worse(crashed, clean) is True
    assert _worse(clean, crashed) is False


def test_worse_prefers_more_failing_checks_when_neither_raised() -> None:
    mostly_ok = ScenarioResult("s", checks=[Check("a", 1, 1)])
    mostly_bad = ScenarioResult("s", checks=[Check("a", 1, 2), Check("b", 1, 2)])
    assert _worse(mostly_bad, mostly_ok) is True
    assert _worse(mostly_ok, mostly_bad) is False


def test_worse_reports_no_worse_for_two_identical_runs() -> None:
    def _run() -> ScenarioResult:
        return ScenarioResult("s", checks=[Check("a", 1, 2), Check("b", "x", "x")])

    assert _worse(_run(), _run()) is False


# --- _write_json -------------------------------------------------------------


def _results() -> list[ScenarioResult]:
    return [
        ScenarioResult("passing", checks=[Check("a", 1, 1), Check("b", 2, 2)]),
        ScenarioResult("failing", checks=[Check("a", 1, 2), Check("b", 2, 2)]),
        ScenarioResult("errored", error="TimeoutError: x"),
    ]


def test_write_json_totals_count_checks_and_scenarios(tmp_path: Path) -> None:
    path = tmp_path / "report.json"
    _write_json(str(path), _results(), None)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["totals"] == {"ok": 3, "fail": 1, "scenarios": 3, "passed": 1}


def test_write_json_does_not_count_an_errored_scenario_as_passed(tmp_path: Path) -> None:
    path = tmp_path / "report.json"
    # An errored scenario contributes no failing check, so only the "passed"
    # rule can keep it out of the numerator.
    _write_json(str(path), [ScenarioResult("boom", error="boom")], None)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["totals"]["passed"] == 0
    assert payload["scenarios"][0]["ok"] is False
    assert payload["scenarios"][0]["error"] == "boom"


def test_write_json_records_the_coverage_segment(tmp_path: Path) -> None:
    cov = Coverage(
        command_universe={"w", "q", "theme"},
        action_universe={"save", "copy"},
    )
    cov.note_command("w notes.txt")
    cov.note_action("save")
    path = tmp_path / "report.json"
    _write_json(str(path), [], cov)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["coverage"] == {
        "commands": {"hit": 1, "total": 3, "missing": ["q", "theme"]},
        "actions": {"hit": 1, "total": 2, "missing": ["copy"]},
    }


def test_write_json_omits_coverage_when_none_was_tracked(tmp_path: Path) -> None:
    path = tmp_path / "report.json"
    _write_json(str(path), [], None)
    assert "coverage" not in json.loads(path.read_text(encoding="utf-8"))


def test_write_json_marks_invariant_checks_in_each_scenario(tmp_path: Path) -> None:
    path = tmp_path / "report.json"
    _write_json(str(path), [ScenarioResult("s", checks=[
        Check("own", 1, 1), Check("invariant:no_crash", True, True, invariant=True),
    ])], None)
    checks = json.loads(path.read_text(encoding="utf-8"))["scenarios"][0]["checks"]
    assert [c["invariant"] for c in checks] == [False, True]


# --- main: the three exit codes ----------------------------------------------


def test_main_returns_two_when_the_filters_match_no_scenario() -> None:
    # keymap_toggle is tagged "view" only, so pairing it with "stress" selects
    # nothing -- a legal filter combination, unlike an unknown scenario name
    # (which select_scenarios rejects with SystemExit).
    code = main([
        "run", "--scenario", _LIGHT_SCENARIO, "--tag", "stress",
        "--quiet", "--no-color",
    ])
    assert code == 2


def test_main_returns_two_when_the_compare_baseline_dir_is_absent(
    tmp_path: Path,
) -> None:
    code = main([
        "compare", "--baseline", str(tmp_path / "no-such-dir"),
        "--scenario", _LIGHT_SCENARIO, "--quiet", "--no-color",
    ])
    assert code == 2


def test_main_returns_zero_for_a_shipped_scenario_that_passes() -> None:
    assert main(["run", "--scenario", _LIGHT_SCENARIO, "--quiet", "--no-color"]) == 0


def test_main_returns_two_when_jobs_is_below_one() -> None:
    # A bad worker count is a usage error, not a scenario failure: exit 2 is
    # the same code the "filters matched nothing" path uses.
    code = main([
        "run", "--scenario", _LIGHT_SCENARIO, "--jobs", "0",
        "--quiet", "--no-color",
    ])
    assert code == 2


# --- run_shard seed propagation and the full-app invariant sweep (m12/m13) ----


def test_run_shard_reseeds_the_worker_process(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A spawned shard is re-seeded with the requested seed (m12).

    Workers are fresh processes whose module state starts at the default
    seed, so ``run_shard`` must call ``set_seed`` itself: ``run --jobs 4
    --seed N`` previously ran the fuzz scenarios on 1337 while the report
    header claimed N.
    """
    seeds: list[int] = []
    monkeypatch.setattr(harness, "set_seed", lambda value: seeds.append(int(value)))

    def fake_run_one(scenario: Scenario, tmp_root: Path, options: RunOptions) -> ScenarioResult:
        return ScenarioResult(scenario.name, tags=scenario.tags)

    monkeypatch.setattr(harness, "_run_one", fake_run_one)

    results, _ = harness.run_shard(
        (_LIGHT_SCENARIO,), str(tmp_path), svg=False, invariants=False, timeout=60,
        seed=4242,
    )

    assert seeds == [4242]
    assert [result.name for result in results] == [_LIGHT_SCENARIO]


def test_parallel_runner_forwards_the_fuzz_seed_to_shards() -> None:
    """Both the worker submit and the in-process retry carry the seed (m12).

    A functional probe would need a real spawned worker whose observable
    state is the child's module global, so the wiring is pinned on the
    source text (the same textual-pin convention tests/test_keyproto.py
    uses for process-bound code).
    """
    source = inspect.getsource(harness.run_scenarios_parallel)
    assert source.count("seed=get_seed()") == 2


def test_run_one_sweeps_invariants_over_every_tracked_app(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The invariant sweep sees all apps a scenario tracked, not just the last (m13)."""
    first, second = object(), object()
    swept: list[object] = []

    def recording_invariants(app: object, *, theme_before: str) -> list[Check]:
        swept.append(app)
        return [Check(f"invariant:{len(swept)}", True, True, invariant=True, ok_override=True)]

    async def fake_run(tmp: Path) -> ScenarioResult:
        harness.track(cast(YateApp, first))
        harness.track(cast(YateApp, second))
        return ScenarioResult("seed_probe")

    monkeypatch.setattr(harness, "invariant_checks", recording_invariants)
    scenario = Scenario(name="seed_probe", run=fake_run, tags=("regression",))

    result = harness._run_one(scenario, tmp_path, RunOptions(invariants=True))

    assert swept == [first, second]
    assert [check.label for check in result.checks] == ["invariant:1", "invariant:2"]
