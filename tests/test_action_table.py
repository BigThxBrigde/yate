"""The built-in action table (:mod:`yate.actions`).

``populate`` only registers closures against a concrete editor, so the table
can be built against a *recording* stand-in: editing actions are then asserted
through a real :class:`~yate.editor_core.buffer.TextBuffer` (via a real
:class:`~yate.session.EditorSession`), while session-level actions are
asserted by the hook they forward to and the arguments they pass.
"""

from __future__ import annotations

from typing import Any, Callable, cast

import pytest

from yate.actions import populate
from yate.keymaps.base import ActionContext
from yate.registries import ActionRegistry
from yate.services import clipboard as clipboard_service

from conftest import make_action_context

#: Every editor hook the built-in table forwards to.  A typo in ``actions.py``
#: (a hook the real editor does not have) shows up here as an unexpected name.
#: Hooks on the flow collaborators (``document_flows`` / ``prompt_flows`` /
#: ``overlays`` / ``shell``) are recorded with their dotted path
#: (``overlays.show_help``).
FORWARDED_HOOKS: frozenset[str] = frozenset(
    {
        "command_prompt",
        "document_flows.close_tab",
        "document_flows.cycle_tab",
        "document_flows.new_buffer",
        "document_flows.prompt_open",
        "document_flows.save_document",
        "focus_editor",
        "focus_explorer",
        "overlays.open_command_palette",
        "overlays.open_file_palette",
        "overlays.show_help",
        "overlays.show_manual",
        "overlays.toggle_screensaver",
        "page",
        "prompt_flows.find_next",
        "prompt_flows.find_prompt",
        "prompt_flows.goto_prompt",
        "prompt_flows.replace_prompt",
        "quit",
        "shell.open_prompt",
        "toggle_explorer",
        "toggle_keymap",
    }
)

#: Editor members the table reaches through (each a flow collaborator).
_FLOW_NAMESPACES: frozenset[str] = frozenset(
    {"document_flows", "prompt_flows", "overlays", "shell", "lsp_sync"}
)

Call = tuple[str, tuple[Any, ...], dict[str, Any]]


class _StubFlows:
    """Records calls on one of the editor's flow collaborators.

    The table calls through ``editor.<flows>.<hook>``; the stub mirrors
    that shape and records the dotted name so :meth:`_StubEditor.calls_to`
    keeps a single flat namespace.
    """

    def __init__(self, parent: _StubEditor, namespace: str) -> None:
        self._parent = parent
        self._namespace = namespace

    def __getattr__(self, name: str) -> Callable[..., None]:
        if name.startswith("_"):
            raise AttributeError(
                f"{type(self).__name__!r} object has no attribute {name!r}"
            )

        def record(*args: Any, **kwargs: Any) -> None:
            self._parent.calls.append(
                (f"{self._namespace}.{name}", args, kwargs)
            )

        return record


class _StubEditor:
    """Records every editor hook the action table forwards to.

    Hooks are not implemented: :meth:`__getattr__` returns a call-recording
    no-op (the same idea as ``_FakeApp`` in ``test_editor_core.py``), so a
    newly added action stays a harmless no-op instead of raising
    ``AttributeError``, while tests can still assert the call.  Flow
    collaborators (:data:`_FLOW_NAMESPACES`) return a :class:`_StubFlows`
    sub-recorder.  Private and dunder lookups are real errors.
    """

    def __init__(self) -> None:
        self.calls: list[Call] = []

    def __getattr__(
        self, name: str
    ) -> Callable[..., None] | _StubFlows:
        if name in _FLOW_NAMESPACES:
            return _StubFlows(self, name)
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


def _select(ctx: ActionContext, row: int, col: int) -> None:
    """Select from the buffer start to ``(row, col)``."""
    ctx.buffer.set_cursor((row, col), select=True)


class _RecordingClip:
    """Recording stand-in replacing the clipboard service entry points."""

    def __init__(self) -> None:
        self.copies: list[str] = []
        self.paste_result: str | None = None

    def copy_text(self, text: str) -> bool:
        self.copies.append(text)
        return True

    def paste_text(self) -> str | None:
        return self.paste_result


@pytest.fixture()
def recording_clip(monkeypatch: pytest.MonkeyPatch) -> _RecordingClip:
    """Patch the clipboard service module the action table calls into."""
    fake = _RecordingClip()
    monkeypatch.setattr(clipboard_service, "copy_text", fake.copy_text)
    monkeypatch.setattr(clipboard_service, "paste_text", fake.paste_text)
    return fake


def _make_block(
    ctx: ActionContext, top: int, left: int, bottom: int, right: int,
) -> None:
    """Anchor a block selection at ``(top, left)`` and extend to (bottom, right)."""
    buf = ctx.buffer
    buf.set_cursor((top, left))
    buf.begin_block_selection()
    buf.set_cursor((bottom, right), select=True)


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
    ctx = make_action_context("hello world")
    _select(ctx, 0, 5)

    assert registry.execute("cut", ctx) is True
    assert ctx.buffer.register == "hello"
    assert ctx.buffer.get_text() == " world"
    assert ctx.buffer.cursor == (0, 0)
    assert ctx.buffer.has_selection() is False


