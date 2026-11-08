"""Install and uninstall ``.yxp`` packages, with rollback on failure.

Extraction re-verifies every digest at write time and records ownership
next to the payload; any failure after the first file lands restores the
previous installation exactly (overwritten files regain their old
content, stale-removed files reappear, fresh files are dropped).
See :mod:`yate.services.yxp` (the package facade) for the format
contract and the wiring notes.

This submodule is internal -- consumers enter through the
``yate.services.yxp`` facade.
"""

from __future__ import annotations

# pyright: reportPrivateUsage=false
# Package-internal split keeps the helpers private: install.py consumes
# private helpers of manifest.py / records.py (bounded, reviewed
# surface), and the facade re-exports the test-seam names the yxp test
# suite patches and calls directly.
import json
import os
import zipfile
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path, PurePosixPath

from yate.logs import tracing
from yate.services.yxp.manifest import (
    CHECKSUM_NAME,
    NAME_RE,
    RECORDS_DIRNAME,
    RECORD_SUFFIX,
    InstallReport,
    UninstallReport,
    YxpError,
    YxpManifest,
    YxpPackage,
    _read_member,
)
from yate.services.yxp.records import (
    _parse_record,
    _prune_empty_parents,
    _read_record_files,
    _unlink_quietly,
)

#: Trace logger ("yate.services.yxp"); silent unless yate_trace is on.
#: The name is frozen (not ``__name__``) so the unchanged caplog
#: assertions in tests/test_yxp.py keep matching after the split.
log = tracing.get_logger("yate.services.yxp")


def install_package(
    package_path: Path,
    base_dir: Path | None = None,
    *,
    allow_unverified: bool = False,
) -> InstallReport:
    """Verify *package_path* and extract its payload into *base_dir*.

    ``base_dir`` defaults to ``~/.yate/extensions``.  Reinstalling the same
    package name upgrades in place: its recorded files are overwritten and
    files dropped from the new version are removed.  A target file that
    exists but is not owned by the same package refuses the install (the
    user's own hand-placed files are never clobbered).  Every payload file
    is on disk before the record is written; a failure anywhere after the
    first file lands -- mid-extraction, while pruning stale files, or
    while writing the record -- restores the previous installation
    exactly (overwritten files get their old content back, stale-removed
    files reappear, fresh files are dropped) and raises
    :class:`YxpError`.

    *allow_unverified* defaults to ``False``: a package without a
    ``checksum`` member is rejected with :class:`YxpError` before any
    directory is created or any file is written.  Only an explicit
    ``True`` takes the historical unverified-install path (with a
    warning that the contents cannot be verified).
    """
    # Late-bound through the facade: tests patch ``yxp.read_package``,
    # ``yxp._write_record`` and ``yxp.default_extensions_dir`` on the
    # facade namespace, so these three must resolve at call time.
    from yate.services import yxp as _facade

    ext_dir = base_dir if base_dir is not None else _facade.default_extensions_dir()
    package = _facade.read_package(package_path)
    if package.checksums is None:
        if not allow_unverified:
            raise YxpError(
                f"cannot install {package.manifest.name}: missing "
                f"{CHECKSUM_NAME!r} member; pass --allow-unverified to "
                "install an unverified package"
            )
        log.warning(
            "installing extension package %s without a checksum member: "
            "contents cannot be verified",
            package.manifest.name,
        )
    manifest = package.manifest
    records = ext_dir / RECORDS_DIRNAME
    if records.is_symlink():
        raise YxpError(
            f"cannot install {manifest.name}: {records} is a symlink; "
            "refusing to operate through it"
        )
    try:
        ext_dir.mkdir(parents=True, exist_ok=True)
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
    previous = _extract_payload(package, ext_dir)
    stale_previous: dict[str, bytes] = {}
    try:
        stale_removed, stale_previous = _remove_stale_files(
            old_files, manifest, ext_dir
        )
        _facade._write_record(records, package)
    except YxpError:
        _rollback_files(manifest.files, previous, ext_dir)
        _restore_stale_files(stale_previous, ext_dir)
        raise
    log.info(
        "installed extension package %s %s: %d file(s) -> %s",
        manifest.name, manifest.version, len(manifest.files), ext_dir,
    )
    return InstallReport(
        name=manifest.name,
        version=manifest.version,
        files=manifest.files,
        stale_removed=stale_removed,
        target_dir=ext_dir,
    )


