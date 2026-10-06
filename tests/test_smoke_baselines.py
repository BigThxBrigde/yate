"""Baseline snapshot and drift-diff tests for ``tools/smoke_test/baselines.py``.

Covers the pure side of the baseline contract: the ``jsonable`` cleaner (which
has to survive whatever a scenario put in a check), ``serialize``'s reduction
to ``label/expected/actual/ok`` plus the y-sorted SVG rows, the write/read round
trip through a temp directory, and every line shape ``diff_baseline`` can emit
(``-`` missing / ``~`` drift / ``+`` new / ``~ svg drift:`` / no drift at all).

Not covered: the shipped ``tools/smoke_test/smoke_baselines/*.json`` contents
(those are data, verified by the release gate's ``compare`` run) and the CLI
plumbing around snapshot/compare, which lives in ``tests/test_smoke_cli.py``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import override

from tools._util import repo_root
from tools.smoke_test.baselines import (
    default_baseline_dir,
    diff_baseline,
    jsonable,
    load_baseline,
    serialize,
    write_baselines,
)
from tools.smoke_test.harness import Check, ScenarioResult


# --- jsonable ----------------------------------------------------------------


def test_jsonable_scalars_pass_through_untouched() -> None:
    assert jsonable("text") == "text"
    assert jsonable(7) == 7
    assert jsonable(1.5) == 1.5
    assert jsonable(True) is True


def test_jsonable_none_stays_none() -> None:
    assert jsonable(None) is None


def test_jsonable_path_becomes_its_string_form() -> None:
    assert jsonable(Path("notes/中文.txt")) == str(Path("notes/中文.txt"))


def test_jsonable_list_and_tuple_become_json_arrays() -> None:
    assert jsonable([1, Path("a"), ("x", 2)]) == [1, "a", ["x", 2]]


def test_jsonable_dict_stringifies_keys_and_cleans_values() -> None:
    assert jsonable({1: Path("a"), "b": (True, None)}) == {
        "1": "a",
        "b": [True, None],
    }


def test_jsonable_unserializable_object_falls_back_to_repr() -> None:
    class Widget:
        @override
        def __repr__(self) -> str:
            return "<Widget name='x'>"

    assert jsonable(Widget()) == "<Widget name='x'>"


# --- serialize ---------------------------------------------------------------


def test_serialize_maps_checks_onto_the_baseline_schema() -> None:
    result = ScenarioResult(
        "demo",
        checks=[
            Check("buffer[0]", "hello", "hello"),
            Check("modified", True, False),
        ],
    )
    payload = serialize(result)
    assert payload == {
        "checks": [
            {"label": "buffer[0]", "expected": "hello", "actual": "hello",
             "ok": True},
            {"label": "modified", "expected": True, "actual": False, "ok": False},
        ],
        "svg_rows": {},
    }


def test_serialize_cleans_check_values_through_jsonable() -> None:
    result = ScenarioResult("demo", checks=[Check("path", Path("a/b"), Path("a/b"))])
    assert serialize(result)["checks"][0]["expected"] == str(Path("a/b"))


def test_serialize_svg_row_keys_become_strings_sorted_by_y() -> None:
    result = ScenarioResult("demo", svg_rows={30: "third", 10: "first", 20: "second"})
    rows = serialize(result)["svg_rows"]
    assert list(rows) == ["10", "20", "30"]
    assert rows == {"10": "first", "20": "second", "30": "third"}


# --- write / load round trip -------------------------------------------------


def test_write_baselines_writes_one_file_per_result(tmp_path: Path) -> None:
    outdir = tmp_path / "bl"
    results = [
        ScenarioResult("alpha", checks=[Check("a", 1, 1)]),
        ScenarioResult("beta", checks=[Check("b", 2, 3)]),
    ]
    assert write_baselines(results, outdir) == 2
    assert sorted(p.name for p in outdir.iterdir()) == ["alpha.json", "beta.json"]


def test_write_baselines_output_is_readable_json_matching_serialize(
    tmp_path: Path,
) -> None:
    outdir = tmp_path / "bl"
    result = ScenarioResult("alpha", checks=[Check("a", 1, 1)], svg_rows={5: "x"})
    write_baselines([result], outdir)
    loaded = load_baseline(outdir / "alpha.json")
    assert loaded == serialize(result)


def test_write_baselines_keeps_non_ascii_text_unescaped(tmp_path: Path) -> None:
    outdir = tmp_path / "bl"
    write_baselines([ScenarioResult("zh", checks=[Check("msg", "中文", "中文")])], outdir)
    raw = (outdir / "zh.json").read_text(encoding="utf-8")
    assert "中文" in raw
    assert "\\u" not in raw
    assert json.loads(raw)["checks"][0]["expected"] == "中文"


def test_load_baseline_reads_back_what_write_baselines_stored(tmp_path: Path) -> None:
    outdir = tmp_path / "bl"
    result = ScenarioResult(
        "alpha",
        checks=[Check("rows", [Path("a"), ("b", 1)], [Path("a"), ("b", 1)])],
    )
    write_baselines([result], outdir)
    assert load_baseline(outdir / "alpha.json") == serialize(result)


# --- diff_baseline -----------------------------------------------------------


def _snapshot(
    checks: list[tuple[str, object]], rows: dict[str, str] | None = None
) -> dict[str, object]:
    """A baseline-shaped payload built from ``(label, actual)`` pairs."""
    return {
        "checks": [
            {"label": label, "expected": actual, "actual": actual, "ok": True}
            for label, actual in checks
        ],
        "svg_rows": rows or {},
    }


def test_diff_baseline_reports_a_label_the_actual_run_dropped() -> None:
    expected = _snapshot([("kept", 1), ("gone", 2)])
    actual = _snapshot([("kept", 1)])
    assert diff_baseline(expected, actual) == ["- gone: missing in actual"]


def test_diff_baseline_reports_a_changed_actual_with_both_values() -> None:
    expected = _snapshot([("count", 3)])
    actual = _snapshot([("count", 4)])
    assert diff_baseline(expected, actual) == [
        "~ count: baseline=3 current=4"
    ]


def test_diff_baseline_reports_a_check_the_actual_run_added() -> None:
    expected = _snapshot([("kept", 1)])
    actual = _snapshot([("kept", 1), ("fresh", "x")])
    assert diff_baseline(expected, actual) == ["+ fresh: new check (actual='x')"]


def test_diff_baseline_lists_svg_rows_by_y_with_base_and_current() -> None:
    expected = _snapshot([], rows={"10": "old", "20": "same"})
    actual = _snapshot([], rows={"10": "new", "20": "same"})
    assert diff_baseline(expected, actual) == [
        "~ svg drift:",
        "    y=10: base='old' cur='new'",
    ]


def test_diff_baseline_reports_an_svg_row_the_actual_run_dropped() -> None:
    expected = _snapshot([], rows={"10": "old"})
    assert diff_baseline(expected, _snapshot([])) == [
        "~ svg drift:",
        "    y=10: base='old' cur=''",
    ]


def test_diff_baseline_returns_no_lines_for_identical_payloads() -> None:
    payload = _snapshot([("kept", 1), ("other", "x")], rows={"10": "same"})
    assert diff_baseline(payload, _snapshot(
        [("kept", 1), ("other", "x")], rows={"10": "same"}
    )) == []


def test_diff_baseline_ignores_a_matching_label_with_a_different_expected() -> None:
    # Only ``actual`` is part of the drift contract: the baseline's ``expected``
    # is whatever the scenario asserted at snapshot time and may legitimately
    # change when the assertion itself is rewritten.
    expected = {"checks": [{"label": "a", "expected": "old", "actual": 1, "ok": True}]}
    actual = {"checks": [{"label": "a", "expected": "new", "actual": 1, "ok": True}]}
    assert diff_baseline(expected, actual) == []


# --- default_baseline_dir ----------------------------------------------------


def test_default_baseline_dir_points_at_the_shipped_baselines() -> None:
    assert default_baseline_dir() == (
        repo_root() / "tools" / "smoke_test" / "smoke_baselines"
    )
