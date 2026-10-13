"""Unit tests for ``yate.services.extension_api`` (the ExtensionAPI surface).

Covers the gap ``tests/test_extensions.py`` does not: the ``bind_key``
decorator form and its ``both`` / ``normal`` / positional-keymap variants,
the ``command`` decorator versus ``register_command``, the default
descriptions, the narrow accessors, and the A13 rollback-scope edge cases
(stale-scope warning, no-scope idempotence).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import override

from conftest import make_action_context

from yate.config import YateConfig
from yate.editor_lsp.manager import LspManager
from yate.keymaps.base import Keymap
from yate.keymaps.registry import KeymapSet
from yate.registries import ActionRegistry, CommandRegistry
from yate.session import EditorSession
from yate.services.events import EditorEvent
from yate.services.extension_bridges import (
    ActionExtensionBridge,
    ClipboardExtensionBridge,
    DocsExtensionBridge,
    HighlightExtensionBridge,
    LspExtensionBridge,
    SpriteExtensionBridge,
    SyntaxExtensionBridge,
    ThemeExtensionBridge,
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
    *,
    run_action: Callable[[str], bool] | None = None,
) -> tuple[ExtensionAPI, ActionRegistry, CommandRegistry, KeymapSet]:
    """An ExtensionAPI over real registries (the test_extensions.py shape).

    *messages*, when given, collects everything the API reports on the
    message line.  *run_action*, when given, is the dispatch callback the
    context carries from construction (the bridges snapshot it, so it
    cannot be swapped in later).
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
        run_action=run_action if run_action is not None
        else (lambda _name: False),
        set_theme=lambda _name: None,
        active_theme_name=lambda: "mocha",
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


# --- api surface additions ----------------------------------------------------


def test_events_bridge_reexports_editor_event() -> None:
    """``api.events.EditorEvent`` is the services.events enum itself."""
    api, _actions, _commands, _keymaps = _extension_api()
    assert api.events.EditorEvent is EditorEvent


def test_new_bridge_properties_return_bridge_instances() -> None:
    """The four new accessors hand out the matching bridge instances."""
    api, _actions, _commands, _keymaps = _extension_api()
    assert isinstance(api.theme, ThemeExtensionBridge)
    assert isinstance(api.clipboard, ClipboardExtensionBridge)
    assert isinstance(api.docs, DocsExtensionBridge)
    assert isinstance(api.actions, ActionExtensionBridge)


# --- bind_action --------------------------------------------------------------


def test_bind_action_default_keymap_binds_vsc_only() -> None:
    """The default keymap is vsc; vim keeps its own bindings untouched."""
    api, _actions, _commands, keymaps = _extension_api()
    api.register_action("probe_act", _noop)
    api.bind_action("ctrl+shift+1", "probe_act")

    vsc = keymaps.get("vsc")
    assert vsc is not None
    binding = vsc.lookup("ctrl+shift+1")
    assert binding is not None
    assert binding.action == "probe_act"
    vim = keymaps.get("vim")
    assert vim is not None
    assert vim.lookup("ctrl+shift+1") is None


def test_bind_action_vim_binds_vim_only() -> None:
    """``keymap="vim"`` binds vim; vsc stays untouched."""
    api, _actions, _commands, keymaps = _extension_api()
    api.register_action("probe_act", _noop)
    api.bind_action("ctrl+shift+2", "probe_act", keymap="vim")

    vim = keymaps.get("vim")
    assert vim is not None
    binding = vim.lookup("ctrl+shift+2")
    assert binding is not None
    assert binding.action == "probe_act"
    vsc = keymaps.get("vsc")
    assert vsc is not None
    assert vsc.lookup("ctrl+shift+2") is None


def test_bind_action_both_targets_two_keymaps() -> None:
    """``keymap="both"`` binds the action name in vsc and vim alike."""
    api, _actions, _commands, keymaps = _extension_api()
    api.register_action("probe_act", _noop)
    api.bind_action("ctrl+shift+3", "probe_act", keymap="both")

    for name in ("vsc", "vim"):
        km = keymaps.get(name)
        assert km is not None
        binding = km.lookup("ctrl+shift+3")
        assert binding is not None
        assert binding.action == "probe_act"


def test_bind_action_unknown_action_binds_nothing_and_warns() -> None:
    """An unregistered action name binds nothing and logs a warning."""
    api, actions, _commands, keymaps = _extension_api()
    capture = _LogCapture()
    logger = logging.getLogger("yate.services.extension_api")
    logger.addHandler(capture)
    try:
        api.bind_action("ctrl+shift+4", "never_registered")
    finally:
        logger.removeHandler(capture)

    vsc = keymaps.get("vsc")
    assert vsc is not None
    assert vsc.lookup("ctrl+shift+4") is None
    warns = [record for record in capture.records if record.levelno == logging.WARNING]
    assert len(warns) == 1
    assert "unknown action" in warns[0].getMessage()
    # the misspelled name never reached the registry either
    assert actions.get("never_registered") is None


