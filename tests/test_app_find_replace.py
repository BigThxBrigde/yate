"""FindReplaceScreen pilot tests (pushed directly, no wiring -- run via pilot)."""

# tests legitimately poke at internals:
# pyright: reportPrivateUsage=false

from __future__ import annotations

import asyncio
import os
import pytest
from pathlib import Path

from textual.color import Color
from textual.containers import VerticalScroll
from textual.pilot import Pilot
from textual.widgets import Input, Static

from yate.app import YateApp
from yate.editor_core import project_search
from yate.editor_view import theme
from yate.editor_view.find_replace import (
    FindReplaceScreen,
    RevealFn,
    _Results,
)
from yate.editor_view.scrollbars import SlimScrollBarRender

from conftest import message_text, plain_text, wait_until


def _push(
    app: YateApp, tmp_path: Path, *, reveal: RevealFn | None = None,
) -> tuple[FindReplaceScreen, list[tuple[str, str]], list[bool]]:
    """Construct the screen over the app's session and push it.

    Returns the screen plus the recorded message-line texts/kinds and the
    read-only notices (injected recorders instead of the real prompt bar, so
    the worker's final "replaced ..." message cannot overwrite the evidence).
    """
    messages: list[tuple[str, str]] = []
    notices: list[bool] = []
    screen = FindReplaceScreen(
        app.editor.workspace,
        app.editor.session,
        open_path=app.editor.document_flows.open_path,
        reveal=reveal,
        message=lambda text, kind="info": messages.append((text, kind)),
        readonly_notice=lambda: notices.append(True),
        refresh=app.editor.refresh_ui,
    )
    app.editor.workspace.set_root(tmp_path)
    app.push_screen(screen)
    return screen, messages, notices


def _type_query(screen: FindReplaceScreen, query: str) -> None:
    """Fill the find input (reactive assignment fires the debounced search)."""
    screen.query_one("#fr-find", Input).value = query


def _results_plain(screen: FindReplaceScreen) -> str:
    """Plain text of the results pane renderable."""
    return plain_text(screen.query_one("#fr-results", Static).render())


def test_screen_compose_focuses_find_input(tmp_path: Path) -> None:
    async def scenario() -> None:
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            screen, _messages, _notices = _push(app, tmp_path)
            await pilot.pause()
            assert app.focused is not None
            assert app.focused.id == "fr-find"
            assert type(app.screen).__name__ == "FindReplaceScreen"
            assert screen is not None
            # the footer advertises every binding the overlay honours
            footer = screen.query_one("#fr-footer", Static)
            plain = plain_text(footer.render())
            for hint in ("enter: jump", "r: replace file", "a: replace all",
                         "alt+r: regex", "esc: close"):
                assert hint in plain

    asyncio.run(scenario())


def test_live_search_renders_grouped_results(tmp_path: Path) -> None:
    async def scenario() -> None:
        alpha = tmp_path / "alpha.txt"
        beta = tmp_path / "beta.txt"
        alpha.write_text("needle one\n", encoding="utf-8")
        beta.write_text("filler\nfiller\nx needle y\n", encoding="utf-8")
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            screen, _messages, _notices = _push(app, tmp_path)
            await pilot.pause()
            _type_query(screen, "needle")
            assert await wait_until(pilot, lambda: len(screen._flat) == 2)
            plain = _results_plain(screen)
            assert "alpha.txt" in plain
            assert "beta.txt" in plain
            assert "1: " in plain  # row+1 of the alpha hit
            assert "3: " in plain  # row+1 of the beta hit
            assert "needle" in plain  # snippet body rendered

    asyncio.run(scenario())


def test_option_toggles_rerun_search(tmp_path: Path) -> None:
    async def scenario() -> None:
        doc = tmp_path / "note.txt"
        doc.write_text("needle\nneedles\n", encoding="utf-8")
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            screen, _messages, _notices = _push(app, tmp_path)
            await pilot.pause()
            _type_query(screen, "needle")
            # whole-word off: the needle inside "needles" matches too
            assert await wait_until(pilot, lambda: len(screen._flat) == 2)
            await pilot.press("alt+w")
            assert await wait_until(pilot, lambda: len(screen._flat) == 1)

    asyncio.run(scenario())


def test_enter_opens_and_reveals_match(tmp_path: Path) -> None:
    async def scenario() -> None:
        doc = tmp_path / "note.txt"
        doc.write_text("needle here\n", encoding="utf-8")
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            seen: list[tuple[Path, int, int]] = []

            def reveal(path: Path, row: int, col: int) -> None:
                seen.append((path, row, col))
                app.editor.session.buffer.set_cursor((row, col + len("needle")))

            screen, _messages, _notices = _push(app, tmp_path, reveal=reveal)
            await pilot.pause()
            _type_query(screen, "needle")
            assert await wait_until(pilot, lambda: len(screen._flat) == 1)
            screen.query_one("#fr-results", Static).focus()
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            # the cursor lands on the match end, Vim-style
            assert seen == [(doc, 0, 0)]
            assert app.editor.session.buffer.cursor == (0, len("needle"))
            assert app.editor.session.is_open(doc) is not None
            assert app.screen is not screen

    asyncio.run(scenario())


