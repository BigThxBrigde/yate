"""Extension-visible API contract.

:class:`ExtensionContext` is the concrete service bundle handed to a
running extension, :class:`ExtensionAPI` is the surface scripts program
against, and the rollback-scope aliases support the loader's A13
snapshot-restore semantics.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from yate.editor_lsp.manager import LspManager
from yate.keymaps.base import KeyBinding, Keymap
from yate.keymaps.registry import KeymapSet
from yate.logs import tracing
from yate.registries import Action, ActionRegistry, CommandFunc, CommandRegistry
from yate.services.extension_bridges import (
    HighlightExtensionBridge,
    LspExtensionBridge,
    SpriteExtensionBridge,
    SyntaxExtensionBridge,
)
from yate.services.shell import ShellResult
from yate.services.workspace import Workspace
from yate.session import EditorSession

#: Trace logger ("yate.services.extension_api"); silent unless yate_trace is on.
log = tracing.get_logger(__name__)

#: One undo step of a loading scope: drop whatever a single ``api.register_*``
#: / ``api.bind_key`` call just added (A13 snapshot-restore rollback).
type RollbackHook = Callable[[], None]

#: ``api.command`` decorator: takes the handler, returns it unchanged.
type CommandDecorator = Callable[[CommandFunc], CommandFunc]

#: An extension-supplied callback of unknown shape.  Extension code is a
#: user-code boundary: the loader registers and forwards it without
#: inspecting it, so the shape stays deliberately open (the ``Any`` here is
#: the same one ``bind_key`` already carries in its ``noqa`` note).
type AnyCallback = Callable[..., Any]


@dataclass
class ExtensionContext:
    """The concrete services an extension script drives.

    Built by the editor once everything is constructed and handed to
    :class:`ExtensionAPI`; extensions reach it through ``api.app`` (advanced
    use) or through the narrow accessors on the API.
    """

    session: EditorSession
    workspace: Workspace
    lsp: LspManager
    keymaps: KeymapSet
    actions: ActionRegistry
    commands: CommandRegistry
    #: ``message(text)`` -- report on the message line.
    message: Callable[[str], None]
    #: ``run_shell(command, show_output)`` -- synchronous shell command.
    run_shell: Callable[[str, bool], ShellResult | None]
    #: ``open_path(path)`` -- open a file/folder in the editor.
    open_path: Callable[[Path], None]
    #: ``save()`` -- save the active document.
    save: Callable[[], None]


class ExtensionAPI:
    """The surface exposed to extension scripts."""

    def __init__(self, ctx: ExtensionContext) -> None:
        self._ctx = ctx
        self._lsp = LspExtensionBridge(ctx.lsp)
        self._highlight = HighlightExtensionBridge()
        self._syntax = SyntaxExtensionBridge()
        self._sprites = SpriteExtensionBridge()
        #: Registration rollback scope (audit A13): undo thunks recorded
        #: while one ``setup`` runs; ``None`` when no scope is active (the
        #: normal state outside
        #: :meth:`ExtensionLoader.load_file
        #: <yate.services.extension_loader.ExtensionLoader.load_file>`).
        self._scope: list[RollbackHook] | None = None

    # ------------------------------------------------------- rollback scope

    def start_scope(self) -> None:
        """Begin recording registrations for rollback (loader use, A13).

        A stale active scope (defensive: ``load_file`` does not re-enter)
        is dropped with a warning.
        """
        if self._scope is not None:
            log.warning(
                "extension scope restarted: %d pending undo entries dropped",
                len(self._scope),
            )
        self._scope = []

    def end_scope(self) -> None:
        """Accept the recorded registrations (successful ``setup``)."""
        self._scope = None

    def rollback_scope(self) -> None:
        """Undo the recorded registrations in reverse order (audit A13).

        Snapshot-restore semantics: a registration that replaced an
        earlier entry restores that entry; a brand-new registration is
        removed.  A no-op when no scope is active.  Public because the
        loader (:mod:`yate.services.extension_loader`) drives the scope.
        """
        if self._scope is None:
            return
        for undo in reversed(self._scope):
            undo()
        self._scope = None

    def _record_action_snapshot(self, name: str) -> None:
        """Record the undo thunk for an action registration (audit A13)."""
        if self._scope is None:
            return
        previous = self._ctx.actions.get(name)

        def undo(
            name: str = name, previous: Action | None = previous
        ) -> None:
            if previous is None:
                self._ctx.actions.unregister(name)
            else:
                self._ctx.actions.register(name, previous.func, previous.description)

        self._scope.append(undo)

    def _record_command_snapshot(self, name: str) -> None:
        """Record the undo thunk for a ``:`` command registration (A13)."""
        if self._scope is None:
            return
        previous = self._ctx.commands.get(name)

        def undo(
            name: str = name, previous: tuple[CommandFunc, str] | None = previous
        ) -> None:
            if previous is None:
                self._ctx.commands.unregister(name)
            else:
                self._ctx.commands.register(name, previous[0], previous[1])

        self._scope.append(undo)

    # ------------------------------------------------------------- accessors

    @property
    def app(self) -> ExtensionContext:
        """The host context (advanced use; prefer the narrow accessors)."""
        return self._ctx

    @property
    def buffer(self):
        """The buffer of the active document."""
        return self._ctx.session.buffer

    @property
    def doc(self):
        """The active document."""
        return self._ctx.session.doc

    @property
    def workspace(self):
        """The open workspace."""
        return self._ctx.workspace

    @property
    def keymaps(self) -> KeymapSet:
        """The loaded keymap set (``vsc`` / ``vim``)."""
        return self._ctx.keymaps

    @property
    def lsp(self) -> LspExtensionBridge:
        """Register language servers (autocomplete/diagnostics)."""
        return self._lsp

    @property
    def highlight(self) -> HighlightExtensionBridge:
        """Register custom syntax highlighters (``api.highlight.register``)."""
        return self._highlight

    @property
    def syntax(self) -> SyntaxExtensionBridge:
        """Register tree-sitter grammars (``api.syntax.register_tree_sitter``)."""
        return self._syntax

    @property
    def sprites(self) -> SpriteExtensionBridge:
        """Register custom screensaver characters (``api.sprites.register``)."""
        return self._sprites

    # ------------------------------------------------------------ registrars

    def _guarded_callback(self, what: str, func: AnyCallback) -> AnyCallback:
        """Wrap a user callback so a runtime failure reports, never crashes.

        Load-time failures are already contained by the loader's rollback
        scope; callbacks keep running long after ``setup`` returned, so a
        raise inside one would otherwise propagate into dispatch code and
        take the whole app down.  The wrapper mirrors the loader's error
        shape (``extension <what>: <Exc>: <msg>``) on the message line and
        logs the full traceback.
        """

        def guarded(*args: Any, **kwargs: Any) -> Any:
            try:
                return func(*args, **kwargs)
            except Exception as exc:  # noqa: BLE001 - user code, never crash the app
                log.exception("extension %s callback failed", what)
                self._ctx.message(f"extension {what}: {type(exc).__name__}: {exc}")

        return guarded

    def register_action(self, name: str, func: AnyCallback, description: str = "") -> None:
        """Register a named action (usable from key maps / commands)."""
        self._record_action_snapshot(name)
        self._ctx.actions.register(
            name,
            self._guarded_callback(f"action {name}", func),
            description=description or "extension action",
        )

    def bind_key(  # noqa: Any - extension-supplied callbacks, untyped boundary
        self,
        key_spec: str,
        callback: AnyCallback | None = None,
        keymap: str = "vsc",
        description: str = "extension binding",
        category: str = "extension",
    ) -> AnyCallback:
        """Bind *key_spec* in the named keymap (``vsc``/``vim``/``both``).

        Can be used as a decorator when *callback* is omitted.  The legacy
        name ``normal`` is accepted as an alias for ``vsc``.  An unknown
        keymap name binds nothing and is reported as a warning listing the
        registered names.  The parameters after *callback* also accept
        positional arguments: Lua extension scripts cannot pass keyword
        arguments through the lupa bridge, so the Lua API library calls
        this as ``bind_key(spec, fn, keymap)``; Python callers keep using
        keywords.
        """

        def _do(func: AnyCallback) -> AnyCallback:
            if keymap == "both":
                targets = ["vsc", "vim"]
            else:
                targets = ["vsc"] if keymap == "normal" else [keymap]
            for target in targets:
                km = self._ctx.keymaps.get(target)
                if km is None:
                    # A misspelled keymap name used to bind nothing and stay
                    # silent (S34); name the registered keymaps so the typo
                    # is visible in the trace log.
                    log.warning(
                        "bind_key: unknown keymap %r (available: %s)",
                        target,
                        ", ".join(self._ctx.keymaps.names()),
                    )
                    continue
                raw = km.normalize_key(key_spec)
                previous = km.lookup(raw)
                if self._scope is not None:
                    def undo(
                        km: Keymap = km,
                        raw: str = raw,
                        previous: KeyBinding | None = previous,
                    ) -> None:
                        if previous is None:
                            km.remove_binding(raw)
                        else:
                            km.add_binding(
                                raw, previous.action, previous.description,
                                previous.category,
                            )

                    self._scope.append(undo)
                km.add_binding(
                    key_spec, self._guarded_callback(f"binding {key_spec}", func),
                    description, category,
                )
            return func

        return _do(callback) if callback is not None else _do

    def command(
        self, name: str, description: str = "extension command"
    ) -> CommandDecorator:
        """Decorator registering a ``:`` command.

        The function receives the raw argument string after the command name.
        """

        def _decorator(func: CommandFunc) -> CommandFunc:
            self._record_command_snapshot(name)
            self._ctx.commands.register(
                name, self._guarded_callback(f"command {name}", func), description
            )
            return func

        return _decorator

    def register_command(self, name: str, func: CommandFunc, description: str = "") -> None:
        """Register a ``:`` command (the non-decorator form)."""
        self._record_command_snapshot(name)
        self._ctx.commands.register(
            name,
            self._guarded_callback(f"command {name}", func),
            description or "extension command",
        )

    # -------------------------------------------------------------- services

    def message(self, text: str) -> None:
        """Show *text* on the message line."""
        self._ctx.message(text)

    def shell(self, command: str) -> object:
        """Run *command* synchronously without showing its output."""
        return self._ctx.run_shell(command, False)

    def open_path(self, path: str | Path) -> None:
        """Open *path* (file or folder) in the editor."""
        self._ctx.open_path(Path(path))

    def save(self) -> None:
        """Save the active document."""
        self._ctx.save()
