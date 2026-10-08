"""Split panes / window focus headless Textual UI tests (run via pilot, no real terminal)."""

# tests legitimately poke at internals:
# pyright: reportPrivateUsage=false

from __future__ import annotations

import asyncio
import contextlib
from pathlib import Path
from typing import Any, cast
import pytest
from textual.events import MouseMove, MouseUp
from yate.app import YateApp
from yate.editor_view.editor import EditorView
from yate.session import Split as PaneSplit
from yate.session import leaves as pane_leaves
from conftest import message_text, wait_until

# --------------------------------------- window focus / pane focus switching


@pytest.fixture
def pane_root(tmp_path: Path) -> Path:
    """Workspace root pre-seeded with the files the pane tests open."""
    (tmp_path / "alpha.txt").write_text(
        "alpha\nbeta\ngamma\n", encoding="utf-8")
    (tmp_path / "bravo.txt").write_text(
        "bravo one\nbravo two\n", encoding="utf-8")
    return tmp_path


def test_vsc_chords_focus_panes(pane_root: Path) -> None:
    async def scenario() -> None:
        app = YateApp(target=pane_root)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            # initial focus is the editor; ctrl+shift+e moves to the explorer
            assert app.focused is app.editor.panes.active_view
            await pilot.press("ctrl+shift+e")
            await pilot.pause()
            assert app.focused is app.editor.explorer_tree
            # vscode-style: ctrl+1 focuses the editor again
            await pilot.press("ctrl+1")
            await pilot.pause()
            assert app.focused is app.editor.panes.active_view
            # ... and ctrl+shift+e focuses the explorer once more
            await pilot.press("ctrl+shift+e")
            await pilot.pause()
            assert app.focused is app.editor.explorer_tree
            await pilot.press("ctrl+1")
            await pilot.pause()
            assert app.focused is app.editor.panes.active_view

    asyncio.run(scenario())


def test_vim_ctrl_w_prefix_switches_panes(pane_root: Path) -> None:
    async def scenario() -> None:
        app = YateApp(target=pane_root)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            app.editor.select_keymap("vim")
            await pilot.pause()
            # ctrl+w arms the prefix, h goes to the left pane (explorer)
            await pilot.press("ctrl+w")
            await pilot.pause()
            assert app.editor.window_flows.window_pending
            await pilot.press("h")
            await pilot.pause()
            assert not app.editor.window_flows.window_pending
            assert app.focused is app.editor.explorer_tree
            # l goes back to the right pane (editor)
            await pilot.press("ctrl+w")
            await pilot.press("l")
            await pilot.pause()
            assert app.focused is app.editor.panes.active_view
            # ctrl+w ctrl+w cycles between the two panes
            await pilot.press("ctrl+w")
            await pilot.press("ctrl+w")
            await pilot.pause()
            assert app.focused is app.editor.explorer_tree

    asyncio.run(scenario())


def test_vim_window_prefix_cancelled_by_other_keys(pane_root: Path) -> None:
    async def scenario() -> None:
        app = YateApp(target=pane_root)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            app.editor.select_keymap("vim")
            await pilot.pause()
            await pilot.press("ctrl+w")
            await pilot.pause()
            assert app.editor.window_flows.window_pending
            # an unrelated key cancels the prefix and is processed normally
            before = app.editor.session.buffer.lines[0]
            await pilot.press("x")
            await pilot.pause()
            assert not app.editor.window_flows.window_pending
            assert app.editor.session.buffer.lines[0] == before[1:]  # x deleted a char

    asyncio.run(scenario())


def test_vim_insert_mode_ctrl_w_not_intercepted(pane_root: Path) -> None:
    async def scenario() -> None:
        app = YateApp(target=pane_root)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            app.editor.select_keymap("vim")
            await pilot.pause()
            await pilot.press("i")  # INSERT
            await pilot.pause()
            await pilot.press("ctrl+w")
            await pilot.pause()
            assert not app.editor.window_flows.window_pending

    asyncio.run(scenario())


# ----------------------------------------------------------------- split panes


