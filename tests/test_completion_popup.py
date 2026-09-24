"""Tests for the completion popup and the buffer completion source.

The popup is a non-focusable widget whose ``show`` / ``render_line`` /
``select_*`` / ``close`` only touch its own state, so the geometry, the row
rendering and the selection are asserted without spinning a Textual app; the
buffer/path candidate builders are plain functions over a ``TextBuffer``.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any, Callable

import pytest

from yate.app import YateApp
from yate.editor_core import Document
from yate.editor_core.buffer import TextBuffer
from yate.editor_lsp.client import Completion
from yate.editor_view import completion


def _private(name: str) -> Any:
    """Reach a module-private helper on purpose (they carry the logic)."""
    return getattr(completion, name)


def _item(label: str, detail: str = "", kind: int = 0) -> Completion:
    """A completion item that inserts its own label."""
    return Completion(label=label, insert_text=label, detail=detail, kind=kind)


def _popup() -> completion.CompletionPopup:
    """A popup in its post-mount state (no app needed for these code paths)."""
    widget = completion.CompletionPopup()
    widget.on_mount()
    return widget


def _text(strip: Any) -> str:
    return "".join(segment.text for segment in strip)


def _box_size(popup: completion.CompletionPopup) -> tuple[float, float]:
    """The popup's (width, height) in cells, as ``show`` left them."""
    width = popup.styles.width
    height = popup.styles.height
    assert width is not None and height is not None
    return width.value, height.value


def _box_origin(popup: completion.CompletionPopup) -> tuple[float, float]:
    """The popup's (x, y) offset in cells, as ``show`` left it."""
    x = popup.styles.offset.x.value
    y = popup.styles.offset.y.value
    return x, y


# --- popup geometry ---------------------------------------------------------


def test_show_opens_below_the_cursor_and_reports_its_state() -> None:
    """The box starts at the cursor column, one row under the cursor."""
    popup = _popup()
    popup.show([_item("alpha"), _item("beta")], "al", (3, 2), (80, 20), 2)
    assert popup.is_open is True
    assert popup.item_count == 2
    assert popup.prefix == "al"
    selected = popup.selected()
    assert selected is not None
    assert selected.label == "alpha"
    assert _box_origin(popup) == (5, 3)
    assert _box_size(popup)[1] == 4  # items + two border rows


def test_show_flips_above_when_there_is_no_room_below() -> None:
    """A cursor on the last row opens the box above itself, inside the editor."""
    popup = _popup()
    popup.show([_item("alpha")], "al", (78, 19), (80, 20), 2)
    x, y = _box_origin(popup)
    assert (x, y) == (56, 17)
    assert y + _box_size(popup)[1] <= 20


def test_show_pins_the_box_left_in_a_narrow_editor() -> None:
    """A box wider than the editor starts at column zero instead of going off."""
    popup = _popup()
    popup.show([_item("alpha")], "al", (3, 2), (10, 6), 2)
    assert _box_origin(popup)[0] == 0


def test_show_caps_the_visible_rows() -> None:
    """Only MAX_VISIBLE rows are drawn, however many candidates arrive."""
    popup = _popup()
    popup.show([_item(f"item{i}") for i in range(20)], "i", (0, 0), (80, 40), 0)
    assert popup.item_count == 20
    assert _box_size(popup)[1] == completion.MAX_VISIBLE + 2


def test_compute_width_clamps_between_the_minimum_and_maximum() -> None:
    """A tiny candidate list still gets a usable box; a huge one is capped."""
    popup = _popup()
    popup.show([_item("a")], "a", (0, 0), (80, 20), 2)
    assert _box_size(popup)[0] == 24
    popup.show([_item("x" * 200)], "x", (0, 0), (80, 20), 2)
    assert _box_size(popup)[0] == 60


def test_show_without_items_closes_the_popup() -> None:
    """An empty candidate list hides the popup instead of an empty box."""
    popup = _popup()
    popup.show([_item("alpha")], "al", (0, 0), (80, 20), 2)
    popup.show([], "al", (0, 0), (80, 20), 2)
    assert popup.items == []
    assert popup.display is False
    assert popup.is_open is False


def test_close_resets_the_state_and_hides() -> None:
    """Closing forgets the candidates, the prefix and the selection."""
    popup = _popup()
    popup.show([_item("alpha")], "al", (0, 0), (80, 20), 2)
    popup.close()
    assert (popup.items, popup.prefix, popup.index) == ([], "", 0)
    assert popup.display is False


# --- popup selection --------------------------------------------------------


def test_selected_is_none_without_items() -> None:
    """An empty popup has nothing to accept."""
    assert _popup().selected() is None


