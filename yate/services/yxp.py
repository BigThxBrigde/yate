"""Extension packages (``.yxp``): read, verify, install, uninstall, list.

A ``.yxp`` file (Yate eXtension Package) is a zip archive named ``*.yxp``
holding the extension's payload files plus two reserved metadata members:

* ``manifest`` -- JSON ``{"name", "version", "description", "author",
  "files"}``.  ``name`` is required and must match ``[A-Za-z0-9._-]+``;
  ``files`` lists every payload member and must match the archive exactly.
* ``checksum`` -- optional JSON mapping each payload member to its SHA-256
  hex digest.  When the member is present, installing verifies the file
  list and every digest; without it the payload installs unverified (the
  format contract: the bundled packager ``python -m tools.yxp`` always
  writes both members).

Installing extracts the payload flat into the user extensions directory
(``~/.yate/extensions``, the directory the startup loader already scans)
and records ownership in ``_manifests/<name>.json`` next to the files, so
uninstalling removes exactly the installed files and reinstalling the same
package upgrades in place while refusing to overwrite files it does not
own.  This module is pure zip/hash/file logic: no Textual, no editor
imports (R4 -- ``services/*`` stays UI-free).
"""

from __future__ import annotations

import json
import re
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path, PurePosixPath
from typing import Any, cast

from yate.logs import tracing
from yate.services.user_setup import default_base_dir

#: Trace logger ("yate.services.yxp"); silent unless yate_trace is on.
log = tracing.get_logger(__name__)

#: Reserved archive member holding the package manifest (JSON).
MANIFEST_NAME: str = "manifest"
#: Reserved archive member holding the per-file SHA-256 digests (JSON).
CHECKSUM_NAME: str = "checksum"
#: Directory (inside the extensions dir) holding one install record per
#: package.  Invisible to the startup loader, which globs only top-level
#: ``*.py`` / ``*.lua`` files and never descends into directories.
RECORDS_DIRNAME: str = "_manifests"
#: Install-record file suffix (``_manifests/<name>.json``).
RECORD_SUFFIX: str = ".json"

#: Package names double as record file names, so they stay conservative.
_NAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")
#: SHA-256 hex digest, lowercase.
_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")
#: ``C:``-style drive prefixes are invalid inside an archive member but
#: ``PurePosixPath`` does not flag them, and on Windows ``Path("C:x")``
#: would escape the install directory.
_DRIVE_RE = re.compile(r"^[A-Za-z]:")


class YxpError(Exception):
    """A package could not be read, verified, installed or removed."""


def default_extensions_dir() -> Path:
    """The default install target (``~/.yate/extensions``)."""
    return default_base_dir() / "extensions"


# ------------------------------------------------------------------ records


@dataclass(frozen=True)
class YxpManifest:
    """Parsed ``manifest`` member."""

    name: str
    version: str
    description: str
    author: str
    files: tuple[str, ...]


@dataclass(frozen=True)
class YxpPackage:
    """A validated ``.yxp`` archive.  ``checksums`` is ``None`` when the
    package ships no ``checksum`` member (payload installs unverified)."""

    path: Path
    manifest: YxpManifest
    checksums: dict[str, str] | None


@dataclass(frozen=True)
class InstallReport:
    """Outcome of :func:`install_package`."""

    name: str
    version: str
    files: tuple[str, ...]
    stale_removed: tuple[str, ...]
    target_dir: Path


@dataclass(frozen=True)
class UninstallReport:
    """Outcome of :func:`uninstall_package`."""

    name: str
    removed: tuple[str, ...]
    missing: tuple[str, ...]


@dataclass(frozen=True)
class InstalledPackage:
    """One install record as reported by :func:`list_packages`."""

    name: str
    version: str
    description: str
    author: str
    file_count: int
    installed_at: str
    error: str | None = None


# ------------------------------------------------------------------- read


