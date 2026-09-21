"""Thin shell re-exporting yate's runtime trace log.

The implementation lives in :mod:`yate.logs` (one module for both the trace
log and the crash report); this module only keeps the historical import path
alive for the call sites that actually exist::

    from yate import tracing
    log = tracing.get_logger(__name__)       # bound method of the singleton
    tracing.install(yate_trace=True)
    tracing.LEVEL_NAMES                      # "DEBUG", "INFO", ...

Anything without a caller is *not* carried here: the service object
(``yate.tracing.tracing``), ``SessionFileHandler``, ``file_handlers()`` and
the file-naming / env vocabulary (``LOGGER_NAME``, ``TRUE_VALUES``,
``FALSE_VALUES``, ``LOG_DIRNAME``, ``LOG_PREFIX``, ``LOG_SUFFIX``,
``logs_dir``) are reached through :mod:`yate.logs`.
"""

from __future__ import annotations

from yate.logs import (
    DEFAULT_LEVEL,
    LEVEL_NAMES,
    env_level,
    env_trace,
    resolve_level,
)
# Private alias: the shell binds the singleton's methods below but never
# publishes the object itself.
from yate.logs import tracing as _service

# Bound methods of the singleton, re-exported for module attribute lookup
# (``tracing.install()``, ``tracing.get_logger(...)``).
install = _service.install
configure = _service.configure
uninstall = _service.uninstall
get_logger = _service.get_logger
is_enabled = _service.is_enabled
current_log_path = _service.current_log_path

__all__ = [
    "LEVEL_NAMES",
    "DEFAULT_LEVEL",
    "resolve_level",
    "env_trace",
    "env_level",
    "install",
    "configure",
    "uninstall",
    "get_logger",
    "is_enabled",
    "current_log_path",
]
