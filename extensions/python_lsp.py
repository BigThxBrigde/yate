r"""Built-in extension: Python language server support (LSP).

Registers a Python language server so yate provides autocomplete and
diagnostics for ``.py`` / ``.pyi`` files.  Server discovery, in order:

1. The ``YATE_PYTHON_LSP`` environment variable -- a full command line,
   shell-style quoting supported, e.g.::

       set YATE_PYTHON_LSP=C:\tools\pyright-langserver.cmd --stdio
       export YATE_PYTHON_LSP="/usr/bin/pylsp --log-file /tmp/pylsp.log"

2. ``pyright-langserver`` on ``PATH`` (started with ``--stdio``).
   Install with ``npm install -g pyright`` or ``pip install pyright``.
3. ``pylsp`` on ``PATH`` (Python LSP server).
   Install with ``pip install python-lsp-server``.

If no executable is available the server is still registered but stays
in the ``failed`` state lazily on first use; nothing is spawned while
loading this extension and no startup messages are emitted.
"""

from __future__ import annotations

import os
import shlex
import shutil
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from yate.services.extensions import ExtensionAPI


def discover_command() -> tuple[str, list[str]]:
    """Return (executable, args) for the preferred available Python server."""
    override = os.environ.get("YATE_PYTHON_LSP", "").strip()
    if override.lower() in {"0", "off", "false", "none", "no"}:
        # Explicit opt-out: register the server but never spawn anything.
        return "", []
    if override:
        parts = shlex.split(override, posix=True)
        if parts:
            return parts[0], parts[1:]
    pyright = shutil.which("pyright-langserver")
    if pyright:
        return pyright, ["--stdio"]
    pylsp = shutil.which("pylsp")
    if pylsp:
        return pylsp, []
    return "", []


def setup(api: "ExtensionAPI") -> None:
    command, args = discover_command()
    api.lsp.register_server(
        name="python",
        command=command,
        args=args,
        filetypes=["py", "pyi"],
        language_ids={"py": "python", "pyi": "python"},
        root_markers=[
            "pyproject.toml",
            "setup.py",
            "setup.cfg",
            "requirements.txt",
            "Pipfile",
            ".git",
        ],
    )
