"""Unified logging for yate: crash reports and runtime tracing.

Both services live here as independent singletons and know nothing about each
other. Callers import them straight from this module::

    from yate.logs import crash, tracing

    crash.install()                            # ~/.yate/data/crash-*.err
    tracing.install(yate_trace=True)           # ~/.yate/data/logs/yate-*.log
    log = tracing.get_logger(__name__)

* :data:`crash` -- best-effort crash diagnostics. :meth:`CrashService.install`
  eagerly opens ``~/.yate/data/crash-*.err``, writes a metadata header, points
  :mod:`faulthandler` at the open file descriptor and wraps ``sys.excepthook``
  (chaining to the hook it replaced). An ``atexit`` handler deletes a
  header-only report on a healthy exit; uncaught exceptions and native crashes
  keep it. :meth:`CrashService.uninstall` reverses the whole install early --
  original hook and atexit entry included.
* :data:`tracing` -- opt-in runtime trace log, off by default. Records land in
  ``~/.yate/data/logs/yate-YYYYMMDD-HHMMSS.log``; the file is created on the
  first emitted record, so an early-exit command (``yate --version``) leaves no
  empty shell behind even with ``YATE_TRACE=1``.

The two share nothing but the module-level helpers below them -- no base class,
no cross-reference between the classes, no :mod:`yate.config` dependency (the
yaterc values arrive as plain scalars). That keeps this module a *leaf*: it
imports only the standard library plus :data:`yate.__version__`, so importing
it is safe from anywhere, including modules pulled in while a package is still
initializing.

Both services write the same process metadata in the same order
(:func:`build_session_header`), so a crash report and a trace log are read the
same way. Everything here is best-effort: an unwritable directory prints one
warning on stderr and the editor still starts.
"""

from __future__ import annotations

import atexit
import faulthandler
import logging
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path
from types import TracebackType
from typing import Any, Callable, IO, Mapping, Optional, TextIO

from yate import __version__

# ==============================================================
# Constants -- consumed directly by config.py, cli.py, tests, ...
# ==============================================================

#: Root logger name; every yate logger is ``yate`` or a child of it.
LOGGER_NAME = "yate"

#: Accepted level names -- :mod:`logging`'s built-ins, in increasing order.
LEVEL_NAMES: tuple[str, ...] = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")

#: Level used when tracing is enabled without an explicit level.
DEFAULT_LEVEL = "DEBUG"

#: Accepted spellings of ``YATE_TRACE`` (compared lower-cased).
TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
FALSE_VALUES = frozenset({"0", "false", "no", "off"})

#: ``~/.yate/data`` parent and ``~/.yate/data/logs`` child.
DATA_DIRNAME = "data"
LOG_DIRNAME = "logs"

#: Filename stems/suffixes for the two services.
LOG_PREFIX = "yate-"
LOG_SUFFIX = ".log"
ERR_PREFIX = "crash-"
ERR_SUFFIX = ".err"


# ==============================================================
# Pure functions -- no state, so no class needed
# ==============================================================


def warn(message: str) -> None:
    """Print ``yate: <message>`` to stderr. Never raises."""
    print(f"yate: {message}", file=sys.stderr)


def build_session_header(
    *,
    title: str,
    extra_lines: Optional[Mapping[str, str]] = None,
    footer_lines: Optional[Mapping[str, str]] = None,
) -> str:
    """Process-metadata header shared by the crash report and the trace log.

    *title* is the banner line: ``yate <version> crash report`` for crash
    files, ``=== yate <version> trace session ===`` for trace logs, so each
    service keeps its own historical banner.

    *extra_lines* are ``key: value`` rows written straight after ``time``
    (the trace header puts ``pid`` there -- both identify "this run"), and
    *footer_lines* close the block after the environment rows (the trace
    header puts its ``trace level`` there). Both keep insertion order.
    Layout::

        <title>
        time: ...
        [extra_lines]
        cwd: ...
        argv: [...]
        python: ... on ...
        [footer_lines]
        ------------------------------------------------------------
    """
    lines: list[str] = [
        title,
        f"time: {datetime.now().isoformat(timespec='seconds')}",
    ]
    if extra_lines:
        lines.extend(f"{key}: {value}" for key, value in extra_lines.items())
    lines.extend(
        [
            f"cwd: {os.getcwd()}",
            f"argv: {sys.argv!r}",
            f"python: {sys.version.split()[0]} on {sys.platform}",
        ]
    )
    if footer_lines:
        lines.extend(f"{key}: {value}" for key, value in footer_lines.items())
    lines.append("-" * 60)
    return "\n".join(lines) + "\n"


