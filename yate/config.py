"""yaterc: Python-based configuration files (vimrc / init.vim style).

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
from typing import Any, cast

from collections.abc import Callable, Sequence

from yate.logs import DEFAULT_LEVEL, LEVEL_NAMES, tracing

#: File name yate looks for in the project tree.
RC_FILENAME = "yaterc"

log = tracing.get_logger(__name__)

#: Recognized option variables in a yaterc file.
_KNOWN_OPTIONS = (
    "keymap", "theme", "tab_width", "use_spaces",
    "shell", "terminal_height", "show_hidden",
    "yate_trace", "yate_trace_level", "key_protocol",
)

_VALID_KEYMAPS = ("vsc", "vim")

#: Accepted ``key_protocol`` values: ``auto`` (Windows -> chord driver)
#: and ``legacy`` (stock driver).
_VALID_KEY_PROTOCOLS = ("auto", "legacy")

#: Accepted ``yate_trace_level`` values -- :mod:`logging`'s built-in levels
#: (single source of truth: :data:`yate.logs.LEVEL_NAMES`).
_VALID_TRACE_LEVELS = LEVEL_NAMES


@dataclass
class LanguageServerSpec:
    """One validated ``language_servers`` entry declared in a yaterc file.

    The fields mirror the keyword arguments of
    :meth:`yate.services.extensions.LspExtensionBridge.register_server`;
    ``root_markers`` of ``None`` means "use the manager's defaults".
    """

    name: str
    command: str
    filetypes: list[str]
    args: list[str] = field(default_factory=list[str])
    language_ids: dict[str, str] = field(default_factory=dict[str, str])
    initialization_options: Any = None
    settings: Any = None
    env: dict[str, str] | None = None
    root_markers: list[str] | None = None


@dataclass(frozen=True)
class ScreenSaverConfig:
    """Resolved ``screen_saver`` dict option (idle screensaver settings).

    ``interval`` of ``0`` disables the automatic idle trigger (the manual
    :kbd:`Alt+Shift+S` toggle still works while ``enable`` is true).
    ``switch`` is the minimum number of seconds between two successive
    spawns; ``0`` lets a successor spawn as soon as the newest walker is
    1/8-1/3 through its journey.  When both ``dist_lower_bound`` and
    ``dist_upper_bound`` are set (fractions of the walk, via
    :attr:`dist_bounds`) they define that random spawn window explicitly
    and ``switch`` is ignored.  ``characters`` is a name whitelist --
    empty means the whole roster; name membership is validated where the
    roster lives (:func:`yate.editor_sprites.characters.character_names`),
    keeping this module free of sprite-pack knowledge.
    """

    enable: bool = True
    interval: int = 120
    switch: int = 0
    characters: tuple[str, ...] = ()
    #: Lower edge of the spawn window as a fraction of the journey
    #: (``None`` = unset; both bounds must be set to take effect).
    dist_lower_bound: float | None = None
    #: Upper edge of the spawn window as a fraction of the journey.
    dist_upper_bound: float | None = None

    @property
    def dist_bounds(self) -> tuple[float, float] | None:
        """The ``(lower, upper)`` spawn window when both edges are set.

        Any other combination (only one edge, or a rejected pair cleared
        to ``None`` by the loader) yields ``None`` and the screen falls
        back to its built-in 1/8-1/3 window plus the ``switch`` floor.
        """
        if self.dist_lower_bound is None or self.dist_upper_bound is None:
            return None
        return (self.dist_lower_bound, self.dist_upper_bound)


@dataclass
class YateConfig:
    """Resolved editor options plus observability metadata.

    ``sources`` lists the rc files that were actually exec'd (earlier =
    lower priority), answering "which config is in effect?".  ``errors``
    holds human-readable load/validation problems.
    """

    keymap: str = "vsc"
    theme: str = "mocha"
    #: Windows input channel selection (``key_protocol = "legacy"`` in
    #: yaterc restores the stock driver). ``auto`` uses the chord driver on
    #: Windows so ctrl+digit / ctrl+` / ctrl+shift+letter arrive complete.
    key_protocol: str = "auto"
    tab_width: int = 4
    use_spaces: bool = True
    #: Shell command for the integrated terminal (empty = platform default:
    #: pwsh/PowerShell/cmd on Windows, $SHELL/bash on Unix).
    shell: str = ""
    #: Integrated terminal panel height in rows.
    terminal_height: int = 12
    #: Show dotfiles in the explorer by default (``show_hidden = True``
    #: in yaterc).  Off by default — dotfiles are hidden until toggled.
    show_hidden: bool = False
    #: Runtime trace log switch (``yate_trace = True`` in yaterc). Off by
    #: default: nothing is written until it is turned on. ``YATE_TRACE``
    #: overrides it per session.
    yate_trace: bool = False
    #: Trace verbosity (``yate_trace_level = "DEBUG"`` in yaterc), one of
    #: :data:`yate.logs.LEVEL_NAMES`. ``YATE_TRACE_LEVEL`` overrides it.
    yate_trace_level: str = DEFAULT_LEVEL
    #: Extra extension paths (directories or ``.py`` files) declared by rc
    #: files, accumulated in load order (user rc first, project rc after).
    extension_paths: list[Path] = field(default_factory=list[Path])
    #: Stems of bundled (shipped) extensions to skip at startup, e.g.
    #: ``disabled_extensions = ["python_lsp"]``; accumulated across rc files.
    disabled_extensions: list[str] = field(default_factory=list[str])
    #: Directories holding ``*.py`` custom theme files, accumulated in load
    #: order and scanned at startup (see editor_view.theme).
    theme_dirs: list[Path] = field(default_factory=list[Path])
    #: Declarative LSP servers (the ``language_servers`` option); the app
    #: registers them after extensions so a same-named rc entry wins.
    language_servers: list[LanguageServerSpec] = field(
        default_factory=list[LanguageServerSpec]
    )
    #: Idle screensaver settings (the ``screen_saver`` dict option).
    screen_saver: ScreenSaverConfig = field(default_factory=ScreenSaverConfig)
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
    not abort the remaining files.

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


def _extract_disabled_extensions(
    namespace: dict[str, Any], config: YateConfig
) -> None:
    """Pull the ``disabled_extensions`` option out of one rc file.

    A string or a list/tuple of bundled-extension stems (``"python_lsp"``);
    entries accumulate and de-duplicate across rc files. The option only
    affects extensions shipped inside yate -- user/project scripts keep
    loading regardless.
    """
    raw = namespace.get("disabled_extensions")
    if raw is None:
        return
    entries: list[Any]
    if isinstance(raw, str):
        entries = [raw]
    elif isinstance(raw, (list, tuple)):
        entries = list(cast(Sequence[Any], raw))
    else:
        config.errors.append(
            f"disabled_extensions must be a string or a list of strings, got {raw!r}"
        )
        return
    for entry in entries:
        if not isinstance(entry, str) or not entry.strip():
            config.errors.append(
                f"disabled_extensions entries must be non-empty strings, got {entry!r}"
            )
            continue
        name = entry.strip()
        if name not in config.disabled_extensions:
            config.disabled_extensions.append(name)


def _extract_theme_dirs(
    namespace: dict[str, Any], config: YateConfig, rc_dir: Path
) -> None:
    """Pull the ``theme_dirs`` option out of one rc file's namespace.

    Mirrors :func:`_extract_extensions`: a path string or a list/tuple of
    path strings; an entry may be a directory (every ``*.py`` inside is
    loaded as a theme file) or a single ``.py`` theme file.  ``~`` is
    expanded and relative paths resolve against *rc_dir*.  Entries
    accumulate across rc files and are de-duplicated.
    """
    raw = namespace.get("theme_dirs")
    if raw is None:
        return
    entries: list[Any]
    if isinstance(raw, str):
        entries = [raw]
    elif isinstance(raw, (list, tuple)):
        entries = list(cast(Sequence[Any], raw))
    else:
        config.errors.append(
            f"theme_dirs must be a path string or a list of strings, got {raw!r}"
        )
        return
    for entry in entries:
        if not isinstance(entry, str) or not entry.strip():
            config.errors.append(
                f"theme_dirs entries must be non-empty strings, got {entry!r}"
            )
            continue
        path = Path(entry.strip()).expanduser()
        if not path.is_absolute():
            path = rc_dir / path
        if not path.exists():
            config.errors.append(f"theme_dirs path does not exist: {entry}")
            continue
        resolved = path.resolve()
        if resolved not in config.theme_dirs:
            config.theme_dirs.append(resolved)


def _parse_journey_fraction(
    value: Any, key: str, config: YateConfig
) -> float | None:
    """Parse one ``screen_saver`` journey bound and report bad values.

    Accepts a float (integers included, bools rejected as usual) or a
    ``"p/q"`` fraction string such as ``"1/8"``.  Returns the parsed
    fraction when it lies in ``(0, 1)``; otherwise appends an error to
    *config* and returns ``None``.
    """
    parsed: float | None = None
    if isinstance(value, bool):
        pass  # bool is a subclass of int -- reject it explicitly
    elif isinstance(value, (int, float)):
        parsed = float(value)
    elif isinstance(value, str):
        numerator, slash, denominator = value.partition("/")
        if (
            slash
            and numerator.strip().lstrip("-").isdigit()
            and denominator.strip().lstrip("-").isdigit()
        ):
            bottom = int(denominator)
            if bottom != 0:
                parsed = int(numerator) / bottom
    if parsed is None or not 0.0 < parsed < 1.0:
        config.errors.append(
            f"screen_saver {key} must be a float in (0, 1) or a fraction "
            f'like "1/8", got {value!r}'
        )
        return None
    return parsed


def _extract_screen_saver(
    namespace: dict[str, Any], config: YateConfig
) -> None:
    """Pull the ``screen_saver`` dict option out of one rc file.

    Recognized keys: ``enable`` (bool), ``interval`` (integer 0-3600, the
    idle seconds before an automatic start; ``0`` disables it), ``switch``
    (integer 0-3600, the minimum seconds between two successive spawns;
    ``0`` follows the 1/8-1/3-of-journey rule alone), ``dist_lower_bound``
    / ``dist_upper_bound`` (float or ``"p/q"`` fraction in ``(0, 1)``,
    pinning the random spawn window as a fraction of the walk -- when
    both are set ``switch`` is ignored) and ``characters`` (a list of
    roster names; empty means all).  The two bounds must appear together
    with ``lower < upper`` or the pair is rejected whole.  Missing keys
    keep their defaults; an unknown key or a wrong-typed value is
    reported individually and that key keeps its default while the rest
    still apply.  A later valid declaration replaces the previous one
    whole (same semantics as ``language_servers``).
    """
    raw = namespace.get("screen_saver")
    if raw is None:
        return
    if not isinstance(raw, dict):
        config.errors.append(f"screen_saver must be a dict, got {raw!r}")
        return
    values = cast(dict[str, Any], raw)
    known = (
        "enable",
        "interval",
        "switch",
        "dist_lower_bound",
        "dist_upper_bound",
        "characters",
    )
    unknown = sorted(key for key in values if key not in known)
    if unknown:
        config.errors.append(f"screen_saver has unknown keys: {unknown}")

    enable: bool = True
    if "enable" in values:
        value = values["enable"]
        if isinstance(value, bool):
            enable = value
        else:
            config.errors.append(
                f"screen_saver enable must be True or False, got {value!r}"
            )

    interval: int = 120
    if "interval" in values:
        value = values["interval"]
        # bool is a subclass of int -- reject it explicitly for this option.
        if isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 3600:
            interval = value
        else:
            config.errors.append(
                f"screen_saver interval must be an integer between 0 and "
                f"3600, got {value!r}"
            )

    switch: int = 0
    if "switch" in values:
        value = values["switch"]
        if isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 3600:
            switch = value
        else:
            config.errors.append(
                f"screen_saver switch must be an integer between 0 and "
                f"3600, got {value!r}"
            )

    names: tuple[str, ...] = ()
    if "characters" in values:
        value = values["characters"]
        valid = isinstance(value, (list, tuple)) and all(
            isinstance(entry, str) for entry in cast(Sequence[Any], value)
        )
        if valid:
            names = tuple(dict.fromkeys(cast(Sequence[str], value)))
        else:
            config.errors.append(
                f"screen_saver characters must be a list of character "
                f"names, got {value!r}"
            )

    lower: float | None = None
    if "dist_lower_bound" in values:
        lower = _parse_journey_fraction(
            values["dist_lower_bound"], "dist_lower_bound", config
        )
    upper: float | None = None
    if "dist_upper_bound" in values:
        upper = _parse_journey_fraction(
            values["dist_upper_bound"], "dist_upper_bound", config
        )
    if (lower is None) != (upper is None):
        config.errors.append(
            "screen_saver dist_lower_bound and dist_upper_bound must be "
            "set together"
        )
        lower = upper = None
    elif lower is not None and upper is not None and lower >= upper:
        config.errors.append(
            "screen_saver dist_lower_bound must be less than "
            f"dist_upper_bound, got {lower!r} >= {upper!r}"
        )
        lower = upper = None

    config.screen_saver = ScreenSaverConfig(
        enable=enable,
        interval=interval,
        switch=switch,
        dist_lower_bound=lower,
        dist_upper_bound=upper,
        characters=names,
    )


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

    key_protocol = options.get("key_protocol")
    if key_protocol is not None:
        if isinstance(key_protocol, str) and key_protocol in _VALID_KEY_PROTOCOLS:
            config.key_protocol = key_protocol
        else:
            config.errors.append(
                f"key_protocol must be one of {_VALID_KEY_PROTOCOLS}, got {key_protocol!r}"
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

    shell = options.get("shell")
    if shell is not None:
        if isinstance(shell, str) and shell.strip():
            config.shell = shell.strip()
        else:
            config.errors.append(f"shell must be a non-empty string, got {shell!r}")

    terminal_height = options.get("terminal_height")
    if terminal_height is not None:
        if (
            isinstance(terminal_height, int)
            and not isinstance(terminal_height, bool)
            and 3 <= terminal_height <= 40
        ):
            config.terminal_height = terminal_height
        else:
            config.errors.append(
                f"terminal_height must be an integer between 3 and 40, "
                f"got {terminal_height!r}"
            )

    show_hidden = options.get("show_hidden")
    if show_hidden is not None:
        if isinstance(show_hidden, bool):
            config.show_hidden = show_hidden
        else:
            config.errors.append(
                f"show_hidden must be True or False, got {show_hidden!r}"
            )

    trace = options.get("yate_trace")
    if trace is not None:
        if isinstance(trace, bool):
            config.yate_trace = trace
        else:
            config.errors.append(
                f"yate_trace must be True or False, got {trace!r}"
            )

    trace_level = options.get("yate_trace_level")
    if trace_level is not None:
        if isinstance(trace_level, str) and trace_level.strip():
            level_name = trace_level.strip().upper()
            if level_name in _VALID_TRACE_LEVELS:
                config.yate_trace_level = level_name
            else:
                config.errors.append(
                    f"yate_trace_level must be one of {_VALID_TRACE_LEVELS}, "
                    f"got {trace_level!r}"
                )
        else:
            config.errors.append(
                f"yate_trace_level must be a non-empty string, "
                f"got {trace_level!r}"
            )

    _extract_language_servers(namespace, config)
    _extract_screen_saver(namespace, config)


def _extract_language_servers(namespace: dict[str, Any], config: YateConfig) -> None:
    """Pull the ``language_servers`` option out of the exec'd namespace.

    The value is a list of mappings (one per server). As with scalar options,
    a declaration in a later rc file replaces the whole list rather than
    merging. Malformed entries are skipped with an error; valid entries in
    the same list are still applied.
    """
    raw = namespace.get("language_servers")
    if raw is None:
        return
    if not isinstance(raw, (list, tuple)):
        config.errors.append(
            f"language_servers must be a list of mappings, got {raw!r}"
        )
        return
    specs: list[LanguageServerSpec] = []
    for index, entry_raw in enumerate(cast(Sequence[Any], raw)):
        where = f"language_servers[{index}]"
        if not isinstance(entry_raw, dict):
            config.errors.append(
                f"{where}: server entry must be a mapping, got {entry_raw!r}"
            )
            continue
        spec = _parse_language_server(
            cast(dict[str, Any], entry_raw), config.errors, where
        )
        if spec is not None:
            specs.append(spec)
    config.language_servers = specs


def _parse_language_server(
    entry: dict[str, Any], errors: list[str], where: str
) -> LanguageServerSpec | None:
    """Validate one ``language_servers`` mapping; append an error and return
    ``None`` when a required field is missing or mistyped."""
    name = entry.get("name")
    if not isinstance(name, str) or not name.strip():
        errors.append(f"{where}.name must be a non-empty string, got {name!r}")
        return None
    command = entry.get("command")
    if not isinstance(command, str) or not command.strip():
        errors.append(
            f"{where}.command must be a non-empty string, got {command!r}"
        )
        return None
    filetypes_raw = entry.get("filetypes")
    filetypes = _require_str_list(
        filetypes_raw, f"{where}.filetypes", errors, nonempty=True
    )
    if filetypes is None:
        return None
    # Accept leading dots (".rs") even though the canonical form is "rs";
    # guard against values that normalize to empty ("." / ".." / "...").
    filetypes = [ft.lstrip(".") for ft in filetypes]
    if any(not ft for ft in filetypes):
        errors.append(
            f"{where}.filetypes entries must name an extension, got {filetypes_raw!r}"
        )
        return None
    args = _require_str_list(entry.get("args", []), f"{where}.args", errors)
    if args is None:
        return None
    root_markers_raw = entry.get("root_markers")
    root_markers: list[str] | None = None
    if root_markers_raw is not None:
        root_markers = _require_str_list(
            root_markers_raw, f"{where}.root_markers", errors
        )
        if root_markers is None:
            return None
    language_ids = _require_str_map(
        entry.get("language_ids", {}), f"{where}.language_ids", errors
    )
    if language_ids is None:
        return None
    env_raw = entry.get("env")
    env: dict[str, str] | None = None
    if env_raw is not None:
        env = _require_str_map(env_raw, f"{where}.env", errors)
        if env is None:
            return None
    return LanguageServerSpec(
        name=name.strip(),
        command=command.strip(),
        filetypes=filetypes,
        args=args,
        language_ids=language_ids,
        initialization_options=entry.get("initialization_options"),
        settings=entry.get("settings"),
        env=env,
        root_markers=root_markers,
    )


def _require_str_list(
    value: Any,
    label: str,
    errors: list[str],
    *,
    nonempty: bool = False,
) -> list[str] | None:
    """Validate a ``list[str]`` (tuple accepted); ``None`` is only valid when
    the caller handles it before calling. Empty/whitespace items rejected."""
    if not isinstance(value, (list, tuple)):
        errors.append(f"{label} must be a list of strings, got {value!r}")
        return None
    result: list[str] = []
    for item in cast(Sequence[Any], value):
        if not isinstance(item, str) or not item.strip():
            errors.append(f"{label} entries must be non-empty strings, got {item!r}")
            return None
        result.append(item)
    if nonempty and not result:
        errors.append(f"{label} must contain at least one entry")
        return None
    return result


def _require_str_map(
    value: Any, label: str, errors: list[str]
) -> dict[str, str] | None:
    """Validate a ``dict[str, str]`` mapping."""
    if not isinstance(value, dict):
        errors.append(f"{label} must be a mapping of strings, got {value!r}")
        return None
    result: dict[str, str] = {}
    for key, item in cast(dict[Any, Any], value).items():
        if not isinstance(key, str) or not isinstance(item, str):
            errors.append(
                f"{label} keys and values must be strings, got {key!r}: {item!r}"
            )
            return None
        result[key] = item
    return result