def test_close_command_closes_active_pane(pane_root: Path) -> None:
    """:close / :cl close the active pane; on the last pane they warn
    instead of quitting (use :q for that)."""

    async def scenario() -> None:
        app = YateApp(target=pane_root / "alpha.txt", keymap="vim")
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            panes = app.editor.panes
            assert panes is not None

            app.editor.run_command("sp")
            assert await wait_until(pilot, lambda: panes.leaf_count == 2)
            app.editor.run_command("close")
            assert await wait_until(pilot, lambda: panes.leaf_count == 1)
            # the last pane is never closed by :close
            app.editor.run_command("cl")
            await pilot.pause()
            assert panes.leaf_count == 1
            assert app.is_running

    asyncio.run(scenario())


def test_pane_regions_stay_visible_after_split(pane_root: Path) -> None:
    """Regression: sizes set before mount resolved against an unknown
    parent, pushing every pane after the first off-screen."""

    async def scenario() -> None:
        app = YateApp(target=pane_root / "alpha.txt", keymap="vim")
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            panes = app.editor.panes
            assert panes is not None

            app.editor.run_command("sp")
            assert await wait_until(pilot, lambda: panes.leaf_count == 2)
            app.editor.run_command("vs")
            assert await wait_until(pilot, lambda: panes.leaf_count == 3)
            await pilot.pause()
            host = panes.host
            assert host is not None
            host_region = host.region
            views = panes.all_views()
            for view in views:
                region = view.region
                assert region.width > 5 and region.height > 2, (
                    f"pane collapsed: {region}"
                )
                assert host_region.contains_region(region), (
                    f"pane outside host: {region} vs {host_region}"
                )
            # dividers: after :sp the top pane has a bottom border; after
            # :vs the bottom-left pane has a right border; last panes none
            assert views[0].styles.border_bottom[0] not in ("", "none")
            assert views[0].styles.border_right[0] in ("", "none")
            assert views[1].styles.border_right[0] not in ("", "none")
            assert views[1].styles.border_bottom[0] in ("", "none")
            assert views[2].styles.border_bottom[0] in ("", "none")
            assert views[2].styles.border_right[0] in ("", "none")

    asyncio.run(scenario())


def test_split_independent_cursors_and_navigation(pane_root: Path) -> None:
    async def scenario() -> None:
        app = YateApp(target=pane_root / "alpha.txt", keymap="vim")
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            panes = app.editor.panes
            assert panes is not None

            app.editor.run_command("sp")
            assert await wait_until(pilot, lambda: panes.leaf_count == 2)
            root = panes.root
            assert isinstance(root, PaneSplit)
            assert root.axis == "horizontal"
            assert len(app.query(EditorView)) == 2

            # the new (bottom) pane is active: move its cursor to row 1
            await pilot.press("j")
            await pilot.pause()
            assert app.editor.session.buffer.cursor == (1, 0)

            # ctrl+w k jumps to the top pane: its cursor stayed at row 0
            await pilot.press("ctrl+w", "k")
            await pilot.pause()
            assert app.editor.session.buffer.cursor == (0, 0)
            # ctrl+w j returns to the bottom pane and its row-1 cursor
            await pilot.press("ctrl+w", "j")
            await pilot.pause()
            assert app.editor.session.buffer.cursor == (1, 0)

            # ctrl+w ctrl+w from the last editor pane wraps to the explorer,
            # then from the explorer back to the active editor pane
            await pilot.press("ctrl+w", "ctrl+w")
            await pilot.pause()
            assert app.focused is app.editor.explorer_tree
            assert app.editor.session.buffer.cursor == (1, 0)
            await pilot.press("ctrl+w", "ctrl+w")
            await pilot.pause()
            assert app.focused is app.editor.panes.active_view
            assert app.editor.session.buffer.cursor == (1, 0)

    asyncio.run(scenario())


