"""Headless tests for the vim keymap: modes, counts, operators, visual mode.

The keymap is driven through :meth:`VimKeymap.handle_key` with a real
:class:`EditorSession`, the real built-in action table (so editing actions do
what the editor does) and a recording stand-in for the few editor-level entry
points the table calls.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import pytest

from yate.actions import populate
from yate.config import YateConfig
from yate.editor_core import BufferReadOnlyError, Document, TextBuffer
from yate.keymaps import vim as vim_module
from yate.keymaps.base import ActionContext, KeyUi, parse_key
from yate.keymaps.vim import VimKeymap, VimMode
from yate.registries import ActionRegistry
from yate.session import EditorSession

ESC: str = "\x1b"
CTRL_R: str = "\x12"
CTRL_G: str = "\x07"
CTRL_D: str = "\x04"
CTRL_U: str = "\x15"
CTRL_F: str = "\x06"
CTRL_B: str = "\x02"
CTRL_W: str = "\x17"
CTRL_SLASH: str = "\x1f"
CTRL_V: str = "\x16"
DEL: str = "\x1b[3~"


class _Editor:
    """A minimal editor: real session + action table, recorded UI calls."""

    def __init__(self, text: str = "") -> None:
        self.session = EditorSession(YateConfig())
        self.session.new_buffer().buffer.set_text(text)
        self.actions = ActionRegistry()
        self.messages: list[str] = []
        self.prompts: list[tuple[str, bool]] = []
        self.pages: list[tuple[int, bool]] = []
        self.help_shown = 0
        self.ui = KeyUi(
            execute_action=self.execute_action,
            message=self.message,
            command_prompt=self.command_prompt,
            find_prompt=self.find_prompt,
            goto_prompt=self.goto_prompt,
            toggle_keymap=self.toggle_keymap,
        )
        self.populate()

    def populate(self) -> None:
        """Load the built-in action table bound to this stand-in editor."""
        populate(self.actions, cast(Any, self))

    # ---------------------------------------------------------- state access
    @property
    def doc(self) -> Document:
        """The active document."""
        return self.session.doc

    @property
    def buffer(self) -> TextBuffer:
        """The active text buffer."""
        return self.session.buffer

    def context(self) -> ActionContext:
        """Build an action context against this editor."""
        return ActionContext(self.session, self.ui)

    # ------------------------------------------------------- UI entry points
    def execute_action(self, name: str) -> bool:
        """Run a named action from the registry."""
        return self.actions.execute(name, self.context())

    def message(self, text: str) -> None:
        """Record a status message."""
        self.messages.append(text)

    def command_prompt(self) -> None:
        """Record the command prompt opening."""
        self.prompts.append(("command", True))

    def find_prompt(self, forward: bool) -> None:
        """Record the find prompt opening with its direction."""
        self.prompts.append(("find", forward))

    def goto_prompt(self) -> None:
        """Record the go-to-line prompt opening."""
        self.prompts.append(("goto", True))

    def toggle_keymap(self) -> None:
        """Record a keymap toggle request."""
        self.prompts.append(("toggle", True))

    # ------------------------------------------------- editor-side entry points
    def page(self, direction: int, half: bool = False) -> None:
        """Record a page scroll with direction and half-page flag."""
        self.pages.append((direction, half))

    def find_next(self, forward: bool) -> None:
        """Record a find-next dispatch with its direction."""
        self.prompts.append(("next", forward))

    def replace_prompt(self) -> None:
        """Record the replace prompt opening."""
        self.prompts.append(("replace", True))

    def show_manual(self) -> None:
        """Record the manual overlay opening."""
        self.prompts.append(("manual", True))

    def shell_prompt(self) -> None:
        """Record the shell prompt opening."""
        self.prompts.append(("shell", True))

    def show_help(self) -> None:
        """Count a help overlay opening."""
        self.help_shown += 1

    # The tables reach some hooks through the flow collaborators
    # (editor.prompt_flows / overlays / shell); these stand-ins keep the
    # calls recording into the same lists, so the assertions do not move.
    @property
    def prompt_flows(self) -> SimpleNamespace:
        """Flow-collaborator stand-in for the prompt hooks."""
        return SimpleNamespace(
            find_prompt=self.find_prompt,
            find_next=self.find_next,
            replace_prompt=self.replace_prompt,
            goto_prompt=self.goto_prompt,
        )

    @property
    def overlays(self) -> SimpleNamespace:
        """Flow-collaborator stand-in for the overlay hooks."""
        return SimpleNamespace(
            show_help=self.show_help,
            show_manual=self.show_manual,
        )

    @property
    def shell(self) -> SimpleNamespace:
        """Flow-collaborator stand-in for the shell hooks."""
        return SimpleNamespace(open_prompt=self.shell_prompt)

    def save_document(self) -> None:
        """Record a save-document dispatch."""
        self.prompts.append(("save", True))

    def prompt_open(self) -> None:
        """Record the open-file prompt opening."""
        self.prompts.append(("open", True))

    def new_buffer(self) -> None:
        """Record a new-buffer dispatch."""
        self.prompts.append(("new", True))

    def close_tab(self) -> None:
        """Record a close-tab dispatch."""
        self.prompts.append(("close", True))


def _setup(text: str = "") -> tuple[_Editor, VimKeymap, ActionContext]:
    editor = _Editor(text)
    keymap = VimKeymap()
    return editor, keymap, editor.context()


def _press(keymap: VimKeymap, ctx: ActionContext, *keys: str) -> None:
    for key in keys:
        keymap.handle_key(ctx, key)


# --- insert mode ------------------------------------------------------------


def test_insert_enters_and_escape_returns_to_normal() -> None:
    """i types before the cursor; ESC steps back and reports the mode."""
    editor, keymap, ctx = _setup("abc")
    _press(keymap, ctx, "i")
    assert keymap.mode is VimMode.INSERT
    assert editor.messages[-1] == "-- INSERT --"

    _press(keymap, ctx, "X")
    assert editor.buffer.get_text() == "Xabc"
    assert editor.buffer.cursor == (0, 1)

    _press(keymap, ctx, ESC)
    assert keymap.mode is VimMode.NORMAL
    assert editor.buffer.cursor == (0, 0)
    assert editor.messages[-1] == "-- NORMAL --"


def test_append_inserts_after_the_cursor() -> None:
    """a puts insert mode one column to the right."""
    editor, keymap, ctx = _setup("abc")
    _press(keymap, ctx, "a", "X")
    assert editor.buffer.get_text() == "aXbc"
    assert editor.buffer.cursor == (0, 2)


def test_insert_at_line_start_and_line_end() -> None:
    """I and A jump to the edges of the line before inserting."""
    editor, keymap, ctx = _setup("abc")
    editor.buffer.set_cursor((0, 1))

    _press(keymap, ctx, "I")
    assert editor.buffer.cursor == (0, 0)
    _press(keymap, ctx, "X", ESC)
    assert editor.buffer.get_text() == "Xabc"

    _press(keymap, ctx, "A", "Z", ESC)
    assert editor.buffer.get_text() == "XabcZ"


def test_open_line_below_and_above() -> None:
    """o opens a line under the cursor, O above it."""
    editor, keymap, ctx = _setup("ab")
    _press(keymap, ctx, "o", "x", ESC)
    assert editor.buffer.lines == ["ab", "x"]
    assert editor.buffer.cursor == (1, 0)  # ESC steps back over the typed char

    editor, keymap, ctx = _setup("ab")
    editor.buffer.set_cursor((0, 1))
    _press(keymap, ctx, "O", "y", ESC)
    assert editor.buffer.lines == ["y", "ab"]


def test_insert_entry_refused_on_read_only_buffer() -> None:
    """Read-only buffers refuse all insert entries and stay in NORMAL."""
    editor, keymap, ctx = _setup("abc")
    editor.buffer.read_only = True
    for key in ("i", "I", "a", "A", "o", "O"):
        with pytest.raises(BufferReadOnlyError):
            keymap.handle_key(ctx, key)
        assert keymap.mode is VimMode.NORMAL
    assert editor.buffer.get_text() == "abc"


def test_insert_mode_editing_keys() -> None:
    """Enter, tab, backspace, delete, ctrl-w and ctrl-u dispatch their actions."""
    editor, keymap, ctx = _setup("abc")
    _press(keymap, ctx, "a", "\r")
    assert editor.buffer.lines == ["a", "bc"]

    editor, keymap, ctx = _setup("abc")
    _press(keymap, ctx, "a", "\t")
    assert editor.buffer.lines == ["a   bc"]  # tab stop at column 4

    editor, keymap, ctx = _setup("abc")
    _press(keymap, ctx, "a", "\x7f")
    assert editor.buffer.get_text() == "bc"

    editor, keymap, ctx = _setup("abc")
    _press(keymap, ctx, "i", DEL)
    assert editor.buffer.get_text() == "bc"

    editor, keymap, ctx = _setup("hello world")
    editor.buffer.set_cursor((0, 11))
    _press(keymap, ctx, "i", CTRL_W)
    assert editor.buffer.get_text() == "hello "

    editor, keymap, ctx = _setup("hello world")
    editor.buffer.set_cursor((0, 11))
    _press(keymap, ctx, "i", CTRL_U)
    assert editor.buffer.get_text() == ""


def test_insert_mode_arrows_move_the_cursor() -> None:
    """The arrow escapes run the matching motion without leaving insert mode."""
    editor, keymap, ctx = _setup("ab\ncd")
    _press(keymap, ctx, "i")
    _press(keymap, ctx, "\x1b[C")
    assert editor.buffer.cursor == (0, 1)
    _press(keymap, ctx, "\x1b[B")
    assert editor.buffer.cursor == (1, 1)
    _press(keymap, ctx, "\x1b[D")
    assert editor.buffer.cursor == (1, 0)
    _press(keymap, ctx, "\x1b[A")
    assert editor.buffer.cursor == (0, 0)
    assert keymap.mode is VimMode.INSERT


def test_insert_mode_swallows_unmapped_keys() -> None:
    """A key with no insert-mode meaning changes nothing but is consumed."""
    editor, keymap, ctx = _setup("abc")
    _press(keymap, ctx, "i")
    assert keymap.handle_key(ctx, "\x1b[Z") is True
    assert editor.buffer.get_text() == "abc"
    assert keymap.mode is VimMode.INSERT


# --- motions ----------------------------------------------------------------


def test_horizontal_motion_and_counts() -> None:
    """Counts repeat the motion and the column is clamped to the line."""
    editor, keymap, ctx = _setup("abcdef")
    _press(keymap, ctx, "3", "l")
    assert editor.buffer.col == 3
    _press(keymap, ctx, "h")
    assert editor.buffer.col == 2
    _press(keymap, ctx, "2", "l")
    assert editor.buffer.col == 4
    _press(keymap, ctx, "9", "l")
    assert editor.buffer.col == 6  # clamped to the end of the line


def test_vertical_motion_keeps_the_goal_column() -> None:
    """Crossing a short line does not lose the desired column."""
    editor, keymap, ctx = _setup("long line\nab\nanother long line")
    editor.buffer.set_cursor((0, 8))

    _press(keymap, ctx, "j")
    assert editor.buffer.cursor == (1, 2)
    _press(keymap, ctx, "j")
    assert editor.buffer.cursor == (2, 8)
    _press(keymap, ctx, "2", "k")
    assert editor.buffer.cursor == (0, 8)


def test_word_motions() -> None:
    """w/b/e walk words; counts repeat them."""
    editor, keymap, ctx = _setup("foo bar baz")
    _press(keymap, ctx, "w")
    assert editor.buffer.col == 4
    _press(keymap, ctx, "w")
    assert editor.buffer.col == 8
    _press(keymap, ctx, "b")
    assert editor.buffer.col == 4
    _press(keymap, ctx, "e")
    assert editor.buffer.col == 6
    _press(keymap, ctx, "0", "2", "w")
    assert editor.buffer.col == 8


def test_word_motion_wraps_to_the_next_line_word_start() -> None:
    """w past the row's last word stops on the last char, then wraps."""
    editor, keymap, ctx = _setup("ab cd\n  ef")
    _press(keymap, ctx, "w", "w")
    assert editor.buffer.cursor == (0, 4)  # the row's last char first
    _press(keymap, ctx, "w")
    assert editor.buffer.cursor == (1, 2)  # wrap lands on the first non-blank
    _press(keymap, ctx, "w")
    assert editor.buffer.cursor == (1, 3)  # same rule on the indented row
    _press(keymap, ctx, "w")
    assert editor.buffer.cursor == (1, 3)  # document end: no landing


