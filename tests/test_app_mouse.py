"""Text-area mouse interaction headless tests (IKJRFK wave-2, run via pilot).

Covers the EditorView -> MouseFlows dispatch: click moves the cursor,
drag selects, double/triple click select word/line, vim mode cooperation,
the plan-b separator-border contract, the unconsumed-press bubbling
contract (PR#66 review disposition) and the scroll-consistent click
mapping.
"""

# tests legitimately poke at internals:
# pyright: reportPrivateUsage=false

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import patch

from textual.events import MouseDown, MouseEvent, MouseMove, MouseUp
from textual.pilot import _get_mouse_message_arguments
from yate.app import YateApp
from yate.config import YateConfig
from yate.editor_view.editor import EditorView
from yate.editor_view.panes import PaneHost
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


def test_unconsumed_press_bubbles_to_pane_host(tmp_path: Path) -> None:
    """An unconsumed left press must still reach PaneHost (R10 mouse
    analogue, PR#66 review blocker disposition).

    The bare ``return`` in ``EditorView.on_mouse_down`` relies on Textual
    bubbling (``MouseDown`` is ``bubble=True``); it must not swallow the
    event, and must not re-dispatch it to MouseFlows a second time.  The
    unconsumed path is manufactured through the MouseFlows gate
    (``support_mouse=False``): pilot.click forwards at screen level
    (bypassing the shell gate in App.on_event), so the press arrives at
    the view and the gate-closed dispatch returns False.
    """

    async def scenario() -> None:
        target = tmp_path / "mouse.txt"
        target.write_text("hello world\nsecond line\n", encoding="utf-8")
        app = YateApp(target=target, config=YateConfig(support_mouse=False))
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            host = app.editor.panes.host
            assert host is not None
            # Textual dispatches handlers via cls.__dict__ (MRO walk), so
            # the PaneHost spy must patch the class, not the instance.  The
            # flows spy counts MouseDown deliveries to MouseFlows: a
            # re-dispatch variant (e.g. re-calling _forward_mouse on the
            # unconsumed path) would show up as 2 even with the gate
            # closed, since the second call has no observable side effect.
            calls: list[MouseDown] = []
            original = PaneHost.on_mouse_down

            def spy(self: PaneHost, event: MouseDown) -> None:
                calls.append(event)
                original(self, event)

            flow = app.editor.mouse_flows
            dispatches: list[MouseDown] = []
            original_handle = flow.handle_view_mouse

            def handle_spy(view: EditorView, event: MouseEvent) -> bool:
                if isinstance(event, MouseDown):
                    dispatches.append(event)
                return original_handle(view, event)

            with (
                patch.object(PaneHost, "on_mouse_down", spy),
                patch.object(flow, "handle_view_mouse", handle_spy),
            ):
                await pilot.click(EditorView, offset=(_GUTTER + 5, 0))
                await pilot.pause()
            assert len(calls) == 1  # bubbled exactly once to PaneHost
            assert len(dispatches) == 1  # dispatched exactly once
            assert app.editor.session.buffer.cursor == (0, 0)

    asyncio.run(scenario())


def test_consumed_press_does_not_reach_pane_host(tmp_path: Path) -> None:
    """The consumed half of the dispatch contract (_forward_mouse
    docstring: stop only the events the dispatcher consumed): a press
    MouseFlows consumes is captured and stopped, so PaneHost never sees
    the MouseDown."""

    async def scenario() -> None:
        app = _mouse_app(tmp_path)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            host = app.editor.panes.host
            assert host is not None
            calls: list[MouseDown] = []
            original = PaneHost.on_mouse_down

            def spy(self: PaneHost, event: MouseDown) -> None:
                calls.append(event)
                original(self, event)

            with patch.object(PaneHost, "on_mouse_down", spy):
                await pilot.click(EditorView, offset=(_GUTTER + 5, 0))
                await pilot.pause()
            assert calls == []  # consumed at the view: no bubbling
            assert app.editor.session.buffer.cursor == (0, 5)

    asyncio.run(scenario())


