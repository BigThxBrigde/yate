"""Status bar mode chip regression tests (plan-g, wave-3).

``mode_chip`` is a pure function but its inputs are widgets, so these
tests drive :meth:`yate.editor.Editor.mode_label` through a real app
under ``pilot.run_test()`` -- the same path the smoke scenarios use.
They pin the vim block-mode chip (``V-COLUMN``, plan-c's
``VimMode.VISUAL_BLOCK``), the escape exit, the vsc ``Ctrl+V`` paste
fallback and the existing ``V-LINE`` chip.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from yate.app import YateApp
from yate.editor_view import theme


def test_mode_chip_shows_v_column_in_visual_block(tmp_path: Path) -> None:
    async def scenario() -> None:
        app = YateApp(target=tmp_path / "notes.txt")
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            app.editor.run_command("vim")
            await pilot.pause()
            await pilot.press("ctrl+v")
            await pilot.pause()
            assert app.editor.mode_label() == (
                "V-COLUMN",
                theme.active().mode_visual_bg,
            )

    asyncio.run(scenario())


def test_mode_chip_back_to_normal_after_block_exit(tmp_path: Path) -> None:
    async def scenario() -> None:
        app = YateApp(target=tmp_path / "notes.txt")
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            app.editor.run_command("vim")
            await pilot.pause()
            await pilot.press("ctrl+v")
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()
            assert app.editor.mode_label()[0] == "NORMAL"

    asyncio.run(scenario())


def test_mode_chip_vsc_falls_back_to_vsc_label(tmp_path: Path) -> None:
    async def scenario() -> None:
        app = YateApp(target=tmp_path / "notes.txt")
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            # In the vsc keymap ctrl+v is paste: no vim mode is entered,
            # so the chip must stay on the plain VSC label.
            await pilot.press("ctrl+v")
            await pilot.pause()
            assert app.editor.mode_label()[0] == "VSC"

    asyncio.run(scenario())


def test_mode_chip_v_line_unchanged(tmp_path: Path) -> None:
    async def scenario() -> None:
        app = YateApp(target=tmp_path / "notes.txt")
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            app.editor.run_command("vim")
            await pilot.pause()
            await pilot.press("V")
            await pilot.pause()
            assert app.editor.mode_label()[0] == "V-LINE"

    asyncio.run(scenario())
