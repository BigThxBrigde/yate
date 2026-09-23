"""Unit tests for Workspace file filtering.

Covers the explorer filter feature: dotfile visibility (``show_hidden``)
and ``.gitignore`` / ``.yateignore`` pattern handling (root level and
per-directory, negation, directory-only rules).
"""

# pyright: reportPrivateUsage=false

from __future__ import annotations

from pathlib import Path

import pytest

from yate.services.workspace import IGNORED_NAMES, Entry, Workspace


def entry_names(entries: list[Entry]) -> list[str]:
    return [e.name for e in entries]


def list_names(ws: Workspace, path: Path | None = None) -> list[str]:
    return entry_names(ws.list_dir(path if path is not None else ws.root))  # type: ignore[arg-type]


# --- Entry ------------------------------------------------------------------


def test_hidden_flag_is_dot_prefix() -> None:
    p = Path("x/.secret")
    assert Entry(p, ".secret", False).hidden
    assert not Entry(Path("x/secret"), "secret", False).hidden


# --- show_hidden ------------------------------------------------------------


@pytest.fixture
def ws(tmp_path: Path) -> Workspace:
    (tmp_path / "plain.py").write_text("x\n", encoding="utf-8")
    (tmp_path / ".dotfile").write_text("x\n", encoding="utf-8")
    (tmp_path / ".config").mkdir()
    (tmp_path / "sub").mkdir()
    return Workspace(tmp_path)


def test_dotfiles_hidden_by_default(ws: Workspace) -> None:
    assert not ws.show_hidden
    got = list_names(ws)
    assert "plain.py" in got
    assert "sub" in got
    assert ".dotfile" not in got
    assert ".config" not in got


def test_show_hidden_reveals_dotfiles(ws: Workspace) -> None:
    ws.show_hidden = True
    got = list_names(ws)
    assert ".dotfile" in got
    assert ".config" in got
    assert "plain.py" in got


def test_walk_files_respects_show_hidden(ws: Workspace) -> None:
    files = {f.name for f in ws.walk_files()}
    assert files == {"plain.py"}
    ws.show_hidden = True
    files = {f.name for f in ws.walk_files()}
    assert ".dotfile" in files
    assert "plain.py" in files


def test_visible_tree_respects_show_hidden(ws: Workspace) -> None:
    rows = ws.visible_tree(set())
    got = {e.name for _, e in rows}
    assert ".dotfile" not in got
    ws.show_hidden = True
    rows = ws.visible_tree(set())
    assert ".dotfile" in {e.name for _, e in rows}


# --- _parse_ignore ----------------------------------------------------------


def parse_ignore(text: str) -> list[tuple[str, bool, bool]]:
    pats = Workspace._parse_ignore(text)
    return [(p.pattern, p.negated, p.dir_only) for p in pats]


def test_comments_and_blank_lines_skipped() -> None:
    assert parse_ignore("# comment\n\n   \n*.log\n") == [("*.log", False, False)]


def test_negation() -> None:
    assert parse_ignore("!keep.txt") == [("keep.txt", True, False)]


def test_dir_only_marker() -> None:
    assert parse_ignore("build/") == [("build", False, True)]


def test_patterns_lowercased() -> None:
    assert parse_ignore("*.TMP") == [("*.tmp", False, False)]


def test_bare_negation_or_slash_ignored() -> None:
    assert parse_ignore("!\n/\n") == []


# --- ignore rules -----------------------------------------------------------


def test_root_gitignore_glob_hides_matching_files(tmp_path: Path) -> None:
    (tmp_path / ".gitignore").write_text("*.log\n", encoding="utf-8")
    (tmp_path / "a.log").write_text("x\n", encoding="utf-8")
    (tmp_path / "a.py").write_text("x\n", encoding="utf-8")
    ws = Workspace(tmp_path)
    got = list_names(ws)
    assert "a.log" not in got
    assert "a.py" in got


