"""Headless tests for editor_core and the key map dispatch logic.

Run with:  python -m pytest tests -v
"""

from __future__ import annotations

import asyncio
import os
import stat
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import pytest

from yate.config import YateConfig
from yate.editor_core import Document, SearchEngine, TextBuffer
from yate.editor_core.buffer import (
    MAX_UNDO_STEPS,
    next_word_start,
    prev_word_start,
    word_end,
)
from yate.editor_core.search import Match
from yate.keymaps.base import ActionContext, KeyUi, parse_key
from yate.keymaps.vsc import VscKeymap
from yate.keymaps.vim import VimKeymap, VimMode
from yate.session import EditorSession


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


def test_vertical_movement_keeps_desired_column() -> None:
    buf = TextBuffer("long line here\nabc\nanother long line")
    buf.set_cursor((0, 10))
    buf.move_down()  # short line clamps the cursor to its end
    assert buf.cursor == (1, 3)
    buf.move_down()  # the goal column survives the short line
    assert buf.cursor == (2, 10)


def test_vertical_movement_goal_resets_on_horizontal_move() -> None:
    buf = TextBuffer("long line here\nabc\nanother long line")
    buf.set_cursor((0, 10))
    buf.move_down()  # (1, 3), goal col 10
    buf.move_left()  # explicit horizontal move ends tracking
    buf.move_down()
    assert buf.cursor == (2, 2)


def test_vertical_movement_goal_resets_on_edit() -> None:
    buf = TextBuffer("long line here\nabc\nanother long line")
    buf.set_cursor((0, 10))
    buf.move_down()  # (1, 3), goal col 10
    buf.insert_text("xy")  # edit ends tracking
    assert buf.cursor == (1, 5)
    buf.move_down()
    assert buf.cursor == (2, 5)


def test_vertical_movement_goal_with_selection() -> None:
    buf = TextBuffer("long line here\nabc\nanother long line")
    buf.set_cursor((0, 10))
    buf.move_down(select=True)
    buf.move_down(select=True)
    assert buf.cursor == (2, 10)
    assert buf.selection() == ((0, 10), (2, 10))


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


def test_save_is_atomic_and_leaves_no_temp_file(tmp_path: Path) -> None:
    path = tmp_path / "note.txt"
    doc = Document(path, TextBuffer("line1\nline2"))
    doc.save()
    assert path.read_text(encoding="utf-8") == "line1\nline2"
    assert list(tmp_path.iterdir()) == [path], "temp file must be gone after save"
    doc.buffer.insert_text("!")
    doc.save()
    assert path.read_text(encoding="utf-8") == "!line1\nline2"
    assert list(tmp_path.iterdir()) == [path]


def test_save_creates_a_missing_path_without_leaving_a_temp_file(
    tmp_path: Path,
) -> None:
    """Saving a brand new path works and never leaves a sibling temp file."""
    path = tmp_path / "fresh.txt"
    assert not path.exists()

    doc = Document(path, TextBuffer("fresh content"))
    doc.save()

    assert path.read_text(encoding="utf-8") == "fresh content"
    assert list(tmp_path.glob("*.yate-tmp-*")) == []
    assert list(tmp_path.iterdir()) == [path]


@pytest.mark.skipif(os.name != "posix", reason="POSIX permission bits only")
def test_save_preserves_the_existing_permission_bits(tmp_path: Path) -> None:
    """``os.replace`` swaps the inode, so the target's mode (e.g. 0600 from a
    secret or private file) must be copied onto the temp file before the swap
    instead of falling back to the process umask."""
    path = tmp_path / "private.txt"
    path.write_text("old", encoding="utf-8")
    path.chmod(0o600)

    doc = Document.open(path)
    doc.buffer.set_text("new")
    doc.save()

    assert path.read_text(encoding="utf-8") == "new"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert list(tmp_path.glob("*.yate-tmp-*")) == []


