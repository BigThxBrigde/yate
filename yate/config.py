"""yaterc: Python-based configuration files (vimrc / init.vim style).

A ``yaterc`` file is ordinary Python.  Options are plain module-level
variables; one injected helper (``register_theme``) allows custom themes::

    keymap = "vim"          # "vsc" (default) or "vim"
    theme = "mocha"         # mocha | macchiato | frappe | latte | <custom>
    tab_width = 4
    use_spaces = True
    extensions = ["~/.yate/ext", "./tools/ext.py"]   # extra extension paths

Load order (later wins, like ``~/.vimrc`` followed by ``./.vimrc``):

1. the user rc:        ``~/.yate/yaterc``
2. the project rc:     a ``yaterc`` file in the current directory or any
                       ancestor directory (checked when yate starts)
3. an explicit file:   ``yate -u <file>`` replaces steps 1 and 2;
                       ``yate -u NONE`` skips rc loading entirely

Files are exec'd in order in one shared namespace, so a project rc sees the
variables set by the user rc and can override them.  Neither a missing rc
nor an invalid option ever crashes the editor: problems are collected on
:class:`YateConfig` and surfaced in the message line at startup.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence, cast

from yate.editor_view import theme as themes

#: File name yate looks for in the project tree.
RC_FILENAME = "yaterc"

#: Recognized option variables in a yaterc file.
_KNOWN_OPTIONS = ("keymap", "theme", "tab_width", "use_spaces")

_VALID_KEYMAPS = ("vsc", "vim")


@dataclass
class YateConfig:
    """Resolved editor options plus observability metadata.

    ``sources`` lists the rc files that were actually exec'd (earlier =
    lower priority), answering "which config is in effect?".  ``errors``
    holds human-readable load/validation problems.
    """

    keymap: str = "vsc"
    theme: str = "mocha"
    tab_width: int = 4
    use_spaces: bool = True
    #: Extra extension paths (directories or ``.py`` files) declared by rc
    #: files, accumulated in load order (user rc first, project rc after).
    extension_paths: list[Path] = field(default_factory=list[Path])
    sources: list[Path] = field(default_factory=list[Path])
    errors: list[str] = field(default_factory=list[str])


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
    """Ordered rc files to load: user rc then project rc (existing only)."""
    paths: list[Path] = []
    user = user_config_path()
    if user.is_file():
        paths.append(user)
    project = find_project_config(target)
    if project is not None and project not in paths:
        paths.append(project)
    return paths


def load_config(paths: list[Path]) -> YateConfig:
    """Exec the given rc files in order and return the resolved config.

    Files share one namespace (later files see and override earlier
    variables).  Read/compile/exec failures are recorded per file and do
    not abort the remaining files.
    """
    config = YateConfig()
    # The rc API surface injected into every yaterc namespace.
    namespace: dict[str, Any] = {
        "__name__": "__yaterc__",
        "register_theme": themes.register_theme,
    }
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
        # Extension paths are extracted per file so relative entries resolve
        # against the directory of the rc file that declared them.
        _extract_extensions(namespace, config, path.parent)
    _extract_options(namespace, config)
    return config


def _extract_extensions(
    namespace: dict[str, Any], config: YateConfig, rc_dir: Path
) -> None:
    """Pull the ``extensions`` option out of one rc file's namespace.

    The value is a path string or a list/tuple of path strings; each entry
    may point at a directory (all ``*.py`` inside are loaded) or a single
    ``.py`` file.  ``~`` is expanded and relative paths resolve against
    *rc_dir*.  Entries accumulate across rc files and are de-duplicated.
    """
    raw = namespace.get("extensions")
    if raw is None:
        return
    entries: list[Any]
    if isinstance(raw, str):
        entries = [raw]
    elif isinstance(raw, (list, tuple)):
        entries = list(cast(Sequence[Any], raw))
    else:
        config.errors.append(
            f"extensions must be a path string or a list of strings, got {raw!r}"
        )
        return
    for entry in entries:
        if not isinstance(entry, str) or not entry.strip():
            config.errors.append(
                f"extensions entries must be non-empty strings, got {entry!r}"
            )
            continue
        path = Path(entry.strip()).expanduser()
        if not path.is_absolute():
            path = rc_dir / path
        if not path.exists():
            config.errors.append(f"extensions path does not exist: {entry}")
            continue
        resolved = path.resolve()
        if resolved not in config.extension_paths:
            config.extension_paths.append(resolved)


def _extract_options(namespace: dict[str, Any], config: YateConfig) -> None:
    """Pull recognized option variables out of the exec'd namespace."""
    options = {name: namespace[name] for name in _KNOWN_OPTIONS if name in namespace}

    keymap = options.get("keymap")
    if keymap is not None:
        if isinstance(keymap, str) and keymap in _VALID_KEYMAPS:
            config.keymap = keymap
        else:
            config.errors.append(
                f"keymap must be one of {_VALID_KEYMAPS}, got {keymap!r}"
            )

    theme_name = options.get("theme")
    if theme_name is not None:
        if isinstance(theme_name, str) and theme_name:
            config.theme = theme_name
        else:
            config.errors.append(f"theme must be a non-empty string, got {theme_name!r}")

    tab_width = options.get("tab_width")
    if tab_width is not None:
        # bool is a subclass of int -- reject it explicitly for this option.
        if isinstance(tab_width, int) and not isinstance(tab_width, bool) and 1 <= tab_width <= 16:
            config.tab_width = tab_width
        else:
            config.errors.append(
                f"tab_width must be an integer between 1 and 16, got {tab_width!r}"
            )

    use_spaces = options.get("use_spaces")
    if use_spaces is not None:
        if isinstance(use_spaces, bool):
            config.use_spaces = use_spaces
        else:
            config.errors.append(f"use_spaces must be True or False, got {use_spaces!r}")