def test_word_motion_stops_on_an_empty_line() -> None:
    """w stops on an empty line instead of skipping it."""
    editor, keymap, ctx = _setup("ab\n\ncd")
    _press(keymap, ctx, "w")
    assert editor.buffer.cursor == (0, 1)  # the row's last char first
    _press(keymap, ctx, "w")
    assert editor.buffer.cursor == (1, 0)  # the empty line stops the motion
    _press(keymap, ctx, "w")
    assert editor.buffer.cursor == (2, 0)


def test_backward_word_motion_wraps_to_the_last_word_start() -> None:
    """b from a line start lands on the previous line's last word start."""
    editor, keymap, ctx = _setup("ab cd\nef")
    editor.buffer.set_cursor((1, 0))
    _press(keymap, ctx, "b")
    assert editor.buffer.cursor == (0, 3)


def test_delete_word_stops_at_the_line_end() -> None:
    """dw on the row's last word does not swallow the newline."""
    editor, keymap, ctx = _setup("ab cd\nef")
    editor.buffer.set_cursor((0, 3))
    _press(keymap, ctx, "d", "w")
    assert editor.buffer.lines == ["ab ", "ef"]


def test_delete_word_back_stops_at_the_line_start() -> None:
    """db from a line start does not reach into the previous line."""
    editor, keymap, ctx = _setup("ab\ncd")
    editor.buffer.set_cursor((1, 0))
    _press(keymap, ctx, "d", "b")
    assert editor.buffer.lines == ["ab", "cd"]


def test_upper_g_lands_on_the_first_non_blank() -> None:
    """G skips leading indent; gg starts on the first line's word."""
    editor, keymap, ctx = _setup("l1\n  l2")
    _press(keymap, ctx, "G")
    assert editor.buffer.cursor == (1, 2)
    _press(keymap, ctx, "g", "g")
    assert editor.buffer.cursor == (0, 0)


def test_zero_always_lands_on_column_zero() -> None:
    """Unlike the vsc binding, vim's 0 ignores the indent."""
    editor, keymap, ctx = _setup("    indented")
    editor.buffer.set_cursor((0, 8))
    _press(keymap, ctx, "0")
    assert editor.buffer.cursor == (0, 0)


def test_dollar_moves_to_the_line_end() -> None:
    """$ sits on the last character like vim."""
    editor, keymap, ctx = _setup("abc\nde")
    _press(keymap, ctx, "$")
    assert editor.buffer.cursor == (0, 2)
    _press(keymap, ctx, "j", "$")
    assert editor.buffer.cursor == (1, 1)


def test_gg_and_upper_g_jump_to_the_document_edges() -> None:
    """gg is the start, G the end; a count makes both a line jump."""
    editor, keymap, ctx = _setup("l1\nl2\nl3")
    _press(keymap, ctx, "G")
    assert editor.buffer.cursor == (2, 0)  # first non-blank of "l3"
    _press(keymap, ctx, "g", "g")
    assert editor.buffer.cursor == (0, 0)

    _press(keymap, ctx, "2", "G")
    assert editor.buffer.cursor == (1, 0)
    _press(keymap, ctx, "3", "g", "g")
    assert editor.buffer.cursor == (2, 0)


def test_arrow_keys_run_the_same_motions() -> None:
    """The arrow escapes map onto h/j/k/l."""
    editor, keymap, ctx = _setup("ab\ncd")
    _press(keymap, ctx, "\x1b[C")
    assert editor.buffer.cursor == (0, 1)
    _press(keymap, ctx, "\x1b[B")
    assert editor.buffer.cursor == (1, 1)
    _press(keymap, ctx, "\x1b[A")
    assert editor.buffer.cursor == (0, 1)
    _press(keymap, ctx, "\x1b[D")
    assert editor.buffer.cursor == (0, 0)


# --- operators --------------------------------------------------------------


def test_dd_deletes_the_line_into_the_register() -> None:
    """dd removes the current line and yanks it."""
    editor, keymap, ctx = _setup("one\ntwo")
    _press(keymap, ctx, "d", "d")
    assert editor.buffer.lines == ["two"]
    assert editor.buffer.register == "one\n"
    assert editor.messages[-1] == "deleted line"


def test_yy_yanks_and_p_pastes_below_and_above() -> None:
    """yy stores the line; p pastes below, P above."""
    editor, keymap, ctx = _setup("one\ntwo")
    _press(keymap, ctx, "y", "y")
    assert editor.buffer.register == "one\n"
    assert editor.messages[-1] == "yanked line"

    _press(keymap, ctx, "p")
    assert editor.buffer.lines == ["one", "one", "two"]

    _press(keymap, ctx, "P")
    assert editor.buffer.lines == ["one", "one", "one", "two"]


def test_delete_word_operator_with_count() -> None:
    """dw deletes over the motion; a count repeats the motion."""
    editor, keymap, ctx = _setup("hello world")
    _press(keymap, ctx, "d", "w")
    assert editor.buffer.get_text() == "world"
    assert editor.messages[-1] == "deleted"

    editor, keymap, ctx = _setup("one two three")
    _press(keymap, ctx, "2", "d", "w")
    assert editor.buffer.get_text() == "three"


def test_delete_to_line_end_operator() -> None:
    """d$ clears the rest of the line."""
    editor, keymap, ctx = _setup("hello world")
    editor.buffer.set_cursor((0, 5))
    _press(keymap, ctx, "d", "$")
    assert editor.buffer.get_text() == "hello"


def test_yank_operator_restores_the_cursor() -> None:
    """y{motion} copies and leaves the cursor where it was."""
    editor, keymap, ctx = _setup("hello world")
    _press(keymap, ctx, "y", "w")
    assert editor.buffer.register == "hello "
    assert editor.buffer.cursor == (0, 0)
    assert editor.buffer.anchor is None
    assert editor.messages[-1] == "yanked"


def test_delete_word_operator_writes_the_register() -> None:
    """dw fills the register, so p pastes the deleted word back."""
    editor, keymap, ctx = _setup("alpha beta")
    _press(keymap, ctx, "d", "w")
    assert editor.buffer.register == "alpha "
    _press(keymap, ctx, "p")
    assert editor.buffer.get_text() == "alpha beta"


def test_linewise_yank_is_replaced_by_the_next_delete() -> None:
    """yy then d$ replaces the register; p pastes the deleted text."""
    editor, keymap, ctx = _setup("one\ntwo three")
    _press(keymap, ctx, "y", "y")
    assert editor.buffer.register == "one\n"
    _press(keymap, ctx, "j", "d", "$")
    assert editor.buffer.register == "two three"
    _press(keymap, ctx, "p")
    assert editor.buffer.lines == ["one", "two three"]


