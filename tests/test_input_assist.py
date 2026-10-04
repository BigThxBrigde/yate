"""Acceptance tests for the input-assist feature (issue IKJMQ2).

Covers the eight reproduction steps of the issue -- bracket auto-completion,
closing-symbol skipping, paired backspace, selection wrapping, Python
auto-indent, ``Tab`` / ``Shift+Tab`` re-indentation, one-undo-per-pair and the
paste / read-only carve-outs -- plus the language detection, indent-unit and
performance pins the plan asks for.

Everything runs headless: the keys go through the real keymap dispatch
(:class:`~yate.keymaps.vsc.VscKeymap` / :class:`~yate.keymaps.vim.VimKeymap`)
and the real built-in action table against a real
:class:`~yate.session.EditorSession`, so the assertions cover the whole
key -> action -> buffer chain rather than a buffer method in isolation.  No
Textual pilot is started: a pilot would add concurrency jitter to a file whose
performance budget is part of the contract.
"""

from __future__ import annotations

import time
from typing import cast

import pytest

from yate.actions import populate
from yate.config import YateConfig
from yate.editor import Editor
from yate.editor_core import BufferReadOnlyError, Document, TextBuffer
from yate.editor_core.indentation import PYTHON_RULES, closes_block, indent_unit
from yate.keymaps.base import ActionContext, KeyUi, Keymap, parse_key
from yate.keymaps.vim import EDT, VimKeymap, VimMode
from yate.keymaps.vsc import VscKeymap
from yate.registries import ActionRegistry
from yate.services import clipboard
from yate.session import EditorSession

#: Keystrokes the G9 benchmark types before averaging.
KEYSTROKES: int = 1000

#: Loose per-keystroke budget in milliseconds.  The issue asks for 5 ms; the
#: plan deliberately halves-then-quarters nothing and instead keeps the issue
#: figure as a hard ceiling so an O(n) regression fails the build instead of
#: being skipped, while normal CI jitter stays far below it.
AVERAGE_KEYSTROKE_BUDGET_MS: float = 5.0


class _Editor:
    """A real session and the real built-in action table.

    Editing actions are exactly what these tests exercise, so the table is the
    genuine one from :mod:`yate.actions`; the stand-in exists only because
    :func:`~yate.actions.populate` closes over a concrete
    :class:`~yate.editor.Editor`.  Every editor-level hook the table registers
    is resolved lazily inside its lambda, so an editing action never touches
    it and the cast is never dereferenced.

    *path* and *filetype* drive the two ways a document reports its language:
    the file suffix and the ``:set filetype=`` override.
    """

    def __init__(
        self,
        text: str = "",
        *,
        path: str | None = None,
        filetype: str | None = None,
    ) -> None:
        self.session = EditorSession(YateConfig())
        self.session.new_buffer()
        self.actions = ActionRegistry()
        self.messages: list[str] = []
        doc = Document(path, self.session.make_buffer(text))
        if filetype is not None:
            doc.filetype_override = filetype
        self.session.docs[self.session.index] = doc
        self.ui = KeyUi(
            execute_action=self.execute_action,
            message=self.message,
            command_prompt=lambda: None,
            find_prompt=lambda _forward: None,
            goto_prompt=lambda: None,
            toggle_keymap=lambda: None,
        )
        populate(self.actions, cast(Editor, self))

    @property
    def buffer(self) -> TextBuffer:
        """The active document's text buffer."""
        return self.session.buffer

    def context(self) -> ActionContext:
        """Build a fresh action context against this editor."""
        return ActionContext(self.session, self.ui)

    def execute_action(self, name: str) -> bool:
        """Run the named built-in action, reporting whether it was known."""
        return self.actions.execute(name, self.context())

    def message(self, text: str) -> None:
        """Record a status message."""
        self.messages.append(text)


def _press(keymap: Keymap, ctx: ActionContext, *keys: str) -> None:
    """Feed *keys* to *keymap* one at a time."""
    for key in keys:
        keymap.handle_key(ctx, key)


def _clipboard_paste() -> str | None:
    """Pretend the system clipboard holds nothing."""
    return None


def _clipboard_copy(_text: str) -> bool:
    """Swallow clipboard writes so no test reaches the desktop clipboard."""
    return True


