"""Coverage accounting, fuzz RNG and invariant sweep of ``tools/smoke_test/harness.py``.

Covers the three pieces of the harness that decide whether a smoke run means
anything at all:

* :class:`Coverage` -- which ``:`` command lines count (empty, ``!shell`` and
  bare line numbers do not), how the hit set intersects the editor's registries
  and how the missing names are reported;
* :func:`set_seed` / :func:`rng_for` -- the determinism contract the randomized
  scenarios rely on;
* :func:`invariant_checks` -- proven **both ways** here: a clean scenario gets
  green ``invariant:*`` checks appended, and a scenario that leaves the app in
  an impossible state (a modal still on the screen stack, the cursor pushed past
  the last line) is failed by the same hook;
* the scenario registry guards -- unique names, tags drawn from
  :data:`tools.smoke_test.harness.TAGS`, coroutine ``run`` callables and
  docstrings, so a later scenario cannot silently shadow or skip the suite.

Not covered: the scenario bodies themselves (they are the smoke suite, run by
``python -m tools.smoke_test``), the SVG extraction patterns and the reporter
(``tests/test_smoke_tool.py``).
"""

from __future__ import annotations

import inspect
import random
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast, override

import pytest
from textual.app import ComposeResult
from textual.screen import Screen
from tools.smoke_test.harness import (
    TAGS,
    Check,
    Coverage,
    RunOptions,
    Scenario,
    ScenarioResult,
    get_seed,
    new_app,
    rng_for,
    run_scenarios,
    set_seed,
)
from tools.smoke_test.scenarios import SCENARIOS
from yate.editor_view import theme


@pytest.fixture(autouse=True)
def restore_fuzz_seed() -> Iterator[None]:
    """Undo any :func:`set_seed` call so the global seed never leaks."""
    before = get_seed()
    yield
    set_seed(before)


@pytest.fixture
def restore_theme() -> Iterator[None]:
    """Undo the process-global theme change a bare :class:`YateApp` makes."""
    before = theme.active().name
    yield
    theme.set_theme(before)


# --- Coverage.note_command ---------------------------------------------------


def test_note_command_ignores_blank_input() -> None:
    cov = Coverage()
    cov.note_command("")
    cov.note_command("   \t ")
    assert cov.commands == {}


def test_note_command_ignores_shell_escape_lines() -> None:
    cov = Coverage()
    cov.note_command("!echo hi")
    cov.note_command("  !echo hi  ")
    assert cov.commands == {}


def test_note_command_ignores_bare_line_numbers() -> None:
    cov = Coverage()
    for text in ("12", " 42 ", "+7", "-3"):
        cov.note_command(text)
    assert cov.commands == {}


def test_note_command_counts_a_plain_command_under_its_first_word() -> None:
    cov = Coverage()
    cov.note_command("  theme   latte  ")
    assert cov.commands == {"theme": 1}


def test_note_command_accumulates_repeats_of_the_same_name() -> None:
    cov = Coverage()
    cov.note_command("w")
    cov.note_command("w notes.txt")
    assert cov.commands == {"w": 2}


# --- Coverage.note_action / report ------------------------------------------


def test_note_action_ignores_an_empty_name() -> None:
    cov = Coverage()
    cov.note_action("")
    assert cov.actions == {}


def test_report_counts_only_names_present_in_the_universe() -> None:
    cov = Coverage(command_universe={"w", "q"}, action_universe={"save"})
    cov.note_command("w notes.txt")
    cov.note_command("bogus")
    cov.note_action("save")
    cov.note_action("not_an_action")
    (c_hit, c_total, c_missing), (a_hit, a_total, a_missing) = cov.report()
    assert (c_hit, c_total, c_missing) == (1, 2, ["q"])
    assert (a_hit, a_total, a_missing) == (1, 1, [])


def test_report_sorts_the_missing_names() -> None:
    cov = Coverage(command_universe={"z", "a", "m"}, action_universe=set())
    (c_hit, _, c_missing), _ = cov.report()
    assert c_missing == ["a", "m", "z"]
    assert c_hit == 0


def test_report_of_an_empty_run_reports_empty_universes() -> None:
    assert Coverage().report() == ((0, 0, []), (0, 0, []))


def test_note_registries_reads_the_full_editor_name_space(restore_theme: None) -> None:
    # A bare YateApp (no pilot) already ran the shell table registration, so the
    # universe is the real one -- ~20ms, no app run, no terminal.
    app = new_app()
    cov = Coverage()
    cov.note_registries(app.editor)
    (c_hit, c_total, _), (a_hit, a_total, _) = cov.report()
    assert c_total == len(app.editor.commands.names()) > 0
    assert a_total == len(app.editor.actions.names()) > 0
    assert (c_hit, a_hit) == (0, 0)


def test_note_registries_then_note_command_registers_a_hit(restore_theme: None) -> None:
    app = new_app()
    cov = Coverage()
    cov.note_registries(app.editor)
    known = app.editor.commands.names()[0]
    cov.note_command(f"{known} arg")
    (c_hit, _, c_missing), _ = cov.report()
    assert c_hit == 1
    assert known not in c_missing


# --- fuzz seed ---------------------------------------------------------------


def test_set_seed_round_trips_through_get_seed() -> None:
    set_seed(4242)
    assert get_seed() == 4242


def test_rng_for_same_name_and_seed_yields_the_same_sequence() -> None:
    set_seed(7)
    first = [rng_for("fuzz").random() for _ in range(3)]
    second = [rng_for("fuzz").random() for _ in range(3)]
    assert first == second


def test_rng_for_different_seeds_yields_different_sequences() -> None:
    set_seed(1)
    first = [rng_for("fuzz").random() for _ in range(3)]
    set_seed(2)
    second = [rng_for("fuzz").random() for _ in range(3)]
    assert first != second