def test_operator_with_the_g_motion_reports_nothing() -> None:
    """dg / yg drop the operator: no message, no edit, register untouched."""
    editor, keymap, ctx = _setup("abc")
    _press(keymap, ctx, "d", "g")
    assert editor.buffer.get_text() == "abc"
    assert "deleted" not in editor.messages

    editor, keymap, ctx = _setup("abc")
    editor.buffer.register = "keep"
    _press(keymap, ctx, "y", "g")
    assert editor.buffer.get_text() == "abc"
    assert editor.buffer.register == "keep"
    assert "yanked" not in editor.messages


def test_x_deletes_characters() -> None:
    """x deletes under the cursor; a count deletes several."""
    editor, keymap, ctx = _setup("abcdef")
    _press(keymap, ctx, "x")
    assert editor.buffer.get_text() == "bcdef"
    _press(keymap, ctx, "3", "x")
    assert editor.buffer.get_text() == "ef"


def test_undo_and_redo_keys() -> None:
    """u undoes, ctrl-r redoes."""
    editor, keymap, ctx = _setup("abcdef")
    _press(keymap, ctx, "x")
    _press(keymap, ctx, "u")
    assert editor.buffer.get_text() == "abcdef"
    _press(keymap, ctx, CTRL_R)
    assert editor.buffer.get_text() == "bcdef"


def test_join_lines_key() -> None:
    """J dispatches the editor's join action."""
    editor, keymap, ctx = _setup("aa\nbb")
    _press(keymap, ctx, "J")
    assert editor.buffer.lines == ["aa bb"]


def test_unknown_motion_after_an_operator_is_dropped() -> None:
    """An operator without a motion is cancelled, not deferred."""
    editor, keymap, ctx = _setup("aaa")
    _press(keymap, ctx, "d", "z")
    assert editor.buffer.get_text() == "aaa"
    assert keymap.op is None
    _press(keymap, ctx, "w")  # must not fire a delayed dw
    assert editor.buffer.get_text() == "aaa"
    assert editor.buffer.cursor == (0, 2)  # w ran as a plain motion


def test_unknown_operator_follower_runs_its_own_key_once() -> None:
    """dx deletes one char like plain x and does not leave d armed."""
    editor, keymap, ctx = _setup("abc")
    _press(keymap, ctx, "d", "x")
    assert editor.buffer.get_text() == "bc"
    assert keymap.op is None
    _press(keymap, ctx, "w")
    assert editor.buffer.cursor == (0, 1)  # plain motion, nothing deleted


def test_g_prefix_with_an_unknown_key_is_dropped() -> None:
    """A stray g does not swallow the next motion either."""
    editor, keymap, ctx = _setup("abc")
    _press(keymap, ctx, "g", "z", "l")
    assert editor.buffer.cursor == (0, 1)


# --- visual mode ------------------------------------------------------------


def test_visual_delete_selection() -> None:
    """v + motions selects; d deletes the selection."""
    editor, keymap, ctx = _setup("hello")
    _press(keymap, ctx, "v")
    assert keymap.mode is VimMode.VISUAL
    assert editor.messages[-1] == "-- VISUAL --"

    # the selection spans half-open: the cell under the cursor is not in it
    _press(keymap, ctx, "l", "l", "d")
    assert editor.buffer.get_text() == "llo"
    assert keymap.mode is VimMode.NORMAL
    assert editor.messages[-1] == "deleted selection"


def test_visual_yank_clears_the_selection() -> None:
    """y copies the selection and returns the cursor to its start."""
    editor, keymap, ctx = _setup("hello")
    _press(keymap, ctx, "v", "l", "l", "y")
    assert editor.buffer.register == "he"
    assert editor.buffer.cursor == (0, 0)
    assert editor.buffer.has_selection() is False
    assert keymap.mode is VimMode.NORMAL


def test_visual_mode_swallows_a_count_prefix() -> None:
    """Digits are consumed in visual mode; the count is not accumulated.

    Only the motion that follows runs, so ``v2l`` extends one column, not two.
    """
    editor, keymap, ctx = _setup("abcdef")
    _press(keymap, ctx, "v", "2", "l")
    assert editor.buffer.cursor == (0, 1)
    assert editor.buffer.has_selection() is True


def test_visual_line_mode_deletes_whole_lines() -> None:
    """V selects whole lines; j extends them linewise."""
    editor, keymap, ctx = _setup("a\nbb\nccc")
    _press(keymap, ctx, "V")
    assert keymap.mode is VimMode.VISUAL_LINE
    assert editor.buffer.anchor == (0, 0)
    assert editor.buffer.cursor == (0, 1)

    _press(keymap, ctx, "j", "d")
    assert editor.buffer.lines == ["ccc"]
    assert editor.messages[-1] == "deleted lines"


def test_visual_line_mode_yanks_whole_lines() -> None:
    """y in visual-line mode yanks the selected lines."""
    editor, keymap, ctx = _setup("a\nbb\nccc")
    _press(keymap, ctx, "V", "j", "y")
    assert editor.buffer.register == "a\nbb\n"
    assert editor.messages[-1] == "yanked lines"


def test_visual_and_visual_line_toggle_each_other() -> None:
    """v leaves visual-line mode, V enters it, v again cancels."""
    editor, keymap, ctx = _setup("a\nbb")
    _press(keymap, ctx, "V")
    _press(keymap, ctx, "v")
    assert keymap.mode is VimMode.VISUAL

    _press(keymap, ctx, "v")
    assert keymap.mode is VimMode.NORMAL
    assert editor.buffer.has_selection() is False


def test_escape_and_prompts_leave_visual_mode() -> None:
    """ESC clears; : and / return to normal before opening the prompt."""
    editor, keymap, ctx = _setup("abc")
    _press(keymap, ctx, "v", ESC)
    assert keymap.mode is VimMode.NORMAL
    assert editor.buffer.has_selection() is False

    _press(keymap, ctx, "v", ":")
    assert keymap.mode is VimMode.NORMAL
    assert editor.prompts[-1] == ("command", True)

    _press(keymap, ctx, "v", "/")
    assert keymap.mode is VimMode.NORMAL
    assert editor.prompts[-1] == ("find", True)

    _press(keymap, ctx, "v", "?")
    assert editor.prompts[-1] == ("find", False)


# --- visual block mode (ctrl+v, column selection) ----------------------------


def test_ctrl_v_enters_visual_block_mode() -> None:
    """ctrl+v enters blockwise visual mode anchored at the cursor."""
    editor, keymap, ctx = _setup("abc")
    _press(keymap, ctx, CTRL_V)
    assert keymap.mode is VimMode.VISUAL_BLOCK
    assert editor.messages[-1] == "-- VISUAL BLOCK --"
    assert editor.buffer.anchor == (0, 0)


def test_ctrl_v_in_block_mode_exits_and_clears() -> None:
    """A second ctrl+v leaves block mode and drops the block selection."""
    editor, keymap, ctx = _setup("abc")
    _press(keymap, ctx, CTRL_V, CTRL_V)
    assert keymap.mode is VimMode.NORMAL
    assert editor.buffer.has_selection() is False
    assert editor.buffer.block is False


def test_block_motions_extend_rectangle() -> None:
    """Motions in block mode extend the rectangle via the block flag."""
    editor, keymap, ctx = _setup("abcd\nefgh\nijkl")
    _press(keymap, ctx, CTRL_V, "l", "j")
    assert editor.buffer.block_region() == (0, 0, 1, 1)
    assert keymap.mode is VimMode.VISUAL_BLOCK


def test_block_yank_copies_rectangle_and_lands_at_corner() -> None:
    """y in block mode yanks the rectangle and lands on its top-left corner.

    The block API's right column is half-open (plan-a), so the second ``l``
    is what makes the rectangle cover both ``ab`` / ``ef`` columns.
    """
    editor, keymap, ctx = _setup("abcd\nefgh\nijkl")
    _press(keymap, ctx, CTRL_V, "l", "l", "j", "y")
    assert editor.buffer.register == "ab\nef"
    assert editor.buffer.register_block is True
    assert editor.buffer.cursor == (0, 0)
    assert keymap.mode is VimMode.NORMAL


def test_block_delete_removes_rectangle_one_undo() -> None:
    """d in block mode removes each covered span in one undo step."""
    editor, keymap, ctx = _setup("abcd\nefgh\nijkl")
    _press(keymap, ctx, CTRL_V, "l", "l", "j", "d")
    assert editor.buffer.lines == ["cd", "gh", "ijkl"]
    assert keymap.mode is VimMode.NORMAL

    editor.buffer.undo()
    assert editor.buffer.lines == ["abcd", "efgh", "ijkl"]


def test_block_delete_feeds_block_paste() -> None:
    """A deleted block pastes back as a rectangle at the cursor column."""
    editor, keymap, ctx = _setup("abcd\nefgh\nijkl")
    # the second l widens the rectangle past the half-open right column:
    # \x16 + j alone is zero-width, one l is one column wide
    _press(keymap, ctx, CTRL_V, "l", "l", "j", "d")
    assert editor.buffer.lines == ["cd", "gh", "ijkl"]
    assert editor.buffer.register_block is True

    _press(keymap, ctx, "j", "p")
    # the rectangle re-lands at the cursor's column on rows 1..2
    assert editor.buffer.lines == ["cd", "abgh", "efijkl"]