def test_replace_all_writes_unopened_files(tmp_path: Path) -> None:
    async def scenario() -> None:
        alpha = tmp_path / "alpha.txt"
        beta = tmp_path / "beta.txt"
        alpha.write_text("needle x\nneedle y\n", encoding="utf-8")
        beta.write_text("z needle\n", encoding="utf-8")
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            screen, messages, _notices = _push(app, tmp_path)
            await pilot.pause()
            _type_query(screen, "needle")
            assert await wait_until(pilot, lambda: len(screen._flat) == 3)
            screen.query_one("#fr-replace", Input).value = "dog"
            screen.query_one("#fr-results", Static).focus()
            await pilot.pause()
            await pilot.press("a")
            assert await wait_until(
                pilot, lambda: "dog" in alpha.read_text(encoding="utf-8")
            )
            assert "dog" in beta.read_text(encoding="utf-8")
            assert any(
                "replaced 3" in text and kind == "ok" for text, kind in messages
            )

    asyncio.run(scenario())


def test_empty_replacement_deletes_matches_on_disk(tmp_path: Path) -> None:
    """An empty replace field deletes every match (a legitimate use)."""
    async def scenario() -> None:
        note = tmp_path / "note.txt"
        note.write_text("needle x\nkeep y\nneedle z\n", encoding="utf-8")
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            screen, messages, _notices = _push(app, tmp_path)
            await pilot.pause()
            _type_query(screen, "needle")
            assert await wait_until(pilot, lambda: len(screen._flat) == 2)
            # the replace input stays empty: deletion semantics
            screen.query_one("#fr-results", _Results).focus()
            await pilot.pause()
            await pilot.press("a")
            assert await wait_until(
                pilot,
                lambda: note.read_text(encoding="utf-8") == " x\nkeep y\n z\n",
            )
            assert any(
                "replaced 2" in text and kind == "ok" for text, kind in messages
            )

    asyncio.run(scenario())


def test_replace_updates_open_buffer_and_keeps_dirty(tmp_path: Path) -> None:
    async def scenario() -> None:
        doc = tmp_path / "note.txt"
        doc.write_text("needle\n", encoding="utf-8")
        app = YateApp(str(doc))  # open at startup: is_open() hits
        async with app.run_test(size=(100, 30)) as pilot:
            screen, messages, _notices = _push(app, tmp_path)
            await pilot.pause()
            _type_query(screen, "needle")
            assert await wait_until(pilot, lambda: len(screen._flat) == 1)
            screen.query_one("#fr-replace", Input).value = "dog"
            screen.query_one("#fr-results", Static).focus()
            await pilot.pause()
            await pilot.press("a")
            assert await wait_until(
                pilot, lambda: app.editor.session.buffer.get_text() == "dog\n"
            )
            assert app.editor.session.doc.modified is True
            # the disk copy stays untouched (in-memory replacement only)
            assert doc.read_text(encoding="utf-8") == "needle\n"
            assert any("replaced 1" in text for text, _kind in messages)

    asyncio.run(scenario())


def test_replace_skips_read_only_buffer(tmp_path: Path) -> None:
    async def scenario() -> None:
        alpha = tmp_path / "alpha.txt"
        beta = tmp_path / "beta.txt"
        alpha.write_text("needle\n", encoding="utf-8")
        beta.write_text("needle\n", encoding="utf-8")
        app = YateApp(str(alpha))
        async with app.run_test(size=(100, 30)) as pilot:
            app.editor.document_flows.open_path(beta)
            beta_doc = app.editor.session.is_open(beta)
            assert beta_doc is not None
            beta_doc.buffer.read_only = True
            alpha_doc = app.editor.session.is_open(alpha)
            assert alpha_doc is not None
            screen, messages, notices = _push(app, tmp_path)
            await pilot.pause()
            _type_query(screen, "needle")
            assert await wait_until(pilot, lambda: len(screen._flat) == 2)
            screen.query_one("#fr-replace", Input).value = "dog"
            screen.query_one("#fr-results", Static).focus()
            await pilot.pause()
            await pilot.press("a")
            assert await wait_until(
                pilot, lambda: alpha_doc.buffer.get_text() == "dog\n"
            )
            # alpha is an open buffer: replaced in memory only...
            assert alpha_doc.modified is True
            # ...and the read-only beta buffer was skipped entirely
            assert beta_doc.buffer.get_text() == "needle\n"
            assert "needle" in alpha.read_text(encoding="utf-8")
            assert "needle" in beta.read_text(encoding="utf-8")
            assert notices  # the read-only refusal surfaced (recorder proof)
            assert any("replaced 1" in text for text, _kind in messages)

    asyncio.run(scenario())