def resolve_level(raw: str) -> Optional[int]:
    """Map a level name to its :mod:`logging` value; ``None`` if unknown.

    Case- and whitespace-insensitive (``"debug"`` -> ``10``).
    """
    name = raw.strip().upper()
    if name not in LEVEL_NAMES:
        return None
    return int(getattr(logging, name))


def env_trace() -> Optional[bool]:
    """``YATE_TRACE`` decoded; ``None`` when unset (or unrecognizable)."""
    value = os.environ.get("YATE_TRACE", "").strip().lower()
    if not value:
        return None
    if value in TRUE_VALUES:
        return True
    if value in FALSE_VALUES:
        return False
    warn(f"ignoring unrecognized YATE_TRACE={value!r}")
    return None


def env_level() -> Optional[str]:
    """``YATE_TRACE_LEVEL`` normalized to upper case; ``None`` if unset/invalid."""
    value = os.environ.get("YATE_TRACE_LEVEL", "").strip()
    if not value:
        return None
    if resolve_level(value) is None:
        warn(f"ignoring unrecognized YATE_TRACE_LEVEL={value!r}")
        return None
    return value.upper()


def logs_dir() -> Path:
    """Return (creating if needed) ``~/.yate/data/logs/``."""
    directory = Path.home() / ".yate" / DATA_DIRNAME / LOG_DIRNAME
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def crash_data_dir() -> Path:
    """Return (creating if needed) ``~/.yate/data/``."""
    directory = Path.home() / ".yate" / DATA_DIRNAME
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _trace_header(level: int) -> str:
    """Metadata header of one trace session (read by the file handler)."""
    return build_session_header(
        title=f"=== yate {__version__} trace session ===",
        extra_lines={"pid": str(os.getpid())},
        footer_lines={"trace level": logging.getLevelName(level)},
    )


class _SessionFileHandler(logging.FileHandler):
    """File handler that opens lazily and starts the file with a header.

    Private: it is the implementation of :meth:`TracingService.install`, with
    no caller outside this module.

    Two properties matter here:

    * the file is created on the **first emitted record**, so a traced run
      that logs nothing (``YATE_TRACE=1 yate --version``) leaves no empty
      shell behind in ``~/.yate/data/logs``;
    * an open error at that point is reported through :meth:`handleError`
      instead of escaping into the editor -- logging must never break yate.

    The header is written straight to the stream (not through the logger)
    so it always appears, whatever the configured level is.

    The lazy open is tracked by our own :attr:`_stream` rather than by
    testing ``self.stream is None``: stdlib really leaves that attribute
    unset until the first emit (``delay=True``), but its declared type is
    not stable across type-checker versions -- depending on the stub the
    guard reads either as "always false" or as an unsafe access on
    ``None``.  Holding the handle ourselves keeps the ``None`` honest
    whatever the stub says.
    """

    def __init__(self, filename: Path, level: int) -> None:
        super().__init__(filename, mode="a", encoding="utf-8", delay=True)
        self.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s")
        )
        self.setLevel(level)
        self._stream: Optional[IO[str]] = None
        self._header_written = False

    def emit(self, record: logging.LogRecord) -> None:
        try:
            stream = self._stream
            if stream is None:
                stream = self._open()
                self.stream = stream  # StreamHandler.emit writes to it
                self._stream = stream
            if not self._header_written:
                stream.write(_trace_header(self.level))
                self.flush()
                # Mark it written only once it really is: a failed write
                # must not silently drop the header forever.
                self._header_written = True
        except OSError:
            # Only I/O is forgiven (logging must never break the editor); a
            # genuine bug in the header still has to surface.
            self.handleError(record)
            return
        super().emit(record)

    def close(self) -> None:
        super().close()  # FileHandler.close() drops the stream handle
        # Reopen rather than write into a dropped one: without this the
        # handler would keep claiming "already open" and every later record
        # would silently go nowhere.
        self._stream = None


