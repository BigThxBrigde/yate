"""Runtime trace logging for yate: stdlib :mod:`logging`, off by default.

yate has no runtime log until it is asked for one -- normal sessions write
nothing and pay nothing (the ``yate`` logger carries a ``NullHandler``, so
the calls below are a cheap level check).  Two switches turn tracing on,
checked in this order (an environment variable is a per-session override,
like a command line flag beating a yaterc file):

1. ``YATE_TRACE``            -- ``1/true/yes/on`` or ``0/false/no/off``
2. ``yate_trace``            -- the yaterc option (``yate_trace = True``)

and the verbosity likewise:

1. ``YATE_TRACE_LEVEL``      -- ``DEBUG`` | ``INFO`` | ``WARNING`` | ``ERROR``
                                 | ``CRITICAL`` (case-insensitive)
2. ``yate_trace_level``      -- the yaterc option

The names and numbers are exactly :mod:`logging`'s built-in levels; the
default when tracing is on but no level was given is ``DEBUG``.

Records land in ``~/.yate/data/logs/yate-YYYYMMDD-HHMMSS.log`` (append
mode, one session header per process).  The file is created on the first
record that is actually emitted, so an early-exit command (``yate
--version``) never leaves an empty shell behind even with ``YATE_TRACE=1``.
The directory sits next to the ``crash-*.err`` reports of
:mod:`yate.crash`: those cover "died badly", these cover "alive but
misbehaving".

Like :mod:`yate.crash`, everything here is best-effort: an unwritable logs
directory prints one warning to stderr and the editor still starts.
:func:`uninstall` closes the open file handle so
``yate --cleanup-defaults --include-data`` can remove ``data/`` (on Windows
an open handle would block the deletion).

Usage in a module::

    from yate import tracing
    log = tracing.get_logger(__name__)      # "yate.editor_lsp.manager"
    log.debug("completion request %s", uri)

:func:`install` is called twice by :mod:`yate.cli`: once before argument
parsing (environment only, so startup itself is observable) and once after
the yaterc files have been loaded (yaterc values merged in).  Both passes
are idempotent and the second one keeps the log file opened by the first.
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, IO, Optional

from yate import __version__

if TYPE_CHECKING:
    from yate.config import YateConfig

#: Root logger name; every yate logger is ``yate`` or a child of it.
LOGGER_NAME = "yate"

#: ``~/.yate/data/logs`` -- mirrors :func:`yate.crash.crash_data_dir`'s
#: ``~/.yate/data`` parent (kept local to avoid a runtime import cycle).
_DATA_DIRNAME = "data"
LOG_DIRNAME = "logs"

LOG_PREFIX = "yate-"
LOG_SUFFIX = ".log"

#: Level used when tracing is enabled without an explicit level.
DEFAULT_LEVEL = "DEBUG"

#: Accepted level names -- :mod:`logging`'s built-ins, in increasing order.
LEVEL_NAMES: tuple[str, ...] = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")

#: Accepted spellings of ``YATE_TRACE`` (compared lower-cased).
TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
FALSE_VALUES = frozenset({"0", "false", "no", "off"})

_logger = logging.getLogger(LOGGER_NAME)
# Library convention: quiet until install() attaches a real handler, and
# never leak records to the root logger (that would print into the TUI).
_logger.addHandler(logging.NullHandler())
_logger.propagate = False


# ------------------------------------------------------------------ helpers


def logs_dir() -> Path:
    """Return (creating if needed) ``~/.yate/data/logs/``."""
    directory = Path.home() / ".yate" / _DATA_DIRNAME / LOG_DIRNAME
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """The shared ``yate`` logger, or a child of it.

    ``get_logger(__name__)`` from inside the package yields
    ``yate.editor_lsp.manager`` and friends; the prefix is not doubled when
    *name* already starts with ``yate.``.
    """
    if not name or name == LOGGER_NAME:
        return _logger
    if name.startswith(LOGGER_NAME + "."):
        name = name[len(LOGGER_NAME) + 1 :]
    return logging.getLogger(f"{LOGGER_NAME}.{name.strip('.')}")


def resolve_level(raw: str) -> Optional[int]:
    """Map a level name to its :mod:`logging` value; ``None`` if unknown.

    Case- and whitespace-insensitive (``"debug"`` -> ``10``).
    """
    name = raw.strip().upper()
    if name not in LEVEL_NAMES:
        return None
    return int(getattr(logging, name))


def is_enabled() -> bool:
    """True while a log file handler is attached (i.e. tracing is on)."""
    return bool(_file_handlers())


def current_log_path() -> Optional[Path]:
    """Path of this session's log file, or ``None`` when tracing is off."""
    for handler in _file_handlers():
        return Path(handler.baseFilename)
    return None