@pytest.fixture()
def empty_clipboard(monkeypatch: pytest.MonkeyPatch) -> None:
    """Report an empty system clipboard so ``paste`` falls back to the register.

    The tests must never touch the real desktop clipboard, and an empty one
    keeps ``paste`` deterministic: whatever sits in
    :attr:`~yate.editor_core.buffer.TextBuffer.register` is what lands.
    """
    monkeypatch.setattr(clipboard, "paste_text", _clipboard_paste)
    monkeypatch.setattr(clipboard, "copy_text", _clipboard_copy)


# --- issue step 1: typing a left symbol completes the pair --------------------


def test_typing_open_paren_inserts_both_halves_with_the_cursor_inside() -> None:
    """``(`` at the cursor yields ``()`` with the cursor between the halves."""
    editor = _Editor()
    vsc = VscKeymap()

    assert vsc.handle_key(editor.context(), "(") is True
    assert editor.buffer.get_text() == "()"
    assert editor.buffer.cursor == (0, 1)


def test_typing_a_quote_inserts_an_empty_quoted_pair() -> None:
    """``'`` is a pair of its own, so it completes to ``''``."""
    editor = _Editor()
    vsc = VscKeymap()

    vsc.handle_key(editor.context(), "'")
    assert editor.buffer.get_text() == "''"
    assert editor.buffer.cursor == (0, 1)


def test_vim_insert_mode_completes_pairs_like_the_modeless_path() -> None:
    """Vim's insert state shares the modeless auto-completion behaviour."""
    editor = _Editor("abc")
    keymap = VimKeymap()

    _press(keymap, editor.context(), "A", "(")
    assert editor.buffer.get_text() == "abc()"
    assert editor.buffer.cursor == (0, 4)


# --- quote smart-skip: the twin test runs before the completion branch --------
#
# The quotes are pairs of one character (``pair_for("'") == "'"``), so a
# completion-first branch order would make the twin test unreachable for them
# and turn ``|""`` + ``"`` into ``""""``.  These four cases pin the ordering
# from both sides: the skip when it applies, and the completion when it must
# still win.


def test_typing_a_quote_inside_a_quoted_pair_only_steps_right() -> None:
    """``|""`` + ``"`` gives ``"|"`` -- the twin is stepped over, not doubled."""
    editor = _Editor('""')
    editor.buffer.set_cursor((0, 1))
    vsc = VscKeymap()

    assert vsc.handle_key(editor.context(), '"') is True
    assert editor.buffer.get_text() == '""'
    assert editor.buffer.cursor == (0, 2)


def test_typing_a_single_quote_inside_a_quoted_pair_only_steps_right() -> None:
    """The same for ``''``: the second press steps over rather than inserts."""
    editor = _Editor("''")
    editor.buffer.set_cursor((0, 1))
    vsc = VscKeymap()

    assert vsc.handle_key(editor.context(), "'") is True
    assert editor.buffer.get_text() == "''"
    assert editor.buffer.cursor == (0, 2)


def test_typing_a_quote_on_an_empty_row_still_completes_the_pair() -> None:
    """The skip needs ``c < len(line)``, so row 0 of an empty buffer completes.

    This is the negative half of the ordering pin: moving the twin test ahead
    of the completion branch must not make it swallow the very keystroke that
    creates the pair.
    """
    editor = _Editor()
    vsc = VscKeymap()

    vsc.handle_key(editor.context(), "'")
    assert editor.buffer.get_text() == "''"
    assert editor.buffer.cursor == (0, 1)


def test_typing_a_quote_at_the_row_end_still_completes_the_pair() -> None:
    """``a|`` + ``'`` gives ``a'|'``: no twin on the right, so it completes."""
    editor = _Editor()
    vsc = VscKeymap()
    ctx = editor.context()
    vsc.handle_key(ctx, "a")
    editor.buffer.move_line_end()

    vsc.handle_key(ctx, "'")
    assert editor.buffer.get_text() == "a''"
    assert editor.buffer.cursor == (0, 2)


def test_typing_a_quote_over_a_selection_wraps_instead_of_skipping() -> None:
    """A selection outranks the twin test: ``h|ell|o`` + ``'`` wraps the word.

    The wrap branch is reached before the skip, so a quote typed over a
    selection never reads as "step over the quote that happens to follow".
    """
    editor = _Editor("hello")
    buf = editor.buffer
    buf.anchor = (0, 1)
    buf.cursor = (0, 4)
    vsc = VscKeymap()

    assert vsc.handle_key(editor.context(), "'") is True
    assert buf.get_text() == "h'ell'o"
    assert buf.cursor == (0, 5)  # parked before the closing quote
    assert buf.has_selection() is False


