"""Integration scenarios: shell, terminal, LSP-free diagnostics, big files.

Everything that talks to the outside world (a shell process, a PTY) is
marked ``slow`` so ``--skip-slow`` keeps the suite hermetic and fast.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..harness import Check, Scenario, ScenarioResult, new_app, snapshot_svg
from ._base import message_text, run_command, type_text, wait_until

__all__ = ["SCENARIOS"]


async def _shell_command_output(tmp: Path) -> ScenarioResult:
    """F2 runs a shell command and shows its output in an overlay."""
    app = new_app(target=tmp / "a.txt")
    checks: list[Check] = []
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await pilot.press("f2")
        await pilot.pause()
        bar = app.prompt_bar
        checks.append(Check("shell_mode", "shell",
                            bar.active_mode if bar else None))
        await type_text(pilot, "echo smoke-ok")
        await pilot.press("enter")
        await wait_until(pilot, lambda: len(app.screen_stack) == 2)
        checks.append(Check("overlay_open", 2, len(app.screen_stack)))
        screen: Any = app.screen
        checks.append(Check("exit_code", 0, screen.exit_code))
        checks.append(Check("captured", True, "smoke-ok" in screen.output_text))
        await pilot.press("q")
        await pilot.pause()
        checks.append(Check("overlay_closed", 1, len(app.screen_stack)))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("shell_command_output", checks, rows)


async def _terminal_panel_toggle(tmp: Path) -> ScenarioResult:
    """Ctrl+` shows and hides the bottom terminal panel.

    Once the panel is visible it owns the keyboard (typing goes to the
    shell), so it can only be closed with the toggle key -- the ``:term``
    / ``:termclose`` commands are reachable while the editor has focus.
    """
    app = new_app(target=tmp / "a.txt")
    checks: list[Check] = []
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        panel = app.terminal_panel
        assert panel is not None
        checks.append(Check("hidden_at_start", False, panel.display))
        await pilot.press("ctrl+`")
        await pilot.pause()
        checks.append(Check("shown", True, panel.display))
        await pilot.press("ctrl+`")
        await pilot.pause()
        checks.append(Check("hidden_by_toggle", False, panel.display))
        await run_command(pilot, "term")
        await pilot.pause()
        checks.append(Check("shown_by_command", True, panel.display))
        await pilot.press("ctrl+`")
        await pilot.pause()
        checks.append(Check("hidden_again", False, panel.display))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("terminal_panel_toggle", checks, rows)


async def _diagnostics_empty_state(tmp: Path) -> ScenarioResult:
    """:diagnostics reports "no diagnostics" instead of opening a screen."""
    app = new_app(target=tmp / "a.py")
    checks: list[Check] = []
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await run_command(pilot, "diagnostics")
        checks.append(Check("no_overlay", 1, len(app.screen_stack)))
        checks.append(Check("message", True, "no diagnostics" in message_text(app)))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("diagnostics_empty_state", checks, rows)


async def _large_file_scroll(tmp: Path) -> ScenarioResult:
    """A 2000 line file opens at the top and scrolls with page down."""
    target = tmp / "big.txt"
    target.write_text("\n".join(f"line {i}" for i in range(2000)), encoding="utf-8")
    app = new_app(target=target)
    checks: list[Check] = []
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        view = app.panes.active_view if app.panes else None
        assert view is not None
        checks.append(Check("line_count", 2000, app.buffer.line_count))
        checks.append(Check("top_at_start", 0, view.scroll_offset.y))
        await pilot.press("pagedown")
        await pilot.pause()
        checks.append(Check("scrolled", True, view.scroll_offset.y > 0))
        await run_command(pilot, "1500")
        checks.append(Check("goto_row", 1499, app.buffer.cursor[0]))
        checks.append(Check("followed", True, view.scroll_offset.y > 0))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("large_file_scroll", checks, rows)


SCENARIOS: list[Scenario] = [
    Scenario("shell_command_output", _shell_command_output, ("integration",),
             slow=True),
    Scenario("terminal_panel_toggle", _terminal_panel_toggle, ("integration",),
             slow=True),
    Scenario("diagnostics_empty_state", _diagnostics_empty_state,
             ("integration",)),
    Scenario("large_file_scroll", _large_file_scroll, ("integration",)),
]