def _file_handlers() -> list[logging.FileHandler]:
    return [h for h in _logger.handlers if isinstance(h, logging.FileHandler)]


def _warn(message: str) -> None:
    print(f"yate: {message}", file=sys.stderr)


class _SessionFileHandler(logging.FileHandler):
    """File handler that opens lazily and starts the file with a header.

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
                stream.write(_session_header(self.level))
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


# ------------------------------------------------------------ env variables


def env_trace() -> Optional[bool]:
    """``YATE_TRACE`` decoded; ``None`` when unset (or unrecognizable)."""
    value = os.environ.get("YATE_TRACE", "").strip().lower()
    if not value:
        return None
    if value in TRUE_VALUES:
        return True
    if value in FALSE_VALUES:
        return False
    _warn(f"ignoring unrecognized YATE_TRACE={value!r}")
    return None


def env_level() -> Optional[str]:
    """``YATE_TRACE_LEVEL`` normalized to upper case; ``None`` if unset/invalid."""
    value = os.environ.get("YATE_TRACE_LEVEL", "").strip()
    if not value:
        return None
    if resolve_level(value) is None:
        _warn(f"ignoring unrecognized YATE_TRACE_LEVEL={value!r}")
        return None
    return value.upper()


# ------------------------------------------------------------------- install


def install(config: Optional["YateConfig"] = None) -> bool:
    """(Re)configure tracing and return whether it is on.

    *config* is the resolved yaterc configuration (``None`` during the
    pre-config startup pass, where only the environment is known).  A
    second call keeps the file opened by the first and only adjusts the
    level, so the two passes never produce two files or two headers.
    """
    trace = env_trace()
    if trace is None and config is not None:
        trace = config.yate_trace
    if not trace:
        uninstall()
        return False

    level = _requested_level(config)
    handlers = _file_handlers()
    if handlers:
        for extra in handlers[1:]:
            _logger.removeHandler(extra)
            extra.close()
        handlers[0].setLevel(level)
        return True

    try:
        path = logs_dir() / (
            f"{LOG_PREFIX}{datetime.now():%Y%m%d-%H%M%S}{LOG_SUFFIX}"
        )
        handler = _SessionFileHandler(path, level)
    except OSError as exc:
        _warn(f"trace log unavailable: {exc}")
        return False
    # Records are filtered at the handler, so a later level change (or a
    # second handler with its own level) needs no logger-level juggling.
    _logger.setLevel(logging.DEBUG)
    _logger.addHandler(handler)
    return True


def uninstall() -> None:
    """Detach and close file handlers (before deleting ``~/.yate/data``)."""
    for handler in _file_handlers():
        _logger.removeHandler(handler)
        handler.close()


def _requested_level(config: Optional["YateConfig"]) -> int:
    name = env_level()
    if name is None and config is not None:
        name = config.yate_trace_level
    if name is None:
        name = DEFAULT_LEVEL
    resolved = resolve_level(name)
    # Explicit None test, not ``or``: 0 (logging.NOTSET) is falsy and would
    # be silently rewritten into DEBUG, hiding a bad input.
    return resolved if resolved is not None else logging.DEBUG


def _session_header(level: int) -> str:
    """Metadata header of one session (same fields as a crash report)."""
    return (
        f"=== yate {__version__} trace session ===\n"
        f"time: {datetime.now().isoformat(timespec='seconds')}\n"
        f"pid: {os.getpid()}\n"
        f"cwd: {os.getcwd()}\n"
        f"argv: {sys.argv!r}\n"
        f"python: {sys.version.split()[0]} on {sys.platform}\n"
        f"trace level: {logging.getLevelName(level)}\n"
        f"{'-' * 60}\n"
    )
