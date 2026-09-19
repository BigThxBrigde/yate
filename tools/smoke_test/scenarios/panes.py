"""Split pane scenarios (tag: ``panes``)."""

from __future__ import annotations

from pathlib import Path

from ..harness import Check, Scenario, ScenarioResult, new_app, snapshot_svg
from ._base import message_text, run_command, wait_until

__all__ = ["SCENARIOS"]


async def _split_vs_sp_only(tmp: Path) -> ScenarioResult:
    """:vs / :sp grow the pane tree, :only collapses it again."""
    app = new_app(target=tmp / "a.txt")
    checks: list[Check] = []
    async with app.run_test(size=(110, 32)) as pilot:
        await pilot.pause()
        panes = app.panes
        assert panes is not None
        checks.append(Check("one_pane", 1, panes.leaf_count))
        await run_command(pilot, "vs")
        await wait_until(pilot, lambda: panes.leaf_count == 2)
        checks.append(Check("vsplit", 2, panes.leaf_count))
        await run_command(pilot, "split")
        await wait_until(pilot, lambda: panes.leaf_count == 3)
        checks.append(Check("hsplit", 3, panes.leaf_count))
        await run_command(pilot, "only")
        await wait_until(pilot, lambda: panes.leaf_count == 1)
        checks.append(Check("only", 1, panes.leaf_count))
        await run_command(pilot, "close")
        await pilot.pause()
        checks.append(Check("close_last_is_noop", 1, panes.leaf_count))
        checks.append(Check("warned", True, "only one pane" in message_text(app)))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("split_vs_sp_only", checks, rows)


async def _split_with_file(tmp: Path) -> ScenarioResult:
    """:vs <file> splits and opens that file in the new pane."""
    (tmp / "a.txt").write_text("a\n", encoding="utf-8")
    (tmp / "b.txt").write_text("b\n", encoding="utf-8")
    app = new_app(target=tmp / "a.txt")
    checks: list[Check] = []
    async with app.run_test(size=(110, 32)) as pilot:
        await pilot.pause()
        panes = app.panes
        assert panes is not None
        await run_command(pilot, "vs b.txt")
        await wait_until(pilot, lambda: panes.leaf_count == 2)
        checks.append(Check("two_panes", 2, panes.leaf_count))
        checks.append(Check("new_pane_doc", "b.txt", app.doc.name))
        checks.append(Check("two_docs", 2, len(app.docs)))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("split_with_file", checks, rows)


async def _pane_focus_window_keys(tmp: Path) -> ScenarioResult:
    """vim ``ctrl+w h`` moves the focus to the pane on the left."""
    app = new_app(target=tmp / "a.txt")
    checks: list[Check] = []
    async with app.run_test(size=(110, 32)) as pilot:
        await pilot.pause()
        panes = app.panes
        assert panes is not None
        await run_command(pilot, "vim")
        await run_command(pilot, "vs")
        await wait_until(pilot, lambda: panes.leaf_count == 2)
        focused_after_split = panes.active.id
        await pilot.press("ctrl+w")
        await pilot.pause()
        checks.append(Check("chord_armed", True, app.window_pending))
        await pilot.press("h")
        await pilot.pause()
        checks.append(Check("chord_consumed", False, app.window_pending))
        checks.append(Check("focus_moved", True,
                            panes.active.id != focused_after_split))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("pane_focus_window_keys", checks, rows)


SCENARIOS: list[Scenario] = [
    Scenario("split_vs_sp_only", _split_vs_sp_only, ("panes",)),
    Scenario("split_with_file", _split_with_file, ("panes",)),
    Scenario("pane_focus_window_keys", _pane_focus_window_keys, ("panes",)),
]
