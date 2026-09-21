"""Thin shell re-exporting yate's crash diagnostics.

The implementation lives in :mod:`yate.logs` (one module for both the crash
report and the trace log); this module only keeps the historical import path
alive for the call sites that actually exist::

    from yate import crash
    crash.install()
    crash.crash_data_dir()
    crash.current_crash_file()

Anything without a caller is *not* carried here: the service object
(``yate.crash.crash``), ``build_err_path()``, ``cleanup_on_exit()`` and the
report-naming constants (``DATA_DIRNAME``, ``ERR_PREFIX``, ``ERR_SUFFIX``) are
reached through :mod:`yate.logs`.
"""

from __future__ import annotations

from yate.logs import crash_data_dir
# Private alias: the shell binds the singleton's methods below but never
# publishes the object itself.
from yate.logs import crash as _service

# Bound methods of the singleton, re-exported for module attribute lookup
# (``crash.install()``) -- and for ``patch("yate.crash.install")`` in tests.
install = _service.install
uninstall = _service.uninstall
current_crash_file = _service.current_crash_file

__all__ = [
    "crash_data_dir",
    "install",
    "uninstall",
    "current_crash_file",
]
