"""Runtime tests for the diff viewer screen (DiffScreen / DiffPane).

Pilot-driven (headless Textual): a minimal host app pushes the screen,
then the tests drive navigation, copying, edit mode, saving and the
close guard through real key events.
"""

# tests legitimately poke at screen/pane internals:
# pyright: reportPrivateUsage=false

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Literal, cast

from textual.app import App

from yate.editor_core.diff import DiffHunk, diff_lines
from yate.editor_core.document import Document
from yate.editor_view.diffview import (
    DiffPane,
    DiffScreen,
)
from yate.keymaps.registry import KeymapSet
from yate.keymaps.vim import VimKeymap
from yate.keymaps.vsc import VscKeymap


class _Host(App[None]):
    """Minimal host app that pushes the DiffScreen under test."""

    def __init__(
        self,
        docs: list[Document],
        mode: Literal["2way", "3way"],
        keymaps: KeymapSet,
        labels: list[str],
    ) -> None:
        super().__init__()
        self._docs: list[Document] = docs
        self._mode: Literal["2way", "3way"] = mode
        self._keymaps: KeymapSet = keymaps
        self._labels: list[str] = labels

    def on_mount(self) -> None:
        self.push_screen(DiffScreen(self._docs, self._mode, self._keymaps, self._labels))


def _keymaps(name: str) -> KeymapSet:
    """A KeymapSet carrying both built-in tables, *name* active."""
    return KeymapSet({"vsc": VscKeymap(), "vim": VimKeymap()}, name)


def _make_docs(tmp_path: Path, contents: list[str]) -> list[Document]:
    """Persist *contents* to temp files and open them as Documents."""
    docs: list[Document] = []
    for i, text in enumerate(contents):
        path = tmp_path / f"side{i}.txt"
        path.write_text(text, encoding="utf-8")
        docs.append(Document.open(path))
    return docs


def test_diff_screen_two_way_composes_two_panes(tmp_path: Path) -> None:
    """A 2way screen mounts two panes and finds the single line diff."""

    async def scenario() -> None:
        docs = _make_docs(tmp_path, ["one\ntwo\nthree", "one\nTWO\nthree"])
        app = _Host(docs, "2way", _keymaps("vsc"), ["left", "right"])
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, DiffScreen)
            assert len(screen.query(DiffPane)) == 2
            assert len(screen._regions) == 1

    asyncio.run(scenario())


def test_diff_screen_three_way_composes_three_panes(tmp_path: Path) -> None:
    """A 3way screen mounts three panes and classifies the conflict."""

    async def scenario() -> None:
        docs = _make_docs(tmp_path, ["a\nb\nc", "a\nB\nc", "a\nC\nc"])
        app = _Host(docs, "3way", _keymaps("vsc"), ["base", "local", "remote"])
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, DiffScreen)
            assert len(screen.query(DiffPane)) == 3
            assert any(r.kind == "conflict" for r in screen._regions)

    asyncio.run(scenario())


def test_alt_down_steps_hunk_and_scrolls_panes(tmp_path: Path) -> None:
    """alt+down steps hunks in order, clamps at the tail and hints."""

    async def scenario() -> None:
        docs = _make_docs(tmp_path, ["a\nb\nc\nd\ne", "A\nb\nC\nd\nE"])
        app = _Host(docs, "2way", _keymaps("vsc"), ["left", "right"])
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, DiffScreen)
            panes = list(screen.query(DiffPane))
            assert screen._current == -1
            await pilot.press("alt+down")
            assert screen._current == 0
            # first difference starts at row 0: both panes sit on top
            assert panes[0].scroll_offset.y == 0
            assert panes[1].scroll_offset.y == 0
            await pilot.press("alt+down", "alt+down")
            assert screen._current == 2
            await pilot.press("alt+down")
            assert screen._current == 2
            assert "no next change" in screen._hint_text()

    asyncio.run(scenario())


def test_alt_up_steps_back_and_clamps_at_first_hunk(tmp_path: Path) -> None:
    """alt+up steps back through hunks and clamps at the first one."""

    async def scenario() -> None:
        docs = _make_docs(tmp_path, ["a\nb\nc\nd\ne", "A\nb\nC\nd\nE"])
        app = _Host(docs, "2way", _keymaps("vsc"), ["left", "right"])
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, DiffScreen)
            await pilot.press("alt+down", "alt+down")
            assert screen._current == 1
            await pilot.press("alt+up")
            assert screen._current == 0
            await pilot.press("alt+up")
            assert screen._current == 0  # clamped, no wrap-around
            assert "no previous change" in screen._hint_text()

    asyncio.run(scenario())


def test_alt_right_copies_hunk_and_diff_recomputes(tmp_path: Path) -> None:
    """alt+right applies the left side's lines to the right and recomputes."""

    async def scenario() -> None:
        docs = _make_docs(tmp_path, ["one\ntwo\nthree", "one\nTWO\nthree"])
        app = _Host(docs, "2way", _keymaps("vsc"), ["left", "right"])
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, DiffScreen)
            await pilot.press("alt+down")  # select the only hunk
            await pilot.press("alt+right")
            assert docs[1].buffer.lines[1] == "two"
            assert screen._regions == []
            assert docs[1].modified

    asyncio.run(scenario())


