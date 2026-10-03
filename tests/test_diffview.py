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

import pytest
from textual.app import App
from textual.events import Key

from yate.editor_core.diff import DiffHunk, MergeRegion, diff_lines
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


def _line_states(pane: DiffPane) -> tuple[str, ...]:
    """Line states of *pane*'s current render state (None-narrowing helper)."""
    state = pane._state
    assert state is not None
    return state.line_states


def _current_rows(pane: DiffPane) -> frozenset[int]:
    """Currently highlighted rows of *pane*'s render state."""
    state = pane._state
    assert state is not None
    return state.current_rows


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


def test_screen_rejects_wrong_document_count(tmp_path: Path) -> None:
    """A screen built with the wrong document count raises ValueError."""
    docs = _make_docs(tmp_path, ["a", "b", "c"])
    with pytest.raises(ValueError):
        DiffScreen(docs[:1], "2way", _keymaps("vsc"), ["left"])
    with pytest.raises(ValueError):
        DiffScreen(docs, "2way", _keymaps("vsc"), ["left", "right"])
    with pytest.raises(ValueError):
        DiffScreen(docs[:2], "3way", _keymaps("vsc"), ["base", "local"])


def test_navigation_without_differences_hints_no_differences(
    tmp_path: Path,
) -> None:
    """alt+up/alt+down on identical sides hint there is nothing to visit."""

    async def scenario() -> None:
        docs = _make_docs(tmp_path, ["same\nlines", "same\nlines"])
        app = _Host(docs, "2way", _keymaps("vsc"), ["left", "right"])
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, DiffScreen)
            await pilot.press("alt+up")
            assert screen._current == -1
            assert "no differences" in screen._hint_text()
            await pilot.press("alt+down")
            assert screen._current == -1
            assert "no differences" in screen._hint_text()

    asyncio.run(scenario())


def test_copy_without_selected_change_hints_and_skips(tmp_path: Path) -> None:
    """alt+right with no selected change only hints; buffers stay untouched."""

    async def scenario() -> None:
        docs = _make_docs(tmp_path, ["one\ntwo", "one\nTWO"])
        app = _Host(docs, "2way", _keymaps("vsc"), ["left", "right"])
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, DiffScreen)
            await pilot.press("alt+right")
            assert "no change selected" in screen._hint_text()
            assert docs[1].buffer.lines == ["one", "TWO"]

    asyncio.run(scenario())


def test_focus_keys_move_focus_between_panes(tmp_path: Path) -> None:
    """shift+tab cycles focus backwards; ctrl+1 focuses pane 1 directly."""

    async def scenario() -> None:
        docs = _make_docs(tmp_path, ["one", "one"])
        app = _Host(docs, "2way", _keymaps("vsc"), ["left", "right"])
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, DiffScreen)
            panes = list(screen.query(DiffPane))
            await pilot.press("shift+tab")
            assert screen._focused_pane() is panes[1]
            await pilot.press("ctrl+1")
            assert screen._focused_pane() is panes[0]
            await pilot.press("ctrl+3")  # out of range in a 2way screen
            assert screen._focused_pane() is panes[0]

    asyncio.run(scenario())


def test_insert_hunk_marks_added_rows_on_right_side(tmp_path: Path) -> None:
    """An insert-type hunk paints right-side rows as added, left as same."""

    async def scenario() -> None:
        docs = _make_docs(tmp_path, ["a\nc", "a\nb\nc"])
        app = _Host(docs, "2way", _keymaps("vsc"), ["left", "right"])
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, DiffScreen)
            panes = list(screen.query(DiffPane))
            regions = cast(list[DiffHunk], screen._regions)
            assert [h.kind for h in regions] == ["insert"]
            assert _line_states(panes[0]) == ("same", "same")
            assert _line_states(panes[1]) == ("same", "added", "same")
            assert _current_rows(panes[0]) == frozenset()

    asyncio.run(scenario())


def test_delete_hunk_marks_removed_rows_on_left_side(tmp_path: Path) -> None:
    """A delete-type hunk paints left-side rows as removed, right as same."""

    async def scenario() -> None:
        docs = _make_docs(tmp_path, ["a\nb\nc", "a\nc"])
        app = _Host(docs, "2way", _keymaps("vsc"), ["left", "right"])
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, DiffScreen)
            panes = list(screen.query(DiffPane))
            regions = cast(list[DiffHunk], screen._regions)
            assert [h.kind for h in regions] == ["delete"]
            assert _line_states(panes[0]) == ("same", "removed", "same")
            assert _line_states(panes[1]) == ("same", "same")

    asyncio.run(scenario())


