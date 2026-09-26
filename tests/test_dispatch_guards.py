"""Regression guards for global chord reachability, per keymap.

``pilot.press`` synthesizes canonical Textual ``Key`` events -- it can never
exercise the terminal byte layer (mapping unit tests and the real-terminal
matrix cover that).  These guards pin that the global dispatch branches in
``Editor.handle_key`` fire *before* keymap dispatch in BOTH keymaps; the
vim-mode guard is the one that catches a branch removal, because in vsc the
``\\x10`` raw binding in the keymap opens the palette too and would mask the
loss of the branch (this exact blind spot caused the SP2 drill to pass while
the branch was disabled).
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


def test_vim_mode_keeps_global_chords_reachable(tmp_path: Path) -> None:
    """In vim the keymap swallows unmapped keys, so the global branches in
    ``Editor.handle_key`` are the ONLY path for ``ctrl+p`` / ``ctrl+1``;
    removing a branch must turn this test red (unlike the vsc guard, which
    the keymap's own ``\\x10`` binding would satisfy)."""

    async def scenario() -> None:
        target = tmp_path / "notes.txt"
        app = YateApp(target=target)
        async with app.run_test(size=(100, 30)) as pilot:
            assert isinstance(app.focused, EditorView)
            # --- toggle to vim (vsc consumes \x1f -> toggle_keymap)
            app.editor.handle_raw_key("\x1f")
            assert app.editor.keymaps.active.name == "vim"

            # --- ctrl+p opens the palette although vim has no binding
            await pilot.press("ctrl+p")
            await pilot.pause()
            assert len(app.screen_stack) == 2
            await pilot.press("escape")
            await pilot.pause()
            assert len(app.screen_stack) == 1

            # --- ctrl+/ toggles back to vsc by either spelling
            await pilot.press("ctrl+/")
            assert app.editor.keymaps.active.name == "vsc"
            app.editor.handle_raw_key("\x1f")
            assert app.editor.keymaps.active.name == "vim"

            # --- ctrl+1 focuses the editor even from the explorer
            app.editor.explorer_tree.focus()
            await pilot.press("ctrl+1")
            assert isinstance(app.focused, EditorView)

    asyncio.run(scenario())