def test_vsplit_with_file_and_only(pane_root: Path) -> None:
    async def scenario() -> None:
        app = YateApp(target=pane_root / "alpha.txt", keymap="vim")
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            panes = app.editor.panes
            assert panes is not None

            # relative path resolves against the current file's directory
            app.editor.run_command("vs bravo.txt")
            opened = await wait_until(
                pilot,
                lambda: panes.leaf_count == 2
                and app.editor.session.doc.path is not None
                and app.editor.session.doc.path.name == "bravo.txt",
            )
            assert opened
            root = panes.root
            assert isinstance(root, PaneSplit)
            assert root.axis == "vertical"
            assert app.editor.session.buffer.lines[0] == "bravo one"
            assert len(app.query(EditorView)) == 2

            # :sp on the bravo pane clones it -> 3 panes
            app.editor.run_command("split")
            assert await wait_until(pilot, lambda: panes.leaf_count == 3)
            # :only collapses back to the active (bravo) pane
            app.editor.run_command("only")
            assert await wait_until(pilot, lambda: panes.leaf_count == 1)
            assert len(app.query(EditorView)) == 1
            current = app.editor.session.doc
            assert current.path is not None
            assert current.path.name == "bravo.txt"

    asyncio.run(scenario())


async def _wait_quit(app: YateApp, pilot: Any) -> None:
    """Pump the pilot until *app* exits (mirrors the :q tests above).

    After the pump loop the app must have exited cleanly: ``_exception``
    being set would mean the shutdown crashed rather than quit, and that
    must not pass silently as a successful quit.
    """
    for _ in range(5):
        with contextlib.suppress(Exception):
            await pilot.pause()
        if not app.is_running:
            break
    for _ in range(3):
        await asyncio.sleep(0)
    assert app._exception is None


def test_chord_split_resize_close_and_q(pane_root: Path) -> None:
    async def scenario() -> None:
        app = YateApp(target=pane_root / "alpha.txt", keymap="vim")
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            panes = app.editor.panes
            assert panes is not None

            await pilot.press("ctrl+w", "s")
            assert await wait_until(pilot, lambda: panes.leaf_count == 2)
            root = panes.root
            assert isinstance(root, PaneSplit)
            assert root.axis == "horizontal"

            # ctrl+w - shrinks the active (new) pane; ctrl+w = equalizes
            await pilot.press("ctrl+w", "minus")
            await pilot.pause()
            assert abs(root.sizes[1] - 0.42) <= 0.005
            await pilot.press("ctrl+w", "equals_sign")
            await pilot.pause()
            assert root.sizes == [0.5, 0.5]

            # a dirty document does not block closing a pane (the document
            # stays open as a hidden buffer)
            await pilot.press("i", "x", "escape")
            await pilot.pause()
            assert app.editor.session.doc.modified
            await pilot.press("ctrl+w", "q")
            assert await wait_until(pilot, lambda: panes.leaf_count == 1)
            assert app.is_running

            # single pane: :q is blocked by unsaved changes, :q! exits
            app.editor.run_command("q")
            await pilot.pause()
            assert app.is_running
            app.editor.run_command("q!")
            await _wait_quit(app, pilot)
            assert not app.is_running

    asyncio.run(scenario())


def test_q_always_quits_whole_editor_with_panes(pane_root: Path) -> None:
    """:q must quit yate even when several panes are open -- it never
    just closes the active pane (use :close / :cl / Ctrl+W q for that).
    A dirty buffer blocks it like any other quit attempt."""

    async def scenario() -> None:
        app = YateApp(target=pane_root / "alpha.txt", keymap="vim")
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            panes = app.editor.panes
            assert panes is not None

            await pilot.press("ctrl+w", "s")
            assert await wait_until(pilot, lambda: panes.leaf_count == 2)
            # make the buffer dirty: :q is a whole-editor quit attempt and
            # the unsaved-changes guard blocks it; a pane close would not
            await pilot.press("i", "y", "escape")
            await pilot.pause()
            assert app.editor.session.doc.modified

            app.editor.run_command("q")
            await pilot.pause()
            # blocked: unsaved changes guard, and no pane was closed
            assert app.is_running
            assert panes.leaf_count == 2

            app.editor.run_command("quit")
            await pilot.pause()
            # :quit is a plain alias of :q and is blocked the same way
            assert app.is_running
            assert panes.leaf_count == 2

            app.editor.run_command("q!")  # discard and quit the whole editor
            await _wait_quit(app, pilot)
            assert not app.is_running

    asyncio.run(scenario())


