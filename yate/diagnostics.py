"""One-shot environment/configuration diagnostics for ``yate --diag``.

All values are read from existing modules' real interfaces -- nothing is
re-detected here.  Every section is best-effort: a failure in one probe
prints a single ``<probe failed: ...>`` line and the report keeps going, so
a buggy environment never hides the rest of the picture.

Output is plain text with a fixed section order, suitable for redirection
to a file or pasting into an issue. When stdout is a terminal the report
is styled with ANSI colors; redirected output stays clean plain text.
"""

from __future__ import annotations

import os
import platform
import re
import sys
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import Any, Callable

from yate import __description__, __version__
from yate.interfaces import AppProtocol

# Terminal environment variables worth surfacing.  Values are shown for the
# descriptive ones; opaque session ids are reported as ``<set>`` / ``<unset>``.
_TERMINAL_ENV = (
    "TERM",
    "COLORTERM",
    "TERM_PROGRAM",
    "TERM_PROGRAM_VERSION",
)
_OPAQUE_TERMINAL_ENV = ("WT_SESSION",)


# ------------------------------------------------------------------- color

# ANSI SGR codes; the report stays plain text whenever stdout is not a
# terminal (``format_report(color=False)``), so redirection / issue pasting
# never carries escape sequences.
_ANSI_RESET = "\x1b[0m"
_ANSI_BOLD = "\x1b[1m"
_ANSI_DIM = "\x1b[2m"
_ANSI_CYAN = "\x1b[36m"
_ANSI_BOLD_CYAN = "\x1b[1;36m"
_ANSI_GREEN = "\x1b[32m"
_ANSI_RED = "\x1b[31m"

#: ``  key: value`` / ``    key: value`` -- the unified key-value shape every
#: section uses (keys never start with a space or hyphen, so bullets and
#: list items are excluded).
_KV_LINE_RE = re.compile(r"^( +)([^ -].*?): (.+)$")
#: ``  label:`` -- a sub-header that introduces an indented list below it.
_LABEL_LINE_RE = re.compile(r"^( +)(\S.*):$")
_SECTION_TITLE_RE = re.compile(r"^\[[a-z]+\]$")


# ----------------------------------------------------------------- version

def version_lines() -> str:
    """yate / description / Python / platform information (``--version``).

    Kept free of any configuration loading so ``--version`` stays instant
    and works without a terminal.
    """
    impl = platform.python_implementation()
    return (
        f"yate {__version__} — {__description__}\n"
        f"Python {platform.python_version()} ({impl})\n"
        f"{platform.platform()}"
    )


# ------------------------------------------------------------------ report

def format_report(app: AppProtocol, *, color: bool = False) -> str:
    """Collect every diagnostic section and return the report text.

    With ``color=True`` the lines carry ANSI styling (section titles, keys,
    errors); callers pass ``sys.stdout.isatty()`` so redirected output
    stays clean plain text.
    """
    sections: list[tuple[str, Callable[[], list[str]]]] = [
        ("system", _section_system),
        ("terminal", _section_terminal),
        ("shell", _section_shell),
        ("paths", _section_paths),
        ("yaterc", lambda: _section_yaterc(app)),
        ("config", lambda: _section_config(app)),
        ("themes", _section_themes),
        ("syntax", _section_syntax),
        ("extensions", lambda: _section_extensions(app)),
        ("lsp", lambda: _section_lsp(app)),
        ("fonts", _section_fonts),
        ("packages", _section_packages),
    ]

    lines: list[str] = [
        f"yate {__version__} — diagnostics",
        "=" * 40,
        "",
    ]
    for title, builder in sections:
        lines.append(f"[{title}]")
        try:
            body = builder()
        except Exception as exc:  # noqa: BLE001 - best-effort downgrade
            body = [f"  <probe failed: {type(exc).__name__}: {exc}>"]
        if body:
            lines.extend(body)
        else:
            lines.append("  (none)")
        lines.append("")
    text = "\n".join(lines).rstrip()
    if color:
        text = "\n".join(_colorize_line(line) for line in text.splitlines())
    return text + "\n"