def test_v_from_block_mode_converts_to_charwise() -> None:
    """v in block mode keeps both corners but drops the block flag."""
    editor, keymap, ctx = _setup("abcd")
    _press(keymap, ctx, CTRL_V, "j", "v")
    assert keymap.mode is VimMode.VISUAL
    assert editor.buffer.block is False
    assert editor.buffer.anchor == (0, 0)


def test_v_from_block_mode_converts_to_linewise() -> None:
    """V in block mode converts the corners into whole selected rows."""
    editor, keymap, ctx = _setup("abcd")
    _press(keymap, ctx, CTRL_V, "j", "V")
    assert keymap.mode is VimMode.VISUAL_LINE
    assert editor.buffer.anchor == (0, 0)
    assert editor.buffer.cursor == (0, 4)  # _fix_linewise reached the row end


def test_escape_leaves_block_mode() -> None:
    """ESC clears the selection and leaves no stale block flag."""
    editor, keymap, ctx = _setup("abcd\nefgh")
    _press(keymap, ctx, CTRL_V, "j", ESC)
    assert keymap.mode is VimMode.NORMAL
    assert editor.buffer.has_selection() is False
    assert editor.buffer.block is False


def test_prompt_keys_leave_block_mode() -> None:
    """: / ? return to normal mode before opening their prompts."""
    editor, keymap, ctx = _setup("abcd")
    _press(keymap, ctx, CTRL_V, ":")
    assert keymap.mode is VimMode.NORMAL
    assert editor.prompts[-1] == ("command", True)

    _press(keymap, ctx, CTRL_V, "/")
    assert keymap.mode is VimMode.NORMAL
    assert editor.prompts[-1] == ("find", True)

    _press(keymap, ctx, CTRL_V, "?")
    assert editor.prompts[-1] == ("find", False)


def test_drop_visual_from_block_returns_to_normal() -> None:
    """drop_visual (a mouse click) ends blockwise visual mode too."""
    _, keymap, ctx = _setup("abc")
    _press(keymap, ctx, CTRL_V)
    assert keymap.mode is VimMode.VISUAL_BLOCK

    keymap.drop_visual()
    assert keymap.mode is VimMode.NORMAL


def test_block_shift_indents_covered_rows() -> None:
    """> in block mode indents the covered rows; the selection survives."""
    editor, keymap, ctx = _setup("ab\ncd")
    _press(keymap, ctx, CTRL_V, "j", ">")
    assert editor.buffer.lines == ["    ab", "    cd"]
    assert keymap.mode is VimMode.VISUAL_BLOCK

    _press(keymap, ctx, ">")
    assert editor.buffer.lines == ["        ab", "        cd"]


def test_zero_width_block_yank_drops_to_normal_without_crash() -> None:
    """y right after Ctrl+V (no motion) yanks nothing, exits block mode."""
    editor, keymap, ctx = _setup("abc")
    _press(keymap, ctx, CTRL_V, "y")
    assert keymap.mode is VimMode.NORMAL
    assert editor.buffer.lines == ["abc"]
    assert not editor.buffer.has_block_selection()


def test_block_yank_resets_goal_column() -> None:
    """After a block yank, j lands at column 0 (set_cursor drops the goal)."""
    editor, keymap, ctx = _setup("ab\ncd")
    _press(keymap, ctx, CTRL_V, "l", "y", "j")
    assert editor.buffer.cursor == (1, 0)


def test_v_from_line_mode_ctrl_v_converts_to_block() -> None:
    """V then Ctrl+V converts the linewise visual to a block selection."""
    editor, keymap, ctx = _setup("ab\ncd\nef")
    _press(keymap, ctx, "V", CTRL_V)
    assert keymap.mode is VimMode.VISUAL_BLOCK
    assert editor.buffer.block is True


def test_visual_mode_ctrl_v_converts_to_block() -> None:
    """v then Ctrl+V converts the charwise visual to a block selection."""
    editor, keymap, ctx = _setup("ab\ncd\nef")
    _press(keymap, ctx, "v", "l", CTRL_V)
    assert keymap.mode is VimMode.VISUAL_BLOCK
    assert editor.buffer.block is True


def test_named_register_block_yank_stays_internal() -> None:
    """"a-prefixed block yank stores the rectangle but records no type."""
    editor, keymap, ctx = _setup("ab\ncd")
    _press(keymap, ctx, '"', "a", CTRL_V, "l", "j", "y")
    # half-open right bound: the block covers column 0 only
    assert editor.buffer.named_registers["a"] == "a\nc"
    assert editor.buffer.register == ""
    assert editor.buffer.register_block is False


def test_zero_width_multiline_block_yank_is_noop() -> None:
    """Ctrl+V j y (zero-width block) stores nothing, like vim."""
    editor, keymap, ctx = _setup("ab\ncd")
    _press(keymap, ctx, CTRL_V, "j", "y")
    assert keymap.mode is VimMode.NORMAL
    assert editor.buffer.register == ""
    assert editor.buffer.register_block is False
    assert editor.buffer.lines == ["ab", "cd"]


def test_zero_width_multiline_block_delete_is_noop() -> None:
    """Ctrl+V j d (zero-width block) changes no text, like vim."""
    editor, keymap, ctx = _setup("ab\ncd")
    _press(keymap, ctx, CTRL_V, "j", "d")
    assert keymap.mode is VimMode.NORMAL
    assert editor.buffer.lines == ["ab", "cd"]
    assert editor.buffer.register == ""
    assert editor.buffer.register_block is False


def test_register_rewrite_after_block_yank_drops_block_type() -> None:
    """A register rewrite after a block yank drops the block paste type."""
    editor, keymap, ctx = _setup("ab\ncd")
    _press(keymap, ctx, CTRL_V, "l", "j", "y")
    assert editor.buffer.register_block is True
    # dd rewrites the register linewise (delete_lines)
    _press(keymap, ctx, "d", "d")
    assert editor.buffer.register_block is False
    _press(keymap, ctx, "p")
    # linewise paste below row 0; a stale block type would replay the
    # rectangle into row 0 instead (["abcd", ""])
    assert editor.buffer.lines == ["cd", "ab"]


# --- normal-mode entry points ----------------------------------------------


def test_prompt_keys_dispatch_the_recorded_prompts() -> None:
    """/ ? : n N reach the editor through the UI callbacks and the tables."""
    editor, keymap, ctx = _setup("abc")
    _press(keymap, ctx, "/")
    assert editor.prompts[-1] == ("find", True)
    _press(keymap, ctx, "?")
    assert editor.prompts[-1] == ("find", False)
    _press(keymap, ctx, ":")
    assert editor.prompts[-1] == ("command", True)
    _press(keymap, ctx, "n")
    assert editor.prompts[-1] == ("next", True)
    _press(keymap, ctx, "N")
    assert editor.prompts[-1] == ("next", False)


def test_goto_and_page_keys_dispatch_their_actions() -> None:
    """ctrl-g opens go-to-line; the page keys run the pager actions."""
    editor, keymap, ctx = _setup("abc")
    _press(keymap, ctx, CTRL_G)
    assert editor.prompts[-1] == ("goto", True)

    _press(keymap, ctx, CTRL_D)
    assert editor.pages[-1] == (1, True)
    _press(keymap, ctx, CTRL_U)
    assert editor.pages[-1] == (-1, True)
    _press(keymap, ctx, CTRL_F)
    assert editor.pages[-1] == (1, False)
    _press(keymap, ctx, CTRL_B)
    assert editor.pages[-1] == (-1, False)


def test_escape_clears_a_pending_operator_and_count() -> None:
    """ESC drops half-typed commands so the next key starts clean."""
    editor, keymap, ctx = _setup("abc")
    _press(keymap, ctx, "3", "d", ESC, "x")
    assert editor.buffer.get_text() == "bc"


def test_ctrl_slash_toggles_the_keymap_and_clears_state() -> None:
    """ctrl+/ works in every mode and drops pending state."""
    editor, keymap, ctx = _setup("abc")
    _press(keymap, ctx, "3", "d", CTRL_SLASH)
    assert editor.prompts[-1] == ("toggle", True)
    _press(keymap, ctx, "x")
    assert editor.buffer.get_text() == "bc"


def test_function_keys_run_their_actions() -> None:
    """The F-keys are handled before mode dispatch."""
    editor, keymap, ctx = _setup("abc")
    _press(keymap, ctx, parse_key("<f1>"))
    assert editor.help_shown == 1
    _press(keymap, ctx, parse_key("<f2>"))
    assert editor.prompts[-1] == ("shell", True)
    _press(keymap, ctx, parse_key("<f3>"))
    assert editor.prompts[-1] == ("next", True)
    _press(keymap, ctx, parse_key("<f4>"))
    assert editor.prompts[-1] == ("replace", True)
    _press(keymap, ctx, parse_key("<f5>"))
    assert editor.prompts[-1] == ("command", True)
    _press(keymap, ctx, parse_key("<f8>"))
    assert editor.prompts[-1] == ("manual", True)
    assert keymap.mode is VimMode.NORMAL


def test_function_keys_work_from_insert_mode_too() -> None:
    """A function key leaves the mode untouched but still dispatches."""
    editor, keymap, ctx = _setup("abc")
    _press(keymap, ctx, "i", parse_key("<f5>"))
    assert editor.prompts[-1] == ("command", True)
    assert keymap.mode is VimMode.INSERT


# --- extension bindings -----------------------------------------------------


def test_extension_binding_in_normal_mode_is_dispatched() -> None:
    """An extension-registered key runs its action in normal mode."""
    editor, keymap, ctx = _setup("abc")
    calls: list[str] = []
    editor.actions.register("ext_run", lambda _ctx: calls.append("ran"), "ext")

    keymap.add_binding("q", "ext_run")

    assert keymap.handle_key(ctx, "q") is True
    assert calls == ["ran"]


