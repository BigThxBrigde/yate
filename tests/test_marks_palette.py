"""Pilot smoke tests for the marks / jumps overview palette screens.

Drives the real ``YateApp`` headless through the L3 ``NavigationFlows``
push verbs (the same path ``alt+m`` / ``:marks`` / ``:jumps`` take):
marks and jump rows render with their columns, the on-key cursor steps,
enter jumps the editor to the selected row, ``d`` deletes a mark in
place, and keys the screens do not consume neither double-dispatch into
the editor below nor close the screen (R10, palette precedent).
"""

from __future__ import annotations

import asyncio
from typing import cast

from textual.app import App
from textual.widgets import Static

from yate.app import YateApp
from yate.editor_components.marks_palette import (
    JumpRow,
    JumpsScreen,
    MarkRow,
    MarksScreen,
)

from conftest import plain_text, wait_until


def _body_text(screen: MarksScreen | JumpsScreen) -> str:
    """The overview body as plain text, as painted into ``#overlay-body``."""
    return plain_text(screen.query_one("#overlay-body", Static).content)


def _row_line(screen: JumpsScreen, side: str) -> str:
    """The painted line of the *side* row (caret prefix stripped away)."""
    return next(
        line
        for line in _body_text(screen).splitlines()
        if line.lstrip("> ").startswith(side)
    )


def _seed_marks(app: YateApp, marks: dict[str, tuple[int, int]]) -> int:
    """Give the startup buffer four lines, set marks on it, return its uid."""
    session = app.editor.session
    session.buffer.insert_text("alpha\nbeta\ngamma\n")
    uid = session.doc.uid
    for name, (row, col) in marks.items():
        session.marks.set(uid, name, row, col)
    return uid


def test_marks_screen_renders_name_line_and_preview_columns() -> None:
    """Two session marks paint as rows with name, line number and preview."""
    async def scenario() -> None:
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            uid = _seed_marks(app, {"a": (1, 0), "b": (2, 2)})
            app.editor.navigation_flows.show_marks()
            assert await wait_until(
                pilot, lambda: isinstance(app.screen, MarksScreen)
            )
            screen = cast(MarksScreen, app.screen)
            # one 1-based row per mark, ordered by name
            assert [(r.uid, r.name, r.line_no, r.preview) for r in screen.rows] == [
                (uid, "a", 2, "beta"),
                (uid, "b", 3, "gamma"),
            ]
            lines = _body_text(screen).splitlines()
            # the column header and the scratch-buffer doc name are painted
            assert lines[0].lstrip().startswith("NAME")
            assert "DOC" in lines[0] and "LINE" in lines[0] and "TEXT" in lines[0]
            assert "[no name]" in _body_text(screen)
            # first row carries the selection caret, the second does not
            assert lines[1].startswith(" > ") and lines[1].rstrip().endswith("beta")
            assert lines[2].startswith("   ") and lines[2].rstrip().endswith("gamma")

    asyncio.run(scenario())


def test_marks_screen_enter_jumps_to_mark_and_closes() -> None:
    """Enter on the selected row lands the cursor on the mark and dismisses."""
    async def scenario() -> None:
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            session = app.editor.session
            _seed_marks(app, {"a": (1, 0), "b": (2, 1)})
            app.editor.navigation_flows.show_marks()
            assert await wait_until(
                pilot, lambda: isinstance(app.screen, MarksScreen)
            )
            # step onto the second row, then jump through enter
            await pilot.press("down")
            await pilot.press("enter")
            assert await wait_until(
                pilot, lambda: not isinstance(app.screen, MarksScreen)
            )
            assert session.doc.buffer.cursor == (2, 1)

    asyncio.run(scenario())


def test_marks_screen_d_deletes_selected_mark_in_place() -> None:
    """``d`` removes the selected mark from the session and the palette."""
    async def scenario() -> None:
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            session = app.editor.session
            uid = _seed_marks(app, {"a": (1, 0), "b": (2, 0)})
            app.editor.navigation_flows.show_marks()
            assert await wait_until(
                pilot, lambda: isinstance(app.screen, MarksScreen)
            )
            screen = cast(MarksScreen, app.screen)
            await pilot.press("d")
            await pilot.pause()
            # the mark is gone from the session and from the painted rows
            assert session.marks.get(uid, "a") is None
            assert [r.name for r in screen.rows] == ["b"]
            assert await wait_until(
                pilot, lambda: "alpha" not in _body_text(screen)
            )
            # deleting the last row empties the palette; the screen stays open
            await pilot.press("d")
            assert await wait_until(
                pilot,
                lambda: "(no marks)" in _body_text(screen),
            )
            assert session.marks.all_marks() == []
            assert screen.rows == []
            # d / enter on empty rows are both no-ops: the screen stays open
            await pilot.press("d")
            await pilot.press("enter")
            await pilot.pause()
            assert isinstance(app.screen, MarksScreen)
            # esc closes the empty palette
            await pilot.press("escape")
            assert await wait_until(
                pilot, lambda: not isinstance(app.screen, MarksScreen)
            )

    asyncio.run(scenario())