def print_report(app: AppProtocol) -> None:
    """Print the report to stdout, colored when stdout is a terminal."""
    color = sys.stdout.isatty()
    if color:
        _enable_windows_ansi()
    print(format_report(app, color=color))


def _enable_windows_ansi() -> None:
    """Enable ANSI escape processing on legacy Windows consoles (best effort).

    Windows Terminal / VS Code / iTerm render ANSI natively; plain conhost
    needs ``ENABLE_VIRTUAL_TERMINAL_PROCESSING`` turned on first.
    """
    if sys.platform != "win32":
        return
    try:
        import ctypes  # pylint: disable=import-outside-toplevel; Windows only

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        mode = ctypes.c_uint32()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            kernel32.SetConsoleMode(handle, mode.value | 0x0004)  # noqa: PLR2004
    except Exception:  # noqa: BLE001 - best-effort, never block the report
        pass


def _colorize_line(line: str) -> str:
    """Wrap one plain report line in ANSI styling (rules in priority order)."""
    if line.startswith("=="):
        return f"{_ANSI_DIM}{line}{_ANSI_RESET}"
    if _SECTION_TITLE_RE.match(line):
        return f"{_ANSI_BOLD_CYAN}{line}{_ANSI_RESET}"
    if line.startswith("yate ") and line.endswith("diagnostics"):
        return f"{_ANSI_BOLD}{line}{_ANSI_RESET}"
    if "<probe failed:" in line or "[error]" in line:
        return f"{_ANSI_RED}{line}{_ANSI_RESET}"
    if "[ok]" in line:
        return f"{_ANSI_GREEN}{line}{_ANSI_RESET}"
    match = _KV_LINE_RE.match(line)
    if match:
        indent, key, value = match.groups()
        return f"{_ANSI_CYAN}{indent}{key}: {_ANSI_RESET}{value}"
    if _LABEL_LINE_RE.match(line):
        return f"{_ANSI_CYAN}{line}{_ANSI_RESET}"
    return line


# -------------------------------------------------------------- formatting

def _kv(key: str, value: Any, *, width: int = 18) -> str:
    """``  key : value`` with the key padded to *width* characters."""
    return f"  {key.ljust(width)}: {value}"


# ----------------------------------------------------------------- system

def _section_system() -> list[str]:
    frozen = "yes" if getattr(sys, "frozen", False) else "no"
    return [
        _kv("platform", platform.platform()),
        _kv("machine", platform.machine()),
        _kv("python", f"{platform.python_version()} ({platform.python_implementation()})"),
        _kv("executable", sys.executable),
        _kv("prefix", sys.prefix),
        _kv("frozen", frozen),
    ]


# --------------------------------------------------------------- terminal

def _section_terminal() -> list[str]:
    from yate.services import fonts

    detected = fonts.detect_terminal()
    lines = [
        _kv("detected", detected),
        _kv("isatty", "yes (stdout)" if sys.stdout.isatty() else "no"),
    ]
    for name in _TERMINAL_ENV:
        value = os.environ.get(name)
        lines.append(_kv(name, value if value else "<unset>", width=20))
    for name in _OPAQUE_TERMINAL_ENV:
        value = os.environ.get(name)
        lines.append(_kv(name, "<set>" if value else "<unset>", width=20))
    return lines


# ------------------------------------------------------------------ shell

def _section_shell() -> list[str]:
    from yate.editor_term.shells import resolve_shell
    from yate.services.shell import shell_name

    integrated = resolve_shell()
    return [
        _kv("integrated", " ".join(integrated)),
        _kv(":! default", shell_name()),
    ]


# ------------------------------------------------------------------ paths