def test_3way_local_only_region_keeps_remote_side_plain(tmp_path: Path) -> None:
    """A one-sided merge change tints base+local and leaves remote same."""

    async def scenario() -> None:
        docs = _make_docs(tmp_path, ["a\nb\nc", "a\nB\nc", "a\nb\nc"])
        app = _Host(docs, "3way", _keymaps("vsc"), ["base", "local", "remote"])
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, DiffScreen)
            panes = list(screen.query(DiffPane))
            assert any(r.kind == "local" for r in screen._regions)
            assert _line_states(panes[0]) == ("same", "changed", "same")
            assert _line_states(panes[1]) == ("same", "changed", "same")
            assert _line_states(panes[2]) == ("same", "same", "same")

    asyncio.run(scenario())


def test_3way_identical_both_region_copy_hints_nothing_to_copy(
    tmp_path: Path,
) -> None:
    """Copying a region whose sides already match reports nothing to copy."""

    async def scenario() -> None:
        docs = _make_docs(tmp_path, ["a\nb\nc", "a\nB\nc", "a\nB\nc"])
        app = _Host(docs, "3way", _keymaps("vsc"), ["base", "local", "remote"])
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, DiffScreen)
            await pilot.press("alt+down")  # select the "both" region
            assert screen._current == 0
            await pilot.press("alt+right")  # local -> remote, already equal
            assert "nothing to copy" in screen._hint_text()
            assert not docs[2].modified

    asyncio.run(scenario())


def test_states_2way_identical_replace_pair_yields_no_inline(
    tmp_path: Path,
) -> None:
    """A replace hunk over identical lines yields no inline highlight spans.

    ``diff_words`` returns empty ranges for identical lines, so both sides
    skip their inline assignment -- the empty word-diff branch guards.
    """

    async def scenario() -> None:
        docs = _make_docs(tmp_path, ["same\ntail", "same\ntail"])
        app = _Host(docs, "2way", _keymaps("vsc"), ["left", "right"])
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, DiffScreen)
            screen._regions = [DiffHunk("replace", 0, 1, 0, 1)]
            screen._current = 0
            states = screen._states_2way()
            assert states[0].inline == {}
            assert states[1].inline == {}
            assert states[0].line_states[0] == "changed"
            assert states[0].current_rows == frozenset({0})

    asyncio.run(scenario())


def test_states_3way_ignores_non_merge_region_selection(tmp_path: Path) -> None:
    """A non-MergeRegion in the 3way region list selects nothing (guard)."""

    async def scenario() -> None:
        docs = _make_docs(tmp_path, ["a\nb", "a\nb", "a\nb"])
        app = _Host(docs, "3way", _keymaps("vsc"), ["base", "local", "remote"])
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, DiffScreen)
            screen._regions = [DiffHunk("replace", 0, 0, 0, 0)]
            screen._current = 0
            states = screen._states_3way()
            assert len(states) == 3
            assert all(state.current_rows == frozenset() for state in states)

    asyncio.run(scenario())


def test_copy_2way_ignores_non_hunk_region(tmp_path: Path) -> None:
    """A non-DiffHunk region makes 2way copy a no-op (type guard)."""

    async def scenario() -> None:
        docs = _make_docs(tmp_path, ["one\ntwo", "one\nTWO"])
        app = _Host(docs, "2way", _keymaps("vsc"), ["left", "right"])
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, DiffScreen)
            screen._regions = [MergeRegion("same", 0, 0, 0, 0, 0, 0)]
            screen._current = 0
            screen._copy(1)
            assert docs[1].buffer.lines == ["one", "TWO"]
            assert screen._hint_text() == ""

    asyncio.run(scenario())


def test_copy_3way_ignores_non_merge_region(tmp_path: Path) -> None:
    """A non-MergeRegion region makes 3way copy a no-op (type guard)."""

    async def scenario() -> None:
        docs = _make_docs(tmp_path, ["a\nb", "a\nB", "a\nb"])
        app = _Host(docs, "3way", _keymaps("vsc"), ["base", "local", "remote"])
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, DiffScreen)
            screen._regions = [DiffHunk("replace", 0, 1, 0, 1)]
            screen._current = 0
            screen._copy(1)
            assert docs[2].buffer.lines == ["a", "b"]
            assert screen._hint_text() == ""

    asyncio.run(scenario())