def test_cut_without_a_selection_deletes_the_whole_line() -> None:
    """cut falls back to delete_lines: the line goes to the register."""
    registry, _editor = _table()
    ctx = make_action_context("one\ntwo\nthree")
    ctx.buffer.set_cursor((1, 1))

    assert registry.execute("cut", ctx) is True
    assert ctx.buffer.register == "two\n"
    assert ctx.buffer.get_text() == "one\nthree"
    assert ctx.buffer.cursor == (1, 0)


def test_copy_with_a_selection_yanks_the_selected_text() -> None:
    """copy with a selection leaves the buffer untouched."""
    registry, _editor = _table()
    ctx = make_action_context("hello world")
    _select(ctx, 0, 5)

    assert registry.execute("copy", ctx) is True
    assert ctx.buffer.register == "hello"
    assert ctx.buffer.get_text() == "hello world"


def test_copy_without_a_selection_yanks_the_whole_line() -> None:
    """copy falls back to yank_lines: the line is captured line-wise."""
    registry, _editor = _table()
    ctx = make_action_context("one\ntwo")
    ctx.buffer.set_cursor((1, 1))

    assert registry.execute("copy", ctx) is True
    assert ctx.buffer.register == "two\n"
    assert ctx.buffer.get_text() == "one\ntwo"


# --- editing actions (end to end through the buffer) -------------------------


def test_newline_and_insert_tab_grow_the_buffer() -> None:
    """Both editing actions insert through the buffer at the cursor."""
    registry, _editor = _table()

    ctx = make_action_context("abc")
    ctx.buffer.set_cursor((0, 3))
    registry.execute("newline", ctx)
    assert ctx.buffer.get_text() == "abc\n"
    assert ctx.buffer.cursor == (1, 0)

    ctx = make_action_context("abc")
    ctx.buffer.set_cursor((0, 3))
    registry.execute("insert_tab", ctx)
    assert ctx.buffer.get_text() == "abc "


def test_delete_actions_shorten_the_buffer() -> None:
    """Backward and forward deletion drop the neighbouring character."""
    registry, _editor = _table()

    ctx = make_action_context("abc")
    ctx.buffer.set_cursor((0, 3))
    registry.execute("delete_backward", ctx)
    assert ctx.buffer.get_text() == "ab"
    assert ctx.buffer.cursor == (0, 2)

    ctx = make_action_context("abc")
    registry.execute("delete_forward", ctx)
    assert ctx.buffer.get_text() == "bc"


def test_move_left_and_right_move_the_cursor() -> None:
    """Horizontal motion walks the cursor column by column."""
    registry, _editor = _table()
    ctx = make_action_context("abc")

    registry.execute("move_right", ctx)
    assert ctx.buffer.col == 1
    registry.execute("move_right", ctx)
    registry.execute("move_left", ctx)
    assert ctx.buffer.cursor == (0, 1)


def test_undo_and_redo_reverse_and_replay_the_edit() -> None:
    """The history actions run the buffer's own undo/redo stack."""
    registry, _editor = _table()
    ctx = make_action_context("abc")
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
    ctx = make_action_context("abc")

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
    assert registry.execute("save", make_action_context()) is True
    assert editor.calls_to("document_flows.save_document") == [((), {})]


def test_toggle_keymap_forwards_to_the_editor() -> None:
    """The keymap toggle is the editor's, not the keymap's."""
    registry, editor = _table()
    assert registry.execute("toggle_keymap", make_action_context()) is True
    assert editor.calls_to("toggle_keymap") == [((), {})]


def test_page_actions_forward_the_direction_and_the_half_flag() -> None:
    """Paging passes the direction plus the ``half=`` keyword."""
    registry, editor = _table()
    ctx = make_action_context()
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
    ctx = make_action_context()
    assert registry.execute("next_tab", ctx) is True
    assert registry.execute("prev_tab", ctx) is True
    assert editor.calls_to("document_flows.cycle_tab") == [((1,), {}), ((-1,), {})]


def test_search_actions_forward_the_direction() -> None:
    """find opens the prompt, find_next / find_prev pass the direction."""
    registry, editor = _table()
    ctx = make_action_context()
    for name in ("find", "find_next", "find_prev", "replace"):
        assert registry.execute(name, ctx) is True

    assert editor.calls_to("prompt_flows.find_prompt") == [((True,), {})]
    assert editor.calls_to("prompt_flows.find_next") == [
        ((True,), {}), ((False,), {})
    ]
    assert editor.calls_to("prompt_flows.replace_prompt") == [((), {})]


