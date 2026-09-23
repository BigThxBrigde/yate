"""Command line, palette, theme and status-bar scenarios (tag: ``view``)."""

from __future__ import annotations

import types
from pathlib import Path

from ..harness import Check, Scenario, ScenarioResult, new_app, snapshot_svg
from ._base import goto, message_text, run_command, type_text, wait_until
from yate.editor_view import theme
from yate.services import fonts

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
        checks.append(Check("ran_command", "vim", app.editor.keymaps.name))
        await run_command(pilot, "vsc")
        checks.append(Check("restored", "vsc", app.editor.keymaps.name))
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
        bar = app.editor.prompt_bar
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
        checks.append(Check("keymap", "vim", app.editor.keymaps.name))
        await run_command(pilot, "set keymap=nope")
        checks.append(Check("keymap_kept", "vim", app.editor.keymaps.name))
        checks.append(Check("keymap_warned", True,
                            "unknown keymap" in message_text(app)))
        height_before = app.editor.config.terminal_height
        await run_command(pilot, "set terminal_height=99")
        checks.append(Check("height_kept", height_before,
                            app.editor.config.terminal_height))
        await run_command(pilot, "set show_hidden=on")
        checks.append(Check("show_hidden", True, app.editor.workspace.show_hidden))
        await run_command(pilot, "set bogus=1")
        checks.append(Check("option_warned", True,
                            "unknown option" in message_text(app)))
        await run_command(pilot, "set theme=latte")
        checks.append(Check("theme", "latte", theme.active().name))
        await run_command(pilot, "set theme=mocha")
        await run_command(pilot, "set keymap=vsc")
        checks.append(Check("keymap_restored", "vsc", app.editor.keymaps.name))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("set_options_matrix", checks, rows)


async def _status_mode_label(tmp: Path) -> ScenarioResult:
    """The status bar chip follows the keymap / vim mode."""
    app = new_app(target=tmp / "a.txt")
    checks: list[Check] = []
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        checks.append(Check("vsc_chip", "VSC", app.editor.mode_label()[0]))
        await run_command(pilot, "vim")
        checks.append(Check("normal_chip", "NORMAL", app.editor.mode_label()[0]))
        await pilot.press("i")
        await pilot.pause()
        checks.append(Check("insert_chip", "INSERT", app.editor.mode_label()[0]))
        await pilot.press("escape")
        await pilot.pause()
        checks.append(Check("back_to_normal", "NORMAL", app.editor.mode_label()[0]))
        await run_command(pilot, "vsc")
        checks.append(Check("back_to_vsc", "VSC", app.editor.mode_label()[0]))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("status_mode_label", checks, rows)


async def _manual_command_langs(tmp: Path) -> ScenarioResult:
    """:manual (default en) and :manual zh open the manual overlay; q closes.

    F8 already opens the manual in ``manual_changelog_modals``; this scenario
    walks the *command* and both branches of ``_manual`` (the ``args or "en"``
    default and the ``zh`` argument).
    """
    app = new_app(target=tmp / "a.txt")
    checks: list[Check] = []
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await run_command(pilot, "manual")
        checks.append(Check("manual_default_open", 2, len(app.screen_stack)))
        await pilot.press("q")
        await pilot.pause()
        checks.append(Check("manual_default_closed", 1, len(app.screen_stack)))
        await run_command(pilot, "manual zh")
        checks.append(Check("manual_zh_open", 2, len(app.screen_stack)))
        await pilot.press("q")
        await pilot.pause()
        checks.append(Check("manual_zh_closed", 1, len(app.screen_stack)))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("view_manual_command", checks, rows)


async def _normal_command_alias(tmp: Path) -> ScenarioResult:
    """:normal is :vsc's alias and restores the vsc keymap after :vim."""
    app = new_app(target=tmp / "a.txt")
    checks: list[Check] = []
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await run_command(pilot, "vim")
        checks.append(Check("switched_to_vim", "vim", app.editor.keymaps.name))
        await run_command(pilot, "normal")
        checks.append(Check("normal_is_vsc", "vsc", app.editor.keymaps.name))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("view_normal_command", checks, rows)


async def _font_command_stub(tmp: Path) -> ScenarioResult:
    """:font reaches install_font() with the font service stubbed out.

    Real ``ensure_font`` performs registry / font-file installation, so the
    module attribute is swapped for a fake returning a ``SimpleNamespace``
    standing in for a FontStatus (``_font_command_async`` only reads
    ``detail`` / ``has_nerd_font``).  The original is restored in ``finally``.
    """
    detail = "smoke-stub: nerd font ready"
    app = new_app(target=tmp / "a.txt")
    checks: list[Check] = []
    original = fonts.ensure_font

    def _stub(*args: object, **kwargs: object) -> types.SimpleNamespace:
        return types.SimpleNamespace(detail=detail, has_nerd_font=True)

    setattr(fonts, "ensure_font", _stub)
    try:
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            await run_command(pilot, "font")
            landed = await wait_until(
                pilot, lambda: detail in message_text(app))
            checks.append(Check("font_worker_landed", True, landed))
            checks.append(Check("font_detail_shown", True,
                                detail in message_text(app)))
            rows = snapshot_svg(app, tmp)
    finally:
        setattr(fonts, "ensure_font", original)
    return ScenarioResult("view_font_command", checks, rows)


