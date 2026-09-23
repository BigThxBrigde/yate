"""Custom, extensible Python script support.

An extension is any ``.py`` file exposing a ``setup(api)`` function (and an
optional ``teardown(api)``).  ``setup`` receives an :class:`ExtensionAPI`
through which it can register actions, key bindings, ``:`` commands, run
shell commands and manipulate the active document.

Example bundled extension ``yate/extensions/uppercase.py``::

    def setup(api):
        @api.command("upper", "Uppercase the selection (or whole line)")
        def upper(args):
            buf = api.buffer
            text = buf.selected_text()
            if text is None:
                row = buf.row
                text = buf.lines[row]
                buf.lines[row] = text.upper()
                buf.mark_content_changed()  # direct line edit: refresh caches
            else:
                api.buffer.insert_text(text.upper())
            api.message("uppercased!")

        api.bind_key("<alt-u>", lambda ctx: upper(""), keymap="vsc")
"""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Mapping, Optional, Sequence, cast

from yate.config import YateConfig
from yate.editor_lsp import LspManager
from yate.editor_lsp.client import DEFAULT_ROOT_MARKERS, ServerConfig
from yate.editor_syntax import (
    LangSpec,
    available_filetypes,
    prefer_regex,
    register_language,
)
from yate.editor_syntax.ts_backend import load_language_from_grammar
from yate.keymaps.registry import KeymapSet
from yate.logs import tracing
from yate.paths import bundled_extensions_dir
from yate.services.trust import is_trusted
from yate.registries import ActionRegistry, CommandFunc, CommandRegistry
from yate.services.shell import ShellResult
from yate.services.workspace import Workspace
from yate.session import EditorSession

#: Trace logger ("yate.services.extensions"); silent unless yate_trace is on.
log = tracing.get_logger(__name__)


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
    run_shell: Callable[[str, bool], Optional[ShellResult]]
    #: ``open_path(path)`` -- open a file/folder in the editor.
    open_path: Callable[[Path], None]
    #: ``save()`` -- save the active document.
    save: Callable[[], None]


class LspExtensionBridge:
    """``api.lsp`` -- register language servers from an extension."""

    def __init__(self, lsp: LspManager) -> None:
        self._lsp = lsp

    def register_server(
        self,
        name: str,
        *,
        command: str,
        args: Optional[Sequence[str]] = None,
        filetypes: Sequence[str],
        language_ids: Optional[Mapping[str, str]] = None,
        initialization_options: Any = None,
        settings: Any = None,
        env: Optional[Mapping[str, str]] = None,
        root_markers: Optional[Sequence[str]] = None,
    ) -> None:
        """Register an LSP server (lazily spawned on first matching file).

        ``command`` may be empty when the extension could not find an
        executable; the registration stays visible and fails lazily without
        disturbing the user.
        """
        self._lsp.register_server(ServerConfig(
            name=name,
            command=command,
            args=list(args) if args is not None else [],
            filetypes=list(filetypes),
            language_ids=dict(language_ids) if language_ids is not None else {},
            initialization_options=initialization_options,
            settings=settings,
            env=dict(env) if env is not None else None,
            root_markers=list(root_markers) if root_markers is not None
            else list(DEFAULT_ROOT_MARKERS),
        ))

    def statuses(self) -> dict[str, str]:
        """``{server name: state name}`` for every registered server."""
        return {name: state.value for name, state in self._lsp.states().items()}

    def has_state(self, name: str, state: str) -> bool:
        current = self._lsp.states().get(name)
        return current is not None and current.value == state


class HighlightExtensionBridge:
    """``api.highlight`` -- register custom syntax highlighters.

    The built-in tokenizer is declarative: a :class:`LangSpec` lists comment
    markers, keyword/type/builtin word sets and a few lexical flags, and the
    engine handles strings, numbers, comments and multiline state for free.
    See ``yate/extensions/csharp_highlight.py`` for a complete example.
    """

    #: Re-exported so extensions can build specs via ``api.highlight.LangSpec``.
    LangSpec = LangSpec

    def register(self, spec: LangSpec, *extensions: str) -> None:
        """Register *spec* under extension keys (``"cs"``, ``"csx"``, ...).

        Re-registering an existing key replaces its highlighter, so a custom
        language can override a built-in one. The type is immediately usable
        from ``:set filetype=`` and resolved by both extension key and the
        spec's language ``name``.  The keys are also pinned to the regex
        backend, so a deliberately registered declarative highlighter wins
        over the built-in tree-sitter registration for the same key.
        """
        register_language(spec, *extensions)
        prefer_regex(*extensions)

    @staticmethod
    def spec(**kwargs: Any) -> LangSpec:
        """Build a :class:`LangSpec` with keyword arguments (``name=...``)."""
        return LangSpec(**kwargs)

    @staticmethod
    def available() -> list[str]:
        """All extension keys and language names accepted by ``:set filetype``."""
        return available_filetypes()