def test_replace_no_change_skips_disk_write(tmp_path: Path) -> None:
    async def scenario() -> None:
        changed = tmp_path / "changed.txt"
        changed.write_text("needle\n", encoding="utf-8")
        untouched = tmp_path / "untouched.txt"
        untouched.write_text("plain body\n", encoding="utf-8")
        os.utime(untouched, ns=(1_000_000_000, 1_000_000_000))
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            screen, _messages, _notices = _push(app, tmp_path)
            await pilot.pause()
            pattern = project_search.compile_query("needle")
            assert pattern is not None
            # positive control: a hit rewrites the file and reports the count
            assert screen._replace_on_disk(changed, pattern, "dog") == 1
            assert changed.read_text(encoding="utf-8") == "dog\n"
            # no-match contract: the same lines object back means no write
            assert screen._replace_on_disk(untouched, pattern, "dog") == 0
            assert untouched.read_text(encoding="utf-8") == "plain body\n"
            assert untouched.stat().st_mtime_ns == 1_000_000_000
            await pilot.pause()

    asyncio.run(scenario())


def test_escape_closes_screen(tmp_path: Path) -> None:
    async def scenario() -> None:
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            screen, _messages, _notices = _push(app, tmp_path)
            await pilot.pause()
            assert type(app.screen).__name__ == "FindReplaceScreen"
            await pilot.press("escape")
            await pilot.pause()
            assert app.screen is not screen
            assert type(app.screen).__name__ != "FindReplaceScreen"

    asyncio.run(scenario())


def test_binary_and_oversize_absent_from_results(tmp_path: Path) -> None:
    async def scenario() -> None:
        ok = tmp_path / "ok.txt"
        ok.write_text("needle\n", encoding="utf-8")
        blob = tmp_path / "blob.bin"
        blob.write_bytes(b"\xff\xfe\x00needle")  # not valid UTF-8
        big = tmp_path / "big.txt"
        big.write_text("needle" + "x" * 2_000_000, encoding="utf-8")  # > 2 MB
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            screen, _messages, _notices = _push(app, tmp_path)
            await pilot.pause()
            _type_query(screen, "needle")
            assert await wait_until(pilot, lambda: len(screen._flat) == 1)
            plain = _results_plain(screen)
            assert "ok.txt" in plain
            assert "blob.bin" not in plain
            assert "big.txt" not in plain

    asyncio.run(scenario())


def test_results_up_down_move_cursor(tmp_path: Path) -> None:
    async def scenario() -> None:
        doc = tmp_path / "note.txt"
        doc.write_text("needle one\nfiller\nneedle two\n", encoding="utf-8")
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            screen, _messages, _notices = _push(app, tmp_path)
            await pilot.pause()
            _type_query(screen, "needle")
            assert await wait_until(pilot, lambda: len(screen._flat) == 2)
            assert screen._cursor == 0
            screen.query_one("#fr-results", Static).focus()
            await pilot.pause()
            await pilot.press("down")
            await pilot.pause()
            assert screen._cursor == 1
            assert "> 3: " in _results_plain(screen)  # second hit is row 2
            await pilot.press("up")
            await pilot.pause()
            assert screen._cursor == 0

    asyncio.run(scenario())


def test_replace_r_current_file_only(tmp_path: Path) -> None:
    async def scenario() -> None:
        alpha = tmp_path / "alpha.txt"
        beta = tmp_path / "beta.txt"
        alpha.write_text("needle\n", encoding="utf-8")
        beta.write_text("needle\n", encoding="utf-8")
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            screen, _messages, _notices = _push(app, tmp_path)
            await pilot.pause()
            _type_query(screen, "needle")
            assert await wait_until(pilot, lambda: len(screen._flat) == 2)
            screen.query_one("#fr-replace", Input).value = "dog"
            screen.query_one("#fr-results", Static).focus()
            await pilot.pause()
            # the cursor sits on the first (alpha) hit
            await pilot.press("r")
            assert await wait_until(
                pilot, lambda: "dog" in alpha.read_text(encoding="utf-8")
            )
            assert "needle" in beta.read_text(encoding="utf-8")

    asyncio.run(scenario())


# ------------------------------------------------- wiring (plan-d, ctrl+h)