async def _page_up_key(tmp: Path) -> ScenarioResult:
    """vsc ``pageup`` runs the page_up action: the cursor moves up a page."""
    target = tmp / "big.txt"
    target.write_text(
        "\n".join(f"line {i}" for i in range(1, 2001)), encoding="utf-8"
    )
    app = new_app(target=target)
    checks: list[Check] = []
    async with app.run_test(size=(110, 32)) as pilot:
        await pilot.pause()
        await goto(pilot, "1000")
        buf = app.editor.session.buffer
        before = buf.row
        checks.append(Check("started_mid_file", 999, before))
        await pilot.press("pageup")
        await pilot.pause()
        checks.append(Check("page_up_moved_up", True, buf.row < before))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("view_page_up", checks, rows)


async def _page_half_scroll_vim(tmp: Path) -> ScenarioResult:
    """vim NORMAL ctrl+d / ctrl+u run page_half_down / page_half_up."""
    target = tmp / "big.txt"
    target.write_text(
        "\n".join(f"line {i}" for i in range(1, 2001)), encoding="utf-8"
    )
    app = new_app(target=target)
    checks: list[Check] = []
    async with app.run_test(size=(110, 32)) as pilot:
        await pilot.pause()
        await goto(pilot, "1000")
        await run_command(pilot, "vim")
        checks.append(Check("in_vim_normal", "vim", app.editor.keymaps.name))
        buf = app.editor.session.buffer
        before = buf.row
        await pilot.press("ctrl+d")
        await pilot.pause()
        after_down = buf.row
        checks.append(Check("half_down_moved_down", True, after_down > before))
        await pilot.press("ctrl+u")
        await pilot.pause()
        checks.append(Check("half_up_moved_up", True, buf.row < after_down))
        await run_command(pilot, "vsc")
        checks.append(Check("keymap_restored", "vsc", app.editor.keymaps.name))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("view_page_half_scroll", checks, rows)


async def _palette_actions(tmp: Path) -> ScenarioResult:
    """quick_open / command_palette actions open the palette overlays.

    The ctrl+p and alt+shift+p *keys* are intercepted by ``Editor.handle_key``
    (they call ``open_file_palette`` / ``open_command_palette`` directly, as
    ``file_palette`` / ``command_palette_run`` already cover), so the
    registered actions are only reachable through ``execute_action``.
    """
    app = new_app(target=tmp / "a.txt")
    checks: list[Check] = []
    async with app.run_test(size=(110, 32)) as pilot:
        await pilot.pause()
        app.editor.execute_action("quick_open")
        await pilot.pause()
        checks.append(Check("quick_open_overlay", 2, len(app.screen_stack)))
        await pilot.press("escape")
        await pilot.pause()
        checks.append(Check("quick_open_closed", 1, len(app.screen_stack)))
        app.editor.execute_action("command_palette")
        await pilot.pause()
        checks.append(Check("command_palette_overlay", 2, len(app.screen_stack)))
        await pilot.press("escape")
        await pilot.pause()
        checks.append(Check("command_palette_closed", 1, len(app.screen_stack)))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("view_palette_actions", checks, rows)


async def _focus_editor_action(tmp: Path) -> ScenarioResult:
    """execute_action("focus_editor") refocuses the active pane's view.

    ctrl+1 calls ``Editor.focus_editor`` directly in ``handle_key``, so the
    registered action needs this explicit ``execute_action`` call to be hit.
    """
    (tmp / "a.txt").write_text("a\n", encoding="utf-8")
    app = new_app(target=tmp)  # opening a directory shows the explorer
    checks: list[Check] = []
    async with app.run_test(size=(110, 32)) as pilot:
        await pilot.pause()
        panes = app.editor.panes
        tree = app.editor.explorer_tree
        assert panes is not None and tree is not None
        view = panes.active_view
        tree.focus()
        await pilot.pause()
        checks.append(Check("explorer_focused_first", True, app.focused is tree))
        app.editor.execute_action("focus_editor")
        await pilot.pause()
        checks.append(Check("editor_focused", True, app.focused is view))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("view_focus_editor_action", checks, rows)


SCENARIOS: list[Scenario] = [
    Scenario("command_palette_run", _command_palette_run, ("view",)),
    Scenario("theme_switch_invalid", _theme_switch_invalid, ("view",)),
    Scenario("command_history_recall", _command_history_recall, ("view",)),
    Scenario("manual_changelog_modals", _manual_changelog_modals, ("view",)),
    Scenario("set_options_matrix", _set_options_matrix, ("view",)),
    Scenario("status_mode_label", _status_mode_label, ("view",)),
    Scenario("view_manual_command", _manual_command_langs, ("view", "command")),
    Scenario("view_normal_command", _normal_command_alias, ("view", "command")),
    Scenario("view_font_command", _font_command_stub, ("view", "command")),
    Scenario("view_page_up", _page_up_key, ("view",)),
    Scenario("view_page_half_scroll", _page_half_scroll_vim, ("view",)),
    Scenario("view_palette_actions", _palette_actions, ("view",)),
    Scenario("view_focus_editor_action", _focus_editor_action, ("view",)),
]