def test_right_button_up_during_drag_keeps_drag_alive(tmp_path: Path) -> None:
    """Chording: a non-left MouseUp during a left-button drag must not
    terminate the drag -- neither the MouseFlows drag state (the _on_up
    button gate) nor the mouse capture (the on_mouse_up release gate),
    parity with the PaneHost.on_mouse_up fix."""

    async def scenario() -> None:
        app = _mouse_app(tmp_path)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            await pilot.mouse_down(EditorView, offset=(_GUTTER, 0))
            await pilot.pause()
            # releasing the right button mid-drag ends neither the drag
            # nor the capture
            await pilot._post_mouse_events(
                [MouseUp], widget=EditorView, offset=(_GUTTER + 1, 0), button=2,
            )
            await pilot.pause()
            # the left-button drag continues and extends the selection
            await pilot._post_mouse_events(
                [MouseMove], widget=EditorView,
                offset=(_GUTTER + 3, 0), button=1,
            )
            await pilot._post_mouse_events(
                [MouseUp], widget=EditorView,
                offset=(_GUTTER + 3, 0), button=1,
            )
            await pilot.pause()
            assert app.editor.session.buffer.selected_text() == "hel"

    asyncio.run(scenario())


def test_mouse_click_maps_columns_after_horizontal_scroll(
    tmp_path: Path,
) -> None:
    """Column mapping stays render-consistent under horizontal scroll:
    cell = x - gutter + scroll_col (PR#66 review improvement 1)."""

    async def scenario() -> None:
        app = _mouse_app(tmp_path)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            view = app.editor.panes.active_view
            assert view is not None
            # scroll_col=3: the text window starts at char cell 3, so
            # x = gutter + 5 maps to cell 5 + 3 == 8 ('r' of "world")
            view.scroll_col = 3
            await pilot.pause()
            await pilot.click(EditorView, offset=(_GUTTER + 5, 0))
            await pilot.pause()
            assert app.editor.session.buffer.cursor == (0, 8)
            # a scrolled gutter click still clamps to column 0
            view.scroll_col = 3
            await pilot.pause()
            await pilot.click(EditorView, offset=(2, 0))
            await pilot.pause()
            assert app.editor.session.buffer.cursor == (0, 0)

    asyncio.run(scenario())


def test_mouse_click_maps_rows_after_vertical_scroll(tmp_path: Path) -> None:
    """Row mapping stays render-consistent under vertical scroll:
    row = y + scroll_offset.y (PR#66 review improvement 1)."""

    async def scenario() -> None:
        target = tmp_path / "tall.txt"
        target.write_text(
            "".join(f"line{i:02d}\n" for i in range(60)), encoding="utf-8"
        )
        app = YateApp(target=target)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            view = app.editor.panes.active_view
            assert view is not None
            view.scroll_to(y=5, animate=False)
            await pilot.pause()
            # y=3 with scroll offset 5 lands on row 8 ("line08"); the
            # 60-line gutter is max(3, len("60")) + 3 == 6 cells, so
            # x = gutter + 2 maps to column 2
            await pilot.click(EditorView, offset=(_GUTTER + 2, 3))
            await pilot.pause()
            assert app.editor.session.buffer.cursor == (8, 2)

    asyncio.run(scenario())


def test_alt_drag_makes_block_selection(tmp_path: Path) -> None:
    async def scenario() -> None:
        app = _mouse_app(tmp_path)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            # Alt+press anchors a column selection at (0, 1)...
            await pilot.mouse_down(
                EditorView, offset=(_GUTTER + 1, 0), meta=True,
            )
            await pilot.pause()
            # ...an Alt drag extends the rectangle to (1, 3)...
            await pilot._post_mouse_events(
                [MouseMove], widget=EditorView,
                offset=(_GUTTER + 3, 1), button=1, meta=True,
            )
            await pilot.pause()
            # ...and MouseUp keeps the block selection (VS Code parity)
            await pilot.mouse_up(
                EditorView, offset=(_GUTTER + 3, 1), meta=True,
            )
            await pilot.pause()
            buf = app.editor.session.buffer
            assert buf.has_block_selection() is True
            assert buf.block_region() == (0, 1, 1, 3)
            assert app.editor.mouse_flows._dragging is False

    asyncio.run(scenario())


