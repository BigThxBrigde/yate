"""Pure-function tests for the smoke harness (``tools/smoke_test``).

Only the parts that run without Textual's pilot are covered: scenario
selection, the per-scenario timeout, report rendering and SVG row
extraction.  The harness end-to-end path is exercised by the smoke tool
itself (``python -m tools.smoke_test run``), which the release gate runs.
"""

from __future__ import annotations

import asyncio
from io import StringIO
from pathlib import Path

import pytest
from rich.console import Console

from tools.smoke_test.harness import (
    Check,
    RunOptions,
    Scenario,
    ScenarioResult,
    SvgDriftError,
    extract_svg_rows,
    run_scenarios,
    select_scenarios,
)
from tools.smoke_test.report import Reporter


def _scenario(name: str, *tags: str, slow: bool = False) -> Scenario:
    async def run(tmp: Path) -> ScenarioResult:
        return ScenarioResult(name)

    return Scenario(name, run, tags, slow=slow)


# --- select_scenarios -------------------------------------------------------


def test_select_scenarios_by_name_keeps_requested_order() -> None:
    alpha = _scenario("alpha", "edit")
    beta = _scenario("beta", "files")
    chosen = select_scenarios([alpha, beta], names=["beta", "alpha"])
    assert [s.name for s in chosen] == ["beta", "alpha"]


def test_select_scenarios_tag_filter_matches_any_declared_tag() -> None:
    alpha = _scenario("alpha", "edit", "regression")
    beta = _scenario("beta", "files")
    chosen = select_scenarios([alpha, beta], tags=["regression", "files"])
    assert [s.name for s in chosen] == ["alpha", "beta"]


def test_select_scenarios_skip_slow_drops_only_slow_scenarios() -> None:
    alpha = _scenario("alpha", "edit")
    beta = _scenario("beta", "stress", slow=True)
    assert [s.name for s in select_scenarios([alpha, beta], skip_slow=True)] == [
        "alpha"
    ]
    assert [s.name for s in select_scenarios([alpha, beta])] == ["alpha", "beta"]


def test_select_scenarios_unknown_name_raises_system_exit() -> None:
    with pytest.raises(SystemExit) as excinfo:
        select_scenarios([_scenario("alpha", "edit")], names=["nope"])
    assert "nope" in str(excinfo.value)


def test_select_scenarios_unknown_tag_raises_system_exit() -> None:
    with pytest.raises(SystemExit) as excinfo:
        select_scenarios([_scenario("alpha", "edit")], tags=["bogus"])
    assert "bogus" in str(excinfo.value)


# --- extract_svg_rows (format adapted to Textual 8.2.8) ---------------------

#: Trimmed from a real ``save_screenshot`` export of this checkout's
#: Textual 8.2.8 (Rich terminal SVG): class is the first attribute, y is a
#: decimal, and entities like ``&#160;`` stay undecoded in the row text.
_CURRENT_FORMAT_SVG = (
    '<svg class="rich-terminal" viewBox="0 0 1238 782.0" '
    'xmlns="http://www.w3.org/2000/svg">\n'
    "    <!-- Generated with Rich https://www.textualize.io -->\n"
    '    <text class="terminal-1-title" fill="#c5c8c6" '
    'text-anchor="middle" x="618" y="27">yate&#160;0.2.4</text>\n'
    '    <text class="terminal-1-r6" x="12.2" y="68.8" textLength="36.6" '
    'clip-path="url(#terminal-1-line-2)">&#160;&#160;1</text>\n'
    "</svg>\n"
)

#: The same shape with single-quoted attributes (a plausible drift variant):
#: every ``<text`` element becomes unreadable for the patterns.
_DRIFTED_FORMAT_SVG = (
    "<svg>\n"
    "    <text class='terminal-1-r6' x='12.2' y='68.8'>orphan</text>\n"
    "</svg>\n"
)

#: Half readable, half drifted: the partial-coverage guard must also fire.
_PARTIAL_DRIFT_SVG = (
    "<svg>\n"
    '    <text class="terminal-1-r1" x="12.2" y="20">kept</text>\n'
    "    <text class='terminal-1-r6' x='12.2' y='68.8'>orphan</text>\n"
    "</svg>\n"
)


def test_extract_svg_rows_current_format_maps_rows_by_y() -> None:
    rows = extract_svg_rows(_CURRENT_FORMAT_SVG)
    assert rows == {27: "yate&#160;0.2.4", 68: "&#160;&#160;1"}


def test_extract_svg_rows_full_drift_raises_with_svg_head() -> None:
    with pytest.raises(SvgDriftError) as excinfo:
        extract_svg_rows(_DRIFTED_FORMAT_SVG)
    message = str(excinfo.value)
    assert "Textual" in message
    assert "<svg>" in message  # the head snippet is part of the diagnosis


def test_extract_svg_rows_partial_drift_raises_instead_of_losing_rows() -> None:
    with pytest.raises(SvgDriftError):
        extract_svg_rows(_PARTIAL_DRIFT_SVG)


def test_extract_svg_rows_blank_svg_returns_empty_without_alarm() -> None:
    assert extract_svg_rows("<svg></svg>") == {}


# --- per-scenario timeout ---------------------------------------------------


async def _hang_run(tmp: Path) -> ScenarioResult:
    await asyncio.sleep(999)
    raise AssertionError("unreachable")  # pragma: no cover


async def _ok_run(tmp: Path) -> ScenarioResult:
    return ScenarioResult("after_hang", checks=[Check("done", True, True)])


def test_run_scenarios_timeout_fails_scenario_and_continues(tmp_path: Path) -> None:
    hang = Scenario("hang", _hang_run)
    after = Scenario("after_hang", _ok_run)
    results = run_scenarios([hang, after], tmp_path, RunOptions(timeout=0.3))
    hang_error = results[0].error
    assert hang_error is not None
    assert "timeout" in hang_error
    assert results[0].checks == []
    assert results[1].error is None
    assert [c.ok for c in results[1].checks] == [True]


# --- report rendering -------------------------------------------------------


def _make_reporter(
    quiet: bool = False, verbose: bool = False
) -> tuple[Reporter, StringIO]:
    reporter = Reporter(quiet=quiet, verbose=verbose)
    stream = StringIO()
    reporter.console = Console(file=stream, width=120, no_color=True)
    return reporter, stream


def test_reporter_results_renders_failed_check_diff() -> None:
    reporter, stream = _make_reporter()
    result = ScenarioResult(
        "demo", checks=[Check("buffer[0]", "hello", "world")], tags=("edit",)
    )
    reporter.results([result])
    out = stream.getvalue()
    assert "demo" in out
    assert "buffer[0]" in out
    assert "'hello'" in out
    assert "'world'" in out


def test_reporter_results_renders_scenario_error_text() -> None:
    reporter, stream = _make_reporter()
    result = ScenarioResult("boom", tags=("edit",), error="TimeoutError: x")
    reporter.results([result])
    out = stream.getvalue()
    assert "ERROR" in out
    assert "TimeoutError: x" in out


def test_reporter_summary_reports_failing_exit_code() -> None:
    reporter, stream = _make_reporter()
    result = ScenarioResult("boom", checks=[Check("a", 1, 2)])
    reporter.summary([result], exit_code=1)
    assert "exit 1" in stream.getvalue()


def test_reporter_quiet_suppresses_result_tables_and_progress() -> None:
    reporter, stream = _make_reporter(quiet=True)
    result = ScenarioResult("demo", checks=[Check("a", 1, 2)], tags=("edit",))
    reporter.results([result])
    reporter.progress(1, 1, "demo")
    assert stream.getvalue() == ""