def test_save_resets_the_timestamp_and_keeps_permission_bits(
    tmp_path: Path,
) -> None:
    """A save must look freshly written even though ``copystat`` carries the
    target's mode/xattrs onto the temp file: the inherited atime/mtime are put
    back to now, so build tools and file watchers notice the change."""
    path = tmp_path / "note.txt"
    path.write_text("before", encoding="utf-8")
    if os.name == "posix":
        path.chmod(0o600)
    old = time.time() - 3600.0
    os.utime(path, (old, old))
    assert abs(path.stat().st_mtime - old) < 1.0, "mtime must start stale"

    doc = Document.open(path)
    doc.buffer.set_text("after")
    doc.save()

    assert path.read_text(encoding="utf-8") == "after"
    assert abs(time.time() - path.stat().st_mtime) < 5.0
    if os.name == "posix":
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert list(tmp_path.glob("*.yate-tmp-*")) == []


def test_failed_save_keeps_previous_contents(tmp_path: Path) -> None:
    path = tmp_path / "note.txt"
    doc = Document(path, TextBuffer("original"), encoding="ascii")
    doc.save()
    doc.buffer.set_text("emoji 😀")
    # ascii cannot encode the emoji: the save must fail without destroying
    # the on-disk file or leaving a .yate-tmp sibling behind
    try:
        doc.save()
        raised = False
    except UnicodeEncodeError:
        raised = True
    assert raised
    assert path.read_text(encoding="utf-8") == "original"
    assert list(tmp_path.iterdir()) == [path]


def test_modified_tracks_undo_back_to_saved_state(tmp_path: Path) -> None:
    path = tmp_path / "note.txt"
    doc = Document(path, TextBuffer("hello"))
    assert not doc.modified
    doc.buffer.move_doc_end()
    doc.buffer.insert_text(" world")
    doc.save()
    assert not doc.modified
    # a discrete (non-coalesced) edit undoes exactly back to the saved text
    doc.buffer.insert_text("x", kind="step")
    assert doc.modified
    assert doc.buffer.undo()
    assert doc.buffer.get_text() == "hello world"
    assert not doc.modified
    # undoing further crosses the save point: content differs -> dirty
    assert doc.buffer.undo()
    assert doc.buffer.get_text() == "hello"
    assert doc.modified
    assert doc.buffer.redo()
    assert not doc.modified


def test_modified_when_save_lands_inside_coalesced_step(tmp_path: Path) -> None:
    """Saving mid-step makes the counter miss the save point (one undo rewinds
    the whole step); the exact line comparison must still decide correctly."""
    path = tmp_path / "note.txt"
    doc = Document(path, TextBuffer("hello"))
    doc.buffer.move_doc_end()
    doc.buffer.insert_text(" world")
    doc.save()
    doc.buffer.insert_text("!")  # coalesces onto the pre-save step
    assert doc.modified
    assert doc.buffer.undo()  # rewinds past the save point to "hello"
    assert doc.buffer.get_text() == "hello"
    assert doc.modified  # "hello" != saved "hello world"


def test_modified_memo_stays_correct_across_save_and_undo(tmp_path: Path) -> None:
    """The dirty verdict is memoized on the buffer's edit counter; saving
    moves the baseline and undo rewinds the counter, so neither may serve
    a verdict cached for a different buffer state."""
    path = tmp_path / "note.txt"
    doc = Document(path, TextBuffer("hello"))
    doc.buffer.move_doc_end()
    assert not doc.modified
    doc.buffer.insert_text("x")
    assert doc.modified
    doc.save()  # the baseline moves: the memo must be dropped
    assert not doc.modified  # a stale memo from before the save would fail
    assert doc.buffer.undo()  # rewinds the counter past the save point
    assert doc.modified  # exact comparison: "hello" != saved "hellox"
    assert doc.buffer.redo()
    assert not doc.modified


