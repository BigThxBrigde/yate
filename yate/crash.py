"""Best-effort crash diagnostics for yate.

At process startup :func:`install` opens ``~/.yate/data/crash-*.err``,
writes a metadata header, points :mod:`faulthandler` at the open file
descriptor and wraps ``sys.excepthook``. Two failure modes are covered:

* native crashes (access violation, SIGABRT, ...): ``faulthandler`` writes
  every thread's Python traceback straight to the fd, bypassing Python
  buffers -- the process dies hard, so the file must already be open;
* uncaught Python exceptions: the excepthook wrapper appends the
  traceback, then delegates to the original hook.

The file is opened eagerly because doing it from inside a crash handler
is not reliable (the heap may already be corrupt). To avoid littering
``~/.yate/data`` on healthy runs, an ``atexit`` handler deletes a
header-only file on normal shutdown; native crashes never reach atexit,
and a logged exception marks the file to keep.

Everything here is best-effort: diagnostics must never break startup.
Handlers intentionally perform only short, low-dependency file I/O.
"""

from __future__ import annotations

import atexit
import faulthandler
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path
from types import TracebackType
from typing import Optional, TextIO

from yate import __version__

#: Writable per-user data folder (under ``~/.yate``).
DATA_DIRNAME = "data"
ERR_PREFIX = "crash-"
ERR_SUFFIX = ".err"
_HEADER_RULE = "-" * 60

#: Open report handle while diagnostics are installed (``None`` otherwise).
_err_file: Optional[TextIO] = None
#: Path of ``_err_file``, kept for clean-exit removal.
_err_path: Optional[Path] = None
#: Set once an uncaught exception has been logged, so atexit keeps the file.
_crashed = False
_original_excepthook = sys.excepthook


def crash_data_dir() -> Path:
    """Return (creating if needed) ``~/.yate/data/``."""
    directory = Path.home() / ".yate" / DATA_DIRNAME
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def current_crash_file() -> Optional[Path]:
    """Path of this process's in-progress crash report, if installed.

    The file is header-only while the process is healthy; it must be
    excluded from "previous crash reports" listings so a normal run does
    not look like it already crashed.
    """
    return _err_path


def _err_file_path(directory: Path, now: Optional[datetime] = None) -> Path:
    """Build ``crash-YYYYMMDD-HHMMSS.err`` inside *directory*."""
    moment = now if now is not None else datetime.now()
    return directory / f"{ERR_PREFIX}{moment:%Y%m%d-%H%M%S}{ERR_SUFFIX}"


def _write_header(handle: TextIO) -> None:
    """Write process metadata; the caller flushes before faulthandler use."""
    handle.write(f"yate {__version__} crash report\n")
    handle.write(f"time: {datetime.now().isoformat(timespec='seconds')}\n")
    handle.write(f"cwd: {os.getcwd()}\n")
    handle.write(f"argv: {sys.argv!r}\n")
    handle.write(f"python: {sys.version.split()[0]} on {sys.platform}\n")
    handle.write(_HEADER_RULE + "\n")


def _excepthook(
    exc_type: type[BaseException],
    exc_value: BaseException,
    exc_tb: Optional[TracebackType],
) -> None:
    """Append the traceback to the report, then run the original hook."""
    global _crashed
    _crashed = True
    handle = _err_file
    if handle is not None:
        try:
            handle.write("\n=== uncaught Python exception ===\n")
            traceback.print_exception(exc_type, exc_value, exc_tb, file=handle)
            handle.flush()
        except Exception:
            # Never let diagnostics mask the original failure.
            pass
    _original_excepthook(exc_type, exc_value, exc_tb)


def _cleanup_on_exit() -> None:
    """Close the report on shutdown; remove it when no failure was logged.

    Native crashes terminate the process before atexit runs, so genuine
    crash reports are always left on disk.
    """
    global _err_file, _err_path
    handle = _err_file
    path = _err_path
    _err_file = None
    _err_path = None
    if handle is None:
        return
    try:
        handle.flush()
        handle.close()
    except OSError:
        pass
    if not _crashed and path is not None:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass


def uninstall() -> None:
    """Release the open crash report and disable :mod:`faulthandler`.

    One-shot CLI commands that remove the data directory (``yate
    --cleanup-defaults --include-data``) call this first: on Windows the
    eagerly-opened report handle would otherwise make removing ``data/``
    fail. A healthy header-only report is deleted, as on a normal exit.
    Idempotent and best-effort, like :func:`install`.
    """
    try:
        faulthandler.disable()
    except (OSError, ValueError):
        pass
    _cleanup_on_exit()


def install() -> None:
    """Enable on-disk crash diagnostics. Idempotent and best-effort."""
    global _err_file, _err_path
    if _err_file is not None:
        return
    try:
        path = _err_file_path(crash_data_dir())
        handle = open(path, "w", encoding="utf-8", buffering=1)
        _write_header(handle)
        handle.flush()
        # faulthandler writes to this fd directly on fatal signals.
        faulthandler.enable(file=handle, all_threads=True)
    except (OSError, ValueError):
        # No usable data directory or handle: still enable faulthandler on
        # stderr so a native crash leaves *some* trace behind.
        try:
            faulthandler.enable(file=sys.stderr, all_threads=True)
        except Exception:
            pass
        return

    _err_file = handle
    _err_path = path
    atexit.register(_cleanup_on_exit)
    sys.excepthook = _excepthook
