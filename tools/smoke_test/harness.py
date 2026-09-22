"""Core types, coverage tracking and the scenario runner.

The smoke harness drives :class:`~yate.app.YateApp` under Textual's
``pilot.run_test()`` exactly like ``tests/test_app_textual.py``; it never
touches a real terminal.  This module holds everything that is *not*
rendering (see :mod:`tools.smoke_test.report`) and *not* baseline storage
(see :mod:`tools.smoke_test.baselines`):

* :class:`Check` / :class:`Scenario` / :class:`ScenarioResult` -- the data
  model every scenario builds;
* :func:`new_app` -- app factory that registers the instance so the runner
  can run the global invariant sweep on it afterwards;
* :class:`Coverage` -- command / action hit counters (the "how much did we
  actually exercise" metric);
* :func:`run_scenarios` -- the sequential runner.
"""

from __future__ import annotations

import asyncio
import os
import random
import re
import time
from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import (
    Awaitable,
    Callable,
    Generator,
    Optional,
    Sequence,
)

os.environ.setdefault("YATE_PYTHON_LSP", "off")

from yate.app import YateApp  # noqa: E402
from yate.config import YateConfig  # noqa: E402
from yate.editor import Editor  # noqa: E402
from yate.editor_view import theme  # noqa: E402


def _speed_up_pilot() -> None:
    """Cut Textual's per-key wall clock from ~70ms to a few ms.

    ``Pilot._press_keys`` calls ``wait_for_idle(0)`` twice per key, which
    always performs one ``asyncio.sleep(SLEEP_GRANULARITY)`` (1/50s, rounded
    up to ~15-30ms by the Windows timer).  Typing a 70-character path then
    costs five seconds of pure sleeping, and the whole suite would blow its
    time budget on waiting instead of asserting.

    The constant is only read inside ``wait_for_idle``'s body, so lowering it
    keeps every call site intact: the pilot still drains the message queue,
    it just polls faster.  Scenarios that really have to wait for a worker
    use :func:`wait_until` (an explicit ``asyncio.sleep``), not this.
    """
    try:
        from textual import _wait  # pyright: ignore[reportPrivateUsage]
    except ImportError:  # pragma: no cover - every Textual ships this module
        return
    _wait.SLEEP_GRANULARITY = 0.001


_speed_up_pilot()

__all__ = [
    "Check",
    "Coverage",
    "RunOptions",
    "Scenario",
    "ScenarioResult",
    "TAGS",
    "extract_svg_rows",
    "get_seed",
    "new_app",
    "rng_for",
    "run_scenarios",
    "set_seed",
    "snapshot_svg",
    "track_coverage",
]

# ------------------------------------------------------------ scenario tags

#: Every tag a scenario may carry.  ``--tag`` filters on these; the report
#: groups the result tables by the scenario's *primary* tag (its first one).
TAGS: tuple[str, ...] = (
    "edit",
    "select",
    "search",
    "files",
    "panes",
    "explorer",
    "command",
    "view",
    "integration",
    "regression",
    "stress",
)

# --------------------------------------------------------- fuzz seed

_DEFAULT_SEED = 1337
_seed = _DEFAULT_SEED


def set_seed(value: int) -> None:
    """Set the seed shared by every randomized (fuzz) scenario."""
    global _seed
    _seed = int(value)


def get_seed() -> int:
    return _seed


def rng_for(name: str) -> random.Random:
    """Deterministic RNG for *name* (stable across runs for a fixed seed)."""
    return random.Random(f"{name}:{_seed}")


# --------------------------------------------------- SVG text extraction

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


def snapshot_svg(app: YateApp, tmp: Path) -> dict[int, str]:
    """Screenshot *app* into *tmp* and return its rendered text rows."""
    svg_path = tmp / "shot.svg"
    app.save_screenshot(str(svg_path))
    return extract_svg_rows(svg_path.read_text(encoding="utf-8"))


# ------------------------------------------------------------- result types


@dataclass
class Check:
    """One ``expected == actual`` assertion."""

    label: str
    expected: object
    actual: object
    #: True for checks appended automatically by the invariant sweep.
    invariant: bool = False

    @property
    def ok(self) -> bool:
        return self.expected == self.actual


@dataclass
class ScenarioResult:
    name: str
    checks: list[Check] = field(default_factory=lambda: [])
    svg_rows: dict[int, str] = field(default_factory=lambda: {})
    tags: tuple[str, ...] = ()
    duration: float = 0.0
    #: Set when the scenario raised; rendered as a failure by the report.
    error: str | None = None

    @property
    def ok_count(self) -> int:
        return sum(1 for c in self.checks if c.ok)

    @property
    def fail_count(self) -> int:
        return len(self.checks) - self.ok_count

    @property
    def failed(self) -> list[Check]:
        return [c for c in self.checks if not c.ok]


