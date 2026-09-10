"""Default shell discovery for the integrated terminal.

The shell is configurable via the ``shell`` yaterc option; when it is empty
yate picks a platform-appropriate default (PowerShell on Windows,
``$SHELL`` on Unix).
"""

from __future__ import annotations

import os
import shlex
import shutil
import sys
from pathlib import Path


def _powershell_args(argv: list[str]) -> list[str]:
    return [*argv, "-NoLogo"]


def resolve_shell(configured: str = "") -> list[str]:
    """Return the ``[executable, ...args]`` vector for the configured shell.

    *configured* is split with shell-style quoting (``"/usr/bin/zsh -l"``);
    on Windows the string is used verbatim when it points at an existing
    file, because real paths often contain spaces
    (``C:\\Program Files\\...``).
    """
    text = configured.strip()
    if text:
        if sys.platform.startswith("win"):
            candidate = Path(text)
            if candidate.is_file():
                return [str(candidate)]
        return shlex.split(text, posix=not sys.platform.startswith("win"))

    if sys.platform.startswith("win"):
        return _windows_default()
    return _posix_default()


def _windows_default() -> list[str]:
    # 1. PowerShell 7+ on PATH (pwsh.exe ships a console that works well in
    #    a ConPTY without profile banner noise thanks to -NoLogo).
    pwsh = shutil.which("pwsh") or shutil.which("pwsh.exe")
    if pwsh:
        return _powershell_args([pwsh])
    # 2. Bundled Windows PowerShell 5.1 (always present on supported Windows).
    system_root = os.environ.get("SystemRoot", r"C:\Windows")
    bundled = Path(system_root) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    if bundled.is_file():
        return _powershell_args([str(bundled)])
    # 3. cmd.exe via COMSPEC.
    comspec = os.environ.get("COMSPEC")
    if comspec and Path(comspec).is_file():
        return [comspec]
    cmd = shutil.which("cmd") or shutil.which("cmd.exe")
    return [cmd] if cmd else ["cmd.exe"]


def _posix_default() -> list[str]:
    env_shell = os.environ.get("SHELL")
    if env_shell and Path(env_shell).is_file():
        return [env_shell]
    bash = shutil.which("bash")
    if bash:
        return [bash]
    return ["/bin/sh"]


def shell_label(argv: list[str]) -> str:
    """Short label for the panel header (``pwsh``, ``bash`` ...)."""
    if not argv:
        return "shell"
    return Path(argv[0]).name
