"""Headless tests for editor_core and the key map dispatch logic.

Run with:  python -m pytest tests -v
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, cast

from yate.editor_core import Document, SearchEngine, TextBuffer
from yate.keymaps.base import ActionContext, parse_key
from yate.keymaps.vsc import VscKeymap
from yate.keymaps.vim import VimKeymap, VimMode


# --- TextBuffer -------------------------------------------------------------


def test_insert_and_movement() -> None:
    buf = TextBuffer("hello\nworld")
    assert buf.lines == ["hello", "world"]
    buf.move_doc_end()
    assert buf.cursor == (1, 5)
    buf.move_line_start()
    assert buf.cursor == (1, 0)


def test_insert_text_multiline() -> None:
    buf = TextBuffer("ab")
    buf.move_right()
    buf.insert_text("X\nY")
    assert buf.get_text() == "aX\nYb"
    assert buf.cursor == (1, 1)


def test_backspace_joins_lines() -> None:
    buf = TextBuffer("ab\ncd")
    buf.cursor = (1, 0)
    buf.delete_backward()
    assert buf.get_text() == "abcd"


def test_undo_redo() -> None:
    buf = TextBuffer("hello")
    buf.move_doc_end()
    buf.insert_text(" world")
    assert buf.get_text() == "hello world"
    buf.undo()
    assert buf.get_text() == "hello"
    buf.redo()
    assert buf.get_text() == "hello world"


def test_typed_chars_coalesce_in_one_undo_step() -> None:
    buf = TextBuffer("")
    for ch in "abc":
        buf.insert_text(ch)
    assert buf.get_text() == "abc"
    buf.undo()
    assert buf.get_text() == ""


def test_content_version_tracks_text_only() -> None:
    buf = TextBuffer("def foo():\n    pass\n")
    assert buf.content_version == 0
    # cursor movement and selection changes do not bump the version
    buf.move_down()
    buf.set_cursor((0, 0), select=True)
    buf.clear_selection()
    assert buf.content_version == 0
    # every real text mutation bumps it
    buf.insert_text("x")
    assert buf.content_version == 1
    buf.undo()
    assert buf.content_version == 2
    buf.redo()
    assert buf.content_version == 3
    buf.set_text("fresh")
    assert buf.content_version == 4


def test_word_motions() -> None:
    buf = TextBuffer("foo bar  baz")
    buf.move_right(word=True)
    assert buf.col == 4
    buf.move_right(word=True)
    assert buf.col == 9  # "baz" starts after the double space
    buf.move_left(word=True)
    assert buf.col == 4


def test_selection_and_cut() -> None:
    buf = TextBuffer("hello world")
    buf.anchor = (0, 0)
    buf.cursor = (0, 5)
    assert buf.selected_text() == "hello"
    text = buf.delete_selection()
    assert text == "hello"
    assert buf.get_text() == " world"


def test_duplicate_and_move_line() -> None:
    buf = TextBuffer("a\nb")
    buf.cursor = (0, 0)
    buf.duplicate_line()
    assert buf.lines == ["a", "a", "b"]
    buf.move_line(1)
    assert buf.lines == ["a", "b", "a"]


def test_delete_lines_yanks() -> None:
    buf = TextBuffer("a\nb\nc")
    buf.cursor = (1, 0)
    buf.delete_lines()
    assert buf.lines == ["a", "c"]
    assert buf.register == "b\n"
    buf.paste()
    assert "b" in buf.lines


def test_join_lines() -> None:
    buf = TextBuffer("foo\nbar")
    buf.cursor = (0, 0)
    buf.join_lines()
    assert buf.get_text() == "foo bar"


def test_indent_outdent() -> None:
    buf = TextBuffer("a\nb", tab_width=4)
    buf.select_all()
    buf.indent_selection()
    assert all(line.startswith("    ") for line in buf.lines)
    buf.outdent_selection()
    assert buf.get_text() == "a\nb"


def test_outdent_keeps_cursor_inside_the_line() -> None:
    """shift+tab shortens the line: the cursor must follow, not dangle."""
    buf = TextBuffer("    a", tab_width=4)
    buf.cursor = (0, 4)
    buf.outdent_selection()
    assert buf.get_text() == "a"
    assert buf.cursor == (0, 1)


# --- SearchEngine -----------------------------------------------------------


def test_find_all_matches() -> None:
    buf = TextBuffer("cat bat cat")
    engine = SearchEngine()
    matches = engine.update("cat", buf)
    assert len(matches) == 2


def test_next_wraps_around() -> None:
    buf = TextBuffer("cat\ncat")
    engine = SearchEngine()
    engine.update("cat", buf)
    m1 = engine.next(buf, forward=True)
    assert m1 is not None
    assert m1.row == 0
    m2 = engine.next(buf, forward=True)
    assert m2 is not None
    assert m2.row == 1
    m3 = engine.next(buf, forward=True)
    assert m3 is not None
    assert m3.row == 0


def test_replace_all() -> None:
    buf = TextBuffer("cat dog cat")
    engine = SearchEngine()
    engine.update("cat", buf)
    count = engine.replace_all(buf, "fox")
    assert count == 2
    assert buf.get_text() == "fox dog fox"


def test_regex_search() -> None:
    buf = TextBuffer("a1 b2 c3")
    engine = SearchEngine()
    engine.use_regex = True
    matches = engine.update(r"[a-z]\d", buf)
    assert len(matches) == 3


# --- Document ---------------------------------------------------------------


def test_save_and_reopen(tmp_path: Path) -> None:
    path = tmp_path / "note.txt"
    doc = Document(path, TextBuffer("line1\nline2"))
    doc.save()
    reopened = Document.open(path)
    assert reopened.buffer.get_text() == "line1\nline2"
    assert not reopened.modified
    reopened.buffer.insert_text("x")
    assert reopened.modified


def test_filetype_detection() -> None:
    doc = Document(Path("foo.py"))
    assert doc.filetype == "py"


def test_filetype_override_wins_over_path_suffix() -> None:
    doc = Document(Path("foo.txt"))
    assert doc.filetype == "txt"
    doc.filetype_override = "py"
    assert doc.filetype == "py"
    doc.filetype_override = None
    assert doc.filetype == "txt"


def test_filetype_override_for_unnamed_buffer() -> None:
    doc = Document(None)
    assert doc.filetype == "plaintext"
    doc.filetype_override = "json"
    assert doc.filetype == "json"


def test_open_async_matches_sync_open(tmp_path: Path) -> None:
    async def scenario() -> None:
        path = tmp_path / "note.txt"
        path.write_text("alpha\nbeta\r\n", encoding="utf-8")
        doc = await Document.open_async(path)
        sync_doc = Document.open(path)
        # same content (CRLF normalized), encoding and saved state
        assert doc.buffer.get_text() == sync_doc.buffer.get_text()
        assert doc.encoding == sync_doc.encoding
        assert not doc.modified

    asyncio.run(scenario())


# --- key notation -----------------------------------------------------------


def test_parse_special_keys() -> None:
    assert parse_key("<ctrl-s>") == "\x13"
    assert parse_key("<esc>") == "\x1b"
    assert parse_key("<f1>") == "\x1bOP"
    assert parse_key("a") == "a"
    assert parse_key("<alt-x>") == "\x1bx"
    assert parse_key("<ctrl-]>") == "\x1d"


class _FakeApp:
    """Minimal app stand-in for keymap dispatch tests."""

    def __init__(self) -> None:
        from yate.actions import ActionRegistry, SessionOps, populate

        self.actions = ActionRegistry()
        populate(self.actions, cast(SessionOps, self))
        self.doc: Document = Document(None, TextBuffer(""))
        self.messages: list[str | tuple[str, bool]] = []

    @property
    def buffer(self) -> TextBuffer:
        return self.doc.buffer

    def execute_action(self, name: str) -> None:
        self.actions.execute(name, ActionContext(cast(Any, self)))

    def insert_char(self, ch: str) -> None:
        self.buffer.insert_text(ch)

    def message(self, text: str) -> None:
        self.messages.append(text)

    # vim-keymap-only hooks (not used by normal mode tests)
    def command_prompt(self) -> None:
        self.messages.append("command_prompt")

    def find_prompt(self, forward: bool) -> None:
        self.messages.append(("find", forward))

    def page(self, direction: int, half: bool = False) -> None:
        # ``half`` mirrors YateApp.page's signature (actions call it with the
        # ``half=`` keyword); the stand-in only dispatches full-page actions.
        self.execute_action("page_down" if direction > 0 else "page_up")


# --- vsc keymap -------------------------------------------------------------


def test_typing_and_enter() -> None:
    app = _FakeApp()
    km = VscKeymap()
    ctx = ActionContext(cast(Any, app))
    for ch in "hi":
        km.handle_key(ctx, ch)
    km.handle_key(ctx, "\r")
    km.handle_key(ctx, "x")
    assert app.buffer.get_text() == "hi\nx"


def test_colon_is_inserted_literally() -> None:
    # In vsc mode ":" is ordinary text, not the (vim-only) ex prompt.
    app = _FakeApp()
    km = VscKeymap()
    ctx = ActionContext(cast(Any, app))
    assert km.handle_key(ctx, ":")
    for ch in "wq":
        km.handle_key(ctx, ch)
    assert app.buffer.get_text() == ":wq"
    assert "command_prompt" not in app.messages


def test_ctrl_a_selects_all() -> None:
    app = _FakeApp()
    app.doc = Document(None, TextBuffer("hello\nworld"))
    km = VscKeymap()
    km.handle_key(ActionContext(cast(Any, app)), parse_key("<ctrl-a>"))
    assert app.buffer.has_selection()


# --- vim keymap -------------------------------------------------------------


def test_insert_and_escape() -> None:
    app = _FakeApp()
    km = VimKeymap()
    ctx = ActionContext(cast(Any, app))
    km.handle_key(ctx, "i")
    assert km.mode is VimMode.INSERT
    for ch in "abc":
        km.handle_key(ctx, ch)
    km.handle_key(ctx, "\x1b")
    assert km.mode is VimMode.NORMAL
    assert app.buffer.get_text() == "abc"


def test_dd_deletes_line() -> None:
    app = _FakeApp()
    app.doc = Document(None, TextBuffer("one\ntwo\nthree"))
    km = VimKeymap()
    ctx = ActionContext(cast(Any, app))
    km.handle_key(ctx, "d")
    km.handle_key(ctx, "d")
    assert "one" not in app.buffer.lines
    assert app.buffer.register == "one\n"


def test_yy_pastes_line() -> None:
    app = _FakeApp()
    app.doc = Document(None, TextBuffer("one"))
    km = VimKeymap()
    ctx = ActionContext(cast(Any, app))
    km.handle_key(ctx, "y")
    km.handle_key(ctx, "y")
    km.handle_key(ctx, "p")
    assert app.buffer.line_count == 2


def test_word_motion() -> None:
    app = _FakeApp()
    app.doc = Document(None, TextBuffer("foo bar"))
    km = VimKeymap()
    ctx = ActionContext(cast(Any, app))
    km.handle_key(ctx, "w")
    assert app.buffer.col == 4


def test_visual_selection_delete() -> None:
    app = _FakeApp()
    app.doc = Document(None, TextBuffer("hello"))
    km = VimKeymap()
    ctx = ActionContext(cast(Any, app))
    km.handle_key(ctx, "v")
    km.handle_key(ctx, "l")
    km.handle_key(ctx, "l")
    assert app.buffer.has_selection()
    km.handle_key(ctx, "x")
    assert app.buffer.get_text() == "llo"
    assert km.mode is VimMode.NORMAL