def test_modified_with_coalesced_typing_since_creation(tmp_path: Path) -> None:
    """Mirror of the undo_redo smoke scenario: type fast (coalesced into one
    undo step), undo, redo -- the dirty flag must follow the saved state."""
    doc = Document(Path("note.txt"), TextBuffer(""))
    for ch in "hello":
        doc.buffer.insert_text(ch)
    assert doc.modified
    assert doc.buffer.undo()
    assert doc.buffer.get_text() == ""
    assert not doc.modified
    assert doc.buffer.redo()
    assert doc.buffer.get_text() == "hello"
    assert doc.modified


def test_cursor_only_edits_do_not_mark_document_modified(tmp_path: Path) -> None:
    path = tmp_path / "note.txt"
    doc = Document(path, TextBuffer("hello"))
    doc.save()
    doc.buffer.move_doc_end()
    doc.buffer.move_line_start()
    assert not doc.modified


def test_undo_stack_is_capped() -> None:
    buf = TextBuffer("")
    for _ in range(MAX_UNDO_STEPS + 50):
        buf.insert_text("x", kind="step")
    undos = 0
    while buf.undo():
        undos += 1
    # exactly the cap is kept: the 50 oldest steps are dropped, so undoing
    # can only rewind to the 50th insertion
    assert undos == MAX_UNDO_STEPS
    assert buf.get_text() == "x" * 50


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
    """Minimal editor stand-in for keymap dispatch tests.

    The keymap layer only needs the document session plus the :class:`KeyUi`
    callbacks, so the stand-in owns a real :class:`EditorSession` and wires a
    :class:`KeyUi` record back to its own dispatch hooks.

    Hooks that are not implemented explicitly fall back to :meth:`__getattr__`,
    which returns a call-recording no-op: a newly added action defaults to a
    harmless no-op instead of raising AttributeError, and tests can still
    assert the call via :attr:`messages`.
    """

    def __init__(self) -> None:
        from yate.actions import populate
        from yate.registries import ActionRegistry

        self.session = EditorSession(YateConfig())
        self.session.new_buffer()
        self.actions = ActionRegistry()
        self.messages: list[str | tuple[str, bool]] = []
        self.ui = KeyUi(
            execute_action=self.execute_action,
            message=self.message,
            command_prompt=self.command_prompt,
            find_prompt=self.find_prompt,
            goto_prompt=self.goto_prompt,
            toggle_keymap=self.toggle_keymap,
        )
        populate(self.actions, cast(Any, self))

    @property
    def doc(self) -> Document:
        return self.session.doc

    @doc.setter
    def doc(self, doc: Document) -> None:
        self.session.docs[self.session.index] = doc

    @property
    def buffer(self) -> TextBuffer:
        return self.session.buffer

    def execute_action(self, name: str) -> bool:
        return self.actions.execute(name, ActionContext(self.session, self.ui))

    def insert_char(self, ch: str) -> None:
        self.buffer.insert_text(ch)

    def message(self, text: str) -> None:
        self.messages.append(text)

    # vim-keymap-only hooks (not used by normal mode tests)
    def command_prompt(self) -> None:
        self.messages.append("command_prompt")

    def find_prompt(self, forward: bool) -> None:
        self.messages.append(("find", forward))

    def goto_prompt(self) -> None:
        self.messages.append("goto_prompt")

    def toggle_keymap(self) -> None:
        self.messages.append("toggle_keymap")

    def page(self, direction: int, half: bool = False) -> None:
        # ``half`` mirrors Editor.page's signature (actions call it with the
        # ``half=`` keyword); the stand-in only dispatches full-page actions.
        self.execute_action("page_down" if direction > 0 else "page_up")

    def __getattr__(self, name: str) -> Callable[..., None]:
        """Return a call-recording no-op for any unimplemented hook.

        Newly added actions default to a no-op (recorded in ``messages``)
        instead of raising AttributeError.  Private/dunder lookups and a
        not-yet-initialized ``messages`` are real errors, not hooks.
        """
        if name.startswith("_") or name == "messages":
            raise AttributeError(
                f"{type(self).__name__!r} object has no attribute {name!r}"
            )

        # *args/**kwargs: dynamic dispatch -- hooks have varied signatures.
        def record(*args: Any, **kwargs: Any) -> None:
            self.messages.append(name)

        return record


