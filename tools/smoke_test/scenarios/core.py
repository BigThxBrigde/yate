"""The five original smoke scenarios (baseline behaviour)."""

from __future__ import annotations

from pathlib import Path

from ..harness import Check, Scenario, ScenarioResult, new_app, snapshot_svg
from ._base import run_command, type_text
from yate.editor_view import theme

__all__ = ["SCENARIOS"]


async def _type_save_find(tmp: Path) -> ScenarioResult:
    """Type text, save with ctrl+s, then find a substring."""
    target = tmp / "notes.txt"
    app = new_app(target=target)
    checks: list[Check] = []
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await pilot.press("h", "e", "l", "l", "o")
        await pilot.pause()
        checks.append(Check("buffer[0]", "hello", app.buffer.lines[0]))
        checks.append(Check("modified", True, app.doc.modified))
        await pilot.press("ctrl+s")
        await pilot.pause()
        checks.append(Check("file_exists", True, target.exists()))
        checks.append(Check("file_content", "hello", target.read_text(encoding="utf-8")))
        checks.append(Check("clean", False, app.doc.modified))
        await pilot.press("ctrl+f")
        await pilot.pause()
        mode = app.prompt_bar.active_mode if app.prompt_bar else None
        checks.append(Check("find_mode", "find", mode))
        await pilot.press("l", "l")
        await pilot.press("enter")
        await pilot.pause()
        checks.append(Check("search_query", "ll", app.search.query))
        checks.append(Check("search_matches>=1", True, len(app.search.matches) >= 1))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("type_save_find", checks, rows)


async def _file_palette(tmp: Path) -> ScenarioResult:
    """Open a file via the ctrl+p fuzzy palette."""
    (tmp / "notes.txt").write_text("hello\n", encoding="utf-8")
    (tmp / "todo.txt").write_text("buy milk\n", encoding="utf-8")
    app = new_app(target=tmp)
    checks: list[Check] = []
    async with app.run_test(size=(110, 32)) as pilot:
        await pilot.pause()
        await pilot.press("ctrl+p")
        await pilot.pause()
        checks.append(Check("palette_open", 2, len(app.screen_stack)))
        await type_text(pilot, "note")
        await pilot.press("enter")
        await pilot.pause()
        checks.append(Check("doc.name", "notes.txt", app.doc.name))
        checks.append(Check("palette_closed", 1, len(app.screen_stack)))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("file_palette", checks, rows)


async def _keymap_toggle(tmp: Path) -> ScenarioResult:
    """Toggle the keymap between vsc and vim via ctrl+/."""
    app = new_app(target=tmp / "scratch.txt")
    checks: list[Check] = []
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        checks.append(Check("default_keymap", "vsc", app.keymap_name))
        await pilot.press("ctrl+/")
        await pilot.pause()
        checks.append(Check("toggled_keymap", "vim", app.keymap_name))
        await pilot.press("ctrl+/")
        await pilot.pause()
        checks.append(Check("back_to_vsc", "vsc", app.keymap_name))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("keymap_toggle", checks, rows)


async def _theme_switch(tmp: Path) -> ScenarioResult:
    """Switch theme via :theme latte, then restore mocha."""
    app = new_app(target=tmp / "scratch.txt")
    checks: list[Check] = []
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        checks.append(Check("default_theme", "mocha", theme.active().name))
        await run_command(pilot, "theme latte")
        checks.append(Check("latte_theme", "latte", theme.active().name))
        theme.set_theme("mocha")
        await pilot.pause()
        checks.append(Check("restored_mocha", "mocha", theme.active().name))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("theme_switch", checks, rows)


async def _help_modal(tmp: Path) -> ScenarioResult:
    """Open the :help manual modal and close it with q."""
    app = new_app(target=tmp / "scratch.txt")
    checks: list[Check] = []
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await run_command(pilot, "help")
        checks.append(Check("modal_open", 2, len(app.screen_stack)))
        await pilot.press("q")
        await pilot.pause()
        checks.append(Check("modal_closed", 1, len(app.screen_stack)))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("help_modal", checks, rows)


SCENARIOS: list[Scenario] = [
    Scenario("type_save_find", _type_save_find, ("edit", "search", "files")),
    Scenario("file_palette", _file_palette, ("files", "command")),
    Scenario("keymap_toggle", _keymap_toggle, ("view",)),
    Scenario("theme_switch", _theme_switch, ("view",)),
    Scenario("help_modal", _help_modal, ("command",)),
]