def test_selection_wraps_in_both_directions() -> None:
    """Up at the top wraps to the last item, down at the bottom to the first."""
    popup = _popup()
    popup.show([_item("a1"), _item("b2"), _item("c3")], "a", (0, 0), (80, 20), 2)
    assert popup.index == 0
    popup.select_prev()
    assert popup.index == 2
    popup.select_next()
    assert popup.index == 0
    popup.select_next()
    assert popup.index == 1


def test_selection_without_items_is_a_noop() -> None:
    """Moving the selection in an empty popup cannot raise."""
    popup = _popup()
    popup.select_next()
    popup.select_prev()
    assert popup.index == 0


# --- popup rendering --------------------------------------------------------


def test_render_line_draws_borders_glyphs_detail_and_the_selection() -> None:
    """Borders frame the box, each row carries its glyph/label/detail."""
    popup = _popup()
    popup.show(
        [_item("alpha", "word", kind=1), _item("beta", "path", kind=17)],
        "a",
        (0, 0),
        (80, 20),
        2,
    )
    width_cells, height_cells = _box_size(popup)
    width = int(width_cells)
    height = int(height_cells)

    assert _text(popup.render_line(0)) == " " * width
    assert _text(popup.render_line(height - 1)) == " " * width

    first = list(popup.render_line(1))
    assert "alpha" in _text(popup.render_line(1))
    assert "word" in _text(popup.render_line(1))
    assert first[1].text == "T"  # kind 1 -> the text glyph
    second = list(popup.render_line(2))
    assert "beta" in _text(popup.render_line(2))
    assert second[1].text == "D"  # kind 17 -> the path glyph

    # the selected row is highlighted differently from the others
    selected_bg = first[0].style
    plain_bg = second[0].style
    assert selected_bg is not None and plain_bg is not None
    assert selected_bg.bgcolor != plain_bg.bgcolor


@pytest.mark.parametrize("kind", [0, 999], ids=["plain-word", "unknown"])
def test_kinds_without_a_glyph_render_blank(kind: int) -> None:
    """Buffer words (kind 0) and unknown kinds render a blank glyph slot."""
    popup = _popup()
    popup.show([_item("gamma", "word", kind=kind)], "g", (0, 0), (80, 20), 2)
    assert popup.render_line(1)[1].text == " "


def test_long_labels_and_details_are_truncated_with_an_ellipsis() -> None:
    """Over-long text is cut to the cell budget instead of overflowing it."""
    popup = _popup()
    popup.show([_item("x" * 200, "d" * 200)], "x", (0, 0), (80, 20), 2)
    text = _text(popup.render_line(1))
    assert "…" in text
    assert len(text) == int(_box_size(popup)[0])


def test_render_line_after_close_is_blank() -> None:
    """A repaint arriving after close renders an empty row."""
    popup = _popup()
    popup.show([_item("alpha", "word")], "a", (0, 0), (80, 20), 2)
    popup.close()
    assert _text(popup.render_line(1)) == " " * int(_box_size(popup)[0])


# --- identifier / word helpers ----------------------------------------------


def test_ident_prefix_takes_the_run_left_of_the_cursor() -> None:
    """The prefix is the identifier characters touching the cursor."""
    ident_prefix = _private("_ident_prefix")
    assert ident_prefix("alpha beta", 5) == ("alpha", 0)
    assert ident_prefix("let x = val", 11) == ("val", 8)
    assert ident_prefix("alpha", 0) == ("", 0)
    assert ident_prefix("alpha.run", 9) == ("run", 6)


def test_ident_prefix_keeps_paths_and_clamps_the_column() -> None:
    """Path separators and ~ stay part of the prefix; a stale column is clamped."""
    ident_prefix = _private("_ident_prefix")
    assert ident_prefix("open src/ma", 11) == ("src/ma", 5)
    assert ident_prefix("~/dir", 5) == ("~/dir", 0)
    assert ident_prefix("abc", 99) == ("abc", 0)


def test_words_from_buffer_skips_the_cursor_row_and_single_letters() -> None:
    """Words are collected as a set, ignoring the typed row and 1-char runs."""
    words = _private("_words_from_buffer")
    buf = TextBuffer("alpha beta\nx gamma\ndelta alpha")
    assert words(buf, 2) == {"alpha", "beta", "gamma"}
    assert words(buf, 0) == {"alpha", "gamma", "delta"}


# --- path completion --------------------------------------------------------


def test_path_completions_lists_matching_entries(tmp_path: Path) -> None:
    """Entries match case-insensitively; directories get a trailing slash."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src.py").write_text("", encoding="utf-8")
    (tmp_path / "sub").mkdir()
    (tmp_path / "other.txt").write_text("", encoding="utf-8")
    assert _private("_path_completions")("s", tmp_path) == ["src/", "src.py", "sub/"]


def test_path_completions_descends_into_a_named_directory(tmp_path: Path) -> None:
    """A prefix naming a directory completes that directory's children."""
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "mod_a.py").write_text("", encoding="utf-8")
    (tmp_path / "pkg" / "mod_b.py").write_text("", encoding="utf-8")
    paths = _private("_path_completions")
    assert paths("pkg/mod", tmp_path) == ["pkg/mod_a.py", "pkg/mod_b.py"]
    assert paths("pkg/", tmp_path) == ["pkg/mod_a.py", "pkg/mod_b.py"]


