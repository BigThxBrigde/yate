"""Tests for the shared toggle-comment action, command and dispatch split."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

from textual.events import Key

from yate.actions import populate
from yate.commands import register_commands
from yate.editor_dispatch import _handle_key
from yate.editor_syntax import lang_for
from yate.keymaps.keys import TOGGLE_COMMENT_KEY, TOGGLE_KEYMAP_KEY, parse_key
from yate.keymaps.vim import VimKeymap, VimMode
from yate.keymaps.vsc import VscKeymap
from yate.registries import ActionRegistry, CommandRegistry

from conftest import make_action_context, make_key_ui


def _dispatch_stub() -> SimpleNamespace:
    """A tiny editor stand-in exposing only the fields _handle_key reads."""
    calls: list[str] = []
    return SimpleNamespace(
        calls=calls,
        app=SimpleNamespace(focused=None),
        hover=SimpleNamespace(dismiss=lambda: None),
        completion_popup=SimpleNamespace(is_open=False),
        window_flows=SimpleNamespace(try_window_prefix=lambda event: False),
        prompt_bar=SimpleNamespace(active_mode=""),
        completion=SimpleNamespace(request=lambda manual: None),
        overlays=SimpleNamespace(
            open_command_palette=lambda: None,
            open_file_palette=lambda: None,
        ),
        completion_popup_actions=None,
        has_modal_screen=lambda: False,
        execute_action=lambda name: calls.append(f"action:{name}") or True,
        focus_explorer=lambda: calls.append("focus_explorer"),
        focus_editor=lambda: calls.append("focus_editor"),
        explorer_focused=lambda: False,
        handle_raw_key=lambda raw: calls.append(f"raw:{raw!r}") or True,
        message=lambda text, kind="info": calls.append(f"message:{text}"),
        refresh_ui=lambda: None,
        terminal_panel=SimpleNamespace(toggle=lambda: None),
    )


def _dispatch_key(ed: SimpleNamespace, key: str, character: str | None = None) -> bool:
    """Send one synthetic Textual key event to the dispatch function."""
    return _handle_key(cast(Any, ed), Key(key, character))


def _action_context(text: str, filetype: str) -> Any:
    """Build a real action context with an explicit filetype override."""
    ctx = make_action_context(text)
    ctx.doc.filetype_override = filetype
    return ctx


def _run_action(ctx: Any) -> None:
    registry = ActionRegistry()
    populate(registry, cast(Any, object()))
    assert registry.execute("toggle_comment", ctx)


def test_action_toggles_current_python_line_and_restores() -> None:
    ctx = _action_context("def f():\n    pass\n", "py")

    _run_action(ctx)
    assert ctx.buffer.lines == ["# def f():", "    pass", ""]

    _run_action(ctx)
    assert ctx.buffer.lines == ["def f():", "    pass", ""]


def test_action_uses_langspec_for_html_block_comment() -> None:
    ctx = _action_context("<p>hi</p>\n", "html")

    _run_action(ctx)
    assert ctx.buffer.lines == ["<!-- <p>hi</p> -->", ""]

    _run_action(ctx)
    assert ctx.buffer.lines == ["<p>hi</p>", ""]


def test_action_respects_selection_rows_and_restores() -> None:
    ctx = _action_context("one\ntwo\nthree\n", "py")
    ctx.buffer.set_cursor((1, 0))
    ctx.buffer.set_cursor((2, 3), select=True)

    _run_action(ctx)
    assert ctx.buffer.lines == ["one", "# two", "# three", ""]

    _run_action(ctx)
    assert ctx.buffer.lines == ["one", "two", "three", ""]


def test_action_reports_missing_comment_syntax() -> None:
    messages: list[str] = []
    ctx = _action_context("plain", "txt")
    ctx.ui = make_key_ui(on_message=messages.append)

    _run_action(ctx)
    assert ctx.buffer.lines == ["plain"]
    assert any("no comment syntax" in text for text in messages)


def test_action_is_one_undo_step() -> None:
    ctx = _action_context("a\nb\n", "py")

    _run_action(ctx)
    ctx.buffer.undo()
    assert ctx.buffer.lines == ["a", "b", ""]


def test_toggle_comment_command_forwards_to_action() -> None:
    calls: list[str] = []
    editor = SimpleNamespace(execute_action=lambda name: calls.append(name))
    commands = CommandRegistry()
    register_commands(commands, cast(Any, editor))

    command = commands.get("toggle-comment")
    assert command is not None
    command.func("")
    assert calls == ["toggle_comment"]


def test_ctrl_shift_slash_switches_keymap_only() -> None:
    ed = _dispatch_stub()

    consumed = _dispatch_key(ed, TOGGLE_KEYMAP_KEY)

    assert consumed is True
    assert ed.calls == ["action:toggle_keymap"]


def test_kitty_ctrl_shift_slash_alias_switches_keymap() -> None:
    ed = _dispatch_stub()

    _dispatch_key(ed, "ctrl+shift+slash")

    assert ed.calls == ["action:toggle_keymap"]


def test_ctrl_slash_reaches_raw_dispatch_only() -> None:
    ed = _dispatch_stub()

    _dispatch_key(ed, "ctrl+/", "\x1f")

    assert ed.calls == ["raw:'\\x1f'"]
    assert not any("toggle_keymap" in call for call in ed.calls)


def test_keymap_toggle_ignored_while_command_line_is_active() -> None:
    ed = _dispatch_stub()
    ed.prompt_bar.active_mode = "command"

    consumed = _dispatch_key(ed, TOGGLE_KEYMAP_KEY)

    assert consumed is False
    assert ed.calls == []


def test_both_keymaps_resolve_shared_raw_key_to_toggle_comment() -> None:
    raw = parse_key(TOGGLE_COMMENT_KEY)
    assert raw == "\x1f"

    for keymap in (VscKeymap(), VimKeymap()):
        binding = keymap.lookup(raw)
        assert binding is not None
        assert binding.action == "toggle_comment"


def test_both_keymaps_expose_the_help_only_keymap_chord() -> None:
    for keymap in (VscKeymap(), VimKeymap()):
        binding = keymap.lookup(TOGGLE_KEYMAP_KEY)
        assert binding is not None
        assert binding.action == "toggle_keymap"


def test_vim_ctrl_slash_comments_in_normal_and_insert() -> None:
    ctx = _action_context("hello\n", "py")
    registry = ActionRegistry()
    populate(registry, cast(Any, object()))
    ctx.ui = make_key_ui(execute=lambda name: registry.execute(name, ctx))
    keymap = VimKeymap()
    raw = parse_key(TOGGLE_COMMENT_KEY)

    assert keymap.handle_key(ctx, raw) is True
    assert ctx.buffer.lines == ["# hello", ""]

    keymap.mode = VimMode.INSERT
    assert keymap.handle_key(ctx, raw) is True
    assert ctx.buffer.lines == ["hello", ""]


def test_vim_ctrl_slash_clears_pending_prefix() -> None:
    ctx = _action_context("hello\n", "py")
    registry = ActionRegistry()
    populate(registry, cast(Any, object()))
    ctx.ui = make_key_ui(execute=lambda name: registry.execute(name, ctx))
    keymap = VimKeymap()
    keymap.prefix = "g"
    keymap.count_str = "3"

    keymap.handle_key(ctx, parse_key(TOGGLE_COMMENT_KEY))

    assert keymap.prefix is None
    assert keymap.count_str == ""


def test_langspec_markers_are_the_only_source() -> None:
    py = lang_for("py")
    html = lang_for("html")
    assert py is not None
    assert html is not None
    assert py.line_comment == "#"
    assert html.block_comment == ("<!--", "-->")