def test_ctrl_h_opens_project_replace_vsc(tmp_path: Path) -> None:
    async def scenario() -> None:
        app = YateApp(str(tmp_path))
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            await pilot.press("ctrl+h")
            await pilot.pause()
            assert type(app.screen).__name__ == "FindReplaceScreen"

    asyncio.run(scenario())


def test_ctrl_h_opens_project_replace_vim(tmp_path: Path) -> None:
    async def scenario() -> None:
        app = YateApp(str(tmp_path), keymap="vim")
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            await pilot.press("ctrl+h")
            await pilot.pause()
            assert type(app.screen).__name__ == "FindReplaceScreen"

    asyncio.run(scenario())


def test_ctrl_h_without_workspace_warns(tmp_path: Path) -> None:
    async def scenario() -> None:
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            await pilot.press("ctrl+h")
            await pilot.pause()
            assert type(app.screen).__name__ != "FindReplaceScreen"
            assert "no workspace" in message_text(app)

    asyncio.run(scenario())


def test_project_replace_action_registered() -> None:
    async def scenario() -> None:
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            assert app.editor.actions.get("project_replace") is not None

    asyncio.run(scenario())


def test_overlay_push_clears_stale_message(tmp_path: Path) -> None:
    async def scenario() -> None:
        app = YateApp(str(tmp_path))
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            app.editor.message("stale saved note", "info")
            assert "stale saved note" in message_text(app)
            await pilot.press("ctrl+h")
            await pilot.pause()
            assert type(app.screen).__name__ == "FindReplaceScreen"
            assert message_text(app) != "stale saved note"
            assert "Ready. Press F1" in message_text(app)

    asyncio.run(scenario())


def test_enter_reveals_cursor_at_match(tmp_path: Path) -> None:
    """Timing proof (plan-d): the async open worker the screen scheduled
    must not clobber the reveal -- the cursor stays on the match start."""
    async def scenario() -> None:
        note = tmp_path / "note.txt"
        note.write_text("filler\nfiller\nx needle y\n", encoding="utf-8")
        app = YateApp(str(tmp_path))
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            await pilot.press("ctrl+h")
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, FindReplaceScreen)
            screen.query_one("#fr-find", Input).value = "needle"
            assert await wait_until(pilot, lambda: len(screen._flat) == 1)
            screen.query_one("#fr-results", Static).focus()
            await pilot.pause()
            await pilot.press("enter")
            assert await wait_until(
                pilot, lambda: app.editor.session.is_open(note) is not None
            )
            await pilot.pause()
            await pilot.pause()
            # the cursor sits on the match start ("x needle y": row 2, col 2)
            assert app.editor.session.buffer.cursor == (2, 2)

    asyncio.run(scenario())


# -------------------------------------- cross-wave integration (plan-e)


async def _press_f4_replace(
    pilot: Pilot[None], find: str, replacement: str
) -> None:
    """Drive F4 through the two-step replace prompt (vim keymap)."""
    await pilot.press("f4")
    await pilot.pause()
    await pilot.press(*find)
    await pilot.press("enter")
    await pilot.pause()
    await pilot.press(*replacement)
    await pilot.press("enter")
    await pilot.pause()


def test_project_replace_end_to_end_open_edit_replace(tmp_path: Path) -> None:
    """One ``a`` replaces every hit: closed files on disk, the open file
    in memory (dirty), with the replaced total on the message line."""
    async def scenario() -> None:
        one = tmp_path / "one.txt"
        two = tmp_path / "two.txt"
        three = tmp_path / "three.txt"
        one.write_text("x needle y\n", encoding="utf-8")
        two.write_text("needle two\n", encoding="utf-8")
        three.write_text("three needle\n", encoding="utf-8")
        app = YateApp(str(tmp_path))
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            # file 1 is open before the replace runs: its hit goes through
            # the in-memory buffer path, the other two through disk writes.
            app.editor.document_flows.open_path(one)
            await pilot.pause()
            await pilot.press("ctrl+h")
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, FindReplaceScreen)
            _type_query(screen, "needle")
            # generous budgets: the scan is debounced and the replace writes
            # three files, both of which lag under a parallel runner's load
            assert await wait_until(
                pilot, lambda: len(screen._flat) == 3, timeout=15.0
            )
            screen.query_one("#fr-replace", Input).value = "dog"
            screen.query_one("#fr-results", Static).focus()
            await pilot.pause()
            await pilot.press("a")

            # Windows: the replace lands via os.replace and a read racing
            # the rename raises PermissionError -- treat that as "not landed
            # yet" so the poll retries instead of aborting.
            def _landed() -> bool:
                try:
                    return (
                        two.read_text(encoding="utf-8") == "dog two\n"
                        and three.read_text(encoding="utf-8") == "three dog\n"
                    )
                except OSError:
                    return False

            assert await wait_until(pilot, _landed, timeout=15.0)
            # the replaced total surfaces while the overlay is still open
            assert "replaced 3" in message_text(app)
            await pilot.press("escape")
            await pilot.pause()
            assert app.screen is not screen
            # closed files landed on disk ...
            assert two.read_text(encoding="utf-8") == "dog two\n"
            assert three.read_text(encoding="utf-8") == "three dog\n"
            # ... the open file was replaced in memory and stayed dirty
            one_doc = app.editor.session.is_open(one)
            assert one_doc is not None
            assert one_doc.buffer.get_text() == "x dog y\n"
            assert one_doc.modified is True
            assert one.read_text(encoding="utf-8") == "x needle y\n"

    asyncio.run(scenario())


