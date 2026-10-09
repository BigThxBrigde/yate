"""yaterc option extraction and validation (big-module-split wave f).

Pure validators pulling recognized option variables out of an exec'd
yaterc namespace and folding them into a
:class:`~yate.config.YateConfig`: path-list options (``extensions`` /
``theme_dirs`` / ``disabled_extensions``), the scalar option table
(:func:`_extract_options`), the ``screen_saver`` and ``file_preview``
dicts and the declarative ``language_servers`` list.

Malformed values never raise: each problem is appended to
``config.errors`` (or the caller's *errors* list) and that option keeps
its default while the rest still apply.

Split out of :mod:`yate.yaterc` (wave f), which keeps the rc discovery
and exec loop (:func:`yate.yaterc.load_config`).  Import direction is
one-way: ``yaterc.py -> yaterc_options.py -> (yate.config, stdlib)``.
This module has no logging calls, so it does not depend on
:mod:`yate.logs`.

The functions are package-private (consumed only by
:mod:`yate.yaterc`); they are listed in ``__all__`` so those imports
read as deliberate re-exports to pyright (wave-a private-registry
precedent), not as ``reportPrivateUsage`` violations.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any, cast

from yate.config import (
    KNOWN_OPTIONS,
    VALID_KEYMAPS,
    VALID_KEY_PROTOCOLS,
    VALID_TRACE_LEVELS,
    FilePreviewConfig,
    LanguageServerSpec,
    ScreenSaverConfig,
    YateConfig,
)

__all__ = [
    "_extract_disabled_extensions",
    "_extract_extensions",
    "_extract_file_preview",
    "_extract_language_servers",
    "_extract_options",
    "_extract_path_list",
    "_extract_screen_saver",
    "_extract_theme_dirs",
    "_parse_journey_fraction",
    "_parse_language_server",
    "_require_str_list",
    "_require_str_map",
]


def _extract_path_list(  # noqa: Any - raw yaterc exec-namespace values, narrowed below
    namespace: dict[str, Any],
    config: YateConfig,
    rc_dir: Path,
    key: str,
    target: list[Path],
) -> None:
    """Pull one path-string-or-list option (*key*) out of one rc namespace.

    Shared body of :func:`_extract_extensions` and
    :func:`_extract_theme_dirs` -- only the option *key* and the target
    list differ.  The value is a path string or a list/tuple of path
    strings; each entry may point at a directory or a single ``.py`` file.
    ``~`` is expanded and relative paths resolve against *rc_dir*.
    Entries accumulate across rc files and are de-duplicated into *target*.
    """
    raw = namespace.get(key)
    if raw is None:
        return
    entries: list[Any]
    if isinstance(raw, str):
        entries = [raw]
    elif isinstance(raw, (list, tuple)):
        entries = list(cast(Sequence[Any], raw))
    else:
        config.errors.append(
            f"{key} must be a path string or a list of strings, got {raw!r}"
        )
        return
    for entry in entries:
        if not isinstance(entry, str) or not entry.strip():
            config.errors.append(
                f"{key} entries must be non-empty strings, got {entry!r}"
            )
            continue
        path = Path(entry.strip()).expanduser()
        if not path.is_absolute():
            path = rc_dir / path
        if not path.exists():
            config.errors.append(f"{key} path does not exist: {entry}")
            continue
        resolved = path.resolve()
        if resolved not in target:
            target.append(resolved)


def _extract_extensions(  # noqa: Any - raw yaterc exec-namespace values, narrowed below
    namespace: dict[str, Any], config: YateConfig, rc_dir: Path
) -> None:
    """Pull the ``extensions`` option out of one rc file's namespace.

    A thin wrapper over :func:`_extract_path_list`: each entry may point at
    a directory (all ``*.py`` inside are loaded) or a single ``.py`` file;
    resolved entries accumulate into ``config.extension_paths``.
    """
    _extract_path_list(
        namespace, config, rc_dir, "extensions", config.extension_paths
    )


def _extract_disabled_extensions(  # noqa: Any - raw yaterc exec-namespace values, narrowed below
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


def _extract_theme_dirs(  # noqa: Any - raw yaterc exec-namespace values, narrowed below
    namespace: dict[str, Any], config: YateConfig, rc_dir: Path
) -> None:
    """Pull the ``theme_dirs`` option out of one rc file's namespace.

    A thin wrapper over :func:`_extract_path_list` (which see): an entry
    may be a directory (every ``*.py`` inside is loaded as a theme file)
    or a single ``.py`` theme file; resolved entries accumulate into
    ``config.theme_dirs``.
    """
    _extract_path_list(
        namespace, config, rc_dir, "theme_dirs", config.theme_dirs
    )


def _parse_journey_fraction(  # noqa: Any - raw yaterc value, parsed and validated below
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


def _extract_screen_saver(  # noqa: Any - raw yaterc exec-namespace values, narrowed below
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


def _extract_file_preview(  # noqa: Any - raw yaterc exec-namespace values, narrowed below
    namespace: dict[str, Any], config: YateConfig
) -> None:
    """Pull the ``file_preview`` dict option out of one rc file.

    Recognized keys: ``enable`` (bool), ``position`` (``"right"`` or
    ``"left"``, the pane side of the results list), ``size`` (integer
    10-80, the preview pane width as a percent of the palette width),
    ``max_lines`` (integer 1-100000, the read/tokenize line cap) and
    ``max_size`` (integer 1024-16777216 bytes, above which the file is
    not read at all).  Missing keys keep their defaults; an unknown key
    or a wrong-typed value is reported individually and that key keeps
    its default while the rest still apply.  A later valid declaration
    replaces the previous one whole (same semantics as ``screen_saver``).
    """
    raw = namespace.get("file_preview")
    if raw is None:
        return
    if not isinstance(raw, dict):
        config.errors.append(f"file_preview must be a dict, got {raw!r}")
        return
    values = cast(dict[str, Any], raw)
    known = ("enable", "position", "size", "max_lines", "max_size")
    unknown = sorted(key for key in values if key not in known)
    if unknown:
        config.errors.append(f"file_preview has unknown keys: {unknown}")

    enable: bool = True
    if "enable" in values:
        value = values["enable"]
        if isinstance(value, bool):
            enable = value
        else:
            config.errors.append(
                f"file_preview enable must be True or False, got {value!r}"
            )

    position: str = "right"
    if "position" in values:
        value = values["position"]
        if isinstance(value, str) and value in ("right", "left"):
            position = value
        else:
            config.errors.append(
                f"file_preview position must be 'right' or 'left', got {value!r}"
            )

    size: int = 60
    if "size" in values:
        value = values["size"]
        # bool is a subclass of int -- reject it explicitly for this option.
        if isinstance(value, int) and not isinstance(value, bool) and 10 <= value <= 80:
            size = value
        else:
            config.errors.append(
                f"file_preview size must be an integer between 10 and 80, "
                f"got {value!r}"
            )

    max_lines: int = 2000
    if "max_lines" in values:
        value = values["max_lines"]
        if (
            isinstance(value, int)
            and not isinstance(value, bool)
            and 1 <= value <= 100_000
        ):
            max_lines = value
        else:
            config.errors.append(
                f"file_preview max_lines must be an integer between 1 and "
                f"100000, got {value!r}"
            )

    max_size: int = 1_048_576
    if "max_size" in values:
        value = values["max_size"]
        if (
            isinstance(value, int)
            and not isinstance(value, bool)
            and 1024 <= value <= 16_777_216
        ):
            max_size = value
        else:
            config.errors.append(
                f"file_preview max_size must be an integer between 1024 and "
                f"16777216 bytes, got {value!r}"
            )

    config.file_preview = FilePreviewConfig(
        enable=enable,
        position=position,
        size=size,
        max_lines=max_lines,
        max_size=max_size,
    )


def _extract_options(namespace: dict[str, Any], config: YateConfig) -> None:
    """Pull recognized option variables out of the exec'd namespace."""
    options = {name: namespace[name] for name in KNOWN_OPTIONS if name in namespace}

    keymap = options.get("keymap")
    if keymap is not None:
        if isinstance(keymap, str) and keymap in VALID_KEYMAPS:
            config.keymap = keymap
        else:
            config.errors.append(
                f"keymap must be one of {VALID_KEYMAPS}, got {keymap!r}"
            )

    key_protocol = options.get("key_protocol")
    if key_protocol is not None:
        if isinstance(key_protocol, str) and key_protocol in VALID_KEY_PROTOCOLS:
            config.key_protocol = key_protocol
        else:
            config.errors.append(
                f"key_protocol must be one of {VALID_KEY_PROTOCOLS}, got {key_protocol!r}"
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

    support_mouse = options.get("support_mouse")
    if support_mouse is not None:
        if isinstance(support_mouse, bool):
            config.support_mouse = support_mouse
        else:
            config.errors.append(
                f"support_mouse must be True or False, got {support_mouse!r}"
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
            if level_name in VALID_TRACE_LEVELS:
                config.yate_trace_level = level_name
            else:
                config.errors.append(
                    f"yate_trace_level must be one of {VALID_TRACE_LEVELS}, "
                    f"got {trace_level!r}"
                )
        else:
            config.errors.append(
                f"yate_trace_level must be a non-empty string, "
                f"got {trace_level!r}"
            )

    _extract_language_servers(namespace, config)
    _extract_screen_saver(namespace, config)
    _extract_file_preview(namespace, config)


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


def _parse_language_server(  # noqa: Any - raw yaterc mapping, validated field by field
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


def _require_str_list(  # noqa: Any - raw yaterc value, validated below
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


def _require_str_map(  # noqa: Any - raw yaterc value, validated below
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
