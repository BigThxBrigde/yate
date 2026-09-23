"""Unit tests for the workspace trust store (yate.services.trust)."""

from __future__ import annotations

from pathlib import Path

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
    trust_workspace(root, store)
    assert is_trusted(root, store)
    # a .-spelling of the same directory resolves to the same root
    assert is_trusted(root / ".", store)


def test_trust_workspace_is_idempotent(tmp_path: Path) -> None:
    store = tmp_path / "store.txt"
    trust_workspace(tmp_path, store)
    trust_workspace(tmp_path, store)
    assert len(store.read_text(encoding="utf-8").splitlines()) == 1


def test_comments_and_blank_lines_are_skipped(tmp_path: Path) -> None:
    store = tmp_path / "store.txt"
    root = tmp_path / "repo"
    root.mkdir()
    store.write_text(
        f"# trusted by :trust\n\n{root}\n", encoding="utf-8"
    )
    assert load_trusted_workspaces(store) == {root.resolve()}
