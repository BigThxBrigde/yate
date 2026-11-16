"""Configuration data model: resolved options and the ``:set`` option table.

The dataclasses here are the single shape of yate's resolved configuration:
:class:`YateConfig` (scalar options and accumulated lists) plus the
dict-backed :class:`ScreenSaverConfig` / :class:`FilePreviewConfig` and the
declarative :class:`LanguageServerSpec`.  Loading, exec'ing and validating
``yaterc`` files lives in :mod:`yate.yaterc`.

This module also owns the ``:set`` option table (:class:`SetOption` /
:data:`SET_OPTION_SPECS`) so the ``:`` command layer
(:mod:`yate.commands`) and the prompt completion
(:mod:`yate.cmdline_completions`) derive from one definition instead
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
from typing import Any, cast

from yate.logs import DEFAULT_LEVEL, LEVEL_NAMES

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
    initialization_options: Any = None  # noqa: Any - arbitrary LSP JSON
    settings: Any = None  # noqa: Any - arbitrary LSP JSON
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


@dataclass(frozen=True)
class LargeFileConfig:
    """Resolved ``large_file`` dict option (chunked loading of huge files).

    ``threshold`` is the file size in bytes above which ``session.open``
    loads the document as a locked, progressively filled chunked buffer
    instead of reading it whole.      ``0`` disables chunked loading (every
    file is read whole); otherwise the value must lie in
    ``[1048576, 1073741824]`` (1 MiB files are never chunked by accident
    and nothing above 1 GiB is loaded whole on purpose).
    """

    threshold: int = 8_388_608  # 8 MiB; 0 = disabled


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
    #: Master switch for all mouse interaction (``support_mouse = False``
    #: in yaterc).  ``False`` makes the app drop every mouse event before
    #: it reaches any widget (gate lives in ``YateApp.on_event``).  On by
    #: default: mouse support is additive, the switch is an explicit
    #: opt-out (issue IKJRFK).
    support_mouse: bool = True
    #: Master switch for the which-key panel (``which_key = False`` in
    #: yaterc).  ``False`` suppresses every panel push (the candidate grid,
    #: the ``ctrl+w`` chord grid and the pinned sheet); the F9 toggle
    #: becomes a no-op.  On by default -- the panel is part of the standard
    #: UX, the switch is an explicit opt-out for users who prefer the bare
    #: vsc layout.  Re-enabling mid-session restores the panel at whatever
    #: pinned state the flows module holds.
    which_key: bool = True
    #: Gate for automatic which-key popups only (``which_key_auto = False``
    #: in yaterc).  ``False`` stops the pending-prefix and ``ctrl+w`` chord
    #: grids from auto-triggering; the ``<f9>`` manual toggle keeps working
    #: and the pinned sheet stays visible.  The ``which_key`` master switch
    #: takes priority: when it is off nothing shows regardless of this
    #: option.  On by default -- keeps the existing behavior.
    which_key_auto: bool = True
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
    #: order and scanned at startup (see editor_components.theme).
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
    #: Chunked-loading settings for very large files (the ``large_file``
    #: dict option).
    large_file: LargeFileConfig = field(default_factory=LargeFileConfig)
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
#: mapping receives, or ``None`` when the value is invalid.
type OptionParser = Callable[[str], object | None]

#: Legal-value domain of one option: enum spellings, an inclusive integer
#: range, or ``None`` for a free string.
type Domain = tuple[str, ...] | tuple[int, int] | None


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


@dataclass(frozen=True)
class OptionSpec:
    """One option definition shared by yaterc loading and the ``:set`` command.

    ``name`` is the canonical spelling and the yaterc variable name.
    ``rc_visible`` marks options yaterc recognizes; ``settable`` marks options
    exposed on ``:set``.  ``domain`` is the one place where legal values live.
    ``kind`` selects the native/parse strategies; ``bool`` uses the shared
    :func:`parse_bool` spellings.  ``invalid_message`` is the ``:set`` warning,
    ``invalid_message_fmt`` the yaterc template, and ``summary`` the usage
    fragment.
    """

    name: str
    aliases: tuple[str, ...]
    rc_visible: bool
    settable: bool
    kind: str  # "enum" | "int" | "bool" | "text" | "any_text"
    domain: Domain
    invalid_message: str
    invalid_message_fmt: str
    summary: str
    set_text_any: bool = False
    native_strip: bool = False
    invalid_message_fmt_empty: str = ""

    def validate_native(self, value: object) -> object | None:
        """Return *value* when legal for yaterc, else ``None``.

        Enum matching and integer bounds read :attr:`domain`; booleans accept
        only native ``bool`` values (the text spellings are a ``:set`` concern).
        ``yate_trace_level`` upper-cases before the membership check and keeps
        the canonical spelling for storage.  Text options keep their historical
        distinctions: a plain non-empty string is enough unless
        :attr:`native_strip` requires content after stripping.
        """
        if self.kind == "bool":
            return value if isinstance(value, bool) else None
        if self.kind == "int":
            bounds = cast(tuple[int, int], self.domain)
            if isinstance(value, int) and not isinstance(value, bool):
                return value if bounds[0] <= value <= bounds[1] else None
            return None
        if self.kind == "enum":
            if not isinstance(value, str):
                return None
            candidate = value.strip().upper() if self.name == "yate_trace_level" else value
            values = cast(tuple[str, ...], self.domain)
            return candidate if candidate in values else None
        if not isinstance(value, str):
            return None
        if self.kind == "any_text":
            return value
        if not value:
            return None
        if self.native_strip:
            return value.strip() if value.strip() else None
        return value

    def native_error(self, raw: object) -> str:
        """Format the yaterc error line for a rejected native value."""
        if self.invalid_message_fmt_empty and (
            not isinstance(raw, str) or not raw.strip()
        ):
            return self.invalid_message_fmt_empty.format(value=raw)
        return self.invalid_message_fmt.format(value=raw)

    def parse_set_text(self, text: str) -> object | None:
        """Parse a ``:set`` command-line string; ``None`` when invalid."""
        if self.set_text_any:
            return text
        if self.kind == "bool":
            return parse_bool(text)
        if self.kind == "int":
            bounds = cast(tuple[int, int], self.domain)
            return _parse_int_in_range(text, bounds[0], bounds[1])
        if self.kind == "enum":
            return text if text in cast(tuple[str, ...], self.domain) else None
        return text if text.strip() else None


#: The single source of option truth: yaterc loading and ``:set`` both read
#: their names, legal values and messages from these rows.  Order fixes the
#: usage message and the rc-visible option list.
OPTION_SPECS: tuple[OptionSpec, ...] = (
    OptionSpec(
        name="keymap",
        aliases=(),
        rc_visible=True,
        settable=True,
        kind="enum",
        domain=VALID_KEYMAPS,
        invalid_message="keymap must be vsc or vim",
        invalid_message_fmt="keymap must be one of ('vsc', 'vim'), got {value!r}",
        summary="keymap=vsc|vim",
    ),
    OptionSpec(
        name="theme",
        aliases=(),
        rc_visible=True,
        settable=True,
        kind="text",
        domain=None,
        invalid_message="theme must be a non-empty name",
        invalid_message_fmt="theme must be a non-empty string, got {value!r}",
        summary="theme=mocha",
    ),
    OptionSpec(
        name="tab_width",
        aliases=(),
        rc_visible=True,
        settable=False,
        kind="int",
        domain=(1, 16),
        invalid_message="tab_width must be an integer between 1 and 16",
        invalid_message_fmt="tab_width must be an integer between 1 and 16, "
        "got {value!r}",
        summary="",
    ),
    OptionSpec(
        name="use_spaces",
        aliases=(),
        rc_visible=True,
        settable=False,
        kind="bool",
        domain=None,
        invalid_message="use_spaces must be True or False",
        invalid_message_fmt="use_spaces must be True or False, got {value!r}",
        summary="",
    ),
    OptionSpec(
        name="shell",
        aliases=(),
        rc_visible=True,
        settable=True,
        kind="text",
        domain=None,
        invalid_message="shell must be a command string",
        invalid_message_fmt="shell must be a non-empty string, got {value!r}",
        summary="shell=powershell",
        set_text_any=True,
        native_strip=True,
    ),
    OptionSpec(
        name="terminal_height",
        aliases=(),
        rc_visible=True,
        settable=True,
        kind="int",
        domain=(3, 40),
        invalid_message="terminal_height must be an integer between 3 and 40",
        invalid_message_fmt="terminal_height must be an integer between 3 and "
        "40, got {value!r}",
        summary="terminal_height=12",
    ),
    OptionSpec(
        name="show_hidden",
        aliases=(),
        rc_visible=True,
        settable=True,
        kind="bool",
        domain=None,
        invalid_message="show_hidden must be on|off (true/false/1/0/yes/no accepted)",
        invalid_message_fmt="show_hidden must be True or False, got {value!r}",
        summary="show_hidden=on|off",
    ),
    OptionSpec(
        name="support_mouse",
        aliases=(),
        rc_visible=True,
        settable=True,
        kind="bool",
        domain=None,
        invalid_message="support_mouse must be on|off (true/false/1/0/yes/no accepted)",
        invalid_message_fmt="support_mouse must be True or False, got {value!r}",
        summary="support_mouse=on|off",
    ),
    OptionSpec(
        name="which_key",
        aliases=(),
        rc_visible=True,
        settable=True,
        kind="bool",
        domain=None,
        invalid_message="which_key must be on|off (true/false/1/0/yes/no accepted)",
        invalid_message_fmt="which_key must be True or False, got {value!r}",
        summary="which_key=on|off",
    ),
    OptionSpec(
        name="which_key_auto",
        aliases=(),
        rc_visible=True,
        settable=True,
        kind="bool",
        domain=None,
        invalid_message="which_key_auto must be on|off (true/false/1/0/yes/no accepted)",
        invalid_message_fmt="which_key_auto must be True or False, got {value!r}",
        summary="which_key_auto=on|off",
    ),
    OptionSpec(
        name="key_protocol",
        aliases=(),
        rc_visible=True,
        settable=False,
        kind="enum",
        domain=VALID_KEY_PROTOCOLS,
        invalid_message="key_protocol must be one of ('auto', 'legacy')",
        invalid_message_fmt="key_protocol must be one of ('auto', 'legacy'), "
        "got {value!r}",
        summary="",
    ),
    OptionSpec(
        name="yate_trace",
        aliases=(),
        rc_visible=True,
        settable=False,
        kind="bool",
        domain=None,
        invalid_message="yate_trace must be True or False",
        invalid_message_fmt="yate_trace must be True or False, got {value!r}",
        summary="",
    ),
    OptionSpec(
        name="yate_trace_level",
        aliases=(),
        rc_visible=True,
        settable=False,
        kind="enum",
        domain=VALID_TRACE_LEVELS,
        invalid_message="yate_trace_level must be a valid level name",
        invalid_message_fmt=f"yate_trace_level must be one of {VALID_TRACE_LEVELS}, "
        "got {value!r}",
        invalid_message_fmt_empty="yate_trace_level must be a non-empty string, "
        "got {value!r}",
        summary="",
    ),
    OptionSpec(
        name="filetype",
        aliases=("ft", "language", "lang"),
        rc_visible=False,
        settable=True,
        kind="any_text",
        domain=None,
        invalid_message="filetype must be a filetype name",
        invalid_message_fmt="",
        summary="filetype=py (auto = detect)",
    ),
    OptionSpec(
        name="readonly",
        aliases=(),
        rc_visible=False,
        settable=True,
        kind="bool",
        domain=None,
        invalid_message="readonly must be true|false (on/off/1/0/yes/no accepted)",
        invalid_message_fmt="",
        summary="readonly=true|false",
    ),
)

#: Recognized option variables in a yaterc file (public: the loader in
#: :mod:`yate.yaterc` consumes it).  ``large_file`` is a dict option handled
#: by a dedicated extractor; only its name is listed here.
KNOWN_OPTIONS: tuple[str, ...] = tuple(
    spec.name for spec in OPTION_SPECS if spec.rc_visible
) + ("large_file",)

#: The ``:set`` view of :data:`OPTION_SPECS`: commands._set dispatches through
#: it and the arg completer derives its candidates from it.  Order fixes the
#: usage message and matches the pre-unification table exactly.
SET_OPTION_SPECS: tuple[SetOption, ...] = tuple(
    SetOption(
        name=spec.name,
        aliases=spec.aliases,
        parse=spec.parse_set_text,
        invalid_message=spec.invalid_message,
        summary=spec.summary,
    )
    for spec in OPTION_SPECS
    if spec.settable
)


def set_option_names() -> tuple[str, ...]:
    """Every accepted ``:set`` spelling (canonical names plus aliases)."""
    return tuple(
        spelling for spec in SET_OPTION_SPECS for spelling in (spec.name, *spec.aliases)
    )


def set_option_value_candidates(name: str) -> tuple[str, ...]:
    """Static value candidates for a ``:set`` option, empty when dynamic."""
    spec = next((s for s in OPTION_SPECS if s.name == name), None)
    if spec is None or spec.kind != "enum" or not isinstance(spec.domain, tuple):
        return ()
    return cast(tuple[str, ...], spec.domain)
