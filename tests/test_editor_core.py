"""Headless tests for editor_core and the key map dispatch logic.

Run with:  .venv\\Scripts\\python -m unittest discover -s tests -v
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import TYPE_CHECKING, cast

from yate.editor_core import Document, SearchEngine, TextBuffer
from yate.keymaps.base import ActionContext, parse_key
from yate.keymaps.vsc import VscKeymap
from yate.keymaps.vim import VimKeymap, VimMode

if TYPE_CHECKING:
    from yate.app import YateApp


class BufferTests(unittest.TestCase):
    def test_insert_and_movement(self):
        buf = TextBuffer("hello\nworld")
        self.assertEqual(buf.lines, ["hello", "world"])
        buf.move_doc_end()
        self.assertEqual(buf.cursor, (1, 5))
        buf.move_line_start()
        self.assertEqual(buf.cursor, (1, 0))

    def test_insert_text_multiline(self):
        buf = TextBuffer("ab")
        buf.move_right()
        buf.insert_text("X\nY")
        self.assertEqual(buf.get_text(), "aX\nYb")
        self.assertEqual(buf.cursor, (1, 1))

    def test_backspace_joins_lines(self):
        buf = TextBuffer("ab\ncd")
        buf.cursor = (1, 0)
        buf.delete_backward()
        self.assertEqual(buf.get_text(), "abcd")

    def test_undo_redo(self):
        buf = TextBuffer("hello")
        buf.move_doc_end()
        buf.insert_text(" world")
        self.assertEqual(buf.get_text(), "hello world")
        buf.undo()
        self.assertEqual(buf.get_text(), "hello")
        buf.redo()
        self.assertEqual(buf.get_text(), "hello world")

    def test_typed_chars_coalesce_in_one_undo_step(self):
        buf = TextBuffer("")
        for ch in "abc":
            buf.insert_text(ch)
        self.assertEqual(buf.get_text(), "abc")
        buf.undo()
        self.assertEqual(buf.get_text(), "")

    def test_word_motions(self):
        buf = TextBuffer("foo bar  baz")
        buf.move_right(word=True)
        self.assertEqual(buf.col, 4)
        buf.move_right(word=True)
        self.assertEqual(buf.col, 9)  # "baz" starts after the double space
        buf.move_left(word=True)
        self.assertEqual(buf.col, 4)

    def test_selection_and_cut(self):
        buf = TextBuffer("hello world")
        buf.anchor = (0, 0)
        buf.cursor = (0, 5)
        self.assertEqual(buf.selected_text(), "hello")
        text = buf.delete_selection()
        self.assertEqual(text, "hello")
        self.assertEqual(buf.get_text(), " world")

    def test_duplicate_and_move_line(self):
        buf = TextBuffer("a\nb")
        buf.cursor = (0, 0)
        buf.duplicate_line()
        self.assertEqual(buf.lines, ["a", "a", "b"])
        buf.move_line(1)
        self.assertEqual(buf.lines, ["a", "b", "a"])

    def test_delete_lines_yanks(self):
        buf = TextBuffer("a\nb\nc")
        buf.cursor = (1, 0)
        buf.delete_lines()
        self.assertEqual(buf.lines, ["a", "c"])
        self.assertEqual(buf.register, "b\n")
        buf.paste()
        self.assertIn("b", buf.lines)

    def test_join_lines(self):
        buf = TextBuffer("foo\nbar")
        buf.cursor = (0, 0)
        buf.join_lines()
        self.assertEqual(buf.get_text(), "foo bar")

    def test_indent_outdent(self):
        buf = TextBuffer("a\nb", tab_width=4)
        buf.select_all()
        buf.indent_selection()
        self.assertTrue(all(line.startswith("    ") for line in buf.lines))
        buf.outdent_selection()
        self.assertEqual(buf.get_text(), "a\nb")


class SearchTests(unittest.TestCase):
    def test_find_all_matches(self):
        buf = TextBuffer("cat bat cat")
        engine = SearchEngine()
        matches = engine.update("cat", buf)
        self.assertEqual(len(matches), 2)

    def test_next_wraps_around(self):
        buf = TextBuffer("cat\ncat")
        engine = SearchEngine()
        engine.update("cat", buf)
        m1 = engine.next(buf, forward=True)
        assert m1 is not None
        self.assertEqual(m1.row, 0)
        m2 = engine.next(buf, forward=True)
        assert m2 is not None
        self.assertEqual(m2.row, 1)
        m3 = engine.next(buf, forward=True)
        assert m3 is not None
        self.assertEqual(m3.row, 0)

    def test_replace_all(self):
        buf = TextBuffer("cat dog cat")
        engine = SearchEngine()
        engine.update("cat", buf)
        count = engine.replace_all(buf, "fox")
        self.assertEqual(count, 2)
        self.assertEqual(buf.get_text(), "fox dog fox")

    def test_regex_search(self):
        buf = TextBuffer("a1 b2 c3")
        engine = SearchEngine()
        engine.use_regex = True
        matches = engine.update(r"[a-z]\d", buf)
        self.assertEqual(len(matches), 3)


class DocumentTests(unittest.TestCase):
    def test_save_and_reopen(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "note.txt"
            doc = Document(path, TextBuffer("line1\nline2"))
            doc.save()
            reopened = Document.open(path)
            self.assertEqual(reopened.buffer.get_text(), "line1\nline2")
            self.assertFalse(reopened.modified)
            reopened.buffer.insert_text("x")
            self.assertTrue(reopened.modified)

    def test_filetype_detection(self):
        doc = Document(Path("foo.py"))
        self.assertEqual(doc.filetype, "py")


class KeyNotationTests(unittest.TestCase):
    def test_parse_special_keys(self):
        self.assertEqual(parse_key("<ctrl-s>"), "\x13")
        self.assertEqual(parse_key("<esc>"), "\x1b")
        self.assertEqual(parse_key("<f1>"), "\x1bOP")
        self.assertEqual(parse_key("a"), "a")
        self.assertEqual(parse_key("<alt-x>"), "\x1bx")
        self.assertEqual(parse_key("<ctrl-]>"), "\x1d")


class _FakeApp:
    """Minimal app stand-in for keymap dispatch tests."""

    def __init__(self) -> None:
        from yate.actions import ActionRegistry, populate

        self.actions = ActionRegistry()
        populate(self.actions)
        self.doc: Document = Document(None, TextBuffer(""))
        self.messages: list[str | tuple[str, bool]] = []

    @property
    def buffer(self) -> TextBuffer:
        return self.doc.buffer

    def execute_action(self, name: str) -> None:
        self.actions.execute(name, ActionContext(cast("YateApp", self)))

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


class VscKeymapTests(unittest.TestCase):
    def test_typing_and_enter(self) -> None:
        app = _FakeApp()
        km = VscKeymap()
        ctx = ActionContext(cast("YateApp", app))
        for ch in "hi":
            km.handle_key(ctx, ch)
        km.handle_key(ctx, "\r")
        km.handle_key(ctx, "x")
        self.assertEqual(app.buffer.get_text(), "hi\nx")

    def test_ctrl_a_selects_all(self) -> None:
        app = _FakeApp()
        app.doc = Document(None, TextBuffer("hello\nworld"))
        km = VscKeymap()
        km.handle_key(ActionContext(cast("YateApp", app)), parse_key("<ctrl-a>"))
        self.assertTrue(app.buffer.has_selection())


class VimKeymapTests(unittest.TestCase):
    def _ctx(self, app: _FakeApp) -> ActionContext:
        return ActionContext(cast("YateApp", app))

    def test_insert_and_escape(self):
        app = _FakeApp()
        km = VimKeymap()
        ctx = self._ctx(app)
        km.handle_key(ctx, "i")
        self.assertEqual(km.mode, VimMode.INSERT)
        for ch in "abc":
            km.handle_key(ctx, ch)
        km.handle_key(ctx, "\x1b")
        self.assertEqual(km.mode, VimMode.NORMAL)
        self.assertEqual(app.buffer.get_text(), "abc")

    def test_dd_deletes_line(self):
        app = _FakeApp()
        app.doc = Document(None, TextBuffer("one\ntwo\nthree"))
        km = VimKeymap()
        ctx = self._ctx(app)
        km.handle_key(ctx, "d")
        km.handle_key(ctx, "d")
        self.assertNotIn("one", app.buffer.lines)
        self.assertEqual(app.buffer.register, "one\n")

    def test_yy_pastes_line(self):
        app = _FakeApp()
        app.doc = Document(None, TextBuffer("one"))
        km = VimKeymap()
        ctx = self._ctx(app)
        km.handle_key(ctx, "y")
        km.handle_key(ctx, "y")
        km.handle_key(ctx, "p")
        self.assertEqual(app.buffer.line_count, 2)

    def test_word_motion(self):
        app = _FakeApp()
        app.doc = Document(None, TextBuffer("foo bar"))
        km = VimKeymap()
        ctx = self._ctx(app)
        km.handle_key(ctx, "w")
        self.assertEqual(app.buffer.col, 4)

    def test_visual_selection_delete(self):
        app = _FakeApp()
        app.doc = Document(None, TextBuffer("hello"))
        km = VimKeymap()
        ctx = self._ctx(app)
        km.handle_key(ctx, "v")
        km.handle_key(ctx, "l")
        km.handle_key(ctx, "l")
        self.assertTrue(app.buffer.has_selection())
        km.handle_key(ctx, "x")
        self.assertEqual(app.buffer.get_text(), "llo")
        self.assertEqual(km.mode, VimMode.NORMAL)


if __name__ == "__main__":
    unittest.main()