def test_rng_for_gives_each_name_an_independent_stream() -> None:
    set_seed(99)
    alpha = [rng_for("alpha").random() for _ in range(3)]
    beta = [rng_for("beta").random() for _ in range(3)]
    assert alpha != beta
    # ... and asking again for one name replays its own stream, not the other's.
    assert [rng_for("alpha").random() for _ in range(3)] == alpha


def test_rng_for_returns_a_fresh_random_instance() -> None:
    set_seed(5)
    rng = rng_for("fuzz")
    assert isinstance(rng, random.Random)
    assert rng is not rng_for("fuzz")


# --- the invariant sweep: the green direction --------------------------------


async def _tidy_scenario(tmp: Path) -> ScenarioResult:
    """Type into a fresh buffer and close the app cleanly."""
    app = new_app(target=tmp / "notes.txt")
    checks: list[Check] = []
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("h", "i")
        await pilot.pause()
        checks.append(
            Check("typed", "hi", app.editor.session.buffer.lines[0])
        )
    return ScenarioResult("invariant_tidy", checks)


def test_run_scenarios_appends_green_invariant_checks_to_a_clean_scenario(
    tmp_path: Path,
) -> None:
    results = run_scenarios(
        [Scenario("invariant_tidy", _tidy_scenario)], tmp_path, RunOptions()
    )
    result = results[0]
    assert result.error is None
    assert [c.label for c in result.checks] == [
        "typed",
        "invariant:cursor_row",
        "invariant:cursor_col",
        "invariant:no_leftover_modal",
        "invariant:no_crash",
        "invariant:theme_restored",
    ]
    assert all(c.invariant for c in result.checks[1:])
    assert all(c.ok for c in result.checks)
    assert result.fail_count == 0


def test_run_scenarios_skips_the_sweep_when_invariants_are_disabled(
    tmp_path: Path,
) -> None:
    results = run_scenarios(
        [Scenario("invariant_tidy", _tidy_scenario)],
        tmp_path,
        RunOptions(invariants=False),
    )
    assert [c.label for c in results[0].checks] == ["typed"]


# --- the invariant sweep: the failing direction ------------------------------


class _BlankScreen(Screen[None]):
    """A screen that is never mounted, standing in for a forgotten modal."""

    @override
    def compose(self) -> ComposeResult:
        return []


async def _leftover_modal_scenario(tmp: Path) -> ScenarioResult:
    """Refill the screen stack so a modal outlives the run."""
    app = new_app(target=tmp / "notes.txt")
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
    # run_test() tears the app down and empties the stack, and no public API can
    # push a screen onto a stopped app, so the leftover modal is reproduced by
    # refilling the private stack -- the state the invariant is meant to catch.
    # cast(): getattr() returns Any and neither private field is annotated.
    stacks = cast("dict[str, list[Screen[Any]]]", getattr(app, "_screen_stacks"))
    mode = cast(str, getattr(app, "_current_mode"))
    stacks[mode].extend([_BlankScreen(), _BlankScreen()])
    return ScenarioResult("invariant_modal")


def test_invariant_sweep_fails_a_scenario_that_leaves_a_modal_open(
    tmp_path: Path,
) -> None:
    results = run_scenarios(
        [Scenario("invariant_modal", _leftover_modal_scenario)],
        tmp_path,
        RunOptions(),
    )
    result = results[0]
    assert result.error is None
    modal = next(c for c in result.checks if c.label == "invariant:no_leftover_modal")
    assert modal.invariant is True
    assert modal.ok is False
    assert result.fail_count == 1


async def _illegal_cursor_scenario(tmp: Path) -> ScenarioResult:
    """Park the cursor past the last line, an impossible editor state."""
    app = new_app(target=tmp / "notes.txt")
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        app.editor.session.buffer.cursor = (99, 0)
    return ScenarioResult("invariant_cursor")


def test_invariant_sweep_fails_a_scenario_that_leaves_the_cursor_out_of_range(
    tmp_path: Path,
) -> None:
    results = run_scenarios(
        [Scenario("invariant_cursor", _illegal_cursor_scenario)],
        tmp_path,
        RunOptions(),
    )
    result = results[0]
    assert result.error is None
    assert {c.label for c in result.failed} == {
        "invariant:cursor_row",
        "invariant:cursor_col",
    }
    assert all(c.invariant for c in result.failed)


# --- scenario registry guards ------------------------------------------------


def test_scenario_registry_names_are_unique() -> None:
    names = [s.name for s in SCENARIOS]
    duplicates = sorted({n for n in names if names.count(n) > 1})
    assert duplicates == []


def test_scenario_registry_tags_are_declared_in_harness_tags() -> None:
    undeclared = sorted(
        f"{s.name}:{tag}"
        for s in SCENARIOS
        for tag in set(s.tags) - set(TAGS)
    )
    assert undeclared == []


def test_scenario_registry_runs_are_coroutine_functions() -> None:
    not_async = sorted(
        s.name for s in SCENARIOS if not inspect.iscoroutinefunction(s.run)
    )
    assert not_async == []


def test_scenario_registry_runs_are_documented() -> None:
    undocumented = sorted(
        s.name for s in SCENARIOS if not (s.run.__doc__ or "").strip()
    )
    assert undocumented == []


def test_scenario_registry_primary_tag_is_always_a_declared_tag() -> None:
    # primary_tag drives the report grouping, so an undeclared first tag would
    # create a report group the --tag filter can never select.
    stray = sorted(
        {s.primary_tag for s in SCENARIOS if s.tags} - set(TAGS)
    )
    assert stray == []
