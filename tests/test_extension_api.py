"""Unit tests for ``yate.services.extension_api`` (the ExtensionAPI surface).

Covers the gap ``tests/test_extensions.py`` does not: the ``bind_key``
decorator form and its ``both`` / ``normal`` / positional-keymap variants,
the ``command`` decorator versus ``register_command``, the default
descriptions, the narrow accessors, and the A13 rollback-scope edge cases
(stale-scope warning, no-scope idempotence).
"""

from __future__ import annotations

import logging
from typing import override

from conftest import make_action_context

from yate.config import YateConfig
from yate.editor_lsp.manager import LspManager
from yate.keymaps.base import Keymap
from yate.keymaps.registry import KeymapSet
from yate.registries import ActionRegistry, CommandRegistry
from yate.session import EditorSession
from yate.services.extension_bridges import (
    HighlightExtensionBridge,
    LspExtensionBridge,
    SpriteExtensionBridge,
    SyntaxExtensionBridge,
)
from yate.services.extensions import ExtensionAPI, ExtensionContext
from yate.services.workspace import Workspace


class _LogCapture(logging.Handler):
    """Collect records from one logger.

    The ``yate`` root logger never propagates (``propagate = False``, see
    ``yate/logs.py``), so pytest's caplog cannot see child-logger records;
    attach this instead (the same pattern ``tests/test_extensions.py`` uses).
    """

    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    @override
    def emit(self, record: logging.LogRecord) -> None:
        """Collect every record handed to this handler."""
        self.records.append(record)


def _extension_api(
    messages: list[str] | None = None,
) -> tuple[ExtensionAPI, ActionRegistry, CommandRegistry, KeymapSet]:
    """An ExtensionAPI over real registries (the test_extensions.py shape).

    *messages*, when given, collects everything the API reports on the
    message line.
    """
    session = EditorSession(YateConfig())
    session.new_buffer()
    keymaps = KeymapSet({"vsc": Keymap(), "vim": Keymap()}, "vsc")
    actions = ActionRegistry()
    commands = CommandRegistry()
    ctx = ExtensionContext(
        session=session,
        workspace=Workspace(),
        lsp=LspManager(),
        keymaps=keymaps,
        actions=actions,
        commands=commands,
        message=(lambda text: messages.append(text)) if messages is not None
        else (lambda _text: None),
        run_shell=lambda _command, _show: None,
        open_path=lambda _path: None,
        save=lambda: None,
    )
    return ExtensionAPI(ctx), actions, commands, keymaps


def _noop(_ctx: object) -> None:
    """An inert action callback."""
    pass


# --- bind_key ----------------------------------------------------------------


def test_bind_key_decorator_form_registers_binding() -> None:
    """``callback=None`` turns ``bind_key`` into a registering decorator."""
    api, _actions, _commands, keymaps = _extension_api()
    hits: list[str] = []

    @api.bind_key("ctrl+shift+t", keymap="vsc")
    def _bound(_ctx: object) -> None:
        hits.append("t")

    vsc = keymaps.get("vsc")
    assert vsc is not None
    binding = vsc.lookup("ctrl+shift+t")
    assert binding is not None
    action = binding.action
    assert callable(action)
    action(make_action_context())
    assert hits == ["t"]


def test_bind_key_both_targets_two_keymaps() -> None:
    """``keymap="both"`` registers the callback in vsc and vim alike."""
    api, _actions, _commands, keymaps = _extension_api()
    hits: list[str] = []

    def _fn(_ctx: object) -> None:
        hits.append("both")

    api.bind_key("ctrl+shift+b", _fn, keymap="both")
    for name in ("vsc", "vim"):
        km = keymaps.get(name)
        assert km is not None
        binding = km.lookup("ctrl+shift+b")
        assert binding is not None
        action = binding.action
        assert callable(action)
        action(make_action_context())
    # both keymaps dispatch into the very same callback
    assert hits == ["both", "both"]