# --- issue step 2: the closing symbol only steps over its twin ----------------


def test_typing_closing_paren_in_front_of_its_twin_only_steps_right() -> None:
    """Inside ``(|)`` a typed ``)`` moves past the symbol instead of doubling it."""
    editor = _Editor()
    vsc = VscKeymap()
    ctx = editor.context()
    vsc.handle_key(ctx, "(")

    assert vsc.handle_key(ctx, ")") is True
    assert editor.buffer.get_text() == "()"
    assert editor.buffer.cursor == (0, 2)


def test_typing_closing_paren_without_a_twin_inserts_it_literally() -> None:
    """A ``)`` typed in front of ordinary text is a normal insert."""
    editor = _Editor("ab")
    vsc = VscKeymap()
    ctx = editor.context()
    editor.buffer.set_cursor((0, 1))

    vsc.handle_key(ctx, ")")
    assert editor.buffer.get_text() == "a)b"
    assert editor.buffer.cursor == (0, 2)


# --- issue step 3: backspace removes an emptied pair --------------------------


def test_backspace_between_the_halves_removes_both_symbols() -> None:
    """Backspace inside ``(|)`` takes both symbols in one keystroke."""
    editor = _Editor()
    vsc = VscKeymap()
    ctx = editor.context()
    vsc.handle_key(ctx, "(")

    assert vsc.handle_key(ctx, parse_key("<backspace>")) is True
    assert editor.buffer.get_text() == ""
    assert editor.buffer.cursor == (0, 0)


def test_backspace_outside_a_pair_deletes_a_single_character() -> None:
    """The paired deletion needs a real pair; ``ab|`` loses only the ``b``."""
    editor = _Editor("ab")
    vsc = VscKeymap()
    ctx = editor.context()
    editor.buffer.set_cursor((0, 2))

    vsc.handle_key(ctx, parse_key("<backspace>"))
    assert editor.buffer.get_text() == "a"
    assert editor.buffer.cursor == (0, 1)


# --- issue step 4: a left symbol wraps the selection --------------------------


def test_typing_open_paren_wraps_the_selection_and_parks_before_the_closer() -> None:
    """``(`` over a selected ``abc`` yields ``(abc)`` with the cursor after ``abc``."""
    editor = _Editor("abc")
    buf = editor.buffer
    buf.anchor = (0, 0)
    buf.cursor = (0, 3)
    vsc = VscKeymap()

    assert vsc.handle_key(editor.context(), "(") is True
    assert buf.get_text() == "(abc)"
    assert buf.cursor == (0, 4)
    assert buf.has_selection() is False


def test_typing_a_plain_letter_replaces_the_selection_without_wrapping() -> None:
    """Only left symbols wrap; ``a`` over a selection is an ordinary replace."""
    editor = _Editor("abc")
    buf = editor.buffer
    buf.anchor = (0, 0)
    buf.cursor = (0, 3)
    vsc = VscKeymap()

    vsc.handle_key(editor.context(), "a")
    assert buf.get_text() == "a"
    assert buf.cursor == (0, 1)


# --- issue step 5: python auto-indent on enter --------------------------------


def test_enter_after_a_python_colon_indents_the_new_line_by_one_unit() -> None:
    """Enter at the end of ``if True:`` in a ``.py`` document adds one level."""
    editor = _Editor("if True:", path="demo.py")
    vsc = VscKeymap()
    editor.buffer.move_line_end()

    assert vsc.handle_key(editor.context(), parse_key("<enter>")) is True
    assert editor.buffer.lines == ["if True:", "    "]
    assert editor.buffer.cursor == (1, 4)


def test_enter_after_a_python_colon_with_trailing_blanks_keeps_the_indent_intact() -> None:
    """Trailing blanks after the ``:`` must not leak into the new line's indent.

    The indent is the line's *leading* whitespace, so deriving it from a
    ``strip()``-based length would reach past the indent and slice the line's
    own text in instead (``"if True:  "`` would indent with ``"if"``).
    """
    editor = _Editor("if True:  ", path="demo.py")
    vsc = VscKeymap()
    editor.buffer.move_line_end()

    vsc.handle_key(editor.context(), parse_key("<enter>"))
    assert editor.buffer.lines == ["if True:  ", "    "]
    assert editor.buffer.cursor == (1, 4)


