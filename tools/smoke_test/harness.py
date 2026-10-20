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
* :func:`run_scenarios` -- the sequential runner, plus
  :func:`run_scenarios_parallel` which shards the selection over worker
  processes (``--jobs N``) and merges their coverage tallies.
"""

from __future__ import annotations

import asyncio
import os
import pickle
import random
import re
import sys
import time
from collections import Counter
from collections.abc import Awaitable, Callable, Generator, Sequence
from concurrent.futures import ProcessPoolExecutor, as_completed
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

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
        # Private on purpose upstream: the constant has no public accessor.
        from textual import _wait  # pyright: ignore[reportPrivateUsage]
    except ImportError:  # pragma: no cover - every Textual ships this module
        return
    _wait.SLEEP_GRANULARITY = 0.001


_speed_up_pilot()

__all__ = [
    "Check",
    "Coverage",
    "DEFAULT_SCENARIO_TIMEOUT_S",
    "RunOptions",
    "Scenario",
    "ScenarioResult",
    "SvgDriftError",
    "TAGS",
    "extract_svg_rows",
    "get_seed",
    "new_app",
    "rng_for",
    "run_scenarios",
    "run_scenarios_parallel",
    "run_shard",
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

_DEFAULT_SEED: int = 1337
_seed = _DEFAULT_SEED


def set_seed(value: int) -> None:
    """Set the seed shared by every randomized (fuzz) scenario."""
    global _seed
    _seed = int(value)


def get_seed() -> int:
    """The seed set by :func:`set_seed` (default: 1337)."""
    return _seed


def rng_for(name: str) -> random.Random:
    """Deterministic RNG for *name* (stable across runs for a fixed seed)."""
    return random.Random(f"{name}:{_seed}")


# --------------------------------------------------- SVG text extraction

#: Textual version whose ``save_screenshot`` output the patterns below were
#: adapted to (measured against the .venv of this checkout).
_ADAPTED_TEXTUAL_VERSION: str = "8.2.8"

# Textual 8.2.8 (via Rich's terminal SVG export) emits one
# ``<text class="..." ... y="N.N" ...>content</text>`` element per text run:
# class is always the first attribute and y is always a decimal number.
_TEXT_RE: re.Pattern[str] = re.compile(
    r'<text class="[^"]*"[^>]*?\sy="(\d+(?:\.\d+)?)"[^>]*>(.*?)</text>', re.S
)
_INNER_RE: re.Pattern[str] = re.compile(r">([^<]+)<")


class SvgDriftError(RuntimeError):
    """The exported SVG markup no longer matches the extraction patterns.

    Raised when a screenshot contains ``<text`` elements the patterns above
    cannot read -- almost always a Textual upgrade changing Rich's SVG
    export format.
    """


def extract_svg_rows(svg: str) -> dict[int, str]:
    """Map y-coordinate -> concatenated text content for each rendered row.

    Raises :class:`SvgDriftError` instead of returning silently empty or
    partial rows when the file contains ``<text`` elements the patterns do
    not cover; the message carries the SVG head so the version drift is
    diagnosed at the source rather than as a shower of empty-row failures.
    """
    matches = list(_TEXT_RE.finditer(svg))
    expected = svg.count("<text")
    if len(matches) != expected:
        head = " ".join(svg[:200].split())
        raise SvgDriftError(
            f"SVG text extraction covers {len(matches)} of {expected} "
            "<text> elements -- the markup format likely drifted with a "
            f"Textual upgrade (patterns adapted to Textual "
            f"{_ADAPTED_TEXTUAL_VERSION}); SVG head: {head!r}"
        )
    rows: dict[int, str] = {}
    for m in matches:
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
    #: Verdict frozen before a worker process hands the check back.  Payloads
    #: that cannot be pickled (Textual widgets hold weakrefs) are replaced by
    #: their repr, which could otherwise flip a failure into a pass; ``None``
    #: means "compare expected with actual as usual".
    ok_override: bool | None = None

    @property
    def ok(self) -> bool:
        """Whether expected and actual match (or the frozen verdict says so)."""
        if self.ok_override is not None:
            return self.ok_override
        return self.expected == self.actual


@dataclass
class ScenarioResult:
    """Outcome of one scenario run: checks, SVG rows, duration, error."""

    name: str
    checks: list[Check] = field(default_factory=lambda: [])
    svg_rows: dict[int, str] = field(default_factory=lambda: {})
    tags: tuple[str, ...] = ()
    duration: float = 0.0
    #: Set when the scenario raised; rendered as a failure by the report.
    error: str | None = None

    @property
    def ok_count(self) -> int:
        """Number of passing checks."""
        return sum(1 for c in self.checks if c.ok)

    @property
    def fail_count(self) -> int:
        """Number of failing checks."""
        return len(self.checks) - self.ok_count

    @property
    def failed(self) -> list[Check]:
        """The failing checks, in insertion order."""
        return [c for c in self.checks if not c.ok]


@dataclass
class Scenario:
    """One named smoke scenario with an async run function and tags."""

    name: str
    run: Callable[[Path], Awaitable[ScenarioResult]]
    tags: tuple[str, ...] = ()
    #: P2 scenarios: skipped by ``--skip-slow``.
    slow: bool = False

    @property
    def primary_tag(self) -> str:
        """The first tag, or ``"misc"`` when the scenario has none."""
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
        """Count a ``:`` command (shell ``!`` lines and line jumps excluded)."""
        text = text.strip()
        if not text or text.startswith("!"):
            return
        # A bare number is a line jump, not a command (see Editor.run_command).
        if re.fullmatch(r"[+-]?\d+", text):
            return
        self.commands[text.split()[0]] += 1

    def note_action(self, name: str) -> None:
        """Count a named action invocation."""
        if name:
            self.actions[name] += 1

    def merge(self, other: Coverage) -> None:
        """Fold another coverage tally into this one.

        Parallel runs collect counters in each worker process; the parent
        merges them here so ``--coverage`` reports the same numbers as a
        single-process run.
        """
        self.commands.update(other.commands)
        self.actions.update(other.actions)
        self.command_universe.update(other.command_universe)
        self.action_universe.update(other.action_universe)

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
def track_coverage() -> Generator[Coverage]:
    """Count every ``run_command`` / ``execute_action`` while active.

    The wrappers only *count* and delegate, so behaviour is unchanged; the
    patch is installed for the duration of the run and removed afterwards
    (it never reaches product code).
    """
    cov = Coverage()
    original_run_command = Editor.run_command
    original_execute_action = Editor.execute_action
    original_app_init = YateApp.__init__

    def run_command(self: Editor, text: str) -> None:
        cov.note_command(text)
        original_run_command(self, text)

    def execute_action(self: Editor, name: str) -> bool:
        cov.note_action(name)
        return original_execute_action(self, name)

    def app_init(self: YateApp, *args: object, **kwargs: object) -> None:
        # The name spaces are only complete once the shell has loaded the
        # built-in tables into the editor's registries (R7), so snapshot them
        # at the end of the shell's __init__ -- the editor's own __init__ runs
        # before that and would report an empty universe.
        cast(Callable[..., None], original_app_init)(self, *args, **kwargs)
        cov.note_registries(self.editor)

    Editor.run_command = run_command
    Editor.execute_action = execute_action
    YateApp.__init__ = app_init
    try:
        yield cov
    finally:
        Editor.run_command = original_run_command
        Editor.execute_action = original_execute_action
        YateApp.__init__ = original_app_init


# --------------------------------------------------------------- app factory

#: Apps built by the currently running scenario (reset before each one).
_apps: list[YateApp] = []


def new_app(
    target: str | Path | None = None,
    *,
    keymap: str | None = None,
    theme_name: str | None = None,
    config: YateConfig | None = None,
) -> YateApp:
    """Create a :class:`YateApp` and register it for the invariant sweep."""
    app = YateApp(
        target=target, keymap=keymap, theme_name=theme_name, config=config
    )
    _apps.append(app)
    return app


def current_app() -> YateApp | None:
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
    row_in_lines = 0 <= row < len(buf.lines)
    checks.append(Check("invariant:cursor_row", True,
                        row_in_lines, invariant=True))
    # Guard the column probe: a crashing scenario can leave the cursor out
    # of range, and this sweep runs outside _run_one's try/except -- it must
    # record a failed check, never IndexError the whole harness.
    checks.append(Check(
        "invariant:cursor_col", True,
        row_in_lines and 0 <= col <= len(buf.lines[row]), invariant=True))
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

#: Default per-scenario wall clock budget in seconds (``--timeout`` overrides).
DEFAULT_SCENARIO_TIMEOUT_S: float = 60.0


@dataclass
class RunOptions:
    """Knobs for one harness run: SVG capture, invariants, timeout."""

    svg: bool = False
    invariants: bool = True
    #: Wall clock budget per scenario in seconds: a scenario exceeding it is
    #: cancelled and reported with ``error`` set, so one hung scenario cannot
    #: stall the remaining ones (``--timeout`` overrides the default).
    timeout: float = DEFAULT_SCENARIO_TIMEOUT_S
    progress: Callable[[int, int, str], None] | None = None


def _run_one(
    scenario: Scenario, tmp_root: Path, options: RunOptions
) -> ScenarioResult:
    sub = tmp_root / scenario.name
    sub.mkdir(parents=True, exist_ok=True)
    _apps.clear()
    theme_before = theme.active().name
    started = time.monotonic()
    try:
        result = asyncio.run(_timed(scenario, sub, options.timeout))
    except (KeyboardInterrupt, SystemExit):
        # Ctrl+C must still abort the whole suite: a crashing scenario is a
        # FAIL, an interrupted operator is not.
        raise
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


async def _timed(
    scenario: Scenario, tmp: Path, timeout: float
) -> ScenarioResult:
    """Await one scenario under a wall clock budget (``--timeout``).

    ``asyncio.wait_for`` cancels a scenario that exceeds *timeout* seconds;
    the cancellation unwinds the scenario (shutting down its app) and the
    runner reports the scenario as failed instead of hanging forever.
    """
    try:
        return await asyncio.wait_for(scenario.run(tmp), timeout=timeout)
    except TimeoutError:
        return ScenarioResult(
            scenario.name,
            tags=scenario.tags,
            error=f"timeout: exceeded {timeout:g}s wall clock budget",
        )


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


def _picklable_payload(value: object) -> object:
    """Return *value* if a worker can hand it back, else its ``repr``.

    ``pickle`` reports every unserializable payload as an ``Exception``
    (``TypeError`` / ``AttributeError`` / ``PicklingError``) and never as a
    ``BaseException``, so the broad catch cannot swallow an interrupt.
    """
    try:
        pickle.dumps(value)
    except Exception:  # noqa: BLE001 - any payload may hold a weakref
        return repr(value)
    return value


def _make_picklable(result: ScenarioResult) -> ScenarioResult:
    """Rewrite check payloads a spawned worker cannot pickle.

    Textual widgets (``DiffPane`` in ``diff_three_way_merge``) carry weakrefs,
    so a result holding one cannot cross the process boundary.  The report only
    ever renders these values, so the repr keeps the failure detail readable --
    but the verdict is frozen first, because two distinct widgets can share a
    repr and a rewritten pair must not turn a failure into a pass.
    """
    try:
        pickle.dumps(result)
    except Exception:  # noqa: BLE001 - only a probe for the rewrite below
        pass
    else:
        return result
    for check in result.checks:
        verdict = check.ok
        check.expected = _picklable_payload(check.expected)
        check.actual = _picklable_payload(check.actual)
        check.ok_override = verdict
    return result


def run_shard(
    names: Sequence[str],
    tmp_root: str,
    *,
    svg: bool,
    invariants: bool,
    timeout: float,
) -> tuple[list[ScenarioResult], Coverage]:
    """Run the named scenarios here and return their results plus coverage.

    Module level and name-only on purpose: workers are spawned processes
    (Windows has no fork), so every argument has to be picklable and the
    parent's progress callback -- which lives in :class:`RunOptions` -- cannot
    travel with the call.  The scenario registry is imported inside the
    function because ``tools.smoke_test.scenarios`` imports this module.
    """
    from tools.smoke_test.scenarios import SCENARIOS

    selected = select_scenarios(SCENARIOS, names=list(names))
    options = RunOptions(svg=svg, invariants=invariants, timeout=timeout)
    with track_coverage() as cov:
        results = [
            _run_one(scenario, Path(tmp_root), options) for scenario in selected
        ]
    return [_make_picklable(result) for result in results], cov


def run_scenarios_parallel(
    selected: Sequence[Scenario], tmp_root: Path, options: RunOptions, jobs: int
) -> tuple[list[ScenarioResult], Coverage]:
    """Run *selected* across *jobs* processes; results in selection order.

    One task per scenario, so the pool balances itself: scenario lengths range
    from 0.1s to 30s here, and any static split either starves a worker or
    makes the slowest shard the wall clock.  Each worker runs the scenario in
    its own interpreter, which preserves the isolation the serial runner
    relies on: the module-level ``_apps`` list, the :func:`track_coverage`
    monkeypatch and the process-global theme all live inside the worker.
    Coverage tallies come back from every worker and are merged here, so
    ``--coverage`` reports the same numbers as the serial run.

    A task that raises is reported on stderr and re-run in this process, so a
    worker-startup or pickling problem degrades to the serial path instead of
    losing a scenario.
    """
    names = tuple(scenario.name for scenario in selected)
    tags_by_name = {scenario.name: scenario.tags for scenario in selected}
    by_name: dict[str, ScenarioResult] = {}
    merged = Coverage()
    total = len(names)
    finished = 0
    fallback: list[str] = []

    def _absorb(
        results: Sequence[ScenarioResult], cov: Coverage
    ) -> None:
        nonlocal finished
        merged.merge(cov)
        for result in results:
            by_name[result.name] = result
            finished += 1
            if options.progress is not None:
                options.progress(finished, total, result.name)

    with ProcessPoolExecutor(max_workers=min(jobs, len(names))) as pool:
        futures = {
            pool.submit(
                run_shard, (name,), str(tmp_root),
                svg=options.svg,
                invariants=options.invariants,
                timeout=options.timeout,
            ): name
            for name in names
        }
        for future in as_completed(futures):
            try:
                results, cov = future.result()
            except Exception as exc:  # noqa: BLE001 - a dead worker is not a scenario failure
                print(
                    f"warning: smoke worker for {futures[future]!r} failed "
                    f"({exc!r}); re-running it in this process",
                    file=sys.stderr,
                )
                fallback.append(futures[future])
                continue
            _absorb(results, cov)

    if fallback:
        # A fresh directory for the retries: several scenarios build their
        # fixtures with a bare ``mkdir()`` and would raise FileExistsError if a
        # half-finished earlier attempt had already written them.  The retry is
        # guarded in turn: a shard that fails twice must turn into failed
        # scenarios, never into a traceback that discards the results already
        # collected from the healthy workers.
        try:
            retried, retry_cov = run_shard(
                tuple(fallback), str(tmp_root / "retry"),
                svg=options.svg,
                invariants=options.invariants,
                timeout=options.timeout,
            )
        except Exception as exc:  # noqa: BLE001 - a dead retry is a failed scenario
            for name in fallback:
                by_name[name] = ScenarioResult(
                    name,
                    tags=tags_by_name[name],
                    error=f"{type(exc).__name__}: {exc}",
                )
                finished += 1
                if options.progress is not None:
                    options.progress(finished, total, name)
        else:
            _absorb(retried, retry_cov)

    return [by_name[s.name] for s in selected if s.name in by_name], merged


def select_scenarios(
    all_scenarios: Sequence[Scenario],
    *,
    names: Sequence[str] | None = None,
    tags: Sequence[str] | None = None,
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