def test_q_quits_immediately_with_clean_panes(pane_root: Path) -> None:
    """With no unsaved changes :q exits yate straight away even with
    several panes open (it does not close them one by one)."""

    async def scenario() -> None:
        app = YateApp(target=pane_root / "alpha.txt", keymap="vim")
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            panes = app.editor.panes
            assert panes is not None

            await pilot.press("ctrl+w", "s")
            assert await wait_until(pilot, lambda: panes.leaf_count == 2)
            app.editor.run_command("q")
            await _wait_quit(app, pilot)
            assert not app.is_running

    asyncio.run(scenario())


# ------------------------------------------------- separator drag-resize


def test_separator_drag_updates_split_sizes(pane_root: Path) -> None:
    """Dragging the vsplit separator border live-transfers fraction between
    the two panes (IKJRFK wave-1): press on the divider column, move right,
    release -- the left slot grows and its widget gets wider."""

    async def scenario() -> None:
        app = YateApp(target=pane_root / "alpha.txt", keymap="vim")
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            panes = app.editor.panes
            assert panes is not None

            await pilot.press(":", "v", "s", "p", "l", "i", "t", "enter")
            assert await wait_until(pilot, lambda: panes.leaf_count == 2)
            await pilot.pause()
            root = panes.root
            assert isinstance(root, PaneSplit)
            assert root.axis == "vertical"

            host = panes.host
            assert host is not None
            box, split = host._split_boxes[0]
            assert split is root
            left_view, right_view = box.children
            # the separator cell is the left pane's right border column
            sx = left_view.region.x + left_view.region.width - 1
            sy = left_view.region.y + left_view.region.height // 2

            await pilot.mouse_down(None, offset=(sx, sy))
            # Textual private API (verified on 8.2.8; revisit on upgrades,
            # same containment discipline as keyproto/textual_internals.py)
            await pilot._post_mouse_events(
                [MouseMove, MouseUp], offset=(sx + 4, sy), button=1
            )
            await pilot.pause()

            assert root.sizes[0] > 0.5
            assert left_view.region.width > right_view.region.width

    asyncio.run(scenario())


def test_separator_drag_record_keeps_hit_box(pane_root: Path) -> None:
    """The drag record stores the hit-tested box: on_mouse_move resizes
    through the stored box instead of re-walking _split_boxes (PR#66
    review round 3, item 2)."""

    async def scenario() -> None:
        app = YateApp(target=pane_root / "alpha.txt", keymap="vim")
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            panes = app.editor.panes
            assert panes is not None
            await pilot.press(":", "v", "s", "p", "l", "i", "t", "enter")
            assert await wait_until(pilot, lambda: panes.leaf_count == 2)
            await pilot.pause()
            host = panes.host
            assert host is not None
            box, split = host._split_boxes[0]
            left_view, _right_view = box.children
            assert isinstance(left_view, EditorView)
            sx = left_view.region.x + left_view.region.width - 1
            sy = left_view.region.y + left_view.region.height // 2

            await pilot.mouse_down(None, offset=(sx, sy))
            await pilot.pause()
            drag = host._drag
            assert drag is not None
            assert drag.box is box
            assert drag.split is split
            assert drag.child_index == 0
            assert app.mouse_captured is host

            await pilot._post_mouse_events(
                [MouseUp], offset=(sx + 4, sy), button=1
            )
            await pilot.pause()
            assert host._drag is None
            assert app.mouse_captured is None

    asyncio.run(scenario())


def test_toggle_off_mid_drag_cancels_separator_drag(pane_root: Path) -> None:
    """``:set support_mouse off`` while a separator drag is in flight must
    not lock the capture or the drag record: the gate drops the MouseUp
    that would end the drag, so the setter sweeps the state (PR#66 review
    round 3, item 1)."""

    async def scenario() -> None:
        app = YateApp(target=pane_root / "alpha.txt", keymap="vim")
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            panes = app.editor.panes
            assert panes is not None
            await pilot.press(":", "v", "s", "p", "l", "i", "t", "enter")
            assert await wait_until(pilot, lambda: panes.leaf_count == 2)
            await pilot.pause()
            host = panes.host
            assert host is not None
            box, _split = host._split_boxes[0]
            left_view, _right_view = box.children
            assert isinstance(left_view, EditorView)
            sx = left_view.region.x + left_view.region.width - 1
            sy = left_view.region.y + left_view.region.height // 2

            await pilot.mouse_down(None, offset=(sx, sy))
            await pilot.pause()
            assert host._drag is not None
            assert app.mouse_captured is host

            app.editor.run_command("set support_mouse=off")
            assert app.editor.config.support_mouse is False
            assert host._drag is None
            assert app.mouse_captured is None

    asyncio.run(scenario())