def test_enter_after_a_python_filetype_override_indents_the_new_line() -> None:
    """``:set filetype=python`` reaches the same rules as the ``.py`` suffix."""
    editor = _Editor("if True:", filetype="python")
    vsc = VscKeymap()
    editor.buffer.move_line_end()

    vsc.handle_key(editor.context(), parse_key("<enter>"))
    assert editor.buffer.lines == ["if True:", "    "]


def test_enter_in_a_non_python_document_only_copies_the_current_indent() -> None:
    """A ``.txt`` document keeps the old "newline continues the indent" rule."""
    editor = _Editor("    x = 1", path="notes.txt")
    vsc = VscKeymap()
    editor.buffer.move_line_end()

    vsc.handle_key(editor.context(), parse_key("<enter>"))
    assert editor.buffer.lines == ["    x = 1", "    "]


def test_enter_in_an_unnamed_document_never_gains_a_level() -> None:
    """No path means ``plaintext``, so even a trailing ``:`` indents nothing."""
    editor = _Editor("if True:")
    vsc = VscKeymap()
    editor.buffer.move_line_end()

    vsc.handle_key(editor.context(), parse_key("<enter>"))
    assert editor.buffer.lines == ["if True:", ""]


def test_vim_insert_mode_enter_applies_the_python_indent_rules() -> None:
    """The vim insert path reaches ``newline`` and inherits the same rules."""
    editor = _Editor("if True:", path="demo.py")
    keymap = VimKeymap()

    _press(keymap, editor.context(), "A", "\r")
    assert editor.buffer.lines == ["if True:", "    "]


def test_newline_language_argument_selects_the_python_rules_at_buffer_level() -> None:
    """``insert_newline(language=...)`` alone flips the auto-indent on and off."""
    python_side = TextBuffer("if True:")
    python_side.move_line_end()
    python_side.insert_newline(language="python")

    plain = TextBuffer("if True:")
    plain.move_line_end()
    plain.insert_newline(language="plaintext")

    assert python_side.lines == ["if True:", "    "]
    assert plain.lines == ["if True:", ""]


def test_newline_after_a_dedent_statement_keeps_the_current_level() -> None:
    """``return`` ends a block, so its continuation line is not indented."""
    buf = TextBuffer("    return x")
    buf.move_line_end()
    buf.insert_newline(language="python")

    assert buf.lines == ["    return x", "    "]


def test_newline_on_a_blank_line_adds_no_indentation() -> None:
    """A blank line never opens a block, so nothing is added after it."""
    buf = TextBuffer("")
    buf.insert_newline(language="python")

    assert buf.lines == ["", ""]


# --- issue step 6: tab / shift-tab re-indentation -----------------------------


def test_tab_indents_the_row_of_a_single_line_selection() -> None:
    """``Tab`` over a one-row selection shifts that whole row by one level."""
    editor = _Editor("abc")
    buf = editor.buffer
    buf.anchor = (0, 0)
    buf.cursor = (0, 1)
    vsc = VscKeymap()

    assert vsc.handle_key(editor.context(), parse_key("<tab>")) is True
    assert buf.lines == ["    abc"]


def test_tab_indents_every_row_of_a_multi_line_selection() -> None:
    """A multi-row selection shifts all of its rows, and only those."""
    editor = _Editor("a\nb\nc")
    buf = editor.buffer
    buf.anchor = (0, 0)
    buf.cursor = (1, 1)
    vsc = VscKeymap()

    vsc.handle_key(editor.context(), parse_key("<tab>"))
    assert buf.lines == ["    a", "    b", "c"]


def test_tab_on_a_single_line_selection_widens_it_to_the_whole_row() -> None:
    """``Tab`` indents the row *and* leaves the selection covering all of it.

    Existing :meth:`~yate.editor_core.buffer.TextBuffer.indent_selection`
    behaviour -- it parks the anchor at column 0 and the cursor at the row end
    (this is what makes vim's ``V``-style linewise shift work), and it has
    always done so for multi-row selections.  Pinned here for the single-row
    case to make the widening visible: this records the behaviour, it does not
    endorse it, and it is **not** changed by this feature.
    """
    editor = _Editor("abc")
    buf = editor.buffer
    buf.anchor = (0, 0)
    buf.cursor = (0, 1)
    vsc = VscKeymap()

    vsc.handle_key(editor.context(), parse_key("<tab>"))
    assert buf.lines == ["    abc"]
    assert buf.anchor == (0, 0)
    assert buf.cursor == (0, len("    abc"))
    assert buf.selection() == ((0, 0), (0, 7))