def test_view_and_file_actions_forward_to_their_hook() -> None:
    """Prompts, palettes, panels and tab/file operations reach the editor."""
    registry, editor = _table()
    expected = {
        "open_prompt": "document_flows.prompt_open",
        "new_buffer": "document_flows.new_buffer",
        "close_tab": "document_flows.close_tab",
        "quit": "quit",
        "command_prompt": "command_prompt",
        "goto_prompt": "prompt_flows.goto_prompt",
        "quick_open": "overlays.open_file_palette",
        "command_palette": "overlays.open_command_palette",
        "focus_explorer": "focus_explorer",
        "focus_editor": "focus_editor",
        "toggle_explorer": "toggle_explorer",
        "manual": "overlays.show_manual",
        "shell_prompt": "shell.open_prompt",
        "help": "overlays.show_help",
    }
    for action, hook in expected.items():
        assert registry.execute(action, make_action_context()) is True
        assert editor.calls_to(hook) == [((), {})], action


def test_every_action_runs_and_forwards_only_known_hooks() -> None:
    """No built-in action raises, and every forwarded hook is a real one."""
    registry, editor = _table()
    for name in registry.names():
        assert registry.execute(name, make_action_context("one\ntwo\nthree")) is True, name

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
    assert registry.execute("nope", make_action_context()) is False
    assert editor.calls == []


# --- block (column) selection ------------------------------------------------


def test_select_block_down_begins_at_cursor_and_extends() -> None:
    """The first press anchors at the cursor; further presses extend the block."""
    registry, _editor = _table()
    ctx = make_action_context("one\ntwo\nthree")
    ctx.buffer.set_cursor((0, 1))

    assert registry.execute("select_block_down", ctx) is True
    assert ctx.buffer.has_block_selection() is True
    assert ctx.buffer.block_region() == (0, 1, 1, 1)

    assert registry.execute("select_block_down", ctx) is True
    assert ctx.buffer.has_block_selection() is True
    assert ctx.buffer.block_region() == (0, 1, 2, 1)


def test_select_block_right_then_up_normalizes_region() -> None:
    """block_region() is normalized regardless of the anchor/cursor order."""
    registry, _editor = _table()
    ctx = make_action_context("one\ntwo\nthree")
    ctx.buffer.set_cursor((2, 2))

    assert registry.execute("select_block_right", ctx) is True
    assert registry.execute("select_block_up", ctx) is True

    assert ctx.buffer.block_region() == (1, 2, 2, 3)


def test_plain_select_down_extends_block_selection() -> None:
    """Plain shift+arrow extends the ongoing block selection, matching VS Code.

    A charwise ``select_down`` over an active block keeps the block flag and
    stretches the rectangle downward -- the anchor is not reset.
    """
    registry, _editor = _table()
    ctx = make_action_context("one\ntwo\nthree")
    ctx.buffer.set_cursor((0, 1))
    assert registry.execute("select_block_down", ctx) is True
    assert ctx.buffer.block_region() == (0, 1, 1, 1)

    assert registry.execute("select_down", ctx) is True

    assert ctx.buffer.has_block_selection() is True
    assert ctx.buffer.block_region() == (0, 1, 2, 1)


def test_copy_action_yanks_block_text(recording_clip: _RecordingClip) -> None:
    """copy on a block selection yanks the rectangle and mirrors the clipboard."""
    registry, _editor = _table()
    ctx = make_action_context("abcd\nefgh")
    _make_block(ctx, 0, 1, 1, 3)

    assert registry.execute("copy", ctx) is True
    assert ctx.buffer.register == "bc\nfg"
    assert ctx.buffer.register_block is True
    assert recording_clip.copies == ["bc\nfg"]


def test_cut_action_deletes_block_and_copies(
    recording_clip: _RecordingClip,
) -> None:
    """cut on a block selection removes the rectangle; one undo restores it."""
    registry, _editor = _table()
    ctx = make_action_context("abcd\nefgh")
    _make_block(ctx, 0, 1, 1, 3)

    assert registry.execute("cut", ctx) is True
    assert ctx.buffer.get_text() == "ad\neh"
    assert ctx.buffer.register == "bc\nfg"
    assert ctx.buffer.register_block is True
    assert recording_clip.copies == ["bc\nfg"]

    assert ctx.buffer.undo() is True
    assert ctx.buffer.get_text() == "abcd\nefgh"


def test_paste_action_replaces_block_selection_per_row(
    recording_clip: _RecordingClip,
) -> None:
    """paste on a block selection replaces each row's span (VS Code semantics)."""
    registry, _editor = _table()
    ctx = make_action_context("abcd\nefgh")
    _make_block(ctx, 0, 1, 1, 3)
    recording_clip.paste_result = "X\nYY"

    assert registry.execute("paste", ctx) is True
    assert ctx.buffer.get_text() == "aXd\neYYh"


def test_paste_action_block_falls_back_to_register(
    recording_clip: _RecordingClip,
) -> None:
    """A clipboard miss (None) pastes the register per block row."""
    registry, _editor = _table()
    ctx = make_action_context("abcd\nefgh")
    _make_block(ctx, 0, 1, 1, 3)
    ctx.buffer.register = "Z\nW"
    recording_clip.paste_result = None

    assert registry.execute("paste", ctx) is True
    assert ctx.buffer.get_text() == "aZd\neWh"