def test_jumps_screen_renders_back_stack_and_current_row() -> None:
    """A pushed origin renders as a back row; the live cursor as current."""
    async def scenario() -> None:
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            session = app.editor.session
            session.buffer.insert_text("alpha\nbeta\ngamma\n")
            session.buffer.set_cursor((1, 0))
            session.push_jump()
            session.buffer.set_cursor((2, 1))
            app.editor.navigation_flows.show_jumps()
            assert await wait_until(
                pilot, lambda: isinstance(app.screen, JumpsScreen)
            )
            screen = cast(JumpsScreen, app.screen)
            # the back stack first, then the current pointer (no forward yet)
            assert [r.side for r in screen.rows] == ["back", "current"]
            back, forward = session.jumps.stacks()
            assert forward == []
            assert screen.rows[0].entry == back[0]
            assert screen.rows[1].entry.row == 2
            assert screen.rows[1].entry.col == 1
            lines = _body_text(screen).splitlines()
            assert lines[0].lstrip().startswith("STACK")
            assert "DOC" in lines[0] and "LINE" in lines[0] and "COL" in lines[0]
            # the back row shows the 1-based origin (line 2, col 1) ...
            back_line = _row_line(screen, "back")
            assert back_line.startswith(" > ")
            assert back_line.rstrip().endswith("2  1")
            # ... and the current row shows the live cursor (line 3, col 2)
            current_line = _row_line(screen, "current")
            assert current_line.startswith(" > ")
            assert current_line.rstrip().endswith("3  2")
            # enter on the selected back row jumps to the recorded origin
            await pilot.press("enter")
            assert await wait_until(
                pilot, lambda: not isinstance(app.screen, JumpsScreen)
            )
            assert session.doc.buffer.cursor == (1, 0)

    asyncio.run(scenario())


def test_jumps_screen_steps_selection_and_ignores_unconsumed_keys() -> None:
    """Up/down move the caret; stray keys neither dispatch nor close it."""
    async def scenario() -> None:
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            session = app.editor.session
            session.buffer.insert_text("alpha\nbeta\ngamma\n")
            session.buffer.set_cursor((1, 0))
            session.push_jump()
            session.buffer.set_cursor((2, 1))
            app.editor.navigation_flows.show_jumps()
            assert await wait_until(
                pilot, lambda: isinstance(app.screen, JumpsScreen)
            )
            screen = cast(JumpsScreen, app.screen)
            # row 0 (the back entry) is selected initially
            assert _row_line(screen, "back").startswith(" > ")
            await pilot.press("down")
            assert await wait_until(
                pilot, lambda: _row_line(screen, "back").startswith("   ")
            )
            await pilot.press("up")
            assert await wait_until(
                pilot, lambda: _row_line(screen, "back").startswith(" > ")
            )
            # an unconsumed key must not fall through into the editor below:
            # the screen stays open and nothing moved (R10)
            await pilot.press("z")
            await pilot.pause()
            assert isinstance(app.screen, JumpsScreen)
            assert session.doc.buffer.cursor == (2, 1)
            # enter on the current row is a no-op (the editor is already there)
            await pilot.press("down")
            await pilot.press("enter")
            await pilot.pause()
            assert isinstance(app.screen, JumpsScreen)
            # esc closes the screen; the cursor is untouched by the whole tour
            await pilot.press("escape")
            assert await wait_until(
                pilot, lambda: not isinstance(app.screen, JumpsScreen)
            )
            assert session.doc.buffer.cursor == (2, 1)
            assert len(screen.rows) == 2

    asyncio.run(scenario())


def test_empty_screens_render_placeholders_and_ignore_actions() -> None:
    """With no rows both screens paint a placeholder and swallow actions."""
    deleted: list[MarkRow] = []
    marks_jumped: list[MarkRow] = []
    jumped: list[JumpRow] = []

    class _Host(App[None]):
        """Minimal host app that pushes the palette screen under test."""

        def __init__(self, screen: MarksScreen | JumpsScreen) -> None:
            super().__init__()
            self._screen = screen

        def on_mount(self) -> None:
            self.push_screen(self._screen)

    async def scenario() -> None:
        marks = MarksScreen([], marks_jumped.append, deleted.append)
        app = _Host(marks)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            assert "(no marks)" in _body_text(marks)
            await pilot.press("d")
            await pilot.press("enter")
            await pilot.pause()
            # both actions are no-ops: nothing recorded, the screen stays open
            assert deleted == [] and marks_jumped == [] and jumped == []
            assert app.screen is marks
            await pilot.press("escape")
            assert await wait_until(pilot, lambda: app.screen is not marks)

        empty = JumpsScreen([], jumped.append)
        app = _Host(empty)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            assert "(no jumps)" in _body_text(empty)
            await pilot.press("enter")
            await pilot.pause()
            assert jumped == []
            assert app.screen is empty
            await pilot.press("escape")
            assert await wait_until(pilot, lambda: app.screen is not empty)

    asyncio.run(scenario())
