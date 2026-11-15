"""Which-key smoke scenarios (tag: ``view``).

Three scenarios cover the panel's visible states:

* ``which_key_toggle``       -- F9 pins / unpins the full keymap sheet
  (``toggle_whichkey`` -> ``WhichKeyFlows.toggle``);
* ``which_key_ctrl_w_chord`` -- the vim ``ctrl+w`` chord arms the window
  pending state and the panel lists the chord table rows until the chord
  is cancelled with any other key;
* ``which_key_auto_off_manual_toggle`` -- with ``YateConfig(which_key_auto=False)``
  the auto popup stays off (pending prefix / chord do not push the panel)
  while the pinned F9 toggle still works.

Assertions read the app state (``which_key_panel.display`` /
``border_title``, ``window_flows.window_pending``); the snapshots only
freeze the rendered rows into the baseline.
"""

from __future__ import annotations

from pathlib import Path

from tools.smoke_test.harness import Check, Scenario, ScenarioResult, new_app, snapshot_svg
from tools.smoke_test.scenarios._base import run_command
from yate.config import YateConfig

__all__ = ["SCENARIOS"]


async def _which_key_toggle(tmp: Path) -> ScenarioResult:
    """F9 pins the full keymap sheet; F9 again hides the panel."""
    app = new_app(target=tmp / "scratch.txt")
    checks: list[Check] = []
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        panel = app.editor.which_key_panel
        checks.append(Check("starts_hidden", False, panel.display))
        await pilot.press("f9")
        await pilot.pause()
        # Pinned sheet: shown under the active keymap's name (vsc default).
        checks.append(Check("pinned_visible", True, panel.display))
        checks.append(Check("pinned_title", "vsc", panel.border_title))
        rows = snapshot_svg(app, tmp)
        await pilot.press("f9")
        await pilot.pause()
        checks.append(Check("unpinned_hidden", False, panel.display))
        checks.append(Check("unpinned_title", "", panel.border_title))
    return ScenarioResult("which_key_toggle", checks, rows)


async def _which_key_ctrl_w_chord(tmp: Path) -> ScenarioResult:
    """vim ctrl+w arms the window chord; the panel lists the chord table."""
    app = new_app(target=tmp / "scratch.txt")
    checks: list[Check] = []
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        # The ctrl+w chord only arms on the vim keymap (window_flows
        # checks keymaps.name == "vim"), so switch the way a user does.
        await run_command(pilot, "vim")
        checks.append(Check("in_vim", "vim", app.editor.keymaps.name))
        panel = app.editor.which_key_panel
        checks.append(Check("starts_hidden", False, panel.display))
        await pilot.press("ctrl+w")
        await pilot.pause()
        checks.append(Check("chord_pending", True,
                            app.editor.window_flows.window_pending))
        checks.append(Check("chord_visible", True, panel.display))
        checks.append(Check("chord_title", "ctrl+w", panel.border_title))
        rows = snapshot_svg(app, tmp)
        # Any key outside the chord table cancels the pending chord and
        # the panel hides again (escape is a no-op in NORMAL mode).
        await pilot.press("escape")
        await pilot.pause()
        checks.append(Check("chord_cancelled", False,
                            app.editor.window_flows.window_pending))
        checks.append(Check("hidden_after_cancel", False, panel.display))
    return ScenarioResult("which_key_ctrl_w_chord", checks, rows)


async def _which_key_auto_off_manual_toggle(tmp: Path) -> ScenarioResult:
    """Auto popup off plus F9 pin still works; prefixes never push the panel."""
    app = new_app(target=tmp / "scratch.txt",
                  config=YateConfig(which_key_auto=False))
    checks: list[Check] = []
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await run_command(pilot, "vim")
        panel = app.editor.which_key_panel
        checks.append(Check("in_vim", "vim", app.editor.keymaps.name))
        checks.append(Check("starts_hidden", False, panel.display))
        # A pending vim prefix must not trigger the auto popup.
        await pilot.press("d")
        await pilot.pause()
        checks.append(Check("prefix_pending", "d",
                            app.editor.keymaps.active.pending_prefix()))
        checks.append(Check("auto_hidden_on_prefix", False, panel.display))
        # Clean up the pending prefix; no assertion on escape's own effect.
        await pilot.press("escape")
        await pilot.pause()
        # The ctrl+w chord still completes without the panel popping up.
        await pilot.press("ctrl+w")
        await pilot.pause()
        checks.append(Check("chord_pending", True,
                            app.editor.window_flows.window_pending))
        checks.append(Check("auto_hidden_on_chord", False, panel.display))
        # Cancel the chord like the existing chord scenario does.
        await pilot.press("escape")
        await pilot.pause()
        checks.append(Check("chord_cancelled", False,
                            app.editor.window_flows.window_pending))
        # F9 pins the sheet manually even with auto popup disabled.
        await pilot.press("f9")
        await pilot.pause()
        checks.append(Check("manual_pinned_visible", True, panel.display))
        checks.append(Check("manual_pinned_title", "vim", panel.border_title))
        # A pending prefix while pinned must not overwrite the pinned sheet.
        await pilot.press("g")
        await pilot.pause()
        checks.append(Check("pinned_not_overwritten", True, panel.display))
        checks.append(Check("pinned_title_still_vim", "vim", panel.border_title))
        # F9 again unpins; the auto popup stays off afterwards.
        await pilot.press("f9")
        await pilot.pause()
        checks.append(Check("manual_unpinned_hidden", False, panel.display))
        await pilot.press("g")
        await pilot.pause()
        checks.append(Check("no_auto_after_unpin", False, panel.display))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("which_key_auto_off_manual_toggle", checks, rows)


SCENARIOS: list[Scenario] = [
    Scenario("which_key_toggle", _which_key_toggle, ("view",)),
    Scenario("which_key_ctrl_w_chord", _which_key_ctrl_w_chord, ("view",)),
    Scenario("which_key_auto_off_manual_toggle",
             _which_key_auto_off_manual_toggle, ("view",)),
]
