"""Extension discovery and loading orchestration.

Discovers ``.py`` / ``.lua`` extension scripts on disk, drives the A13
rollback scope around each ``setup``, runs the optional ``teardown`` hooks
at shutdown and sequences the documented startup load order
(:func:`load_startup_extensions`).
"""

from __future__ import annotations

import importlib.util
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any, cast

from yate.config import YateConfig
from yate.logs import tracing
from yate.paths import bundled_extensions_dir
from yate.services.extensions.api import ExtensionAPI
from yate.services.extensions.lua.library import is_lua_available, lua_api_library_source
from yate.services.extensions.lua.runtime import create_runtime, run_extension
from yate.services.trust import is_trusted

#: Trace logger ("yate.services.extensions.loader"); silent unless yate_trace is on.
log = tracing.get_logger(__name__)

#: ``teardown(api)`` -- the optional counterpart of ``setup(api)``.
type TeardownHook = Callable[[ExtensionAPI], None]


@dataclass
class LoadedExtension:
    """Record of one extension discovered on disk.
    A healthy load fills ``module`` and ``teardown`` and leaves ``error``
    ``None``; any failure stores the exception summary there.  ``lua``
    records keep ``module`` ``None`` (Lua extensions carry no Python module).
    """

    name: str
    path: Path
    module: ModuleType | None = None
    error: str | None = None
    teardown: TeardownHook | None = None


@dataclass
class ExtensionLoader:
    """Discovers and loads extension scripts from disk."""

    api: ExtensionAPI
    loaded: list[LoadedExtension] = field(default_factory=list[LoadedExtension])

    def load_directory(
        self,
        directory: Path,
        *,
        exclude: Sequence[str] | None = None,
    ) -> list[LoadedExtension]:
        """Load every ``*.py`` and ``*.lua`` script in *directory* (sorted by path).

        Files whose stem is in *exclude* are skipped (used for bundled
        extensions turned off with ``disabled_extensions``); underscore-
        prefixed files are always skipped.
        """
        directory = Path(directory)
        if not directory.is_dir():
            return []
        skipped: set[str] = set(exclude) if exclude is not None else set()
        results: list[LoadedExtension] = []
        for path in sorted([*directory.glob("*.py"), *directory.glob("*.lua")]):
            if path.name.startswith("_") or path.stem in skipped:
                continue
            results.append(self.load_file(path))
        return results

    def load_file(self, path: Path) -> LoadedExtension:
        """Load the extension at *path* once and run its ``setup(api)``.

        Re-loading an already-loaded path (resolved comparison) hands back
        the earlier record.  Failures are stored on the record and logged,
        never raised.
        """
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
        if path.suffix == ".lua":
            return self._load_lua(path)
        # The resolved-path hash keeps same-stem extensions from different
        # directories under distinct sys.modules entries, so a failed
        # second load cannot pop the first one's module on cleanup (S33).
        mod_name = f"yate_ext_{path.stem}_{hash(resolved) & 0xFFFFFFFF:08x}"
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
            # Registration rollback scope (audit A13): everything this setup
            # registers is undone on failure; a success accepts the scope.
            self.api.start_scope()
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
                    TeardownHook, hook
                )
        except Exception as exc:  # noqa: BLE001 - extensions are user code, never crash the app
            # Roll back every registration this setup made (audit A13),
            # then drop the half-initialized module: a leftover under
            # sys.modules would make a later import of the same name hit the
            # broken remains instead of a clean retry (S33).
            self.api.rollback_scope()
            sys.modules.pop(mod_name, None)
            record.error = f"{type(exc).__name__}: {exc}"
            log.exception("extension failed to load: %s", path)
        else:
            self.api.end_scope()
            log.debug("extension loaded: %s", path)
        self.loaded.append(record)
        return record

    def _load_lua(self, path: Path) -> LoadedExtension:
        """Load a ``.lua`` extension (top-level setup, or explicit ``setup(api)``).

        Mirrors the Python branch (rollback scope A13; errors recorded,
        never raised); without ``lupa`` the record gets an install hint.
        """
        record = LoadedExtension(name=path.stem, path=path)
        if not is_lua_available():
            record.error = (
                "lua extensions require the lupa package; "
                "install with: pip install yate[lua]"
            )
        else:
            try:
                self.api.start_scope()
                runtime = create_runtime(self.api, lua_api_library_source())
                record.teardown = run_extension(
                    runtime, path.read_text(encoding="utf-8")
                )
            except Exception as exc:  # noqa: BLE001 - user code, never crash the app
                self.api.rollback_scope()
                record.error = f"{type(exc).__name__}: {exc}"
                log.exception("extension failed to load: %s", path)
            else:
                self.api.end_scope()
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
