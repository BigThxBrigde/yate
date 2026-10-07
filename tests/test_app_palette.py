"""Palette headless Textual UI tests (run via pilot, no real terminal)."""

# tests legitimately poke at internals:
# pyright: reportPrivateUsage=false

from __future__ import annotations

import asyncio
import threading
from pathlib import Path
from typing import Any, cast
from yate.app import YateApp
from conftest import wait_until

# --------------------------------------------------------------------- palette


def test_ctrl_p_chord_opens_file_palette(tmp_path: Path) -> None:
    from yate.editor_view.palette import PaletteScreen

    async def scenario() -> None:
        (tmp_path / "notes.txt").write_text("hi\n", encoding="utf-8")
        app = YateApp(target=tmp_path)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.press("ctrl+p")
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, PaletteScreen)
            assert screen.mode == "files"
            # escape dismisses
            await pilot.press("escape")
            await pilot.pause()
            assert len(app.screen_stack) == 1

    asyncio.run(scenario())


def test_file_palette_filters_and_opens(tmp_path: Path) -> None:
    from yate.editor_view.palette import PaletteScreen

    async def scenario() -> None:
        (tmp_path / "notes.txt").write_text("hi\n", encoding="utf-8")
        (tmp_path / "data.txt").write_text("data\n", encoding="utf-8")
        app = YateApp(target=tmp_path)
        async with app.run_test(size=(100, 30)) as pilot:
            app.editor.overlays.open_file_palette()
            await pilot.pause()
            assert isinstance(app.screen, PaletteScreen)
            for ch in "note":
                await pilot.press(ch)
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, PaletteScreen)
            # only notes.txt matches "note"
            assert screen.filtered_count == 1
            await pilot.press("enter")
            await pilot.pause()
            assert len(app.screen_stack) == 1
            assert app.editor.session.doc.name == "notes.txt"

    asyncio.run(scenario())


def test_command_palette_runs_command() -> None:
    from yate.editor_view.palette import PaletteScreen

    async def scenario() -> None:
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            # alt+shift+p is the default: ctrl+shift+p clashes with Windows
            # Terminal's own command palette, ctrl+shift+a with other
            # terminal emulators.
            await pilot.press("alt+shift+p")
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, PaletteScreen)
            assert screen.mode == "commands"
            for ch in "vim":
                await pilot.press(ch)
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            assert app.editor.keymaps.name == "vim"

    asyncio.run(scenario())


def test_command_palette_alt_shift_p_binding() -> None:
    from yate.editor_view.palette import PaletteScreen

    async def scenario() -> None:
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            # the vsc keymap advertises the binding and the chord opens the
            # palette even while the editor widget has focus
            binding = app.editor.keymaps.active.lookup("\x1bP")
            assert binding is not None
            assert binding.action == "command_palette"
            await pilot.press("alt+shift+p")
            await pilot.pause()
            assert isinstance(app.screen, PaletteScreen)

    asyncio.run(scenario())


def test_command_palette_lists_all_commands_and_actions() -> None:
    from yate.editor_view.palette import PaletteScreen

    async def scenario() -> None:
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            # as an extension would: one new command and one new action
            def _cmd(args: str) -> None:
                pass

            def _act(ctx: object) -> None:
                pass

            app.editor.commands.register("zzz_palette_cmd", _cmd,
                                  "zz palette command")
            app.editor.actions.register(
                "zzz_palette_action", _act, "zz palette action")
            app.editor.overlays.open_command_palette()
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, PaletteScreen)
            entries = cast(Any, screen)._entries
            by_name = {name: payload for name, _hint, payload in entries}

            # built-in : commands and raw keymap actions are both present,
            # each with its full name
            assert by_name["write"] == ("command", "write")
            assert by_name["move_left"] == ("action", "move_left")
            assert by_name["command_palette"] == ("action", "command_palette")
            # extension-registered items show up too
            assert by_name["zzz_palette_cmd"] == ("command", "zzz_palette_cmd")
            assert by_name["zzz_palette_action"] == (
                "action", "zzz_palette_action")
            # a name registered in both tables appears once and resolves
            # to the : command spelling
            assert by_name["quit"] == ("command", "quit")
            # every row has a non-empty name and (for built-ins) a hint
            assert all(name for name, _h, _p in entries)
            hinted = {name: hint for name, hint, _p in entries}
            assert hinted["write"] == "save the current file"
            assert hinted["move_left"] == "Move left"

    asyncio.run(scenario())


def test_command_palette_runs_action_by_full_name() -> None:
    from yate.editor_view.palette import PaletteScreen

    async def scenario() -> None:
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            assert app.editor.keymaps.name == "vsc"
            app.editor.overlays.open_command_palette()
            await pilot.pause()
            assert isinstance(app.screen, PaletteScreen)
            for ch in "toggle_keymap":
                await pilot.press(ch)
            await pilot.pause()
            screen = cast(Any, app.screen)
            # the action is found by its full name and is the top hit
            assert screen._entries[screen._filtered[0][2]][2] == (
                "action", "toggle_keymap",
            )
            await pilot.press("enter")
            await pilot.pause()
            assert len(app.screen_stack) == 1
            assert app.editor.keymaps.name == "vim"

    asyncio.run(scenario())