def test_bind_action_unknown_keymap_binds_nothing_and_warns() -> None:
    """An unknown keymap name binds nothing and logs a warning."""
    api, _actions, _commands, keymaps = _extension_api()
    api.register_action("probe_act", _noop)
    capture = _LogCapture()
    logger = logging.getLogger("yate.services.extension_api")
    logger.addHandler(capture)
    try:
        api.bind_action("ctrl+shift+5", "probe_act", keymap="bogus")
    finally:
        logger.removeHandler(capture)

    vsc = keymaps.get("vsc")
    assert vsc is not None
    assert vsc.lookup("ctrl+shift+5") is None
    warns = [record for record in capture.records if record.levelno == logging.WARNING]
    assert len(warns) == 1
    assert "unknown keymap" in warns[0].getMessage()


def test_bind_action_replaces_a_previous_bind_key_binding() -> None:
    """Rebinding a key from a callback to an action name swaps the entry."""
    api, _actions, _commands, keymaps = _extension_api()
    api.register_action("probe_act", _noop)
    api.bind_key("ctrl+shift+6", _noop)
    api.bind_action("ctrl+shift+6", "probe_act")

    vsc = keymaps.get("vsc")
    assert vsc is not None
    binding = vsc.lookup("ctrl+shift+6")
    assert binding is not None
    assert binding.action == "probe_act"


def test_bind_action_rollback_restores_previous_binding() -> None:
    """Rollback restores the pre-existing binding the action replaced."""
    api, _actions, _commands, keymaps = _extension_api()
    api.register_action("probe_act", _noop)
    vsc = keymaps.get("vsc")
    assert vsc is not None
    vsc.add_binding("ctrl+shift+7", "editor-back", "builtin placeholder", "test")

    api.start_scope()
    api.bind_action("ctrl+shift+7", "probe_act")
    bound = vsc.lookup("ctrl+shift+7")
    assert bound is not None
    assert bound.action == "probe_act"
    api.rollback_scope()

    restored = vsc.lookup("ctrl+shift+7")
    assert restored is not None
    assert restored.action == "editor-back"
    assert restored.category == "test"


# --- unbind_key ---------------------------------------------------------------


def test_unbind_key_removes_bound_key_and_reports_true() -> None:
    """Removing a bound key returns True and leaves the key unbound."""
    api, _actions, _commands, keymaps = _extension_api()
    api.bind_key("ctrl+shift+8", _noop)
    vsc = keymaps.get("vsc")
    assert vsc is not None

    assert api.unbind_key("ctrl+shift+8") is True
    assert vsc.lookup("ctrl+shift+8") is None


def test_unbind_key_unbound_key_reports_false() -> None:
    """Removing a never-bound key returns False."""
    api, _actions, _commands, _keymaps = _extension_api()
    assert api.unbind_key("ctrl+shift+9") is False


def test_unbind_key_both_removes_from_two_keymaps() -> None:
    """``keymap="both"`` drops the binding from vsc and vim alike."""
    api, _actions, _commands, keymaps = _extension_api()
    api.bind_key("ctrl+shift+a", _noop, keymap="both")

    assert api.unbind_key("ctrl+shift+a", keymap="both") is True
    for name in ("vsc", "vim"):
        km = keymaps.get(name)
        assert km is not None
        assert km.lookup("ctrl+shift+a") is None


def test_unbind_key_rollback_restores_the_binding() -> None:
    """Rollback brings the removed binding back (A13 restore thunk)."""
    api, _actions, _commands, keymaps = _extension_api()
    api.bind_key("ctrl+shift+b", _noop)
    vsc = keymaps.get("vsc")
    assert vsc is not None

    api.start_scope()
    assert api.unbind_key("ctrl+shift+b") is True
    assert vsc.lookup("ctrl+shift+b") is None
    api.rollback_scope()

    restored = vsc.lookup("ctrl+shift+b")
    assert restored is not None
    assert callable(restored.action)


# --- actions accessor ---------------------------------------------------------


def test_actions_run_reports_known_and_unknown() -> None:
    """``run`` answers True for a registered action, False for a ghost."""
    seen: list[tuple[str, bool]] = []

    def run_action(name: str) -> bool:
        # mirrors ``key_ui.execute_action``: known names dispatch as True
        known = name == "probe_act"
        seen.append((name, known))
        return known

    api, _actions, _commands, _keymaps = _extension_api(run_action=run_action)
    api.register_action("probe_act", _noop)

    assert api.actions.run("probe_act") is True
    assert api.actions.run("ghost") is False
    assert seen == [("probe_act", True), ("ghost", False)]