def test_separator_click_does_not_move_cursor(pane_root: Path) -> None:
    """Clicking the divider cell must not land in a text area: the active
    pane and the buffer cursor stay put (wave-2's border guard on
    EditorView keeps this contract once it consumes text-area presses)."""

    async def scenario() -> None:
        app = YateApp(target=pane_root / "alpha.txt", keymap="vim")
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            panes = app.editor.panes
            assert panes is not None

            await pilot.press(":", "v", "s", "p", "l", "i", "t", "enter")
            assert await wait_until(pilot, lambda: panes.leaf_count == 2)
            await pilot.pause()
            root = panes.root
            assert isinstance(root, PaneSplit)

            host = panes.host
            assert host is not None
            box, _split = host._split_boxes[0]
            left_view, _right_view = box.children
            sx = left_view.region.x + left_view.region.width - 1
            sy = left_view.region.y + left_view.region.height // 2

            # Focus the pane owning the divider border first: Textual's
            # screen-level click-to-focus focuses whatever pane was pressed
            # on (a framework behavior outside this change), so aiming the
            # click at the already-focused pane is what pins "no focus
            # switch, no cursor move" as the guarded contract.
            await pilot.press("ctrl+w", "h")
            await pilot.pause()
            assert app.focused is left_view
            active_before = panes.active
            cursor_before = app.editor.session.buffer.cursor

            await pilot.click(None, offset=(sx, sy))
            await pilot.pause()

            assert panes.active is active_before
            assert app.editor.session.buffer.cursor == cursor_before

    asyncio.run(scenario())


# --------------------------------------------------------------- :wq guarding


def test_wq_saves_and_quits_when_save_succeeds(tmp_path: Path) -> None:
    """Happy path: :wq writes the dirty buffer to disk, clears the modified
    flag and then calls quit() without force (other-tab dirty checks still
    apply inside quit()).

    quit() is recorded instead of letting the app tear down: a real
    save-and-quit orphans the fire-and-forget LSP didSave worker (its
    coroutine is GC'd unawaited -- pre-existing app behavior that only
    shows up once the loop is gone). Keeping the app alive lets the
    worker drain while the recorder still proves the quit decision.
    """

    async def scenario() -> None:
        target = tmp_path / "notes.txt"
        app = YateApp(target=target, keymap="vim")
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            # dirty the buffer
            await pilot.press("i", "h", "i", "escape")
            await pilot.pause()
            assert app.editor.session.doc.modified

            quit_calls: list[bool] = []

            def _record_quit(force: bool = False) -> None:
                quit_calls.append(force)

            cast(Any, app.editor).quit = _record_quit
            app.editor.run_command("wq")
            await pilot.pause()
            await pilot.pause()

            assert quit_calls == [False]
            assert not app.editor.session.doc.modified
            assert target.read_text(encoding="utf-8") == "hi"

    asyncio.run(scenario())


def test_wq_does_not_quit_when_save_fails(tmp_path: Path) -> None:
    """Data-loss regression: when the write raises (here the path points at a
    directory), :wq must NOT force-quit -- the unsaved work stays in memory."""

    async def scenario() -> None:
        target = tmp_path / "notes.txt"
        app = YateApp(target=target, keymap="vim")
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            await pilot.press("i", "k", "e", "e", "p", "escape")
            await pilot.pause()
            assert app.editor.session.doc.modified

            # Aim the document at a directory so write_text() raises OSError.
            blocker = tmp_path / "blocker"
            blocker.mkdir()
            app.editor.session.doc.path = blocker

            app.editor.run_command("wq")
            await pilot.pause()

            # Still running: the failed save aborted the quit.
            assert app.is_running
            assert app.editor.session.doc.modified
            assert app.editor.session.doc.buffer.get_text() == "keep"
            assert "save failed" in message_text(app)

    asyncio.run(scenario())


