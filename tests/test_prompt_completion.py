"""Tab-completion candidates for the bottom prompt line.

Covers the ``prompt_completions`` dispatch, the argument completion of the
``:set`` / filetype / theme / manual commands and the filesystem matching
behind the path modes -- all through the public entry point.
"""

# pyright: reportPrivateUsage=false

from __future__ import annotations

from pathlib import Path

import pytest

from yate.config import YateConfig
from yate.prompt_completion import _path_matches, prompt_completions
from yate.registries import CommandRegistry
from yate.services.workspace import Workspace
from yate.session import EditorSession


def _commands(*names: str) -> CommandRegistry:
    registry = CommandRegistry()
    for name in names:
        registry.register(name, lambda _args: None, "test command")
    return registry


def _prompt(text: str, mode: str = "command", root: Path | None = None) -> list[str]:
    workspace = Workspace()
    if root is not None:
        workspace.set_root(root)
    return prompt_completions(
        text,
        mode,
        commands=_commands("write", "wipe", "quit", "set", "e", "theme"),
        session=EditorSession(YateConfig()),
        workspace=workspace,
    )


# --- dispatch ---------------------------------------------------------------


def test_command_mode_lists_names_with_the_prefix() -> None:
    """A bare prefix completes against the registered command names."""
    assert _prompt("w") == ["wipe", "write"]


def test_unknown_prompt_mode_offers_nothing() -> None:
    """Modes without a completion source return an empty list."""
    assert _prompt("w", mode="find") == []


# --- path modes -------------------------------------------------------------


def test_path_mode_lists_entries_under_the_workspace_root(tmp_path: Path) -> None:
    """Relative prefixes resolve against the workspace root."""
    (tmp_path / "alpha.txt").write_text("x", encoding="utf-8")
    (tmp_path / "beta").mkdir()
    assert _prompt("al", mode="open", root=tmp_path) == ["alpha.txt"]
    assert _prompt("be", mode="save", root=tmp_path) == ["beta/"]


def test_path_mode_excludes_the_exact_name(tmp_path: Path) -> None:
    """A name that already matches the prefix exactly is not offered."""
    (tmp_path / "alpha.txt").write_text("x", encoding="utf-8")
    assert _prompt("alpha.txt", mode="open", root=tmp_path) == []


def test_path_mode_returns_nothing_for_a_missing_directory(tmp_path: Path) -> None:
    """A prefix whose parent does not exist yields no candidates."""
    assert _prompt("nope/deep", mode="open", root=tmp_path) == []


def test_path_prefix_with_trailing_separator_lists_the_directory(
    tmp_path: Path,
) -> None:
    """A trailing separator means "list this directory", not "match an entry".

    With ``src/`` as the prefix there is no needle to match, so the entries
    *inside* ``src`` are offered with their ``src/`` prefix intact (the old
    code re-appended the whole prefix and produced corrupt ``ssrc...`` names).
    """
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "alpha.py").write_text("x", encoding="utf-8")
    (tmp_path / "src" / "beta.py").write_text("x", encoding="utf-8")
    (tmp_path / "other").mkdir()
    workspace = Workspace(tmp_path)

    assert _path_matches("src/", workspace) == ["src/alpha.py", "src/beta.py"]
    # a partial name still resolves to the directory entry itself
    assert _path_matches("src", workspace) == ["src/"]
    assert _path_matches("sr", workspace) == ["src/"]


def test_path_mode_returns_nothing_when_the_parent_is_a_file(tmp_path: Path) -> None:
    """A prefix that walks *through* a file yields no candidates."""
    (tmp_path / "file.txt").write_text("x", encoding="utf-8")
    assert _prompt("file.txt/inner", mode="open", root=tmp_path) == []


def test_path_mode_expands_the_home_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``~`` is expanded before matching entries."""
    home = tmp_path / "home"
    (home / "notes").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    assert _prompt("~/no", mode="open") == ["~/notes/"]


# --- command arguments ------------------------------------------------------


def test_path_command_appends_candidates(tmp_path: Path) -> None:
    """``:e`` keeps the command name in front of every candidate."""
    (tmp_path / "notes.md").write_text("x", encoding="utf-8")
    assert _prompt("e no", root=tmp_path) == ["e notes.md"]


def test_set_option_completion_lists_matching_keys() -> None:
    """``:set`` without a value completes the option names."""
    assert _prompt("set the") == ["set theme"]
    assert "set keymap" in _prompt("set k")


def test_set_option_completion_excludes_an_exact_option() -> None:
    """An option that already matches exactly is not offered again."""
    assert _prompt("set shell") == []


def test_set_keymap_values() -> None:
    """``keymap`` offers the two built-in maps."""
    assert _prompt("set keymap=") == ["set keymap=vsc", "set keymap=vim"]


def test_set_theme_values_come_from_the_registry() -> None:
    """``theme`` offers the registered theme names."""
    assert "set theme=latte" in _prompt("set theme=l")
    assert "set theme=mocha" not in _prompt("set theme=l")


def test_set_filetype_values_include_auto() -> None:
    """``filetype`` completes from the syntax registry, prefixed by auto."""
    assert "set filetype=auto" in _prompt("set filetype=")
    assert "set filetype=python" in _prompt("set filetype=py")


def test_set_show_hidden_values() -> None:
    """``show_hidden`` offers on / off."""
    assert _prompt("set show_hidden=") == ["set show_hidden=on", "set show_hidden=off"]


def test_set_readonly_values() -> None:
    """``readonly`` offers true / false."""
    assert _prompt("set readonly=") == [
        "set readonly=true",
        "set readonly=false",
    ]


def test_set_unknown_key_offers_nothing() -> None:
    """An option without a value source offers no candidates."""
    assert _prompt("set nope=") == []


def test_filetype_command_values() -> None:
    """``:filetype`` completes filetypes without the ``key=`` form."""
    assert "filetype python" in _prompt("filetype py")


def test_theme_command_values() -> None:
    """``:theme`` completes the registered theme names."""
    assert "theme latte" in _prompt("theme l")
    assert "theme mocha" not in _prompt("theme l")


def test_manual_command_values() -> None:
    """``:manual`` offers the shipped languages."""
    assert _prompt("manual ") == ["manual en", "manual zh"]


def test_unknown_command_with_arguments_offers_nothing() -> None:
    """A command with no argument completion returns an empty list."""
    assert _prompt("write foo") == []
