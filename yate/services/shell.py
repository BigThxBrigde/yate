"""Shell command execution service."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ShellResult:
    """Outcome of one :func:`run_shell` call: command, exit code, output, cwd."""

    command: str
    returncode: int
    output: str
    cwd: Path

    @property
    def ok(self) -> bool:
        """True when the command exited successfully."""
        return self.returncode == 0


def _kill_tree(proc: subprocess.Popen[str]) -> None:
    """Force-terminate *proc* together with every descendant process.

    The shell is only the root of the process tree; the command it spawned
    (a grandchild) keeps the output pipes open, so killing the shell alone
    would leave an orphan that ``communicate()`` would then wait on for as
    long as the grandchild happens to live.
    """
    if sys.platform == "win32":
        # taskkill /T walks and terminates the whole tree in one call.
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
            capture_output=True,
            check=False,
        )
        return
    # POSIX branch: unreachable on Windows (pyright skips it on win32), so
    # the POSIX-only killpg/getpgid symbols never fail the Windows typecheck.
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except OSError:
        try:
            proc.kill()
        except OSError:
            pass


def run_shell(
    command: str, cwd: Path | None = None, timeout: float = 60.0
) -> ShellResult:
    """Run *command* through the system shell, capturing output.

    The shell is the platform default (``cmd.exe`` on Windows, ``/bin/sh``
    elsewhere).  On timeout the whole process tree is force-terminated --
    not just the shell -- so the call returns promptly instead of waiting
    for an orphaned grandchild to release the output pipes.
    """
    workdir = Path(cwd) if cwd is not None else Path.cwd()
    try:
        proc = subprocess.Popen(
            command,
            shell=True,
            cwd=str(workdir),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            start_new_session=not sys.platform.startswith("win"),
        )
    except OSError as exc:  # pragma: no cover - environment dependent
        return ShellResult(command, 1, f"[yate] failed to run shell: {exc}", workdir)
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        _kill_tree(proc)
        # The tree is dead, so this drains the remaining buffer immediately.
        stdout, stderr = proc.communicate()
        return ShellResult(
            command, 124, f"[yate] command timed out after {timeout}s", workdir
        )
    output = stdout
    if stderr:
        output += ("\n" if output and not output.endswith("\n") else "") + stderr
    returncode = proc.returncode if proc.returncode is not None else -1
    return ShellResult(command, returncode, output, workdir)


def shell_name() -> str:
    """Human readable name of the shell :func:`run_shell` will use."""
    return "cmd.exe" if sys.platform.startswith("win") else "/bin/sh"
