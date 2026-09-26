"""Command line entry point for yate.

Usage::

    yate                 # start with an empty buffer
    yate path/to/file    # open a file
    yate path/to/dir     # open a directory in the explorer
"""

from __future__ import annotations

import argparse
import platform
import sys
from pathlib import Path

from collections.abc import Sequence

from yate import __description__, __version__


# ------------------------------------------------------------------ version

def version_lines() -> str:
    """yate / description / Python / platform information (``--version``).

    Lives here instead of :mod:`yate.diagnostics` so ``--version`` only pays
    for this leaf module: diagnostics needs ``yate.editor`` for its report
    signatures, which would drag in the whole TUI stack.
    """
    impl = platform.python_implementation()
    return (
        f"yate {__version__} — {__description__}\n"
        f"Python {platform.python_version()} ({impl})\n"
        f"{platform.platform()}"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="yate",
        description=f"yate - {__description__}",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  yate                      start with an empty buffer\n"
            "  yate README.md            edit a file\n"
            "  yate ./src                browse a directory\n"
            "  yate --keymap vim .       start with the vim key map\n"
            "  yate -u ~/.yate/yaterc    use a specific config file\n"
            "  yate -u NONE              start without loading any yaterc\n"
            "  yate --ext mytool.py      load an extension script (repeatable)\n"
            "  yate --ext-dir myexts     load every extension in a directory\n"
            "  yate --theme-dir mythemes load custom color themes from a dir\n"
            "  yate --theme my-mocha     start with a (custom) color theme\n"
            "  yate --changelog zh       print the changelog (en|zh) and exit\n"
            "  yate --install-font       install the bundled Nerd Font and exit\n"
            "  yate --diag               print the environment & config report and exit\n"
            "  yate --setup-defaults     create ~/.yate with a default yaterc\n"
            "                            and bundled *.example templates, then exit\n"
            "  yate --cleanup-defaults   remove ~/.yate config (data/ kept unless\n"
            "                            --include-data), then exit\n"
        ),
    )
    parser.add_argument("path", nargs="?", help="file or directory to open")
    parser.add_argument(
        "--readonly",
        action="store_true",
        help="open the file argument read-only (edits and saves are "
             "refused; ignored when the argument is a directory)",
    )
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
        help="load custom *.py color themes from a directory or from a single "
             "*.py file (repeatable); defaults to ./themes and ~/.yate/themes "
             "when present",
    )
    parser.add_argument(
        "--theme",
        dest="theme",
        default=None,
        metavar="NAME",
        help="color theme to start with (a built-in name or a custom theme "
             "registered from yaterc/theme dirs; overrides the yaterc theme)",
    )
    parser.add_argument(
        "--install-font",
        action="store_true",
        help="install the bundled Nerd Font for the current user, configure "
             "Windows Terminal if possible, then exit",
    )
    setup_group = parser.add_mutually_exclusive_group()
    setup_group.add_argument(
        "--setup-defaults",
        action="store_true",
        help="create ~/.yate with a default yaterc and the bundled theme/"
             "extension *.example templates (rename one to *.py to activate), "
             "then exit",
    )
    setup_group.add_argument(
        "--cleanup-defaults",
        action="store_true",
        help="remove ~/.yate configuration (yaterc, themes, extensions; "
             "data/ kept unless --include-data), asking for confirmation, "
             "then exit",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="with --setup-defaults: replace an existing yaterc (a .yate-bak "
             "backup is kept); with --cleanup-defaults: skip confirmation",
    )
    parser.add_argument(
        "--include-data",
        action="store_true",
        help="with --cleanup-defaults: also delete the ~/.yate/data crash logs",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="print yate / Python / platform version information and exit",
    )
    parser.add_argument(
        "--changelog",
        nargs="?",
        const="en",
        choices=["en", "zh"],
        default=None,
        metavar="LANG",
        help="print the changelog (en|zh, default en) and exit",
    )
    parser.add_argument(
        "--diag",
        action="store_true",
        help="print a full environment & configuration diagnostics report "
             "(extensions, LSP, fonts, ...) and exit",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    # Best-effort native-crash / uncaught-exception log (~/.yate/data/).
    # First line so even startup failures are covered.
    from yate.logs import crash, tracing  # pylint: disable=import-outside-toplevel

    crash.install()
    # Trace pass 1: environment only (YATE_TRACE / YATE_TRACE_LEVEL), so
    # startup itself is observable. Pass 2 after load_config() merges the
    # yaterc options yate_trace / yate_trace_level.
    tracing.install()

    parser = build_parser()
    args = parser.parse_args(argv)

    # --version prints basic information without loading any configuration
    # or touching the terminal. Handle it first so it stays instant.
    if args.version:
        print(version_lines())
        return 0

    # --changelog prints the bundled changelog and exits. Like --version it
    # only reads importlib.resources: no config, no app, no terminal.
    if args.changelog is not None:
        # Lazy import keeps --help/--version free of TUI-side imports.
        from yate.editor_view.manual import (  # pylint: disable=import-outside-toplevel
            load_changelog_markdown,
        )

        print(load_changelog_markdown(args.changelog))
        return 0

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

    # User-directory initialization/cleanup runs without launching the TUI
    # and without loading any configuration.
    if args.setup_defaults:
        from yate.services import user_setup  # pylint: disable=import-outside-toplevel

        report = user_setup.setup_defaults(force=args.force)
        print(user_setup.format_setup_report(report))
        return 1 if report.errors else 0

    if args.cleanup_defaults:
        from yate.services import user_setup  # pylint: disable=import-outside-toplevel

        # The crash handler keeps data/crash-*.err open for the process
        # lifetime; on Windows that handle blocks removing data/. Release it
        # before deleting (no diagnostics are needed for an exit-only CLI).
        # Same for an open trace log under data/logs/.
        if args.include_data:
            from yate.logs import crash, tracing  # pylint: disable=import-outside-toplevel

            crash.uninstall()
            tracing.uninstall()
        try:
            report = user_setup.cleanup_defaults(
                force=args.force, include_data=args.include_data
            )
        except user_setup.ConfirmationRequiredError as exc:
            print(str(exc))
            return 2
        print(user_setup.format_cleanup_report(report))
        return 1 if report.errors else 0

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
    # Theme callbacks are injected (N30): the L0 config loader must not
    # import the L2 UI package itself.
    config = load_config(
        rc_paths,
        register_theme=theme_mod.register_theme,
        load_theme_paths=theme_mod.load_theme_paths,
    )
    config.errors = default_errors + config.errors
    # Expand "~" here: unlike POSIX shells, PowerShell/cmd pass it through
    # literally and Path("~")/is_dir() would silently skip the directory.
    theme_mod.load_theme_paths(
        [Path(p).expanduser() for p in args.theme_dirs], config.errors
    )

    # Trace pass 2: yaterc's yate_trace / yate_trace_level are known now.
    # An environment variable still wins over the rc files. configure() is
    # the rc-stage spelling of install(): the level name is resolved inside
    # the service, not here.
    tracing.configure(
        yate_trace=config.yate_trace,
        yate_trace_level=config.yate_trace_level,
    )
    log = tracing.get_logger("cli")
    log.info("startup: argv=%r cwd=%s", sys.argv, Path.cwd())
    log.info(
        "rc files: %s",
        [str(p) for p in config.sources] or "<none>",
    )
    log.info(
        "resolved: keymap=%s theme=%s tab_width=%s use_spaces=%s "
        "yate_trace=%s yate_trace_level=%s",
        config.keymap, config.theme, config.tab_width, config.use_spaces,
        config.yate_trace, config.yate_trace_level,
    )
    if config.errors:
        log.warning("config errors: %s", "; ".join(config.errors))

    # Imported lazily so ``--help`` / ``--version`` work without a terminal.
    from yate.app import YateApp

    keymap = None
    if args.keymap is not None:
        keymap = "vsc" if args.keymap == "normal" else args.keymap

    # --diag builds the app through the exact same constructor path as a
    # normal run so the report reflects what would actually be loaded, but
    # never enters the TUI. load_startup_services() is headless-safe.
    if args.diag:
        from yate import diagnostics

        app = YateApp(
            target=target,
            keymap=keymap,
            theme_name=args.theme,
            config=config,
            readonly=args.readonly,
            ext_files=args.ext_files,
            ext_dirs=args.ext_dirs,
        )
        app.editor.load_startup_services()
        diagnostics.print_report(app.editor)
        return 0

    app = YateApp(
        target=target,
        keymap=keymap,
        theme_name=args.theme,
        config=config,
        readonly=args.readonly,
        ext_files=args.ext_files,
        ext_dirs=args.ext_dirs,
    )
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
