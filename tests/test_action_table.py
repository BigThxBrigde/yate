"""The built-in action table (:mod:`yate.actions`).

``populate`` only registers closures against a concrete editor, so the table
can be built against a *recording* stand-in: editing actions are then asserted
through a real :class:`~yate.editor_core.buffer.TextBuffer` (via a real
:class:`~yate.session.EditorSession`), while session-level actions are
asserted by the hook they forward to and the arguments they pass.
"""

from __future__ import annotations

from typing import Any, Callable, cast

from yate.actions import populate
from yate.config import YateConfig
from yate.editor_core import Document
from yate.keymaps.base import ActionContext, KeyUi
from yate.registries import ActionRegistry
from yate.session import EditorSession

#: Every editor hook the built-in table forwards to.  A typo in ``actions.py``
#: (a hook the real editor does not have) shows up here as an unexpected name.
FORWARDED_HOOKS = frozenset(
    {
        "close_tab",
        "command_prompt",
        "cycle_tab",
        "find_next",
        "find_prompt",
        "focus_editor",
        "focus_explorer",
        "goto_prompt",
        "new_buffer",
        "open_command_palette",
        "open_file_palette",
        "page",
        "prompt_open",
        "quit",
        "replace_prompt",
        "save_document",
        "shell_prompt",
        "show_help",
        "show_manual",
        "toggle_explorer",
        "toggle_keymap",
    }
)

Call = tuple[str, tuple[Any, ...], dict[str, Any]]


class _StubEditor:
    """Records every editor hook the action table forwards to.

    Hooks are not implemented: :meth:`__getattr__` returns a call-recording
    no-op (the same idea as ``_FakeApp`` in ``test_editor_core.py``), so a
    newly added action stays a harmless no-op instead of raising
    ``AttributeError``, while tests can still assert the call.  Private and
    dunder lookups are real errors.
    """

    def __init__(self) -> None:
        self.calls: list[Call] = []

    def __getattr__(self, name: str) -> Callable[..., None]:
        if name.startswith("_") or name == "calls":
            raise AttributeError(
                f"{type(self).__name__!r} object has no attribute {name!r}"
            )

        def record(*args: Any, **kwargs: Any) -> None:
            self.calls.append((name, args, kwargs))

        return record

    def calls_to(self, name: str) -> list[tuple[tuple[Any, ...], dict[str, Any]]]:
        """The ``(args, kwargs)`` of every recorded call to the hook *name*."""
        return [(args, kwargs) for hook, args, kwargs in self.calls if hook == name]


def _table() -> tuple[ActionRegistry, _StubEditor]:
    """A populated action table plus the stand-in it was built against."""
    registry = ActionRegistry()
    editor = _StubEditor()
    populate(registry, cast(Any, editor))
    return registry, editor


def _context(text: str = "") -> ActionContext:
    """A real action context whose active buffer holds *text*."""
    session = EditorSession(YateConfig())
    session.new_buffer()
    session.docs[session.index] = Document(None, session.make_buffer(text))
    ui = KeyUi(
        execute_action=lambda _name: True,
        message=lambda _text: None,
        command_prompt=lambda: None,
        find_prompt=lambda _forward: None,
        goto_prompt=lambda: None,
        toggle_keymap=lambda: None,
    )
    return ActionContext(session, ui)


def _select(ctx: ActionContext, row: int, col: int) -> None:
    """Select from the buffer start to ``(row, col)``."""
    ctx.buffer.set_cursor((row, col), select=True)


# --- registration ------------------------------------------------------------


def test_populate_only_registers_closures() -> None:
    """Building the table never touches the editor."""
    registry, editor = _table()
    assert editor.calls == []
    assert registry.names()


# --- cut / copy --------------------------------------------------------------


def test_cut_with_a_selection_yanks_and_removes_the_selected_text() -> None:
    """cut puts the selection in the register and deletes it from the buffer."""
    registry, _editor = _table()
    ctx = _context("hello world")
    _select(ctx, 0, 5)

    assert registry.execute("cut", ctx) is True
    assert ctx.buffer.register == "hello"
    assert ctx.buffer.get_text() == " world"
    assert ctx.buffer.cursor == (0, 0)
    assert ctx.buffer.has_selection() is False


