"""Custom, extensible Python script support.

An extension is any ``.py`` file exposing a ``setup(api)`` function (and an
optional ``teardown(api)``).  ``setup`` receives an :class:`ExtensionAPI`
through which it can register actions, key bindings, ``:`` commands, run
shell commands and manipulate the active document.

Example ``extensions/uppercase.py``::

    def setup(api):
        @api.command("upper", "Uppercase the selection (or whole line)")
        def upper(args):
            buf = api.buffer
            text = buf.selected_text()
            if text is None:
                row = buf.row
                text = buf.lines[row]
                buf.lines[row] = text.upper()
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
from typing import TYPE_CHECKING, Any, Callable, Mapping, Optional, Sequence

from yate.editor_lsp.client import DEFAULT_ROOT_MARKERS, ServerConfig

if TYPE_CHECKING:
    from yate.app import YateApp
    from yate.keymaps.base import Keymap

CommandFunc = Callable[[str], object]


class LspExtensionBridge:
    """``api.lsp`` -- register language servers from an extension."""

    def __init__(self, app: "YateApp") -> None:
        self._app = app

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
        self._app.lsp.register_server(ServerConfig(
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
        return {name: state.value for name, state in self._app.lsp.states().items()}

    def has_state(self, name: str, state: str) -> bool:
        current = self._app.lsp.states().get(name)
        return current is not None and current.value == state


class ExtensionAPI:
    """The surface exposed to extension scripts."""

    def __init__(self, app: "YateApp") -> None:
        self._app = app
        self._lsp = LspExtensionBridge(app)

    # ------------------------------------------------------------- accessors

    @property
    def app(self) -> "YateApp":
        return self._app

    @property
    def buffer(self):
        return self._app.buffer

    @property
    def doc(self):
        return self._app.doc

    @property
    def workspace(self):
        return self._app.workspace

    @property
    def keymaps(self) -> dict[str, Keymap]:
        return self._app.keymaps

    @property
    def lsp(self) -> LspExtensionBridge:
        """Register language servers (autocomplete/diagnostics)."""
        return self._lsp

    # ------------------------------------------------------------ registrars

    def register_action(self, name: str, func: Callable[..., Any], description: str = "") -> None:
        """Register a named action (usable from key maps / commands)."""
        self._app.actions.register(name, func, description=description or "extension action")

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
                km = self._app.keymaps.get(target)
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
            self._app.commands.register(name, func, description)
            return func

        return _decorator

    def register_command(self, name: str, func: CommandFunc, description: str = "") -> None:
        self._app.commands.register(name, func, description or "extension command")

    # -------------------------------------------------------------- services

    def message(self, text: str) -> None:
        self._app.message(text)

    def shell(self, command: str) -> object:
        return self._app.run_shell_command(command, show_output=False)

    def open_path(self, path: str | Path) -> None:
        self._app.open_path(Path(path))

    def save(self) -> None:
        self._app.save_document()


@dataclass
class LoadedExtension:
    name: str
    path: Path
    module: Optional[ModuleType] = None
    error: Optional[str] = None


@dataclass
class ExtensionLoader:
    """Discovers and loads extension scripts from disk."""

    api: ExtensionAPI
    loaded: list[LoadedExtension] = field(default_factory=list[LoadedExtension])

    def load_directory(self, directory: Path) -> list[LoadedExtension]:
        directory = Path(directory)
        if not directory.is_dir():
            return []
        results: list[LoadedExtension] = []
        for path in sorted(directory.glob("*.py")):
            if path.name.startswith("_"):
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
        except Exception as exc:  # extensions are user code - never crash the app
            record.error = f"{type(exc).__name__}: {exc}"
        self.loaded.append(record)
        return record