def test_shift_tab_outdents_the_selection_by_one_level() -> None:
    """``Shift+Tab`` removes exactly one indentation level."""
    editor = _Editor("        abc")
    buf = editor.buffer
    buf.anchor = (0, 0)
    buf.cursor = (0, 1)
    vsc = VscKeymap()

    assert vsc.handle_key(editor.context(), parse_key("<shift-tab>")) is True
    assert buf.lines == ["    abc"]


def test_shift_tab_on_an_unindented_row_leaves_it_at_zero() -> None:
    """Outdenting never goes negative, however often it is pressed."""
    editor = _Editor("abc")
    buf = editor.buffer
    buf.anchor = (0, 0)
    buf.cursor = (0, 1)
    vsc = VscKeymap()
    ctx = editor.context()

    vsc.handle_key(ctx, parse_key("<shift-tab>"))
    vsc.handle_key(ctx, parse_key("<shift-tab>"))
    assert buf.lines == ["abc"]
    assert buf.lines[0].startswith(" ") is False


def test_vim_normal_mode_count_indents_the_current_line() -> None:
    """``3>`` shifts the line by three levels, one per count."""
    editor = _Editor("abc")
    keymap = VimKeymap()

    _press(keymap, editor.context(), "3", ">")
    assert editor.buffer.lines == ["            abc"]


def test_vim_normal_mode_outdent_stops_at_column_zero() -> None:
    """``3<`` on an 8-space line removes both levels and then stops at zero."""
    editor = _Editor("        abc")
    keymap = VimKeymap()

    _press(keymap, editor.context(), "3", "<")
    assert editor.buffer.lines == ["abc"]


def test_vim_normal_mode_indent_shifts_the_whole_line_from_any_column() -> None:
    """``>`` shifts the line, not the text before the cursor, wherever it sits.

    Without a selection the ``indent`` primitives pad to the next tab stop at
    the cursor, so a cursor mid-row used to splice spaces into ``abc``; the
    keymap now selects the row first.
    """
    editor = _Editor("abc")
    editor.buffer.set_cursor((0, 2))
    keymap = VimKeymap()

    keymap.handle_key(editor.context(), ">")
    assert editor.buffer.lines == ["    abc"]
    # the cursor lands on the first non-blank column and keeps no selection
    assert editor.buffer.cursor == (0, 4)
    assert editor.buffer.has_selection() is False


def test_vim_normal_mode_outdent_shifts_the_whole_line_from_any_column() -> None:
    """``<`` is symmetric: the row is selected first, so the column never matters."""
    editor = _Editor("        abc")
    editor.buffer.set_cursor((0, 10))
    keymap = VimKeymap()

    keymap.handle_key(editor.context(), "<")
    assert editor.buffer.lines == ["    abc"]
    assert editor.buffer.cursor == (0, 4)
    assert editor.buffer.has_selection() is False


def test_vim_normal_mode_indent_on_an_empty_row_adds_one_unit_per_count() -> None:
    """An empty row cannot be selected, so it keeps the ``insert_tab`` fallback.

    That is the sensible reading -- one unit at column 0 -- and it is pinned
    here so the fallback is a documented behaviour rather than an accident.
    """
    editor = _Editor("abc\n")
    editor.buffer.set_cursor((1, 0))
    keymap = VimKeymap()

    _press(keymap, editor.context(), "3", ">")
    assert editor.buffer.lines == ["abc", "            "]


def test_vsc_indent_action_without_a_selection_pads_at_the_cursor() -> None:
    """Records the built-in ``indent`` action's existing cursor-relative padding.

    vsc's ``<ctrl-]>`` with no selection inserts up to the next tab stop *at the
    cursor* -- ``ab|c`` becomes ``ab  c``.  This is long-standing action
    behaviour and is deliberately **not** changed here; the pin exists so that
    anyone unifying it with vim's ``>`` (which shifts the whole line) can see
    both semantics side by side.
    """
    editor = _Editor("abc")
    editor.buffer.set_cursor((0, 2))
    vsc = VscKeymap()

    assert vsc.handle_key(editor.context(), parse_key("<ctrl-]>")) is True
    assert editor.buffer.lines == ["ab  c"]
    assert editor.buffer.cursor == (0, 4)


