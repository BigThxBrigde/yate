"""Extension packages (``.yxp``): read, verify, install, uninstall, list.

A ``.yxp`` file is a zip archive holding extension payload plus
``manifest`` and ``checksum`` metadata members. See the submodules for
the implementation: :mod:`yate.services.yxp.manifest` (read/verify),
:mod:`yate.services.yxp.install` (install/uninstall/rollback) and
:mod:`yate.services.yxp.records` (ownership records and listing).

Package-root re-export exception note (architecture rules section 3.5,
architecture-boundaries): UI and service packages normally must not
re-export; this facade is a registered exception -- the consumer path
``from yate.services import yxp`` (and ``from yate.services.yxp import
YxpError``) is used by ``yate/commands.py``, ``yate/cli.py``,
``tools/yxp/cli.py`` and the test suite. The submodules are internal;
consumers import from here (R14 precedent: only the facade path is
public, and nothing imports ``yate.services.yxp.*`` submodules
directly).

Two wiring notes frozen by the unchanged test suite
(big-module-split-2 yxp plan-a correction, 2026-11-04):

* every submodule creates its logger with the explicit frozen name
  ``"yate.services.yxp"`` (not ``__name__``) -- ``tests/test_yxp.py``
  asserts caplog records on that logger name;
* the names the tests patch on this facade namespace or call directly
  (``_write_record``, ``read_package``, ``default_extensions_dir``,
  ``MAX_MEMBER_BYTES``, ``os`` to reach ``os.replace``, and the
  directly-called ``_read_member`` / ``_rollback_files`` /
  ``_restore_stale_files``) are re-exported here, while their in-package
  callers resolve them through a late-bound
  ``from yate.services import yxp as _facade`` lookup at call time.
  ``__all__`` is kept exactly equal to the re-exported, importable set.
"""

from __future__ import annotations

# pyright: reportPrivateUsage=false
# The yxp test suite patches and calls private names on this facade
# namespace (see the wiring notes in the docstring); the names stay
# package-internal while being re-exported here, which is the
# deliberate, plan-approved seam.
import os

from yate.services.yxp.install import (
    _restore_stale_files,
    _rollback_files,
    _write_record,
    install_package,
    uninstall_package,
)
from yate.services.yxp.manifest import (
    CHECKSUM_NAME,
    MANIFEST_NAME,
    MAX_MEMBER_BYTES,
    MAX_PAYLOAD_BYTES,
    NAME_RE,
    RECORDS_DIRNAME,
    RECORD_SUFFIX,
    InstalledPackage,
    InstallReport,
    UninstallReport,
    YxpError,
    YxpManifest,
    YxpPackage,
    _read_member,
    default_extensions_dir,
    read_package,
)
from yate.services.yxp.records import (
    format_install_report,
    format_package_list,
    format_uninstall_report,
    list_packages,
)

__all__ = [
    "CHECKSUM_NAME",
    "InstalledPackage",
    "InstallReport",
    "MANIFEST_NAME",
    "MAX_MEMBER_BYTES",
    "MAX_PAYLOAD_BYTES",
    "NAME_RE",
    "RECORDS_DIRNAME",
    "RECORD_SUFFIX",
    "UninstallReport",
    "YxpError",
    "YxpManifest",
    "YxpPackage",
    "_read_member",
    "_restore_stale_files",
    "_rollback_files",
    "_write_record",
    "default_extensions_dir",
    "format_install_report",
    "format_package_list",
    "format_uninstall_report",
    "install_package",
    "list_packages",
    "os",
    "read_package",
    "uninstall_package",
]