def test_actions_without_panes_or_focus_are_noops(tmp_path: Path) -> None:
    """Edit/save/undo/focus actions skip work when no pane is available."""

    async def scenario() -> None:
        docs = _make_docs(tmp_path, ["one\ntwo", "one\nTWO"])
        app = _Host(docs, "2way", _keymaps("vsc"), ["left", "right"])
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, DiffScreen)
            screen.set_focus(None)
            assert screen._focused_pane() is None
            screen.action_toggle_edit()
            assert all(not pane.editing for pane in screen.query(DiffPane))
            screen.action_save_pane()
            screen.action_undo_pane()
            assert screen._hint_text() == ""
            assert docs[1].buffer.lines == ["one", "TWO"]
            screen._panes = []
            screen.action_cycle_focus_next()  # empty-panes guard
            assert screen._focused_pane() is None

    asyncio.run(scenario())


def test_read_only_side_refuses_edit_and_save_with_hint(tmp_path: Path) -> None:
    """A read-only side refuses edit mode and ctrl+s, both with a hint."""

    async def scenario() -> None:
        docs = _make_docs(tmp_path, ["one\ntwo", "one\nTWO"])
        docs[0].buffer.read_only = True
        app = _Host(docs, "2way", _keymaps("vsc"), ["left", "right"])
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, DiffScreen)
            pane = screen.query_one("#diff-pane-0", DiffPane)
            await pilot.press("enter")  # toggle edit on the read-only side
            assert not pane.editing
            assert "read-only" in screen._hint_text()
            await pilot.press("ctrl+s")  # saving is refused as well
            assert "read-only" in screen._hint_text()
            assert not docs[0].modified

    asyncio.run(scenario())


def test_save_io_failure_reports_error_hint(tmp_path: Path) -> None:
    """A save that fails on I/O reports the OS error as a hint."""

    async def scenario() -> None:
        docs = _make_docs(tmp_path, ["one\ntwo", "one\nTWO"])
        app = _Host(docs, "2way", _keymaps("vsc"), ["left", "right"])
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, DiffScreen)
            docs[1].path = tmp_path / "no-such-dir" / "out.txt"
            await pilot.press("tab")  # focus the right side
            await pilot.press("ctrl+s")
            assert "save failed" in screen._hint_text()
            assert not docs[1].modified  # nothing was written

    asyncio.run(scenario())


def test_undo_read_only_side_reports_hint(tmp_path: Path) -> None:
    """ctrl+z on a read-only side reports the refusal; the buffer is intact."""

    async def scenario() -> None:
        docs = _make_docs(tmp_path, ["one\ntwo", "one\nTWO"])
        docs[0].buffer.read_only = True
        app = _Host(docs, "2way", _keymaps("vsc"), ["left", "right"])
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, DiffScreen)
            await pilot.press("ctrl+z")
            assert "read-only" in screen._hint_text()
            assert docs[0].buffer.lines == ["one", "two"]

    asyncio.run(scenario())


def test_vsc_edit_ctrl_z_undoes_typed_character(tmp_path: Path) -> None:
    """ctrl+z inside vsc edit mode undoes the pane's last keystroke."""

    async def scenario() -> None:
        docs = _make_docs(tmp_path, ["one\ntwo", "one\nTWO"])
        app = _Host(docs, "2way", _keymaps("vsc"), ["left", "right"])
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, DiffScreen)
            pane = screen.query_one("#diff-pane-0", DiffPane)
            await pilot.press("enter")
            await pilot.press("x")
            assert pane.buffer.lines[0] == "xone"
            await pilot.press("ctrl+z")
            assert pane.buffer.lines[0] == "one"
            assert pane.editing  # undo keeps edit mode

    asyncio.run(scenario())


def test_vsc_edit_unmapped_key_falls_through_to_screen(tmp_path: Path) -> None:
    """A non-printable key missing from the vsc table falls through (R10)."""

    async def scenario() -> None:
        docs = _make_docs(tmp_path, ["one", "ONE"])
        app = _Host(docs, "2way", _keymaps("vsc"), ["left", "right"])
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, DiffScreen)
            pane = screen.query_one("#diff-pane-0", DiffPane)
            await pilot.press("enter")
            await pilot.press("f1")  # not in the table, not printable
            assert pane.editing
            assert pane.buffer.lines == ["one"]
            await pilot.press("escape")  # pane-consumed: back to nav
            await pilot.press("q")  # reaches the screen close guard
            assert "press esc again" in screen._hint_text()

    asyncio.run(scenario())


