"""Baseline snapshots and drift comparison.

``snapshot`` writes one JSON file per scenario under
``tools/smoke_test/smoke_baselines/``; ``compare`` re-runs the scenarios and diffs the
fresh results against them.  Only *checks* are part of the contract (plus
the SVG rows when they were captured) -- no absolute paths or timings, so
the baselines are stable across machines.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence, cast

from .harness import ScenarioResult

__all__ = [
    "default_baseline_dir",
    "diff_baseline",
    "repo_root",
    "serialize",
    "write_baselines",
]


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_baseline_dir() -> Path:
    return repo_root() / "tools" / "smoke_test" / "smoke_baselines"


def _jsonable(value: Any) -> Any:
    """Make a check value storable in JSON.

    Scenarios mostly assert on strings / ints / bools, but a stray
    ``Path`` (or anything else Rich can render and JSON cannot) must not
    abort the whole snapshot run.
    """
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (list, tuple)):
        seq = cast("Sequence[Any]", value)
        return [_jsonable(v) for v in seq]
    if isinstance(value, dict):
        raw = cast("Mapping[Any, Any]", value)
        return {str(k): _jsonable(v) for k, v in raw.items()}
    return repr(value)


def serialize(result: ScenarioResult) -> dict[str, Any]:
    return {
        "checks": [
            {
                "label": c.label,
                "expected": _jsonable(c.expected),
                "actual": _jsonable(c.actual),
                "ok": c.ok,
            }
            for c in result.checks
        ],
        "svg_rows": {str(k): v for k, v in sorted(result.svg_rows.items())},
    }


def write_baselines(results: list[ScenarioResult], outdir: Path) -> int:
    outdir.mkdir(parents=True, exist_ok=True)
    for r in results:
        (outdir / f"{r.name}.json").write_text(
            json.dumps(serialize(r), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    return len(results)


def load_baseline(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def diff_baseline(
    expected: dict[str, Any], actual: dict[str, Any]
) -> list[str]:
    """Human readable ``- missing`` / ``~ drift`` / ``+ new`` diff lines."""
    lines: list[str] = []
    exp = {c["label"]: c for c in expected.get("checks", [])}
    act = {c["label"]: c for c in actual.get("checks", [])}
    for label, ec in exp.items():
        ac = act.get(label)
        if ac is None:
            lines.append(f"- {label}: missing in actual")
        elif ec["actual"] != ac["actual"]:
            lines.append(
                f"~ {label}: baseline={ec['actual']!r} "
                f"current={ac['actual']!r}"
            )
    for label in act.keys() - exp.keys():
        lines.append(f"+ {label}: new check (actual={act[label]['actual']!r})")
    exp_rows = expected.get("svg_rows", {})
    act_rows = actual.get("svg_rows", {})
    if exp_rows != act_rows:
        lines.append("~ svg drift:")
        for y in sorted(set(exp_rows) | set(act_rows), key=int):
            e = exp_rows.get(y, "")
            a = act_rows.get(y, "")
            if e != a:
                lines.append(f"    y={y}: base={e[:80]!r} cur={a[:80]!r}")
    return lines