class CrashService:
    """Best-effort crash diagnostics for one yate process.

    Eagerly opens ``~/.yate/data/crash-*.err`` at install time, writes a
    metadata header, points :mod:`faulthandler` at the fd, and wraps
    ``sys.excepthook`` to append uncaught Python tracebacks. Atexit deletes
    a header-only report on healthy shutdown; :meth:`uninstall` does the
    same early and hands ``sys.excepthook`` back to the interpreter.

    Self-contained: it never imports, references or notifies
    :class:`TracingService`.
    """

    def __init__(self) -> None:
        #: Open report handle while diagnostics are installed.
        self._err_file: Optional[TextIO] = None
        #: Path of ``_err_file``, kept for clean-exit removal.
        self._err_path: Optional[Path] = None
        #: Set once an uncaught exception has been logged, so atexit keeps
        #: the file.
        self._crashed: bool = False
        #: The hook that was in place before us, called last. Captured on
        #: the first :meth:`install` -- *not* at construction (= import
        #: time) -- so a hook the host installed between import and install
        #: is the one chained to and later restored, not clobbered.
        #: ``None`` until that first install.
        self._original_excepthook: Optional[Callable[..., Any]] = None
        #: The bound ``_excepthook`` object currently stored in
        #: ``sys.excepthook``, or ``None`` when we are not installed. Held
        #: as a reference on purpose: ``self._excepthook`` is a *fresh*
        #: bound method on every access, so ``sys.excepthook is
        #: self._excepthook`` is never true and could not tell "still ours"
        #: from "wrapped by someone else since".
        self._installed_excepthook: Optional[Callable[..., Any]] = None

    # --- public read-only state -------------------------------------------

    @property
    def err_file(self) -> Optional[TextIO]:
        """Open crash report handle, or ``None`` when not installed."""
        return self._err_file

    @property
    def err_path(self) -> Optional[Path]:
        """Path of the open crash report, or ``None``."""
        return self._err_path

    @property
    def had_crash(self) -> bool:
        """True once an uncaught exception has been logged."""
        return self._crashed

    @property
    def original_excepthook(self) -> Optional[Callable[..., Any]]:
        """The ``sys.excepthook`` captured at install time (chained after us).

        ``None`` while the service has never been installed: the constructor
        deliberately does not touch ``sys.excepthook``, so the capture happens
        on the first :meth:`install` instead of at import time.
        """
        return self._original_excepthook

    # --- lifecycle --------------------------------------------------------

    def install(self) -> None:
        """Enable on-disk crash diagnostics. Idempotent and best-effort."""
        if self._err_file is not None:
            return
        try:
            path = self.build_err_path(crash_data_dir())
            handle = open(path, "w", encoding="utf-8", buffering=1)
            self._write_header(handle)
            handle.flush()
            # faulthandler writes to this fd directly on fatal signals.
            faulthandler.enable(file=handle, all_threads=True)
        except (OSError, ValueError):
            # No usable data directory or handle: still enable faulthandler
            # on stderr so a native crash leaves *some* trace behind.
            try:
                faulthandler.enable(file=sys.stderr, all_threads=True)
            except Exception:
                pass
            return

        self._err_file = handle
        self._err_path = path
        # Register-then-dedup: atexit runs *every* registered entry, so
        # install/uninstall cycles must not pile callbacks up.
        atexit.unregister(self.cleanup_on_exit)
        atexit.register(self.cleanup_on_exit)
        # Capture the hook we are about to replace -- on the first install,
        # not at import time (S5): a hook the host installed between the two
        # is the one chained to below and restored by uninstall().
        if self._original_excepthook is None:
            self._original_excepthook = sys.excepthook
        hook = self._excepthook
        sys.excepthook = hook
        self._installed_excepthook = hook

    def uninstall(self) -> None:
        """Release the report, the ``sys.excepthook`` and :mod:`faulthandler`.

        One-shot CLI commands that remove the data directory (``yate
        --cleanup-defaults --include-data``) call this first: on Windows the
        eagerly-opened report handle would otherwise make removing ``data/``
        fail. A healthy header-only report is deleted, as on a normal exit,
        and the process is left as :meth:`install` found it. Idempotent and
        best-effort, like :meth:`install`.
        """
        try:
            faulthandler.disable()
        except (OSError, ValueError):
            pass
        # Hand the interpreter its hook back *before* dropping the report:
        # left in place, ours would keep this uninstalled instance reachable
        # and still set ``_crashed`` on the next uncaught exception, a state
        # contradicting the released handle. Only while it is still ours --
        # a hook someone else wrapped around ours is not ours to clobber.
        hook = self._installed_excepthook
        original = self._original_excepthook
        if hook is not None and original is not None and sys.excepthook is hook:
            sys.excepthook = original
        self._installed_excepthook = None
        # The cleanup runs right here, so the atexit entry has nothing left
        # to do; dropping it also keeps repeated install/uninstall flat.
        atexit.unregister(self.cleanup_on_exit)
        self.cleanup_on_exit()

    def cleanup_on_exit(self) -> None:
        """Close the report on shutdown; remove it when no failure was logged.

        Native crashes terminate the process before atexit runs, so genuine
        crash reports are always left on disk.
        """
        handle = self._err_file
        path = self._err_path
        self._err_file = None
        self._err_path = None
        if handle is None:
            return
        try:
            handle.flush()
            handle.close()
        except OSError:
            pass
        if not self._crashed and path is not None:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass

    # --- helpers ----------------------------------------------------------

    def build_err_path(
        self, directory: Path, now: Optional[datetime] = None
    ) -> Path:
        """Build ``crash-YYYYMMDD-HHMMSS-<pid>.err`` inside *directory*.

        The pid suffix keeps two yate processes started within the same
        second from colliding: both open their report in ``"w"`` mode, so a
        shared name would have the later header truncate the earlier
        process's report (S36).
        """
        moment = now if now is not None else datetime.now()
        return (
            directory
            / f"{ERR_PREFIX}{moment:%Y%m%d-%H%M%S}-{os.getpid()}{ERR_SUFFIX}"
        )

    def current_path(self) -> Optional[Path]:
        """Path of this process's in-progress crash report, or ``None``.

        The file is header-only while the process is healthy; it must be
        excluded from "previous crash reports" listings so a normal run does
        not look like it already crashed.
        """
        return self._err_path

    def current_crash_file(self) -> Optional[Path]:
        """Alias for :meth:`current_path` (kept for :mod:`yate.diagnostics`)."""
        return self._err_path

    def is_enabled(self) -> bool:
        """True while the report file is open."""
        return self._err_file is not None

    def _write_header(self, handle: TextIO) -> None:
        """Write process metadata; the caller flushes before faulthandler use."""
        handle.write(build_session_header(title=f"yate {__version__} crash report"))

    def _excepthook(
        self,
        exc_type: type[BaseException],
        exc_value: BaseException,
        exc_tb: Optional[TracebackType],
    ) -> None:
        """Append the traceback to the report, then run the original hook."""
        self._crashed = True
        handle = self._err_file
        if handle is not None:
            try:
                handle.write("\n=== uncaught Python exception ===\n")
                traceback.print_exception(exc_type, exc_value, exc_tb, file=handle)
                handle.flush()
            except Exception:
                # Never let diagnostics mask the original failure.
                pass
        original = self._original_excepthook
        if original is not None:
            original(exc_type, exc_value, exc_tb)


