"""Command line interface: ``python -m tools.pack``.

Commands::

    python -m tools.pack icon                  # yate/yate.jpg -> pack/yate.ico
    python -m tools.pack icon --source logo.png --target out.ico
    python -m tools.pack icon --size 256 --size 64

``icon`` regenerates the Windows executable icon consumed by the
PyInstaller specs (see :mod:`tools.pack.icon`); run it after changing the
logo. The built ``.ico`` is committed, so a normal build
(``.\\pack\\pack.ps1`` / ``pack/pack.sh``) never needs Pillow.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from . import icon


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m tools.pack",
        description="Packaging helpers for the standalone executables.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    icon_cmd = subparsers.add_parser(
        "icon",
        help="build pack/yate.ico from the yate logo (yate/yate.jpg)",
        description="Convert the yate logo into the multi-resolution Windows "
                    "icon referenced by pack/yate.spec and "
                    "pack/yate-onefile.spec.",
    )
    icon_cmd.add_argument(
        "--source",
        type=Path,
        default=icon.DEFAULT_SOURCE,
        metavar="FILE",
        help=f"source image (default: {icon.DEFAULT_SOURCE})",
    )
    icon_cmd.add_argument(
        "--target",
        type=Path,
        default=icon.DEFAULT_TARGET,
        metavar="FILE",
        help=f"icon to write (default: {icon.DEFAULT_TARGET})",
    )
    icon_cmd.add_argument(
        "--size",
        dest="sizes",
        type=int,
        action="append",
        metavar="N",
        help="icon size in pixels, repeatable "
             f"(default: {', '.join(str(s) for s in icon.ICON_SIZES)})",
    )
    return parser


def _icon(source: Path, target: Path, sizes: Sequence[int] | None) -> int:
    chosen = tuple(sizes) if sizes else icon.ICON_SIZES
    try:
        written = icon.build_icon(source, target, chosen)
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"tools.pack: {exc}", file=sys.stderr)
        return 1
    print(
        f"wrote {written} ({written.stat().st_size // 1024} KB) "
        f"from {source} (sizes: {', '.join(str(s) for s in chosen)})"
    )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "icon":
        return _icon(args.source, args.target, args.sizes)
    build_parser().error(f"unknown command {args.command!r}")
    return 2