class SyntaxExtensionBridge:
    """``api.syntax`` -- tree-sitter grammars for custom languages.

    Complements :class:`HighlightExtensionBridge`: where ``api.highlight``
    registers a simple declarative word-list spec (regex backend),
    ``api.syntax`` binds a real tree-sitter grammar plus a
    ``highlights.scm`` query for syntax-tree based highlighting.  Requires
    the optional ``tree_sitter`` dependency (``pip install yate[ts]``).
    """

    def register_tree_sitter(
        self,
        name: str,
        *,
        grammar: str,
        extensions: Sequence[str],
        query: str,
        capture_map: Optional[dict[str, str]] = None,
    ) -> None:
        """Register a tree-sitter grammar + query as language *name*.

        *grammar* is either an importable grammar pack name
        (``"tree_sitter_yatesh"``) or a path to a compiled shared library
        (``.dll`` / ``.so`` / ``.dylib`` built with ``tree-sitter generate``
        plus a C compiler; its C entry point must be named
        ``tree_sitter_<name>``).

        *query* is a ``highlights.scm`` source string, or a path to one
        (resolve it against your extension's ``__file__`` for robustness).

        *extensions* are the file extensions (``"ysh"``, ...) that select
        the language; they become available from ``:set filetype=`` with a
        minimal regex fallback should the grammar fail to load.

        *capture_map* optionally overrides/extends the default
        capture-name -> token-kind mapping (see
        ``yate/editor_syntax/ts_backend/languages.py``).

        Raises ``RuntimeError`` when ``tree_sitter`` is not installed,
        ``ValueError`` for unresolvable grammars, and query errors straight
        through -- all surfaced as ``extension <name>: ...`` messages.
        """
        query_src = query
        query_file = Path(query)
        if query_file.is_file():
            query_src = query_file.read_text(encoding="utf-8")
        load_language_from_grammar(
            name,
            grammar,
            query_src,
            capture_map=capture_map,
            extensions=tuple(extensions),
        )


class ExtensionAPI:
    """The surface exposed to extension scripts."""

    def __init__(self, ctx: ExtensionContext) -> None:
        self._ctx = ctx
        self._lsp = LspExtensionBridge(ctx.lsp)
        self._highlight = HighlightExtensionBridge()
        self._syntax = SyntaxExtensionBridge()

    # ------------------------------------------------------------- accessors

    @property
    def app(self) -> ExtensionContext:
        """The host context (advanced use; prefer the narrow accessors)."""
        return self._ctx

    @property
    def buffer(self):
        return self._ctx.session.buffer

    @property
    def doc(self):
        return self._ctx.session.doc

    @property
    def workspace(self):
        return self._ctx.workspace

    @property
    def keymaps(self) -> KeymapSet:
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

    # ------------------------------------------------------------ registrars

    def register_action(self, name: str, func: Callable[..., Any], description: str = "") -> None:
        """Register a named action (usable from key maps / commands)."""
        self._ctx.actions.register(name, func, description=description or "extension action")

    def bind_key(
        self,
        key_spec: str,
        callback: Optional[Callable[..., Any]] = None,
        *,
        keymap: str = "vsc",
        description: str = "extension binding",
        category: str = "extension",
    ) -> Callable[..., Any]:
        """Bind *key_spec* in the named keymap (``vsc``/``vim``/``both``).

        Can be used as a decorator when *callback* is omitted.  The legacy
        name ``normal`` is accepted as an alias for ``vsc``.
        """

        def _do(func: Callable[..., Any]) -> Callable[..., Any]:
            if keymap == "both":
                targets = ["vsc", "vim"]
            else:
                targets = ["vsc"] if keymap == "normal" else [keymap]
            for target in targets:
                km = self._ctx.keymaps.get(target)
                if km is not None:
                    km.add_binding(key_spec, func, description, category)
            return func

        return _do(callback) if callback is not None else _do

    def command(
        self, name: str, description: str = "extension command"
    ) -> Callable[[CommandFunc], CommandFunc]:
        """Decorator registering a ``:`` command.

        The function receives the raw argument string after the command name.
        """

        def _decorator(func: CommandFunc) -> CommandFunc:
            self._ctx.commands.register(name, func, description)
            return func

        return _decorator

    def register_command(self, name: str, func: CommandFunc, description: str = "") -> None:
        self._ctx.commands.register(name, func, description or "extension command")

    # -------------------------------------------------------------- services

    def message(self, text: str) -> None:
        self._ctx.message(text)

    def shell(self, command: str) -> object:
        return self._ctx.run_shell(command, False)

    def open_path(self, path: str | Path) -> None:
        self._ctx.open_path(Path(path))

    def save(self) -> None:
        self._ctx.save()