def test_vim_visual_line_mode_indents_the_selected_rows() -> None:
    """``V j >`` shifts both selected lines and stays in visual mode."""
    editor = _Editor("a\nb\nc")
    keymap = VimKeymap()
    ctx = editor.context()

    _press(keymap, ctx, "V", "j", ">")
    assert editor.buffer.lines == ["    a", "    b", "c"]
    assert keymap.mode is VimMode.VISUAL_LINE


def test_vim_visual_line_mode_outdents_the_selected_rows() -> None:
    """``V j <`` shifts both selected lines back by one level."""
    editor = _Editor("    a\n    b\nc")
    keymap = VimKeymap()

    _press(keymap, editor.context(), "V", "j", "<")
    assert editor.buffer.lines == ["a", "b", "c"]


def test_vim_visual_indent_does_not_leak_a_typed_count_into_normal_mode() -> None:
    """``3 v > <esc>`` leaves no count behind, so the next ``x`` deletes one char.

    Entering visual mode does not clear ``count_str``, and the ``>`` / ``<``
    branch returns before the motion path that normally consumes it -- the
    residue used to turn the following ``x`` into a ``3x``.  Visual mode ignores
    counts by convention, so the branch drops it instead.
    """
    editor = _Editor("abcdef")
    keymap = VimKeymap()
    ctx = editor.context()

    _press(keymap, ctx, "3", "v", ">", "\x1b")
    assert keymap.mode is VimMode.NORMAL
    assert keymap.count_str == ""

    _press(keymap, ctx, "x")
    assert editor.buffer.lines == ["    bcdef"]


def test_vim_visual_outdent_does_not_leak_a_typed_count_into_normal_mode() -> None:
    """The same for ``<``: the count must not survive the visual command.

    A charwise ``v`` leaves the cursor on the outdented row's first column, so
    the following ``x`` has text to delete and a leaked count would show up as
    two characters gone instead of one.
    """
    editor = _Editor("        abcdefgh")
    keymap = VimKeymap()
    ctx = editor.context()

    _press(keymap, ctx, "2", "v", "<", "\x1b")
    assert keymap.count_str == ""
    assert editor.buffer.lines == ["    abcdefgh"]

    _press(keymap, ctx, "x")
    assert editor.buffer.lines == ["   abcdefgh"]


def test_vim_help_table_lists_the_indent_keys() -> None:
    """F1 shows ``>`` / ``<`` in the vim edit category, bound to real actions."""
    table = {b.key: b for b in VimKeymap().bindings}

    assert table[">"].action == "indent"
    assert table["<"].action == "outdent"
    assert table[">"].category == EDT
    assert table["<"].category == EDT


# --- issue step 7: one undo step per auto-completed pair ----------------------


def test_one_undo_removes_both_halves_of_an_auto_completed_pair() -> None:
    """A single Ctrl+Z after the pair (and its skipped twin) leaves no orphan."""
    editor = _Editor()
    vsc = VscKeymap()
    ctx = editor.context()
    vsc.handle_key(ctx, "(")
    vsc.handle_key(ctx, ")")

    assert vsc.handle_key(ctx, parse_key("<ctrl-z>")) is True
    assert editor.buffer.get_text() == ""


def test_one_undo_removes_a_pair_and_a_following_character_together() -> None:
    """``(`` plus the character typed after it is one ``"char"`` step.

    Adjacent typing coalesces into a single undo entry, so one Ctrl+Z takes the
    whole run -- asserted as the exact empty string, not as a bracket-balance
    check: counts of ``(`` and ``)`` are equal for *any* input (both zero on an
    empty buffer) and would pass even if the undo had run too far.
    """
    editor = _Editor()
    vsc = VscKeymap()
    ctx = editor.context()
    vsc.handle_key(ctx, "(")
    vsc.handle_key(ctx, "x")
    assert editor.buffer.get_text() == "(x)"

    vsc.handle_key(ctx, parse_key("<ctrl-z>"))
    assert editor.buffer.get_text() == ""