def test_ctrl_h_from_search_prompt_state_recovers(tmp_path: Path) -> None:
    """ctrl+h works while a live-search prompt state exists, and the
    prompt keeps working after the overlay closes (no dangling hooks)."""
    async def scenario() -> None:
        note = tmp_path / "note.txt"
        note.write_text("needle one\n", encoding="utf-8")
        app = YateApp(str(note), keymap="vim")
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            prompt_bar = app.editor.prompt_bar
            assert prompt_bar is not None
            # enter the live-search state: "/" opens the find prompt
            await pilot.press("/")
            await pilot.pause()
            assert prompt_bar.active_mode == "find"
            for ch in "needle":
                await pilot.press(ch)
            await pilot.pause()
            assert prompt_bar.input.value == "needle"
            await pilot.press("escape")
            await pilot.pause()
            assert prompt_bar.active_mode is None
            # ctrl+h from that state opens the overlay normally
            await pilot.press("ctrl+h")
            await pilot.pause()
            screen = app.screen
            assert type(screen).__name__ == "FindReplaceScreen"
            await pilot.press("escape")
            await pilot.pause()
            assert app.screen is not screen
            # the prompt recovers: activation, typing and cancel all still
            # behave (nothing swallows the keys any more); the query was
            # reset by the cancel, so the input starts empty
            await pilot.press("/")
            await pilot.pause()
            assert prompt_bar.active_mode == "find"
            assert prompt_bar.input.value == ""
            await pilot.press("x")
            await pilot.pause()
            assert prompt_bar.input.value == "x"
            await pilot.press("escape")
            await pilot.pause()
            assert prompt_bar.active_mode is None

    asyncio.run(scenario())


def test_f4_confirm_loop_then_ctrl_h_coexist(tmp_path: Path) -> None:
    """ctrl+h opens the overlay after a confirm loop was quit halfway;
    the loop state is fully cleared by then (no stale replacement)."""
    async def scenario() -> None:
        note = tmp_path / "note.txt"
        note.write_text("cat cat cat", encoding="utf-8")
        app = YateApp(str(note), keymap="vim")
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            prompt_bar = app.editor.prompt_bar
            assert prompt_bar is not None
            await _press_f4_replace(pilot, "cat", "dog")
            await pilot.press("y")
            await pilot.pause()
            # quit the loop halfway: one match replaced, state cleared
            await pilot.press("q")
            await pilot.pause()
            assert app.editor.session.buffer.get_text() == "dog cat cat"
            assert app.editor.prompt_flows._confirm_total == 0
            # the overlay still opens on top of that state
            await pilot.press("ctrl+h")
            await pilot.pause()
            assert type(app.screen).__name__ == "FindReplaceScreen"

    asyncio.run(scenario())


def test_project_replace_regex_option_end_to_end(tmp_path: Path) -> None:
    """alt+r switches the overlay to regex mode and the replacement's
    backreference expands per match through the disk-write path."""
    async def scenario() -> None:
        note = tmp_path / "note.txt"
        note.write_text("a@x b@x", encoding="utf-8")
        app = YateApp(str(tmp_path))
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            await pilot.press("ctrl+h")
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, FindReplaceScreen)
            # regex mode first: the search itself must run as a regex
            await pilot.press("alt+r")
            await pilot.pause()
            screen.query_one("#fr-find", Input).value = r"(\w+)@x"
            assert await wait_until(pilot, lambda: len(screen._flat) == 2)
            screen.query_one("#fr-replace", Input).value = r"\1"
            screen.query_one("#fr-results", Static).focus()
            await pilot.pause()
            await pilot.press("a")
            assert await wait_until(
                pilot, lambda: note.read_text(encoding="utf-8") == "a b"
            )

    asyncio.run(scenario())


