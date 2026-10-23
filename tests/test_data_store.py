"""Path-safety and atomic-write tests for :mod:`yate.services.data_store`.

The autouse ``isolated_home`` fixture in ``conftest.py`` points ``Path.home``
at a per-test temporary directory, so every write here lands in a throwaway
``~/.yate/data`` and never touches the real user directory.
"""

# _has_drive_prefix is the module's private portable-drive seam (pinned
# directly by one test below, same precedent as tests/test_diagnostics.py).
# pyright: reportPrivateUsage=false

from __future__ import annotations

from pathlib import Path

import pytest

from yate.services import data_store
from yate.services.data_store import _has_drive_prefix


def test_has_drive_prefix_is_platform_independent() -> None:
    """Direct test of the portable drive check, no pathlib involved.

    On Windows pathlib itself parses ``X:`` into ``Path.drive``, so the
    portable branch in ``resolve`` is unreachable there; the helper must
    therefore be pinned directly, cross-platform, on raw strings.
    """
    assert _has_drive_prefix("C:foo")
    assert _has_drive_prefix("a:b")
    assert not _has_drive_prefix("games")
    assert not _has_drive_prefix("")


def test_read_missing_file_returns_none() -> None:
    """A document nobody wrote yet reads as ``None``, not an error."""
    assert data_store.read_text("games/snake.json") is None


def test_write_then_read_roundtrip_creates_parents() -> None:
    """Writing creates missing directories and round-trips UTF-8 text."""
    text = '{"player": "\u73a9\u5bb6 \U0001f40d"}'
    data_store.write_text("games/snake.json", text)

    assert data_store.read_text("games/snake.json") == text
    assert (data_store.data_root() / "games").is_dir()


def test_write_is_atomic_and_leaves_no_temp_file() -> None:
    """Two writes leave exactly the target document, no temporary siblings."""
    data_store.write_text("games/a.json", "one")
    data_store.write_text("games/a.json", "two")

    directory = data_store.data_root() / "games"
    assert [entry.name for entry in directory.iterdir()] == ["a.json"]
    assert data_store.read_text("games/a.json") == "two"


def test_write_falls_back_to_a_direct_write_when_rename_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A locked target (Windows AV/sync) degrades to a direct write."""
    data_store.write_text("games/locked.json", "one")

    def locked(self: Path, target: Path) -> None:
        raise OSError("target is locked")

    monkeypatch.setattr(Path, "replace", locked)
    data_store.write_text("games/locked.json", "two")

    assert data_store.read_text("games/locked.json") == "two"
    directory = data_store.data_root() / "games"
    assert [entry.name for entry in directory.iterdir()] == ["locked.json"]


def test_remove_reports_whether_the_file_existed() -> None:
    """``remove`` is a boolean report, idempotent for a missing document."""
    data_store.write_text("games/b.json", "x")

    assert data_store.remove("games/b.json") is True
    assert data_store.remove("games/b.json") is False


def test_names_lists_files_sorted_and_tolerates_missing_dir() -> None:
    """Listing is sorted and a missing directory means "nothing there"."""
    data_store.write_text("games/b.json", "b")
    data_store.write_text("games/a.json", "a")

    assert data_store.names("games") == ["a.json", "b.json"]
    assert data_store.names("missing") == []


@pytest.mark.parametrize(
    "name",
    [
        "",
        "/etc/passwd",
        "../escape.json",
        "games/../../escape.json",
        "C:\\Windows\\evil.json",
        "C:/Windows/evil.json",
        "games\\evil.json",
        "C:foo/bar",
        "d:relative.json",
    ],
)
def test_rejects_absolute_and_traversal_names(name: str) -> None:
    """Every escaping or empty name is rejected before touching the disk.

    The Windows-flavoured names must be rejected on every platform: on POSIX
    a backslash is a legal filename character and a ``C:/`` prefix an
    ordinary relative directory, so only explicit checks catch them.  The
    drive-relative forms ("C:foo/bar") keep the drive inside the first path
    part, so they need the portable drive-prefix check as well.
    """
    with pytest.raises(ValueError):
        data_store.write_text(name, "x")

    with pytest.raises(ValueError):
        data_store.read_text(name)


def test_resolved_paths_stay_below_the_data_root() -> None:
    """A nested relative name resolves inside ``~/.yate/data``."""
    resolved = data_store.resolve("games/deep/nethack.json")

    assert resolved.is_relative_to(data_store.data_root())
    assert resolved.name == "nethack.json"


def test_data_root_points_at_the_yate_data_directory() -> None:
    """The root is ``~/.yate/data`` -- the same tree the logs live under."""
    root = data_store.data_root()

    assert root == Path.home() / ".yate" / "data"
