"""Unit tests for the workspace trust store (yate.services.trust)."""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from yate.services.trust import (
    is_trusted,
    load_trusted_workspaces,
    trust_workspace,
)


def test_missing_store_yields_no_trusted_workspaces(tmp_path: Path) -> None:
    assert load_trusted_workspaces(tmp_path / "trusted_workspaces") == set()
    assert not is_trusted(tmp_path, tmp_path / "trusted_workspaces")


def test_trust_workspace_roundtrip(tmp_path: Path) -> None:
    store = tmp_path / "store.txt"
    root = tmp_path / "repo"
    root.mkdir()
    assert not is_trusted(root, store)
    assert trust_workspace(root, store) is True
    assert is_trusted(root, store)
    # a .-spelling of the same directory resolves to the same root
    assert is_trusted(root / ".", store)


def test_trust_workspace_is_idempotent(tmp_path: Path) -> None:
    store = tmp_path / "store.txt"
    trust_workspace(tmp_path, store)
    trust_workspace(tmp_path, store)
    assert len(store.read_text(encoding="utf-8").splitlines()) == 1


def test_trust_refuses_a_symlinked_root(tmp_path: Path) -> None:
    """S39: a symlinked root is never persisted, so redirecting the link
    cannot inherit its trust -- the target directory must be trusted with
    its own ``:trust`` call."""
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    try:
        link.symlink_to(real, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks are not supported on this platform")
    store = tmp_path / "store.txt"

    trust_workspace(link, store)  # must be refused without raising
    assert trust_workspace(link, store) is False  # refused reports failure

    assert not store.exists()  # nothing was persisted, not even the file
    assert not is_trusted(real, store)
    # The resolved (link-free) directory itself is still trustable: already
    # trusted entries and honest roots are unaffected by the guard.
    trust_workspace(real, store)
    assert is_trusted(real, store)


def test_comments_and_blank_lines_are_skipped(tmp_path: Path) -> None:
    store = tmp_path / "store.txt"
    root = tmp_path / "repo"
    root.mkdir()
    store.write_text(
        f"# trusted by :trust\n\n{root}\n", encoding="utf-8"
    )
    assert load_trusted_workspaces(store) == {root.resolve()}


def test_load_tolerates_invalid_utf8_bytes(tmp_path: Path) -> None:
    """A corrupted store must not break startup: invalid bytes decode to
    U+FFFD instead of raising, and the valid entries still load."""
    store = tmp_path / "trusted_workspaces"
    real = tmp_path / "repo"
    real.mkdir()
    # the leading garbage line is not valid UTF-8; the second line is
    store.write_bytes(b"\xff\xfe/shared\n" + str(real).encode("utf-8") + b"\n")

    trusted = load_trusted_workspaces(store)  # must not raise
    # the surrounding valid entry survives the undecodable line
    assert real.resolve() in trusted
    assert is_trusted(real, store) is True
    # the mangled line decodes to U+FFFD text, a path unrelated to *real*:
    # it grants trust for nobody the caller actually opened
    assert Path("\ufffd\ufffd/shared").resolve() not in {real.resolve()}


@pytest.mark.skipif(os.name != "posix", reason="POSIX permission bits only")
def test_trust_workspace_creates_owner_only_directory(tmp_path: Path) -> None:
    """The first :trust creates the store directory owner-only so another
    user cannot inject trusted workspace entries."""
    store = tmp_path / "nested" / ".yate" / "trusted_workspaces"
    root = tmp_path / "repo"
    root.mkdir()
    assert not store.parent.exists()

    trust_workspace(root, store)

    assert store.parent.is_dir()
    assert stat.S_IMODE(store.parent.stat().st_mode) == 0o700
    assert is_trusted(root, store)
