"""Text-area mouse interaction headless tests (IKJRFK wave-2, run via pilot).

Covers the EditorView -> MouseFlows dispatch: click moves the cursor,
drag selects, double/triple click select word/line, vim mode cooperation
and the plan-b separator-border contract.
"""

# tests legitimately poke at internals:
# pyright: reportPrivateUsage=false

from __future__ import annotations

import asyncio
from pathlib import Path

from textual.events import MouseMove, MouseUp
from yate.app import YateApp
from yate.editor_view.editor import EditorView
from yate.keymaps.vim import VimKeymap, VimMode
from conftest import wait_until

# "hello world\nsecond line\n": a two-line document, so the gutter is
# max(3, len("2")) + 3 == 6 cells; cell x = mouse x - 6 (scroll_col 0).
_GUTTER: int = 6


def _mouse_app(tmp_path: Path, *, keymap: str | None = None) -> YateApp:
    """A yate app over a known two-line document."""
    target = tmp_path / "mouse.txt"
    target.write_text("hello world\nsecond line\n", encoding="utf-8")
    return YateApp(target=target, keymap=keymap)


def test_mouse_click_moves_cursor(tmp_path: Path) -> None:
    async def scenario() -> None:
        app = _mouse_app(tmp_path)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            view = app.editor.panes.active_view
            assert view is not None
            # x=11 lands on cell 5 of "hello world"
            await pilot.click(EditorView, offset=(_GUTTER + 5, 0))
            await pilot.pause()
            assert app.editor.session.buffer.cursor == (0, 5)
            assert app.editor.panes.active_view is view

    asyncio.run(scenario())


def test_mouse_gutter_click_clamps_column_zero(tmp_path: Path) -> None:
    async def scenario() -> None:
        app = _mouse_app(tmp_path)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            # move the cursor into the line first, then hit the gutter
            await pilot.click(EditorView, offset=(_GUTTER + 5, 0))
            await pilot.pause()
            assert app.editor.session.buffer.cursor == (0, 5)
            await pilot.click(EditorView, offset=(2, 0))
            await pilot.pause()
            assert app.editor.session.buffer.cursor == (0, 0)

    asyncio.run(scenario())


def test_mouse_drag_selects_range(tmp_path: Path) -> None:
    async def scenario() -> None:
        app = _mouse_app(tmp_path)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            await pilot.mouse_down(EditorView, offset=(_GUTTER, 0))
            await pilot.pause()
            # Textual private API (verified on 8.2.8; revisit on upgrades,
            # same containment discipline as keyproto/textual_internals.py):
            # the installed pilot defaults _post_mouse_events to button=0;
            # the drag move must carry the pressed button (button=1)
            await pilot._post_mouse_events(
                [MouseMove, MouseUp], widget=EditorView,
                offset=(_GUTTER + 3, 0), button=1,
            )
            await pilot.pause()
            assert app.editor.session.buffer.selected_text() == "hel"

    asyncio.run(scenario())


def test_mouse_double_click_selects_word(tmp_path: Path) -> None:
    async def scenario() -> None:
        app = _mouse_app(tmp_path)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            # x=14 lands on cell 8, inside "world" (cells 6..11)
            await pilot.double_click(EditorView, offset=(_GUTTER + 8, 0))
            await pilot.pause()
            assert app.editor.session.buffer.selected_text() == "world"

    asyncio.run(scenario())


def test_mouse_triple_click_selects_line(tmp_path: Path) -> None:
    async def scenario() -> None:
        app = _mouse_app(tmp_path)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            await pilot.click(EditorView, offset=(_GUTTER + 2, 0), times=3)
            await pilot.pause()
            assert app.editor.session.buffer.selected_text() == "hello world"

    asyncio.run(scenario())