def test_command_palette_searches_descriptions() -> None:
    from yate.editor_view.palette import PaletteScreen

    async def scenario() -> None:
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            app.editor.overlays.open_command_palette()
            await pilot.pause()
            for ch in "switch color theme":
                await pilot.press(ch)
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, PaletteScreen)
            # no command is *named* "switch color theme"; it matches the
            # description of :theme, and the row is selectable
            assert screen.filtered_count > 0
            top = cast(Any, screen)._entries[cast(Any, screen)._filtered[0][2]]
            assert top[2] == ("command", "theme")
            await pilot.press("enter")
            await pilot.pause()
            assert len(app.screen_stack) == 1

    asyncio.run(scenario())


def test_palette_down_cursor_moves(tmp_path: Path) -> None:
    from yate.editor_view.palette import PaletteScreen

    async def scenario() -> None:
        for name in ("a.txt", "b.txt", "c.txt"):
            (tmp_path / name).write_text("x\n", encoding="utf-8")
        app = YateApp(target=tmp_path)
        async with app.run_test(size=(100, 30)) as pilot:
            app.editor.overlays.open_file_palette()
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, PaletteScreen)
            # the input grabs focus in on_mount; under full-suite load that
            # can land after the press, which then sinks into the editor
            # beneath the modal instead of bubbling to the screen
            assert await wait_until(
                pilot,
                lambda: app.focused is not None
                and app.focused.id == "palette-input",
                timeout=5.0,
            )
            await pilot.press("down")
            # poll instead of asserting after one pause: under full-suite
            # load the key event can land one pump cycle late
            assert await wait_until(
                pilot, lambda: screen.cursor_index == 1, timeout=5.0
            )

    asyncio.run(scenario())


def test_palette_down_on_a_single_result_does_not_execute_it(tmp_path: Path) -> None:
    """Down only moves the cursor: a unique result executes on Tab alone.

    The single-match fast path sat inside the branch shared with
    down / ctrl+n, so pressing Down on the one result opened the file
    (2026-10-03 review R-20).
    """
    from yate.editor_view.palette import PaletteScreen

    async def scenario() -> None:
        (tmp_path / "only.txt").write_text("x\n", encoding="utf-8")
        app = YateApp(target=tmp_path)
        async with app.run_test(size=(100, 30)) as pilot:
            app.editor.overlays.open_file_palette()
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, PaletteScreen)
            assert await wait_until(
                pilot,
                lambda: app.focused is not None
                and app.focused.id == "palette-input",
                timeout=5.0,
            )
            # wait for the file walk to populate the single entry
            assert await wait_until(
                pilot, lambda: len(screen._filtered) == 1, timeout=5.0
            )
            await pilot.press("down")
            await pilot.pause()
            assert isinstance(app.screen, PaletteScreen)
            await pilot.press("tab")
            assert await wait_until(
                pilot,
                lambda: not isinstance(app.screen, PaletteScreen),
                timeout=5.0,
            )

    asyncio.run(scenario())


def test_file_palette_indexes_in_background(tmp_path: Path) -> None:
    from unittest.mock import patch

    from rich.text import Text
    from textual.widgets import Static

    from yate.editor_view.palette import PaletteScreen
    from yate.services.workspace import Workspace

    root = tmp_path
    (root / "notes.txt").write_text("x\n", encoding="utf-8")
    app = YateApp(target=root)

    async def scenario() -> None:
        gate = threading.Event()

        def slow_walk(self: Workspace, limit: int = 5000) -> list[Path]:
            gate.wait(timeout=10.0)
            return [root / "notes.txt"]

        def status_text() -> str:
            content = palette.query_one("#palette-results", Static).content
            return content.plain if isinstance(content, Text) else ""

        with patch.object(Workspace, "walk_files", slow_walk):
            async with app.run_test(size=(100, 30)) as pilot:
                await pilot.press("ctrl+p")
                await pilot.pause(0.15)
                assert isinstance(app.screen, PaletteScreen)
                palette = cast(PaletteScreen, app.screen)
                assert "indexing" in status_text()
                # responsiveness proven: release the parked indexing thread
                gate.set()
                done = await wait_until(
                    pilot, lambda: palette.filtered_count == 1,
                    timeout=10.0,
                )
                assert done
                assert "notes.txt" in status_text()

    asyncio.run(scenario())


# ---------------------------------------------------- palette tab completion


def test_tab_cycles_and_single_match_auto_chooses() -> None:
    from yate.editor_view.palette import PaletteScreen

    async def scenario() -> None:
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.press("alt+shift+p")
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, PaletteScreen)
            # multiple matches: tab cycles the cursor (does not dismiss)
            for ch in "set":
                await pilot.press(ch)
            await pilot.pause()
            before = screen.cursor_index
            await pilot.press("tab")
            await pilot.pause()
            assert screen.cursor_index == (before + 1) % screen.filtered_count
            assert isinstance(app.screen, PaletteScreen)
            # narrow to a single unique match: tab chooses it immediately
            for ch in "theme":
                await pilot.press(ch)
            await pilot.pause()
            assert screen.filtered_count == 1
            await pilot.press("tab")
            await pilot.pause()
            # palette dismissed and :theme ran (prints theme info)
            assert not isinstance(app.screen, PaletteScreen)

    asyncio.run(scenario())
