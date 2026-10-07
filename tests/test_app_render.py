"""SP3 render-path regression guard headless Textual UI tests (run via pilot, no real terminal)."""

# tests legitimately poke at internals:
# pyright: reportPrivateUsage=false

from __future__ import annotations

import asyncio
import threading
from pathlib import Path
from unittest.mock import patch
import pytest
from yate.app import YateApp
from yate.editor_syntax.tokens import Token
from yate.editor_view.manual import MarkdownDocScreen
from conftest import wait_until
from manual_doc_fixture import MANUAL_DOC_FIXTURE

# ------------------------------------------- SP3 render-path regression guards


def test_render_line_queries_diagnostics_once_per_row(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """S12: render_line looks up the row's diagnostics exactly once.

    The gutter marks and the underline pass share one ``diagnostics_on_line``
    lookup per rendered row; the pre-fix code scanned the diagnostics twice
    for every row.
    """

    async def scenario() -> None:
        target = tmp_path / "diag.py"
        target.write_text(
            "x = 1\ny = 2\nz = 3\nw = 4\nv = 5\n", encoding="utf-8"
        )
        app = YateApp(target=target)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            from yate.editor_core.document import Document
            from yate.editor_lsp import Diagnostic, protocol

            app.editor.lsp.handle_notification(
                "textDocument/publishDiagnostics",
                {
                    "uri": protocol.path_to_uri(target.resolve()),
                    "diagnostics": [
                        {
                            "range": {
                                "start": {"line": 0, "character": 0},
                                "end": {"line": 0, "character": 1},
                            },
                            "severity": 1,
                            "message": "boom",
                            "source": "test",
                        },
                        {
                            "range": {
                                "start": {"line": 2, "character": 0},
                                "end": {"line": 2, "character": 1},
                            },
                            "severity": 2,
                            "message": "meh",
                            "source": "test",
                        },
                    ],
                },
            )
            await pilot.pause()
            editor = app.editor.panes.active_view
            assert editor is not None
            lsp = app.editor.lsp
            calls: list[int] = []
            real = lsp.diagnostics_on_line

            def counting(doc: Document, row: int) -> list[Diagnostic]:
                calls.append(row)
                return real(doc, row)

            monkeypatch.setattr(lsp, "diagnostics_on_line", counting)

            # exactly one lookup per rendered row, in row order
            for row in range(5):
                editor.render_line(row)
            assert calls == [0, 1, 2, 3, 4]

    asyncio.run(scenario())


def test_welcome_rows_cached_per_theme_and_keymap() -> None:
    """S13: welcome rows are reused until the theme or keymap changes."""

    async def scenario() -> None:
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            editor = app.editor.panes.active_view
            assert editor is not None
            from yate.editor_view import theme

            # same (theme, keymap) cache key: the same row list object
            first = editor._welcome_lines(theme.active(), vim_keys=False)
            assert editor._welcome_lines(theme.active(), vim_keys=False) is first

            # keymap switch changes the cache key -> rows rebuilt
            await pilot.press("ctrl+/")
            assert editor.keymaps.name == "vim"
            vim_rows = editor._welcome_lines(theme.active(), vim_keys=True)
            assert vim_rows is not first
            assert editor._welcome_lines(theme.active(), vim_keys=True) is vim_rows

            # theme switch changes the key too -> rebuilt under latte
            try:
                app.editor.set_theme("latte")
                await pilot.pause()
                latte_rows = editor._welcome_lines(theme.active(), vim_keys=True)
                assert latte_rows is not vim_rows
            finally:
                theme.set_theme("mocha")  # restore default for other tests

    asyncio.run(scenario())


def test_discarded_highlight_pass_reschedules_immediately(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """S14: a stale (discarded) tokenize pass re-arms without debouncing."""

    async def scenario() -> None:
        target = tmp_path / "script.py"
        target.write_text("def foo():\n    return 42\n", encoding="utf-8")
        app = YateApp(target=target)
        async with app.run_test(size=(100, 30)) as pilot:
            editor = app.editor.panes.active_view
            assert editor is not None
            assert await wait_until(
                pilot, lambda: editor.highlight_probe().tokens is not None,
                timeout=5.0,
            )

            import yate.editor_view.editor as editor_module

            real_tokenize = editor_module._tokenize_with_states
            started = threading.Event()
            gate = threading.Event()

            def slow_tokenize(
                lines: list[str], filetype: str
            ) -> tuple[list[list[Token]], tuple[int, ...]]:
                # hold the in-flight pass until the test has bumped the
                # buffer version, making the pending result stale
                started.set()
                gate.wait(timeout=5.0)
                return real_tokenize(lines, filetype)

            monkeypatch.setattr(
                editor_module, "_tokenize_with_states", slow_tokenize
            )
            delays: list[float] = []
            real_schedule = editor._schedule_highlight

            def tracking_schedule(delay: float) -> None:
                delays.append(delay)
                real_schedule(delay)

            monkeypatch.setattr(
                editor, "_schedule_highlight", tracking_schedule
            )

            # start a pass and let it block inside the tokenizer thread
            editor._schedule_highlight(0.0)
            assert await wait_until(pilot, started.is_set, timeout=5.0)
            delays.clear()

            # edit while the pass is in flight: its result is discarded and
            # the replacement pass must start immediately (delay 0.0) instead
            # of costing another debounce window on top
            app.editor.session.buffer.insert_text("x")
            gate.set()
            new_version = app.editor.session.buffer.content_version
            assert await wait_until(
                pilot,
                lambda: editor.highlight_probe().tokens is not None
                and editor.highlight_probe().version == new_version
                and editor.highlight_probe().scheduled_key is None,
                timeout=5.0,
            )
            assert delays and delays[0] == 0.0

    asyncio.run(scenario())


def test_render_line_computes_cursor_anchor_once_per_row(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """S15: one cursor/anchor lookup per rendered row (was three)."""

    async def scenario() -> None:
        target = tmp_path / "script.py"
        target.write_text("def foo():\n    return 42\n", encoding="utf-8")
        app = YateApp(target=target)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            editor = app.editor.panes.active_view
            assert editor is not None

            from yate.editor_core.buffer import Pos

            calls = 0
            real = editor._cursor_anchor

            def counting() -> tuple[Pos, Pos | None]:
                nonlocal calls
                calls += 1
                return real()

            monkeypatch.setattr(editor, "_cursor_anchor", counting)

            # the pair is computed once per row and shared by the cursor
            # paint, the selection and the style-range passes
            editor.render_line(0)
            assert calls == 1
            editor.render_line(1)
            assert calls == 2

    asyncio.run(scenario())


def test_doc_search_debounce_merges_rapid_typing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """S40: rapid doc-search typing merges into one debounced rebuild."""

    async def scenario() -> None:
        app = YateApp()
        with patch(
            "yate.editor_view.manual.load_doc_markdown",
            return_value=MANUAL_DOC_FIXTURE,
        ):
            async with app.run_test(size=(100, 30)) as pilot:
                await pilot.pause()
                await pilot.press("f8")
                await pilot.pause()
                screen = app.screen
                assert isinstance(screen, MarkdownDocScreen)
                from textual.widgets import Static

                loading = screen.query_one("#doc-loading", Static)
                assert await wait_until(
                    pilot, lambda: not loading.display, timeout=15.0
                )
                # freeze the trailing window before touching the input: with a
                # 30s debounce the timer cannot fire mid-test no matter how the
                # runner schedules the presses (a loaded CI box once let the
                # real 0.12s window elapse between keystrokes and recorded an
                # intermediate rebuild, ['ke', 'key'])
                monkeypatch.setattr(screen, "_SEARCH_DEBOUNCE_S", 30.0)
                await pilot.press("slash")
                await pilot.pause()

                calls: list[str] = []
                real_search = screen._run_search

                def counting(query: str) -> None:
                    calls.append(query)
                    real_search(query)

                monkeypatch.setattr(screen, "_run_search", counting)

                # four keystrokes: zero rebuilds while typing (the merge), then
                # one rebuild carrying the final query when the window callback
                # runs
                keys = ("t", "h", "e", "m")
                await pilot.press(*keys)
                await pilot.pause()
                assert calls == []
                # the trailing window really is armed and pending (the manual
                # flush below only covers the callback body, not the arming)
                assert screen._search_timer is not None
                screen._flush_search()
                assert calls == ["".join(keys)]

    asyncio.run(scenario())


def test_doc_search_enter_flushes_pending_query_immediately(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """S40: submitting runs the pending query without waiting the window."""

    async def scenario() -> None:
        app = YateApp()
        with patch(
            "yate.editor_view.manual.load_doc_markdown",
            return_value=MANUAL_DOC_FIXTURE,
        ):
            async with app.run_test(size=(100, 30)) as pilot:
                await pilot.pause()
                await pilot.press("f8")
                await pilot.pause()
                screen = app.screen
                assert isinstance(screen, MarkdownDocScreen)
                from textual.widgets import Static

                loading = screen.query_one("#doc-loading", Static)
                assert await wait_until(
                    pilot, lambda: not loading.display, timeout=15.0
                )
                # freeze the trailing window before touching the input: with a
                # 30s debounce no timer can fire, so the only way a search can
                # run is the enter flush itself
                monkeypatch.setattr(screen, "_SEARCH_DEBOUNCE_S", 30.0)
                await pilot.press("slash")
                await pilot.pause()

                calls: list[str] = []
                real_search = screen._run_search

                def counting(query: str) -> None:
                    calls.append(query)
                    real_search(query)

                monkeypatch.setattr(screen, "_run_search", counting)

                # type, then submit: enter must flush the pending query right
                # away instead of waiting the (frozen) window
                await pilot.press("k", "e", "y")
                await pilot.press("enter")
                await pilot.pause()
                assert calls == ["key"]

    asyncio.run(scenario())
