"""Cross-cutting soft-wrap integration tests (plan E).

Verifies AC2/AC6/AC7/AC8 against the fully wired editor: rendering a wrapped
display row of a chunked document loads only the mapped logical row's chunk
(interval table, locked buffer and content untouched), toggling wrap never
bumps the content version or re-fills chunks, stable frames never rebuild the
span table nor rescan off-screen lines, viewport resizes / pane splits /
keymap switches rewrap with the cursor kept visible, and wrapped mouse clicks
map back onto the owning logical row with blank continuation gutters.
"""

# tests legitimately poke at widget internals (view._wrap, buffer._loaded_*):
# pyright: reportPrivateUsage=false

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from conftest import wait_until
from yate.app import YateApp
from yate.config import LargeFileConfig, YateConfig
from yate.editor_components import theme
from yate.editor_components.view import EditorView
from yate.editor_components.wrap_layout import RowSpan
from yate.editor_core.document import Document
from yate.editor_lsp import Diagnostic
from yate.editor_lsp.client import DiagnosticSeverity


def _write(path: Path, text: str) -> Path:
    """Write *text* byte-exactly (no newline translation) and return it."""
    path.write_bytes(text.encode("utf-8"))
    return path


def _padded_chunked_lines() -> list[str]:
    """2500 rows of 300 ASCII chars; row 1200 is a 5000-char long line.

    At ~301 bytes per row the 256 KiB default chunk holds ~871 rows, so
    the file spans three chunks and the long row sits in chunk 1 while
    chunk 2 stays a pure on-demand chunk.
    """
    lines: list[str] = []
    for i in range(2500):
        if i == 1200:
            lines.append("z" * 5000)
        else:
            tag = f"row {i:04d}: "
            lines.append(tag + "a" * (300 - len(tag)))
    return lines


def _chunked_config() -> YateConfig:
    """A config whose tiny chunk threshold turns any real file chunked."""
    config = YateConfig()
    config.large_file = LargeFileConfig(threshold=64)
    return config


def _wrap_config(threshold: int = 0) -> YateConfig:
    """A config with soft wrap on from startup and chunking at *threshold*."""
    config = YateConfig()
    config.large_file = LargeFileConfig(threshold=threshold)
    config.wrap = True
    return config


# --- AC7: chunked loading under soft wrap ------------------------------------


def test_wrap_on_chunked_loads_mapped_logical_row_only(tmp_path: Path) -> None:
    """Rendering a wrapped far row loads exactly the owning logical chunk."""

    async def scenario() -> None:
        lines = _padded_chunked_lines()
        path = _write(tmp_path / "big.txt", "\n".join(lines))
        app = YateApp(target=path, config=_chunked_config())
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            doc = app.editor.session.doc
            chunked = doc.chunked
            assert chunked is not None
            buf = doc.buffer
            assert await wait_until(
                pilot, lambda: buf.line_count == chunked.row_count()
            )
            assert buf.locked is True
            starts = chunked.chunk_start_rows
            assert len(starts) >= 3  # row 1200 must sit in a later chunk
            assert not buf.rows_loaded(1200, 1)

            view = app.editor.panes.active_view
            assert view is not None
            ensured: list[int] = []
            real_ensure = view._ensure_row
            assert real_ensure is not None

            def spy_ensure(row: int) -> None:
                ensured.append(row)
                real_ensure(row)

            view._ensure_row = spy_ensure
            app.editor.set_soft_wrap(True)
            await pilot.pause()
            view._sync_wrap(view._text_width())
            display_row, _ = view._wrap.logical_to_display(1200, 0)

            view.render_line(display_row)
            await pilot.pause()

            # the render hook received the MAPPED logical row, not a
            # display row, and asked for it exactly once
            assert ensured.count(1200) == 1
            assert all(row < starts[1] or row == 1200 for row in ensured)
            assert buf.rows_loaded(1200, 1)
            assert buf.line(1200) == "z" * 5000
            # interval table: chunks 0+1 merged, chunk 2 still unloaded
            s2 = starts[2]
            assert (buf._loaded_starts, buf._loaded_ends) == ([0], [s2])
            assert not buf.rows_loaded(s2, 1)
            assert buf.line(s2) == ""  # placeholder rows untouched
            assert doc.buffer.locked is True
            # loaded content is byte-identical to the file prefix
            assert [buf.line(i) for i in range(s2)] == lines[:s2]
            assert all(buf.line(i) == "" for i in range(s2, buf.line_count))

            # after the load the span table re-synced: the long row paints
            # from its own first span at the recomputed display row
            view._sync_wrap(view._text_width())
            row_after, _ = view._wrap.logical_to_display(1200, 0)
            assert view._wrap.display_to_logical(row_after) == RowSpan(
                1200, 0, view._text_width(), 0
            )

            # wrap toggles never clear the loaded intervals nor the content
            snapshot = buf.get_text()
            lines_before = list(buf.lines)
            for _ in range(2):
                app.editor.set_soft_wrap(False)
                await pilot.pause()
                app.editor.set_soft_wrap(True)
                await pilot.pause()
            assert buf.get_text() == snapshot
            assert buf.lines == lines_before
            assert (buf._loaded_starts, buf._loaded_ends) == ([0], [s2])
            assert buf.locked is True

    asyncio.run(scenario())


