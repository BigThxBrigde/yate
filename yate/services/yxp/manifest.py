"""Extension packages (``.yxp``): read, verify, install, uninstall, list.

A ``.yxp`` file (Yate eXtension Package) is a zip archive named ``*.yxp``
holding the extension's payload files plus two reserved metadata members:

* ``manifest`` -- JSON ``{"name", "version", "description", "author",
  "files"}``.  ``name`` is required and must match ``[A-Za-z0-9._-]+``;
  ``files`` lists every payload member and must match the archive exactly.
* ``checksum`` -- optional JSON mapping each payload member to its SHA-256
  hex digest.  When the member is present, installing verifies the file
  list and every digest; without it :func:`read_package` still returns
  ``YxpPackage(checksums=None)`` (the format contract), but
  :func:`install_package` rejects the package by default -- only an
  explicit ``allow_unverified=True`` installs it, with a warning (the
  bundled packager ``python -m tools.yxp`` always writes both members).

Installing extracts the payload flat into the user extensions directory
(``~/.yate/extensions``, the directory the startup loader already scans)
and records ownership in ``_manifests/<name>.json`` next to the files, so
uninstalling removes exactly the installed files and reinstalling the same
package upgrades in place while refusing to overwrite files it does not
own.  Neither a symlinked member target nor a symlinked intermediate
directory is ever written through or deleted through: the install fails
outright, and rollback skips such paths with a warning.  This module is
pure zip/hash/file logic: no Textual, no editor imports (R4 --
``services/*`` stays UI-free).

This submodule holds the archive reading / verification half; it is
internal -- consumers enter through the ``yate.services.yxp`` facade.
"""

from __future__ import annotations

import json
import re
import zipfile
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path, PurePosixPath
from typing import Any, Final, cast

from yate.logs import tracing
from yate.services.user_setup import default_base_dir

#: Trace logger ("yate.services.yxp"); silent unless yate_trace is on.
#: The name is frozen (not ``__name__``) so the unchanged caplog
#: assertions in tests/test_yxp.py keep matching after the split.
log = tracing.get_logger("yate.services.yxp")

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
NAME_RE: re.Pattern[str] = re.compile(r"^[A-Za-z0-9._-]+$")
#: SHA-256 hex digest, lowercase.
_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")
#: ``C:``-style drive prefixes are invalid inside an archive member but
#: ``PurePosixPath`` does not flag them, and on Windows ``Path("C:x")``
#: would escape the install directory.
_DRIVE_RE = re.compile(r"^[A-Za-z]:")

#: Hard caps for one .yxp payload (extensions are small scripts).
MAX_MEMBER_BYTES: Final[int] = 32 * 1024 * 1024
MAX_PAYLOAD_BYTES: Final[int] = 128 * 1024 * 1024

#: Chunk size for the bounded streaming read of archive members.
_READ_CHUNK: Final[int] = 1024 * 1024


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
            payload_names = set(payload)
            total_size = sum(
                zi.file_size for zi in zf.infolist() if zi.filename in payload_names
            )
            if total_size > MAX_PAYLOAD_BYTES:
                raise YxpError(
                    f"{package_path.name}: payload exceeds the size cap "
                    f"({total_size} > {MAX_PAYLOAD_BYTES} bytes)"
                )
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
    if name is None or not NAME_RE.match(name):
        raise YxpError(
            f"{source}: manifest 'name' must match {NAME_RE.pattern!r}"
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
    # On case-insensitive filesystems names differing only by letter case
    # would silently overwrite each other on disk, so they are rejected too.
    seen: set[tuple[str, ...]] = set()
    for entry in files:
        _check_member_name(entry)
        key = tuple(part.casefold() for part in PurePosixPath(entry).parts)
        if key in seen:
            raise YxpError(
                f"{source}: manifest 'files' contains case-colliding entries "
                f"({entry!r}); a package must not ship names differing only "
                "by letter case"
            )
        seen.add(key)
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


def _read_member(zf: zipfile.ZipFile, rel: str, source: str) -> bytes:
    """Read member *rel* with a bounded streaming read.

    The bytes are pulled in chunks and counted as they arrive, so a
    member that is larger than :data:`MAX_MEMBER_BYTES` -- or one whose
    ``ZipInfo.file_size`` lies about its real size -- is rejected before
    it can exhaust memory.  ``ZipInfo.file_size`` is deliberately not
    trusted.
    """
    # Late-bound through the facade: tests patch ``yxp.MAX_MEMBER_BYTES``
    # on the facade namespace, so the cap must be read at call time.
    from yate.services import yxp as _facade

    chunks: list[bytes] = []
    total = 0
    with zf.open(rel) as stream:
        while True:
            chunk = stream.read(_READ_CHUNK)
            if not chunk:
                break
            total += len(chunk)
            if total > _facade.MAX_MEMBER_BYTES:
                raise YxpError(
                    f"{source}: member {rel!r} exceeds the size cap"
                )
            chunks.append(chunk)
    return b"".join(chunks)


def _verify_digests(
    zf: zipfile.ZipFile, payload: list[str], checksums: dict[str, str], source: str
) -> None:
    """Every payload member must hash to its recorded digest."""
    for name in payload:
        digest = sha256(_read_member(zf, name, source)).hexdigest()
        if digest != checksums[name]:
            raise YxpError(
                f"{source}: checksum mismatch for {name!r} "
                f"(expected {checksums[name]}, got {digest})"
            )