def test_vim_dd_deletes_line_and_mismatch_cancels_chord(tmp_path: Path) -> None:
    """vim ``dd`` deletes the current line; ``d`` plus another key cancels."""

    async def scenario() -> None:
        docs = _make_docs(tmp_path, ["r1\nr2\nr3", "r1\nr2\nr3"])
        app = _Host(docs, "2way", _keymaps("vim"), ["left", "right"])
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, DiffScreen)
            pane = screen.query_one("#diff-pane-0", DiffPane)
            await pilot.press("enter")  # vim normal
            await pilot.press("d")
            assert pane.pending_d
            await pilot.press("d")
            assert pane.buffer.lines == ["r2", "r3"]
            assert not pane.pending_d
            await pilot.press("d")  # arm the chord again...
            await pilot.press("j")  # ...but j cancels it and moves down
            assert pane.buffer.lines == ["r2", "r3"]
            assert pane.buffer.row == 1
            assert not pane.pending_d

    asyncio.run(scenario())


def test_vim_i_enters_insert_and_escape_returns_to_normal(tmp_path: Path) -> None:
    """vim ``i`` enters the insert sub-mode; escape leaves normal untouched."""

    async def scenario() -> None:
        docs = _make_docs(tmp_path, ["r1\nr2", "r1\nr2"])
        app = _Host(docs, "2way", _keymaps("vim"), ["left", "right"])
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, DiffScreen)
            pane = screen.query_one("#diff-pane-0", DiffPane)
            await pilot.press("enter")
            await pilot.press("i")
            assert pane.vim_insert
            await pilot.press("escape")  # insert escape: normal sub-mode only
            assert pane.editing
            assert not pane.vim_insert
            await pilot.press("enter")  # miss in vim normal: screen exits edit
            assert not pane.editing

    asyncio.run(scenario())


def test_vim_insert_enter_backspace_and_miss_fall_through(
    tmp_path: Path,
) -> None:
    """In vim insert, enter/backspace edit lines and a miss falls through."""

    async def scenario() -> None:
        docs = _make_docs(tmp_path, ["r1\nr2", "r1\nr2"])
        app = _Host(docs, "2way", _keymaps("vim"), ["left", "right"])
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, DiffScreen)
            pane = screen.query_one("#diff-pane-0", DiffPane)
            await pilot.press("enter")  # vim normal
            await pilot.press("i")  # insert sub-mode at the cursor
            await pilot.press("X")
            assert pane.buffer.lines[0] == "Xr1"
            await pilot.press("enter")  # insert-table hit: split the line
            assert pane.buffer.lines == ["X", "r1", "r2"]
            await pilot.press("backspace")  # join it back
            assert pane.buffer.lines == ["Xr1", "r2"]
            await pilot.press("f1")  # not printable, not in the insert table
            assert pane.vim_insert
            assert pane.editing
            assert pane.buffer.lines == ["Xr1", "r2"]

    asyncio.run(scenario())


def test_vim_o_opens_line_below_in_insert_mode(tmp_path: Path) -> None:
    """vim ``o`` opens a line below and lands in the insert sub-table."""

    async def scenario() -> None:
        docs = _make_docs(tmp_path, ["r1\nr2", "r1\nr2"])
        app = _Host(docs, "2way", _keymaps("vim"), ["left", "right"])
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, DiffScreen)
            pane = screen.query_one("#diff-pane-0", DiffPane)
            await pilot.press("enter")
            await pilot.press("o")
            assert pane.vim_insert
            await pilot.press("X")
            assert pane.buffer.lines == ["r1", "X", "r2"]
            assert pane.buffer.cursor == (1, 1)

    asyncio.run(scenario())


def test_vim_e_after_last_word_end_is_noop(tmp_path: Path) -> None:
    """vim ``e`` at the line's last word end stays put (in-line subset)."""

    async def scenario() -> None:
        docs = _make_docs(tmp_path, ["abc\ntwo", "abc\ntwo"])
        app = _Host(docs, "2way", _keymaps("vim"), ["left", "right"])
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, DiffScreen)
            pane = screen.query_one("#diff-pane-0", DiffPane)
            await pilot.press("enter")
            await pilot.press("e")
            assert pane.buffer.cursor == (0, 2)
            await pilot.press("e")  # no further word end on this line
            assert pane.buffer.cursor == (0, 2)
            assert pane.editing

    asyncio.run(scenario())