def test_paired_deletion_coalesces_with_the_completion_into_one_undo_step() -> None:
    """``(`` then Backspace is a single ``"char"`` step, so one Ctrl+Z empties it.

    The two keystrokes meet the buffer's long-standing coalescing rule (an
    adjacent ``"char"`` step extends the previous one), which is what keeps the
    auto-completed pair and its removal a single history entry instead of two.
    """
    editor = _Editor()
    vsc = VscKeymap()
    ctx = editor.context()
    vsc.handle_key(ctx, "(")
    vsc.handle_key(ctx, parse_key("<backspace>"))
    assert editor.buffer.get_text() == ""

    vsc.handle_key(ctx, parse_key("<ctrl-z>"))
    assert editor.buffer.get_text() == ""


# --- issue step 8: paste and read-only never trigger the assist ---------------


def test_paste_inserts_the_register_text_verbatim() -> None:
    """``paste`` is a different code path: the text lands unchanged."""
    editor = _Editor()
    editor.buffer.register = "abc"

    editor.buffer.paste()
    assert editor.buffer.get_text() == "abc"


def test_pasted_brackets_are_not_auto_completed() -> None:
    """Unbalanced brackets in a paste stay unbalanced -- no symbols are added."""
    editor = _Editor()
    editor.buffer.register = "(()"

    editor.buffer.paste()
    assert editor.buffer.get_text() == "(()"


def test_paste_action_inserts_the_register_text_verbatim(
    empty_clipboard: None,
) -> None:
    """The ``paste`` action reaches the same verbatim insert, clipboard aside."""
    editor = _Editor()
    editor.buffer.register = "(()"

    assert editor.execute_action("paste") is True
    assert editor.buffer.get_text() == "(()"


def test_paste_action_keeps_a_selection_verbatim(empty_clipboard: None) -> None:
    """A wrapped selection is replaced by the pasted text, not by a new pair."""
    editor = _Editor()
    buf = editor.buffer
    buf.anchor = (0, 0)
    buf.cursor = (0, 3)
    buf.register = "x(y"

    editor.execute_action("paste")
    assert buf.get_text() == "x(y"


def test_type_char_on_a_read_only_buffer_raises() -> None:
    """Auto-completion is refused outright on a read-only buffer."""
    buf = TextBuffer("", read_only=True)

    with pytest.raises(BufferReadOnlyError):
        buf.type_char("(")


def test_delete_backward_on_a_read_only_buffer_raises() -> None:
    """The paired deletion is guarded by the same read-only fence."""
    buf = TextBuffer("()", read_only=True)
    buf.set_cursor((0, 1))

    with pytest.raises(BufferReadOnlyError):
        buf.delete_backward()


def test_insert_newline_on_a_read_only_buffer_raises() -> None:
    """Auto-indent cannot write to a read-only buffer either."""
    buf = TextBuffer("if True:", read_only=True)

    with pytest.raises(BufferReadOnlyError):
        buf.insert_newline(language="py")


def test_insert_tab_on_a_read_only_buffer_raises() -> None:
    """``Tab`` re-indentation is refused before any line is touched."""
    buf = TextBuffer("abc", read_only=True)

    with pytest.raises(BufferReadOnlyError):
        buf.insert_tab()


def test_a_read_only_keyboard_keystroke_raises_instead_of_completing() -> None:
    """The refusal reaches the user through the keymap path, not just the buffer."""
    editor = _Editor()
    editor.buffer.read_only = True
    vsc = VscKeymap()

    with pytest.raises(BufferReadOnlyError):
        vsc.handle_key(editor.context(), "(")
    assert editor.buffer.get_text() == ""


# --- language rules and indent units -----------------------------------------


