"""Headless tests for the vim keymap: modes, counts, operators, visual mode.

The keymap is driven through :meth:`VimKeymap.handle_key` with a real
:class:`EditorSession`, the real built-in action table (so editing actions do
what the editor does) and a recording stand-in for the few editor-level entry
points the table calls.
"""

from __future__ import annotations

from typing import Any, cast

from yate.actions import populate
from yate.config import YateConfig
from yate.editor_core import Document, TextBuffer
from yate.keymaps.base import ActionContext, KeyUi, parse_key
from yate.keymaps.vim import VimKeymap, VimMode
from yate.registries import ActionRegistry
from yate.session import EditorSession

ESC = "\x1b"
CTRL_R = "\x12"
CTRL_G = "\x07"
CTRL_D = "\x04"
CTRL_U = "\x15"
CTRL_F = "\x06"
CTRL_B = "\x02"
CTRL_W = "\x17"
CTRL_SLASH = "\x1f"
DEL = "\x1b[3~"


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
        populate(self.actions, cast(Any, self))

    # ---------------------------------------------------------- state access
    @property
    def doc(self) -> Document:
        return self.session.doc

    @property
    def buffer(self) -> TextBuffer:
        return self.session.buffer

    def context(self) -> ActionContext:
        return ActionContext(self.session, self.ui)

    # ------------------------------------------------------- UI entry points
    def execute_action(self, name: str) -> bool:
        return self.actions.execute(name, self.context())

    def message(self, text: str) -> None:
        self.messages.append(text)

    def command_prompt(self) -> None:
        self.prompts.append(("command", True))

    def find_prompt(self, forward: bool) -> None:
        self.prompts.append(("find", forward))

    def goto_prompt(self) -> None:
        self.prompts.append(("goto", True))

    def toggle_keymap(self) -> None:
        self.prompts.append(("toggle", True))

    # ------------------------------------------------- editor-side entry points
    def page(self, direction: int, half: bool = False) -> None:
        self.pages.append((direction, half))

    def find_next(self, forward: bool) -> None:
        self.prompts.append(("next", forward))

    def replace_prompt(self) -> None:
        self.prompts.append(("replace", True))

    def show_manual(self) -> None:
        self.prompts.append(("manual", True))

    def shell_prompt(self) -> None:
        self.prompts.append(("shell", True))

    def show_help(self) -> None:
        self.help_shown += 1

    def save_document(self) -> None:
        self.prompts.append(("save", True))

    def prompt_open(self) -> None:
        self.prompts.append(("open", True))

    def new_buffer(self) -> None:
        self.prompts.append(("new", True))

    def close_tab(self) -> None:
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
    assert editor.buffer.col == 7
    _press(keymap, ctx, "0", "2", "w")
    assert editor.buffer.col == 8


def test_zero_always_lands_on_column_zero() -> None:
    """Unlike the vsc binding, vim's 0 ignores the indent."""
    editor, keymap, ctx = _setup("    indented")
    editor.buffer.set_cursor((0, 8))
    _press(keymap, ctx, "0")
    assert editor.buffer.cursor == (0, 0)


def test_dollar_moves_to_the_line_end() -> None:
    """$ goes past the last character."""
    editor, keymap, ctx = _setup("abc\nde")
    _press(keymap, ctx, "$")
    assert editor.buffer.cursor == (0, 3)
    _press(keymap, ctx, "j", "$")
    assert editor.buffer.cursor == (1, 2)


def test_gg_and_upper_g_jump_to_the_document_edges() -> None:
    """gg is the start, G the end; a count makes both a line jump."""
    editor, keymap, ctx = _setup("l1\nl2\nl3")
    _press(keymap, ctx, "G")
    assert editor.buffer.cursor == (2, 2)
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
    """An operator without a motion deletes nothing."""
    editor, keymap, ctx = _setup("aaa")
    _press(keymap, ctx, "d", "z")
    assert editor.buffer.get_text() == "aaa"
    _press(keymap, ctx, "x")
    assert editor.buffer.get_text() == "aa"


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
    assert editor.buffer.col == 3  # the motion ran instead


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


def test_binding_to_an_unknown_action_is_not_swallowed() -> None:
    """A binding that names an unregistered action drops the key, and says so.

    Normal mode deliberately swallows unmapped keys (see
    ``test_unmapped_normal_key_is_swallowed``), so the new fall-through is
    observable on the function-key path, which returns the dispatch result
    directly.  A typo'd/never-registered action name must not eat the key in
    silence any more.
    """
    editor, keymap, ctx = _setup("abc")
    keymap.add_binding("<f7>", "nope_action")

    assert keymap.handle_key(ctx, parse_key("<f7>")) is False
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


def test_word_end_motion_wraps_to_the_next_line() -> None:
    """e at the end of a line steps onto the next one."""
    editor, keymap, ctx = _setup("ab\ncd")
    _press(keymap, ctx, "$")
    _press(keymap, ctx, "e")
    assert editor.buffer.cursor == (1, 0)


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
