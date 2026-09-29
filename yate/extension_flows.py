"""Extension startup flows: loading extensions and LSP server registration.

Extracted from :mod:`yate.editor`.  :class:`ExtensionFlows` owns the
startup sequence for extension code -- loading every configured source
(rc paths, bundled defaults, trusted directories), the explicit
``:trust`` confirmation for the current workspace, and the registration
of yaterc-declared language servers.  Like the other ``*Flows`` modules
it is constructed by the editor and never imports upward: collaborators
are concrete objects, and user-visible messages go through the injected
``message`` callable.

The editor keeps ownership of its pre-mount message buffer; the loader's
warnings are *returned* (not pushed) so the caller decides where they go.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from yate.config import YateConfig
from yate.services.extensions import (
    ExtensionAPI,
    ExtensionLoader,
    load_startup_extensions,
)
from yate.services.trust import trust_workspace


class ExtensionFlows:
    """Owns extension loading, workspace trust and LSP server registration."""

    def __init__(
        self,
        extension_loader: ExtensionLoader,
        extension_api: ExtensionAPI,
        config: YateConfig,
        ext_dirs: list[Path],
        ext_files: list[Path],
        message: Callable[[str, str], None],
    ) -> None:
        self.extension_loader = extension_loader
        self.extension_api = extension_api
        self.config = config
        self.ext_dirs = ext_dirs
        self.ext_files = ext_files
        self._message = message

    def load_extensions(self) -> list[str]:
        """Load extensions from every configured source; return the warnings.

        The caller owns the warnings from here on: the editor buffers them
        in its pre-mount message list *before* the servers are registered
        (:meth:`register_configured_servers`), so a registration failure
        cannot lose them.  Headless safe: shared by
        :meth:`yate.editor.Editor.on_mount` and ``yate --diag`` so the
        diagnostics always show exactly what a real start would load.  No
        LSP process is spawned here (servers start lazily).
        """
        return load_startup_extensions(
            self.extension_loader,
            self.config,
            ext_dirs=self.ext_dirs,
            ext_files=self.ext_files,
        )

    def trust_cwd_extensions(self) -> None:
        """Trust the current workspace and load its ``./extensions`` now.

        The explicit confirmation step of workspace trust: startup skips
        an untrusted project ``./extensions`` (opening a repository must
        not execute that repository's own code), and ``:trust`` both
        records the workspace in ``~/.yate/trusted_workspaces`` and loads
        the directory immediately.  Re-running is safe -- the loader
        de-duplicates by resolved path, so already-loaded scripts are
        skipped and only genuinely new ones run.
        """
        cwd = Path.cwd()
        if not trust_workspace(cwd):
            # S39 minimal hardening: a symlinked cwd is refused by the
            # store, and pretending otherwise (or still loading its
            # extensions) would defeat the guard.
            self._message(
                f"refused to trust {cwd}: it contains a symlink component; "
                "trust the resolved directory instead",
                "error",
            )
            return
        directory = cwd / "extensions"
        if not directory.is_dir():
            self._message(f"trusted {cwd}; no extensions directory to load",
                          "info")
            return
        records = self.extension_loader.load_directory(directory)
        failures = [record for record in records if record.error]
        loaded = len(records) - len(failures)
        self._message(
            f"trusted {cwd}; loaded {loaded} extension(s) from {directory}",
            "info",
        )
        for record in failures:
            self._message(f"extension {record.name}: {record.error}", "error")

    def register_configured_servers(self) -> None:
        """Register LSP servers declared by the yaterc ``language_servers``.

        Must run after :meth:`load_extensions` so an explicit rc entry with a
        server's name replaces a same-named extension registration. Nothing
        is spawned here: the manager starts the process lazily the first time
        a matching file is shown, so merely configuring a server is free.
        """
        bridge = self.extension_api.lsp
        for spec in self.config.language_servers:
            bridge.register_server(
                spec.name,
                command=spec.command,
                args=spec.args,
                filetypes=spec.filetypes,
                language_ids=spec.language_ids,
                initialization_options=spec.initialization_options,
                settings=spec.settings,
                env=spec.env,
                root_markers=spec.root_markers,
            )