def test_non_extension_binding_is_not_dispatched_by_fallback() -> None:
    """The fallback only honours bindings marked as extension ones."""
    editor, keymap, ctx = _setup("abc")
    calls: list[str] = []
    editor.actions.register("ext_run", lambda _ctx: calls.append("ran"), "ext")

    keymap.add_binding("w", "ext_run", category="vim")

    _press(keymap, ctx, "w")
    assert calls == []
    assert editor.buffer.col == 2  # the motion ran instead


def test_unmapped_normal_key_is_swallowed() -> None:
    """A key with no binding and no motion does nothing, but is consumed."""
    editor, keymap, ctx = _setup("abc")
    assert keymap.handle_key(ctx, "z") is True
    assert editor.buffer.get_text() == "abc"
    assert editor.buffer.cursor == (0, 0)


def test_function_key_without_a_binding_is_consumed() -> None:
    """F-keys the table does not bind are still handled by the keymap."""
    editor, keymap, ctx = _setup("abc")
    assert keymap.handle_key(ctx, parse_key("<f6>")) is True
    assert keymap.mode is VimMode.NORMAL
    assert editor.buffer.get_text() == "abc"


def test_binding_to_an_unknown_action_is_reported_and_consumed() -> None:
    """A binding naming an unregistered action reports it, then swallows it.

    The unknown name is surfaced by ``dispatch`` ("unknown action: ...") so
    the failure is never silent, but in vim mode the key itself stays
    consumed: F-keys are keymap-owned (unbound ones are swallowed too, see
    ``test_function_key_without_a_binding_is_consumed``) and normal mode
    deliberately swallows unmapped keys -- a dead action on an
    extension-bound normal key is absorbed the same way.
    """
    editor, keymap, ctx = _setup("abc")
    keymap.add_binding("<f7>", "nope_action")

    assert keymap.handle_key(ctx, parse_key("<f7>")) is True
    assert editor.messages[-1] == "unknown action: nope_action"
    assert editor.buffer.get_text() == "abc"


def test_binding_to_a_registered_action_is_dispatched() -> None:
    """The same function-key path still runs a registered action."""
    editor, keymap, ctx = _setup("abc")
    calls: list[str] = []
    editor.actions.register("f7_run", lambda _ctx: calls.append("ran"), "ext")
    keymap.add_binding("<f7>", "f7_run")

    assert keymap.handle_key(ctx, parse_key("<f7>")) is True
    assert calls == ["ran"]


def test_add_binding_twice_for_a_key_keeps_one_list_entry() -> None:
    """Re-registering a key replaces its binding instead of duplicating it.

    The stale list entry must go with the overwritten index one, otherwise
    the help overlay (which walks ``bindings``) shows the key twice.
    """
    editor, keymap, ctx = _setup("abc")
    calls: list[str] = []
    editor.actions.register("ext_first", lambda _ctx: calls.append("first"), "ext")
    editor.actions.register("ext_second", lambda _ctx: calls.append("second"), "ext")

    keymap.add_binding("q", "ext_first")
    keymap.add_binding("q", "ext_second")

    entries = [b for b in keymap.bindings if b.key == "q"]
    assert len(entries) == 1
    assert entries[0].action == "ext_second"
    assert keymap.lookup("q") is entries[0]

    assert keymap.handle_key(ctx, "q") is True
    assert calls == ["second"]


def test_add_binding_over_a_built_in_key_keeps_one_list_entry() -> None:
    """Overriding a built-in key drops the stale table entry, not just the index."""
    keymap = VimKeymap()
    keymap.add_binding("w", "ext_run")

    entries = [b for b in keymap.bindings if b.key == "w"]
    assert len(entries) == 1
    assert entries[0].category == "extension"
    assert keymap.lookup("w") is entries[0]


def test_word_end_motion_wraps_to_the_next_line() -> None:
    """e past a line's last word lands on the next line's word end."""
    editor, keymap, ctx = _setup("ab\ncd")
    _press(keymap, ctx, "$")
    _press(keymap, ctx, "e")
    assert editor.buffer.cursor == (1, 1)

    editor, keymap, ctx = _setup("ab\n\ncd")
    _press(keymap, ctx, "$")
    _press(keymap, ctx, "e")
    assert editor.buffer.cursor == (2, 1)  # blank lines are skipped


def test_word_end_motion_lands_on_the_last_char() -> None:
    """e stops on the word's final char and stays put with no next word."""
    editor, keymap, ctx = _setup("foo bar baz")
    _press(keymap, ctx, "e")
    assert editor.buffer.col == 2
    _press(keymap, ctx, "e")
    assert editor.buffer.col == 6
    _press(keymap, ctx, "e")
    assert editor.buffer.col == 10
    _press(keymap, ctx, "e")
    assert editor.buffer.col == 10  # document end: no landing, no move

    editor.buffer.set_cursor((0, 3))
    _press(keymap, ctx, "e")
    assert editor.buffer.col == 6  # from a delimiter: next word's end

    editor.buffer.set_cursor((0, 0))
    _press(keymap, ctx, "2", "e")
    assert editor.buffer.col == 6  # counts repeat the landing


def test_word_end_motion_treats_punctuation_as_a_word() -> None:
    """e lands on the last char of word and punctuation runs alike."""
    editor, keymap, ctx = _setup("ab! cd")
    _press(keymap, ctx, "e")
    assert editor.buffer.col == 1
    _press(keymap, ctx, "e")
    assert editor.buffer.col == 2
    _press(keymap, ctx, "e")
    assert editor.buffer.col == 5


def test_delete_over_e_from_the_word_end_takes_the_next_word() -> None:
    """de on a word's last char deletes through the next word's end."""
    editor, keymap, ctx = _setup("ab cd")
    editor.buffer.set_cursor((0, 1))
    _press(keymap, ctx, "d", "e")
    assert editor.buffer.get_text() == "a"


def test_cw_on_the_last_char_changes_only_that_char() -> None:
    """vim's cw special case is one char when the cursor ends the word."""
    editor, keymap, ctx = _setup("foo bar")
    editor.buffer.set_cursor((0, 6))
    _press(keymap, ctx, "c", "w", "X", ESC)
    assert editor.buffer.get_text() == "foo baX"


def test_operator_with_the_g_motion_deletes_nothing() -> None:
    """dg has no motion behind it, so the operator is dropped."""
    editor, keymap, ctx = _setup("abc")
    _press(keymap, ctx, "d", "g")
    assert editor.buffer.get_text() == "abc"
    # the anchor is left where the cursor is, which is "no selection"
    assert editor.buffer.has_selection() is False


def test_visual_delete_of_a_collapsed_selection() -> None:
    """v then x with no motion deletes nothing and keeps the register."""
    editor, keymap, ctx = _setup("abc")
    editor.buffer.register = "keep"
    _press(keymap, ctx, "v", "x")
    assert editor.buffer.get_text() == "abc"
    assert editor.buffer.register == "keep"
    assert editor.messages[-1] == "deleted selection"
    assert keymap.mode is VimMode.NORMAL


def test_visual_arrow_motion_extends_the_selection() -> None:
    """Arrows work in visual mode like their letter equivalents."""
    editor, keymap, ctx = _setup("ab\ncd")
    _press(keymap, ctx, "v", "\x1b[B")
    assert editor.buffer.cursor == (1, 0)
    assert editor.buffer.has_selection() is True


def test_visual_gg_presses_change_nothing() -> None:
    """g has no jump semantics in visual mode: gg moves nothing.

    The keys stay consumed, the collapsed selection survives and the mode
    is unchanged.
    """
    editor, keymap, ctx = _setup("ab\ncd")
    _press(keymap, ctx, "v", "g", "g")
    assert editor.buffer.cursor == (0, 0)
    assert editor.buffer.has_selection() is False
    assert keymap.mode is VimMode.VISUAL


def test_visual_line_toggle_on_an_empty_line() -> None:
    """V on an empty line leaves a collapsed selection and still works."""
    editor, keymap, ctx = _setup("")
    _press(keymap, ctx, "V")
    assert keymap.mode is VimMode.VISUAL_LINE
    assert editor.buffer.anchor == (0, 0)
    assert editor.buffer.cursor == (0, 0)

    _press(keymap, ctx, "V")
    assert keymap.mode is VimMode.VISUAL
    assert editor.buffer.has_selection() is False


# --- counted operators and the change operator -------------------------------


def test_counted_dd_deletes_n_lines() -> None:
    """3dd removes three lines into the register."""
    editor, keymap, ctx = _setup("one\ntwo\nthree\nfour")
    _press(keymap, ctx, "3", "d", "d")
    assert editor.buffer.lines == ["four"]
    assert editor.buffer.register == "one\ntwo\nthree\n"


def test_counted_yy_yanks_n_lines_and_keeps_the_cursor() -> None:
    """2yy yanks two lines; the cursor stays put like vim."""
    editor, keymap, ctx = _setup("one\ntwo\nthree")
    editor.buffer.set_cursor((0, 1))
    _press(keymap, ctx, "2", "y", "y")
    assert editor.buffer.register == "one\ntwo\n"
    assert editor.buffer.cursor == (0, 1)
    assert editor.buffer.has_selection() is False


def test_operator_count_multiplies_the_motion_count() -> None:
    """2d3w covers six words: operator and motion counts multiply."""
    editor, keymap, ctx = _setup("one two three four five six seven")
    _press(keymap, ctx, "2", "d", "3", "w")
    assert editor.buffer.get_text() == "seven"


