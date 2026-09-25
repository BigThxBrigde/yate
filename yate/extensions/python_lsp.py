r"""Bundled extension: Python language server support (LSP).

Ships with yate at ``yate/extensions/python_lsp.py`` and is auto-loaded at
startup. Disable it with the yaterc option
``disabled_extensions = ["python_lsp"]``.

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
import sys
from pathlib import Path

from yate.services.extensions import ExtensionAPI


def _venv_langserver() -> str | None:
    """Find pyright-langserver beside the running interpreter.

    ``pip install pyright`` puts its launchers in the environment's
    scripts directory (e.g. ``.venv\\Scripts``); ``shutil.which`` misses
    them when that directory is not on ``PATH``.
    """
    here = Path(sys.executable).parent
    for name in ("pyright-langserver.exe", "pyright-langserver.cmd",
                 "pyright-langserver.bat", "pyright-langserver"):
        candidate = here / name
        if candidate.is_file():
            return str(candidate)
    return None


def _python_settings() -> dict[str, object] | None:
    """Point pyright at the running interpreter for stdlib resolution.

    A frozen exe has no interpreter to reference, so skip it there and
    let pyright fall back to its own environment discovery.
    """
    if getattr(sys, "frozen", False):
        return None
    return {"python": {"pythonPath": sys.executable}}


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
    pyright = _venv_langserver()
    if pyright:
        return pyright, ["--stdio"]
    pylsp = shutil.which("pylsp")
    if pylsp:
        return pylsp, []
    return "", []


def setup(api: ExtensionAPI) -> None:
    command, args = discover_command()
    is_pyright = "pyright" in Path(command).stem.lower()
    api.lsp.register_server(
        name="python",
        command=command,
        args=args,
        settings=_python_settings() if is_pyright else None,
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