@dataclass
class LoadedExtension:
    name: str
    path: Path
    module: Optional[ModuleType] = None
    error: Optional[str] = None
    teardown: Optional[Callable[[ExtensionAPI], None]] = None


@dataclass
class ExtensionLoader:
    """Discovers and loads extension scripts from disk."""

    api: ExtensionAPI
    loaded: list[LoadedExtension] = field(default_factory=list[LoadedExtension])

    def load_directory(
        self,
        directory: Path,
        *,
        exclude: Optional[Sequence[str]] = None,
    ) -> list[LoadedExtension]:
        """Load every ``*.py`` script in *directory* (sorted by name).

        Files whose stem is in *exclude* are skipped (used for bundled
        extensions turned off with ``disabled_extensions``); underscore-
        prefixed files are always skipped.
        """
        directory = Path(directory)
        if not directory.is_dir():
            return []
        skipped: set[str] = set(exclude) if exclude is not None else set()
        results: list[LoadedExtension] = []
        for path in sorted(directory.glob("*.py")):
            if path.name.startswith("_") or path.stem in skipped:
                continue
            results.append(self.load_file(path))
        return results

    def load_file(self, path: Path) -> LoadedExtension:
        path = Path(path)
        # The same script can be reached via several sources (an rc-declared
        # path, the default ./extensions directory, a --ext flag); loading it
        # twice would double-register commands and bindings.
        try:
            resolved = path.resolve()
        except OSError:
            resolved = path.absolute()
        for existing in self.loaded:
            try:
                if existing.path.resolve() == resolved:
                    return existing
            except OSError:
                continue
        mod_name = f"yate_ext_{path.stem}"
        record = LoadedExtension(name=path.stem, path=path)
        log.debug("loading extension: %s", path)
        try:
            spec = importlib.util.spec_from_file_location(mod_name, path)
            if spec is None or spec.loader is None:
                raise ImportError(f"cannot create module spec for {path}")
            module = importlib.util.module_from_spec(spec)
            sys.modules[mod_name] = module
            spec.loader.exec_module(module)
            # Dynamic boundary: the user extension's setup hook comes from
            # getattr, so its type is unknown.
            setup: Any = getattr(module, "setup", None)
            if not callable(setup):
                raise AttributeError(f"{path.name} has no setup(api) function")
            setup(self.api)  # dynamic user module (narrowed via callable() above)
            record.module = module
            # Dynamic boundary: the user extension's teardown hook comes from
            # getattr, so its type is unknown.  It is captured only after a
            # successful setup -- a failed extension never initialized any
            # resource, so teardown_all() must not call its teardown.
            hook: Any = getattr(module, "teardown", None)
            if callable(hook):
                # Dynamic-boundary narrowing: callable(hook) only infers
                # (...)->object, so cast explicitly to the documented
                # teardown(api) signature.
                record.teardown = cast(
                    Callable[[ExtensionAPI], None], hook
                )
        except Exception as exc:  # extensions are user code - never crash the app
            record.error = f"{type(exc).__name__}: {exc}"
            log.exception("extension failed to load: %s", path)
        else:
            log.debug("extension loaded: %s", path)
        self.loaded.append(record)
        return record

    def teardown_all(self) -> None:
        """Call the optional ``teardown(api)`` of every loaded extension.

        Only extensions whose ``setup`` succeeded get their hook invoked.
        Each teardown is isolated: a failing hook must not prevent the
        remaining extensions (or the application shutdown itself) from
        cleaning up, mirroring the error tolerance of ``load_file``.
        """
        for record in self.loaded:
            if record.error is not None:
                continue
            teardown = record.teardown
            if teardown is None:
                continue
            try:
                teardown(self.api)  # dynamic user hook (captured post-setup)
            except Exception:  # noqa: BLE001 - isolate per-extension teardown
                log.exception("extension %s teardown failed", record.name)