def test_vim_normal_unmapped_key_falls_through_to_screen(tmp_path: Path) -> None:
    """A non-printable key missing from the vim table falls through (R10)."""

    async def scenario() -> None:
        docs = _make_docs(tmp_path, ["one", "ONE"])
        app = _Host(docs, "2way", _keymaps("vim"), ["left", "right"])
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, DiffScreen)
            pane = screen.query_one("#diff-pane-0", DiffPane)
            await pilot.press("enter")
            await pilot.press("f1")  # miss: falls through, nothing happens
            assert pane.editing
            assert pane.buffer.lines == ["one"]
            await pilot.press("escape")  # pane-consumed: back to nav
            await pilot.press("q")  # reaches the screen close guard
            assert "press esc again" in screen._hint_text()

    asyncio.run(scenario())


def test_pane_reveal_cursor_scrolls_up_when_cursor_above_view(
    tmp_path: Path,
) -> None:
    """An edit key reveals a cursor scrolled above the view (scrolls up)."""

    async def scenario() -> None:
        text = "\n".join(f"line{i}" for i in range(60))
        docs = _make_docs(tmp_path, [text, text])
        app = _Host(docs, "2way", _keymaps("vsc"), ["left", "right"])
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, DiffScreen)
            pane = screen.query_one("#diff-pane-0", DiffPane)
            await pilot.press("enter")  # edit mode
            pane.scroll_to(y=20, animate=False)
            await pilot.pause()
            pane.buffer.set_cursor((0, 0))
            await pilot.press("home")  # consumed: reveals the cursor row
            assert pane.scroll_offset.y == 0

    asyncio.run(scenario())


def test_pane_reveal_cursor_scrolls_down_when_cursor_below_view(
    tmp_path: Path,
) -> None:
    """An edit key reveals a cursor scrolled below the view (scrolls down)."""

    async def scenario() -> None:
        text = "\n".join(f"line{i}" for i in range(60))
        docs = _make_docs(tmp_path, [text, text])
        app = _Host(docs, "2way", _keymaps("vsc"), ["left", "right"])
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, DiffScreen)
            pane = screen.query_one("#diff-pane-0", DiffPane)
            await pilot.press("enter")  # edit mode
            pane.buffer.set_cursor((55, 0))
            expected = 55 - pane.size.height + 1
            await pilot.press("end")  # consumed: reveals the cursor row
            assert pane.scroll_offset.y == expected

    asyncio.run(scenario())


def test_pane_render_line_without_state_paints_plain_row(tmp_path: Path) -> None:
    """Rendering before any diff state falls back to the plain same row."""

    async def scenario() -> None:
        docs = _make_docs(tmp_path, ["one\ntwo", "one\ntwo"])
        app = _Host(docs, "2way", _keymaps("vsc"), ["left", "right"])
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, DiffScreen)
            pane = screen.query_one("#diff-pane-0", DiffPane)
            pane._state = None
            strip = pane.render_line(0)
            assert "one" in strip.text

    asyncio.run(scenario())


def test_pane_render_line_handles_wide_and_oversized_lines(
    tmp_path: Path,
) -> None:
    """Wide glyphs render a spacer cell; overlong lines fill without padding."""

    async def scenario() -> None:
        text = "中文X\n" + "a" * 200
        docs = _make_docs(tmp_path, [text, text])
        app = _Host(docs, "2way", _keymaps("vsc"), ["left", "right"])
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, DiffScreen)
            pane = screen.query_one("#diff-pane-0", DiffPane)
            wide = pane.render_line(0)
            assert "中" in wide.text
            long_strip = pane.render_line(1)
            assert len(long_strip.text) == pane.size.width
            text_w = pane.size.width - pane._gutter_width()
            assert "a" * text_w in long_strip.text

    asyncio.run(scenario())


def test_pane_unmount_without_theme_subscription_is_safe() -> None:
    """Unmounting a pane that never subscribed is a no-op (guard branch)."""
    pane = DiffPane(Document(), "solo")
    pane.on_unmount()
    assert pane._theme_unsubscribe is None


def test_edit_key_with_no_table_is_a_miss() -> None:
    """Edit-key handling without a table reports a miss (guard branch)."""
    pane = DiffPane(Document(), "solo")
    pane.editing = True
    pane._edit_table = None
    assert pane._handle_edit_key(Key("f1", None)) is False