def test_cut_without_a_selection_deletes_the_whole_line() -> None:
    """cut falls back to delete_lines: the line goes to the register."""
    registry, _editor = _table()
    ctx = _context("one\ntwo\nthree")
    ctx.buffer.set_cursor((1, 1))

    assert registry.execute("cut", ctx) is True
    assert ctx.buffer.register == "two\n"
    assert ctx.buffer.get_text() == "one\nthree"
    assert ctx.buffer.cursor == (1, 0)


def test_copy_with_a_selection_yanks_the_selected_text() -> None:
    """copy with a selection leaves the buffer untouched."""
    registry, _editor = _table()
    ctx = _context("hello world")
    _select(ctx, 0, 5)

    assert registry.execute("copy", ctx) is True
    assert ctx.buffer.register == "hello"
    assert ctx.buffer.get_text() == "hello world"


def test_copy_without_a_selection_yanks_the_whole_line() -> None:
    """copy falls back to yank_lines: the line is captured line-wise."""
    registry, _editor = _table()
    ctx = _context("one\ntwo")
    ctx.buffer.set_cursor((1, 1))

    assert registry.execute("copy", ctx) is True
    assert ctx.buffer.register == "two\n"
    assert ctx.buffer.get_text() == "one\ntwo"


# --- editing actions (end to end through the buffer) -------------------------


def test_newline_and_insert_tab_grow_the_buffer() -> None:
    """Both editing actions insert through the buffer at the cursor."""
    registry, _editor = _table()

    ctx = _context("abc")
    ctx.buffer.set_cursor((0, 3))
    registry.execute("newline", ctx)
    assert ctx.buffer.get_text() == "abc\n"
    assert ctx.buffer.cursor == (1, 0)

    ctx = _context("abc")
    ctx.buffer.set_cursor((0, 3))
    registry.execute("insert_tab", ctx)
    assert ctx.buffer.get_text() == "abc "


def test_delete_actions_shorten_the_buffer() -> None:
    """Backward and forward deletion drop the neighbouring character."""
    registry, _editor = _table()

    ctx = _context("abc")
    ctx.buffer.set_cursor((0, 3))
    registry.execute("delete_backward", ctx)
    assert ctx.buffer.get_text() == "ab"
    assert ctx.buffer.cursor == (0, 2)

    ctx = _context("abc")
    registry.execute("delete_forward", ctx)
    assert ctx.buffer.get_text() == "bc"


def test_move_left_and_right_move_the_cursor() -> None:
    """Horizontal motion walks the cursor column by column."""
    registry, _editor = _table()
    ctx = _context("abc")

    registry.execute("move_right", ctx)
    assert ctx.buffer.col == 1
    registry.execute("move_right", ctx)
    registry.execute("move_left", ctx)
    assert ctx.buffer.cursor == (0, 1)


def test_undo_and_redo_reverse_and_replay_the_edit() -> None:
    """The history actions run the buffer's own undo/redo stack."""
    registry, _editor = _table()
    ctx = _context("abc")
    ctx.buffer.set_cursor((0, 3))

    registry.execute("insert_tab", ctx)
    assert ctx.buffer.get_text() == "abc "
    registry.execute("undo", ctx)
    assert ctx.buffer.get_text() == "abc"
    registry.execute("redo", ctx)
    assert ctx.buffer.get_text() == "abc "


def test_select_all_and_clear_selection_manage_the_anchor() -> None:
    """select_all spans the document; clear_selection drops the anchor."""
    registry, _editor = _table()
    ctx = _context("abc")

    registry.execute("select_all", ctx)
    assert ctx.buffer.has_selection() is True
    assert ctx.buffer.selection() == ((0, 0), (0, 3))

    registry.execute("clear_selection", ctx)
    assert ctx.buffer.anchor is None
    assert ctx.buffer.has_selection() is False


# --- forwarding actions ------------------------------------------------------


