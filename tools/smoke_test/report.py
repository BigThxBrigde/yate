"""Rich rendering for the smoke harness.

Everything the user sees goes through :class:`Reporter`: a header panel,
per-tag result tables, expanded failure diffs, the coverage block, the
summary footer and the ``compare`` output.  Rich ships with Textual, so
this adds no dependency.

The console is created with ``soft_wrap`` and the tables use
``overflow="fold"`` so an 80-column terminal never breaks the layout.
"""

from __future__ import annotations

import platform
import sys
from datetime import datetime
from importlib import metadata
from pathlib import Path
from typing import Optional, Sequence

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .harness import Coverage, Scenario, ScenarioResult

__all__ = ["Reporter", "run_header_lines"]

_OK = "green"
_BAD = "red"
_WARN = "yellow"
_DIM = "dim"


def _version(name: str) -> str:
    try:
        return metadata.version(name)
    except Exception:  # noqa: BLE001 - reporting must never fail the run
        return "?"


def _stream_supports(sample: str) -> bool:
    """Can ``sys.stdout`` actually encode *sample*?

    A Windows console still on a legacy code page (GBK/Big5/...) cannot
    encode the check marks and block glyphs; fall back to ASCII there
    instead of raising ``UnicodeEncodeError`` mid-report.
    """
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    try:
        sample.encode(encoding)
    except (UnicodeEncodeError, LookupError):
        return False
    return True


_UNICODE = _stream_supports("✔✘█░│─╭╯")

#: Glyphs used by the report; ASCII fallbacks on legacy code pages.
OK_MARK, BAD_MARK = ("✔", "✘") if _UNICODE else ("+", "x")
FILL, EMPTY = ("█", "░") if _UNICODE else ("#", ".")
TABLE_BOX = box.SIMPLE_HEAVY if _UNICODE else box.ASCII


def _bar(done: int, total: int, width: int = 24) -> str:
    if total <= 0:
        return ""
    filled = int(round(width * done / total))
    return FILL * filled + EMPTY * (width - filled)


def run_header_lines() -> list[tuple[str, str]]:
    """(label, value) pairs shown in the header panel."""
    from yate import __version__ as yate_version

    return [
        ("yate", yate_version),
        ("python", platform.python_version()),
        ("textual", _version("textual")),
        ("rich", _version("rich")),
        ("platform", platform.system()),
    ]


def _status_cell(result: ScenarioResult) -> Text:
    if result.error is not None:
        return Text(f"{BAD_MARK} ERROR", style=f"bold {_BAD}")
    if result.fail_count == 0:
        return Text(f"{OK_MARK} PASS", style=f"bold {_OK}")
    return Text(f"{BAD_MARK} FAIL({result.fail_count})", style=f"bold {_BAD}")


def _checks_cell(result: ScenarioResult) -> Text:
    text = Text(f"{result.ok_count}/{len(result.checks)}")
    if result.fail_count:
        text.stylize(f"bold {_BAD}")
    return text


def _first_diff(expected: object, actual: object) -> int:
    """Index of the first differing character of the two reprs."""
    e, a = repr(expected), repr(actual)
    for i, (ce, ca) in enumerate(zip(e, a)):
        if ce != ca:
            return i
    return min(len(e), len(a))


def _diff_text(label: str, value: object, *, style: str, at: int) -> Text:
    body = repr(value)
    text = Text(f"    {label}: ")
    text.append(body[:at], style=style)
    text.append(body[at: at + 1], style=f"reverse bold {_BAD}")
    text.append(body[at + 1:], style=style)
    return text


