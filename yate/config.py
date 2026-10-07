"""Configuration data model: resolved options and the ``:set`` option table.

The dataclasses here are the single shape of yate's resolved configuration:
:class:`YateConfig` (scalar options and accumulated lists) plus the
dict-backed :class:`ScreenSaverConfig` / :class:`FilePreviewConfig` and the
declarative :class:`LanguageServerSpec`.  Loading, exec'ing and validating
``yaterc`` files lives in :mod:`yate.yaterc`.

This module also owns the ``:set`` option table (:class:`SetOption` /
:data:`SET_OPTION_SPECS`) so the ``:`` command layer
(:mod:`yate.commands`) and the prompt completion
(:mod:`yate.flows.prompt_completion`) derive from one definition instead
of two hand-maintained copies (audit A8).

Usage in a yaterc file -- see :mod:`yate.yaterc` for the load order and
the full option reference::

    keymap = "vim"          # "vsc" (default) or "vim"
    theme = "mocha"         # mocha | macchiato | frappe | latte | <custom>
    terminal_height = 12
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from yate.logs import DEFAULT_LEVEL, LEVEL_NAMES

#: Recognized option variables in a yaterc file (public: the loader in
#: :mod:`yate.yaterc` consumes it).
KNOWN_OPTIONS: tuple[str, ...] = (
    "keymap", "theme", "tab_width", "use_spaces",
    "shell", "terminal_height", "show_hidden",
    "yate_trace", "yate_trace_level", "key_protocol",
)

VALID_KEYMAPS: tuple[str, ...] = ("vsc", "vim")

#: Accepted ``key_protocol`` values: ``auto`` (Windows -> chord driver)
#: and ``legacy`` (stock driver).
VALID_KEY_PROTOCOLS: tuple[str, ...] = ("auto", "legacy")

#: Accepted ``yate_trace_level`` values -- :mod:`logging`'s built-in levels
#: (single source of truth: :data:`yate.logs.LEVEL_NAMES`).
VALID_TRACE_LEVELS: tuple[str, ...] = LEVEL_NAMES


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


@dataclass(frozen=True)
class FilePreviewConfig:
    """Resolved ``file_preview`` dict option (ctrl+p preview pane)."""

    enable: bool = True
    position: str = "right"     # "right" | "left"
    size: int = 60              # percent of palette width, 10-80
    max_lines: int = 2000       # read/tokenize line cap
    max_size: int = 1048576     # byte cap before refusing to read


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
    #: Ctrl+p preview pane settings (the ``file_preview`` dict option).
    file_preview: FilePreviewConfig = field(default_factory=FilePreviewConfig)
    sources: list[Path] = field(default_factory=list[Path])
    errors: list[str] = field(default_factory=list[str])


# ---- the ``:set`` option table (audit A8) ---------------------------------

#: Values accepted by boolean ``:set`` options (``show_hidden``, ``readonly``).
_TRUTHY: frozenset[str] = frozenset({"true", "on", "1", "yes"})
_FALSY: frozenset[str] = frozenset({"false", "off", "0", "no"})


def parse_bool(value: str) -> bool | None:
    """Parse a boolean ``:set`` value; ``None`` when it is not recognised."""
    lowered = value.lower()
    if lowered in _TRUTHY:
        return True
    if lowered in _FALSY:
        return False
    return None


def _parse_int_in_range(value: str, low: int, high: int) -> int | None:
    """Parse *value* as an ``int`` in ``low..high``; ``None`` otherwise."""
    try:
        parsed = int(value)
    except ValueError:
        return None
    return parsed if low <= parsed <= high else None


#: ``parse(raw)`` -- turn the raw option string into the value the apply
#: mapping receives, or ``None`` when the spelling is invalid.
type OptionParser = Callable[[str], object | None]


@dataclass(frozen=True)
class SetOption:
    """One ``:set`` option: aliases, value parser and help text (A8).

    The canonical *name* and every *alias* are accepted spellings of the
    option on the command line.  *parse* turns the raw string into the
    value handed to the apply mapping (``None`` = invalid, the command
    layer then shows *invalid_message*).  *summary* is the fragment shown
    by the ``:set`` usage line.
    """

    name: str                      # canonical name, e.g. "terminal_height"
    aliases: tuple[str, ...]       # e.g. ("ft", "language", "lang")
    parse: OptionParser             # None = invalid value
    invalid_message: str           # warn text reused by commands._set
    summary: str                   # one-line hint for the usage message


def _parse_filetype(value: str) -> object | None:
    """Accept any filetype spelling; ``editor.set_filetype`` validates it."""
    return value


def _parse_keymap(value: str) -> object | None:
    """Accept only the registered keymap names."""
    return value if value in VALID_KEYMAPS else None


def _parse_theme(value: str) -> object | None:
    """Accept any non-empty theme name; unknown names fail at apply time."""
    return value if value.strip() else None


def _parse_shell(value: str) -> object | None:
    """Accept any shell string (empty resets to the platform default)."""
    return value


def _parse_terminal_height(value: str) -> object | None:
    """Accept an integer in ``3..40`` (the config loader's same range)."""
    return _parse_int_in_range(value, 3, 40)


def _parse_bool_option(value: str) -> object | None:
    """Accept the boolean spellings via :func:`parse_bool`."""
    return parse_bool(value)


#: The single source of ``:set`` truth: canonical names, aliases, value
#: parsers and help text.  ``commands._set`` dispatches through this table
#: and ``flows/prompt_completion`` derives its candidate list from it, so a
#: new option is added exactly once, here.  Order fixes the usage message.
SET_OPTION_SPECS: tuple[SetOption, ...] = (
    SetOption(
        name="keymap",
        aliases=(),
        parse=_parse_keymap,
        invalid_message="keymap must be vsc or vim",
        summary="keymap=vsc|vim",
    ),
    SetOption(
        name="theme",
        aliases=(),
        parse=_parse_theme,
        invalid_message="theme must be a non-empty name",
        summary="theme=mocha",
    ),
    SetOption(
        name="shell",
        aliases=(),
        parse=_parse_shell,
        invalid_message="shell must be a command string",
        summary="shell=powershell",
    ),
    SetOption(
        name="terminal_height",
        aliases=(),
        parse=_parse_terminal_height,
        invalid_message="terminal_height must be an integer between 3 and 40",
        summary="terminal_height=12",
    ),
    SetOption(
        name="filetype",
        aliases=("ft", "language", "lang"),
        parse=_parse_filetype,
        invalid_message="filetype must be a filetype name",
        summary="filetype=py (auto = detect)",
    ),
    SetOption(
        name="show_hidden",
        aliases=(),
        parse=_parse_bool_option,
        invalid_message="show_hidden must be on|off (true/false/1/0/yes/no accepted)",
        summary="show_hidden=on|off",
    ),
    SetOption(
        name="readonly",
        aliases=(),
        parse=_parse_bool_option,
        invalid_message="readonly must be true|false (on/off/1/0/yes/no accepted)",
        summary="readonly=true|false",
    ),
)


def set_option_names() -> tuple[str, ...]:
    """Every accepted ``:set`` spelling (canonical names plus aliases)."""
    return tuple(
        spelling for spec in SET_OPTION_SPECS for spelling in (spec.name, *spec.aliases)
    )