def read_package(package_path: Path) -> YxpPackage:
    """Read and validate *package_path*, verifying checksums when present.

    Raises :class:`YxpError` with a user-facing message when the archive is
    not a zip, misses (or duplicates) the manifest member, carries unsafe
    member names, disagrees with its own file list, or fails checksum
    verification.
    """
    try:
        with zipfile.ZipFile(package_path) as zf:
            file_names = [n for n in zf.namelist() if not n.endswith("/")]
            for name in file_names:
                _check_member_name(name)
            if file_names.count(MANIFEST_NAME) != 1:
                raise YxpError(
                    f"{package_path.name}: expected exactly one "
                    f"{MANIFEST_NAME!r} member, found "
                    f"{file_names.count(MANIFEST_NAME)}"
                )
            if file_names.count(CHECKSUM_NAME) > 1:
                raise YxpError(
                    f"{package_path.name}: expected at most one "
                    f"{CHECKSUM_NAME!r} member"
                )
            manifest = _parse_manifest(
                _load_json_member(zf, MANIFEST_NAME, package_path.name),
                package_path.name,
            )
            payload = [
                n for n in file_names if n not in (MANIFEST_NAME, CHECKSUM_NAME)
            ]
            _check_file_list(manifest, payload, package_path.name)
            checksums: dict[str, str] | None = None
            if CHECKSUM_NAME in file_names:
                checksums = _parse_checksums(
                    _load_json_member(zf, CHECKSUM_NAME, package_path.name),
                    payload,
                    package_path.name,
                )
                _verify_digests(zf, payload, checksums, package_path.name)
            return YxpPackage(
                path=package_path, manifest=manifest, checksums=checksums
            )
    except zipfile.BadZipFile as exc:
        raise YxpError(f"{package_path.name}: not a valid zip archive") from exc
    except OSError as exc:
        raise YxpError(f"{package_path.name}: cannot read package ({exc})") from exc


def _load_json_member(zf: zipfile.ZipFile, member: str, source: str) -> dict[str, Any]:
    """Read and JSON-decode *member*, narrowing to a JSON object."""
    try:
        raw = zf.read(member).decode("utf-8")
    except (UnicodeDecodeError, zipfile.BadZipFile) as exc:
        raise YxpError(f"{source}: cannot read {member!r} member ({exc})") from exc
    try:
        data: Any = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise YxpError(f"{source}: {member!r} is not valid JSON ({exc})") from exc
    if not isinstance(data, dict):
        raise YxpError(f"{source}: {member!r} must contain a JSON object")
    return cast(dict[str, Any], data)


def _check_member_name(name: str) -> None:
    """Reject unsafe or non-portable archive member names (zip-slip guard)."""
    if "\\" in name:
        raise YxpError(f"archive member {name!r}: backslash is not allowed")
    if _DRIVE_RE.match(name) or name.startswith("/"):
        raise YxpError(f"archive member {name!r}: absolute paths are not allowed")
    parts = PurePosixPath(name).parts
    if not parts or ".." in parts:
        raise YxpError(
            f"archive member {name!r}: empty or '..' path segments are not allowed"
        )
    if parts[0] == RECORDS_DIRNAME:
        raise YxpError(
            f"archive member {name!r}: {RECORDS_DIRNAME!r} is a reserved directory"
        )


def _manifest_str(
    data: dict[str, Any], key: str, source: str, *, required: bool
) -> str | None:
    """Read an optional string field from a manifest object."""
    value = data.get(key)
    if value is None:
        if required:
            raise YxpError(f"{source}: manifest field {key!r} is required")
        return None
    if not isinstance(value, str):
        raise YxpError(f"{source}: manifest field {key!r} must be a string")
    return value


def _parse_manifest(data: dict[str, Any], source: str) -> YxpManifest:
    """Validate the manifest object into a :class:`YxpManifest`."""
    name = _manifest_str(data, "name", source, required=True)
    if name is None or not _NAME_RE.match(name):
        raise YxpError(
            f"{source}: manifest 'name' must match {_NAME_RE.pattern!r}"
        )
    version = _manifest_str(data, "version", source, required=False) or "0.1.0"
    description = _manifest_str(data, "description", source, required=False) or ""
    author = _manifest_str(data, "author", source, required=False) or ""
    files_raw = data.get("files")
    if not isinstance(files_raw, list):
        raise YxpError(f"{source}: manifest 'files' must be a list of strings")
    # json boundary: validate element types one by one, then narrow the list.
    entries = cast(list[object], files_raw)
    for entry in entries:
        if not isinstance(entry, str):
            raise YxpError(f"{source}: manifest 'files' must be a list of strings")
    files = tuple(cast(list[str], files_raw))
    if len(set(files)) != len(files):
        raise YxpError(f"{source}: manifest 'files' contains duplicates")
    for entry in files:
        _check_member_name(entry)
    return YxpManifest(
        name=name,
        version=version,
        description=description,
        author=author,
        files=files,
    )


