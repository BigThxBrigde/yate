"""Command line interface: ``python -m tools.pack``.

Commands::

    python -m tools.pack icon                  # yate/yate.jpg -> pack/yate.ico
    python -m tools.pack icon --source logo.png --target out.ico
    python -m tools.pack icon --size 256 --size 64
    python -m tools.pack rosters               # product bitmaps -> roster.svg
    python -m tools.pack rosters --output out.svg
    python -m tools.pack wiki                  # regenerate the ../yate.wiki repo
    python -m tools.pack wiki --check          # gate: exit 1 on missing/stale en
    python -m tools.pack wiki --push           # commit + push origin/github
    python -m tools.pack wiki --jobs 8         # cap concurrent translations

``icon`` regenerates the Windows executable icon consumed by the
PyInstaller specs (see :mod:`tools.pack.icon`); run it after changing the
logo. The built ``.ico`` is committed, so a normal build
(``.\\pack\\pack.ps1`` / ``pack/pack.sh``) never needs Pillow.

``rosters`` regenerates the screensaver roster preview from the product
sprite pack (see :mod:`tools.pack.rosters`); run it after touching any
sprite bitmap.

Every failure is printed as ``error[<CODE>]: <message>`` on stderr (see
:mod:`tools.pack.errors`); tracebacks stay in the log channel and only
reach the terminal with ``wiki --debug``.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from tools import _util
from tools.pack import errors, icon, rosters, wiki
from tools.pack.errors import Code


def build_parser() -> argparse.ArgumentParser:
    """Build the parser for the ``icon`` / ``rosters`` / ``wiki`` subcommands."""
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
    wiki_cmd = subparsers.add_parser(
        "wiki",
        help="generate the bilingual project wiki into the sibling <repo>.wiki repo",
        description="Collect .trae documents (minus agents/rules/skills), the "
                    "bilingual guides and the manual, and publish them as "
                    "*.zh.md / *.en.md page pairs plus Home/_Sidebar "
                    "navigation into the <repo>.wiki git repository next to "
                    "the checkout. English pages live in the wiki repo itself "
                    "as the translation cache: with --translate-cmd only "
                    "missing and stale ones are re-translated (see "
                    "--translate-all). See tools.pack.wiki.",
    )
    wiki_cmd.add_argument(
        "--target",
        type=Path,
        default=None,
        metavar="DIR",
        help="wiki repository directory "
             "(default: <origin-url-basename>.wiki next to the checkout)",
    )
    wiki_cmd.add_argument(
        "--translate-cmd",
        default=None,
        metavar="CMD",
        help="shell command translating Chinese markdown on stdin to "
             "English on stdout (used for missing and stale pages; see "
             "--translate-all); it is run via the shell and must come "
             "from a trusted source",
    )
    wiki_cmd.add_argument(
        "--force",
        action="store_true",
        help="deprecated no-op, kept for compatibility: stale pages are "
             "re-translated whenever --translate-cmd is given",
    )
    wiki_cmd.add_argument(
        "--translate-all",
        action="store_true",
        help="with --translate-cmd, also re-translate fresh pages, "
             "overwriting their existing English pages (default: only "
             "translate pages that are missing or stale)",
    )
    wiki_cmd.add_argument(
        "--check",
        action="store_true",
        help="exit 1 when English pages are missing or stale (gate mode)",
    )
    wiki_cmd.add_argument(
        "--push",
        action="store_true",
        help="commit the wiki repo and push it to origin (gitee) and github",
    )
    wiki_cmd.add_argument(
        "--jobs",
        type=int,
        default=None,
        metavar="N",
        help="maximum number of concurrent translation tasks, each covering at "
             "most 10 documents; the value is clamped to the machine "
             "ceiling (CPU cores x 2, the default), so at most "
             "ceiling x 10 translators run at the same time",
    )
    wiki_cmd.add_argument(
        "--debug",
        action="store_true",
        help="also print the traceback of a failure (errors themselves are "
             "always reported as error[CODE]: message)",
    )
    return parser


def _icon(source: Path, target: Path, sizes: Sequence[int] | None) -> int:
    chosen = tuple(sizes) if sizes else icon.ICON_SIZES
    try:
        written = icon.build_icon(source, target, chosen)
    except errors.PackError as exc:
        errors.report(exc)
        return 1
    except (OSError, RuntimeError, ValueError) as exc:
        errors.report(errors.PackError(Code.ICON_BUILD, f"{exc}"))
        return 1
    print(
        f"wrote {written} ({written.stat().st_size // 1024} KB) "
        f"from {source} (sizes: {', '.join(str(s) for s in chosen)})"
    )
    return 0


def _rosters(output: Path) -> int:
    try:
        written = rosters.render_roster_svg(output)
    except errors.PackError as exc:
        errors.report(exc)
        return 1
    except (OSError, ValueError, KeyError, IndexError) as exc:
        # The roster builder indexes sprite frames directly, so a malformed
        # pack must still surface as ROSTERS-0302 rather than PKG-0001.
        errors.report(errors.PackError(Code.ROSTERS_RENDER, f"{exc}"))
        return 1
    print(f"wrote {written} ({written.stat().st_size // 1024} KB)")
    return 0


def _wiki(args: argparse.Namespace) -> int:
    debug = bool(args.debug)
    try:
        repo_root = _util.repo_root()
        target = (
            args.target
            if args.target is not None
            else wiki.default_target(repo_root)
        )
        return wiki.run(
            target,
            args.translate_cmd,
            force=args.force,
            translate_all=args.translate_all,
            check=args.check,
            push=args.push,
            repo_root=repo_root,
            jobs=args.jobs,
        )
    except errors.PackError as exc:
        errors.report(exc, debug=debug)
        return 1


def main(argv: Sequence[str] | None = None) -> int:
    """Dispatch the parsed arguments to the selected subcommand handler.

    A ``Ctrl+C`` during a long-running subcommand (wiki translation, git
    push) prints a one-line note on stderr and maps to exit code 130 --
    never a traceback.  Every other failure is rendered by
    :func:`tools.pack.errors.report` as ``error[<CODE>]: <message>`` and
    maps to exit code 1, including exceptions that escaped a subcommand's
    own guard: the CLI is the boundary where a traceback must never reach
    the terminal.
    """
    args = build_parser().parse_args(argv)
    debug = bool(getattr(args, "debug", False))
    try:
        if args.command == "icon":
            return _icon(args.source, args.target, args.sizes)
        if args.command == "rosters":
            return _rosters(args.output)
        if args.command == "wiki":
            return _wiki(args)
    except KeyboardInterrupt:
        print("\ntools.pack: interrupted", file=sys.stderr)
        return 130
    except errors.PackError as exc:
        errors.report(exc, debug=debug)
        return 1
    except Exception as exc:  # noqa: BLE001 - CLI boundary, must not leak tracebacks
        errors.report(exc, debug=debug)
        return 1
    build_parser().error(f"unknown command {args.command!r}")
    return 2
