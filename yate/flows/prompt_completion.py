"""Tab-completion candidates for the bottom prompt line (pure functions).

The prompt bar asks for candidates with ``(text, mode)``; everything the
completion needs -- the command registry, the document session and the
workspace -- is passed in, so this module owns no state and imports no UI.
Command argument candidates come from each command's registered
``arg_completer`` metadata; this module owns no per-command knowledge.
"""

from __future__ import annotations

from yate.registries import CommandRegistry
from yate.services.workspace import Workspace, path_matches
from yate.session import EditorSession


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
        return _command_completions(text, commands=commands)
    if mode in ("open", "save", "new_file", "rename", "delete"):
        return path_matches(text, workspace)
    return []


def _command_completions(
    text: str,
    *,
    commands: CommandRegistry,
) -> list[str]:
    """Command-name candidates, then argument candidates from metadata."""
    if " " not in text:
        return sorted(n for n in commands.names() if n.startswith(text))
    name, _, rest = text.partition(" ")
    name = name.strip()
    rest = rest.lstrip()
    entry = commands.get(name)
    if entry is None or entry.arg_completer is None:
        return []
    values = entry.arg_completer(rest)
    return [f"{name} {v}" for v in values]