@dataclass
class Scenario:
    name: str
    run: Callable[[Path], Awaitable[ScenarioResult]]
    tags: tuple[str, ...] = ()
    #: P2 scenarios: skipped by ``--skip-slow``.
    slow: bool = False

    @property
    def primary_tag(self) -> str:
        return self.tags[0] if self.tags else "misc"


# ------------------------------------------------------------------ coverage


@dataclass
class Coverage:
    """How many ``:`` commands / named actions the run actually exercised."""

    commands: Counter[str] = field(default_factory=lambda: Counter[str]())
    actions: Counter[str] = field(default_factory=lambda: Counter[str]())
    command_universe: set[str] = field(default_factory=lambda: set[str]())
    action_universe: set[str] = field(default_factory=lambda: set[str]())

    def note_registries(self, editor: Editor) -> None:
        """Record the full command/action name space of *editor*."""
        self.command_universe.update(editor.commands.names())
        self.action_universe.update(editor.actions.names())

    def note_command(self, text: str) -> None:
        text = text.strip()
        if not text or text.startswith("!"):
            return
        # A bare number is a line jump, not a command (see Editor.run_command).
        if re.fullmatch(r"[+-]?\d+", text):
            return
        self.commands[text.split()[0]] += 1

    def note_action(self, name: str) -> None:
        if name:
            self.actions[name] += 1

    def report(self) -> tuple[tuple[int, int, list[str]], tuple[int, int, list[str]]]:
        """``((hit, total, missing), (hit, total, missing))`` for commands,
        then actions."""
        cmd_hit = {n for n in self.commands if n in self.command_universe}
        act_hit = {n for n in self.actions if n in self.action_universe}
        return (
            (len(cmd_hit), len(self.command_universe),
             sorted(self.command_universe - cmd_hit)),
            (len(act_hit), len(self.action_universe),
             sorted(self.action_universe - act_hit)),
        )


@contextmanager
def track_coverage() -> Generator[Coverage, None, None]:
    """Count every ``run_command`` / ``execute_action`` while active.

    The wrappers only *count* and delegate, so behaviour is unchanged; the
    patch is installed for the duration of the run and removed afterwards
    (it never reaches product code).
    """
    cov = Coverage()
    original_run_command = Editor.run_command
    original_execute_action = Editor.execute_action
    original_init = Editor.__init__

    def run_command(self: Editor, text: str) -> None:
        cov.note_command(text)
        original_run_command(self, text)

    def execute_action(self: Editor, name: str) -> None:
        cov.note_action(name)
        original_execute_action(self, name)

    def init(self: Editor, *args: object, **kwargs: object) -> None:
        original_init(self, *args, **kwargs)  # type: ignore[arg-type]
        cov.note_registries(self)

    Editor.run_command = run_command  # type: ignore[method-assign]
    Editor.execute_action = execute_action  # type: ignore[method-assign]
    Editor.__init__ = init  # type: ignore[method-assign]
    try:
        yield cov
    finally:
        Editor.run_command = original_run_command  # type: ignore[method-assign]
        Editor.execute_action = original_execute_action  # type: ignore[method-assign]
        Editor.__init__ = original_init  # type: ignore[method-assign]


# --------------------------------------------------------------- app factory

#: Apps built by the currently running scenario (reset before each one).
_apps: list[YateApp] = []


def new_app(
    target: Optional[str | Path] = None,
    *,
    keymap: Optional[str] = None,
    theme_name: Optional[str] = None,
    config: Optional[YateConfig] = None,
) -> YateApp:
    """Create a :class:`YateApp` and register it for the invariant sweep."""
    app = YateApp(
        target=target, keymap=keymap, theme_name=theme_name, config=config
    )
    _apps.append(app)
    return app


def current_app() -> Optional[YateApp]:
    """The last app the running scenario created (``None`` before any)."""
    return _apps[-1] if _apps else None


# ---------------------------------------------------------------- invariants