def test_unmatched_printable_keys_fall_through_in_screen(
    tmp_path: Path,
) -> None:
    """A stray printable key on the results pane is not consumed: no
    replacement happens and the cursor stays put (R10 fall-through)."""
    async def scenario() -> None:
        note = tmp_path / "note.txt"
        note.write_text("needle here\n", encoding="utf-8")
        app = YateApp(str(tmp_path))
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            await pilot.press("ctrl+h")
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, FindReplaceScreen)
            _type_query(screen, "needle")
            assert await wait_until(pilot, lambda: len(screen._flat) == 1)
            screen.query_one("#fr-replace", Input).value = "dog"
            screen.query_one("#fr-results", Static).focus()
            await pilot.pause()
            cursor = screen._cursor
            await pilot.press("z")
            await pilot.pause()
            # no crash, no replacement, the overlay stays open untouched
            assert app.screen is screen
            assert screen._cursor == cursor
            assert screen._flat
            assert note.read_text(encoding="utf-8") == "needle here\n"

    asyncio.run(scenario())


def test_f4_no_matches_then_replace_all_still_works(tmp_path: Path) -> None:
    """After a no-match warning the next F4 run enters the loop normally:
    the warn path leaves no state behind that blocks the second pass."""
    async def scenario() -> None:
        note = tmp_path / "note.txt"
        note.write_text("cat cat", encoding="utf-8")
        app = YateApp(str(note), keymap="vim")
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            prompt_bar = app.editor.prompt_bar
            assert prompt_bar is not None
            # first pass: a query with zero hits warns and skips the loop
            await _press_f4_replace(pilot, "zzz", "dog")
            assert "no matches" in message_text(app)
            assert prompt_bar.active_mode is None
            # second pass: a real query still runs, "a" replaces everything
            await _press_f4_replace(pilot, "cat", "dog")
            await pilot.press("a")
            await pilot.pause()
            assert app.editor.session.buffer.get_text() == "dog dog"
            assert "replaced 2" in message_text(app)
    asyncio.run(scenario())


def test_project_replace_enter_jumps_to_match_row_col(tmp_path: Path) -> None:
    """Enter after moving the result cursor lands the editor cursor on the
    match start (Vim search convention) and scrolls the row into view."""
    async def scenario() -> None:
        note = tmp_path / "note.txt"
        note.write_text(
            "needle one\nfiller\nfiller two\nneedle x\nneedle y\n",
            encoding="utf-8",
        )
        app = YateApp(str(tmp_path))
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            await pilot.press("ctrl+h")
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, FindReplaceScreen)
            screen.query_one("#fr-find", Input).value = "needle"
            assert await wait_until(pilot, lambda: len(screen._flat) == 3)
            screen.query_one("#fr-results", Static).focus()
            await pilot.press("down")
            await pilot.pause()
            await pilot.press("enter")
            assert await wait_until(
                pilot, lambda: app.editor.session.is_open(note) is not None
            )
            await pilot.pause()
            await pilot.pause()
            # the second hit is on row 3, starting at column 0
            assert app.editor.session.buffer.cursor == (3, 0)
            view = app.editor.panes.active_view
            assert view is not None
            # reveal_cursor scrolled the match row into the visible window
            top = view.scroll_offset.y
            assert top <= 3 < top + max(1, view.size.height)
    asyncio.run(scenario())


def test_replace_on_disk_preserves_crlf_and_unicode_separators(
    tmp_path: Path,
) -> None:
    """Disk replace keeps CRLF endings and exotic line separators byte-exact:
    only the replaced spans may change, nothing is EOL-normalised."""
    async def scenario() -> None:
        note = tmp_path / "crlf.txt"
        note.write_bytes(b"keep\r\nneedle x\r\nsep\xe2\x80\xa8tail\r\n")
        app = YateApp(str(tmp_path))
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            await pilot.press("ctrl+h")
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, FindReplaceScreen)
            screen.query_one("#fr-find", Input).value = "needle"
            assert await wait_until(pilot, lambda: len(screen._flat) == 1)
            screen.query_one("#fr-replace", Input).value = "swap"
            screen.query_one("#fr-results", Static).focus()
            await pilot.pause()
            await pilot.press("a")
            assert await wait_until(pilot, lambda: "replaced 1" in message_text(app))
            # CRLF endings and the U+2028 separator survive untouched
            assert note.read_bytes() == b"keep\r\nswap x\r\nsep\xe2\x80\xa8tail\r\n"

    asyncio.run(scenario())


