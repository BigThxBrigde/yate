"""Command line interface: ``python -m tools.pack``.

Commands::

    python -m tools.pack icon                  # yate/yate.jpg -> pack/yate.ico
    python -m tools.pack icon --source logo.png --target out.ico
    python -m tools.pack icon --size 256 --size 64
    python -m tools.pack rosters               # product bitmaps -> roster.svg
    python -m tools.pack rosters --output out.svg

``icon`` regenerates the Windows executable icon consumed by the
PyInstaller specs (see :mod:`tools.pack.icon`); run it after changing the
logo. The built ``.ico`` is committed, so a normal build
(``.\\pack\\pack.ps1`` / ``pack/pack.sh``) never needs Pillow.

``rosters`` regenerates the screensaver roster preview from the product
sprite pack (see :mod:`tools.pack.rosters`); run it after touching any
sprite bitmap.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from . import icon, rosters


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
    rosters_cmd = subparsers.add_parser(
        "rosters",
        help="render the screensaver roster preview SVG (roster.svg)",
        description="Render the full sprite roster preview from the product "
                    "bitmaps in yate.editor_sprites -- the single source of "
                    "truth the screensaver itself uses.",
    )
    rosters_cmd.add_argument(
        "--output",
        type=Path,
        default=rosters.DEFAULT_OUTPUT,
        metavar="FILE",
        help=f"SVG to write (default: {rosters.DEFAULT_OUTPUT})",
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


def _rosters(output: Path) -> int:
    try:
        written = rosters.render_roster_svg(output)
    except OSError as exc:
        print(f"tools.pack: {exc}", file=sys.stderr)
        return 1
    print(f"wrote {written} ({written.stat().st_size // 1024} KB)")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "icon":
        return _icon(args.source, args.target, args.sizes)
    if args.command == "rosters":
        return _rosters(args.output)
    build_parser().error(f"unknown command {args.command!r}")
    return 2