def test_yateignore_is_second_source(tmp_path: Path) -> None:
    (tmp_path / ".yateignore").write_text("secret.txt\n", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("x\n", encoding="utf-8")
    (tmp_path / "ok.txt").write_text("x\n", encoding="utf-8")
    ws = Workspace(tmp_path)
    got = list_names(ws)
    assert "secret.txt" not in got
    assert "ok.txt" in got


def test_negation_reincludes(tmp_path: Path) -> None:
    (tmp_path / ".gitignore").write_text("*.txt\n!keep.txt\n", encoding="utf-8")
    (tmp_path / "drop.txt").write_text("x\n", encoding="utf-8")
    (tmp_path / "keep.txt").write_text("x\n", encoding="utf-8")
    ws = Workspace(tmp_path)
    got = list_names(ws)
    assert "drop.txt" not in got
    assert "keep.txt" in got


def test_last_match_wins(tmp_path: Path) -> None:
    (tmp_path / ".gitignore").write_text("!special.log\n*.log\n", encoding="utf-8")
    (tmp_path / "special.log").write_text("x\n", encoding="utf-8")
    ws = Workspace(tmp_path)
    assert "special.log" not in list_names(ws)


def test_dir_only_rule_spares_files(tmp_path: Path) -> None:
    (tmp_path / ".gitignore").write_text("build/\n", encoding="utf-8")
    (tmp_path / "build").mkdir()
    (tmp_path / "build2").write_text("x\n", encoding="utf-8")
    ws = Workspace(tmp_path)
    got = list_names(ws)
    assert "build" not in got
    assert "build2" in got


def test_matching_is_case_insensitive(tmp_path: Path) -> None:
    (tmp_path / ".gitignore").write_text("*.log\n", encoding="utf-8")
    (tmp_path / "UPPER.LOG").write_text("x\n", encoding="utf-8")
    ws = Workspace(tmp_path)
    assert "UPPER.LOG" not in list_names(ws)


def test_directory_level_rules_apply_only_to_that_dir(tmp_path: Path) -> None:
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / ".yateignore").write_text("hidden.txt\n", encoding="utf-8")
    (sub / "hidden.txt").write_text("x\n", encoding="utf-8")
    (tmp_path / "hidden.txt").write_text("x\n", encoding="utf-8")
    ws = Workspace(tmp_path)
    assert "hidden.txt" not in list_names(ws, sub)
    assert "hidden.txt" in list_names(ws)


def test_sub_dir_rule_overrides_root_rule(tmp_path: Path) -> None:
    sub = tmp_path / "sub"
    sub.mkdir()
    (tmp_path / ".gitignore").write_text("*.log\n", encoding="utf-8")
    (sub / ".gitignore").write_text("!special.log\n", encoding="utf-8")
    (sub / "special.log").write_text("x\n", encoding="utf-8")
    (sub / "other.log").write_text("x\n", encoding="utf-8")
    ws = Workspace(tmp_path)
    got = list_names(ws, sub)
    assert "special.log" in got
    assert "other.log" not in got


def test_ignored_names_always_hidden_even_with_show_hidden(tmp_path: Path) -> None:
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "x.pyc").write_bytes(b"")
    (tmp_path / ".git").mkdir()
    ws = Workspace(tmp_path)
    ws.show_hidden = True
    got = list_names(ws)
    for banned in IGNORED_NAMES:
        assert banned not in got


def test_walk_files_applies_ignore_rules(tmp_path: Path) -> None:
    sub = tmp_path / "sub"
    sub.mkdir()
    (tmp_path / ".gitignore").write_text("*.tmp\n", encoding="utf-8")
    (tmp_path / "keep.py").write_text("x\n", encoding="utf-8")
    (sub / "drop.tmp").write_text("x\n", encoding="utf-8")
    (sub / "fine.py").write_text("x\n", encoding="utf-8")
    ws = Workspace(tmp_path)
    got = {p.name for p in ws.walk_files()}
    assert got == {"keep.py", "fine.py"}


def test_walk_files_does_not_follow_symlinked_directories(tmp_path: Path) -> None:
    (tmp_path / "root.py").write_text("x\n", encoding="utf-8")
    inside = tmp_path / "inside"
    inside.mkdir()
    (inside / "inner.py").write_text("x\n", encoding="utf-8")
    # a link pointing back at the workspace root would recurse forever
    loop = tmp_path / "loop"
    try:
        loop.symlink_to(tmp_path, target_is_directory=True)
    except OSError:
        pytest.skip("creating directory symlinks requires privileges on this OS")
    ws = Workspace(tmp_path)
    got = {p.name for p in ws.walk_files()}
    assert got == {"root.py", "inner.py"}


def test_set_root_reloads_ignores(tmp_path: Path) -> None:
    other = tmp_path / "other"
    other.mkdir()
    (tmp_path / ".gitignore").write_text("a.py\n", encoding="utf-8")
    (other / "a.py").write_text("x\n", encoding="utf-8")
    ws = Workspace(tmp_path)
    assert "a.py" not in list_names(ws)
    ws.set_root(other)
    assert ws.root is not None
    assert "a.py" in list_names(ws)


def test_open_target_loads_ignores(tmp_path: Path) -> None:
    (tmp_path / ".gitignore").write_text("b.log\n", encoding="utf-8")
    (tmp_path / "b.log").write_text("x\n", encoding="utf-8")
    ws = Workspace()
    assert ws.open_target(tmp_path / "b.log") == "file"
    assert ws.root is not None
    assert "b.log" not in list_names(ws)