def test_save_forwards_to_the_editor_once() -> None:
    """save calls the editor's save hook exactly once, with no arguments."""
    registry, editor = _table()
    assert registry.execute("save", _context()) is True
    assert editor.calls_to("save_document") == [((), {})]


def test_toggle_keymap_forwards_to_the_editor() -> None:
    """The keymap toggle is the editor's, not the keymap's."""
    registry, editor = _table()
    assert registry.execute("toggle_keymap", _context()) is True
    assert editor.calls_to("toggle_keymap") == [((), {})]


def test_page_actions_forward_the_direction_and_the_half_flag() -> None:
    """Paging passes the direction plus the ``half=`` keyword."""
    registry, editor = _table()
    ctx = _context()
    for name in ("page_down", "page_half_down", "page_up", "page_half_up"):
        assert registry.execute(name, ctx) is True

    assert editor.calls_to("page") == [
        ((1,), {}),
        ((1,), {"half": True}),
        ((-1,), {}),
        ((-1,), {"half": True}),
    ]


def test_tab_cycle_actions_forward_the_delta() -> None:
    """next_tab / prev_tab cycle by +1 / -1."""
    registry, editor = _table()
    ctx = _context()
    assert registry.execute("next_tab", ctx) is True
    assert registry.execute("prev_tab", ctx) is True
    assert editor.calls_to("cycle_tab") == [((1,), {}), ((-1,), {})]


def test_search_actions_forward_the_direction() -> None:
    """find opens the prompt, find_next / find_prev pass the direction."""
    registry, editor = _table()
    ctx = _context()
    for name in ("find", "find_next", "find_prev", "replace"):
        assert registry.execute(name, ctx) is True

    assert editor.calls_to("find_prompt") == [((True,), {})]
    assert editor.calls_to("find_next") == [((True,), {}), ((False,), {})]
    assert editor.calls_to("replace_prompt") == [((), {})]


def test_view_and_file_actions_forward_to_their_hook() -> None:
    """Prompts, palettes, panels and tab/file operations reach the editor."""
    registry, editor = _table()
    expected = {
        "open_prompt": "prompt_open",
        "new_buffer": "new_buffer",
        "close_tab": "close_tab",
        "quit": "quit",
        "command_prompt": "command_prompt",
        "goto_prompt": "goto_prompt",
        "quick_open": "open_file_palette",
        "command_palette": "open_command_palette",
        "focus_explorer": "focus_explorer",
        "focus_editor": "focus_editor",
        "toggle_explorer": "toggle_explorer",
        "manual": "show_manual",
        "shell_prompt": "shell_prompt",
        "help": "show_help",
    }
    for action, hook in expected.items():
        assert registry.execute(action, _context()) is True
        assert editor.calls_to(hook) == [((), {})], action


def test_every_action_runs_and_forwards_only_known_hooks() -> None:
    """No built-in action raises, and every forwarded hook is a real one."""
    registry, editor = _table()
    for name in registry.names():
        assert registry.execute(name, _context("one\ntwo\nthree")) is True, name

    assert {hook for hook, _args, _kwargs in editor.calls} == FORWARDED_HOOKS


# --- table integrity ---------------------------------------------------------


def test_every_registered_action_has_a_name_and_a_description() -> None:
    """The help overlay and the command palette read both fields."""
    registry, _editor = _table()
    for name in registry.names():
        action = registry.get(name)
        assert action is not None
        assert action.name
        assert action.description


def test_names_are_sorted_for_the_help_system() -> None:
    """The help overlay lists the names in sorted order."""
    registry, _editor = _table()
    names = registry.names()
    assert names == sorted(names)
    assert len(names) == len(set(names))


def test_describe_matches_the_registered_names() -> None:
    """describe() is the name-sorted (name, description) view of the table."""
    registry, _editor = _table()
    describe = registry.describe()
    assert [name for name, _desc in describe] == registry.names()
    assert all(description for _name, description in describe)


def test_executing_an_unknown_action_is_reported_as_unhandled() -> None:
    """An unknown name returns False (keymaps fall through) and touches
    nothing."""
    registry, editor = _table()
    assert registry.execute("nope", _context()) is False
    assert editor.calls == []
