"""Command line interface: ``python -m tools.yxp``.

Commands::

    python -m tools.yxp build tools/yxp/example/hello_yxp
    python -m tools.yxp build SRC --output out.yxp
    python -m tools.yxp verify hello-1.0.0.yxp

``build`` packs a source directory into a ``.yxp`` archive.  The directory
must contain a ``manifest`` file -- JSON with the package metadata (``name``
required; ``version`` / ``description`` / ``author`` optional).  The
``files`` list is computed from the directory contents and written into the
packaged manifest, so it is never maintained by hand.  ``checksum`` files in
the source directory are metadata too and never become payload.

``verify`` reads an existing ``.yxp`` with the same validator yate uses at
install time and prints the package summary; a tampered or malformed
archive fails with exit code 1.
"""

from __future__ import annotations

import argparse
import json
import sys
import zipfile
from collections.abc import Sequence
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

from yate.services import yxp

#: Source files that are package metadata, never payload.
_SKIPPED_SOURCES: frozenset[str] = frozenset(
    {yxp.MANIFEST_NAME, yxp.CHECKSUM_NAME}
)
#: Directories excluded from the payload walk.
_SKIP_DIRS: frozenset[str] = frozenset({"__pycache__", ".git"})
#: File suffixes excluded from the payload walk.
_SKIP_SUFFIXES: tuple[str, ...] = (".pyc", ".pyo")


def build_parser() -> argparse.ArgumentParser:
    """Build the parser for the ``build`` / ``verify`` subcommands."""
    parser = argparse.ArgumentParser(
        prog="python -m tools.yxp",
        description="Build and verify yate extension packages (.yxp).",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_cmd = subparsers.add_parser(
        "build",
        help="pack a source directory into a .yxp archive",
        description="Pack a source directory (with a manifest metadata file) "
                    "into a .yxp archive with a regenerated file list and "
                    "sha256 checksums.",
    )
    build_cmd.add_argument(
        "source",
        type=Path,
        metavar="DIR",
        help="source directory containing a 'manifest' metadata file",
    )
    build_cmd.add_argument(
        "--output",
        type=Path,
        default=None,
        metavar="FILE",
        help="output .yxp path (default: <name>.yxp in the current directory)",
    )
    build_cmd.add_argument(
        "--force",
        action="store_true",
        help="overwrite the output file if it exists",
    )

    verify_cmd = subparsers.add_parser(
        "verify",
        help="validate an existing .yxp archive",
        description="Run the same manifest/checksum validation yate performs "
                    "at install time and print the package summary.",
    )
    verify_cmd.add_argument(
        "package",
        type=Path,
        metavar="FILE",
        help="the .yxp archive to validate",
    )
    return parser


def read_source_metadata(source: Path) -> dict[str, Any]:
    """Parse the ``manifest`` metadata file of a source directory."""
    manifest_path = source / yxp.MANIFEST_NAME
    if not manifest_path.is_file():
        raise yxp.YxpError(
            f"{source}: missing {yxp.MANIFEST_NAME!r} metadata file"
        )
    try:
        raw = manifest_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise yxp.YxpError(f"cannot read {manifest_path} ({exc})") from exc
    try:
        data: Any = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise yxp.YxpError(f"{manifest_path} is not valid JSON ({exc})") from exc
    if not isinstance(data, dict):
        raise yxp.YxpError(f"{manifest_path} must contain a JSON object")
    return cast(dict[str, Any], data)


def collect_payload(source: Path) -> list[tuple[str, Path]]:
    """Payload ``(archive_name, path)`` pairs under *source*.

    The walk is recursive and sorted by archive name; ``__pycache__`` /
    ``.git`` directories, ``*.pyc`` / ``*.pyo`` files and the reserved
    ``manifest`` / ``checksum`` metadata files are excluded.
    """
    pairs: list[tuple[str, Path]] = []
    for path in source.rglob("*"):
        if path.is_dir():
            continue
        rel = path.relative_to(source).as_posix()
        if rel in _SKIPPED_SOURCES:
            continue
        if any(part in _SKIP_DIRS for part in path.relative_to(source).parts):
            continue
        if path.suffix.lower() in _SKIP_SUFFIXES:
            continue
        pairs.append((rel, path))
    return sorted(pairs)


def build_package(source: Path, output: Path) -> yxp.YxpManifest:
    """Pack *source* into *output*; returns the packaged manifest."""
    metadata = read_source_metadata(source)
    name = metadata.get("name")
    if not isinstance(name, str) or not name:
        raise yxp.YxpError(
            f"{source / yxp.MANIFEST_NAME}: field 'name' must be a "
            "non-empty string"
        )
    if "files" in metadata:
        raise yxp.YxpError(
            f"{source / yxp.MANIFEST_NAME}: drop the 'files' field -- the "
            "packager computes it from the directory contents"
        )
    pairs = collect_payload(source)
    files = [rel for rel, _ in pairs]
    packaged_manifest = {**metadata, "files": files}
    with zipfile.ZipFile(output, "w") as zf:
        zf.writestr(yxp.MANIFEST_NAME, json.dumps(packaged_manifest, indent=2))
        zf.writestr(
            yxp.CHECKSUM_NAME,
            json.dumps({rel: _digest(path) for rel, path in pairs}, indent=2),
        )
        for rel, path in pairs:
            zf.writestr(rel, path.read_bytes())
    return yxp.YxpManifest(
        name=name,
        version=str(metadata.get("version") or "0.1.0"),
        description=str(metadata.get("description") or ""),
        author=str(metadata.get("author") or ""),
        files=tuple(files),
    )


def _digest(path: Path) -> str:
    """SHA-256 hex digest of a file's bytes."""
    return sha256(path.read_bytes()).hexdigest()


def _summary(manifest: yxp.YxpManifest, archive: Path, verified: bool) -> str:
    """One-line build/verify outcome."""
    state = "checksums verified" if verified else "unverified"
    return (
        f"{archive} ({manifest.name} {manifest.version}): "
        f"{len(manifest.files)} file(s), {state}"
    )


def _run_build(args: argparse.Namespace) -> int:
    """``build`` subcommand: pack a source directory."""
    source: Path = args.source
    if not source.is_dir():
        print(f"error: {source} is not a directory", file=sys.stderr)
        return 1
    try:
        metadata = read_source_metadata(source)
        name = metadata.get("name")
        if not isinstance(name, str) or not name:
            raise yxp.YxpError(
                f"{source / yxp.MANIFEST_NAME}: field 'name' must be a "
                "non-empty string"
            )
    except yxp.YxpError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    output: Path = args.output if args.output is not None else Path(f"{name}.yxp")
    if output.exists() and not args.force:
        print(
            f"error: {output} exists (use --force to overwrite)", file=sys.stderr
        )
        return 1
    try:
        manifest = build_package(source, output)
        package = yxp.read_package(output)
    except yxp.YxpError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(_summary(manifest, output, package.checksums is not None))
    return 0


def _run_verify(args: argparse.Namespace) -> int:
    """``verify`` subcommand: validate an existing archive."""
    try:
        package = yxp.read_package(args.package)
    except yxp.YxpError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(_summary(package.manifest, args.package, package.checksums is not None))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Run the requested subcommand; 0 on success, 1 on failure."""
    args = build_parser().parse_args(argv)
    if args.command == "build":
        return _run_build(args)
    return _run_verify(args)
