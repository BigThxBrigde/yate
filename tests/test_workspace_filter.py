"""Unit tests for Workspace file filtering.

Covers the explorer filter feature: dotfile visibility (``show_hidden``)
and ``.gitignore`` / ``.yateignore`` pattern handling (root level and
per-directory, negation, directory-only rules).
"""

# pyright: reportPrivateUsage=false

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from yate.services.workspace import IGNORED_NAMES, Entry, Workspace


def _raise_permission(*_args: Any, **_kwargs: Any) -> Any:
    """``Path.iterdir`` stand-in that always fails."""
    raise PermissionError("denied")


def root_of(ws: Workspace) -> Path:
    """The workspace root, asserted to be set."""
    assert ws.root is not None
    return ws.root


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


# --- unreadable directories -------------------------------------------------


def test_list_dir_returns_nothing_when_iterdir_fails(
    ws: Workspace, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An unreadable directory yields no entries instead of raising."""
    with monkeypatch.context() as patch_ctx:
        patch_ctx.setattr("pathlib.Path.iterdir", _raise_permission)
        assert ws.list_dir(root_of(ws)) == []


def test_walk_files_survives_an_unreadable_directory(
    ws: Workspace, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A directory that cannot be read is skipped by the walk."""
    with monkeypatch.context() as patch_ctx:
        patch_ctx.setattr("pathlib.Path.iterdir", _raise_permission)
        assert ws.walk_files() == []


# --- no workspace root ------------------------------------------------------


def test_load_root_ignores_without_a_root() -> None:
    """Without an open folder there are no ignore files to read."""
    workspace = Workspace()

    workspace._load_root_ignores()

    assert workspace._root_ignores == []


def test_visible_tree_without_a_root_is_empty() -> None:
    """The flattened tree needs an open folder."""
    assert Workspace().visible_tree(set()) == []


# --- visible tree -----------------------------------------------------------


def test_visible_tree_follows_expanded_directories(ws: Workspace) -> None:
    """Nested expanded folders are flattened depth-first at growing depth."""
    root = root_of(ws)
    nested = root / "sub" / "deep"
    nested.mkdir(parents=True)
    (nested / "file.txt").write_text("x\n", encoding="utf-8")

    depths = {
        entry.name: depth
        for depth, entry in ws.visible_tree({root / "sub", nested})
    }

    assert depths["sub"] == 1
    assert depths["deep"] == 2
    assert depths["file.txt"] == 3


def test_walk_files_stops_at_the_limit(tmp_path: Path) -> None:
    """The walk bails out as soon as the limit is reached."""
    for name in ("a.py", "b.py", "c.py"):
        (tmp_path / name).write_text("x\n", encoding="utf-8")
    ws = Workspace(tmp_path)

    assert ws.walk_files(limit=0) == []
    assert len(ws.walk_files(limit=1)) == 1


def test_walk_files_without_a_root_is_empty() -> None:
    """Quick open collects nothing while no folder is open."""
    assert Workspace().walk_files() == []


def test_walk_files_prunes_ignored_directories(tmp_path: Path) -> None:
    """Ignored directory names are skipped during the walk."""
    (tmp_path / "keep.py").write_text("x\n", encoding="utf-8")
    cache = tmp_path / "sub" / "__pycache__"
    cache.mkdir(parents=True)
    (cache / "junk.pyc").write_bytes(b"")

    names = {p.name for p in Workspace(tmp_path).walk_files()}

    assert names == {"keep.py"}


def test_open_target_switches_to_a_directory(tmp_path: Path) -> None:
    """Opening a folder roots the workspace and loads its ignore file."""
    (tmp_path / ".gitignore").write_text("c.log\n", encoding="utf-8")
    (tmp_path / "c.log").write_text("x\n", encoding="utf-8")
    ws = Workspace()

    assert ws.open_target(tmp_path) == "dir"
    assert ws.root == tmp_path.resolve()
    assert "c.log" not in list_names(ws)


# --- name validation --------------------------------------------------------


@pytest.mark.parametrize("name", ["", "   ", ".", ".."])
def test_validate_name_rejects_empty_and_dot_names(
    ws: Workspace, name: str
) -> None:
    """Empty and single-dot names are refused."""
    with pytest.raises(ValueError, match="empty name"):
        ws.validate_name(name)


@pytest.mark.parametrize("name", ["a/b", "a\\b", "a:b"])
def test_validate_name_rejects_separators(ws: Workspace, name: str) -> None:
    """Names must stay single-segment."""
    with pytest.raises(ValueError, match="must not contain"):
        ws.validate_name(name)


def test_validate_name_strips_surrounding_space(ws: Workspace) -> None:
    """Surrounding whitespace is not part of the name."""
    assert ws.validate_name("  ok.txt  ") == "ok.txt"


# --- file mutation ----------------------------------------------------------


def test_create_entry_makes_files_and_folders(ws: Workspace) -> None:
    """Both branches create their target, parents included."""
    root = root_of(ws)
    folder = ws.create_entry(root / "sub", "fresh", is_dir=True)
    assert folder.is_dir()

    missing_parent = root / "not-yet"
    file = ws.create_entry(missing_parent, "f.txt", is_dir=False)
    assert file.is_file()
    assert file.parent == missing_parent


def test_create_entry_refuses_an_existing_target(ws: Workspace) -> None:
    """Creating over an existing entry is an error, not an overwrite."""
    with pytest.raises(FileExistsError):
        ws.create_entry(root_of(ws), "plain.py", is_dir=False)


def test_rename_entry_with_the_same_name_is_a_noop(ws: Workspace) -> None:
    """Renaming to the current name returns the path untouched."""
    path = root_of(ws) / "plain.py"
    assert ws.rename_entry(path, "plain.py") == path
    assert path.is_file()


def test_rename_entry_moves_the_file(ws: Workspace) -> None:
    """A successful rename returns the new path."""
    renamed = ws.rename_entry(root_of(ws) / "plain.py", "renamed.py")
    assert renamed.name == "renamed.py"
    assert renamed.is_file()


def test_rename_entry_refuses_an_existing_target(ws: Workspace) -> None:
    """Renaming onto an existing entry is an error."""
    with pytest.raises(FileExistsError):
        ws.rename_entry(root_of(ws) / "plain.py", ".dotfile")


def test_remove_entry_deletes_files_and_directories(ws: Workspace) -> None:
    """Files are unlinked; directories are removed as a tree."""
    root = root_of(ws)
    ws.remove_entry(root / "plain.py")
    assert not (root / "plain.py").exists()

    ws.remove_entry(root / "sub")
    assert not (root / "sub").exists()


# --- text detection ---------------------------------------------------------


def test_is_text_file_by_conventional_name(tmp_path: Path) -> None:
    """Extension-less build files are recognised by name."""
    makefile = tmp_path / "makefile"
    makefile.write_text("all:\n", encoding="utf-8")
    assert Workspace.is_text_file(makefile)


def test_is_text_file_accepts_known_suffixes(tmp_path: Path) -> None:
    """A suffix on the text list is editable without sniffing."""
    notes = tmp_path / "notes.txt"
    notes.write_text("hello\n", encoding="utf-8")
    assert Workspace.is_text_file(notes)


def test_is_text_file_sniffs_extension_less_files(tmp_path: Path) -> None:
    """Sniffing accepts decodable content and rejects undecodable bytes."""
    notes = tmp_path / "notes"
    notes.write_text("hello\n", encoding="utf-8")
    assert Workspace.is_text_file(notes)

    blob = tmp_path / "blob"
    blob.write_bytes(b"\xff\xfe\x00")
    assert not Workspace.is_text_file(blob)


def test_is_text_file_rejects_unknown_suffixes(tmp_path: Path) -> None:
    """A suffix outside the text list is not editable."""
    unknown = tmp_path / "thing.weird"
    unknown.write_text("x\n", encoding="utf-8")
    assert not Workspace.is_text_file(unknown)


# --- traversal robustness (S11: iteration instead of recursion) --------------


def test_walk_files_keeps_depth_first_order_across_directories(
    tmp_path: Path,
) -> None:
    """A directory's whole subtree precedes later siblings, and files sort
    after directories at every level."""
    (tmp_path / "a.py").write_text("x\n", encoding="utf-8")
    first = tmp_path / "dir-b"
    second = tmp_path / "dir-c"
    first.mkdir()
    second.mkdir()
    (first / "z.py").write_text("x\n", encoding="utf-8")
    (second / "m.py").write_text("x\n", encoding="utf-8")

    names = [p.name for p in Workspace(tmp_path).walk_files()]

    assert names == ["z.py", "m.py", "a.py"]


def test_walk_files_survives_a_1500_level_chain(
    ws: Workspace, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A chain 1500 directories deep is walked without RecursionError.

    Real 1500-level trees cannot be created on stock Windows (MAX_PATH), so
    the chain is fed through the same ``Path.iterdir`` seam the unreadable-
    directory tests use; only ``child``/``leaf.txt`` names answer "yes" to
    ``is_dir`` and everything else -- including ``is_symlink`` -- stays a
    plain in-memory Path.
    """
    root = root_of(ws)
    depth = 1500

    def chain_iterdir(path: Path) -> Any:
        if path == root:
            return iter([root / "child"])
        if len(path.relative_to(root).parts) >= depth:
            return iter([path / "leaf.txt"])
        return iter([path / "child"])

    def chain_is_dir(path: Path) -> bool:
        return path == root or path.name == "child"

    def chain_is_symlink(path: Path) -> bool:
        return False

    monkeypatch.setattr("pathlib.Path.iterdir", chain_iterdir)
    monkeypatch.setattr("pathlib.Path.is_dir", chain_is_dir)
    # Production consults is_symlink for every directory child (symlink-loop
    # guard, workspace.py). Left real, it lstats the fake deep path: Windows
    # tolerates the ~9k-character path (32k long-path ceiling) so the leak is
    # Windows-masked, but Linux PATH_MAX (4k) raises Errno 36 partway down
    # the chain (pathlib only ignores ENOENT-class lstat errors).
    monkeypatch.setattr("pathlib.Path.is_symlink", chain_is_symlink)

    files = ws.walk_files()

    assert [p.name for p in files] == ["leaf.txt"]


def test_visible_tree_survives_a_1500_level_chain(
    ws: Workspace, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Flattening a 1500-level expanded chain must not recurse (S11)."""
    root = root_of(ws)
    depth = 1500

    expanded: set[Path] = set()
    node = root
    for _ in range(depth):
        node = node / "child"
        expanded.add(node)

    def chain_list_dir(path: Path) -> list[Entry]:
        if path == root:
            return [Entry(root / "child", "child", True)]
        if len(path.relative_to(root).parts) >= depth:
            return []
        return [Entry(path / "child", "child", True)]

    def chain_is_symlink(path: Path) -> bool:
        return False

    monkeypatch.setattr(ws, "list_dir", chain_list_dir)
    # visible_tree consults is_symlink per expanded entry (S11 loop guard,
    # workspace.py); left real it lstats the fake deep path -- past Linux
    # PATH_MAX that is Errno 36 (Windows-masked: its 32k long-path ceiling
    # fits the whole chain).
    monkeypatch.setattr("pathlib.Path.is_symlink", chain_is_symlink)

    rows = ws.visible_tree(expanded)

    assert len(rows) == depth + 1  # the root plus every chain level
    assert rows[-1][1].name == "child"


def test_visible_tree_does_not_expand_a_symlink_loop(ws: Workspace) -> None:
    """An expanded link to an ancestor is listed once, never descended into.

    Descending would re-list the whole root (the loop target) at ever
    growing depth and recurse forever.
    """
    root = root_of(ws)
    try:
        (root / "loop").symlink_to(root, target_is_directory=True)
    except OSError:
        pytest.skip("creating directory symlinks requires privileges on this OS")

    rows = ws.visible_tree({root / "loop"})

    names = [entry.name for _, entry in rows]
    assert names.count("loop") == 1
    assert names.count("plain.py") == 1
    assert max(depth for depth, _ in rows) == 1
