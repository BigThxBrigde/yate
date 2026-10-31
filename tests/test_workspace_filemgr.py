"""Unit tests for the file-manager support surface of Workspace.

Covers the L0 additions from the file-manager plan: ``EntryStat`` /
``Workspace.stat_entry`` metadata snapshots, ``human_size`` formatting,
the Windows drive-letter virtual level (``list_drives``), and
cross-directory copy / move with explicit existing-target rejection.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from yate.services.workspace import Workspace, human_size


def make_source_file(directory: Path) -> Path:
    """Create ``file.txt`` with known content inside *directory*."""
    target = directory / "file.txt"
    target.write_text("hello")
    return target


def test_stat_entry_returns_size_mtime_and_posix_fields(tmp_path: Path) -> None:
    """A 2048-byte file reports its size, a live mtime, and owner fields."""
    target = tmp_path / "blob.bin"
    target.write_bytes(b"x" * 2048)
    st = Workspace().stat_entry(target)
    assert st.size == 2048
    assert st.mtime_ns > 0
    if sys.platform == "win32":
        assert st.owner is None
        assert st.group is None
    else:
        # The file was just created by this process, so pwd/grp resolve.
        assert isinstance(st.owner, str)
        assert isinstance(st.group, str)


def test_stat_entry_dir_reports_zero_size(tmp_path: Path) -> None:
    """A directory reports size 0 (the ls convention) and a live nlink."""
    st = Workspace().stat_entry(tmp_path)
    assert st.size == 0
    if sys.platform == "win32":
        # Windows stat reports nlink == 1 for directories (measured on
        # CPython nt); the >= 2 hard-link convention is POSIX-only.
        assert st.nlink >= 1
    else:
        assert st.nlink >= 2


def test_stat_entry_missing_path_degrades_to_zeroes(tmp_path: Path) -> None:
    """A vanished entry degrades to an all-zero stat instead of raising."""
    st = Workspace().stat_entry(tmp_path / "gone.txt")
    assert st.size == 0
    assert st.mtime_ns == 0


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (0, "0"),
        (1023, "1023"),
        (1024, "1K"),
        (1536, "1.5K"),
        (2621440, "2.5M"),
        (188743680, "180M"),
        (int(1.2 * 1024**3), "1.2G"),
    ],
)
def test_human_size_formats_binary_units(raw: int, expected: str) -> None:
    """Byte counts format in 1024-based units with trimmed decimals."""
    assert human_size(raw) == expected


def test_list_drives_empty_on_posix_and_sorted_on_windows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The drive level is empty on POSIX and letter-sorted on Windows."""
    monkeypatch.setattr(sys, "platform", "posix")
    assert Workspace().list_drives() == []
    monkeypatch.setattr(sys, "platform", "win32")
    drives = Workspace().list_drives()
    letters = [entry.name for entry in drives]
    assert letters == sorted(letters)
    assert all(entry.is_dir for entry in drives)


def test_copy_entry_copies_file_and_dir_recursively(tmp_path: Path) -> None:
    """copy_entry copies files (copy2) and directories (copytree) and
    rejects an already-existing target."""
    ws = Workspace()
    src_dir = tmp_path / "dir_a"
    src_dir.mkdir()
    source = make_source_file(src_dir)
    dest_dir = tmp_path / "dir_b"
    dest_dir.mkdir()

    copied_file = ws.copy_entry(source, dest_dir)
    assert copied_file == dest_dir / "file.txt"
    assert copied_file.read_text() == "hello"
    assert source.exists()  # the source is preserved

    copied_dir = ws.copy_entry(src_dir, dest_dir)
    assert (copied_dir / "file.txt").read_text() == "hello"

    with pytest.raises(FileExistsError):
        ws.copy_entry(source, dest_dir)


def test_move_entry_renames_into_dir_and_rejects_existing(tmp_path: Path) -> None:
    """move_entry relocates the entry (source disappears) and refuses to
    overwrite an existing target, leaving the source in place."""
    ws = Workspace()
    source = make_source_file(tmp_path)
    dest_dir = tmp_path / "dir_b"
    dest_dir.mkdir()

    moved = ws.move_entry(source, dest_dir)
    assert moved == dest_dir / "file.txt"
    assert moved.read_text() == "hello"
    assert not source.exists()

    source.write_text("again")
    with pytest.raises(FileExistsError):
        ws.move_entry(source, dest_dir)
    assert source.exists()  # the source is untouched on rejection


def test_copy_move_reject_escape_via_existing_target(tmp_path: Path) -> None:
    """A pre-existing same-named target blocks both copy and move."""
    ws = Workspace()
    src_dir = tmp_path / "dir_a"
    src_dir.mkdir()
    source = make_source_file(src_dir)
    dest_dir = tmp_path / "dir_b"
    dest_dir.mkdir()
    (dest_dir / "file.txt").write_text("keep me")

    with pytest.raises(FileExistsError):
        ws.copy_entry(source, dest_dir)
    with pytest.raises(FileExistsError):
        ws.move_entry(source, dest_dir)
    assert (dest_dir / "file.txt").read_text() == "keep me"