def _section_paths() -> list[str]:
    from yate.logs import crash, crash_data_dir
    from yate.paths import bundled_extensions_dir, package_root

    user_dir = Path.home() / ".yate"
    crash_dir = crash_data_dir()
    current_crash = crash.current_crash_file()
    all_crashes = sorted(crash_dir.glob("crash-*.err")) if crash_dir.is_dir() else []
    # Exclude this process's own header-only placeholder: it is not a
    # previous crash report and gets deleted on clean shutdown.
    crash_files = [f for f in all_crashes if current_crash is None or f != current_crash]
    crash_note = (
        f"{len(crash_files)} .err file(s)"
        if crash_files else "(no crash reports)"
    )
    lines = [
        _kv("package root", package_root()),
        _kv("bundled extensions", bundled_extensions_dir()),
        _kv("user dir (~/.yate)", user_dir),
        _kv("crash data dir", f"{crash_dir} ({crash_note})"),
    ]
    if crash_files:
        recent = crash_files[-5:]
        lines.append("  recent crash reports:")
        for f in recent:
            lines.append(f"    - {f.name}")
    return lines


# ------------------------------------------------------------------ yaterc

def _section_yaterc(app: AppProtocol) -> list[str]:
    from yate.config import find_project_config, user_config_path

    config = app.config
    user_rc = user_config_path()
    user_note = "exists" if user_rc.is_file() else "missing"
    project_rc = find_project_config()
    project_note = str(project_rc) if project_rc is not None else "not found"

    lines = [
        _kv("user rc", f"{user_rc} ({user_note})"),
        _kv("project rc", project_note),
        "  load order:",
    ]
    if config.sources:
        for src in config.sources:
            lines.append(f"    - {src}")
    else:
        lines.append("    (no yaterc loaded)")
    lines.append("  load errors:")
    if config.errors:
        for err in config.errors:
            lines.append(f"    - {err}")
    else:
        lines.append("    none")
    return lines


# ------------------------------------------------------------------ config

def _section_config(app: AppProtocol) -> list[str]:
    c = app.config
    shell_value = c.shell if c.shell else "(default)"
    return [
        _kv("keymap", c.keymap, width=19),
        _kv("theme", c.theme, width=19),
        _kv("tab_width", c.tab_width, width=19),
        _kv("use_spaces", c.use_spaces, width=19),
        _kv("shell", shell_value, width=19),
        _kv("terminal_height", c.terminal_height, width=19),
        _kv("show_hidden", c.show_hidden, width=19),
        _kv("disabled_extensions", c.disabled_extensions, width=19),
        _kv("extension_paths", [str(p) for p in c.extension_paths], width=19),
        _kv("theme_dirs", [str(p) for p in c.theme_dirs], width=19),
    ]


# ------------------------------------------------------------------ themes

def _section_themes() -> list[str]:
    from yate.editor_view import theme as theme_mod

    return [_kv("available themes", ", ".join(theme_mod.available()), width=18)]


# ------------------------------------------------------------------ syntax

def _section_syntax() -> list[str]:
    from yate.editor_syntax import available_filetypes, resolve_filetype
    from yate.editor_syntax.ts_backend import available_for, ts_available
    from yate.editor_syntax.ts_backend.languages import BUILTIN_PACKS

    lines: list[str] = []
    if ts_available():
        grammars: list[str] = []
        for name in BUILTIN_PACKS:
            ft = resolve_filetype(name)
            if ft is not None and available_for(ft):
                grammars.append(name)
        ts_version = _package_version("tree_sitter") or "?"
        grammar_str = ", ".join(grammars) if grammars else "none"
        lines.append(_kv(
            "tree-sitter",
            f"available (tree-sitter {ts_version}; grammars: {grammar_str})",
            width=14,
        ))
    else:
        lines.append(_kv("tree-sitter", "not available (tree_sitter not installed)", width=14))

    filetypes = available_filetypes()
    shown = ", ".join(filetypes[:12])
    if len(filetypes) > 12:
        shown += f", ... ({len(filetypes)} total)"
    lines.append(_kv("regex languages", shown, width=14))
    return lines


