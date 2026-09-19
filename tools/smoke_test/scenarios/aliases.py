"""Alias / long-tail coverage (tags: ``edit``, ``command``).

``--coverage`` showed the suite exercising the main paths but leaving the
command aliases and a few rarely bound actions untouched.  These two
scenarios walk them in one pass each so the coverage number stays honest.
"""

from __future__ import annotations

from pathlib import Path

from ..harness import Check, Scenario, ScenarioResult, new_app, snapshot_svg
from ._base import run_command
from yate.editor_view import theme

__all__ = ["SCENARIOS"]


async def _action_alias_roundup(tmp: Path) -> ScenarioResult:
    """delete / alt+d / ctrl+shift+arrow / shift+arrow bindings."""
    target = tmp / "act.txt"
    target.write_text("hello world", encoding="utf-8")
    app = new_app(target=target)
    checks: list[Check] = []
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        # delete_forward drops the character under the cursor
        await pilot.press("delete")
        await pilot.pause()
        checks.append(Check("delete_forward", "ello world", app.buffer.lines[0]))
        # alt+d deletes the rest of the word
        await pilot.press("alt+d")
        await pilot.pause()
        checks.append(Check("delete_word_fwd", " world", app.buffer.lines[0]))
        # ctrl+shift+right selects one word to the right
        await pilot.press("ctrl+shift+right")
        await pilot.pause()
        checks.append(Check("select_word_right", True, app.buffer.has_selection()))
        await pilot.press("escape")
        await pilot.pause()
        # shift+up / shift+down extend the selection by a line
        await pilot.press("enter")
        await pilot.pause()
        checks.append(Check("two_lines", 2, app.buffer.line_count))
        await pilot.press("shift+up")
        await pilot.pause()
        checks.append(Check("select_up", True, app.buffer.has_selection()))
        await pilot.press("escape")
        await pilot.pause()
        await pilot.press("shift+down")
        await pilot.pause()
        checks.append(Check("select_down", True, app.buffer.has_selection()))
        await pilot.press("escape")
        await pilot.pause()
        checks.append(Check("cleared", False, app.buffer.has_selection()))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("action_alias_roundup", checks, rows)


async def _command_alias_roundup(tmp: Path) -> ScenarioResult:
    """:enew / :bd / :files / :palette / :e / :colorscheme / :cl / :welcome."""
    app = new_app(target=tmp / "a.txt")
    checks: list[Check] = []
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await run_command(pilot, "enew")
        checks.append(Check("enew", 2, len(app.docs)))
        await run_command(pilot, "bd")
        checks.append(Check("bd", 1, len(app.docs)))
        await run_command(pilot, "files")
        checks.append(Check("files_palette", 2, len(app.screen_stack)))
        await pilot.press("escape")
        await pilot.pause()
        checks.append(Check("files_closed", 1, len(app.screen_stack)))
        await run_command(pilot, "palette")
        checks.append(Check("command_palette", 2, len(app.screen_stack)))
        await pilot.press("escape")
        await pilot.pause()
        checks.append(Check("palette_closed", 1, len(app.screen_stack)))
        await run_command(pilot, "e")
        bar = app.prompt_bar
        checks.append(Check("e_prompts", "open", bar.active_mode if bar else None))
        await pilot.press("escape")
        await pilot.pause()
        await run_command(pilot, "colorscheme latte")
        checks.append(Check("colorscheme", "latte", theme.active().name))
        await run_command(pilot, "colorscheme mocha")
        checks.append(Check("colorscheme_back", "mocha", theme.active().name))
        await run_command(pilot, "cl")
        checks.append(Check("cl_noop", 1, app.panes.leaf_count
                            if app.panes else 0))
        await run_command(pilot, "welcome")
        checks.append(Check("welcome", True, app.welcome_visible))
        checks.append(Check("no_crash", None, app.return_code))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("command_alias_roundup", checks, rows)


SCENARIOS: list[Scenario] = [
    Scenario("action_alias_roundup", _action_alias_roundup, ("edit",)),
    Scenario("command_alias_roundup", _command_alias_roundup, ("command",)),
]
