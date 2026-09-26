"""Tab-completion candidates for the bottom prompt line (pure functions).

The prompt bar asks for candidates with ``(text, mode)``; everything the
completion needs -- the command registry, the document session and the
workspace -- is passed in, so this module owns no state and imports no UI.
"""

from __future__ import annotations

import os
from pathlib import Path

from yate.editor_syntax import available_filetypes
from yate.editor_view import theme
from yate.registries import CommandRegistry
from yate.services.workspace import Workspace
from yate.session import EditorSession

#: Commands whose single argument is a filesystem path.
_PATH_COMMANDS = frozenset({"e", "edit", "sp", "split", "vs", "vsplit"})
_SET_OPTIONS = (
    "filetype", "ft", "keymap", "lang", "language", "shell",
    "terminal_height", "theme", "show_hidden", "readonly",
)
_FILETYPE_KEYS = frozenset({"filetype", "ft", "language", "lang"})
_FILETYPE_COMMANDS = frozenset({"filetype", "ft", "language"})
_MANUAL_LANGS = ("en", "zh")


def prompt_completions(
    text: str,
    mode: str,
    *,
    commands: CommandRegistry,
    session: EditorSession,
    workspace: Workspace,
) -> list[str]:
    """Candidates extending *text* for the active prompt *mode*.

    Returns strings that extend *text*; the caller (``PromptBar``) decides
    how to cycle / apply the common prefix (bash-style).
    """
    if mode == "command":
        return _command_completions(
            text, commands=commands, session=session, workspace=workspace
        )
    if mode in ("open", "save", "new_file", "rename", "delete"):
        return _path_matches(text, workspace)
    return []


def _command_completions(
    text: str,
    *,
    commands: CommandRegistry,
    session: EditorSession,
    workspace: Workspace,
) -> list[str]:
    if " " not in text:
        return sorted(n for n in commands.names() if n.startswith(text))
    name, _, rest = text.partition(" ")
    name = name.strip()
    rest = rest.lstrip()
    if name in _PATH_COMMANDS:
        return [f"{name} {c}" for c in _path_matches(rest, workspace)]
    if name == "set":
        if "=" in rest:
            key, _, value = rest.partition("=")
            key = key.strip()
            if key == "keymap":
                vals = ("vsc", "vim")
            elif key == "theme":
                vals = tuple(theme.available())
            elif key in _FILETYPE_KEYS:
                vals = ("auto", *available_filetypes())
            elif key == "show_hidden":
                vals = ("on", "off")
            elif key == "readonly":
                vals = ("true", "false")
            else:
                return []
            return [
                f"{name} {key}={v}" for v in vals
                if v.startswith(value) and v != value
            ]
        return [
            f"{name} {opt}" for opt in _SET_OPTIONS
            if opt.startswith(rest) and opt != rest
        ]
    if name in _FILETYPE_COMMANDS:
        vals = ("auto", *available_filetypes())
        return [
            f"{name} {v}" for v in vals
            if v.startswith(rest) and v != rest
        ]
    if name in ("theme", "colorscheme"):
        return [
            f"{name} {t}" for t in theme.available()
            if t.startswith(rest) and t != rest
        ]
    if name == "manual":
        return [
            f"{name} {lang}" for lang in _MANUAL_LANGS
            if lang.startswith(rest) and lang != rest
        ]
    return []


def _path_matches(prefix: str, workspace: Workspace) -> list[str]:
    """Filesystem entries whose path starts with *prefix*.

    Relative paths are resolved against the workspace root (falling back to
    the process cwd), mirroring how ``:e`` and the open prompt treat paths.
    """
    expanded = os.path.expanduser(prefix)
    try:
        p = Path(expanded)
    except ValueError:
        return []
    if expanded.endswith(("/", os.sep)):
        # ``Path("src/")`` normalizes the separator away and would look like
        # the entry "src" inside its parent; with a trailing separator the
        # prefix *is* the directory to list and there is no needle to match.
        parent, base = p, ""
    else:
        parent, base = (p.parent if p.name else p), p.name
    if not parent.is_absolute() and workspace.root is not None:
        parent = workspace.root / parent
    if not parent.exists() or not parent.is_dir():
        return []
    try:
        entries = sorted(parent.iterdir(), key=lambda x: x.name.lower())
    except OSError:
        return []
    needle = base.lower()
    results: list[str] = []
    for entry in entries:
        if not entry.name.lower().startswith(needle):
            continue
        dir_part = prefix[: len(prefix) - len(base)] if base else prefix
        candidate = dir_part + entry.name
        if entry.is_dir():
            candidate += "/"
        if candidate != prefix:
            results.append(candidate)
    return results