# --- _FakeApp fallback hook -------------------------------------------------


def test_fake_app_unimplemented_hooks_become_recorded_noops() -> None:
    """A hook the stand-in does not implement resolves to a call-recording
    no-op: a newly added action cannot break these tests with
    AttributeError, and tests can still assert the call via ``messages``."""
    app = _FakeApp()
    assert app.some_future_hook() is None
    assert "some_future_hook" in app.messages
    with pytest.raises(AttributeError):
        getattr(app, "_private")


# --- vsc keymap -------------------------------------------------------------


def test_typing_and_enter() -> None:
    app = _FakeApp()
    km = VscKeymap()
    ctx = ActionContext(app.session, app.ui)
    for ch in "hi":
        km.handle_key(ctx, ch)
    km.handle_key(ctx, "\r")
    km.handle_key(ctx, "x")
    assert app.buffer.get_text() == "hi\nx"


def test_colon_is_inserted_literally() -> None:
    # In vsc mode ":" is ordinary text, not the (vim-only) ex prompt.
    app = _FakeApp()
    km = VscKeymap()
    ctx = ActionContext(app.session, app.ui)
    assert km.handle_key(ctx, ":")
    for ch in "wq":
        km.handle_key(ctx, ch)
    assert app.buffer.get_text() == ":wq"
    assert "command_prompt" not in app.messages


def test_ctrl_a_selects_all() -> None:
    app = _FakeApp()
    app.doc = Document(None, TextBuffer("hello\nworld"))
    km = VscKeymap()
    km.handle_key(ActionContext(app.session, app.ui), parse_key("<ctrl-a>"))
    assert app.buffer.has_selection()


# --- vim keymap -------------------------------------------------------------


def test_insert_and_escape() -> None:
    app = _FakeApp()
    km = VimKeymap()
    ctx = ActionContext(app.session, app.ui)
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
    ctx = ActionContext(app.session, app.ui)
    km.handle_key(ctx, "d")
    km.handle_key(ctx, "d")
    assert "one" not in app.buffer.lines
    assert app.buffer.register == "one\n"


def test_yy_pastes_line() -> None:
    app = _FakeApp()
    app.doc = Document(None, TextBuffer("one"))
    km = VimKeymap()
    ctx = ActionContext(app.session, app.ui)
    km.handle_key(ctx, "y")
    km.handle_key(ctx, "y")
    km.handle_key(ctx, "p")
    assert app.buffer.line_count == 2


def test_word_motion() -> None:
    app = _FakeApp()
    app.doc = Document(None, TextBuffer("foo bar"))
    km = VimKeymap()
    ctx = ActionContext(app.session, app.ui)
    km.handle_key(ctx, "w")
    assert app.buffer.col == 4


def test_visual_selection_delete() -> None:
    app = _FakeApp()
    app.doc = Document(None, TextBuffer("hello"))
    km = VimKeymap()
    ctx = ActionContext(app.session, app.ui)
    km.handle_key(ctx, "v")
    km.handle_key(ctx, "l")
    km.handle_key(ctx, "l")
    assert app.buffer.has_selection()
    km.handle_key(ctx, "x")
    assert app.buffer.get_text() == "llo"
    assert km.mode is VimMode.NORMAL


# --- word-motion helpers ----------------------------------------------------


def test_next_word_start_skips_a_punctuation_run() -> None:
    """A punctuation run before a word: the next start is the word itself."""
    assert next_word_start("!!alpha", 0) == 2


def test_prev_word_start_walks_back_over_punctuation() -> None:
    """Stepping back from the end takes the punctuation run with the word."""
    assert prev_word_start("ab!!", 4) == 2