def test_closes_block_matches_the_python_dedent_keywords() -> None:
    """``closes_block`` keys on the first word with its trailing colons stripped.

    Bare statements (``return x``, ``break``) and the compound headers that
    always carry a colon (``else:``, ``elif cond:``, ``except ValueError:``,
    ``finally:``) all close a block, while ``x = returned``, a commented-out
    ``# return`` and an empty line do not -- the comparison is anchored at the
    start of the line.

    This is an extension point **not wired up in this release**: V1's
    :meth:`~yate.editor_core.buffer.TextBuffer.insert_newline` decides a block
    boundary from :func:`~yate.editor_core.indentation.opens_block` alone, so
    nothing on the product path consults this function yet.  The test pins the
    contract for a future syntax-level dedent (wiring it up is out of scope --
    the issue lists it as an optional V1 extra).  ``else:`` still gaining a
    level on Enter is pinned separately by
    :func:`test_enter_after_else_colon_still_indents_in_v1`.
    """
    assert closes_block(PYTHON_RULES, "return x") is True
    assert closes_block(PYTHON_RULES, "    return x") is True
    assert closes_block(PYTHON_RULES, "    else") is True
    assert closes_block(PYTHON_RULES, "else:") is True
    assert closes_block(PYTHON_RULES, "elif cond:") is True
    assert closes_block(PYTHON_RULES, "except ValueError:") is True
    assert closes_block(PYTHON_RULES, "finally:") is True
    assert closes_block(PYTHON_RULES, "break") is True
    assert closes_block(PYTHON_RULES, "x = returned") is False
    assert closes_block(PYTHON_RULES, "  # return") is False
    assert closes_block(PYTHON_RULES, "a::b") is False
    assert closes_block(PYTHON_RULES, "") is False


def test_enter_after_else_colon_still_indents_in_v1() -> None:
    """Deding ``else:`` / ``elif:`` is an explicit V1 non-goal of the feature.

    Pinned so the boundary is visible: the plan lists syntax-level dedent as
    out of scope, so Enter after a block-closing header keeps the level plus
    one rather than back at the header's own level.
    """
    buf = TextBuffer("    else:")
    buf.move_line_end()
    buf.insert_newline(language="py")

    assert buf.lines == ["    else:", "        "]


def test_indent_unit_follows_the_tab_width_and_space_settings() -> None:
    """Two spaces, four spaces and a hard tab are the three documented units."""
    assert indent_unit(2, use_spaces=True) == "  "
    assert indent_unit(4, use_spaces=True) == "    "
    assert indent_unit(4, use_spaces=False) == "\t"
    assert indent_unit(2, use_spaces=False) == "\t"


def test_auto_indent_uses_a_two_space_unit_when_tab_width_is_two() -> None:
    """``tab_width=2`` indents the auto-opened block by two spaces."""
    buf = TextBuffer("if True:", tab_width=2)
    buf.move_line_end()
    buf.insert_newline(language="py")

    assert buf.lines == ["if True:", "  "]


def test_auto_indent_uses_a_four_space_unit_when_tab_width_is_four() -> None:
    """The same line with ``tab_width=4`` indents by four spaces."""
    buf = TextBuffer("if True:", tab_width=4)
    buf.move_line_end()
    buf.insert_newline(language="py")

    assert buf.lines == ["if True:", "    "]


def test_auto_indent_uses_a_hard_tab_when_spaces_are_disabled() -> None:
    """With ``use_spaces=False`` the auto-indent matches a manually typed tab."""
    buf = TextBuffer("if True:", tab_width=4, use_spaces=False)
    buf.move_line_end()
    buf.insert_newline(language="py")

    assert buf.lines == ["if True:", "\t"]
    assert buf.lines[1] == indent_unit(4, use_spaces=False)


def test_tab_indent_uses_a_hard_tab_when_spaces_are_disabled() -> None:
    """Manual re-indentation and auto-indent agree on the same unit."""
    editor = _Editor("a\nb")
    editor.buffer.tab_width = 4
    editor.buffer.use_spaces = False
    buf = editor.buffer
    buf.anchor = (0, 0)
    buf.cursor = (1, 1)

    VscKeymap().handle_key(editor.context(), parse_key("<tab>"))
    assert buf.lines == ["\ta", "\tb"]


# --- G9 performance -----------------------------------------------------------


def test_typing_stays_within_the_average_keystroke_budget() -> None:
    """A thousand keystrokes into a 500-row buffer average well under 5 ms each.

    The threshold is a ceiling, not a skip: an accidental O(n)-per-keystroke
    regression fails here instead of quietly shipping.
    """
    editor = _Editor("\n".join(f"value_{i} = {i}" for i in range(500)))
    buf = editor.buffer
    buf.set_cursor((0, 0))

    start = time.perf_counter()
    for _ in range(KEYSTROKES):
        buf.type_char("a", language="py")
    average_ms = (time.perf_counter() - start) * 1000.0 / KEYSTROKES

    assert average_ms < AVERAGE_KEYSTROKE_BUDGET_MS, (
        f"average keystroke took {average_ms:.3f} ms, "
        f"budget is {AVERAGE_KEYSTROKE_BUDGET_MS} ms"
    )
