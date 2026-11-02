"""Tests for the file manager pure model (plan-c)."""

from __future__ import annotations

import os
import time
from pathlib import Path
from stat import filemode

from yate.editor_components.file_manager.model import (
    SORT_CYCLE,
    build_row_text,
    count_children,
    filter_entries,
    format_status,
    next_sort,
    parent_and_siblings,
    sort_entries,
)
from yate.editor_components.icons import SETI_COLORS, icon_for_path
from yate.services.workspace import Entry, EntryStat, Workspace, human_size

_MTIME_FORMAT = "%a %b %d %H:%M:%S %Y"
_MID_DOT = "\u00b7"


def _stat(path: Path, *, size: int = 0, mtime_ns: int = 0, is_dir: bool = False) -> EntryStat:
    """Build a frozen EntryStat with plausible mode bits."""
    return EntryStat(
        path=path,
        size=size,
        mtime_ns=mtime_ns,
        mode=0o040755 if is_dir else 0o100644,
        nlink=1,
        owner=None,
        group=None,
    )


def _tree(tmp_path: Path) -> tuple[list[Entry], dict[Path, EntryStat]]:
    """Five mixed entries (2 dirs + 3 files) with hand-made stats."""
    d_a = tmp_path / "dir_a"
    d_b = tmp_path / "dir_b"
    f_a = tmp_path / "a.py"
    f_m = tmp_path / "m.txt"
    f_z = tmp_path / "z.log"
    entries = [
        Entry(f_z, "z.log", False),
        Entry(d_b, "dir_b", True),
        Entry(f_a, "a.py", False),
        Entry(d_a, "dir_a", True),
        Entry(f_m, "m.txt", False),
    ]
    stats = {
        d_a: _stat(d_a, is_dir=True),
        d_b: _stat(d_b, is_dir=True),
        f_a: _stat(f_a, size=30, mtime_ns=300),
        f_m: _stat(f_m, size=1, mtime_ns=200),
        f_z: _stat(f_z, size=3, mtime_ns=100),
    }
    return entries, stats


def test_sort_entries_dirs_first_and_key_cycle(tmp_path: Path) -> None:
    entries, stats = _tree(tmp_path)
    by_name = sort_entries(entries, stats, "name")
    assert [e.name for e in by_name] == ["dir_a", "dir_b", "a.py", "m.txt", "z.log"]
    by_size = sort_entries(entries, stats, "size")
    assert [e.name for e in by_size if e.is_dir] == ["dir_a", "dir_b"]
    assert [e.name for e in by_size if not e.is_dir] == ["m.txt", "z.log", "a.py"]
    by_mtime = sort_entries(entries, stats, "mtime")
    assert [e.name for e in by_mtime if e.is_dir] == ["dir_a", "dir_b"]
    assert [e.name for e in by_mtime if not e.is_dir] == ["z.log", "m.txt", "a.py"]
    assert next_sort("name") == "size"
    assert next_sort("size") == "mtime"
    assert next_sort("mtime") == "name"
    assert SORT_CYCLE == ("name", "size", "mtime")


def test_sort_entries_descending_flips_files_only(tmp_path: Path) -> None:
    entries, stats = _tree(tmp_path)
    desc = sort_entries(entries, stats, "name", descending=True)
    assert [e.name for e in desc if e.is_dir] == ["dir_a", "dir_b"]
    assert [e.name for e in desc if not e.is_dir] == ["z.log", "m.txt", "a.py"]
    desc_size = sort_entries(entries, stats, "size", descending=True)
    assert [e.name for e in desc_size if e.is_dir] == ["dir_a", "dir_b"]
    assert [e.name for e in desc_size if not e.is_dir] == ["a.py", "z.log", "m.txt"]


def test_filter_entries_substring_case_insensitive(tmp_path: Path) -> None:
    entries = [
        Entry(tmp_path / "a.py", "a.py", False),
        Entry(tmp_path / "b.txt", "b.txt", False),
    ]
    assert [e.name for e in filter_entries(entries, "PY")] == ["a.py"]
    assert [e.name for e in filter_entries(entries, ".T")] == ["b.txt"]
    assert [e.name for e in filter_entries(entries, "nope")] == []
    assert filter_entries(entries, "") == entries


