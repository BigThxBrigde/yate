"""FindReplaceScreen pilot tests (pushed directly, no wiring -- run via pilot)."""

# tests legitimately poke at internals:
# pyright: reportPrivateUsage=false

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from textual.widgets import Input, Static

from yate.app import YateApp
from yate.editor_core import project_search
from yate.editor_view.find_replace import FindReplaceScreen, RevealFn

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