# -------------------------------------------------------------- extensions

def _section_extensions(app: AppProtocol) -> list[str]:
    from yate.paths import bundled_extensions_dir

    lines: list[str] = ["  candidate dirs:"]

    def _dir_line(label: str, path: Path) -> None:
        if path.is_dir():
            count = len(list(path.glob("*.py")))
            lines.append(f"    {label:8}: {path} ({count} script(s))")
        else:
            lines.append(f"    {label:8}: {path} (missing)")

    # rc-declared extension paths
    for p in app.config.extension_paths:
        _dir_line("rc", p)
    _dir_line("bundled", bundled_extensions_dir())
    for d in app.ext_dirs:
        _dir_line("ext-dir", d)
    _dir_line("project", Path.cwd() / "extensions")
    _dir_line("user", Path.home() / ".yate" / "extensions")
    for f in app.ext_files:
        if f.is_file():
            lines.append(f"    ext-file: {f}")
        else:
            lines.append(f"    ext-file: {f} (missing)")

    lines.append("  loaded:")
    loaded = app.extension_loader.loaded
    if not loaded:
        lines.append("    (none)")
        return lines
    for record in loaded:
        if record.error:
            lines.append(f"    [error] {record.name}")
            lines.append(f"            {record.path}")
            lines.append(f"            {record.error}")
        else:
            lines.append(f"    [ok]    {record.name}")
            lines.append(f"            {record.path}")
    return lines


# --------------------------------------------------------------------- lsp

def _section_lsp(app: AppProtocol) -> list[str]:
    configs = app.lsp.configs()
    states = app.lsp.states()
    if not configs:
        return ["  (no LSP servers registered)"]

    lines: list[str] = []
    for cfg in configs:
        state = states.get(cfg.name)
        state_name = state.value if state is not None else "unknown"
        env_keys = sorted(cfg.env.keys()) if cfg.env else []
        env_note = ", ".join(env_keys) if env_keys else "(none)"
        filetypes = ", ".join(cfg.filetypes)
        lang_ids = ", ".join(f"{k}:{v}" for k, v in cfg.language_ids.items())
        root_markers = ", ".join(cfg.root_markers)
        lines.append(f"  {cfg.name}")
        lines.append(f"    command      : {cfg.command or '(none)'}")
        lines.append(f"    args         : {cfg.args}")
        lines.append(f"    filetypes    : {filetypes}")
        lines.append(f"    language_ids : {{{lang_ids}}}")
        lines.append(f"    root markers : {root_markers}")
        lines.append(f"    state        : {state_name}")
        lines.append(f"    env keys     : {env_note}")
    return lines


# ------------------------------------------------------------------- fonts

def _section_fonts() -> list[str]:
    from yate.services import fonts

    status = fonts.font_status()
    installed = ", ".join(status.installed_fonts) if status.installed_fonts else "(none)"
    return [
        _kv("nerd font", "yes" if status.has_nerd_font else "no"),
        _kv("installed", installed),
        _kv("terminal", status.terminal),
    ]


# ---------------------------------------------------------------- packages

def _section_packages() -> list[str]:
    names = [
        "textual",
        "tree_sitter",
        "tree_sitter_python",
        "tree_sitter_bash",
    ]
    lines: list[str] = []
    width = max(len(n) for n in names)
    for name in names:
        version = _package_version(name)
        display = version if version is not None else "not installed"
        lines.append(_kv(name, display, width=width))
    return lines


def _package_version(name: str) -> str | None:
    """Distribution version of *name*, or ``None`` if not installed."""
    try:
        return importlib_metadata.version(name)
    except importlib_metadata.PackageNotFoundError:
        return None