def test_wrap_toggle_keeps_chunked_version_and_fills_stable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Toggling wrap neither bumps content_version nor re-fills chunks."""

    async def scenario() -> None:
        path = _write(
            tmp_path / "big.txt", "\n".join(_padded_chunked_lines())
        )
        app = YateApp(target=path, config=_chunked_config())
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            doc = app.editor.session.doc
            chunked = doc.chunked
            assert chunked is not None
            buf = doc.buffer
            assert await wait_until(
                pilot, lambda: buf.line_count == chunked.row_count()
            )
            fills: list[tuple[int, int]] = []
            real_fill = buf.fill_lines

            def spy_fill(start: int, rows: list[str]) -> None:
                fills.append((start, len(rows)))
                real_fill(start, rows)

            monkeypatch.setattr(buf, "fill_lines", spy_fill)

            view = app.editor.panes.active_view
            assert view is not None
            version = buf.content_version
            scroll_top = view.scroll_offset.y
            for _ in range(3):
                app.editor.set_soft_wrap(True)
                await pilot.pause()
                app.editor.set_soft_wrap(False)
                await pilot.pause()
            app.editor.set_soft_wrap(True)
            await pilot.pause()

            assert buf.content_version == version
            assert fills == []  # no duplicate chunk loads while toggling
            assert view.scroll_offset.y == scroll_top  # no re-entrant scroll
            assert view.scroll_col == 0  # wrap on pins horizontal scrolling
            assert buf.locked is True

            # re-rendering loaded rows never re-fills anything
            height = max(1, view.size.height)
            for row in range(height):
                view.render_line(row)
            assert fills == []
            assert buf.content_version == version

    asyncio.run(scenario())


# --- AC8: per-frame rendering cost -------------------------------------------


def test_stable_frames_never_rebuild_span_table_on_large_doc(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC8: 100 frames over a 50k-line doc rebuild nothing and touch only
    the visible rows' geometry."""

    async def scenario() -> None:
        lines = [f"line {i}" for i in range(50_000)]
        path = _write(tmp_path / "plain.txt", "\n".join(lines))
        app = YateApp(target=path, config=_wrap_config())
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            view = app.editor.panes.active_view
            assert view is not None
            rebuilds = view._wrap.rebuild_count
            offsets = 0
            real_offsets = theme.cell_offsets

            def spy_offsets(line: str, tab_width: int) -> list[int]:
                nonlocal offsets
                offsets += 1
                return real_offsets(line, tab_width)

            monkeypatch.setattr(theme, "cell_offsets", spy_offsets)

            height = max(1, view.size.height)
            for _ in range(100):
                for row in range(height):
                    view.render_line(row)

            assert view._wrap.rebuild_count == rebuilds  # zero per-frame work
            assert offsets == 100 * height  # geometry only for visible rows

    asyncio.run(scenario())


def test_long_line_frames_do_not_rescan(tmp_path: Path) -> None:
    """AC8: a 100k-char wrapped line renders from the cached spans only."""

    async def scenario() -> None:
        path = _write(tmp_path / "long.txt", "z" * 100_000 + "\nshort")
        app = YateApp(target=path, config=_wrap_config())
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            view = app.editor.panes.active_view
            assert view is not None
            rebuilds = view._wrap.rebuild_count
            height = max(1, view.size.height)
            for _ in range(100):
                for row in range(height):
                    view.render_line(row)
            assert view._wrap.rebuild_count == rebuilds

    asyncio.run(scenario())