def test_word_end_from_blanks_and_from_punctuation() -> None:
    """word_end skips leading blanks, then ends the word / punctuation run."""
    assert word_end("   ab", 0) == 5
    assert word_end("ab!!", 2) == 4


# --- TextBuffer: state bookkeeping -----------------------------------------


def test_line_clamps_the_row() -> None:
    """line() clamps an out-of-range row instead of raising."""
    buf = TextBuffer("a\nb\nc")
    assert buf.line(-5) == "a"
    assert buf.line(99) == "c"


def test_mark_content_changed_restarts_vertical_tracking() -> None:
    """Out-of-band mutations bump the version and clear the goal column."""
    buf = TextBuffer("long\na")
    buf.cursor = (0, 4)
    buf.move_down()  # goal column 4, clamped to the short line
    assert buf.cursor == (1, 1)
    version, edits = buf.content_version, buf.content_edits
    buf.lines[0] = "x"
    buf.mark_content_changed()
    assert buf.content_version == version + 1
    assert buf.content_edits == edits + 1
    buf.move_up()  # tracking restarted, so the goal is the current column
    assert buf.cursor == (0, 1)


def test_commit_without_changes_records_no_history() -> None:
    """A snapshot/commit pair around a no-op edit keeps the stack empty."""
    buf = TextBuffer("abc")
    buf.commit(buf.snapshot())
    assert buf.undo() is False


def test_redo_without_history_returns_false() -> None:
    """redo() on a fresh buffer reports that there is nothing to redo."""
    assert TextBuffer("x").redo() is False


# --- TextBuffer: selection and edits ---------------------------------------


def test_selected_text_spans_multiple_lines() -> None:
    """A cross-line selection joins the head, the middle lines and the tail."""
    buf = TextBuffer("alpha\nbeta\ngamma")
    buf.anchor = (0, 2)
    buf.cursor = (2, 3)
    assert buf.selected_text() == "pha\nbeta\ngam"
    assert buf.selected_rows() == (0, 2)


def test_delete_selection_across_lines_merges_head_and_tail() -> None:
    """Deleting a cross-line selection joins what surrounds it."""
    buf = TextBuffer("alpha\nbeta\ngamma")
    buf.anchor = (0, 2)
    buf.cursor = (2, 3)
    assert buf.delete_selection() == "pha\nbeta\ngam"
    assert buf.get_text() == "alma"
    assert buf.cursor == (0, 2)


def test_insert_text_empty_string_is_a_noop() -> None:
    """Inserting the empty string changes nothing and records no history."""
    buf = TextBuffer("abc")
    buf.insert_text("")
    assert buf.get_text() == "abc"
    assert buf.undo() is False


def test_insert_text_replaces_the_selection() -> None:
    """Typing over a selection deletes it first, in one undo step."""
    buf = TextBuffer("hello world")
    buf.anchor = (0, 0)
    buf.cursor = (0, 5)
    buf.insert_text("bye")
    assert buf.get_text() == "bye world"
    assert buf.anchor is None
    buf.undo()
    assert buf.get_text() == "hello world"


def test_delete_selection_without_selection_returns_none() -> None:
    """delete_selection() with nothing selected reports nothing deleted."""
    assert TextBuffer("abc").delete_selection() is None


# --- TextBuffer: tabs, backspace, forward delete ---------------------------


def test_insert_tab_expands_to_the_next_tab_stop() -> None:
    """Soft tabs fill up to the next tab stop; hard tabs insert a real tab."""
    buf = TextBuffer("ab")
    buf.move_doc_end()
    buf.insert_tab()
    assert buf.get_text() == "ab  "

    hard = TextBuffer("ab", use_spaces=False)
    hard.move_doc_end()
    hard.insert_tab()
    assert hard.get_text() == "ab\t"


def test_insert_tab_indents_a_multi_line_selection() -> None:
    """Tab with a multi-line selection indents the selected rows."""
    buf = TextBuffer("a\nb")
    buf.anchor = (0, 0)
    buf.cursor = (1, 1)
    buf.insert_tab()
    assert buf.get_text() == "    a\n    b"