def test_path_completions_reports_nothing_for_missing_or_file_paths(
    tmp_path: Path,
) -> None:
    """A missing directory, or a file used as one, yields no candidates."""
    (tmp_path / "file.txt").write_text("", encoding="utf-8")
    paths = _private("_path_completions")
    assert paths("nope/x", tmp_path) == []
    assert paths("file.txt/x", tmp_path) == []
    assert paths("file.txt", tmp_path) == ["file.txt"]


def test_path_completions_matches_an_absolute_prefix(tmp_path: Path) -> None:
    """An absolute prefix resolves on its own, without the base directory."""
    (tmp_path / "abs.txt").write_text("", encoding="utf-8")
    assert _private("_path_completions")(str(tmp_path / "ab")) == [
        str(tmp_path / "abs.txt")
    ]


def test_path_completions_survives_an_unreadable_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A directory that refuses to be listed yields no candidates."""

    def _boom(self: Path) -> Any:
        raise OSError("denied")

    monkeypatch.setattr(Path, "iterdir", _boom)
    assert _private("_path_completions")("s", tmp_path) == []


# --- buffer completions -----------------------------------------------------


def test_buffer_completions_offers_words_from_all_open_buffers(
    tmp_path: Path,
) -> None:
    """Words come from every buffer but the row being typed."""
    buf = TextBuffer("alpha = 1\nalpha_beta = 2\n")
    other = TextBuffer("alphabet soup")
    items, prefix, start = completion.buffer_completions(
        buf, row=1, col=3, extra_buffers=[other], base_dir=tmp_path
    )
    assert prefix == "alp"
    assert start == 0
    assert [item.label for item in items] == ["alpha", "alphabet"]
    assert items[0].detail == "word"
    assert items[0].kind == 0
    assert (items[0].range_start_row, items[0].range_start_col) == (1, 0)
    assert items[0].range_end_col == 3


def test_buffer_completions_prefers_paths_for_a_path_prefix(tmp_path: Path) -> None:
    """A prefix containing a separator offers filesystem entries."""
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "mod.py").write_text("", encoding="utf-8")
    buf = TextBuffer("open pkg/mo")
    items, prefix, _start = completion.buffer_completions(
        buf, row=0, col=12, base_dir=tmp_path
    )
    assert prefix == "pkg/mo"
    assert [(item.label, item.detail, item.kind) for item in items] == [
        ("mod.py", "path", 17)
    ]
    assert items[0].insert_text == "pkg/mod.py"


def test_buffer_completions_descends_once_a_separator_is_typed(
    tmp_path: Path,
) -> None:
    """Typing the slash after a directory still lists its children."""
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "mod.py").write_text("", encoding="utf-8")
    buf = TextBuffer("open pkg/")
    items, prefix, _start = completion.buffer_completions(
        buf, row=0, col=9, base_dir=tmp_path
    )
    assert prefix == "pkg/"
    assert [item.insert_text for item in items] == ["pkg/mod.py"]


def test_buffer_completions_drops_the_typed_file_but_offers_the_directory(
    tmp_path: Path,
) -> None:
    """A file identical to the prefix is dropped; a directory gets a slash."""
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "mod").write_text("", encoding="utf-8")
    buf = TextBuffer("open pkg/mod")
    items, prefix, _start = completion.buffer_completions(
        buf, row=0, col=12, base_dir=tmp_path
    )
    assert prefix == "pkg/mod"
    assert items == []

    (tmp_path / "pkg" / "mod").unlink()
    (tmp_path / "pkg" / "mod").mkdir()
    items, _prefix, _start = completion.buffer_completions(
        buf, row=0, col=12, base_dir=tmp_path
    )
    assert [item.insert_text for item in items] == ["pkg/mod/"]


def test_buffer_completions_is_empty_without_a_prefix(tmp_path: Path) -> None:
    """A cursor in whitespace has nothing to complete."""
    items, prefix, start = completion.buffer_completions(
        TextBuffer("alpha beta"), 0, 6, base_dir=tmp_path
    )
    assert (items, prefix, start) == ([], "", 6)


def test_buffer_completions_treats_a_stale_row_as_empty() -> None:
    """A row past the end of the buffer is an empty line, not an error."""
    items, prefix, _start = completion.buffer_completions(TextBuffer("alpha"), 7, 2)
    assert (items, prefix) == ([], "")


def test_buffer_completions_trims_to_sixty_four_items() -> None:
    """A chatty buffer cannot flood the popup."""
    words = " ".join(f"word{i:03d}" for i in range(80))
    items, prefix, _start = completion.buffer_completions(
        TextBuffer(f"{words}\nwor"), 1, 3
    )
    assert prefix == "wor"
    assert len(items) == 64


# --- controller dismissal (S30) ---------------------------------------------


async def _wait_until(
    pilot: Any, predicate: Callable[[], bool], timeout: float = 5.0
) -> bool:
    """Pause until *predicate* holds; its final value on timeout."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        await pilot.pause(0.05)
        if predicate():
            return True
    return predicate()


