"""Shell command execution service."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from yate.logs import tracing

#: Module logger (R12: all runtime logs go through tracing).
log = tracing.get_logger(__name__)


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
        except OSError as exc:
            log.warning(
                "could not kill the timed-out shell (pid %d)", proc.pid, exc_info=exc
            )


def shell_cwd(workspace_root: Path | None, document_dir: Path | None) -> Path:
    """Pick the command working directory: workspace / document / process."""
    return workspace_root or document_dir or Path.cwd()


def _popen(
    command: str | list[str], *, shell: bool, workdir: Path
) -> subprocess.Popen[str]:
    """Start *command* with the shared Popen configuration of both runners."""
    return subprocess.Popen(
        command,
        shell=shell,
        cwd=str(workdir),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        start_new_session=not sys.platform.startswith("win"),
    )


def _capture(
    proc: subprocess.Popen[str], label: str, workdir: Path, timeout: float
) -> ShellResult:
    """Communicate with *proc*, enforcing *timeout* with a tree kill."""
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        _kill_tree(proc)
        # The tree is normally dead now, so this drains the remaining buffer
        # immediately.  Bounded: a tree that survived _kill_tree (a Windows
        # taskkill race, a POSIX grandchild that left its process group)
        # keeps the output pipes open, and an unbounded communicate() here
        # would block forever.  The drained output is discarded either way --
        # the result below carries a fixed message.
        try:
            proc.communicate(timeout=5.0)
        except subprocess.TimeoutExpired:
            # Degrade to killing the shell root itself, then reap
            # best-effort: a grandchild still holding the pipes can keep
            # even this final drain from finishing, so it is bounded too.
            proc.kill()
            try:
                proc.communicate(timeout=5.0)
            except subprocess.TimeoutExpired as exc:
                log.error(
                    "could not reap shell pid %d after timeout: %s", proc.pid, exc
                )
        return ShellResult(
            label, 124, f"[yate] command timed out after {timeout}s", workdir
        )
    output = stdout
    if stderr:
        output += ("\n" if output and not output.endswith("\n") else "") + stderr
    returncode = proc.returncode if proc.returncode is not None else -1
    return ShellResult(label, returncode, output, workdir)


def run_shell(
    command: str, cwd: Path | None = None, timeout: float = 60.0
) -> ShellResult:
    """Run *command* through the system shell, capturing output.

    The shell is the platform default (``cmd.exe`` on Windows, ``/bin/sh``
    elsewhere).  On timeout the whole process tree is force-terminated -- not just the
    shell -- so the call returns promptly instead of waiting for an
    orphaned grandchild to release the output pipes.
    """
    workdir = Path(cwd) if cwd is not None else Path.cwd()
    try:
        proc = _popen(command, shell=True, workdir=workdir)
    except OSError as exc:  # pragma: no cover - environment dependent
        return ShellResult(command, 1, f"[yate] failed to run shell: {exc}", workdir)
    return _capture(proc, command, workdir, timeout)


def run_argv(
    argv: Sequence[str], cwd: Path | None = None, timeout: float = 60.0
) -> ShellResult:
    """Run *argv* as a program vector (``shell=False``), capturing output.

    This is the variant that avoids shell metacharacter interpretation --
    it is not a sandbox or privilege reduction: the process still runs
    with the full permissions of the current user.  On timeout the whole
    process tree is force-terminated, exactly like :func:`run_shell`.
    An empty vector raises :class:`ValueError`; a missing executable
    yields a :class:`ShellResult` with return code 1 instead of raising.

    ``ShellResult.command`` carries the display label
    ``" ".join(argv)``, not an executable command string.
    """
    args = list(argv)
    if not args:
        raise ValueError("argv must contain at least one element")
    workdir = Path(cwd) if cwd is not None else Path.cwd()
    label = " ".join(args)
    try:
        proc = _popen(args, shell=False, workdir=workdir)
    except OSError as exc:
        return ShellResult(label, 1, f"[yate] failed to run command: {exc}", workdir)
    return _capture(proc, label, workdir, timeout)


def shell_name() -> str:
    """Human readable name of the shell :func:`run_shell` will use."""
    return "cmd.exe" if sys.platform.startswith("win") else "/bin/sh"
