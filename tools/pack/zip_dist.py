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


def _stage_files(stage: Path) -> list[tuple[Path, str]]:
    """Return ``(path, arcname)`` pairs for every archivable file in *stage*.

    Entries are sorted for deterministic entry order; ``smoke-out.txt`` is
    skipped.
    """
    entries: list[tuple[Path, str]] = []
    for path in sorted(stage.rglob("*")):
        if not path.is_file() or path.name in _TEMP_NAMES:
            continue
        arcname = f"{stage.name}/{path.relative_to(stage).as_posix()}"
        entries.append((path, arcname))
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


def _write_archive(target: Path, entries: list[tuple[Path, str]], *, posix: bool) -> None:
    """Write the zip archive for *entries* to *target*.

    A top-level ``<stage-name>/`` directory entry plus one entry per nested
    directory are written explicitly, and every file gets a :class:`zipfile.
    ZipInfo` with ``create_system = 3`` and an explicit ``external_attr`` so
    Unix mode bits survive extraction on either producing platform.
    """
    stage_name = entries[0][1].split("/", 1)[0]
    subdirs: set[str] = set()
    for _, arcname in entries:
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
        for path, arcname in entries:
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
    verbatim; only the last column (decoded as ASCII with replacement, never
    written back) decides whether a row is replaced.  Rows whose last column
    is *archive_name* (a ``*`` binary-mode prefix is tolerated) are removed;
    every other row is kept as-is, and the new ASCII row is appended at the
    end.  The result deliberately uses LF line endings for ``sha256sum -c``
    and ``shasum -c`` compatibility.
    """
    lines: list[bytes] = []
    if sums_path.exists():
        for line in sums_path.read_bytes().splitlines():
            parts = line.decode("ascii", errors="replace").split()
            if len(parts) >= 2 and parts[-1].lstrip("*") == archive_name:
                continue
            lines.append(line)
    lines.append(f"{digest}  {archive_name}".encode("ascii"))
    return b"\n".join(lines) + b"\n"


def archive_stage(stage: Path, dist_root: Path, *, posix: bool | None = None) -> ArchiveResult:
    """Zip *stage* into *dist_root* and upsert the checksum row.

    The zip and the updated ``SHA256SUMS.txt`` are each prepared in a
    same-directory temporary file and swapped in with :func:`os.replace`
    (zip first, checksum second); a failure never touches the previous
    archive and leaves no temporary files behind.
    """
    posix = os.name == "posix" if posix is None else posix
    if not stage.is_dir():
        raise ZipDistError(f"stage directory not found: {stage}")
    dist_root.mkdir(parents=True, exist_ok=True)
    archive = dist_root / f"{stage.name}.zip"
    sums_path = dist_root / "SHA256SUMS.txt"
    entries = _stage_files(stage)
    if not entries:
        raise ZipDistError("stage has no files to archive")
    fd, raw = tempfile.mkstemp(prefix=f".{stage.name}.", suffix=".zip.tmp", dir=dist_root)
    os.close(fd)
    zip_tmp = Path(raw)
    sums_tmp: Path | None = None
    try:
        _write_archive(zip_tmp, entries, posix=posix)
        digest = _digest(zip_tmp)
        size = zip_tmp.stat().st_size
        fd2, raw2 = tempfile.mkstemp(prefix=".SHA256SUMS.", suffix=".tmp", dir=dist_root)
        os.close(fd2)
        sums_tmp = Path(raw2)
        sums_tmp.write_bytes(_checksum_bytes(sums_path, archive.name, digest))
        os.replace(zip_tmp, archive)
        os.replace(sums_tmp, sums_path)
    finally:
        zip_tmp.unlink(missing_ok=True)
        if sums_tmp is not None:
            sums_tmp.unlink(missing_ok=True)
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