def test_delete_backward_with_selection_deletes_it() -> None:
    """Backspace with a selection removes the selection, not one character."""
    buf = TextBuffer("hello")
    buf.anchor = (0, 1)
    buf.cursor = (0, 4)
    buf.delete_backward()
    assert buf.get_text() == "ho"


def test_delete_backward_inside_a_line_and_by_word() -> None:
    """Backspace mid-line removes one character, or the previous word."""
    char = TextBuffer("hello world")
    char.cursor = (0, 5)
    char.delete_backward()
    assert char.get_text() == "hell world"

    word = TextBuffer("hello world")
    word.cursor = (0, 11)
    word.delete_backward(word=True)
    assert word.get_text() == "hello "


def test_delete_forward_with_selection_joins_and_cuts() -> None:
    """Forward delete handles a selection, a line join and a mid-line cut."""
    sel = TextBuffer("hello")
    sel.anchor = (0, 1)
    sel.cursor = (0, 4)
    sel.delete_forward()
    assert sel.get_text() == "ho"

    joined = TextBuffer("ab\ncd")
    joined.cursor = (0, 2)
    joined.delete_forward()
    assert joined.get_text() == "abcd"
    assert joined.cursor == (0, 2)

    mid = TextBuffer("hello world")
    mid.cursor = (0, 5)
    mid.delete_forward()
    assert mid.get_text() == "helloworld"

    word = TextBuffer("hello world")
    word.cursor = (0, 5)
    word.delete_forward(word=True)
    assert word.get_text() == "hello"


# --- TextBuffer: horizontal motion edges -----------------------------------


def test_move_left_wraps_up_a_line_and_clamps_at_the_start() -> None:
    """Left at column 0 wraps to the previous line's end; (0, 0) stays put."""
    buf = TextBuffer("ab\ncd")
    buf.cursor = (1, 0)
    buf.move_left()
    assert buf.cursor == (0, 2)
    buf.move_doc_start()
    buf.move_left()
    assert buf.cursor == (0, 0)


def test_move_right_wraps_down_a_line_and_clamps_at_the_end() -> None:
    """Right at EOL wraps to the next line; on the last line it clamps."""
    buf = TextBuffer("ab\ncd")
    buf.cursor = (0, 2)
    buf.move_right()
    assert buf.cursor == (1, 0)
    buf.move_doc_end()
    buf.move_right()
    assert buf.cursor == (1, 2)


def test_move_right_by_word_wraps_to_the_next_line() -> None:
    """A word-wise right at the end of a line starts the next one."""
    buf = TextBuffer("ab\ncd")
    buf.cursor = (0, 2)
    buf.move_right(word=True)
    assert buf.cursor == (1, 0)


def test_move_line_start_toggles_to_column_zero() -> None:
    """Repeating line-start jumps between the first non-blank and column 0."""
    buf = TextBuffer("    indented")
    buf.cursor = (0, 8)
    buf.move_line_start()
    assert buf.cursor == (0, 4)
    buf.move_line_start()
    assert buf.cursor == (0, 0)


# --- TextBuffer: indent, yank and line commands ----------------------------


def test_indent_selection_without_selection_inserts_a_tab() -> None:
    """Indenting with no selection falls back to one tab stop at the cursor."""
    buf = TextBuffer("ab")
    buf.move_doc_end()
    buf.indent_selection()
    assert buf.get_text() == "ab  "


def test_outdent_strips_a_tab_or_one_tab_width_of_spaces() -> None:
    """Outdent removes a leading tab, or one tab width of leading spaces."""
    tabbed = TextBuffer("\tab")
    tabbed.outdent_selection()
    assert tabbed.get_text() == "ab"

    spaced = TextBuffer("        ab")
    spaced.outdent_selection()
    assert spaced.get_text() == "    ab"


