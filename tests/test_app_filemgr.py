"""App-level pilot tests for the file manager L4 wiring (plan-f).

Covers the three entry points end to end -- the ``alt+shift+f`` chord,
the ``:file-manager`` command and the ``--file-manager`` startup flag --
plus the fullscreen exit, the Q1 dirty gate and the CLI argument rules.
"""

# tests legitimately poke at internals:
# pyright: reportPrivateUsage=false

from __future__ import annotations

import asyncio
import contextlib
from pathlib import Path
from unittest.mock import patch

import pytest

from yate.app import YateApp
from yate.cli import build_parser, main
from yate.editor_view.filemgr import FileManagerScreen
from yate.keymaps.base import parse_key
from yate.keymaps.vim import VimKeymap
from yate.keymaps.vsc import VscKeymap
from conftest import wait_until


def test_alt_shift_f_opens_overlay_and_esc_restores(tmp_path: Path) -> None:
    """The chord opens the overlay; esc closes it and refocuses the editor."""

    async def scenario() -> None:
        app = YateApp(target=tmp_path)
        async with app.run_test(size=(120, 36)) as pilot:
            view = app.editor.panes.active_view
            assert view is not None
            await pilot.press("alt+shift+f")
            assert await wait_until(
                pilot, lambda: isinstance(app.screen, FileManagerScreen)
            )
            await pilot.press("escape")
            assert await wait_until(pilot, lambda: len(app.screen_stack) == 1)
            assert await wait_until(pilot, lambda: app.focused is view)

    asyncio.run(scenario())


def test_command_file_manager_opens_overlay(tmp_path: Path) -> None:
    """The :file-manager command entry opens the same overlay."""

    async def scenario() -> None:
        app = YateApp(target=tmp_path)
        async with app.run_test(size=(120, 36)) as pilot:
            entry = app.editor.commands.get("file-manager")
            assert entry is not None
            entry.func("")
            assert await wait_until(
                pilot, lambda: isinstance(app.screen, FileManagerScreen)
            )
            await pilot.press("escape")
            assert await wait_until(pilot, lambda: len(app.screen_stack) == 1)

    asyncio.run(scenario())


def test_action_file_manager_registered_in_both_keymaps() -> None:
    """Both keymaps bind <alt-shift-f> to the file_manager action."""

    raw = parse_key("<alt-shift-f>")
    for keymap in (VscKeymap(), VimKeymap()):
        binding = keymap.lookup(raw)
        assert binding is not None
        assert binding.action == "file_manager"
    # the action itself resolves against the builtin table (R7 load)
    app = YateApp()
    assert app.editor.actions.get("file_manager") is not None


def test_fullscreen_startup_pushes_filemgr_screen(tmp_path: Path) -> None:
    """--file-manager startup pushes the fullscreen screen after mount."""

    async def scenario() -> None:
        app = YateApp(target=tmp_path, filemanager_dir=tmp_path)
        async with app.run_test(size=(120, 36)) as pilot:
            assert await wait_until(
                pilot, lambda: isinstance(app.screen, FileManagerScreen)
            )
            screen = app.screen
            assert isinstance(screen, FileManagerScreen)
            assert screen.has_class("fullscreen")

    asyncio.run(scenario())


def test_fullscreen_open_file_switches_workspace(tmp_path: Path) -> None:
    """Opening a file fullscreen pops the screen and switches the workspace."""

    async def scenario() -> None:
        # a root-level dir keeps the dirs-first listing two rows deep; the
        # opened file's parent (tmp_path) becomes the new workspace root
        sub = tmp_path / "sub"
        sub.mkdir()
        file = tmp_path / "a.txt"
        file.write_text("hi\n", encoding="utf-8")
        app = YateApp(target=tmp_path, filemanager_dir=tmp_path)
        async with app.run_test(size=(120, 36)) as pilot:
            assert await wait_until(
                pilot, lambda: isinstance(app.screen, FileManagerScreen)
            )
            screen = app.screen
            assert isinstance(screen, FileManagerScreen)
            # wait for the listing, then for the restored cursor row
            assert await wait_until(pilot, lambda: screen._cursor_path() is not None)
            # entries are sorted dirs-first: j moves onto a.txt, enter opens
            await pilot.press("j")
            assert await wait_until(pilot, lambda: screen._cursor_path() == file)
            await pilot.press("enter")
            assert await wait_until(
                pilot,
                lambda: len(app.screen_stack) == 1
                and app.editor.session.doc.path == file,
            )
            assert app.editor.workspace.root == tmp_path

    asyncio.run(scenario())