def test_replace_on_disk_leaves_no_temp_files(tmp_path: Path) -> None:
    """The atomic write consumes its temp file via os.replace on success."""
    async def scenario() -> None:
        note = tmp_path / "note.txt"
        note.write_text("needle here\n", encoding="utf-8")
        app = YateApp(str(tmp_path))
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            await pilot.press("ctrl+h")
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, FindReplaceScreen)
            screen.query_one("#fr-find", Input).value = "needle"
            assert await wait_until(pilot, lambda: len(screen._flat) == 1)
            screen.query_one("#fr-replace", Input).value = "found"
            screen.query_one("#fr-results", Static).focus()
            await pilot.pause()
            await pilot.press("a")
            assert await wait_until(
                pilot, lambda: "replaced 1" in message_text(app)
            )
            assert note.read_text(encoding="utf-8") == "found here\n"
            assert list(tmp_path.glob("*.yate-tmp-*")) == []

    asyncio.run(scenario())


def test_search_rows_follow_the_newline_line_view(tmp_path: Path) -> None:
    """Hit rows use the newline-only view, like the buffer side."""
    async def scenario() -> None:
        doc = tmp_path / "sep.txt"
        doc.write_text("alpha\u2028beta needle\n", encoding="utf-8")
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            screen, _messages, _notices = _push(app, tmp_path)
            await pilot.pause()
            _type_query(screen, "needle")
            assert await wait_until(pilot, lambda: len(screen._flat) == 1)
            plain = _results_plain(screen)
            assert "1: " in plain
            assert "2: " not in plain

    asyncio.run(scenario())


def test_results_pane_scrolls_to_keep_cursor_visible(tmp_path: Path) -> None:
    """Moving the cursor past the first screenful keeps it in view."""
    async def scenario() -> None:
        doc = tmp_path / "many.txt"
        doc.write_text(
            "".join(f"needle {i}\n" for i in range(45)), encoding="utf-8"
        )
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            screen, _messages, _notices = _push(app, tmp_path)
            await pilot.pause()
            _type_query(screen, "needle")
            assert await wait_until(pilot, lambda: len(screen._flat) == 45)
            screen.query_one("#fr-results", _Results).focus()
            await pilot.pause()
            await pilot.press(*["down"] * 24)
            await pilot.pause()
            scroller = screen.query_one("#fr-results-scroll", VerticalScroll)
            assert scroller.scroll_offset.y > 0

    asyncio.run(scenario())


def test_results_scroll_aligns_with_explorer_scrollbar(tmp_path: Path) -> None:
    """The results scroller paints the explorer's sliver thumb and palette.

    Regression guard: the overlay used to ship a plain ``VerticalScroll``,
    so its scrollbar fell back to Textual's full-cell default thumb in the
    app-theme ``$scrollbar`` color instead of the yate palette.
    """

    async def scenario() -> None:
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            screen, _messages, _notices = _push(app, tmp_path)
            await pilot.pause()
            scroller = screen.query_one("#fr-results-scroll", VerticalScroll)
            explorer = app.query_one("#explorer")
            assert scroller.vertical_scrollbar.renderer is SlimScrollBarRender
            assert (
                scroller.vertical_scrollbar.renderer
                is explorer.vertical_scrollbar.renderer
            )
            assert (
                scroller.styles.scrollbar_color == explorer.styles.scrollbar_color
            )
            assert scroller.styles.scrollbar_color == Color.parse(
                theme.active().border
            )

    asyncio.run(scenario())


def test_fresh_results_start_at_the_top_of_the_pane(tmp_path: Path) -> None:
    """A fresh search must not pin the cursor row to the first line.

    Scrolling to the cursor row unconditionally pushed its file header
    (the file name) out of view on every repaint.
    """

    async def scenario() -> None:
        doc = tmp_path / "many.txt"
        doc.write_text(
            "".join(f"needle {i}\n" for i in range(45)), encoding="utf-8"
        )
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            screen, _messages, _notices = _push(app, tmp_path)
            await pilot.pause()
            _type_query(screen, "needle")
            assert await wait_until(pilot, lambda: len(screen._flat) == 45)
            await pilot.pause()
            scroller = screen.query_one("#fr-results-scroll", VerticalScroll)
            # the first group header (the file name) stays on screen
            assert scroller.scroll_offset.y == 0
            assert "many.txt" in _results_plain(screen)

    asyncio.run(scenario())