def _typed_doc_app(tmp_path: Path) -> YateApp:
    """An app over a document whose tail line holds the half-typed ``al``."""
    doc = tmp_path / "note.txt"
    doc.write_text("alpha bravo charlie\nalpha delta\n", encoding="utf-8")
    return YateApp(target=doc)


def test_escape_dismissal_survives_a_pending_debounce(tmp_path: Path) -> None:
    """Esc closes the popup; the debounce scheduled before it stays silent.

    The popup's Esc binding closes the widget directly (editor.py), so the
    controller only sees the dismissal as an ``is_open`` flip between
    ``schedule`` and the debounce firing.
    """

    async def scenario() -> None:
        app = _typed_doc_app(tmp_path)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            popup = app.editor.completion_popup
            assert popup is not None
            controller = app.editor.completion
            app.editor.session.buffer.move_doc_end()
            app.editor.session.buffer.insert_text("\nal")
            app.editor.refresh_ui()
            await pilot.press("ctrl+space")
            assert await _wait_until(pilot, lambda: popup.is_open)

            # schedule the guarded re-query, then close the widget the way
            # the popup's Esc binding does -- both in one loop tick, so the
            # 0.12s debounce cannot fire in between
            controller.after_editor_key("p")
            popup.close()
            resurrected = await _wait_until(
                pilot, lambda: popup.is_open, timeout=0.5
            )
            assert not resurrected

            # typing again is active input: the popup re-opens
            controller.after_editor_key("p")
            assert await _wait_until(pilot, lambda: popup.is_open)

    asyncio.run(scenario())


def test_escape_dismissal_survives_the_in_flight_worker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A query already in flight when the popup closes must not re-show it."""

    async def scenario() -> None:
        app = _typed_doc_app(tmp_path)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            popup = app.editor.completion_popup
            assert popup is not None
            controller = app.editor.completion
            app.editor.session.buffer.move_doc_end()
            app.editor.session.buffer.insert_text("\nal")
            app.editor.refresh_ui()
            await pilot.press("ctrl+space")
            assert await _wait_until(pilot, lambda: popup.is_open)

            # hold the next query mid-flight so the close lands first
            gate = asyncio.Event()

            async def _gated(*_args: Any, **_kwargs: Any) -> list[Completion]:
                await gate.wait()
                return [
                    Completion(label="alpha", insert_text="alpha", kind=1)
                ]

            async def _shown(_doc: Document) -> None:
                return None

            def _supports(_doc: Document) -> bool:
                return True

            def _triggers(_doc: Document) -> list[str]:
                return []

            monkeypatch.setattr(controller.lsp, "supports", _supports)
            monkeypatch.setattr(
                controller.lsp, "on_document_shown", _shown
            )
            monkeypatch.setattr(
                controller.lsp, "trigger_characters_for", _triggers
            )
            monkeypatch.setattr(
                controller.lsp, "request_completion", _gated
            )

            await pilot.press("ctrl+space")  # worker starts, parks on the gate
            await pilot.pause()
            popup.close()  # the popup's Esc binding, mid-flight
            gate.set()
            await pilot.pause()
            resurrected = await _wait_until(
                pilot, lambda: popup.is_open, timeout=0.3
            )
            assert not resurrected

    asyncio.run(scenario())


def test_escape_then_ctrl_space_restores_the_popup(tmp_path: Path) -> None:
    """Esc keeps the popup closed through the debounce; Ctrl+Space re-opens."""

    async def scenario() -> None:
        app = _typed_doc_app(tmp_path)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            popup = app.editor.completion_popup
            assert popup is not None
            app.editor.session.buffer.move_doc_end()
            app.editor.session.buffer.insert_text("\nal")
            app.editor.refresh_ui()
            await pilot.press("ctrl+space")
            assert await _wait_until(pilot, lambda: popup.is_open)

            await pilot.press("p")  # schedules the guarded re-query
            await pilot.press("escape")  # closes the widget directly
            await pilot.pause()
            assert not popup.is_open
            resurrected = await _wait_until(
                pilot, lambda: popup.is_open, timeout=0.5
            )
            assert not resurrected

            await pilot.press("ctrl+space")
            assert await _wait_until(pilot, lambda: popup.is_open)

    asyncio.run(scenario())