def test_wq_does_not_quit_for_unnamed_modified_buffer() -> None:
    """An unnamed (no path) dirty buffer routes :wq to the save-as prompt;
    the editor must stay open rather than force-quit and lose the text."""

    async def scenario() -> None:
        app = YateApp(keymap="vim")  # untitled scratch buffer
        async with app.run_test(size=(100, 30)) as pilot:
            prompt_bar = app.editor.prompt_bar
            assert prompt_bar is not None
            await pilot.press("i", "w", "o", "r", "k", "escape")
            await pilot.pause()
            assert app.editor.session.doc.path is None
            assert app.editor.session.doc.modified

            app.editor.run_command("wq")
            await pilot.pause()

            assert app.is_running
            assert app.editor.session.doc.modified
            assert app.editor.session.doc.buffer.get_text() == "work"
            # the save-as prompt was opened instead of quitting
            assert prompt_bar.active_mode == "save"

            # cancelling the prompt (empty submit) still must not quit
            await pilot.press("enter")
            await pilot.pause()
            assert app.is_running
            assert app.editor.session.doc.modified
            assert app.editor.session.doc.buffer.get_text() == "work"
            assert "save cancelled" in message_text(app)

    asyncio.run(scenario())


def test_wq_quits_for_clean_unnamed_buffer() -> None:
    """A pristine unnamed buffer (welcome page / :enew) has nothing to lose:
    :wq exits straight away, matching the pre-guard behavior."""

    async def scenario() -> None:
        app = YateApp(keymap="vim")
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            assert app.editor.session.doc.path is None
            assert not app.editor.session.doc.modified

            app.editor.run_command("wq")
            await _wait_quit(app, pilot)

            assert not app.is_running

    asyncio.run(scenario())


def test_wq_quits_for_clean_named_buffer(tmp_path: Path) -> None:
    """No unsaved changes: :wq re-writes the (unchanged) file and quits.

    quit() is recorded rather than executed for the same LSP-worker reason
    as test_wq_saves_and_quits_when_save_succeeds above.
    """

    async def scenario() -> None:
        target = tmp_path / "clean.txt"
        target.write_text("already saved", encoding="utf-8")
        app = YateApp(target=target, keymap="vim")
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            assert not app.editor.session.doc.modified

            quit_calls: list[bool] = []

            def _record_quit(force: bool = False) -> None:
                quit_calls.append(force)

            cast(Any, app.editor).quit = _record_quit
            app.editor.run_command("wq")
            await pilot.pause()
            await pilot.pause()

            assert quit_calls == [False]
            assert target.read_text(encoding="utf-8") == "already saved"

    asyncio.run(scenario())


def test_wq_does_not_quit_when_other_tab_is_dirty(tmp_path: Path) -> None:
    """Current doc is saved successfully, but another tab has unsaved
    changes. :wq must call quit() *without* force so the internal
    any(dirty) guard blocks the exit (vim E37 semantics) instead of
    silently discarding the other tab's work."""

    async def scenario() -> None:
        saved = tmp_path / "saved.txt"
        other = tmp_path / "other.txt"
        saved.write_text("already", encoding="utf-8")
        other.write_text("pristine", encoding="utf-8")

        app = YateApp(target=saved, keymap="vim")
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            first = app.editor.session.docs[0]

            # open the second tab and dirty it
            app.editor.document_flows.open_path(other)
            await pilot.pause()
            assert len(app.editor.session.docs) == 2
            assert app.editor.session.doc.path == other
            await pilot.press("i", "e", "d", "i", "t", "escape")
            await pilot.pause()
            assert app.editor.session.doc.modified

            # switch back to saved.txt (the first tab, clean)
            app.editor.document_flows.activate_doc(first)
            assert app.editor.session.doc is first
            assert not app.editor.session.doc.modified

            # Wrap (don't replace) quit: record the force flag while still
            # running the real multi-tab dirty guard.
            quit_calls: list[bool] = []
            original_quit = app.editor.quit

            def _record_quit(force: bool = False) -> None:
                quit_calls.append(force)
                original_quit(force=force)

            cast(Any, app.editor).quit = _record_quit
            app.editor.run_command("wq")
            await pilot.pause()
            await pilot.pause()

            assert quit_calls == [False], f"expected non-force quit, got {quit_calls}"
            assert app.is_running
            # the dirty tab is untouched
            assert app.editor.session.docs[1].modified
            assert other.read_text(encoding="utf-8") == "pristine"
            assert "unsaved changes" in message_text(app)

    asyncio.run(scenario())