class Reporter:
    """Renders every part of the smoke report onto one console."""

    def __init__(
        self,
        *,
        color: bool = True,
        width: Optional[int] = None,
        quiet: bool = False,
        verbose: bool = False,
        fail_only: bool = False,
        svg_rows: int = 6,
        html_path: Optional[str] = None,
    ) -> None:
        self.console = Console(
            width=width, no_color=not color, soft_wrap=True,
            record=html_path is not None,
        )
        self.quiet = quiet
        self.verbose = verbose
        self.fail_only = fail_only
        self.svg_rows = svg_rows
        self.html_path = html_path
        self.started = datetime.now()

    # ------------------------------------------------------------ progress

    def progress(self, done: int, total: int, name: str) -> None:
        if self.quiet:
            return
        self.console.print(
            f"  [{_DIM}][{done}/{total}][/] running {name}",
            markup=True, highlight=False,
        )

    # -------------------------------------------------------------- header

    def header(
        self, *, selected: Sequence[Scenario], tags: Sequence[str],
        command: str, seed: Optional[int] = None, repeat: int = 1,
    ) -> None:
        if self.quiet:
            return
        lines = run_header_lines()
        body = Text()
        body.append(f"{command}", style="bold")
        body.append("  ")
        body.append(self.started.strftime("%Y-%m-%d %H:%M:%S"), style=_DIM)
        body.append("\n")
        body.append("  ".join(f"{k} {v}" for k, v in lines), style=_DIM)
        body.append("\n")
        body.append(f"scenarios {len(selected)}", style="bold")
        if tags:
            body.append(f"  tags {', '.join(tags)}", style=_DIM)
        if repeat > 1:
            body.append(f"  repeat {repeat}", style=_DIM)
        if seed is not None:
            body.append(f"  seed {seed}", style=_DIM)
        body.append(f"  width {self.console.width}", style=_DIM)
        self.console.print(Panel(body, title="yate smoke test",
                                 border_style="blue", expand=False))

    # -------------------------------------------------------------- tables

    def results(self, results: Sequence[ScenarioResult]) -> None:
        """Grouped result tables (failing groups first) + failure details."""
        if self.quiet:
            return
        by_tag = self._group(results)
        for tag, group in by_tag:
            self._table(tag, group)
        self._failures(results)

    def _group(
        self, results: Sequence[ScenarioResult]
    ) -> list[tuple[str, list[ScenarioResult]]]:
        groups: dict[str, list[ScenarioResult]] = {}
        for r in results:
            groups.setdefault(r.tags[0] if r.tags else "misc", []).append(r)
        ordered = sorted(
            groups.items(),
            key=lambda kv: (
                sum(x.fail_count for x in kv[1]) == 0,  # failing groups first
                kv[0],
            ),
        )
        return ordered

    def _table(self, tag: str, group: Sequence[ScenarioResult]) -> None:
        ok = sum(r.ok_count for r in group)
        total = sum(len(r.checks) for r in group)
        fails = sum(r.fail_count for r in group)
        passed = sum(1 for r in group if r.fail_count == 0)
        table = Table(
            title=f"[bold]{tag}[/]  {passed}/{len(group)} scenarios",
            box=TABLE_BOX, expand=False,
            show_header=True, header_style="bold",
            title_style=None,
        )
        table.add_column("scenario", overflow="fold", no_wrap=False)
        table.add_column("status", justify="left")
        table.add_column("checks", justify="right")
        table.add_column("time", justify="right")
        for r in group:
            if self.fail_only and r.fail_count == 0:
                continue
            table.add_row(
                Text(r.name),
                _status_cell(r),
                _checks_cell(r),
                Text(f"{r.duration * 1000:.0f}ms", style=_DIM),
            )
        if fails:
            table.add_section()
            table.add_row(
                Text("subtotal", style="bold"),
                Text(f"{BAD_MARK} {fails} failed", style=f"bold {_BAD}"),
                Text(f"{ok}/{total}", style=f"bold {_BAD}"),
                Text(""),
            )
        else:
            table.add_section()
            table.add_row(
                Text("subtotal", style="bold"),
                Text(f"{OK_MARK} {passed}/{len(group)}", style=f"bold {_OK}"),
                Text(f"{ok}/{total}", style=_OK),
                Text(""),
            )
        self.console.print(table)

    def _failures(self, results: Sequence[ScenarioResult]) -> None:
        for r in results:
            if r.error is not None:
                self.console.print(
                    Panel(
                        Text(r.error, style=_BAD),
                        title=f"[bold {_BAD}]{r.name} raised[/]",
                        border_style=_BAD, expand=False,
                    )
                )
                continue
            failed = r.failed
            if not failed:
                if self.verbose:
                    self._checks(r)
                continue
            body = Text()
            for check in failed:
                at = _first_diff(check.expected, check.actual)
                prefix = "[invariant] " if check.invariant else ""
                body.append(f"{prefix}{check.label}\n", style=f"bold {_BAD}")
                body.append_text(
                    _diff_text("expected", check.expected, style=_OK, at=at)
                )
                body.append("\n")
                body.append_text(
                    _diff_text("actual  ", check.actual, style=_BAD, at=at)
                )
                body.append("\n")
            if self.verbose:
                self._checks(r, into=body)
            self.console.print(
                Panel(body, title=f"[bold {_BAD}]{r.name}[/]",
                      border_style=_BAD, expand=False)
            )

    def _checks(self, result: ScenarioResult, into: Optional[Text] = None) -> None:
        target = into if into is not None else Text()
        for check in result.checks:
            mark = OK_MARK if check.ok else BAD_MARK
            style = _OK if check.ok else _BAD
            target.append(f"  {mark} {check.label}", style=style)
            target.append(f" = {check.actual!r}\n", style=_DIM)
        if into is None:
            self.console.print(target)

    # -------------------------------------------------------------- svg

    def svg(self, results: Sequence[ScenarioResult]) -> None:
        if self.quiet or self.svg_rows <= 0:
            return
        for r in results:
            if not r.svg_rows:
                continue
            body = Text()
            width = max(20, self.console.width - 8)
            for y in sorted(r.svg_rows)[: self.svg_rows]:
                row = r.svg_rows[y].replace("\x00", " ")
                body.append(f"{y:>4} │ ", style=_DIM)
                body.append(row[:width])
                body.append("\n")
            self.console.print(
                Panel(body, title=f"[bold]{r.name}[/] svg",
                      border_style="blue", expand=False)
            )

    # ---------------------------------------------------------- coverage

    def coverage(self, cov: Coverage) -> None:
        if self.quiet:
            return
        (c_hit, c_total, c_missing), (a_hit, a_total, a_missing) = cov.report()
        body = Text()
        for label, hit, total, missing in (
            ("commands", c_hit, c_total, c_missing),
            ("actions ", a_hit, a_total, a_missing),
        ):
            pct = (hit / total * 100) if total else 0.0
            style = _OK if pct >= 60 else _WARN
            body.append(f"{label} ", style="bold")
            body.append(f"{_bar(hit, total)} ", style=style)
            body.append(f"{hit}/{total} ({pct:.0f}%)\n", style=style)
            if missing:
                body.append("  missing: ", style=_DIM)
                body.append(", ".join(missing), style=_WARN)
                body.append("\n")
        self.console.print(
            Panel(body, title="[bold]coverage[/]", border_style="blue",
                  expand=False)
        )

    # ----------------------------------------------------------- summary

    def summary(self, results: Sequence[ScenarioResult], *, exit_code: int) -> None:
        ok = sum(r.ok_count for r in results)
        total = sum(len(r.checks) for r in results)
        fails = total - ok
        elapsed = sum(r.duration for r in results)
        # Same "passed" rule as the CLI exit code / json totals: a scenario
        # that raised (crash or timeout) is never a pass, even though its
        # own checks are green.
        passed = sum(1 for r in results if r.fail_count == 0 and r.error is None)
        body = Text()
        pct = (ok / total * 100) if total else 100.0
        style = _OK if fails == 0 else _BAD
        body.append(f"{_bar(ok, total)} ", style=style)
        body.append(f"{ok}/{total} checks ({pct:.0f}%)\n", style=f"bold {style}")
        body.append(
            f"{passed}/{len(results)} scenarios passed",
            style=style,
        )
        body.append(f"   {elapsed:.2f}s total", style=_DIM)
        body.append("\n")
        if exit_code == 0:
            body.append("exit 0", style=f"bold {_OK}")
        elif exit_code == 2:
            body.append("exit 2", style=f"bold {_WARN}")
            body.append("  (no baselines)", style=_DIM)
        else:
            body.append("exit 1", style=f"bold {_BAD}")
            body.append(f"  ({fails} failing check(s))", style=_BAD)
        self.console.print(
            Panel(body, title="[bold]summary[/]",
                  border_style=_OK if fails == 0 else _BAD, expand=False)
        )
        if self.html_path is not None:
            try:
                self.console.save_html(self.html_path)
            except OSError as exc:  # pragma: no cover - best effort export
                self.console.print(f"[red]html export failed: {exc}[/]")

    # ----------------------------------------------------------- compare

    def compare(
        self, name: str, status: str, diffs: Sequence[str] = ()
    ) -> None:
        if status == "MATCH":
            self.console.print(
                f"  [{_OK}]{OK_MARK}[/{_OK}] {name}: [{_OK}]MATCH[/]"
            )
            return
        if status == "SKIP":
            self.console.print(f"  [{_WARN}]–[/{_WARN}] {name}: "
                               f"[{_WARN}]no baseline (skip)[/]")
            return
        self.console.print(
            f"  [{_BAD}]{BAD_MARK}[/{_BAD}] {name}: [{_BAD}]DRIFT[/]"
        )
        for line in diffs:
            self._diff_line(line)

    def _diff_line(self, line: str) -> None:
        stripped = line.strip()
        if stripped.startswith("- "):
            style = _BAD
        elif stripped.startswith("+ "):
            style = _OK
        elif stripped.startswith("~ "):
            style = _WARN
        else:
            style = _DIM
        self.console.print(f"    {line}", style=style, markup=False)

    # ------------------------------------------------------------ misc

    def note(self, text: str, *, style: str = _DIM) -> None:
        if not self.quiet:
            self.console.print(text, style=style, markup=False)

    def json_written(self, path: Path) -> None:
        self.note(f"json report: {path}")