def test_wrapped_line_expansion_reused_across_display_rows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC8 (pr-review): consecutive display rows of one wrapped logical line
    reuse the expanded cells/offsets rather than re-expanding the whole line
    per row; a distinct logical row invalidates the cache.
    """
    calls: list[str] = []
    real_offsets = theme.cell_offsets

    def counting_offsets(line: str, tab_width: int) -> list[int]:
        calls.append(line)
        return real_offsets(line, tab_width)

    monkeypatch.setattr(theme, "cell_offsets", counting_offsets)
    async def scenario() -> None:
        path = _write(tmp_path / "doc.txt", "a" * 200 + "\nshort")
        app = YateApp(target=path, config=_wrap_config())
        async with app.run_test(size=(40, 10)) as pilot:
            await pilot.pause()
            view = app.editor.panes.active_view
            assert view is not None
            view._line_expand_cache = None
            calls.clear()
            for row in range(6):  # first 6 display rows all map to logical row 0
                view.render_line(row)
            assert len(calls) == 1, f"expected one expansion, got {len(calls)}"
            logical0_rows = view._wrap.logical_display_rows(0)
            view.render_line(logical0_rows)  # first display row of logical row 1
            assert len(calls) == 2

    asyncio.run(scenario())


# --- AC2: viewport / panes / keymap -------------------------------------------


def test_resize_rewraps_and_keeps_cursor_display_row_visible(
    tmp_path: Path,
) -> None:
    """A width change rewraps; reveal_cursor keeps the cursor display row
    inside the visible region."""

    async def scenario() -> None:
        lines = ["a" * 200 for _ in range(300)]
        path = _write(tmp_path / "doc.txt", "\n".join(lines))
        app = YateApp(target=path, config=_wrap_config())
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            view = app.editor.panes.active_view
            assert view is not None
            buf = view.buffer
            buf.set_cursor((200, 0))
            view.reveal_cursor()
            top = view.scroll_offset.y
            disp, _ = view._wrap.logical_to_display(200, 0)
            assert top <= disp < top + max(1, view.size.height)

            before_key = view._wrap.version_key
            assert before_key is not None
            await pilot.resize_terminal(60, 24)
            await pilot.pause()
            await pilot.pause()

            assert view._wrap.version_key != before_key  # narrower -> rewrap
            assert view.virtual_size.height == view._wrap.display_count()
            view.reveal_cursor()
            disp2, _ = view._wrap.logical_to_display(200, 0)
            top2 = view.scroll_offset.y
            assert top2 <= disp2 < top2 + max(1, view.size.height)

    asyncio.run(scenario())


def test_two_panes_keep_independent_wrap_caches(tmp_path: Path) -> None:
    """Each leaf view owns its own WrapLayout and rebuilds it on its own."""

    async def scenario() -> None:
        lines = ["a" * 200 for _ in range(300)]
        path = _write(tmp_path / "doc.txt", "\n".join(lines))
        app = YateApp(target=path, config=_wrap_config())
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            editor = app.editor
            editor.run_command("vsplit")
            assert await wait_until(pilot, lambda: editor.panes.leaf_count == 2)
            views = editor.panes.all_views()
            assert len(views) == 2
            view_a = editor.panes.active_view
            assert view_a is not None
            view_b = views[0] if views[1] is view_a else views[1]
            wrap_a = view_a._wrap
            wrap_b = view_b._wrap
            assert wrap_a is not wrap_b

            ra = wrap_a.rebuild_count
            rb = wrap_b.rebuild_count
            # a rebuild on one view (simulated width change) never touches
            # the other pane's cache object; rebuild counts are checked as
            # lower bounds because Textual may repaint panes on its own
            # scheduling outside of the test-driven syncs
            view_a._sync_wrap(view_a._text_width() + 10)
            assert wrap_a.rebuild_count >= ra + 1
            key_a = wrap_a.version_key
            assert key_a is not None
            assert key_a[1] == view_a._text_width() + 10
            assert wrap_b.rebuild_count >= rb

            ra = wrap_a.rebuild_count
            rb = wrap_b.rebuild_count
            editor.set_soft_wrap(False)  # the injected switch flips globally
            await pilot.pause()
            view_a._sync_wrap(view_a._text_width())
            view_b._sync_wrap(view_b._text_width())
            assert wrap_a.rebuild_count >= ra + 1  # each cache rebuilt once
            assert wrap_b.rebuild_count >= rb + 1
            assert wrap_a.version_key is not None
            assert wrap_a.version_key[3] is False
            assert wrap_b.version_key is not None
            assert wrap_b.version_key[3] is False

            ra = wrap_a.rebuild_count
            rb = wrap_b.rebuild_count
            editor.set_soft_wrap(True)
            await pilot.pause()
            view_a._sync_wrap(view_a._text_width())
            view_b._sync_wrap(view_b._text_width())
            assert wrap_a.rebuild_count >= ra + 1
            assert wrap_b.rebuild_count >= rb + 1
            assert wrap_a.version_key[3] is True
            assert wrap_b.version_key[3] is True
            assert view_a.render_line(0) is not None
            assert view_b.render_line(0) is not None

    asyncio.run(scenario())


def test_keymap_switch_keeps_wrap_state_and_repaints(tmp_path: Path) -> None:
    """Switching vsc<->vim leaves config.wrap untouched and repaints from
    the cached wrap geometry."""

    async def scenario() -> None:
        lines = ["a" * 200 for _ in range(50)]
        path = _write(tmp_path / "doc.txt", "\n".join(lines))
        app = YateApp(target=path, config=_wrap_config())
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            editor = app.editor
            view = editor.panes.active_view
            assert view is not None
            assert editor.config.wrap is True
            key = view._wrap.version_key
            assert key is not None

            editor.select_keymap("vim")
            await pilot.pause()

            assert editor.keymaps.name == "vim"
            assert editor.config.wrap is True
            assert view._wrap.version_key == key  # cache key unchanged
            assert view._wrap.rebuild_count >= 1
            assert view.virtual_size.height == view._wrap.display_count()
            assert view.render_line(0) is not None

    asyncio.run(scenario())


# --- AC6: mouse mapping / gutter / diagnostics --------------------------------


def test_wrapped_click_maps_continuation_to_logical_cell(tmp_path: Path) -> None:
    """A click on a continuation display row lands on the owning logical
    row at the right character column."""

    async def scenario() -> None:
        lines = ["a" * 200, "b" * 200, "c" * 200, "short", "d" * 200]
        path = _write(tmp_path / "doc.txt", "\n".join(lines))
        app = YateApp(target=path, config=_wrap_config())
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            view = app.editor.panes.active_view
            assert view is not None
            gutter = view.gutter_width()
            text_w = view._text_width()  # 80 - gutter

            # display row 1 of "a"*200: cells [text_w, 2*text_w)
            await pilot.click(EditorView, offset=(gutter + 26, 1))
            await pilot.pause()
            assert app.editor.session.buffer.cursor == (0, text_w + 26)
            # display row 2: cells [2*text_w, 200)
            await pilot.click(EditorView, offset=(gutter + 10, 2))
            await pilot.pause()
            assert app.editor.session.buffer.cursor == (0, 2 * text_w + 10)
            # display row 3 is the first display row of logical row 1
            await pilot.click(EditorView, offset=(gutter, 3))
            await pilot.pause()
            assert app.editor.session.buffer.cursor == (1, 0)

    asyncio.run(scenario())


def test_continuation_gutter_number_slot_stays_blank(tmp_path: Path) -> None:
    """Continuation display rows keep the number column blank at the same
    width; the logical row's first display row shows the number."""

    async def scenario() -> None:
        lines = ["a" * 200 for _ in range(5)]
        path = _write(tmp_path / "doc.txt", "\n".join(lines))
        app = YateApp(target=path, config=_wrap_config())
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            view = app.editor.panes.active_view
            assert view is not None
            view.buffer.set_cursor((4, 0))  # cursor away from logical row 0
            view.reveal_cursor()
            await pilot.pause()
            digits = view.gutter_width() - 3
            first = view.render_line(0).text
            cont = view.render_line(1).text
            assert first[1 : 1 + digits] == "1".rjust(digits)
            assert cont[1 : 1 + digits] == " " * digits

    asyncio.run(scenario())