def _check_file_list(
    manifest: YxpManifest, payload: list[str], source: str
) -> None:
    """The manifest file list must describe the archive payload exactly."""
    listed = set(manifest.files)
    present = set(payload)
    missing = sorted(listed - present)
    extra = sorted(present - listed)
    if missing or extra:
        details: list[str] = []
        if missing:
            details.append(f"missing from the archive: {', '.join(missing)}")
        if extra:
            details.append(f"not listed in the manifest: {', '.join(extra)}")
        raise YxpError(f"{source}: file list mismatch ({'; '.join(details)})")


def _parse_checksums(
    data: dict[str, Any], payload: list[str], source: str
) -> dict[str, str]:
    """Validate the ``checksum`` member against the payload file list."""
    checksums: dict[str, str] = {}
    for key, value in data.items():
        if not isinstance(value, str):
            raise YxpError(f"{source}: {CHECKSUM_NAME!r} must map file names "
                           "to hex digests")
        checksums[key] = value
    expected = set(payload)
    unlisted = sorted(set(checksums) - expected)
    uncovered = sorted(expected - set(checksums))
    if unlisted or uncovered:
        details: list[str] = []
        if unlisted:
            details.append(f"no such payload file: {', '.join(unlisted)}")
        if uncovered:
            details.append(f"no digest for: {', '.join(uncovered)}")
        raise YxpError(f"{source}: checksum list mismatch ({'; '.join(details)})")
    for name, digest in checksums.items():
        if not _DIGEST_RE.match(digest):
            raise YxpError(
                f"{source}: checksum for {name!r} is not a sha256 hex digest"
            )
    return checksums


def _verify_digests(
    zf: zipfile.ZipFile, payload: list[str], checksums: dict[str, str], source: str
) -> None:
    """Every payload member must hash to its recorded digest."""
    for name in payload:
        digest = sha256(zf.read(name)).hexdigest()
        if digest != checksums[name]:
            raise YxpError(
                f"{source}: checksum mismatch for {name!r} "
                f"(expected {checksums[name]}, got {digest})"
            )


# ---------------------------------------------------------------- install


def install_package(
    package_path: Path, base_dir: Path | None = None
) -> InstallReport:
    """Verify *package_path* and extract its payload into *base_dir*.

    ``base_dir`` defaults to ``~/.yate/extensions``.  Reinstalling the same
    package name upgrades in place: its recorded files are overwritten and
    files dropped from the new version are removed.  A target file that
    exists but is not owned by the same package refuses the install (the
    user's own hand-placed files are never clobbered).  The record is
    written only after every payload file is on disk; a failed extraction
    removes the partial files and leaves any previous installation intact.
    """
    ext_dir = base_dir if base_dir is not None else default_extensions_dir()
    package = read_package(package_path)
    manifest = package.manifest
    try:
        ext_dir.mkdir(parents=True, exist_ok=True)
        records = ext_dir / RECORDS_DIRNAME
        records.mkdir(exist_ok=True)
    except OSError as exc:
        raise YxpError(f"cannot prepare {ext_dir} ({exc})") from exc
    old_files = _read_record_files(records, manifest.name)
    collisions = sorted(
        rel
        for rel in manifest.files
        if (ext_dir / rel).exists() and (old_files is None or rel not in old_files)
    )
    if collisions:
        raise YxpError(
            f"cannot install {manifest.name}: target files already exist and "
            f"belong to another package or to you: {', '.join(collisions)}"
        )
    extracted = _extract_payload(package, ext_dir)
    stale_removed = _remove_stale_files(old_files, manifest, ext_dir)
    _write_record(records, package)
    log.info(
        "installed extension package %s %s: %d file(s) -> %s",
        manifest.name, manifest.version, len(extracted), ext_dir,
    )
    return InstallReport(
        name=manifest.name,
        version=manifest.version,
        files=tuple(extracted),
        stale_removed=stale_removed,
        target_dir=ext_dir,
    )