def test_alt_left_copy_into_readonly_side_refused(tmp_path: Path) -> None:
    """Copying onto a read-only side is refused with a hint, no writes."""

    async def scenario() -> None:
        docs = _make_docs(tmp_path, ["one\ntwo", "one\nTWO"])
        docs[0].buffer.read_only = True
        app = _Host(docs, "2way", _keymaps("vsc"), ["left", "right"])
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, DiffScreen)
            await pilot.press("alt+down")  # select the hunk
            await pilot.press("alt+left")
            assert docs[0].buffer.lines[1] == "two"
            assert "read-only" in screen._hint_text()

    asyncio.run(scenario())


def test_alt_right_3way_copies_local_side_into_remote(tmp_path: Path) -> None:
    """3way alt+right applies the local side's lines onto the remote side."""

    async def scenario() -> None:
        docs = _make_docs(tmp_path, ["a\nb\nc", "a\nB\nc", "a\nC\nc"])
        app = _Host(docs, "3way", _keymaps("vsc"), ["base", "local", "remote"])
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, DiffScreen)
            await pilot.press("alt+down")  # select the conflict region
            assert screen._current == 0
            await pilot.press("alt+right")  # local -> remote
            assert docs[2].buffer.lines == ["a", "B", "c"]

    asyncio.run(scenario())


def test_edit_mode_types_into_focused_buffer(tmp_path: Path) -> None:
    """Edit mode routes typed characters into the focused side's buffer."""

    async def scenario() -> None:
        docs = _make_docs(tmp_path, ["one\ntwo", "one\nTWO"])
        app = _Host(docs, "2way", _keymaps("vsc"), ["left", "right"])
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, DiffScreen)
            pane = screen.query_one("#diff-pane-0", DiffPane)
            await pilot.press("enter")
            assert pane.editing
            await pilot.press("x")
            assert "x" in pane.doc.buffer.lines[pane.buffer.row]
            await asyncio.sleep(0.25)  # cross the debounced recompute window
            # the typed "x" widens the single hunk onto line 0 as well:
            # "xone" vs "one" and "two" vs "TWO" now both differ
            regions = cast(list[DiffHunk], screen._regions)
            assert [(h.a_start, h.a_end) for h in regions] == [(0, 2)]

    asyncio.run(scenario())


def test_edit_mode_esc_returns_to_nav_and_unmapped_key_falls_through(
    tmp_path: Path,
) -> None:
    """Edit-mode escape stays on the screen; q bubbles once to the screen.

    The unmapped key must fall through the pane (R10): it reaches the
    screen's close guard, which warns first and only pops on the second
    press -- so nothing is swallowed and nothing closes silently.
    """

    async def scenario() -> None:
        docs = _make_docs(tmp_path, ["one", "ONE"])
        app = _Host(docs, "2way", _keymaps("vsc"), ["left", "right"])
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, DiffScreen)
            pane = screen.query_one("#diff-pane-0", DiffPane)
            await pilot.press("enter")
            assert pane.editing
            await pilot.press("escape")  # consumed by the pane: back to nav
            assert not pane.editing
            assert app.screen is screen
            await pilot.press("q")  # unmapped in edit tables: falls through
            assert app.screen is screen
            assert "press esc again" in screen._hint_text()
            await pilot.press("escape")  # second press: guarded close
            assert app.screen is not screen

    asyncio.run(scenario())


def test_unsaved_close_requires_second_escape(tmp_path: Path) -> None:
    """With an unsaved side the first escape warns, the second one pops."""

    async def scenario() -> None:
        docs = _make_docs(tmp_path, ["one", "ONE"])
        app = _Host(docs, "2way", _keymaps("vsc"), ["left", "right"])
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, DiffScreen)
            await pilot.press("enter")  # edit mode
            await pilot.press("x")  # one unsaved character
            await pilot.press("escape")  # back to nav (pane-consumed)
            await pilot.press("escape")  # first guard press: warn only
            assert app.screen is screen
            assert "unsaved changes" in screen._hint_text()
            await pilot.press("escape")  # second press: close
            assert app.screen is not screen

    asyncio.run(scenario())


def test_ctrl_s_saves_focused_pane_document(tmp_path: Path) -> None:
    """ctrl+s persists the focused side and clears its modified flag."""

    async def scenario() -> None:
        docs = _make_docs(tmp_path, ["one\ntwo", "one\nTWO"])
        app = _Host(docs, "2way", _keymaps("vsc"), ["left", "right"])
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, DiffScreen)
            await pilot.press("alt+down")
            await pilot.press("alt+right")  # copy: right side becomes dirty
            assert docs[1].modified
            await pilot.press("tab")  # focus the modified (target) side
            await pilot.press("ctrl+s")
            assert "saved" in screen._hint_text()
            assert not docs[1].modified
            path = docs[1].path
            assert path is not None
            assert path.read_text(encoding="utf-8") == "one\ntwo"

    asyncio.run(scenario())