class TracingService:
    """Runtime trace log for one yate process. Off by default.

    Two-phase install in :mod:`yate.cli`::

        tracing.install()                                  # pass 1: env only
        ... load_config() ...
        tracing.configure(                                 # pass 2: merge rc
            yate_trace=config.yate_trace,
            yate_trace_level=config.yate_trace_level,
        )

    Self-contained: it never imports, references or notifies
    :class:`CrashService`, and it knows nothing about the yaterc config type
    -- the two trace options arrive as plain scalars (a bool and a level-name
    string) and the level is resolved to an int here, via
    :func:`resolve_level`.
    """

    def __init__(self) -> None:
        self._logger = logging.getLogger(LOGGER_NAME)
        # Library convention: quiet until install() attaches a real handler,
        # and never leak records to the root logger (that would print into
        # the TUI).
        self._logger.addHandler(logging.NullHandler())
        self._logger.propagate = False

    # --- public state -----------------------------------------------------

    @property
    def root_logger(self) -> logging.Logger:
        """The shared ``yate`` logger."""
        return self._logger

    # --- lifecycle --------------------------------------------------------

    def install(
        self,
        yate_trace: Optional[bool] = None,
        yate_trace_level: Optional[str] = None,
    ) -> bool:
        """(Re)configure tracing and return whether it is on.

        ``YATE_TRACE`` / ``YATE_TRACE_LEVEL`` always win when present;
        *yate_trace* / *yate_trace_level* are the yaterc fallbacks (``None``
        = not set). A second call keeps the file opened by the first and only
        adjusts the level, so the two startup passes never produce two files
        or two headers.

        Level resolution order: the env var, then *yate_trace_level*, then
        :data:`DEFAULT_LEVEL`; the chosen name is resolved to an int here.
        """
        trace = env_trace()
        if trace is None:
            trace = yate_trace
        if not trace:
            self.uninstall()
            return False

        name = env_level()
        if name is None:
            name = yate_trace_level
        if name is None:
            name = DEFAULT_LEVEL
        resolved = resolve_level(name)
        # Explicit None test, not ``or``: 0 (logging.NOTSET) is falsy and
        # would be silently rewritten into DEBUG, hiding a bad input.
        level = resolved if resolved is not None else logging.DEBUG

        handlers = self.file_handlers()
        if handlers:
            for extra in handlers[1:]:
                self._logger.removeHandler(extra)
                extra.close()
            handlers[0].setLevel(level)
            return True

        try:
            # Same-second sessions of different processes must not share a
            # file name (the pid disambiguates what the second-granularity
            # timestamp cannot); the header carries the pid as well.
            path = logs_dir() / (
                f"{LOG_PREFIX}{datetime.now():%Y%m%d-%H%M%S}"
                f"-{os.getpid()}{LOG_SUFFIX}"
            )
            handler = _SessionFileHandler(path, level)
        except OSError as exc:
            warn(f"trace log unavailable: {exc}")
            return False
        # Records are filtered at the handler, so a later level change (or a
        # second handler with its own level) needs no logger-level juggling.
        self._logger.setLevel(logging.DEBUG)
        self._logger.addHandler(handler)
        return True

    def configure(
        self,
        yate_trace: Optional[bool] = None,
        yate_trace_level: Optional[str] = None,
    ) -> None:
        """Alias for :meth:`install` -- the rc-stage re-config, spelled out.

        Same parameters and behavior; it exists so the second startup pass in
        :mod:`yate.cli` (after the yaterc files are known) reads as a
        re-configuration rather than a fresh install. Like :meth:`install` it
        returns ``bool`` in spirit, but the pass-2 caller ignores it.
        """
        self.install(yate_trace=yate_trace, yate_trace_level=yate_trace_level)

    def uninstall(self) -> None:
        """Detach and close file handlers (before deleting ``~/.yate/data``)."""
        for handler in self.file_handlers():
            self._logger.removeHandler(handler)
            handler.close()

    # --- state ------------------------------------------------------------

    def current_path(self) -> Optional[Path]:
        """Path of this session's log file, or ``None`` when tracing is off."""
        for handler in self.file_handlers():
            return Path(handler.baseFilename)
        return None

    def current_log_path(self) -> Optional[Path]:
        """Alias for :meth:`current_path` (kept for external callers)."""
        return self.current_path()

    def is_enabled(self) -> bool:
        """True while a log file handler is attached (i.e. tracing is on)."""
        return bool(self.file_handlers())

    def file_handlers(self) -> list[logging.FileHandler]:
        """Active :class:`logging.FileHandler` instances on the root logger."""
        return [
            handler
            for handler in self._logger.handlers
            if isinstance(handler, logging.FileHandler)
        ]

    # --- logger tree (crash has no logger) --------------------------------

    def get_logger(self, name: Optional[str] = None) -> logging.Logger:
        """The shared ``yate`` logger, or a child of it.

        ``get_logger(__name__)`` from inside the package yields
        ``yate.editor_lsp.manager`` and friends; the prefix is not doubled
        when *name* already starts with ``yate.``.
        """
        if not name or name == LOGGER_NAME:
            return self._logger
        if name.startswith(LOGGER_NAME + "."):
            name = name[len(LOGGER_NAME) + 1 :]
        return logging.getLogger(f"{LOGGER_NAME}.{name.strip('.')}")


# ==============================================================
# Singletons -- independent objects, the thin shells re-export them
# ==============================================================

#: Crash diagnostics of this process. Knows nothing about :data:`tracing`.
crash = CrashService()

#: Runtime trace log of this process. Knows nothing about :data:`crash`.
tracing = TracingService()
