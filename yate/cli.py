"""Command line entry point for yate.

Usage::

    yate                 # start with an empty buffer
    yate path/to/file    # open a file
    yate path/to/dir     # open a directory in the explorer
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional, Sequence

from yate import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="yate",
        description="yate - yet another terminal editor (Textual based)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  yate                      start with an empty buffer\n"
            "  yate README.md            edit a file\n"
            "  yate ./src                browse a directory\n"
            "  yate --keymap vim .       start with the vim key map\n"
            "  yate -u ~/.yate/yaterc    use a specific config file\n"
            "  yate -u NONE              start without loading any yaterc\n"
            "  yate --ext mytool.py      load an extension script\n"
            "  yate --theme-dir mythemes load custom color themes from a dir\n"
            "  yate --install-font       install the bundled Nerd Font and exit\n"
        ),
    )
    parser.add_argument("path", nargs="?", help="file or directory to open")
    parser.add_argument(
        "--keymap",
        choices=["vsc", "vim", "normal"],
        default=None,
        help="key map to start with (vsc = VS Code style; overrides yaterc; "
             "'normal' is accepted as an alias for vsc)",
    )
    parser.add_argument(
        "-u",
        "--yaterc",
        metavar="FILE",
        default=None,
        help="config file to load (vim-style -u); 'NONE' skips all yaterc "
             "loading. Without this flag yate reads ~/.yate/yaterc then a "
             "project-level ./yaterc (project wins)",
    )
    parser.add_argument(
        "--ext",
        dest="ext_files",
        action="append",
        default=[],
        metavar="FILE",
        help="load a Python extension script (repeatable)",
    )
    parser.add_argument(
        "--ext-dir",
        dest="ext_dirs",
        action="append",
        default=[],
        metavar="DIR",
        help="load all *.py extensions from a directory (repeatable)",
    )
    parser.add_argument(
        "--theme-dir",
        dest="theme_dirs",
        action="append",
        default=[],
        metavar="DIR",
        help="load custom *.py color themes from a directory (repeatable); "
             "defaults to ./themes and ~/.yate/themes when present",
    )
    parser.add_argument(
        "--install-font",
        action="store_true",
        help="install the bundled Nerd Font for the current user, configure "
             "Windows Terminal if possible, then exit",
    )
    parser.add_argument("--version", action="version", version=f"yate {__version__}")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    # Font setup runs without launching the TUI.
    if args.install_font:
        # Lazy import: font tooling is irrelevant to --help/--version paths.
        from yate.services import fonts  # pylint: disable=import-outside-toplevel

        status = fonts.font_status()
        if status.has_nerd_font:
            print(f"Nerd Font already available: {', '.join(status.installed_fonts[:3])}")
        result = fonts.ensure_font()
        print(result.detail)
        return 0 if result.has_nerd_font else 1

    # Resolve configuration (yaterc) before importing the TUI app.
    from yate.config import default_rc_paths, load_config
    from yate.editor_view import theme as theme_mod

    target = Path(args.path) if args.path else None
    if args.yaterc == "NONE":
        rc_paths: list[Path] = []
    elif args.yaterc:
        rc_paths = [Path(args.yaterc)]
    else:
        rc_paths = default_rc_paths(target)

    # Theme load priority (later wins on name collision, like rc files):
    # built-ins < default dirs < yaterc theme_dirs < explicit --theme-dir.
    default_errors: list[str] = []
    theme_mod.load_theme_paths(
        [Path.cwd() / "themes", Path.home() / ".yate" / "themes"],
        default_errors,
    )
    config = load_config(rc_paths)
    config.errors = default_errors + config.errors
    theme_mod.load_theme_paths(
        [Path(p) for p in args.theme_dirs], config.errors
    )

    # Imported lazily so ``--help`` / ``--version`` work without a terminal.
    from yate.app import YateApp

    keymap = None
    if args.keymap is not None:
        keymap = "vsc" if args.keymap == "normal" else args.keymap
    app = YateApp(
        target=target,
        keymap=keymap,
        config=config,
        ext_files=args.ext_files,
        ext_dirs=args.ext_dirs,
    )
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