def test_plain_drag_makes_charwise_selection(tmp_path: Path) -> None:
    async def scenario() -> None:
        app = _mouse_app(tmp_path)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            await pilot.mouse_down(EditorView, offset=(_GUTTER + 1, 0))
            await pilot.pause()
            await pilot._post_mouse_events(
                [MouseMove], widget=EditorView,
                offset=(_GUTTER + 3, 1), button=1,
            )
            await pilot.mouse_up(EditorView, offset=(_GUTTER + 3, 1))
            await pilot.pause()
            buf = app.editor.session.buffer
            # regression pin: the no-Alt path stays charwise
            assert buf.has_block_selection() is False
            assert buf.selection() == ((0, 1), (1, 3))

    asyncio.run(scenario())


def test_alt_drag_under_vim_keymap_drops_visual_then_blocks(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        app = _mouse_app(tmp_path, keymap="vim")
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            await pilot.press("v")
            await pilot.pause()
            keymap = app.editor.keymaps.active
            assert isinstance(keymap, VimKeymap)
            assert keymap.mode is VimMode.VISUAL

            await pilot.mouse_down(
                EditorView, offset=(_GUTTER + 1, 0), meta=True,
            )
            await pilot.pause()
            await pilot._post_mouse_events(
                [MouseMove], widget=EditorView,
                offset=(_GUTTER + 3, 1), button=1, meta=True,
            )
            await pilot.mouse_up(
                EditorView, offset=(_GUTTER + 3, 1), meta=True,
            )
            await pilot.pause()
            # the Alt+press exits visual mode before anchoring the block
            assert keymap.mode is VimMode.NORMAL
            buf = app.editor.session.buffer
            assert buf.has_block_selection() is True
            assert buf.block_region() == (0, 1, 1, 3)

    asyncio.run(scenario())


def test_alt_click_without_drag_keeps_zero_width_anchor(tmp_path: Path) -> None:
    async def scenario() -> None:
        app = _mouse_app(tmp_path)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            await pilot.mouse_down(
                EditorView, offset=(_GUTTER + 1, 0), meta=True,
            )
            await pilot.pause()
            await pilot.mouse_up(
                EditorView, offset=(_GUTTER + 1, 0), meta=True,
            )
            await pilot.pause()
            buf = app.editor.session.buffer
            # a zero-width block anchor survives the click (VS Code
            # parity); the plan-d select_block_* actions extend from it
            assert buf.block is True
            assert buf.anchor == buf.cursor == (0, 1)
            app.editor.execute_action("select_block_down")
            assert buf.block_region() == (0, 1, 1, 1)

    asyncio.run(scenario())


def test_support_mouse_off_blocks_alt_drag(tmp_path: Path) -> None:
    """With the gate closed, Alt+drag records never reach MouseFlows.

    The pilot mouse helpers bypass ``App.on_event`` (screen-level
    forwarding), so the Alt+drag is delivered through the app queue --
    the driver's path -- the same caliber as the test_support_mouse
    gate cases.
    """

    async def scenario() -> None:
        target = tmp_path / "mouse.txt"
        target.write_text("hello world\nsecond line\n", encoding="utf-8")
        app = YateApp(target=target, config=YateConfig(support_mouse=False))
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            view = app.editor.panes.active_view
            assert view is not None
            for event_cls in (MouseDown, MouseMove):
                kwargs = _get_mouse_message_arguments(
                    view, (_GUTTER + 3, 1), button=1, meta=True,
                )
                app.post_message(event_cls(**kwargs))
            await pilot.pause()
            buf = app.editor.session.buffer
            assert buf.cursor == (0, 0)
            assert buf.block is False
            assert buf.has_selection() is False
            assert buf.has_block_selection() is False

    asyncio.run(scenario())
