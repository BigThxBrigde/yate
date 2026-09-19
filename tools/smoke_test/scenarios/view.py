"""Command line, palette, theme and status-bar scenarios (tag: ``view``)."""

from __future__ import annotations

from pathlib import Path

from ..harness import Check, Scenario, ScenarioResult, new_app, snapshot_svg
from ._base import message_text, run_command, type_text
from yate.editor_view import theme

__all__ = ["SCENARIOS"]


async def _command_palette_run(tmp: Path) -> ScenarioResult:
    """alt+shift+p opens the palette and runs the picked command."""
    app = new_app(target=tmp / "a.txt")
    checks: list[Check] = []
    async with app.run_test(size=(110, 32)) as pilot:
        await pilot.pause()
        await pilot.press("alt+shift+p")
        await pilot.pause()
        checks.append(Check("palette_open", 2, len(app.screen_stack)))
        await type_text(pilot, "vim")
        await pilot.press("enter")
        await pilot.pause()
        checks.append(Check("palette_closed", 1, len(app.screen_stack)))
        checks.append(Check("ran_command", "vim", app.keymap_name))
        await run_command(pilot, "vsc")
        checks.append(Check("restored", "vsc", app.keymap_name))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("command_palette_run", checks, rows)


async def _theme_switch_invalid(tmp: Path) -> ScenarioResult:
    """:theme lists, :theme <bad> warns and never switches."""
    app = new_app(target=tmp / "a.txt")
    checks: list[Check] = []
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        checks.append(Check("default_theme", "mocha", theme.active().name))
        await run_command(pilot, "theme")
        checks.append(Check("unchanged_after_list", "mocha", theme.active().name))
        checks.append(Check("listed", True, "available" in message_text(app)))
        await run_command(pilot, "theme nope")
        checks.append(Check("unchanged_after_bad", "mocha", theme.active().name))
        checks.append(Check("warned", True, "unknown theme" in message_text(app)))
        await run_command(pilot, "theme latte")
        checks.append(Check("switched", "latte", theme.active().name))
        await run_command(pilot, "theme mocha")
        checks.append(Check("restored", "mocha", theme.active().name))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("theme_switch_invalid", checks, rows)


async def _command_history_recall(tmp: Path) -> ScenarioResult:
    """The ex command line remembers what was typed (up arrow)."""
    app = new_app(target=tmp / "a.txt")
    checks: list[Check] = []
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await run_command(pilot, "help")
        checks.append(Check("help_open", 2, len(app.screen_stack)))
        await pilot.press("q")
        await pilot.pause()
        checks.append(Check("help_closed", 1, len(app.screen_stack)))
        await pilot.press("f5")
        await pilot.pause()
        await pilot.press("up")
        await pilot.pause()
        bar = app.prompt_bar
        checks.append(Check("recalled", "help", bar.input.value if bar else None))
        await pilot.press("escape")
        await pilot.pause()
        checks.append(Check("cancelled", None,
                            bar.active_mode if bar else None))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("command_history_recall", checks, rows)


async def _manual_changelog_modals(tmp: Path) -> ScenarioResult:
    """F8 (manual) and :changelog both open dismissible overlays."""
    app = new_app(target=tmp / "a.txt")
    checks: list[Check] = []
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await pilot.press("f8")
        await pilot.pause()
        checks.append(Check("manual_open", 2, len(app.screen_stack)))
        await pilot.press("q")
        await pilot.pause()
        checks.append(Check("manual_closed", 1, len(app.screen_stack)))
        await run_command(pilot, "changelog")
        checks.append(Check("changelog_open", 2, len(app.screen_stack)))
        await pilot.press("q")
        await pilot.pause()
        checks.append(Check("changelog_closed", 1, len(app.screen_stack)))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("manual_changelog_modals", checks, rows)


async def _set_options_matrix(tmp: Path) -> ScenarioResult:
    """:set applies known options and rejects unknown ones."""
    app = new_app(target=tmp / "a.txt")
    checks: list[Check] = []
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await run_command(pilot, "set keymap=vim")
        checks.append(Check("keymap", "vim", app.keymap_name))
        await run_command(pilot, "set keymap=nope")
        checks.append(Check("keymap_kept", "vim", app.keymap_name))
        checks.append(Check("keymap_warned", True,
                            "unknown keymap" in message_text(app)))
        height_before = app.config.terminal_height
        await run_command(pilot, "set terminal_height=99")
        checks.append(Check("height_kept", height_before, app.config.terminal_height))
        await run_command(pilot, "set show_hidden=on")
        checks.append(Check("show_hidden", True, app.workspace.show_hidden))
        await run_command(pilot, "set bogus=1")
        checks.append(Check("option_warned", True,
                            "unknown option" in message_text(app)))
        await run_command(pilot, "set theme=latte")
        checks.append(Check("theme", "latte", theme.active().name))
        await run_command(pilot, "set theme=mocha")
        await run_command(pilot, "set keymap=vsc")
        checks.append(Check("keymap_restored", "vsc", app.keymap_name))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("set_options_matrix", checks, rows)


async def _status_mode_label(tmp: Path) -> ScenarioResult:
    """The status bar chip follows the keymap / vim mode."""
    app = new_app(target=tmp / "a.txt")
    checks: list[Check] = []
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        checks.append(Check("vsc_chip", "VSC", app.mode_label()[0]))
        await run_command(pilot, "vim")
        checks.append(Check("normal_chip", "NORMAL", app.mode_label()[0]))
        await pilot.press("i")
        await pilot.pause()
        checks.append(Check("insert_chip", "INSERT", app.mode_label()[0]))
        await pilot.press("escape")
        await pilot.pause()
        checks.append(Check("back_to_normal", "NORMAL", app.mode_label()[0]))
        await run_command(pilot, "vsc")
        checks.append(Check("back_to_vsc", "VSC", app.mode_label()[0]))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("status_mode_label", checks, rows)


SCENARIOS: list[Scenario] = [
    Scenario("command_palette_run", _command_palette_run, ("view",)),
    Scenario("theme_switch_invalid", _theme_switch_invalid, ("view",)),
    Scenario("command_history_recall", _command_history_recall, ("view",)),
    Scenario("manual_changelog_modals", _manual_changelog_modals, ("view",)),
    Scenario("set_options_matrix", _set_options_matrix, ("view",)),
    Scenario("status_mode_label", _status_mode_label, ("view",)),
]