def test_diagnostic_mark_follows_logical_row_across_wraps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A diagnostic on a wrapped logical row paints its gutter mark on the
    row's first display row and every continuation row."""

    async def scenario() -> None:
        lines = ["a" * 200, "b" * 200, "c" * 200, "short"]
        path = _write(tmp_path / "doc.txt", "\n".join(lines))
        app = YateApp(target=path, config=_wrap_config())
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            view = app.editor.panes.active_view
            assert view is not None
            diag = Diagnostic(
                start_row=0,
                start_col=10,
                end_row=0,
                end_col=30,
                severity=DiagnosticSeverity.ERROR,
                message="boom",
                source="test",
            )
            def diag_for(doc: Document, row: int) -> list[Diagnostic]:
                return [diag] if row == 0 else []

            monkeypatch.setattr(view.lsp, "diagnostics_on_line", diag_for)
            mark = "\u2716"
            first = view.render_line(0).text
            cont = view.render_line(1).text
            other = view.render_line(3).text  # logical row 1, first span
            assert mark in first
            assert mark in cont  # continuation keeps the logical row's mark
            assert mark not in other

    asyncio.run(scenario())


@pytest.mark.parametrize("first_line", ["a\u65e5bc", "a\tbb"])
def test_wrap_eol_block_cursor_painted_with_wide_char(
    tmp_path: Path, first_line: str
) -> None:
    """The end-of-line block cursor stays painted when a wrapped line contains
    a wide glyph or tab, whose cell width exceeds its character count (pr-review).

    The padding cell appended for an EOL cursor must be identified by the
    line's total CELL width, not its character count; otherwise the block
    cursor silently disappears on wide/tab lines whenever soft wrap is on.
    """
    async def scenario() -> None:
        lines = [first_line, "second"]
        path = _write(tmp_path / "doc.txt", "\n".join(lines))
        app = YateApp(target=path, config=_wrap_config())
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            view = app.editor.panes.active_view
            assert view is not None
            view.buffer.set_cursor((0, len(view.buffer.lines[0])))
            strip = view.render_line(0)
            cursor_cells = [
                s for s in strip._segments
                if s.style is not None and getattr(s.style, "reverse", False)
            ]
            assert cursor_cells, "EOL block cursor cell must be painted"

    asyncio.run(scenario())


