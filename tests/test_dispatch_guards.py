"""Regression guards for the global event.key dispatch branches.

``pilot.press`` synthesizes canonical Textual ``Key`` events -- it can never
exercise the terminal byte layer (that is what SP1's mapping unit tests and
the real-terminal matrix cover).  These guards pin the *dispatch* branches in
``Editor.handle_key`` (``ctrl+p`` / ``ctrl+1`` / ``ctrl+shift+e``), which sit
before keymap dispatch and must survive future refactors; ``ctrl+p`` was
regression-fixed exactly by moving it there (9fa5ac8).
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from yate.app import YateApp
from yate.editor_view.editor import EditorView


def test_global_chords_reach_their_dispatch_branches(tmp_path: Path) -> None:
    async def scenario() -> None:
        target = tmp_path / "notes.txt"
        app = YateApp(target=target)
        async with app.run_test(size=(100, 30)) as pilot:
            # --- ctrl+p opens the file palette overlay
            await pilot.press("ctrl+p")
            await pilot.pause()
            assert len(app.screen_stack) == 2
            await pilot.press("escape")
            await pilot.pause()
            assert len(app.screen_stack) == 1

            # --- ctrl+1 focuses the active editor pane
            app.editor.explorer_tree.focus()
            await pilot.press("ctrl+1")
            assert isinstance(app.focused, EditorView)

            # --- ctrl+shift+e moves focus to the explorer
            await pilot.press("ctrl+shift+e")
            assert app.focused is app.editor.explorer_tree

    asyncio.run(scenario())


def test_ctrl_p_palette_via_action_keybinding(tmp_path: Path) -> None:
    """The vsc <ctrl-p> binding must open the palette without the event.key
    branch: raw \\x10 reaches quick_open through the keymap."""

    async def scenario() -> None:
        target = tmp_path / "notes.txt"
        app = YateApp(target=target)
        async with app.run_test(size=(100, 30)) as pilot:
            app.editor.handle_raw_key("\x10")
            await pilot.pause()
            assert len(app.screen_stack) == 2

    asyncio.run(scenario())
