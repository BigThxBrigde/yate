"""Command completion smoke scenario (tag: ``command``).

``command_completion`` drives the multi-match command-name branch of
``CommandInput._do_tab_completion`` (yate/editor_view/commandline.py):
the first tab extends the typed prefix to the longest common prefix and
lists the remaining candidates on the message slot
(``OWNER_CANDIDATES``), the second tab applies the first candidate of
the round.  The existing ``prompt_tab_completion`` guard covers the
single-match and the ``:set`` value / path branches; this scenario
covers the multi-match command-name round end to end.
"""

from __future__ import annotations

from pathlib import Path

from yate.editor_view.commandline import OWNER_CANDIDATES

from tools.smoke_test.harness import Check, Scenario, ScenarioResult, new_app, snapshot_svg
from tools.smoke_test.scenarios._base import message_text, type_text

__all__ = ["SCENARIOS"]


async def _command_completion(tmp: Path) -> ScenarioResult:
    """F5 + "ter" + tab: common-prefix extension plus the candidate list."""
    app = new_app(target=tmp / "scratch.txt")
    checks: list[Check] = []
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        bar = app.editor.prompt_bar
        assert bar is not None
        await pilot.press("f5")
        await pilot.pause()
        checks.append(Check("prompt_open", "command", bar.active_mode))
        await type_text(pilot, "ter")
        await pilot.press("tab")
        await pilot.pause()
        # "ter" matches term / termclose / terminal; their common prefix
        # "term" is longer than what was typed, so it is applied and the
        # remaining candidates own the message slot.
        checks.append(Check("common_prefix_applied", "term", bar.input.value))
        checks.append(Check("candidates_shown", OWNER_CANDIDATES, bar.owner))
        checks.append(Check("candidates_text", True,
                            "termclose" in message_text(app)
                            and "terminal" in message_text(app)))
        rows = snapshot_svg(app, tmp)
        await pilot.press("tab")
        await pilot.pause()
        # The applied prefix is not one of the listed candidates, so this
        # tab applies the first candidate of the round ("term") and drops
        # the candidate string from the message slot.
        checks.append(Check("first_candidate_applied", "term", bar.input.value))
        checks.append(Check("candidates_hidden", False,
                            bar.owner == OWNER_CANDIDATES))
        await pilot.press("escape")
        await pilot.pause()
        checks.append(Check("cancelled", None, bar.active_mode))
    return ScenarioResult("command_completion", checks, rows)


SCENARIOS: list[Scenario] = [
    Scenario("command_completion", _command_completion, ("command",)),
]