def test_d5G_deletes_through_the_first_char_of_line_five() -> None:
    """d5G is charwise inclusive of the target line's first character."""
    editor, keymap, ctx = _setup("l1\nl2\nl3\nl4\nl5\nl6")
    editor.buffer.set_cursor((2, 1))
    _press(keymap, ctx, "d", "5", "G")
    assert editor.buffer.lines == ["l1", "l2", "l5", "l6"]


def test_5dG_also_targets_line_five() -> None:
    """A count before the operator reaches the G motion too."""
    editor, keymap, ctx = _setup("l1\nl2\nl3\nl4\nl5\nl6")
    _press(keymap, ctx, "5", "d", "G")
    assert editor.buffer.lines == ["5", "l6"]


def test_dgg_deletes_the_lines_up_to_the_first_one() -> None:
    """dgg removes the lines from the top through the cursor line."""
    editor, keymap, ctx = _setup("l1\nl2\nl3")
    editor.buffer.set_cursor((2, 0))
    _press(keymap, ctx, "d", "g", "g")
    assert editor.buffer.get_text() == ""
    assert editor.buffer.register == "l1\nl2\nl3\n"


def test_cw_changes_the_word_without_trailing_space() -> None:
    """cw on a word is ce: the trailing space survives."""
    editor, keymap, ctx = _setup("foo bar")
    _press(keymap, ctx, "c", "w", "X", ESC)
    assert editor.buffer.get_text() == "X bar"
    assert keymap.mode is VimMode.NORMAL


def test_cw_on_whitespace_deletes_to_the_next_word() -> None:
    """cw on whitespace behaves like dw."""
    editor, keymap, ctx = _setup("a   b")
    editor.buffer.set_cursor((0, 1))
    _press(keymap, ctx, "c", "w", "X", ESC)
    assert editor.buffer.get_text() == "aXb"


def test_cc_clears_the_line_and_enters_insert() -> None:
    """cc empties the current line for typing."""
    editor, keymap, ctx = _setup("hello")
    _press(keymap, ctx, "c", "c", "X", ESC)
    assert editor.buffer.lines == ["X"]


def test_counted_cc_clears_n_lines_into_one_empty_line() -> None:
    """3cc collapses three lines into a single empty one."""
    editor, keymap, ctx = _setup("aa\nbb\nccc")
    _press(keymap, ctx, "3", "c", "c", "X", ESC)
    assert editor.buffer.lines == ["X"]


def test_c_dollar_changes_to_the_line_end() -> None:
    """c$ clears the rest of the line and inserts."""
    editor, keymap, ctx = _setup("hello world")
    editor.buffer.set_cursor((0, 5))
    _press(keymap, ctx, "c", "$", "X", ESC)
    assert editor.buffer.get_text() == "helloX"


# --- find-char motions (f/F/t/T/;/,) -----------------------------------------


def test_find_char_moves_to_the_next_occurrence() -> None:
    """fx lands on the next x; the cursor char itself is never a match."""
    editor, keymap, ctx = _setup("a b c ab")
    _press(keymap, ctx, "f", "b")
    assert editor.buffer.cursor == (0, 2)


def test_counted_find_char_skips_occurrences() -> None:
    """2fx jumps to the second occurrence."""
    editor, keymap, ctx = _setup("a b c ab")
    _press(keymap, ctx, "2", "f", "b")
    assert editor.buffer.cursor == (0, 7)


def test_find_char_backward_and_till_variants() -> None:
    """F/T/t mirror the forward find with vim's landing rules."""
    editor, keymap, ctx = _setup("abcde cde")
    editor.buffer.set_cursor((0, 8))
    _press(keymap, ctx, "F", "c")
    assert editor.buffer.cursor == (0, 6)

    editor, keymap, ctx = _setup("abcde cde")
    editor.buffer.set_cursor((0, 8))
    _press(keymap, ctx, "T", "c")
    assert editor.buffer.cursor == (0, 7)

    editor, keymap, ctx = _setup("a cde")
    _press(keymap, ctx, "t", "c")
    assert editor.buffer.cursor == (0, 1)


def test_find_char_accepts_digit_characters() -> None:
    """A digit after an armed find prefix is the target char, not a count."""
    editor, keymap, ctx = _setup("a3b3c3")
    _press(keymap, ctx, "f", "3")
    assert editor.buffer.cursor == (0, 1)
    _press(keymap, ctx, "f", "3")
    assert editor.buffer.cursor == (0, 3)
    _press(keymap, ctx, "F", "3")
    assert editor.buffer.cursor == (0, 1)
    _press(keymap, ctx, "2", "f", "3")  # counted find still works
    assert editor.buffer.cursor == (0, 5)


# --- visual-mode drop (mouse-click exit, IKJRFK wave-2) ----------------------


def test_drop_visual_from_visual_returns_to_normal() -> None:
    """drop_visual leaves characterwise visual mode back to NORMAL."""
    _, keymap, ctx = _setup("abc")
    _press(keymap, ctx, "v")
    assert keymap.mode is VimMode.VISUAL

    keymap.drop_visual()
    assert keymap.mode is VimMode.NORMAL


def test_drop_visual_from_visual_line_returns_to_normal() -> None:
    """drop_visual leaves linewise visual mode back to NORMAL."""
    _, keymap, ctx = _setup("abc")
    _press(keymap, ctx, "V")
    assert keymap.mode is VimMode.VISUAL_LINE

    keymap.drop_visual()
    assert keymap.mode is VimMode.NORMAL


def test_drop_visual_from_normal_is_noop() -> None:
    """drop_visual in NORMAL mode keeps the mode unchanged."""
    _, keymap, _ = _setup("abc")
    assert keymap.mode is VimMode.NORMAL

    keymap.drop_visual()
    assert keymap.mode is VimMode.NORMAL


def test_drop_visual_from_insert_is_noop() -> None:
    """A mouse click must not kick the editor out of insert mode."""
    _, keymap, ctx = _setup("abc")
    _press(keymap, ctx, "i")
    assert keymap.mode is VimMode.INSERT

    keymap.drop_visual()
    assert keymap.mode is VimMode.INSERT


def test_failed_find_leaves_the_buffer_untouched_and_reports() -> None:
    """A miss moves nothing, says so, and the keymap keeps working."""
    editor, keymap, ctx = _setup("abc")
    _press(keymap, ctx, "f", "z")
    assert editor.buffer.get_text() == "abc"
    assert editor.buffer.cursor == (0, 0)
    assert editor.messages[-1] == "not found"
    _press(keymap, ctx, "l")
    assert editor.buffer.cursor == (0, 1)


def test_find_char_does_not_cross_lines() -> None:
    """f searches the cursor row only, even from a matching cursor char."""
    editor, keymap, ctx = _setup("ax\nbxa")
    _press(keymap, ctx, "f", "a")
    assert editor.buffer.cursor == (0, 0)
    assert editor.messages[-1] == "not found"


def test_semicolon_repeats_and_comma_flips_the_last_find() -> None:
    """; keeps the recorded direction, , flips it -- the record survives ,"""
    editor, keymap, ctx = _setup("a.b.c.d")
    _press(keymap, ctx, "f", ".")
    assert editor.buffer.cursor == (0, 1)
    _press(keymap, ctx, ";")
    assert editor.buffer.cursor == (0, 3)
    _press(keymap, ctx, ",")
    assert editor.buffer.cursor == (0, 1)
    _press(keymap, ctx, ";")
    assert editor.buffer.cursor == (0, 3)


def test_df_deletes_through_the_found_char() -> None:
    """dfx is inclusive of x on the forward side."""
    editor, keymap, ctx = _setup("hello world")
    _press(keymap, ctx, "d", "f", "w")
    assert editor.buffer.get_text() == "orld"


def test_counted_operator_find_uses_the_multiplied_count() -> None:
    """2df- deletes through the second dash (operator x motion counts)."""
    editor, keymap, ctx = _setup("a-b-c-d")
    _press(keymap, ctx, "2", "d", "f", "-")
    assert editor.buffer.get_text() == "c-d"


def test_dF_deletes_backward_including_both_ends() -> None:
    """dFx spans from the found char through the cursor char."""
    editor, keymap, ctx = _setup("hello world")
    editor.buffer.set_cursor((0, 10))
    _press(keymap, ctx, "d", "F", "o")
    assert editor.buffer.get_text() == "hello w"


def test_dF_from_the_line_end_clamps_the_span() -> None:
    """A cursor parked on the EOL column must not overshoot the line."""
    editor, keymap, ctx = _setup("abxba")
    editor.buffer.set_cursor((0, 5))
    _press(keymap, ctx, "d", "F", "x")
    assert editor.buffer.get_text() == "ab"


def test_dt_and_dT_stop_short_of_the_char() -> None:
    """till variants exclude the found char from the operator span."""
    editor, keymap, ctx = _setup("func(x)")
    editor.buffer.set_cursor((0, 1))
    _press(keymap, ctx, "d", "t", "(")
    assert editor.buffer.get_text() == "f(x)"

    editor, keymap, ctx = _setup("func(xy)")
    editor.buffer.set_cursor((0, 6))
    _press(keymap, ctx, "d", "T", "(")
    assert editor.buffer.get_text() == "func()"


def test_cf_changes_through_the_found_char() -> None:
    """cf) deletes through ) and inserts in its place."""
    editor, keymap, ctx = _setup("x = f(y);")
    editor.buffer.set_cursor((0, 4))
    _press(keymap, ctx, "c", "f", ")")
    assert keymap.mode is VimMode.INSERT
    _press(keymap, ctx, "4", "2", ESC)
    assert editor.buffer.get_text() == "x = 42;"