def test_yank_lines_uses_the_selected_rows() -> None:
    """Line-wise yank copies every selected row plus a trailing newline."""
    buf = TextBuffer("a\nb\nc")
    buf.anchor = (0, 0)
    buf.cursor = (1, 0)
    assert buf.yank_lines() == "a\nb\n"
    assert buf.register == "a\nb\n"


def test_yank_selection_prefers_the_selection_over_the_line() -> None:
    """Yank copies the selection when there is one, else the current line."""
    buf = TextBuffer("hello world")
    buf.anchor = (0, 0)
    buf.cursor = (0, 5)
    assert buf.yank_selection() == "hello"
    buf.clear_selection()
    assert buf.yank_selection() == "hello world"


def test_delete_lines_with_a_selection_keeps_one_empty_line() -> None:
    """Deleting every row leaves one empty line and yanks the block."""
    buf = TextBuffer("a\nb")
    buf.anchor = (0, 0)
    buf.cursor = (1, 1)
    assert buf.delete_lines() == "a\nb\n"
    assert buf.lines == [""]
    assert buf.cursor == (0, 0)


def test_move_line_past_the_edge_is_a_noop() -> None:
    """Moving the line beyond the first row changes nothing."""
    buf = TextBuffer("a\nb")
    buf.move_line(-1)
    assert buf.get_text() == "a\nb"


def test_join_lines_at_the_last_row_is_a_noop() -> None:
    """Joining the last row has nothing to join."""
    buf = TextBuffer("a\nb")
    buf.cursor = (1, 0)
    buf.join_lines()
    assert buf.get_text() == "a\nb"


def test_join_lines_keeps_existing_whitespace() -> None:
    """A trailing space or an indented next row joins without adding one."""
    trailing = TextBuffer("ab \ncd")
    trailing.join_lines()
    assert trailing.get_text() == "ab cd"

    indented = TextBuffer("ab\n    cd")
    indented.join_lines()
    assert indented.get_text() == "ab    cd"


def test_delete_to_line_start_removes_the_prefix() -> None:
    """ctrl-u deletes from the line start up to the cursor."""
    buf = TextBuffer("hello")
    buf.cursor = (0, 3)
    buf.delete_to_line_start()
    assert buf.get_text() == "lo"
    assert buf.cursor == (0, 0)


def test_paste_ignores_an_empty_register() -> None:
    """Pasting with nothing yanked changes nothing."""
    buf = TextBuffer("abc")
    buf.paste()
    assert buf.get_text() == "abc"


def test_paste_character_wise_inserts_at_the_cursor() -> None:
    """A non line-wise register is inserted at the cursor."""
    buf = TextBuffer("ab")
    buf.register = "XY"
    buf.cursor = (0, 1)
    buf.paste()
    assert buf.get_text() == "aXYb"


# --- SearchEngine: options, navigation and replace -------------------------


def test_match_pos_is_the_start_of_the_match() -> None:
    """Match.pos exposes (row, start) for cursor placement."""
    assert Match(row=2, start=3, end=5).pos == (2, 3)


def test_whole_word_search_skips_longer_words() -> None:
    """With whole_word on, only the standalone occurrence matches."""
    engine = SearchEngine()
    engine.whole_word = True
    matches = engine.update("foo", TextBuffer("a foo b\nfoobar"))
    assert [(m.row, m.start) for m in matches] == [(0, 2)]


def test_invalid_regex_yields_no_matches() -> None:
    """An uncompilable pattern reports no matches instead of raising."""
    engine = SearchEngine()
    engine.use_regex = True
    assert engine.update("(", TextBuffer("abc")) == []
    assert engine.query == "("


def test_zero_length_matches_are_skipped() -> None:
    """A regex that can match the empty string contributes no matches."""
    engine = SearchEngine()
    engine.use_regex = True
    assert engine.update("a*", TextBuffer("b")) == []


def test_next_without_matches_returns_none() -> None:
    """Navigation with an empty match list reports nothing to jump to."""
    engine = SearchEngine()
    engine.update("zzz", TextBuffer("abc"))
    assert engine.next(TextBuffer("abc")) is None


