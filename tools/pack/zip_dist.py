"""Post-build helper that zips a ``--dist`` stage and updates SHA256SUMS.txt.

Called by the platform build scripts (``pack/pack.ps1`` / ``pack/pack.sh``)
right after a successful smoke test::

    python -m tools.pack.zip_dist --stage <stage-dir> --dist-root <dist-dir>

The archive keeps ``<stage-name>/`` as its top-level directory, excludes the
smoke-test output file, preserves Unix mode bits on extracted files, and
upserts ``<hash>  <stage-name>.zip`` into ``<dist>/SHA256SUMS.txt``.  Both
the zip and the checksum file are written to same-directory temporary files
and swapped in with :func:`os.replace`, so a failure never leaves a partial
archive behind.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import stat
import sys
import tempfile
import time
import zipfile
from collections.abc import Sequence
from pathlib import Path
from typing import NamedTuple

#: Files the smoke test creates; they must never appear in the archive.
_TEMP_NAMES: frozenset[str] = frozenset({"smoke-out.txt"})

#: Executables that still need 0o755 on a Windows-produced archive.
_EXECUTABLE_NAMES: frozenset[str] = frozenset({"yate", "yate.exe"})

#: Streaming read chunk size for digest computation.
_CHUNK_SIZE = 1024 * 1024

#: Fixed timestamp for directory entries so repeated builds produce stable
#: archive metadata (file entries keep their real source mtime).
_ZIP_EPOCH: tuple[int, int, int, int, int, int] = (1980, 1, 1, 0, 0, 0)


class ZipDistError(Exception):
    """Raised when the stage cannot be archived."""


class ArchiveResult(NamedTuple):
    """Outcome of a successful :func:`archive_stage` call."""

    path: Path
    size: int
    digest: str
    checksum_path: Path


def _stage_files(root: Path, stage_name: str) -> list[tuple[Path, str, bool]]:
    """Return ``(path, arcname, is_link)`` triples for every archivable entry.

    Entries are sorted for deterministic entry order; ``smoke-out.txt`` is
    skipped.  Symbolic links are recorded as link entries (``is_link``
    ``True``) with their target text, never followed; their targets are
    neither read nor archived.  Any regular file whose resolved location is
    not inside *root* is rejected with :class:`ZipDistError` so a crafted
    stage cannot smuggle paths outside the stage directory into the archive.
    """
    entries: list[tuple[Path, str, bool]] = []
    for path in sorted(root.rglob("*")):
        if path.name in _TEMP_NAMES:
            continue
        arcname = f"{stage_name}/{path.relative_to(root).as_posix()}"
        if path.is_symlink():
            entries.append((path, arcname, True))
            continue
        if not path.is_file():
            continue
        real = path.resolve()
        if not real.is_relative_to(root):
            raise ZipDistError(f"stage entry escapes stage root: {path}")
        entries.append((path, arcname, False))
    return entries


def _file_mode(path: Path) -> int:
    """Return the POSIX permission bits of *path*."""
    return stat.S_IMODE(path.stat().st_mode)


def _unix_mode(path: Path, *, posix: bool) -> int:
    """Return the mode to store for *path* in the archive.

    With *posix* set, the real permission bits are kept; otherwise only the
    known executables get ``0o755`` (a Windows filesystem has no exec bit).
    """
    if posix:
        return _file_mode(path)
    return 0o755 if path.name in _EXECUTABLE_NAMES else 0o644


def _write_archive(
    target: Path, entries: list[tuple[Path, str, bool]], stage_name: str, *, posix: bool
) -> None:
    """Write the zip archive for *entries* to *target*.

    A top-level ``<stage-name>/`` directory entry plus one entry per nested
    directory are written explicitly, and every file gets a :class:`zipfile.
    ZipInfo` with ``create_system = 3`` and an explicit ``external_attr`` so
    Unix mode bits survive extraction on either producing platform.  Link
    entries are stored as symlinks (``S_IFLNK`` mode with the link target as
    content); their targets are never followed or read.
    """
    subdirs: set[str] = set()
    for _, arcname, _ in entries:
        parts = arcname.split("/")[:-1]
        for i in range(1, len(parts)):
            subdirs.add("/".join(parts[: i + 1]))
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        top = zipfile.ZipInfo(f"{stage_name}/", date_time=_ZIP_EPOCH)
        top.create_system = 3
        top.compress_type = zipfile.ZIP_DEFLATED
        top.external_attr = ((0o755 | stat.S_IFDIR) << 16)
        zf.writestr(top, b"")
        for name in sorted(subdirs):
            info = zipfile.ZipInfo(f"{name}/", date_time=_ZIP_EPOCH)
            info.create_system = 3
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = ((0o755 | stat.S_IFDIR) << 16)
            zf.writestr(info, b"")
        for path, arcname, is_link in entries:
            if is_link:
                info = zipfile.ZipInfo(
                    arcname, date_time=time.localtime(path.lstat().st_mtime)[:6]
                )
                info.compress_type = zipfile.ZIP_DEFLATED
                info.create_system = 3
                info.external_attr = ((0o777 | stat.S_IFLNK) << 16)
                zf.writestr(info, os.fsencode(os.readlink(path)))
                continue
            info = zipfile.ZipInfo(
                arcname, date_time=time.localtime(path.stat().st_mtime)[:6]
            )
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = ((_unix_mode(path, posix=posix) | stat.S_IFREG) << 16)
            zf.writestr(info, path.read_bytes())


def _digest(path: Path) -> str:
    """Return the SHA256 hex digest of *path*, read in streaming chunks."""
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(_CHUNK_SIZE):
            hasher.update(chunk)
    return hasher.hexdigest()


def _checksum_bytes(sums_path: Path, archive_name: str, digest: str) -> bytes:
    """Return new SHA256SUMS.txt content with *archive_name* upserted.

    Existing rows are handled as raw bytes so any encoding is preserved
    verbatim; only the last column (decoded as UTF-8 with surrogateescape,
    never written back) decides whether a row is replaced.  Whitespace
    splitting uses ``str.split()`` (Unicode whitespace), so a trailing
    full-width space no longer breaks the last-column match.  Rows whose
    last column is *archive_name* (a ``*`` binary-mode prefix is tolerated)
    are removed; every other row is kept as-is, and the new row is appended
    at the end with *archive_name* encoded losslessly via ``os.fsencode``.
    The result deliberately uses LF line endings for ``sha256sum -c`` and
    ``shasum -c`` compatibility.
    """
    lines: list[bytes] = []
    if sums_path.exists():
        for line in sums_path.read_bytes().splitlines():
            fields = line.decode("utf-8", errors="surrogateescape").split()
            if len(fields) >= 2 and fields[-1].lstrip("*") == archive_name:
                continue
            lines.append(line)
    lines.append(f"{digest}  ".encode("ascii") + os.fsencode(archive_name))
    return b"\n".join(lines) + b"\n"


def archive_stage(stage: Path, dist_root: Path, *, posix: bool | None = None) -> ArchiveResult:
    """Zip *stage* into *dist_root* and upsert the checksum row.

    The zip and the updated ``SHA256SUMS.txt`` are each prepared in a
    same-directory temporary file and swapped in with :func:`os.replace`
    transactionally: a failure before the swap leaves the previous archive
    untouched; any swap failure restores the previous archive from a copy
    backup; all temporary/lock files are cleaned up.  A lock file
    (``.<stage-name>.lock``)
    guards against concurrent archives of the same stage, and a dist root
    inside the stage is rejected.
    """
    posix = os.name == "posix" if posix is None else posix
    raw_name = stage.name
    if not raw_name or raw_name in {".", ".."}:
        raise ZipDistError(f"invalid stage directory name: {stage!r}")
    if not stage.is_dir():
        raise ZipDistError(f"stage directory not found: {stage}")
    root = stage.resolve()
    stage_name = root.name
    resolved_dist = dist_root.resolve()
    if resolved_dist == root or resolved_dist.is_relative_to(root):
        raise ZipDistError(f"dist root must not be inside the stage: {dist_root}")
    dist_root.mkdir(parents=True, exist_ok=True)
    lock_path = dist_root / f".{stage_name}.lock"
    try:
        lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except FileExistsError as exc:
        raise ZipDistError(
            f"another archive is in progress for {stage_name}: {lock_path}"
        ) from exc
    os.close(lock_fd)
    archive = dist_root / f"{stage_name}.zip"
    sums_path = dist_root / "SHA256SUMS.txt"
    entries = _stage_files(root, stage_name)
    if not entries:
        raise ZipDistError("stage has no files to archive")
    fd, raw = tempfile.mkstemp(prefix=f".{stage_name}.", suffix=".zip.tmp", dir=dist_root)
    os.close(fd)
    zip_tmp = Path(raw)
    sums_tmp: Path | None = None
    backup: Path | None = None
    try:
        _write_archive(zip_tmp, entries, stage_name, posix=posix)
        digest = _digest(zip_tmp)
        size = zip_tmp.stat().st_size
        fd2, raw2 = tempfile.mkstemp(prefix=".SHA256SUMS.", suffix=".tmp", dir=dist_root)
        os.close(fd2)
        sums_tmp = Path(raw2)
        sums_tmp.write_bytes(_checksum_bytes(sums_path, archive.name, digest))
        os.chmod(zip_tmp, 0o644)
        os.chmod(sums_tmp, 0o644)
        if archive.exists():
            fd3, raw3 = tempfile.mkstemp(
                prefix=f".{stage_name}.", suffix=".zip.bak", dir=dist_root
            )
            os.close(fd3)
            backup = Path(raw3)
            os.chmod(backup, 0o644)
            shutil.copyfile(archive, backup)
        try:
            os.replace(zip_tmp, archive)
            os.replace(sums_tmp, sums_path)
        except OSError:
            if backup is not None:
                os.replace(backup, archive)
                backup = None
            else:
                archive.unlink(missing_ok=True)
            raise
    finally:
        zip_tmp.unlink(missing_ok=True)
        if sums_tmp is not None:
            sums_tmp.unlink(missing_ok=True)
        if backup is not None:
            backup.unlink(missing_ok=True)
        lock_path.unlink(missing_ok=True)
    return ArchiveResult(archive, size, digest, sums_path)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the ``zip_dist`` command line interface and return an exit code."""
    parser = argparse.ArgumentParser(
        prog="python -m tools.pack.zip_dist",
        description="Zip a --dist stage directory and update SHA256SUMS.txt.",
    )
    parser.add_argument("--stage", type=Path, required=True, help="stage directory to archive")
    parser.add_argument("--dist-root", type=Path, required=True, help="distribution output root")
    args = parser.parse_args(argv)
    try:
        result = archive_stage(args.stage, args.dist_root)
    except (ZipDistError, OSError, ValueError, zipfile.BadZipFile) as exc:
        print(f"error: zip archive failed: {exc}", file=sys.stderr)
        return 1
    print(f"ZIP -> {result.path}  ({result.size / (1024 * 1024):.1f} MB)")
    print(f"  SHA256 {result.path.name}: {result.digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