def test_results_scroll_back_to_the_first_group_header(tmp_path: Path) -> None:
    """Walking the cursor back up returns the pane to the top.

    Guards the ``_cursor_line < top`` branch across a file-group boundary:
    the cursor row scrolled out of view below must be pulled back without
    losing the file header above it.
    """

    async def scenario() -> None:
        doc = tmp_path / "many.txt"
        doc.write_text(
            "".join(f"needle {i}\n" for i in range(45)), encoding="utf-8"
        )
        other = tmp_path / "other.txt"
        other.write_text(
            "".join(f"needle {i}\n" for i in range(30)), encoding="utf-8"
        )
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            screen, _messages, _notices = _push(app, tmp_path)
            await pilot.pause()
            _type_query(screen, "needle")
            assert await wait_until(pilot, lambda: len(screen._flat) == 75)
            screen.query_one("#fr-results", _Results).focus()
            await pilot.pause()
            scroller = screen.query_one("#fr-results-scroll", VerticalScroll)
            # down into the second file group
            await pilot.press(*["down"] * 50)
            await pilot.pause()
            assert scroller.scroll_offset.y > 0
            assert screen._cursor == 50
            # ...and all the way back: the first header is on screen again.
            # Pressed in batches with pauses -- a single 50-key burst can
            # outrun the refresh that applies the scroll offset.
            for _ in range(5):
                await pilot.press(*["up"] * 10)
                await pilot.pause()
            assert screen._cursor == 0
            # the cursor's first hit is one row below its file header, so
            # scrolling up to that row puts the pane back at the top
            assert await wait_until(
                pilot, lambda: scroller.scroll_offset.y <= 1
            )
            assert "many.txt" in _results_plain(screen)

    asyncio.run(scenario())


def test_footer_hint_drops_on_short_viewports(tmp_path: Path) -> None:
    """The key hint yields its rows to the results pane on a short screen."""

    async def scenario() -> None:
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            screen, _messages, _notices = _push(app, tmp_path)
            await pilot.pause()
            footer = screen.query_one("#fr-footer", Static)
            assert footer.display is True
            await pilot.resize_terminal(100, 14)
            # a single pause can outrun resize delivery under a loaded
            # suite -- wait for each transition to settle instead
            assert await wait_until(pilot, lambda: footer.display is False)
            await pilot.resize_terminal(100, 30)
            assert await wait_until(pilot, lambda: footer.display is True)

    asyncio.run(scenario())


def test_scan_cap_shows_truncation_notice(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reaching the walk file cap surfaces an incomplete-results notice."""
    async def scenario() -> None:
        doc = tmp_path / "note.txt"
        doc.write_text("needle\n", encoding="utf-8")
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            ghosts = [tmp_path / "ghost" / f"g{i}.txt" for i in range(5000)]

            def fake_walk(limit: int) -> list[Path]:
                return [doc, *ghosts]

            monkeypatch.setattr(
                app.editor.workspace,
                "walk_files",
                fake_walk,
            )
            screen, _messages, _notices = _push(app, tmp_path)
            await pilot.pause()
            _type_query(screen, "needle")
            assert await wait_until(pilot, lambda: len(screen._flat) == 1)
            assert "file cap" in _results_plain(screen)

    asyncio.run(scenario())


def test_enter_reveals_clamped_row_when_buffer_shrunk(tmp_path: Path) -> None:
    """A disk hit beyond the (unsaved-shrunk) buffer clamps, never crashes."""
    async def scenario() -> None:
        doc = tmp_path / "note.txt"
        doc.write_text("keep\nneedle here", encoding="utf-8")
        app = YateApp(str(doc))
        async with app.run_test(size=(100, 30)) as pilot:
            buf = app.editor.session.buffer
            buf.set_cursor((1, 0))
            buf.delete_lines()
            assert buf.get_text() == "keep"
            screen, _messages, _notices = _push(
                app, tmp_path, reveal=app.editor.reveal_match,
            )
            await pilot.pause()
            _type_query(screen, "needle")
            assert await wait_until(pilot, lambda: len(screen._flat) == 1)
            screen.query_one("#fr-results", _Results).focus()
            await pilot.press("enter")
            await pilot.pause()
            assert app.screen is not screen
            assert app.editor.session.buffer.cursor == (0, 0)

    asyncio.run(scenario())


def test_results_show_workspace_relative_labels(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A hit below the workspace root is labeled by its relative path.

    The labels are computed once by the search worker (S-08): the render
    path only reads the ``_labels`` dict and never touches the filesystem.
    """
    async def scenario() -> None:
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "a.txt").write_text("needle\n", encoding="utf-8")
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            screen, _messages, _notices = _push(app, tmp_path)
            await pilot.pause()
            _type_query(screen, "needle")
            assert await wait_until(pilot, lambda: len(screen._flat) == 1)
            assert "sub/a.txt" in _results_plain(screen)

            # S-08 performance pin: re-rendering already-landed results
            # must not re-resolve paths (the labels come from the worker's
            # cached ``_labels`` dict, so the render path stays fs-free).
            resolve_calls = 0
            real_resolve = Path.resolve

            def counting_resolve(path: Path, strict: bool = False) -> Path:
                nonlocal resolve_calls
                resolve_calls += 1
                return real_resolve(path, strict)

            monkeypatch.setattr(Path, "resolve", counting_resolve)
            try:
                screen._render_results()
                screen._render_results()
            finally:
                monkeypatch.undo()
            assert resolve_calls == 0

    asyncio.run(scenario())