def test_yf_yanks_through_the_found_char() -> None:
    """yfx keeps the text and puts the span into the register."""
    editor, keymap, ctx = _setup("key: value")
    _press(keymap, ctx, "y", "f", ":")
    assert editor.buffer.get_text() == "key: value"
    _press(keymap, ctx, "P")
    assert editor.buffer.get_text() == "key:key: value"


def test_failed_operator_find_deletes_nothing() -> None:
    """dfz with no z drops the operator and keeps the buffer."""
    editor, keymap, ctx = _setup("abc")
    _press(keymap, ctx, "d", "f", "z")
    assert editor.buffer.get_text() == "abc"
    assert editor.messages[-1] == "not found"
    # the dropped operator does not swallow the next command
    _press(keymap, ctx, "x")
    assert editor.buffer.get_text() == "bc"


def test_operator_semicolon_deletes_through_the_repeated_find() -> None:
    """d; combines the operator with the recorded find."""
    editor, keymap, ctx = _setup("a.b.c")
    _press(keymap, ctx, "f", ".")
    _press(keymap, ctx, "d", ";")
    assert editor.buffer.get_text() == "ac"


# --- text objects ------------------------------------------------------------


def test_ciw_changes_the_inner_word() -> None:
    """ciw replaces the word under the cursor."""
    editor, keymap, ctx = _setup("foo bar")
    editor.buffer.set_cursor((0, 1))
    _press(keymap, ctx, "c", "i", "w", "X", ESC)
    assert editor.buffer.get_text() == "X bar"


def test_daw_deletes_the_word_and_trailing_space() -> None:
    """daw takes the following whitespace with the word."""
    editor, keymap, ctx = _setup("foo bar")
    _press(keymap, ctx, "d", "a", "w")
    assert editor.buffer.get_text() == "bar"


def test_counted_iw_extends_over_following_words() -> None:
    """3diw covers three words without the trailing space."""
    editor, keymap, ctx = _setup("one two three four")
    _press(keymap, ctx, "3", "d", "i", "w")
    assert editor.buffer.get_text() == " four"


def test_di_paren_deletes_the_inner_block() -> None:
    """di( empties the parens and keeps them."""
    editor, keymap, ctx = _setup("f(a, b)g")
    editor.buffer.set_cursor((0, 3))
    _press(keymap, ctx, "d", "i", "(")
    assert editor.buffer.get_text() == "f()g"


def test_di_brace_spans_lines() -> None:
    """di{ removes an inner block across newlines."""
    editor, keymap, ctx = _setup("a {\n  b\n}c")
    editor.buffer.set_cursor((1, 2))
    _press(keymap, ctx, "d", "i", "{")
    assert editor.buffer.get_text() == "a {}c"


def test_ca_quote_changes_including_the_quotes() -> None:
    """ca\" replaces the quoted text together with the quotes."""
    editor, keymap, ctx = _setup('say "hi"!')
    editor.buffer.set_cursor((0, 6))
    _press(keymap, ctx, "c", "a", '"', "X", ESC)
    assert editor.buffer.get_text() == "say X!"


def test_cit_changes_the_inner_tag_text() -> None:
    """cit replaces the text between the tags."""
    editor, keymap, ctx = _setup("<p>hello</p>")
    editor.buffer.set_cursor((0, 4))
    _press(keymap, ctx, "c", "i", "t", "X", ESC)
    assert editor.buffer.get_text() == "<p>X</p>"


def test_cat_changes_the_whole_tag() -> None:
    """cat replaces the entire tag block."""
    editor, keymap, ctx = _setup("<p>hi</p> tail")
    _press(keymap, ctx, "c", "a", "t", "X", ESC)
    assert editor.buffer.get_text() == "X tail"


def test_unknown_text_object_drops_the_operator() -> None:
    """diq is a miss: nothing happens and the next key works normally."""
    editor, keymap, ctx = _setup("abc")
    _press(keymap, ctx, "d", "i", "q")
    assert editor.buffer.get_text() == "abc"
    _press(keymap, ctx, "x")
    assert editor.buffer.get_text() == "bc"


def test_unbalanced_pair_drops_the_operator_with_a_message() -> None:
    """di( without a closing paren reports the miss."""
    editor, keymap, ctx = _setup("abc (def")
    editor.buffer.set_cursor((0, 6))
    _press(keymap, ctx, "d", "i", "(")
    assert editor.buffer.get_text() == "abc (def"
    assert editor.messages[-1] == "no text object"


# --- replace and insert-entry fixes ------------------------------------------


def test_r_replaces_the_char_under_the_cursor() -> None:
    """rx swaps one char and leaves the cursor on it."""
    editor, keymap, ctx = _setup("abc")
    editor.buffer.set_cursor((0, 1))
    _press(keymap, ctx, "r", "X")
    assert editor.buffer.get_text() == "aXc"
    assert editor.buffer.cursor == (0, 1)
    assert keymap.mode is VimMode.NORMAL


def test_counted_r_replaces_n_chars() -> None:
    """3rx swaps three chars; the cursor ends on the last one."""
    editor, keymap, ctx = _setup("abcdef")
    editor.buffer.set_cursor((0, 1))
    _press(keymap, ctx, "3", "r", "X")
    assert editor.buffer.get_text() == "aXXXef"
    assert editor.buffer.cursor == (0, 3)


def test_replace_accepts_digit_characters() -> None:
    """r5 swaps the char for a literal 5; the count form still works."""
    editor, keymap, ctx = _setup("abc")
    _press(keymap, ctx, "r", "5")
    assert editor.buffer.get_text() == "5bc"

    editor, keymap, ctx = _setup("abcdef")
    _press(keymap, ctx, "2", "r", "5")
    assert editor.buffer.get_text() == "55cdef"


def test_r_beyond_the_line_end_reports_and_keeps_the_text() -> None:
    """vim refuses a replace running past the end of the line."""
    editor, keymap, ctx = _setup("abc")
    editor.buffer.set_cursor((0, 2))
    _press(keymap, ctx, "2", "r", "X")
    assert editor.buffer.get_text() == "abc"
    assert editor.messages[-1] == "nothing to replace"


def test_r_with_a_non_printable_follower_is_dropped() -> None:
    """r esc cancels the replace and esc still clears pending state."""
    editor, keymap, ctx = _setup("abc")
    _press(keymap, ctx, "r", ESC, "x")
    assert editor.buffer.get_text() == "bc"


def test_operator_is_cancelled_by_r() -> None:
    """drx cancels d and replaces one char, like vim."""
    editor, keymap, ctx = _setup("abc")
    _press(keymap, ctx, "d", "r", "X")
    assert editor.buffer.get_text() == "Xbc"
    assert keymap.mode is VimMode.NORMAL


def test_append_at_the_end_of_a_line_stays_on_the_line() -> None:
    """a never spills onto the next line, even from the EOL column."""
    editor, keymap, ctx = _setup("ab\ncd")
    editor.buffer.set_cursor((0, 1))
    _press(keymap, ctx, "a", "X", ESC)
    assert editor.buffer.get_text() == "abX\ncd"

    editor, keymap, ctx = _setup("ab\ncd")
    editor.buffer.set_cursor((0, 2))  # the EOL column
    _press(keymap, ctx, "a", "X", ESC)
    assert editor.buffer.get_text() == "abX\ncd"


def test_visual_line_yank_lands_on_the_first_row() -> None:
    """Vy leaves the cursor on the first column of the first yanked row."""
    editor, keymap, ctx = _setup("one\ntwo\nthree")
    editor.buffer.set_cursor((1, 0))
    _press(keymap, ctx, "V", "j", "y")
    assert editor.buffer.register == "two\nthree\n"
    assert editor.buffer.cursor == (1, 0)
    assert editor.buffer.has_selection() is False
    assert keymap.mode is VimMode.NORMAL


# --- registers and system clipboard sync -------------------------------------


class _FakeClip:
    """Recording stand-in replacing the clipboard entries in the keymap."""

    def __init__(self) -> None:
        self.copies: list[str] = []
        self.pastes: list[int] = []
        self.paste_result: str | None = None
        self.copy_result: bool = True

    def copy_text(self, text: str) -> bool:
        self.copies.append(text)
        return self.copy_result

    def paste_text(self) -> str | None:
        self.pastes.append(1)
        return self.paste_result


@pytest.fixture()
def fake_clip(monkeypatch: pytest.MonkeyPatch) -> _FakeClip:
    """Patch the clipboard entries imported into the vim keymap module."""
    fake = _FakeClip()
    monkeypatch.setattr(vim_module, "copy_text", fake.copy_text)
    monkeypatch.setattr(vim_module, "paste_text", fake.paste_text)
    return fake


def test_linewise_yy_mirrors_unnamed_to_clipboard(fake_clip: _FakeClip) -> None:
    """yy writes the unnamed register and mirrors it to the system clipboard."""
    editor, keymap, ctx = _setup("alpha\nbeta")
    _press(keymap, ctx, "y", "y")
    assert editor.buffer.register == "alpha\n"
    assert fake_clip.copies == ["alpha\n"]


def test_delete_dd_mirrors_unnamed_to_clipboard(fake_clip: _FakeClip) -> None:
    """dd mirrors the deleted line to the system clipboard."""
    editor, keymap, ctx = _setup("alpha\nbeta")
    _press(keymap, ctx, "d", "d")
    assert editor.buffer.get_text() == "beta"
    assert fake_clip.copies == ["alpha\n"]


