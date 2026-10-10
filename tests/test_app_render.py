"""SP3 render-path regression guard headless Textual UI tests (run via pilot, no real terminal)."""

# tests legitimately poke at internals:
# pyright: reportPrivateUsage=false

from __future__ import annotations

import asyncio
import threading
from pathlib import Path
from unittest.mock import patch
import pytest
from rich.style import Style
from textual.strip import Strip
from yate.app import YateApp
from yate.editor_syntax.tokens import Token
from yate.editor_view.manual import MarkdownDocScreen
from conftest import wait_until
from manual_doc_fixture import MANUAL_DOC_FIXTURE

# ------------------------------------------- SP3 render-path regression guards


def _style_at_cell(strip: Strip, cell: int) -> Style | None:
    """The Rich style covering display *cell* of *strip* (``None`` past end)."""
    offset = 0
    for segment in strip:
        if cell < offset + len(segment.text):
            return segment.style
        offset += len(segment.text)
    return None


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

            import yate.editor_view.highlighting as highlighting_module

            real_tokenize = highlighting_module._tokenize_with_states
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
                highlighting_module, "_tokenize_with_states", slow_tokenize
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
    asyncio.run(scenario())


def test_render_paints_cursor_block_on_each_extra_point_row(
    tmp_path: Path,
) -> None:
    """IKKJHH: each extra multi-cursor point paints its own block cursor.

    The extra point on row 1 gets an ``S_CURSOR`` cell (reverse + bold);
    the main cursor on row 0 is untouched.
    """

    async def scenario() -> None:
        target = tmp_path / "multi.txt"
        target.write_text("alpha beta\ngamma delta\n", encoding="utf-8")
        app = YateApp(target=target)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            editor = app.editor.panes.active_view
            assert editor is not None
            buf = app.editor.session.buffer
            assert buf.lines == ["alpha beta", "gamma delta", ""]
            assert buf.add_cursor_at((1, 5))

            from yate.editor_view import theme

            gutter = editor.gutter_width()
            tw = buf.tab_width
            extra_cell = gutter + theme.char_to_cell(buf.lines[1], 5, tw)

            strip = editor.render_line(1)
            extra_style = _style_at_cell(strip, extra_cell)
            assert extra_style is not None
            assert extra_style.reverse and extra_style.bold
            # neighbouring cells stay normal (no overlay leak)
            neighbour = _style_at_cell(strip, gutter + 1)
            assert neighbour is not None
            assert not neighbour.reverse

            # main cursor on row 0 keeps its own block cursor cell
            main_cell = gutter + theme.char_to_cell(buf.lines[0], 0, tw)
            main_style = _style_at_cell(editor.render_line(0), main_cell)
            assert main_style is not None
            assert main_style.reverse and main_style.bold

    asyncio.run(scenario())


def test_render_extra_point_at_row_end_expands_cells(tmp_path: Path) -> None:
    """IKKJHH: a point on (row, len(line)) expands the row by one cell.

    The end-of-line block-cell padding must happen before ``n_cells`` is
    counted, so the padded cell is actually rendered with ``S_CURSOR``.
    """

    async def scenario() -> None:
        target = tmp_path / "multi.txt"
        target.write_text("alpha beta\ngamma delta\n", encoding="utf-8")
        app = YateApp(target=target)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            editor = app.editor.panes.active_view
            assert editor is not None
            buf = app.editor.session.buffer
            row_len = len(buf.lines[1])
            assert buf.add_cursor_at((1, row_len))

            gutter = editor.gutter_width()
            strip = editor.render_line(1)
            end_style = _style_at_cell(strip, gutter + row_len)
            assert end_style is not None
            assert end_style.reverse and end_style.bold

    asyncio.run(scenario())


def test_render_no_extra_points_matches_baseline(tmp_path: Path) -> None:
    """IKKJHH: without extra points rendering matches the single-cursor base.

    Exactly one cursor-styled cell exists -- the main cursor's -- and no
    other row paints a block cursor.
    """

    async def scenario() -> None:
        target = tmp_path / "single.txt"
        target.write_text("alpha beta\ngamma delta\n", encoding="utf-8")
        app = YateApp(target=target)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            editor = app.editor.panes.active_view
            assert editor is not None
            buf = app.editor.session.buffer
            assert not buf.has_extra_cursors()

            gutter = editor.gutter_width()
            for row in range(3):
                strip = editor.render_line(row)
                cursor_cells = [
                    cell
                    for cell in range(gutter, gutter + 32)
                    if (s := _style_at_cell(strip, cell)) is not None
                    and s.reverse and s.bold
                ]
                if row == buf.row:
                    assert cursor_cells == [gutter + buf.col]
                else:
                    assert cursor_cells == []

    asyncio.run(scenario())
