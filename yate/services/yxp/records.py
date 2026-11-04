"""Install records and the installed-package listing.

Each installed package owns a ``_manifests/<name>.json`` record next to
its payload; :func:`list_packages` reads those records and the
``format_*`` helpers render the user-facing reports.  See
:mod:`yate.services.yxp` (the package facade) for the format contract
and the wiring notes.

This submodule is internal -- consumers enter through the
``yate.services.yxp`` facade.
"""

from __future__ import annotations

# pyright: reportPrivateUsage=false
# Package-internal split keeps the helpers private: records.py consumes
# the private ``_parse_manifest`` of manifest.py, and the facade
# re-exports the test-seam names.
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from yate.logs import tracing
from yate.services.yxp.manifest import (
    RECORDS_DIRNAME,
    RECORD_SUFFIX,
    InstalledPackage,
    InstallReport,
    UninstallReport,
    YxpError,
    YxpManifest,
    _parse_manifest,
)

#: Trace logger ("yate.services.yxp"); silent unless yate_trace is on.
#: The name is frozen (not ``__name__``) so the unchanged caplog
#: assertions in tests/test_yxp.py keep matching after the split.
log = tracing.get_logger("yate.services.yxp")


@dataclass(frozen=True)
class _Record:
    """Parsed install record: the manifest fields plus the timestamp."""

    manifest: YxpManifest
    installed_at: str


def _parse_record(record_path: Path) -> _Record:
    """Load and validate an install record file."""
    try:
        raw = record_path.read_text(encoding="utf-8")
        data: Any = json.loads(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise YxpError(
            f"install record {record_path} is unreadable ({exc}); "
            "delete the file manually if it is corrupt"
        ) from exc
    if not isinstance(data, dict):
        raise YxpError(f"install record {record_path} must contain a JSON object")
    record_data = cast(dict[str, Any], data)
    installed_at = record_data.get("installed_at")
    try:
        manifest = _parse_manifest(cast(dict[str, Any], data), record_path.name)
    except YxpError as exc:
        raise YxpError(f"install record {record_path} is invalid: {exc}") from exc
    return _Record(
        manifest=manifest,
        installed_at=installed_at if isinstance(installed_at, str) else "",
    )


# Called only from install.py (package-internal split), so pyright sees
# no in-module caller; suppress the per-module unused-function diagnostic.
def _read_record_files(  # pyright: ignore[reportUnusedFunction]
    records: Path, name: str
) -> set[str] | None:
    """The previous file list of package *name*, or ``None`` if uninstalled."""
    record_path = records / f"{name}{RECORD_SUFFIX}"
    if not record_path.is_file():
        return None
    return set(_parse_record(record_path).manifest.files)


# ------------------------------------------------------------------- list


def list_packages(base_dir: Path | None = None) -> list[InstalledPackage]:
    """Every installed package, sorted by name.

    A record that fails validation is reported with ``error`` set instead
    of breaking the whole listing.
    """
    # Late-bound through the facade: tests patch ``yxp.default_extensions_dir``
    # on the facade namespace, so it must resolve at call time.
    from yate.services import yxp as _facade

    ext_dir = base_dir if base_dir is not None else _facade.default_extensions_dir()
    records = ext_dir / RECORDS_DIRNAME
    if not records.is_dir():
        return []
    packages: list[InstalledPackage] = []
    for record_path in sorted(records.glob(f"*{RECORD_SUFFIX}")):
        try:
            record = _parse_record(record_path)
        except YxpError as exc:
            packages.append(
                InstalledPackage(
                    name=record_path.stem,
                    version="",
                    description="",
                    author="",
                    file_count=0,
                    installed_at="",
                    error=str(exc),
                )
            )
            continue
        manifest = record.manifest
        packages.append(
            InstalledPackage(
                name=manifest.name,
                version=manifest.version,
                description=manifest.description,
                author=manifest.author,
                file_count=len(manifest.files),
                installed_at=record.installed_at,
            )
        )
    return packages


# -------------------------------------------------------------- utilities


# Called only from install.py (package-internal split), so pyright sees
# no in-module caller; suppress the per-module unused-function diagnostic.
def _unlink_quietly(path: Path) -> None:  # pyright: ignore[reportUnusedFunction]
    """Delete *path* if possible; report failures through the log only."""
    try:
        path.unlink()
    except OSError:
        log.warning("could not remove %s during rollback", path)


# Called only from install.py (package-internal split), so pyright sees
# no in-module caller; suppress the per-module unused-function diagnostic.
def _prune_empty_parents(  # pyright: ignore[reportUnusedFunction]
    directory: Path, stop: Path
) -> None:
    """Remove now-empty directories between *directory* and *stop*."""
    current = directory
    while current != stop and stop in current.parents:
        try:
            current.rmdir()
        except OSError:
            return
        current = current.parent


# -------------------------------------------------------------- formatting


def format_install_report(report: InstallReport) -> str:
    """One-line user-facing summary of :func:`install_package`."""
    text = (
        f"installed {report.name} {report.version}: "
        f"{len(report.files)} file(s) -> {report.target_dir}"
    )
    if report.stale_removed:
        text += f"; removed stale: {', '.join(report.stale_removed)}"
    return text


def format_uninstall_report(report: UninstallReport) -> str:
    """One-line user-facing summary of :func:`uninstall_package`."""
    text = f"removed {report.name}: {len(report.removed)} file(s)"
    if report.missing:
        text += f" (already absent: {', '.join(report.missing)})"
    return text


def format_package_list(packages: list[InstalledPackage]) -> str:
    """Multi-line listing for ``--list-extensions`` / ``:list-extensions``."""
    if not packages:
        return "no extension packages installed"
    lines: list[str] = []
    for package in packages:
        if package.error is not None:
            lines.append(f"{package.name}: unreadable install record")
        else:
            lines.append(
                f"{package.name} {package.version} -- {package.description} "
                f"({package.file_count} file(s))"
            )
    return "\n".join(lines)
