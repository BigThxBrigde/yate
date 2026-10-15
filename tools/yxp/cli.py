"""Command line interface: ``python -m tools.yxp``.

Modes (mutually exclusive)::

    python -m tools.yxp --create my_ext              # scaffold ./my_ext/
    python -m tools.yxp --pack tools/yxp/example/hello_yxp
    python -m tools.yxp --pack SRC --output out.yxp --force
    python -m tools.yxp --verify hello_yxp.yxp

``--create NAME`` scaffolds a new extension package source directory: a
``manifest`` metadata file (name / version / description / author) plus a
starter ``<name>.py`` extension that registers one greeting command.  Pass
``--dir`` to choose the parent directory and ``--force`` to replace an
existing scaffold.

``--pack DIR`` packs a source directory into a ``.yxp`` archive.  The
directory must contain a ``manifest`` file -- JSON with the package
metadata (``name`` required; ``version`` / ``description`` / ``author``
optional).  The metadata is validated with the same rules the install-time
parser applies, so a packed archive always passes its own re-verification.
The ``files`` list is computed from the directory contents and
written into the packaged manifest, so it is never maintained by hand.
``checksum`` files in the source directory are metadata too and never
become payload.  ``--output`` overrides the default ``<name>.yxp`` in the
current directory, ``--force`` overwrites an existing archive.

``--verify FILE`` reads an existing ``.yxp`` with the same validator yate
uses at install time and prints the package summary; a tampered or
malformed archive fails with exit code 1.
"""

from __future__ import annotations

import argparse
import json
import shutil
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
#: Scaffold names double as directory and record names -- stay conservative.
_NAME_RE = yxp.NAME_RE
#: Starter module template written by ``--create``.
_STARTER_TEMPLATE: str = '''"""{name} -- yate extension package.

Built with ``python -m tools.yxp --pack``; install with
``yate --install-extension {name}.yxp`` and restart yate.
"""

from __future__ import annotations

from yate.services.extensions import ExtensionAPI


def setup(api: ExtensionAPI) -> None:
    """Register the {name} commands."""

    def hello(_args: str) -> None:
        """Show a greeting from the {name} extension."""
        api.message("hello from {name}!")

    api.register_command("hello-{command}", hello,
                         "greet from the {name} package")
'''


def build_parser() -> argparse.ArgumentParser:
    """Build the parser for the ``--create`` / ``--pack`` / ``--verify`` modes."""
    parser = argparse.ArgumentParser(
        prog="python -m tools.yxp",
        description="Build and verify yate extension packages (.yxp).",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--create",
        metavar="NAME",
        help="scaffold a new extension package source directory named NAME",
    )
    mode.add_argument(
        "--pack",
        type=Path,
        metavar="DIR",
        help="pack a source directory (with a manifest metadata file) into "
             "a .yxp archive",
    )
    mode.add_argument(
        "--verify",
        type=Path,
        metavar="FILE",
        help="validate an existing .yxp archive with the install-time rules",
    )
    parser.add_argument(
        "--dir",
        type=Path,
        default=None,
        metavar="DIR",
        help="[--create] parent directory for the scaffold "
             "(default: the current directory)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        metavar="FILE",
        help="[--pack] output .yxp path (default: <name>.yxp in the current "
             "directory)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="[--create] replace an existing scaffold; [--pack] overwrite "
             "the output archive",
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


def _validate_metadata(
    source: Path, metadata: dict[str, Any]
) -> tuple[str, str, str, str]:
    """Validate the metadata fields; return ``(name, version, desc, author)``.

    The packager enforces the same rules the install-time parser
    (:func:`yate.services.yxp.read_package`) applies, so an archive it
    writes can never fail re-verification over its metadata -- and a
    hand-written ``name`` cannot escape the default ``<name>.yxp`` output
    path.
    """
    manifest_path = source / yxp.MANIFEST_NAME
    name = metadata.get("name")
    if not isinstance(name, str) or not name:
        raise yxp.YxpError(
            f"{manifest_path}: field 'name' must be a non-empty string"
        )
    if not yxp.NAME_RE.match(name):
        raise yxp.YxpError(
            f"{manifest_path}: field 'name' {name!r} must match "
            f"{yxp.NAME_RE.pattern!r}"
        )
    for key in ("version", "description", "author"):
        value = metadata.get(key)
        if value is not None and not isinstance(value, str):
            raise yxp.YxpError(f"{manifest_path}: field {key!r} must be a string")
    if "files" in metadata:
        raise yxp.YxpError(
            f"{manifest_path}: drop the 'files' field -- the packager "
            "computes it from the directory contents"
        )
    return (
        name,
        cast(str, metadata.get("version")) or "0.1.0",
        cast(str, metadata.get("description")) or "",
        cast(str, metadata.get("author")) or "",
    )


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
    """Pack *source* into *output*; returns the packaged manifest.

    The source metadata is validated with the same rules the install-time
    parser applies (see :func:`_validate_metadata`), so a package this
    function writes always passes its own re-verification.
    """
    metadata = read_source_metadata(source)
    name, version, description, author = _validate_metadata(source, metadata)
    pairs = collect_payload(source)
    files = [rel for rel, _ in pairs]
    packaged_manifest = {**metadata, "files": files}
    try:
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(yxp.MANIFEST_NAME, json.dumps(packaged_manifest, indent=2))
            zf.writestr(
                yxp.CHECKSUM_NAME,
                json.dumps({rel: _digest(path) for rel, path in pairs}, indent=2),
            )
            for rel, path in pairs:
                zf.writestr(rel, path.read_bytes())
    except OSError as exc:
        if not output.is_dir():
            # a payload file became unreadable mid-pack: drop the partial
            # archive so no broken .yxp is left behind (when *output* is a
            # directory the open itself failed and nothing was written)
            output.unlink(missing_ok=True)
        raise yxp.YxpError(f"cannot pack {source} ({exc})") from exc
    return yxp.YxpManifest(
        name=name,
        version=version,
        description=description,
        author=author,
        files=tuple(files),
    )


def create_scaffold(name: str, parent: Path, force: bool = False) -> list[Path]:
    """Create a package source scaffold under *parent*; returns the files.

    With *force* an existing scaffold directory of the same name is
    removed and recreated.
    """
    if name in (".", "..") or not _NAME_RE.match(name):
        raise yxp.YxpError(
            f"invalid package name {name!r}: must match {_NAME_RE.pattern!r} "
            "without being '.' or '..' (it doubles as the directory and "
            "record name)"
        )
    target = parent / name
    if target.exists():
        if not force:
            raise yxp.YxpError(
                f"{target} already exists (use --force to replace)"
            )
        shutil.rmtree(target)
    command = name.lower().replace("_", "-").replace(".", "-")
    starter = _STARTER_TEMPLATE.format(name=name, command=command)
    manifest = {
        "name": name,
        "version": "0.1.0",
        "description": f"The {name} extension",
        "author": "your name",
    }
    try:
        target.mkdir(parents=True)
        (target / yxp.MANIFEST_NAME).write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )
        (target / f"{name}.py").write_text(starter, encoding="utf-8")
    except OSError as exc:
        raise yxp.YxpError(f"cannot scaffold {target} ({exc})") from exc
    return [target / yxp.MANIFEST_NAME, target / f"{name}.py"]