def test_visual_mode_click_exits_to_normal(tmp_path: Path) -> None:
    async def scenario() -> None:
        app = _mouse_app(tmp_path, keymap="vim")
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            await pilot.press("v")
            await pilot.pause()
            keymap = app.editor.keymaps.active
            assert isinstance(keymap, VimKeymap)
            assert keymap.mode is VimMode.VISUAL

            await pilot.click(EditorView, offset=(_GUTTER + 5, 0))
            await pilot.pause()
            assert keymap.mode is VimMode.NORMAL
            assert app.editor.session.buffer.has_selection() is False

    asyncio.run(scenario())


def test_insert_mode_click_moves_cursor_keeps_insert(tmp_path: Path) -> None:
    async def scenario() -> None:
        app = _mouse_app(tmp_path, keymap="vim")
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            await pilot.press("i")
            await pilot.pause()
            keymap = app.editor.keymaps.active
            assert isinstance(keymap, VimKeymap)

            await pilot.click(EditorView, offset=(_GUTTER + 5, 0))
            await pilot.pause()
            assert app.editor.session.buffer.cursor == (0, 5)
            assert keymap.mode is VimMode.INSERT

    asyncio.run(scenario())


def test_click_activates_clicked_pane(tmp_path: Path) -> None:
    async def scenario() -> None:
        app = _mouse_app(tmp_path, keymap="vim")
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            panes = app.editor.panes
            await pilot.press(":", "v", "s", "p", "l", "i", "t", "enter")
            assert await wait_until(pilot, lambda: panes.leaf_count == 2)
            await pilot.pause()

            host = panes.host
            assert host is not None
            box, _split = host._split_boxes[0]
            left_view, right_view = box.children
            assert isinstance(left_view, EditorView)
            assert isinstance(right_view, EditorView)
            # after :vsplit the new (right) pane is active
            active_before = panes.active
            assert panes.active_view is right_view

            await pilot.click(left_view, offset=(_GUTTER + 5, 0))
            await pilot.pause()
            assert panes.active is not active_before
            assert panes.active.id == left_view.leaf_id
            assert panes.active_view is left_view

    asyncio.run(scenario())


def test_shift_click_extends_selection(tmp_path: Path) -> None:
    async def scenario() -> None:
        app = _mouse_app(tmp_path)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            # anchor at cell 1 ("e" of hello)...
            await pilot.click(EditorView, offset=(_GUTTER + 1, 0))
            await pilot.pause()
            # ...then shift-click at cell 5 extends the selection over it
            await pilot.click(EditorView, offset=(_GUTTER + 5, 0), shift=True)
            await pilot.pause()
            buf = app.editor.session.buffer
            assert buf.selection() == ((0, 1), (0, 5))
            assert buf.selected_text() == "ello"

    asyncio.run(scenario())


def test_separator_border_press_bubbles_to_pane_host(tmp_path: Path) -> None:
    """A press on the pane-separator border must not move the cursor: the
    border cell belongs to PaneHost's drag (plan-b contract, wave-2 side)."""

    async def scenario() -> None:
        app = _mouse_app(tmp_path, keymap="vim")
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            panes = app.editor.panes
            await pilot.press(":", "v", "s", "p", "l", "i", "t", "enter")
            assert await wait_until(pilot, lambda: panes.leaf_count == 2)
            await pilot.pause()

            host = panes.host
            assert host is not None
            box, _split = host._split_boxes[0]
            left_view, _right_view = box.children
            assert isinstance(left_view, EditorView)

            # focus the pane owning the divider border first
            await pilot.press("ctrl+w", "h")
            await pilot.pause()
            assert app.focused is left_view
            cursor_before = app.editor.session.buffer.cursor

            # the separator cell is the left pane's right border column
            sx = left_view.region.x + left_view.region.width - 1
            sy = left_view.region.y + left_view.region.height // 2
            await pilot.click(None, offset=(sx, sy))
            await pilot.pause()

            assert app.editor.session.buffer.cursor == cursor_before

    asyncio.run(scenario())