def test_charwise_yank_mirrors_to_clipboard(fake_clip: _FakeClip) -> None:
    """yw yanks the motion span into the unnamed register and mirrors it."""
    _editor, keymap, ctx = _setup("hello")
    _press(keymap, ctx, "y", "w")
    assert fake_clip.copies == ["hello"]


def test_paste_prefers_clipboard_and_reads_once_for_count(fake_clip: _FakeClip) -> None:
    """3p pastes the system clipboard text three times, reading it once."""
    editor, keymap, ctx = _setup("")
    editor.buffer.register = "OLD"
    fake_clip.paste_result = "SYS"
    _press(keymap, ctx, "3", "p")
    assert editor.buffer.get_text() == "SYSSYSSYS"
    assert len(fake_clip.pastes) == 1


def test_paste_falls_back_to_unnamed_when_clipboard_unavailable(
    fake_clip: _FakeClip,
) -> None:
    """A failed clipboard read (None) leaves the unnamed register intact."""
    editor, keymap, ctx = _setup("hello")
    fake_clip.paste_result = None
    _press(keymap, ctx, "y", "y", "p")
    assert editor.buffer.get_text() == "hello\nhello"


def test_paste_falls_back_when_clipboard_empty(fake_clip: _FakeClip) -> None:
    """An empty clipboard ("") counts as no text: the unnamed register wins."""
    editor, keymap, ctx = _setup("hello")
    fake_clip.paste_result = ""
    _press(keymap, ctx, "y", "y", "p")
    assert editor.buffer.get_text() == "hello\nhello"


def test_paste_on_a_read_only_buffer_does_not_prime_the_register(
    fake_clip: _FakeClip,
) -> None:
    """p on a read-only buffer fails without touching the unnamed register."""
    editor, keymap, ctx = _setup("hello")
    editor.buffer.register = "KEEP"
    editor.buffer.read_only = True
    fake_clip.paste_result = "SYS"

    with pytest.raises(BufferReadOnlyError):
        keymap.handle_key(ctx, "p")
    assert editor.buffer.register == "KEEP"
    assert fake_clip.pastes == []


def test_named_register_yy_stores_internally_without_clipboard(
    fake_clip: _FakeClip,
) -> None:
    """"ayy fills register a only: no unnamed write, no clipboard mirror."""
    editor, keymap, ctx = _setup("alpha")
    _press(keymap, ctx, '"', "a", "y", "y")
    assert editor.buffer.named_registers["a"] == "alpha\n"
    assert fake_clip.copies == []
    assert editor.buffer.register == ""


def test_named_register_paste_reads_internal_only(fake_clip: _FakeClip) -> None:
    """"ap pastes register a without touching the system clipboard."""
    editor, keymap, ctx = _setup("alpha")
    _press(keymap, ctx, '"', "a", "y", "y", '"', "a", "p")
    assert editor.buffer.get_text() == "alpha\nalpha"
    assert len(fake_clip.pastes) == 0


def test_register_prefix_does_not_survive_an_insert_roundtrip(
    fake_clip: _FakeClip,
) -> None:
    """"ai then ESC discards the pending register: the next yy yanks unnamed."""
    editor, keymap, ctx = _setup("alpha")
    _press(keymap, ctx, '"', "a", "i", ESC, "y", "y")
    assert keymap.pending_register is None
    assert editor.buffer.register == "alpha\n"
    assert editor.buffer.named_registers == {}
    assert fake_clip.copies == ["alpha\n"]


def test_register_prefix_does_not_survive_an_unrelated_command(
    fake_clip: _FakeClip,
) -> None:
    """"ax drops the pending register: the next yy yanks to unnamed."""
    editor, keymap, ctx = _setup("alpha\nbeta")
    _press(keymap, ctx, '"', "a", "x", "y", "y")
    assert editor.buffer.register == "lpha\n"
    assert editor.buffer.named_registers == {}
    assert fake_clip.copies == ["lpha\n"]


def test_yy_survives_unavailable_clipboard_backend(fake_clip: _FakeClip) -> None:
    """An unavailable backend must not break the yank key path."""
    fake_clip.copy_result = False
    editor, keymap, ctx = _setup("alpha\nbeta")
    _press(keymap, ctx, "y", "y")
    assert editor.buffer.register == "alpha\n"


def test_visual_delete_with_empty_result_never_touches_clipboard(
    fake_clip: _FakeClip,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An empty delete result updates the unnamed register, not the clipboard."""
    editor, keymap, ctx = _setup("alpha")
    monkeypatch.setattr(editor.buffer, "delete_selection", lambda: "")
    _press(keymap, ctx, "v", "d")
    assert editor.buffer.register == ""
    assert fake_clip.copies == []


def test_bare_quote_with_invalid_follower_is_swallowed(fake_clip: _FakeClip) -> None:
    """A non a-z follower of " is dropped silently and clears the pending."""
    editor, keymap, ctx = _setup("abc")
    _press(keymap, ctx, '"', "5")
    assert keymap.pending_register is None
    assert keymap.count_str == ""
    assert editor.buffer.get_text() == "abc"


def test_quote_then_motion_keeps_register_for_next_operator(
    fake_clip: _FakeClip,
) -> None:
    """"a survives a motion key and applies to the next yank operator."""
    editor, keymap, ctx = _setup("one two")
    _press(keymap, ctx, '"', "a", "w", "y", "w")
    assert editor.buffer.named_registers["a"] == "two"
    assert fake_clip.copies == []


def test_visual_quote_ay_yanks_to_named_register(fake_clip: _FakeClip) -> None:
    """v"a y fills register a from the selection without mirroring."""
    editor, keymap, ctx = _setup("alpha\nbeta")
    _press(keymap, ctx, "v", '"', "a", "y")
    assert editor.buffer.named_registers["a"] == "alpha"
    assert fake_clip.copies == []


def test_linewise_cc_writes_register_and_mirrors(fake_clip: _FakeClip) -> None:
    """cc stores the cleared line in the unnamed register and mirrors it.

    cc clears via ``delete_selection`` (charwise), so the stored text is
    the line content without the trailing newline.
    """
    editor, keymap, ctx = _setup("alpha\nbeta")
    _press(keymap, ctx, "c", "c", "N", "E", "W", ESC)
    assert editor.buffer.get_text() == "NEW\nbeta"
    assert editor.buffer.register == "alpha"
    assert fake_clip.copies == ["alpha"]


def test_operator_register_prefix_yiw_paths(fake_clip: _FakeClip) -> None:
    """"adw deletes into register a without mirroring to the clipboard."""
    editor, keymap, ctx = _setup("alpha beta")
    _press(keymap, ctx, '"', "a", "d", "w")
    assert editor.buffer.get_text() == "beta"
    assert editor.buffer.named_registers["a"] == "alpha "
    assert fake_clip.copies == []


def test_visual_quote_with_invalid_follower_is_swallowed(
    fake_clip: _FakeClip,
) -> None:
    """A non a-z follower of " in visual mode drops the pending silently."""
    editor, keymap, ctx = _setup("alpha\nbeta")
    _press(keymap, ctx, "v", '"', "5")
    assert keymap.pending_register is None
    assert editor.buffer.get_text() == "alpha\nbeta"
    assert fake_clip.copies == []


def test_visual_quote_then_v_names_the_register() -> None:
    """In visual mode `"v` names register v instead of leaving visual.

    The register wait sits in front of the v/V mode switches (mirroring
    normal mode, 2026-10-03 review R-61): previously `"v` toggled the mode
    and dropped the selection, so the selection could never be yanked into
    a named register in visual mode.
    """
    editor, keymap, ctx = _setup("alpha")
    _press(keymap, ctx, "v", '"', "v", "y")
    assert keymap.mode is VimMode.NORMAL
    assert editor.buffer.named_registers["v"] == "alpha"
    # the next key must run as a fresh command, not be swallowed by the wait
    _press(keymap, ctx, "x")
    assert editor.buffer.get_text() == "lpha"


def test_d2dd_multiplies_counts_and_does_not_leak_the_count() -> None:
    """``d2dd`` deletes two lines and leaves no count on the next key.

    The linewise op used to drop the motion count (deleting one line) and
    to leak ``count_str``, so a following ``x`` deleted two characters
    (2026-10-03 review R-57).
    """
    editor, keymap, ctx = _setup("alpha\nbeta\ngamma\ndelta")
    _press(keymap, ctx, "d", "2", "d")
    assert editor.buffer.get_text() == "gamma\ndelta"
    _press(keymap, ctx, "x")
    assert editor.buffer.get_text() == "amma\ndelta"


def test_delete_dd_into_named_register_stays_internal(
    fake_clip: _FakeClip,
) -> None:
    """"add deletes the line into register a: no unnamed write, no mirror."""
    editor, keymap, ctx = _setup("alpha\nbeta")
    _press(keymap, ctx, '"', "a", "d", "d")
    assert editor.buffer.get_text() == "beta"
    assert editor.buffer.named_registers["a"] == "alpha\n"
    assert fake_clip.copies == []


def test_change_gg_into_named_register_stays_internal(
    fake_clip: _FakeClip,
) -> None:
    """"acgg clears the span into register a without touching the clipboard.

    Behaviour-fix anchor: the c branch of the gg resolution writes the
    deleted span into the register (same as cc) instead of dropping it.
    """
    editor, keymap, ctx = _setup("alpha\nbeta")
    _press(keymap, ctx, '"', "a", "c", "g", "g", "N", "E", "W", ESC)
    assert editor.buffer.get_text() == "NEW\nbeta"
    assert editor.buffer.named_registers["a"] == "alpha"
    assert fake_clip.copies == []