def test_build_row_text_marks_icon_and_size_columns(tmp_path: Path) -> None:
    accent = "#ff0000"
    d = tmp_path / "sub"
    f = tmp_path / "a.py"
    dir_row = build_row_text(
        Entry(d, "sub", True), None, accent, False,
        dir_child_count=None, sort_key="name",
    )
    assert dir_row.plain == f"{icon_for_path('sub', True)} sub"
    assert dir_row.spans[0].style == accent
    assert dir_row.spans[1].style == accent

    file_row = build_row_text(
        Entry(f, "a.py", False), _stat(f, size=4096), accent, False,
        dir_child_count=None, sort_key="name",
    )
    assert file_row.plain == f"{icon_for_path('a.py', False)} a.py {human_size(4096).rjust(6)}"
    assert file_row.plain[-6:] == human_size(4096).rjust(6)
    assert file_row.spans[0].style == SETI_COLORS["blue"]

    marked_row = build_row_text(
        Entry(f, "a.py", False), _stat(f, size=1), accent, True,
        dir_child_count=None, sort_key="name",
    )
    assert marked_row.plain.startswith("* ")


def test_build_row_text_dir_badge_counts_children(tmp_path: Path) -> None:
    accent = "#ffffff"
    d = tmp_path / "sub"
    d.mkdir()
    for i in range(3):
        (d / f"f{i}.txt").write_text("", encoding="utf-8")
    row = build_row_text(
        Entry(d, "sub", True), None, accent, False,
        dir_child_count=count_children(d), sort_key="name",
    )
    assert "(3)" in row.plain
    assert "(999+" not in row.plain

    big = tmp_path / "big"
    big.mkdir()
    for i in range(1000):
        (big / f"{i:04d}").touch()
    assert count_children(big) == 1000
    capped_row = build_row_text(
        Entry(big, "big", True), None, accent, False,
        dir_child_count=count_children(big), sort_key="name",
    )
    assert "(999+)" in capped_row.plain

    omitted = build_row_text(
        Entry(d, "sub", True), None, accent, False,
        dir_child_count=None, sort_key="name",
    )
    assert "(" not in omitted.plain


def test_count_children_missing_dir_returns_minus_one(tmp_path: Path) -> None:
    assert count_children(tmp_path / "missing") == -1


def test_format_status_matches_lf_layout(tmp_path: Path) -> None:
    f = tmp_path / "a.txt"
    f.write_text("x" * 72, encoding="utf-8")
    ts = 1740705721
    os.utime(f, (ts, ts))
    st = Workspace(tmp_path).stat_entry(f)
    owner = st.owner if st.owner is not None else "-"
    group = st.group if st.group is not None else "-"
    mtime_text = time.strftime(_MTIME_FORMAT, time.localtime(ts))
    expected = (
        f"{filemode(st.mode)} {st.nlink} {owner} {group} "
        f"72B {mtime_text} {_MID_DOT} 2/8 {_MID_DOT} name asc"
    )
    assert format_status(st, 1, 8, "name", False, None, 0) == expected

    hand = EntryStat(
        path=f,
        size=72,
        mtime_ns=ts * 1_000_000_000,
        mode=0o100664,
        nlink=1,
        owner="alice",
        group="devteam",
    )
    expected_hand = (
        f"-rw-rw-r-- 1 alice devteam 72B {mtime_text} "
        f"{_MID_DOT} 2/8 {_MID_DOT} name asc"
    )
    assert format_status(hand, 1, 8, "name", False, None, 0) == expected_hand

    decorated = format_status(hand, 0, 8, "size", True, "ab", 3)
    assert decorated.startswith("-rw-rw-r-- 1 alice devteam 72B ")
    assert (
        f"{_MID_DOT} 1/8 {_MID_DOT} size desc {_MID_DOT} filter: ab "
        f"{_MID_DOT} marked: 3" in decorated
    )

    bare = format_status(hand, 0, 8, "name", False, None, 0)
    assert bare.endswith(f"{_MID_DOT} name asc")
    assert "filter" not in bare
    assert "marked" not in bare

    degraded = format_status(None, 0, 8, "name", False, None, 0)
    assert degraded.endswith(f"{_MID_DOT} 1/8 {_MID_DOT} name asc")


def test_parent_and_siblings_returns_parent_listing(tmp_path: Path) -> None:
    """Left-pane model: the parent directory plus its listing."""
    ws = Workspace(tmp_path)
    (tmp_path / "kid.txt").write_text("", encoding="utf-8")
    parent, siblings = parent_and_siblings(tmp_path, ws)
    assert parent == tmp_path.parent
    assert any(e.path == tmp_path for e in siblings)