def invariant_checks(app: YateApp, *, theme_before: str) -> list[Check]:
    """The automatic post-scenario invariant sweep.

    Runs after every scenario (existing ones included) so a scenario that
    leaves the app in an impossible state fails even when its own
    assertions happen to pass:

    1. the cursor is inside the buffer;
    2. no modal screen was left on the stack;
    3. the app did not crash (``return_code`` is ``None`` or ``0``);
    4. process-global singletons (the color theme) are back to their
       pre-scenario value;
    5. a document that claims to be saved really matches the bytes on disk.
    """
    checks: list[Check] = []
    buf = app.editor.session.buffer
    row, col = buf.cursor
    checks.append(Check("invariant:cursor_row", True,
                        0 <= row < len(buf.lines), invariant=True))
    checks.append(Check("invariant:cursor_col", True,
                        0 <= col <= len(buf.lines[row]), invariant=True))
    checks.append(Check("invariant:no_leftover_modal", True,
                        len(app.screen_stack) <= 1, invariant=True))
    rc = app.return_code
    checks.append(Check("invariant:no_crash", True,
                        rc is None or rc == 0, invariant=True))
    checks.append(Check("invariant:theme_restored", theme_before,
                        theme.active().name, invariant=True))
    doc = app.editor.session.doc
    if doc.path is not None and not doc.modified:
        try:
            on_disk = doc.path.read_text(encoding=doc.encoding)
        except OSError:
            on_disk = None
        if on_disk is not None:
            checks.append(Check("invariant:saved_matches_disk",
                                doc.buffer.get_text(), on_disk, invariant=True))
    return checks


# -------------------------------------------------------------------- runner


@dataclass
class RunOptions:
    svg: bool = False
    invariants: bool = True
    progress: Optional[Callable[[int, int, str], None]] = None


def _run_one(
    scenario: Scenario, tmp_root: Path, options: RunOptions
) -> ScenarioResult:
    sub = tmp_root / scenario.name
    sub.mkdir(parents=True, exist_ok=True)
    _apps.clear()
    theme_before = theme.active().name
    started = time.monotonic()
    try:
        result = asyncio.run(_await(scenario.run, sub))
    except BaseException as exc:  # noqa: BLE001 - a crashing scenario is a FAIL
        result = ScenarioResult(
            scenario.name, tags=scenario.tags,
            error=f"{type(exc).__name__}: {exc}",
        )
    result.duration = time.monotonic() - started
    result.tags = scenario.tags
    if not options.svg:
        result.svg_rows = {}
    if options.invariants and (app := current_app()) is not None:
        result.checks.extend(invariant_checks(app, theme_before=theme_before))
    # Hygiene: restore the process-global theme even when a scenario drifted,
    # so the *next* scenario starts from a known state (the check above
    # already recorded the drift).
    try:
        theme.set_theme(theme_before)
    except KeyError:  # pragma: no cover - only if a scenario deletes a theme
        pass
    return result


async def _await(
    run: Callable[[Path], Awaitable[ScenarioResult]], tmp: Path
) -> ScenarioResult:
    """Await the scenario coroutine (``asyncio.run`` needs a coroutine)."""
    return await run(tmp)


def run_scenarios(
    selected: Sequence[Scenario], tmp_root: Path, options: RunOptions
) -> list[ScenarioResult]:
    """Run *selected* sequentially, each in its own ``tmp_root`` subdir."""
    results: list[ScenarioResult] = []
    total = len(selected)
    for i, scenario in enumerate(selected, start=1):
        if options.progress is not None:
            options.progress(i, total, scenario.name)
        results.append(_run_one(scenario, tmp_root, options))
    return results


def select_scenarios(
    all_scenarios: Sequence[Scenario],
    *,
    names: Optional[Sequence[str]] = None,
    tags: Optional[Sequence[str]] = None,
    skip_slow: bool = False,
) -> list[Scenario]:
    """Filter *all_scenarios* by name / tag / slowness, keeping file order."""
    chosen: list[Scenario] = []
    by_name = {s.name: s for s in all_scenarios}
    requested = list(names) if names else [s.name for s in all_scenarios]
    unknown = [n for n in requested if n not in by_name]
    if unknown:
        raise SystemExit(
            f"unknown scenario(s): {', '.join(unknown)}; "
            f"available: {', '.join(by_name)}"
        )
    wanted_tags = set(tags) if tags else None
    for name in requested:
        scenario = by_name[name]
        if skip_slow and scenario.slow:
            continue
        if wanted_tags is not None and not wanted_tags.intersection(scenario.tags):
            continue
        chosen.append(scenario)
    if wanted_tags:
        bad = wanted_tags - set(TAGS)
        if bad:
            raise SystemExit(
                f"unknown tag(s): {', '.join(sorted(bad))}; "
                f"available: {', '.join(TAGS)}"
            )
    return chosen