def _resolves_through_symlink(ext_dir: Path, rel: str) -> bool:
    """Any component of *rel* (parents and leaf) under *ext_dir* is a link.

    Only segments below *ext_dir* are inspected: a symlinked ``$HOME``
    or user directory above the install root is a legitimate user
    environment and must not fail every install.
    """
    probe = ext_dir
    for part in PurePosixPath(rel).parts:
        probe = probe / part
        if probe.is_symlink():
            return True
    return False


def _extract_payload(package: YxpPackage, ext_dir: Path) -> dict[str, bytes]:
    """Write every manifest file into *ext_dir*; roll back on failure.

    Returns the previous content of the package's own files this
    extraction overwrote (empty on a fresh install), so a later failure
    (the install record) can restore the old installation.  Each member
    is re-verified against the shipped digests before it reaches the
    disk -- :func:`read_package` validated the archive through one
    handle while extraction reopens the file.
    """
    extracted: list[str] = []
    previous: dict[str, bytes] = {}
    try:
        with zipfile.ZipFile(package.path) as zf:
            for rel in package.manifest.files:
                target = ext_dir / rel
                if _resolves_through_symlink(ext_dir, rel):
                    raise YxpError(
                        f"cannot install {package.manifest.name}: {rel!r} "
                        "resolves through a symlink; refusing to write "
                        "through it"
                    )
                if target.is_file():
                    previous[rel] = target.read_bytes()
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(_member_bytes(package, zf, rel))
                extracted.append(rel)
    except YxpError:
        _rollback_files(extracted, previous, ext_dir)
        raise
    except OSError as exc:
        _rollback_files(extracted, previous, ext_dir)
        raise YxpError(
            f"cannot install {package.manifest.name}: extraction failed ({exc})"
        ) from exc
    except zipfile.BadZipFile as exc:  # pragma: no cover - read_package validated
        _rollback_files(extracted, previous, ext_dir)
        raise YxpError(
            f"cannot install {package.manifest.name}: archive broke mid-read ({exc})"
        ) from exc
    return previous


def _member_bytes(package: YxpPackage, zf: zipfile.ZipFile, rel: str) -> bytes:
    """Read member *rel*, re-verifying its digest when checksums shipped.

    The bytes are checked against :attr:`YxpPackage.checksums` so payload
    swapped into the archive between :func:`read_package` and extraction
    cannot reach the disk.
    """
    data = _read_member(zf, rel, f"cannot install {package.manifest.name}")
    if (
        package.checksums is not None
        and sha256(data).hexdigest() != package.checksums[rel]
    ):
        raise YxpError(
            f"cannot install {package.manifest.name}: checksum mismatch for "
            f"{rel!r} at extraction time"
        )
    return data


def _rollback_files(
    extracted: list[str] | tuple[str, ...],
    previous: dict[str, bytes],
    ext_dir: Path,
) -> None:
    """Undo a partial extraction: restore overwritten files, drop new ones.

    A member whose path resolves through a symlink is skipped with a
    warning: rollback runs while the original failure is propagating, so
    it must never raise on its own.
    """
    for rel in extracted:
        target = ext_dir / rel
        if _resolves_through_symlink(ext_dir, rel):
            log.warning(
                "skipping rollback of %s: path resolves through a symlink",
                target,
            )
            continue
        if rel not in previous:
            _unlink_quietly(target)
            _prune_empty_parents(target.parent, ext_dir)
            continue
        try:
            target.write_bytes(previous[rel])
        except OSError:
            log.warning("could not restore previous content of %s", target)


