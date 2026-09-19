"""Headless smoke harness for the yate Textual UI.

Run with: ``python -m tools.smoke_test``

Subcommands:

* ``run [--scenario NAME] [--svg] [--tmpdir DIR]``
  Run scenarios and print a PASS/FAIL table of state assertions; with
  ``--svg`` also capture and show the top SVG text rows.

* ``snapshot [--scenario NAME] [--outdir DIR]``
  Run scenarios and write JSON baselines (checks + extracted SVG rows)
  under ``tools/smoke_baselines/`` for later comparison.

* ``compare [--scenario NAME] [--baseline DIR]``
  Run scenarios and diff against the stored baselines, reporting
  ``MATCH`` / ``DRIFT`` and exiting non-zero on drift.

The harness drives ``YateApp`` under ``pilot.run_test()`` exactly like
``tests/test_app_textual.py``; it never touches the real terminal.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Awaitable, Callable

os.environ.setdefault("YATE_PYTHON_LSP", "off")

from yate.app import YateApp  # noqa: E402
from yate.editor_view import theme  # noqa: E402

# ----------------------------------------------------------- SVG text extraction

_TEXT_RE = re.compile(r'<text[^>]*y="([\d.]+)"[^>]*>(.*?)</text>', re.S)
_INNER_RE = re.compile(r">([^<]+)<")

def extract_svg_rows(svg: str) -> dict[int, str]:
    """Map y-coordinate -> concatenated text content for each rendered row."""
    rows: dict[int, str] = {}
    for m in _TEXT_RE.finditer(svg):
        y = int(float(m.group(1)))
        text = "".join(_INNER_RE.findall(">" + m.group(2) + "<"))
        if text:
            rows[y] = rows.get(y, "") + text
    return rows

def _snapshot(app: YateApp, tmp: Path) -> dict[int, str]:
    svg_path = tmp / "shot.svg"
    app.save_screenshot(str(svg_path))
    return extract_svg_rows(svg_path.read_text(encoding="utf-8"))

# ----------------------------------------------------------------- result types

@dataclass
class Check:
    label: str
    expected: Any
    actual: Any

    @property
    def ok(self) -> bool:
        return self.expected == self.actual

@dataclass
class ScenarioResult:
    name: str
    checks: list[Check] = field(default_factory=lambda: [])
    svg_rows: dict[int, str] = field(default_factory=lambda: {})

@dataclass
class Scenario:
    name: str
    run: Callable[[Path], Awaitable[ScenarioResult]]

# -------------------------------------------------------------------- scenarios

async def _type_save_find(tmp: Path) -> ScenarioResult:
    """Type text, save with ctrl+s, then find a substring."""
    target = tmp / "notes.txt"
    app = YateApp(target=target)
    checks: list[Check] = []
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await pilot.press("h", "e", "l", "l", "o")
        await pilot.pause()
        checks.append(Check("buffer[0]", "hello", app.buffer.lines[0]))
        checks.append(Check("modified", True, app.doc.modified))
        await pilot.press("ctrl+s")
        await pilot.pause()
        checks.append(Check("file_exists", True, target.exists()))
        checks.append(Check("file_content", "hello", target.read_text(encoding="utf-8")))
        checks.append(Check("clean", False, app.doc.modified))
        await pilot.press("ctrl+f")
        await pilot.pause()
        mode = app.prompt_bar.active_mode if app.prompt_bar else None
        checks.append(Check("find_mode", "find", mode))
        await pilot.press("l", "l")
        await pilot.press("enter")
        await pilot.pause()
        checks.append(Check("search_query", "ll", app.search.query))
        checks.append(Check("search_matches>=1", True, len(app.search.matches) >= 1))
        rows = _snapshot(app, tmp)
    return ScenarioResult("type_save_find", checks, rows)

async def _file_palette(tmp: Path) -> ScenarioResult:
    """Open a file via the ctrl+p fuzzy palette."""
    (tmp / "notes.txt").write_text("hello\n", encoding="utf-8")
    (tmp / "todo.txt").write_text("buy milk\n", encoding="utf-8")
    app = YateApp(target=tmp)
    checks: list[Check] = []
    async with app.run_test(size=(110, 32)) as pilot:
        await pilot.pause()
        await pilot.press("ctrl+p")
        await pilot.pause()
        checks.append(Check("palette_open", 2, len(app.screen_stack)))
        for ch in "note":
            await pilot.press(ch)
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        checks.append(Check("doc.name", "notes.txt", app.doc.name))
        checks.append(Check("palette_closed", 1, len(app.screen_stack)))
        rows = _snapshot(app, tmp)
    return ScenarioResult("file_palette", checks, rows)

async def _keymap_toggle(tmp: Path) -> ScenarioResult:
    """Toggle the keymap between vsc and vim via ctrl+/."""
    app = YateApp(target=tmp / "scratch.txt")
    checks: list[Check] = []
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        checks.append(Check("default_keymap", "vsc", app.keymap_name))
        await pilot.press("ctrl+/")
        await pilot.pause()
        checks.append(Check("toggled_keymap", "vim", app.keymap_name))
        await pilot.press("ctrl+/")
        await pilot.pause()
        checks.append(Check("back_to_vsc", "vsc", app.keymap_name))
        rows = _snapshot(app, tmp)
    return ScenarioResult("keymap_toggle", checks, rows)

async def _theme_switch(tmp: Path) -> ScenarioResult:
    """Switch theme via :theme latte, then restore mocha."""
    app = YateApp(target=tmp / "scratch.txt")
    checks: list[Check] = []
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        checks.append(Check("default_theme", "mocha", theme.active().name))
        await pilot.press("f5")
        await pilot.pause()
        for ch in "theme latte":
            await pilot.press(ch)
        await pilot.press("enter")
        await pilot.pause()
        checks.append(Check("latte_theme", "latte", theme.active().name))
        theme.set_theme("mocha")
        await pilot.pause()
        checks.append(Check("restored_mocha", "mocha", theme.active().name))
        rows = _snapshot(app, tmp)
    return ScenarioResult("theme_switch", checks, rows)

async def _help_modal(tmp: Path) -> ScenarioResult:
    """Open the :help manual modal and close it with q."""
    app = YateApp(target=tmp / "scratch.txt")
    checks: list[Check] = []
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await pilot.press("f5")
        await pilot.pause()
        for ch in "help":
            await pilot.press(ch)
        await pilot.press("enter")
        await pilot.pause()
        checks.append(Check("modal_open", 2, len(app.screen_stack)))
        await pilot.press("q")
        await pilot.pause()
        checks.append(Check("modal_closed", 1, len(app.screen_stack)))
        rows = _snapshot(app, tmp)
    return ScenarioResult("help_modal", checks, rows)

SCENARIOS: list[Scenario] = [
    Scenario("type_save_find", _type_save_find),
    Scenario("file_palette", _file_palette),
    Scenario("keymap_toggle", _keymap_toggle),
    Scenario("theme_switch", _theme_switch),
    Scenario("help_modal", _help_modal),
]

# ------------------------------------------------------------------------- runner

def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]

def _default_baseline_dir() -> Path:
    return _repo_root() / "tools" / "smoke_baselines"

def _select(names: list[str] | None) -> list[Scenario]:
    if not names:
        return list(SCENARIOS)
    by = {s.name: s for s in SCENARIOS}
    missing = [n for n in names if n not in by]
    if missing:
        raise SystemExit(
            f"unknown scenario(s): {', '.join(missing)}; "
            f"available: {', '.join(by)}"
        )
    return [by[n] for n in names]

def _run_all(
    selected: list[Scenario], tmp_root: Path, *, svg: bool = False
) -> list[ScenarioResult]:
    async def runner() -> list[ScenarioResult]:
        out: list[ScenarioResult] = []
        for s in selected:
            sub = tmp_root / s.name
            sub.mkdir(parents=True, exist_ok=True)
            r = await s.run(sub)
            if not svg:
                r.svg_rows = {}
            out.append(r)
        return out
    return asyncio.run(runner())

def _print_table(results: list[ScenarioResult]) -> int:
    width = max((len(r.name) for r in results), default=8)
    total_ok = total_fail = 0
    for r in results:
        ok = sum(1 for c in r.checks if c.ok)
        fail = len(r.checks) - ok
        total_ok += ok
        total_fail += fail
        print(f"{r.name:<{width}}  {'PASS' if fail == 0 else f'FAIL ({fail})'}")
        for c in r.checks:
            mark = "ok" if c.ok else "XX"
            print(f"  [{mark}] {c.label}: expected={c.expected!r} actual={c.actual!r}")
        if r.svg_rows:
            print("  svg (top 6):")
            for y in sorted(r.svg_rows)[:6]:
                print(f"    {y}: {r.svg_rows[y][:100]!r}")
    print(f"\nTotal: {total_ok} ok, {total_fail} fail")
    return 0 if total_fail == 0 else 1

def _serialize(r: ScenarioResult) -> dict[str, Any]:
    return {
        "checks": [
            {
                "label": c.label,
                "expected": c.expected,
                "actual": c.actual,
                "ok": c.ok,
            }
            for c in r.checks
        ],
        "svg_rows": {str(k): v for k, v in sorted(r.svg_rows.items())},
    }

def _diff(expected: dict[str, Any], actual: dict[str, Any]) -> None:
    exp = {c["label"]: c for c in expected.get("checks", [])}
    act = {c["label"]: c for c in actual.get("checks", [])}
    for label, ec in exp.items():
        ac = act.get(label)
        if ac is None:
            print(f"  - {label}: missing in actual")
        elif ec["actual"] != ac["actual"]:
            print(
                f"  ~ {label}: baseline={ec['actual']!r} current={ac['actual']!r}"
            )
    for label in act.keys() - exp.keys():
        print(f"  + {label}: new check (actual={act[label]['actual']!r})")
    exp_rows = expected.get("svg_rows", {})
    act_rows = actual.get("svg_rows", {})
    if exp_rows != act_rows:
        print("  svg drift:")
        for y in sorted(set(exp_rows) | set(act_rows), key=int):
            e = exp_rows.get(y, "")
            a = act_rows.get(y, "")
            if e != a:
                print(f"    y={y}: base={e[:80]!r} cur={a[:80]!r}")

# ----------------------------------------------------------------------- CLI

def cmd_run(args: argparse.Namespace) -> int:
    selected = _select(args.scenario)
    if args.tmpdir:
        tmp_root = Path(args.tmpdir)
        tmp_root.mkdir(parents=True, exist_ok=True)
        results = _run_all(selected, tmp_root, svg=args.svg)
    else:
        with TemporaryDirectory() as td:
            results = _run_all(selected, Path(td), svg=args.svg)
    return _print_table(results)

def cmd_snapshot(args: argparse.Namespace) -> int:
    outdir = Path(args.outdir) if args.outdir else _default_baseline_dir()
    outdir.mkdir(parents=True, exist_ok=True)
    selected = _select(args.scenario)
    with TemporaryDirectory() as td:
        results = _run_all(selected, Path(td), svg=True)
    for r in results:
        (outdir / f"{r.name}.json").write_text(
            json.dumps(_serialize(r), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    print(f"wrote {len(results)} baselines to {outdir}")
    return _print_table(results)

def cmd_compare(args: argparse.Namespace) -> int:
    baseline_dir = (
        Path(args.baseline) if args.baseline else _default_baseline_dir()
    )
    if not baseline_dir.exists():
        print(f"no baselines at {baseline_dir}; run `snapshot` first")
        return 2
    selected = _select(args.scenario)
    with TemporaryDirectory() as td:
        results = _run_all(selected, Path(td), svg=True)
    exit_code = 0
    for r in results:
        base = baseline_dir / f"{r.name}.json"
        if not base.exists():
            print(f"{r.name}: no baseline (skip)")
            continue
        expected = json.loads(base.read_text(encoding="utf-8"))
        actual = _serialize(r)
        if expected == actual:
            print(f"{r.name}: MATCH")
        else:
            exit_code = 1
            print(f"{r.name}: DRIFT")
            _diff(expected, actual)
    return exit_code

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="tools.smoke_test",
        description="yate headless smoke harness",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    pr = sub.add_parser("run", help="run scenarios and print PASS/FAIL")
    pr.add_argument("--scenario", action="append",
                    help="scenario name (repeatable; default: all)")
    pr.add_argument("--tmpdir", help="scratch dir (default: ephemeral)")
    pr.add_argument("--svg", action="store_true",
                    help="also capture and show SVG text rows")
    pr.set_defaults(func=cmd_run)

    ps = sub.add_parser("snapshot", help="write JSON baselines")
    ps.add_argument("--scenario", action="append")
    ps.add_argument("--outdir", help=f"baseline dir (default: {_default_baseline_dir()})")
    ps.set_defaults(func=cmd_snapshot)

    pc = sub.add_parser("compare", help="run and diff against baselines")
    pc.add_argument("--scenario", action="append")
    pc.add_argument("--baseline", help=f"baseline dir (default: {_default_baseline_dir()})")
    pc.set_defaults(func=cmd_compare)

    args = p.parse_args(argv)
    return args.func(args)