def test_fullscreen_open_dir_sets_root(tmp_path: Path) -> None:
    """A marked directory handed to open_selected becomes the workspace root.

    A plain enter on a directory only navigates into it (lf semantics), so
    the entry is marked first to exercise the open_selected path.
    """

    async def scenario() -> None:
        sub = tmp_path / "sub"
        sub.mkdir()
        app = YateApp(target=tmp_path, filemanager_dir=tmp_path)
        async with app.run_test(size=(120, 36)) as pilot:
            assert await wait_until(
                pilot, lambda: isinstance(app.screen, FileManagerScreen)
            )
            screen = app.screen
            assert isinstance(screen, FileManagerScreen)
            # wait for the listing and the cursor on the lone directory
            assert await wait_until(pilot, lambda: screen._cursor_path() == sub)
            await pilot.press("space")
            await pilot.press("enter")
            assert await wait_until(
                pilot,
                lambda: app.editor.workspace.root == sub
                and app.editor.explorer_tree.root.data == sub,
            )
            assert len(app.screen_stack) == 1

    asyncio.run(scenario())


def test_fullscreen_q_exits_app(tmp_path: Path) -> None:
    """``q`` in the fullscreen form exits the app through the bound verb.

    Observable face (Textual 8.2.8): ``App.exit()`` records the quit
    synchronously (``app._exit`` / ``app.return_code``) and then the app
    shuts down, so the test pumps until ``app.is_running`` turns False.
    """

    async def scenario() -> None:
        app = YateApp(target=tmp_path, filemanager_dir=tmp_path)
        async with app.run_test(size=(120, 36)) as pilot:
            assert await wait_until(
                pilot, lambda: isinstance(app.screen, FileManagerScreen)
            )
            await pilot.press("q")
            assert app._exit is True
            for _ in range(5):
                with contextlib.suppress(Exception):
                    await pilot.pause()
                if not app.is_running:
                    break
            assert app._exception is None
        assert app.return_code == 0

    asyncio.run(scenario())


def test_dirty_blocks_switch_and_reports(tmp_path: Path) -> None:
    """A dirty buffer refuses the switch: warn on the message line, no root change."""

    async def scenario() -> None:
        file = tmp_path / "a.txt"
        file.write_text("x\n", encoding="utf-8")
        app = YateApp(target=tmp_path)
        async with app.run_test(size=(120, 36)) as pilot:
            app.editor.document_flows.open_path(file)
            await pilot.pause()
            assert app.editor.session.doc.path == file
            # dirty the buffer with one keystroke
            await pilot.press("x")
            assert app.editor.session.doc.modified
            root_before = app.editor.workspace.root
            await pilot.press("alt+shift+f")
            assert await wait_until(
                pilot, lambda: isinstance(app.screen, FileManagerScreen)
            )
            screen = app.screen
            assert isinstance(screen, FileManagerScreen)
            # wait for the listing: the file is the lone entry under the cursor
            assert await wait_until(pilot, lambda: screen._cursor_path() == file)
            await pilot.press("enter")
            # the screen dismisses itself first (Q1 fire-and-forget), then
            # the refused switch leaves its warning on the message line
            assert await wait_until(pilot, lambda: len(app.screen_stack) == 1)
            message = app.editor.prompt_bar._message
            assert message is not None
            assert "unsaved" in message[0]
            assert app.editor.workspace.root == root_before

    asyncio.run(scenario())


def test_cli_flag_mutually_exclusive_with_path(tmp_path: Path) -> None:
    """--file-manager and the positional PATH cannot be combined."""

    for argv in (
        ["--file-manager", "somewhere", "other"],
        ["other", "--file-manager", "somewhere"],
    ):
        with (
            patch("yate.logs.crash.install"),
            pytest.raises(SystemExit) as ctx,
        ):
            main(argv)
        assert ctx.value.code == 2


def test_cli_file_manager_defaults_to_cwd() -> None:
    """Bare --file-manager resolves to "." (cwd); a value passes through."""

    args = build_parser().parse_args(["--file-manager"])
    assert args.file_manager == "."
    args = build_parser().parse_args(["--file-manager", "some/dir"])
    assert args.file_manager == "some/dir"
    # the positional alone leaves the flag untouched
    args = build_parser().parse_args(["pos"])
    assert args.file_manager is None
    assert args.path == "pos"