def _extract_payload(package: YxpPackage, ext_dir: Path) -> list[str]:
    """Write every manifest file into *ext_dir*; roll back on failure."""
    extracted: list[str] = []
    try:
        with zipfile.ZipFile(package.path) as zf:
            for rel in package.manifest.files:
                target = ext_dir / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(zf.read(rel))
                extracted.append(rel)
    except OSError as exc:
        for rel in extracted:
            _unlink_quietly(ext_dir / rel)
        raise YxpError(
            f"cannot install {package.manifest.name}: extraction failed ({exc})"
        ) from exc
    except zipfile.BadZipFile as exc:  # pragma: no cover - read_package validated
        for rel in extracted:
            _unlink_quietly(ext_dir / rel)
        raise YxpError(
            f"cannot install {package.manifest.name}: archive broke mid-read ({exc})"
        ) from exc
    return extracted


def _remove_stale_files(
    old_files: set[str] | None, manifest: YxpManifest, ext_dir: Path
) -> tuple[str, ...]:
    """Upgrade path: delete own files dropped from the new manifest."""
    if old_files is None:
        return ()
    removed: list[str] = []
    for rel in sorted(old_files - set(manifest.files)):
        target = ext_dir / rel
        if target.is_file() or target.is_symlink():
            try:
                target.unlink()
            except OSError:
                log.warning("could not remove stale file %s", target)
                continue
            _prune_empty_parents(target.parent, ext_dir)
            removed.append(rel)
    return tuple(removed)


def _write_record(records: Path, package: YxpPackage) -> None:
    """Persist the ownership record (manifest + checksums + timestamp)."""
    manifest = package.manifest
    record = {
        "name": manifest.name,
        "version": manifest.version,
        "description": manifest.description,
        "author": manifest.author,
        "files": list(manifest.files),
        "checksums": package.checksums,
        "installed_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    path = records / f"{manifest.name}{RECORD_SUFFIX}"
    try:
        path.write_text(
            json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    except OSError as exc:
        raise YxpError(f"cannot write install record {path} ({exc})") from exc


# -------------------------------------------------------------- uninstall


def uninstall_package(name: str, base_dir: Path | None = None) -> UninstallReport:
    """Remove the recorded files of package *name* and its record."""
    ext_dir = base_dir if base_dir is not None else default_extensions_dir()
    record_path = ext_dir / RECORDS_DIRNAME / f"{name}{RECORD_SUFFIX}"
    if not record_path.is_file():
        raise YxpError(f"extension package not installed: {name}")
    record = _parse_record(record_path)
    removed: list[str] = []
    missing: list[str] = []
    for rel in record.manifest.files:
        target = ext_dir / rel
        if target.is_file() or target.is_symlink():
            try:
                target.unlink()
            except OSError as exc:
                raise YxpError(f"cannot remove {target} ({exc})") from exc
            _prune_empty_parents(target.parent, ext_dir)
            removed.append(rel)
        else:
            missing.append(rel)
    try:
        record_path.unlink()
    except OSError as exc:
        raise YxpError(f"cannot remove install record {record_path} ({exc})") from exc
    log.info("uninstalled extension package %s: %d file(s)", name, len(removed))
    return UninstallReport(name=name, removed=tuple(removed), missing=tuple(missing))


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


def _read_record_files(records: Path, name: str) -> set[str] | None:
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
    ext_dir = base_dir if base_dir is not None else default_extensions_dir()
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


def _unlink_quietly(path: Path) -> None:
    """Delete *path* if possible; report failures through the log only."""
    try:
        path.unlink()
    except OSError:
        log.warning("could not remove %s during rollback", path)


def _prune_empty_parents(directory: Path, stop: Path) -> None:
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