def _restore_stale_files(previous: dict[str, bytes], ext_dir: Path) -> None:
    """Put back files deleted by a stale-file cleanup that must be undone.

    A member whose path resolves through a symlink is skipped with a
    warning rather than written through.
    """
    for rel, data in previous.items():
        target = ext_dir / rel
        if _resolves_through_symlink(ext_dir, rel):
            log.warning(
                "skipping restore of stale file %s: path resolves through "
                "a symlink",
                target,
            )
            continue
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        except OSError:
            log.warning("could not restore stale file %s", target)


def _remove_stale_files(
    old_files: set[str] | None, manifest: YxpManifest, ext_dir: Path
) -> tuple[tuple[str, ...], dict[str, bytes]]:
    """Upgrade path: delete own files dropped from the new manifest.

    Two phases: every stale path is validated first (one resolving
    through a symlink refuses the whole install before anything is
    touched), then the survivors are deleted -- no mid-set abort can
    leave a partially deleted set behind.  Returns the removed names
    plus their content, so a later failure (the install record) can put
    the files back.
    """
    if old_files is None:
        return (), {}
    stale = sorted(old_files - set(manifest.files))
    for rel in stale:
        if _resolves_through_symlink(ext_dir, rel):
            raise YxpError(
                f"cannot install {manifest.name}: {rel!r} resolves through "
                "a symlink; refusing to delete through it"
            )
    removed: list[str] = []
    previous: dict[str, bytes] = {}
    for rel in stale:
        target = ext_dir / rel
        if target.is_file() or target.is_symlink():
            try:
                previous[rel] = target.read_bytes()
            except OSError:
                log.warning("could not read stale file %s; keeping it", target)
                continue
            try:
                target.unlink()
            except OSError:
                log.warning("could not remove stale file %s", target)
                previous.pop(rel, None)
                continue
            _prune_empty_parents(target.parent, ext_dir)
            removed.append(rel)
    return tuple(removed), previous


# install_package resolves ``_write_record`` through the facade at call
# time (tests patch it there), so pyright sees no in-module caller;
# suppress the per-module unused-function diagnostic for that seam.
def _write_record(  # pyright: ignore[reportUnusedFunction]
    records: Path, package: YxpPackage
) -> None:
    """Persist the ownership record (manifest + checksums + timestamp).

    Written through a temporary file and moved into place with
    :func:`os.replace`, so an interrupted write can never leave a
    truncated record behind (a truncated record would block same-name
    upgrades until it is removed by hand).
    """
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
    tmp = records / f"{manifest.name}{RECORD_SUFFIX}.tmp"
    try:
        tmp.write_text(
            json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        os.replace(tmp, path)
    except OSError as exc:
        _unlink_quietly(tmp)
        raise YxpError(f"cannot write install record {path} ({exc})") from exc


# -------------------------------------------------------------- uninstall


def uninstall_package(name: str, base_dir: Path | None = None) -> UninstallReport:
    """Remove the recorded files of package *name* and its record.

    *name* must match :data:`NAME_RE` -- it becomes a file name under the
    records directory, so a loose name (``..``, separators) is rejected
    before it can reach the filesystem.  The records directory and every
    member path are validated first: one resolving through a symlink
    refuses the whole uninstall before anything is removed.
    """
    # Late-bound through the facade: tests patch ``yxp.default_extensions_dir``
    # on the facade namespace, so it must resolve at call time.
    from yate.services import yxp as _facade

    if not NAME_RE.match(name):
        raise YxpError(
            f"invalid package name {name!r}: must match {NAME_RE.pattern!r}"
        )
    ext_dir = base_dir if base_dir is not None else _facade.default_extensions_dir()
    records = ext_dir / RECORDS_DIRNAME
    if records.is_symlink():
        raise YxpError(
            f"cannot uninstall {name}: {records} is a symlink; refusing "
            "to operate through it"
        )
    record_path = records / f"{name}{RECORD_SUFFIX}"
    if not record_path.is_file():
        raise YxpError(f"extension package not installed: {name}")
    record = _parse_record(record_path)
    for rel in record.manifest.files:
        if _resolves_through_symlink(ext_dir, rel):
            raise YxpError(
                f"cannot uninstall {name}: {rel!r} resolves through a "
                "symlink; refusing to delete through it"
            )
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