def test_current_out_of_range_returns_none() -> None:
    """current() is None until a match is selected."""
    assert SearchEngine().current() is None


def test_backward_search_finds_the_match_before_the_cursor() -> None:
    """A backward search from the middle of the text takes the previous hit."""
    engine = SearchEngine()
    buffer = TextBuffer("foo\nboo")
    engine.update("o", buffer)
    match = engine.next(buffer, forward=False, from_pos=(1, 2))
    assert match is not None
    assert (match.row, match.start) == (1, 1)


def test_backward_search_before_every_match_wraps_to_the_last() -> None:
    """With nothing before the cursor, a backward search wraps to the end."""
    engine = SearchEngine()
    buffer = TextBuffer("foo\nboo")
    engine.update("o", buffer)
    match = engine.next(buffer, forward=False, from_pos=(0, 0))
    assert match is not None
    assert (match.row, match.start) == (1, 2)


def test_replace_current_without_a_match_returns_false() -> None:
    """replace_current is a no-op while no match is selected."""
    engine = SearchEngine()
    buffer = TextBuffer("abc")
    engine.update("abc", buffer)
    assert engine.replace_current(buffer, "x") is False


def test_replace_current_rewrites_the_selected_match() -> None:
    """replace_current swaps the current hit and re-runs the search."""
    engine = SearchEngine()
    buffer = TextBuffer("foo foo")
    engine.update("foo", buffer)
    engine.next(buffer)
    assert engine.replace_current(buffer, "bar") is True
    assert buffer.get_text() == "bar foo"
    assert [(m.start, m.end) for m in engine.matches] == [(4, 7)]


def test_replace_current_expands_backreferences_in_regex_mode() -> None:
    """In regex mode the replacement goes through the compiled pattern."""
    engine = SearchEngine()
    buffer = TextBuffer("foo")
    engine.use_regex = True
    engine.update(r"f(o+)", buffer)
    engine.next(buffer)
    assert engine.replace_current(buffer, r"<\1>") is True
    assert buffer.get_text() == "<oo>"


def test_replace_all_without_matches_returns_zero() -> None:
    """replace_all reports 0 when the query matches nothing."""
    engine = SearchEngine()
    buffer = TextBuffer("abc")
    engine.update("zzz", buffer)
    assert engine.replace_all(buffer, "x") == 0


# --- Document: display path, save target, decoding fallback ----------------


def test_display_path_falls_back_for_unnamed_documents() -> None:
    """A named document shows its path; an unnamed one shows the fallback."""
    named = Document(Path("pkg") / "mod.py")
    assert named.display_path == str(Path("pkg") / "mod.py")
    assert Document().display_path == "[no name]"


def test_save_with_a_path_retargets_the_document(tmp_path: Path) -> None:
    """Saving an unnamed buffer to a path records it as the document path."""
    doc = Document()
    doc.buffer.insert_text("hi")
    target = tmp_path / "new.txt"
    assert doc.save(target) == target
    assert doc.path == target
    assert target.read_text(encoding="utf-8") == "hi"
    assert doc.modified is False


def test_save_without_a_path_raises() -> None:
    """Saving a document that has no path is a programming error."""
    with pytest.raises(ValueError, match="without a path"):
        Document().save()


def test_open_falls_back_when_the_bytes_are_undecodable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An empty preferred encoding is skipped and undecodable bytes degrade."""
    monkeypatch.setattr(
        "yate.editor_core.document.locale.getpreferredencoding",
        lambda do_setlocale=True: "",
    )
    raw = bytes([0x81, 0x8D])  # invalid as UTF-8 and undefined in cp1252
    weird = tmp_path / "weird.bin"
    weird.write_bytes(raw)
    doc = Document.open(weird)
    assert doc.encoding == "utf-8"
    assert doc.buffer.get_text() == raw.decode("utf-8", errors="replace")