def test_wq_does_not_crash_on_unicode_encode_error(tmp_path: Path) -> None:
    """When the file's detected encoding cannot represent the buffer
    content (cp1252 + emoji), :wq must surface a friendly error message
    and keep the editor alive -- NOT crash via Textual's exception
    handler and lose the in-memory buffers."""

    async def scenario() -> None:
        target = tmp_path / "cp1252.txt"
        # Bytes that are valid cp1252 but not UTF-8, so encoding sniffing
        # (utf-8 -> locale -> cp1252) lands on cp1252 on every platform.
        target.write_bytes("caf\xe9".encode("cp1252"))  # "café" in cp1252

        app = YateApp(target=target, keymap="vim")
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            assert app.editor.session.doc.encoding.lower().startswith(("cp1252", "windows-1252"))

            # Append an emoji -- cp1252 cannot encode it. Textual's Pilot
            # has no paste() helper, so insert straight into the buffer.
            app.editor.session.doc.buffer.move_doc_end()
            app.editor.session.doc.buffer.insert_text("\U0001f600")
            await pilot.pause()
            assert app.editor.session.doc.modified

            app.editor.run_command("wq")
            await pilot.pause()

            # save failed -> guard aborts the quit; editor stays alive and
            # the full unsaved content survives in memory, so the user can
            # still recover it via :saveas with a UTF-8-capable path. The
            # save itself is atomic (sibling temp file + os.replace, with
            # encoding done before anything is written), so the on-disk
            # bytes survive the failed write untouched.
            assert app.is_running
            assert app.editor.session.doc.modified
            assert "save failed" in message_text(app)
            assert app.editor.session.doc.buffer.get_text() == "caf\u00e9\U0001f600"
            assert target.read_bytes() == "caf\xe9".encode("cp1252")

    asyncio.run(scenario())


def test_vertical_chord_and_geometry_navigation(pane_root: Path) -> None:
    async def scenario() -> None:
        app = YateApp(target=pane_root / "alpha.txt", keymap="vim")
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            panes = app.editor.panes
            assert panes is not None

            await pilot.press("ctrl+w", "v")
            assert await wait_until(pilot, lambda: panes.leaf_count == 2)
            root = panes.root
            assert isinstance(root, PaneSplit)
            assert root.axis == "vertical"
            ordered = pane_leaves(root)
            left_view = panes.views[ordered[0].id]

            # the new pane is the right one; h moves geometrically to the
            # editor pane on the left first ...
            await pilot.press("ctrl+w", "h")
            await pilot.pause()
            assert app.focused is left_view
            # ... and only then, with no editor further left, to the explorer
            await pilot.press("ctrl+w", "h")
            await pilot.pause()
            assert app.focused is app.editor.explorer_tree
            # l from the explorer returns to the active (right) editor pane
            await pilot.press("ctrl+w", "l")
            await pilot.pause()
            assert app.focused is app.editor.panes.active_view

    asyncio.run(scenario())


def test_bd_rebinds_every_pane_showing_the_document(pane_root: Path) -> None:
    async def scenario() -> None:
        app = YateApp(target=pane_root / "alpha.txt", keymap="vim")
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            panes = app.editor.panes
            assert panes is not None

            app.editor.run_command("sp")
            assert await wait_until(pilot, lambda: panes.leaf_count == 2)
            # the new pane opens bravo; the top pane keeps alpha
            app.editor.run_command("e bravo.txt")
            assert await wait_until(
                pilot,
                lambda: app.editor.session.doc.path is not None
                and app.editor.session.doc.path.name == "bravo.txt",
            )
            app.editor.run_command("bd")
            await pilot.pause()
            assert len(app.editor.session.docs) == 1
            for leaf in pane_leaves(panes.root):
                path = leaf.doc.path
                assert path is not None
                assert path.name == "alpha.txt"
            active_path = app.editor.session.doc.path
            assert active_path is not None
            assert active_path.name == "alpha.txt"

    asyncio.run(scenario())