def _digest(path: Path) -> str:
    """SHA-256 hex digest of a file's bytes."""
    return sha256(path.read_bytes()).hexdigest()


def _summary(manifest: yxp.YxpManifest, archive: Path, verified: bool) -> str:
    """One-line pack/verify outcome."""
    state = "checksums verified" if verified else "unverified"
    return (
        f"{archive} ({manifest.name} {manifest.version}): "
        f"{len(manifest.files)} file(s), {state}"
    )


def _run_create(args: argparse.Namespace) -> int:
    """``--create`` mode: scaffold a source directory."""
    parent: Path = args.dir if args.dir is not None else Path.cwd()
    try:
        files = create_scaffold(args.create, parent, force=args.force)
    except yxp.YxpError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    for path in files:
        print(f"created {path}")
    target = args.dir / args.create if args.dir is not None else Path(args.create)
    print(f"next: python -m tools.yxp --pack {target.as_posix()}")
    return 0


def _run_pack(args: argparse.Namespace) -> int:
    """``--pack`` mode: pack a source directory."""
    source: Path = args.pack
    if not source.is_dir():
        print(f"error: {source} is not a directory", file=sys.stderr)
        return 1
    try:
        metadata = read_source_metadata(source)
        name, _, _, _ = _validate_metadata(source, metadata)
    except yxp.YxpError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    output: Path = args.output if args.output is not None else Path(f"{name}.yxp")
    if output.is_dir():
        print(f"error: {output} is a directory", file=sys.stderr)
        return 1
    if output.exists() and not args.force:
        print(
            f"error: {output} exists (use --force to overwrite)", file=sys.stderr
        )
        return 1
    try:
        manifest = build_package(source, output)
    except yxp.YxpError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    try:
        package = yxp.read_package(output)
    except yxp.YxpError as exc:
        # the freshly written archive failed its own re-verification:
        # drop it instead of leaving an uninstallable .yxp behind
        output.unlink(missing_ok=True)
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(_summary(manifest, output, package.checksums is not None))
    return 0


def _run_verify(args: argparse.Namespace) -> int:
    """``--verify`` mode: validate an existing archive."""
    try:
        package = yxp.read_package(args.verify)
    except yxp.YxpError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(_summary(package.manifest, args.verify, package.checksums is not None))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Run the requested mode; 0 on success, 1 on failure."""
    args = build_parser().parse_args(argv)
    if args.create is not None:
        return _run_create(args)
    if args.pack is not None:
        return _run_pack(args)
    return _run_verify(args)
