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
from typing import Any, Callable, Mapping, Optional, Protocol, Sequence, cast

from yate.actions import ActionRegistry
from yate.editor_core import Document
from yate.editor_core.buffer import TextBuffer
from yate.editor_lsp import LspManager
from yate.editor_lsp.client import DEFAULT_ROOT_MARKERS, ServerConfig
from yate.editor_syntax import (
    LangSpec,
    available_filetypes,
    prefer_regex,
    register_language,
)
from yate.editor_syntax.ts_backend import load_language_from_grammar
from yate.keymaps.base import Keymap
from yate.logs import tracing
from yate.services.shell import ShellResult
from yate.services.workspace import Workspace

CommandFunc = Callable[[str], object]

#: Trace logger ("yate.services.extensions"); silent unless yate_trace is on.
log = tracing.get_logger(__name__)


class ExtensionHost(Protocol):
    """The application surface extension scripts can drive."""

    lsp: LspManager
    workspace: Workspace
    keymaps: dict[str, Keymap]
    actions: ActionRegistry

    @property
    def buffer(self) -> TextBuffer: ...

    @property
    def doc(self) -> Document: ...

    def register_command(self, name: str, func: CommandFunc,
                         description: str) -> None: ...

    def message(self, text: str, kind: str = "info") -> None: ...

    def run_shell_command(
        self, command: str, show_output: bool = True
    ) -> Optional[ShellResult]: ...

    def open_path(self, path: Path) -> None: ...

    def save_document(self) -> None: ...


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

    def __init__(self, host: ExtensionHost) -> None:
        self._host = host
        self._lsp = LspExtensionBridge(host.lsp)
        self._highlight = HighlightExtensionBridge()
        self._syntax = SyntaxExtensionBridge()

    # ------------------------------------------------------------- accessors

    @property
    def app(self) -> ExtensionHost:
        """The application host (advanced use; prefer the narrow accessors)."""
        return self._host

    @property
    def buffer(self):
        return self._host.buffer

    @property
    def doc(self):
        return self._host.doc

    @property
    def workspace(self):
        return self._host.workspace

    @property
    def keymaps(self) -> dict[str, Keymap]:
        return self._host.keymaps

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
        self._host.actions.register(name, func, description=description or "extension action")

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
                km = self._host.keymaps.get(target)
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
            self._host.register_command(name, func, description)
            return func

        return _decorator

    def register_command(self, name: str, func: CommandFunc, description: str = "") -> None:
        self._host.register_command(name, func, description or "extension command")

    # -------------------------------------------------------------- services

    def message(self, text: str) -> None:
        self._host.message(text)

    def shell(self, command: str) -> object:
        return self._host.run_shell_command(command, show_output=False)

    def open_path(self, path: str | Path) -> None:
        self._host.open_path(Path(path))

    def save(self) -> None:
        self._host.save_document()


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
            # 动态边界：用户扩展模块的 setup 钩子通过 getattr 获取，类型未知
            setup: Any = getattr(module, "setup", None)
            if not callable(setup):
                raise AttributeError(f"{path.name} has no setup(api) function")
            setup(self.api)  # dynamic user module (narrowed via callable() above)
            record.module = module
            # 动态边界：用户扩展模块的 teardown 钩子通过 getattr 获取，类型未知。
            # 仅在 setup 成功后捕获——setup 失败的扩展未初始化任何资源，
            # teardown_all() 不应调用它的 teardown。
            hook: Any = getattr(module, "teardown", None)
            if callable(hook):
                # 动态边界收窄：callable(hook) 只能推出 (...)->object，
                # 显式 cast 到文档约定的 teardown(api) 签名。
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
            except Exception:
                pass
