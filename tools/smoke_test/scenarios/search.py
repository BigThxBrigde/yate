"""Search, replace and go-to-line scenarios (tag: ``search``)."""

from __future__ import annotations

from pathlib import Path

from ..harness import Check, Scenario, ScenarioResult, new_app, snapshot_svg
from ._base import goto, run_command, type_text

__all__ = ["SCENARIOS"]


async def _find_next_prev_wrap(tmp: Path) -> ScenarioResult:
    """ctrl+f, f3 cycles through the matches and wraps around."""
    target = tmp / "find.txt"
    target.write_text("one two one", encoding="utf-8")
    app = new_app(target=target)
    checks: list[Check] = []
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await pilot.press("ctrl+f")
        await pilot.pause()
        checks.append(Check("find_mode", "find",
                            app.prompt_bar.active_mode if app.prompt_bar else None))
        await type_text(pilot, "one")
        await pilot.press("enter")
        await pilot.pause()
        checks.append(Check("query", "one", app.search.query))
        checks.append(Check("match_count", 2, len(app.search.matches)))
        checks.append(Check("first_index", 0, app.search.index))
        await pilot.press("f3")
        await pilot.pause()
        checks.append(Check("next_index", 1, app.search.index))
        await pilot.press("f3")
        await pilot.pause()
        checks.append(Check("wrapped_index", 0, app.search.index))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("find_next_prev_wrap", checks, rows)


async def _replace_single_all(tmp: Path) -> ScenarioResult:
    """f4 takes the find string first, the replacement second."""
    target = tmp / "replace.txt"
    target.write_text("cat cat cat", encoding="utf-8")
    app = new_app(target=target)
    checks: list[Check] = []
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await pilot.press("f4")
        await pilot.pause()
        checks.append(Check("replace_find_mode", "replace_find",
                            app.prompt_bar.active_mode if app.prompt_bar else None))
        await type_text(pilot, "cat")
        await pilot.press("enter")
        await pilot.pause()
        checks.append(Check("replace_with_mode", "replace_with",
                            app.prompt_bar.active_mode if app.prompt_bar else None))
        await type_text(pilot, "dog")
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        checks.append(Check("replaced", "dog dog dog", app.buffer.lines[0]))
        checks.append(Check("query_kept", "cat", app.search.query))
        checks.append(Check("no_matches_left", 0, len(app.search.matches)))
        checks.append(Check("modified", True, app.doc.modified))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("replace_single_all", checks, rows)


async def _goto_line_two_ways(tmp: Path) -> ScenarioResult:
    """ctrl+g and the bare ``:42`` both jump to a 1-based line."""
    target = tmp / "lines.txt"
    target.write_text("l1\nl2\nl3\nl4\nl5", encoding="utf-8")
    app = new_app(target=target)
    checks: list[Check] = []
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await goto(pilot, "4")
        checks.append(Check("goto_prompt_row", 3, app.buffer.cursor[0]))
        await run_command(pilot, "2")
        checks.append(Check("colon_row", 1, app.buffer.cursor[0]))
        await run_command(pilot, "+2")
        checks.append(Check("relative_row", 3, app.buffer.cursor[0]))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("goto_line_two_ways", checks, rows)


async def _find_backward(tmp: Path) -> ScenarioResult:
    """``?`` (vim) searches backwards from the cursor."""
    target = tmp / "back.txt"
    target.write_text("one\ntwo\none", encoding="utf-8")
    app = new_app(target=target)
    checks: list[Check] = []
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await run_command(pilot, "vim")
        await pilot.press("?")
        await pilot.pause()
        checks.append(Check("find_back_mode", "find_back",
                            app.prompt_bar.active_mode if app.prompt_bar else None))
        await type_text(pilot, "one")
        await pilot.press("enter")
        await pilot.pause()
        checks.append(Check("query", "one", app.search.query))
        checks.append(Check("match_count", 2, len(app.search.matches)))
        checks.append(Check("index_from_end", 1, app.search.index))
        checks.append(Check("cursor_row", 2, app.buffer.cursor[0]))
        await run_command(pilot, "vsc")
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("find_backward", checks, rows)


SCENARIOS: list[Scenario] = [
    Scenario("find_next_prev_wrap", _find_next_prev_wrap, ("search",)),
    Scenario("replace_single_all", _replace_single_all, ("search",)),
    Scenario("goto_line_two_ways", _goto_line_two_ways, ("search",)),
    Scenario("find_backward", _find_backward, ("search",)),
]