def test_bind_key_normal_alias_binds_vsc_only() -> None:
    """The legacy ``normal`` alias targets vsc; vim keeps its own binding."""
    api, _actions, _commands, keymaps = _extension_api()

    def _sentinel(_ctx: object) -> None:
        pass

    vim = keymaps.get("vim")
    assert vim is not None
    vim.add_binding("ctrl+shift+n", _sentinel, "builtin sentinel", "test")

    hits: list[str] = []

    def _fn(_ctx: object) -> None:
        hits.append("normal")

    api.bind_key("ctrl+shift+n", _fn, keymap="normal")

    vsc = keymaps.get("vsc")
    assert vsc is not None
    binding = vsc.lookup("ctrl+shift+n")
    assert binding is not None
    action = binding.action
    assert callable(action)
    action(make_action_context())
    assert hits == ["normal"]
    # the pre-existing vim binding survived untouched
    kept = vim.lookup("ctrl+shift+n")
    assert kept is not None
    assert kept.action is _sentinel


def test_bind_key_positional_keymap_argument_binds() -> None:
    """The Lua bridge calls ``bind_key(spec, fn, keymap)`` positionally."""
    api, _actions, _commands, keymaps = _extension_api()
    hits: list[str] = []

    def _fn(_ctx: object) -> None:
        hits.append("g")

    api.bind_key("g", _fn, "vim")
    vim = keymaps.get("vim")
    assert vim is not None
    binding = vim.lookup("g")
    assert binding is not None
    action = binding.action
    assert callable(action)
    action(make_action_context())
    assert hits == ["g"]
    # the positional keymap replaced the "vsc" default, not added to it
    vsc = keymaps.get("vsc")
    assert vsc is not None
    assert vsc.lookup("g") is None


# --- command / action registration -------------------------------------------


def test_command_decorator_registers_raw_args_command() -> None:
    """``@api.command`` registers a ``:`` command taking the raw args."""
    api, _actions, commands, _keymaps = _extension_api()
    received: list[str] = []

    @api.command("ext_cmd")
    def _handler(args: str) -> None:
        received.append(args)

    registered = commands.get("ext_cmd")
    assert registered is not None
    registered[0]("with args")
    assert received == ["with args"]


def test_register_command_default_description_applies() -> None:
    """A blank description falls back to "extension command"."""
    api, _actions, commands, _keymaps = _extension_api()

    def _fn(_args: str) -> None:
        pass

    api.register_command("ext_cmd2", _fn)
    registered = commands.get("ext_cmd2")
    assert registered is not None
    assert registered[1] == "extension command"


def test_register_action_default_description_applies() -> None:
    """A blank description falls back to "extension action"."""
    api, actions, _commands, _keymaps = _extension_api()
    api.register_action("ext_act", _noop)
    registered = actions.get("ext_act")
    assert registered is not None
    assert registered.description == "extension action"


# --- accessors ---------------------------------------------------------------


def test_accessors_forward_to_context() -> None:
    """The narrow accessors forward to the context; bridges are bridges."""
    api, _actions, _commands, keymaps = _extension_api()
    ctx = api.app
    assert api.buffer is ctx.session.buffer
    assert api.doc is ctx.session.doc
    assert api.workspace is ctx.workspace
    assert api.keymaps is keymaps
    assert api.keymaps is ctx.keymaps
    assert api.app is ctx
    assert isinstance(api.lsp, LspExtensionBridge)
    assert isinstance(api.highlight, HighlightExtensionBridge)
    assert isinstance(api.syntax, SyntaxExtensionBridge)
    assert isinstance(api.sprites, SpriteExtensionBridge)


# --- rollback scope (audit A13) -----------------------------------------------


def test_start_scope_second_call_drops_stale_pending_with_warning() -> None:
    """A second start_scope warns and drops the stale pending undo entries."""
    api, actions, _commands, _keymaps = _extension_api()
    capture = _LogCapture()
    logger = logging.getLogger("yate.services.extension_api")
    logger.addHandler(capture)
    try:
        api.start_scope()
        api.register_action("x", _noop)
        api.start_scope()  # must not raise
        api.rollback_scope()
    finally:
        logger.removeHandler(capture)

    warns = [record for record in capture.records if record.levelno == logging.WARNING]
    assert len(warns) == 1
    assert warns[0].name == "yate.services.extension_api"
    assert "extension scope restarted" in warns[0].getMessage()
    # the stale undo entries were dropped: the rollback above left x alone
    assert actions.get("x") is not None


def test_rollback_scope_without_active_scope_is_noop() -> None:
    """``rollback_scope`` without an active scope is a no-op."""
    api, actions, _commands, _keymaps = _extension_api()
    api.register_action("kept", _noop)  # no scope active: nothing recorded
    api.rollback_scope()  # must not raise
    assert actions.get("kept") is not None