def test_ctrl_z_undoes_copied_side_and_restores_regions(tmp_path: Path) -> None:
    """ctrl+z undoes the focused side's copy; the diff reappears."""

    async def scenario() -> None:
        docs = _make_docs(tmp_path, ["one\ntwo\nthree", "one\nTWO\nthree"])
        app = _Host(docs, "2way", _keymaps("vsc"), ["left", "right"])
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, DiffScreen)
            await pilot.press("alt+down")  # select the only hunk
            await pilot.press("alt+right")  # copy left -> right
            assert docs[1].buffer.lines == ["one", "two", "three"]
            await pilot.press("tab")  # focus the modified (right) side
            await pilot.press("ctrl+z")
            assert docs[1].buffer.lines == ["one", "TWO", "three"]
            assert len(screen._regions) == 1

    asyncio.run(scenario())


def test_vim_keymap_edit_table_moves_with_hjkl(tmp_path: Path) -> None:
    """With the vim keymap active, edit mode maps j to a downward motion."""

    async def scenario() -> None:
        docs = _make_docs(tmp_path, ["r1\nr2\nr3", "r1\nr2\nr3"])
        app = _Host(docs, "2way", _keymaps("vim"), ["left", "right"])
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, DiffScreen)
            pane = screen.query_one("#diff-pane-0", DiffPane)
            await pilot.press("enter")  # edit mode with the vim table
            assert pane.editing
            assert pane.buffer.cursor[0] == 0
            await pilot.press("j")
            assert pane.buffer.cursor[0] == 1

    asyncio.run(scenario())


def test_vim_append_at_eol_stays_on_line(tmp_path: Path) -> None:
    """vim ``a`` at end of line inserts there instead of spilling to the next.

    The main vim keymap relies on ``set_cursor`` clamping the column; the
    ``move_right`` used here before would wrap onto the next row at EOL.
    """

    async def scenario() -> None:
        docs = _make_docs(tmp_path, ["r1\nr2\nr3", "r1\nr2\nr3"])
        app = _Host(docs, "2way", _keymaps("vim"), ["left", "right"])
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, DiffScreen)
            pane = screen.query_one("#diff-pane-0", DiffPane)
            await pilot.press("enter")  # edit mode with the vim table
            await pilot.press("$")  # end of line 0
            await pilot.press("a")  # append: clamped, no wrap
            await pilot.press("X")
            assert pane.buffer.lines[0] == "r1X"
            assert pane.buffer.cursor[0] == 0

    asyncio.run(scenario())


def test_vim_normal_e_moves_word_end_and_q_is_inert(tmp_path: Path) -> None:
    """vim normal ``e`` lands on the word end; ``q`` stays inert (backlog S3).

    Unmapped, both keys fell through to the screen bindings: ``e`` toggled
    edit mode off and ``q`` armed the close guard -- vim muscle-memory traps.
    """

    async def scenario() -> None:
        docs = _make_docs(tmp_path, ["one two\nthree", "one two\nthree"])
        app = _Host(docs, "2way", _keymaps("vim"), ["left", "right"])
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, DiffScreen)
            pane = screen.query_one("#diff-pane-0", DiffPane)
            await pilot.press("enter")  # vim normal
            assert pane.editing
            await pilot.press("e")
            assert pane.editing  # did not toggle edit mode off
            assert pane.buffer.cursor == (0, 2)  # word end of "one"
            await pilot.press("q")
            assert pane.editing
            assert "press esc again" not in screen._hint_text()
            assert app.screen is screen

    asyncio.run(scenario())


def test_debounced_recompute_applies_burst(tmp_path: Path) -> None:
    """Rapid keystrokes collapse into one recompute after the window.

    Both typed characters must land, and once the debounced recompute
    fires the screen's regions must equal a fresh L0 diff of the buffers.
    """

    async def scenario() -> None:
        docs = _make_docs(tmp_path, ["one\ntwo", "one\nTWO"])
        app = _Host(docs, "2way", _keymaps("vsc"), ["left", "right"])
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, DiffScreen)
            pane = screen.query_one("#diff-pane-0", DiffPane)
            await pilot.press("enter")  # edit mode
            await pilot.press("x", "y")  # burst: two PaneChanged messages
            await asyncio.sleep(0.3)  # > RECOMPUTE_DEBOUNCE_SECONDS
            await pilot.pause()
            line = pane.doc.buffer.lines[pane.buffer.row]
            assert "x" in line and "y" in line
            regions = cast(list[DiffHunk], screen._regions)
            fresh = diff_lines(docs[0].buffer.lines, docs[1].buffer.lines)
            assert [(h.a_start, h.a_end, h.b_start, h.b_end) for h in regions] == [
                (h.a_start, h.a_end, h.b_start, h.b_end) for h in fresh.hunks
            ]

    asyncio.run(scenario())