def load_startup_extensions(
    loader: ExtensionLoader,
    config: YateConfig,
    *,
    ext_dirs: Sequence[Path] = (),
    ext_files: Sequence[Path] = (),
) -> list[str]:
    """Load every configured extension source, in the documented order.

    rc-declared paths load first (user rc then project rc), followed by the
    bundled defaults, the trusted project directory, the user directory and
    the explicit CLI paths.  Returns the user-facing messages (load errors,
    shadowed rc-declared scripts, untrusted-workspace skips); the caller
    reports them on the message line.  The same order is used by a normal
    start and by ``yate --diag``, so the diagnostics always show exactly
    what a start would load.
    """
    messages: list[str] = []

    def _report(records: list[LoadedExtension]) -> None:
        for record in records:
            if record.error:
                messages.append(f"extension {record.name}: {record.error}")

    for path in config.extension_paths:
        if path.is_dir():
            _report(loader.load_directory(path))
        elif path.is_file():
            _report([loader.load_file(path)])
        else:
            messages.append(f"extension path not found: {path}")

    # Extensions shipped with yate (inside the package / the PyInstaller
    # bundle). Individual defaults can be switched off in yaterc with
    # ``disabled_extensions``; same-named scripts loaded afterwards from a
    # project or user directory get the last word on registrations.
    bundled = bundled_extensions_dir()
    if bundled.is_dir():
        # Registrars are last-write-wins, so a bundled default loading
        # *after* an rc-declared same-stem script would silently take over
        # its commands/highlight/server. Name the conflict and point at the
        # documented opt-out instead of letting the user script lose without
        # explanation.
        rc_owners = {record.name: record for record in loader.loaded}
        records = loader.load_directory(bundled, exclude=config.disabled_extensions)
        for record in records:
            owner = rc_owners.get(record.name)
            # Same resolved path means the rc entry *is* the bundled script
            # (e.g. extension_paths pointing at the bundled directory):
            # de-duplication hands back the same record, which must not be
            # reported as shadowing itself.
            if (
                owner is not None
                and record.error is None
                and owner.path.resolve() != record.path.resolve()
            ):
                messages.append(
                    f"extension {record.name}: the rc-declared script "
                    f"{owner.path} is shadowed by the bundled default; "
                    f'add disabled_extensions = ["{record.name}"] to '
                    "yaterc to use the rc-declared version"
                )
        _report(records)

    directories: list[Path] = [*ext_dirs]
    # One resolved spelling for both the trust decision and the load: a
    # symlinked or swapped-in cwd must not be judged as one path and loaded
    # as another (the trust store holds resolved roots too).
    cwd = Path.cwd().resolve()
    cwd_extensions = cwd / "extensions"
    if cwd_extensions.is_dir():
        # Workspace trust: opening a repository must not execute that
        # repository's own code, so a project ``./extensions`` auto-loads
        # only in workspaces the user trusted via ``:trust`` (the list
        # lives in ~/.yate/trusted_workspaces).  rc-declared and CLI
        # paths are deliberate user actions and stay unconditional.
        if is_trusted(cwd):
            directories.append(cwd_extensions)
        else:
            messages.append(
                f"extensions: skipped untrusted {cwd_extensions} "
                "(run :trust to load them)"
            )
    directories.append(Path.home() / ".yate" / "extensions")
    for directory in directories:
        _report(loader.load_directory(directory))
    for file in ext_files:
        _report([loader.load_file(file)])
    return messages
