"""Quickfix action / command registration and key dispatch guards (plan b).

Pure dispatch tests: no Textual app, no editor widgets.  The dispatch stub
follows the ``tests/test_toggle_comment.py`` pattern, except the raw-key
handler routes through the keymap under test (the real ``_handle_raw_key``
does) so the pre-dispatch navigation branch is exercised, and an
unconsumed raw key is recorded as ``raw:`` for the guard assertions.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

from textual.events import Key

from conftest import make_action_context, make_key_ui

from yate.actions import populate
from yate.commands import register_commands
from yate.editor_dispatch import _handle_key
from yate.keymaps.conflicts import find_key_conflicts
from yate.keymaps.keys import (
    QUICKFIX_NEXT_KEY,
    QUICKFIX_PANEL_KEY,
    QUICKFIX_PREV_KEY,
)
from yate.keymaps.vim import VimKeymap, VimMode
from yate.keymaps.vsc import VscKeymap
from yate.registries import ActionRegistry, CommandRegistry

#: Raw key -> Textual ``event.key`` spelling _handle_key converts from.
_SPECS: dict[str, str] = {
    QUICKFIX_NEXT_KEY: "alt+j",
    QUICKFIX_PREV_KEY: "alt+k",
    QUICKFIX_PANEL_KEY: "alt+q",
}

#: Raw key -> flow method / action name both tables must agree on.
_ACTIONS: dict[str, str] = {
    QUICKFIX_NEXT_KEY: "quickfix_next",
    QUICKFIX_PREV_KEY: "quickfix_prev",
    QUICKFIX_PANEL_KEY: "quickfix_open",
}

#: :command name -> flow method both registrations must call.
_COMMAND_FLOWS: dict[str, str] = {
    "quickfix": "open",
    "cnext": "next",
    "cprev": "prev",
}

#: Action name -> flow method the action lambdas must call.
_ACTION_FLOWS: dict[str, str] = {
    "quickfix_next": "next",
    "quickfix_prev": "prev",
    "quickfix_open": "open",
}


def _flow_stub(calls: list[str]) -> SimpleNamespace:
    """A quickfix flow stand-in recording the flow method names."""
    return SimpleNamespace(
        next=lambda: calls.append("flow:next"),
        prev=lambda: calls.append("flow:prev"),
        open=lambda: calls.append("flow:open"),
    )


def test_quickfix_actions_and_commands_are_registered() -> None:
    """Real registries expose the three actions and three commands."""
    calls: list[str] = []
    editor = SimpleNamespace(quickfix_flows=_flow_stub(calls))

    actions = ActionRegistry()
    populate(actions, cast(Any, editor))
    commands = CommandRegistry()
    register_commands(commands, cast(Any, editor))

    ctx = make_action_context()
    for name, flow in _ACTION_FLOWS.items():
        assert actions.get(name) is not None, name
        calls.clear()
        assert actions.execute(name, ctx) is True, name
        assert calls == [f"flow:{flow}"], (name, calls)
    for name, flow in _COMMAND_FLOWS.items():
        command = commands.get(name)
        assert command is not None, name
        calls.clear()
        command.func("")
        assert calls == [f"flow:{flow}"], (name, calls)


def _dispatch_stub(keymap: Any) -> SimpleNamespace:
    """A tiny editor stand-in exposing only the fields _handle_key reads."""
    calls: list[str] = []

    def execute_action(name: str) -> bool:
        calls.append(f"action:{name}")
        return True

    def handle_raw_key(raw: str) -> bool:
        # Route through the keymap under test like _handle_raw_key does;
        # record an unconsumed raw key as ``raw:`` (dispatch never ran).
        ctx = make_action_context(text="", ui=make_key_ui(execute=execute_action))
        handled = keymap.handle_key(ctx, raw)
        if not handled:
            calls.append(f"raw:{raw!r}")
        return handled

    def try_window_prefix(event: Key) -> bool:
        return False

    def request_completion(manual: bool) -> None:
        return None

    def record_message(text: str, kind: str = "info") -> None:
        calls.append(f"message:{text}")

    return SimpleNamespace(
        calls=calls,
        app=SimpleNamespace(focused=None),
        hover=SimpleNamespace(dismiss=lambda: None),
        completion_popup=SimpleNamespace(is_open=False),
        window_flows=SimpleNamespace(try_window_prefix=try_window_prefix),
        prompt_bar=SimpleNamespace(active_mode=""),
        completion=SimpleNamespace(request=request_completion),
        overlays=SimpleNamespace(
            open_command_palette=lambda: None,
            open_file_palette=lambda: None,
        ),
        completion_popup_actions=None,
        has_modal_screen=lambda: False,
        execute_action=execute_action,
        focus_explorer=lambda: calls.append("focus_explorer"),
        focus_editor=lambda: calls.append("focus_editor"),
        explorer_focused=lambda: False,
        handle_raw_key=handle_raw_key,
        message=record_message,
        refresh_ui=lambda: None,
        terminal_panel=SimpleNamespace(toggle=lambda: None),
    )


def _dispatch_key(ed: SimpleNamespace, key: str, character: str | None = None) -> bool:
    """Send one synthetic Textual key event to the dispatch function."""
    return _handle_key(cast(Any, ed), Key(key, character))


def test_quickfix_keys_dispatch_once_in_both_keymaps() -> None:
    """Each raw key fires exactly one action in vsc mode and in vim INSERT.

    The vim case starts in INSERT mode so the pre-dispatch navigation
    branch (not the INSERT character path) is proven; neither keymap ever
    lets the key fall through as a raw key.
    """
    for keymap in (VscKeymap(), _insert_mode_vim()):
        for raw, action in _ACTIONS.items():
            ed = _dispatch_stub(keymap)
            ed.prompt_bar.active_mode = ""
            ed.has_modal_screen = lambda: False

            consumed = _dispatch_key(ed, _SPECS[raw])

            assert consumed is True, (type(keymap).__name__, raw)
            assert ed.calls == [f"action:{action}"], (type(keymap).__name__, raw)
            assert not any(call.startswith("raw:") for call in ed.calls)


def _insert_mode_vim() -> VimKeymap:
    """A fresh VimKeymap parked in INSERT mode (pre-dispatch branch proof)."""
    km = VimKeymap()
    km.mode = VimMode.INSERT
    return km


def test_quickfix_keys_are_ignored_while_prompt_or_modal_active() -> None:
    """Prompt edit mode and a modal screen swallow the keys untouched."""
    for keymap in (VscKeymap(), _insert_mode_vim()):
        for raw in _ACTIONS:
            ed = _dispatch_stub(keymap)
            ed.prompt_bar.active_mode = ":"

            _dispatch_key(ed, _SPECS[raw])

            assert ed.calls == [], ("prompt", type(keymap).__name__, raw)

            ed = _dispatch_stub(keymap)
            ed.has_modal_screen = lambda: True

            _dispatch_key(ed, _SPECS[raw])

            assert ed.calls == [], ("modal", type(keymap).__name__, raw)


def test_quickfix_keys_have_no_conflicts() -> None:
    """The quickfix keys cause no duplicate / reserved-key conflicts.

    ``find_key_conflicts`` reports the stock reserved-key help-mirror rows
    too (e.g. vim's ``\\x1bc`` multi-cursor mirror), so the assertion is
    scoped to the three quickfix raw keys: none of them may appear.
    """
    for keymap in (VscKeymap(), VimKeymap()):
        conflicts = find_key_conflicts(keymap, reserved=keymap.reserved_keys)
        offenders = [c for c in conflicts if c.raw in _ACTIONS]
        assert offenders == [], type(keymap).__name__
