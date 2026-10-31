"""Palette argument-mode tests (issue IKQ4VA wave b).

Pilot-driven (headless Textual): a minimal host app pushes a commands-mode
PaletteScreen wired with a stub ``CommandRegistry`` holding one command with
an ``arg_completer`` and one without; the tests drive Enter / Esc / typing
and assert on the mode switches and the submitted command strings.
"""

# tests legitimately poke at screen internals:
# pyright: reportPrivateUsage=false

from __future__ import annotations

import asyncio
from pathlib import Path

from textual.app import App
from textual.widgets import Input

from yate.config import FilePreviewConfig
from yate.editor_view.palette import PaletteScreen
from yate.registries import ActionRegistry, CommandRegistry
from yate.services.workspace import Workspace


class _Host(App[None]):
    """Minimal host app that pushes the PaletteScreen under test."""

    ENABLE_COMMAND_PALETTE = False

    def __init__(self, screen: PaletteScreen) -> None:
        super().__init__()
        self._screen = screen

    def on_mount(self) -> None:
        self.push_screen(self._screen)


def _completer(prefix: str) -> list[str]:
    """Value candidates for the stub ``arg_completer``."""
    values = ("alpha", "beta")
    return [v for v in values if v.startswith(prefix) and v != prefix]


def _commands() -> CommandRegistry:
    """One parameterized and one bare stub command."""
    commands = CommandRegistry()
    commands.register("zzarg", lambda _args: None, "arg command", _completer)
    commands.register("zzplain", lambda _args: None, "plain command")
    return commands


def _palette(
    root: Path, run_calls: list[str], commands: CommandRegistry | None = None
) -> PaletteScreen:
    """A commands-mode PaletteScreen capturing ``run_command`` into a list."""
    return PaletteScreen(
        "commands",
        workspace=Workspace(root),
        commands=commands if commands is not None else _commands(),
        actions=ActionRegistry(),
        open_path=lambda _p: None,
        focus_editor=lambda: None,
        execute_action=lambda _name: True,
        run_command=run_calls.append,
        refresh=lambda: None,
        preview=FilePreviewConfig(enable=False),
    )


def test_palette_command_with_arg_completer_enters_arg_mode(tmp_path: Path) -> None:
    """Enter on a parameterized command opens argument selection, not a run."""
    run_calls: list[str] = []
    screen = _palette(tmp_path, run_calls)

    async def scenario() -> None:
        app = _Host(screen)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            for ch in "zzarg":
                await pilot.press(ch)
            await pilot.pause()
            assert screen.filtered_count == 1
            await pilot.press("enter")
            await pilot.pause()
            # the palette stays open, now in argument mode
            assert isinstance(app.screen, PaletteScreen)
            assert screen._arg_mode == "zzarg"
            input_widget = screen.query_one("#palette-input", Input)
            assert input_widget.value == ""
            assert input_widget.placeholder == "argument for :zzarg"
            assert [d for d, _h, _p in screen._entries] == ["alpha", "beta"]
            # nothing ran
            assert run_calls == []

    asyncio.run(scenario())


def test_palette_arg_mode_enter_submits_full_command(tmp_path: Path) -> None:
    """Enter in argument mode dismisses and runs the full "cmd value" string."""
    run_calls: list[str] = []
    screen = _palette(tmp_path, run_calls)

    async def scenario() -> None:
        app = _Host(screen)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            for ch in "zzarg":
                await pilot.press(ch)
            await pilot.pause()
            await pilot.press("enter")  # into argument mode
            await pilot.pause()
            await pilot.press("enter")  # submit the highlighted value
            await pilot.pause()
            assert not isinstance(app.screen, PaletteScreen)
            assert run_calls == ["zzarg alpha"]

    asyncio.run(scenario())


def test_palette_arg_mode_escape_returns_to_command_list(tmp_path: Path) -> None:
    """Esc in argument mode restores the command list instead of dismissing."""
    run_calls: list[str] = []
    screen = _palette(tmp_path, run_calls)

    async def scenario() -> None:
        app = _Host(screen)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            for ch in "zzarg":
                await pilot.press(ch)
            await pilot.pause()
            await pilot.press("enter")  # into argument mode
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()
            # the palette is still open, back to the command list
            assert isinstance(app.screen, PaletteScreen)
            assert screen._arg_mode is None
            payloads = [p for _d, _h, p in screen._entries]
            assert ("command", "zzarg") in payloads
            assert ("command", "zzplain") in payloads
            input_widget = screen.query_one("#palette-input", Input)
            assert input_widget.value == ""
            assert screen.filtered_count == 2
            assert run_calls == []

    asyncio.run(scenario())


def test_palette_command_without_arg_completer_runs_directly(tmp_path: Path) -> None:
    """Enter on a bare command dismisses and runs it (unchanged behavior)."""
    run_calls: list[str] = []
    screen = _palette(tmp_path, run_calls)

    async def scenario() -> None:
        app = _Host(screen)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            for ch in "zzplain":
                await pilot.press(ch)
            await pilot.pause()
            assert screen.filtered_count == 1
            await pilot.press("enter")
            await pilot.pause()
            assert not isinstance(app.screen, PaletteScreen)
            assert run_calls == ["zzplain"]

    asyncio.run(scenario())


def test_palette_arg_mode_filters_on_input_change(tmp_path: Path) -> None:
    """Typing in argument mode refilters the value candidates."""
    run_calls: list[str] = []
    screen = _palette(tmp_path, run_calls)

    async def scenario() -> None:
        app = _Host(screen)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            for ch in "zzarg":
                await pilot.press(ch)
            await pilot.pause()
            await pilot.press("enter")  # into argument mode
            await pilot.pause()
            assert screen.filtered_count == 2  # alpha + beta, empty query
            for ch in "beta":
                await pilot.press(ch)
            await pilot.pause()
            assert screen._arg_mode == "zzarg"
            assert screen.filtered_count == 1
            _d, _h, payload = screen._entries[screen._filtered[0][2]]
            assert payload == ("arg", "zzarg beta")

    asyncio.run(scenario())