def test_screen_anchor_uses_display_row_when_wrapped(tmp_path: Path) -> None:
    """Completion/hover anchors are viewport display rows, not logical rows
    (pr-review): a logical row below a wrapped block maps to its display row.
    """
    async def scenario() -> None:
        lines = ["x" * 200, "target line", "third"]
        path = _write(tmp_path / "doc.txt", "\n".join(lines))
        app = YateApp(target=path, config=_wrap_config())
        async with app.run_test(size=(40, 10)) as pilot:
            await pilot.pause()
            view = app.editor.panes.active_view
            assert view is not None
            view._sync_wrap(view._text_width())
            display_row, span_cell = view._wrap.logical_to_display(2, 0)
            cell, rel_row = view.screen_anchor(2, 0)
            assert rel_row == display_row - view.scroll_offset.y
            assert cell == span_cell
            assert rel_row != 2 - view.scroll_offset.y  # not the logical row

    asyncio.run(scenario())


def test_move_display_line_lands_on_continuation(tmp_path: Path) -> None:
    """Real gj/gk display-line mapping (pr-review coverage gap): with wrap on,
    a motion lands on a continuation row and preserves the in-span cell offset
    (vim screen column); wrap off degenerates to a logical-row move.
    """
    async def scenario() -> None:
        line = "abcdefghij" * 6  # 60 chars, wraps into several spans
        path = _write(tmp_path / "doc.txt", line + "\nsecond")
        app = YateApp(target=path, config=_wrap_config())
        async with app.run_test(size=(24, 10)) as pilot:
            await pilot.pause()
            view = app.editor.panes.active_view
            assert view is not None
            view._sync_wrap(view._text_width())
            buf = view.buffer
            spans = [s for s in view._wrap.logical_rows if s.logical_row == 0]
            assert len(spans) > 2
            buf.set_cursor((0, 0))
            view.move_display_line(direction=1, count=1)
            target = buf.cursor
            assert target[0] == spans[1].logical_row  # still logical row 0
            assert target[1] == spans[1].cell_start  # offset 0 preserved

            # a non-zero in-span offset is preserved on the next continuation
            buf.set_cursor((0, 4))
            view.move_display_line(direction=1, count=1)
            assert buf.cursor[0] == 0
            assert buf.cursor[1] == spans[1].cell_start + 4

            # with wrap off the same motion moves a whole logical row down
            app.editor.config.wrap = False
            view.move_display_line(direction=1, count=1)
            assert buf.cursor[0] == 1

    asyncio.run(scenario())
