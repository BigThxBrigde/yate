"""Shell command execution service."""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ShellResult:
    command: str
    returncode: int
    output: str
    cwd: Path

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def run_shell(command: str, cwd: Path | None = None, timeout: float = 60.0) -> ShellResult:
    """Run *command* through the system shell, capturing output.

    The shell is the platform default (``cmd.exe`` on Windows, ``/bin/sh``
    elsewhere via :func:`subprocess.run` ``shell=True``).
    """
    workdir = Path(cwd) if cwd is not None else Path.cwd()
    try:
        proc = subprocess.run(
            command,
            shell=True,
            cwd=str(workdir),
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
            check=False,  # the return code is part of ShellResult, not an error
        )
        output = proc.stdout
        if proc.stderr:
            output += ("\n" if output and not output.endswith("\n") else "") + proc.stderr
        return ShellResult(command, proc.returncode, output, workdir)
    except subprocess.TimeoutExpired:
        return ShellResult(command, 124, f"[yate] command timed out after {timeout}s", workdir)
    except OSError as exc:  # pragma: no cover - environment dependent
        return ShellResult(command, 1, f"[yate] failed to run shell: {exc}", workdir)


def shell_name() -> str:
    """Human readable name of the shell :func:`run_shell` will use."""
    return "cmd.exe" if sys.platform.startswith("win") else "/bin/sh"
