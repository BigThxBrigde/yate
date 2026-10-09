"""yaterc loading: Python-based configuration files (vimrc / init.vim style).

A ``yaterc`` file is ordinary Python.  Options are plain module-level
variables; theme callbacks injected by the caller (``register_theme``,
theme-directory loading) allow custom themes::

    keymap = "vim"          # "vsc" (default) or "vim"
    theme = "mocha"         # mocha | macchiato | frappe | latte | <custom>
    tab_width = 4
    use_spaces = True
    extensions = ["~/.yate/ext", "./tools/ext.py"]   # extra extension paths
    theme_dirs = ["~/.yate/themes"]                  # custom theme directories
    language_servers = [                             # declarative LSP servers
        {
            "name": "rust-analyzer",
            "command": "rust-analyzer",
            "filetypes": ["rs"],
            "language_ids": {"rs": "rust"},
            "root_markers": ["Cargo.toml", ".git"],
        },
    ]
    screen_saver = {                                 # idle screensaver mode
        "enable": True,        # master switch (False also disables Alt+Shift+S)
        "interval": 120,       # idle seconds before it starts (0 = manual only)
        "switch": 0,           # min seconds between spawns (0 = 1/8-1/3 rule)
        "dist_lower_bound": 0.125,  # optional journey window (float or "p/q");
        "dist_upper_bound": "1/3",  # when BOTH are set, `switch` is ignored
        "characters": [],      # name whitelist; [] = the whole roster
    }
    file_preview = {                                 # ctrl+p preview pane
        "enable": True,        # master switch for the preview pane
        "position": "right",   # pane side of the results list ("left" too)
        "size": 60,            # pane width as percent of palette width (10-80)
        "max_lines": 2000,     # lines read/tokenized for one preview
        "max_size": 1048576,   # byte cap; bigger files are not previewed
    }

Load order (later wins, like ``~/.vimrc`` followed by ``./.vimrc``):

1. the user rc:        ``~/.yate/yaterc``
2. the project rc:     a ``yaterc`` file in the current directory or any
                       ancestor directory (checked when yate starts)
3. an explicit file:   ``yate -u <file>`` replaces steps 1 and 2;
                       ``yate -u NONE`` skips rc loading entirely

Files are exec'd in order in one shared namespace, so a project rc sees the
variables set by the user rc and can override them.  Neither a missing rc
nor an invalid option ever crashes the editor: problems are collected on
:class:`yate.config.YateConfig` and surfaced in the message line at startup.

This module stays L0: it keeps the rc discovery and exec loop and imports
only :mod:`yate.config` (dataclasses and validation constants),
:mod:`yate.logs`, and the option validators in :mod:`yaterc_options`
(big-module-split wave f).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from yate.config import YateConfig
from yate.logs import tracing
from yate.yaterc_options import (
    _extract_disabled_extensions,
    _extract_extensions,
    _extract_options,
    _extract_theme_dirs,
)

#: File name yate looks for in the project tree.
RC_FILENAME: str = "yaterc"

log = tracing.get_logger(__name__)


def user_config_path() -> Path:
    """The user-level rc location (``~/.yate/yaterc``)."""
    return Path.home() / ".yate" / RC_FILENAME


def find_project_config(start: Path | None = None) -> Path | None:
    """Nearest ``yaterc`` walking up from *start* (default: cwd); else ``None``.

    A file *start* resolves against its parent directory, so passing the
    file being edited works regardless of whether it exists yet.
    """
    here = (start if start is not None else Path.cwd()).resolve()
    if not here.is_dir():
        here = here.parent
    for directory in (here, *here.parents):
        candidate = directory / RC_FILENAME
        if candidate.is_file():
            return candidate
    return None


def default_rc_paths(target: Path | None = None) -> list[Path]:
    """Ordered rc files to load: user rc then project rc (existing only).

    Both entries are resolved so the same file reached via different spellings
    (Windows 8.3 short names, symlinks) is only loaded once.
    """
    paths: list[Path] = []
    user = user_config_path()
    if user.is_file():
        paths.append(user.resolve())
    project = find_project_config(target)
    if project is not None and project not in paths:
        paths.append(project)
    return paths


#: Callback injected as ``register_theme`` into every yaterc namespace.  The
#: theme object travels opaquely: L0 config must not know the Theme type
#: (that import is exactly the N30 layering debt), hence ``Any`` here.
type ThemeRegistrar = Callable[[Any], None]

#: Callback loading one batch of rc-declared theme files/directories; same
#: contract as :func:`yate.editor_view.theme.load_theme_paths` (problems are
#: appended to *errors*, never raised).
type ThemeDirLoader = Callable[[list[Path], list[str]], None]


def load_config(
    paths: list[Path],
    *,
    register_theme: ThemeRegistrar | None = None,
    load_theme_paths: ThemeDirLoader | None = None,
) -> YateConfig:
    """Exec the given rc files in order and return the resolved config.

    Files share one namespace (later files see and override earlier
    variables).  Read/compile/exec failures are recorded per file and do
    not abort the remaining files.  Note that a file failing mid-way keeps
    the side effects of its earlier statements: a scalar assignment
    executed before the failing line stays in the shared namespace and
    therefore still applies -- only that file's remaining lines are
    skipped.

    Theme support is injected, not imported (N30: an L0 leaf must not
    import the L2 UI package).  *register_theme* is exposed to rc files
    as ``register_theme`` and *load_theme_paths* loads the ``theme_dirs``
    entries after all files ran, before the caller applies ``theme =
    "<custom>"``.  Both callbacks are the same-named functions of
    :mod:`yate.editor_view.theme`; the production caller is
    :mod:`yate.cli`.  With the defaults (``None``) the namespace simply
    lacks ``register_theme`` -- an rc calling it records a NameError on
    the config and the remaining files still run -- and ``theme_dirs``
    is extracted but never loaded, so headless consumers get a UI-free
    loader.
    """
    config = YateConfig()
    # The rc API surface injected into every yaterc namespace.
    namespace: dict[str, Any] = {
        "__name__": "__yaterc__",
    }
    if register_theme is not None:
        namespace["register_theme"] = register_theme
    for path in paths:
        try:
            source = path.read_text(encoding="utf-8")
        except OSError as exc:
            config.errors.append(f"{path}: cannot read: {exc}")
            continue
        try:
            # yaterc is user-authored Python executed by design (like vimrc).
            code = compile(source, str(path), "exec")
            exec(code, namespace)  # noqa: S102 - intentional rc execution
        except Exception as exc:  # noqa: BLE001 - rc errors must not crash yate
            config.errors.append(f"{path}: {type(exc).__name__}: {exc}")
            continue
        config.sources.append(path)
        # Path-list options are extracted per file so relative entries resolve
        # against the directory of the rc file that declared them.
        _extract_extensions(namespace, config, path.parent)
        _extract_theme_dirs(namespace, config, path.parent)
        _extract_disabled_extensions(namespace, config)
    # Register themes from rc-declared directories before the app applies
    # ``theme = "<custom>"`` (the theme registry is process-global).
    if load_theme_paths is not None:
        load_theme_paths(config.theme_dirs, config.errors)
    _extract_options(namespace, config)
    log.debug(
        "yaterc loaded: sources=%s errors=%d",
        [str(p) for p in config.sources], len(config.errors),
    )
    return config
