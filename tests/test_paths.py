"""Tests for the on-disk resource-location authority (yate.paths)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from yate import paths


# --- package root -----------------------------------------------------------


def test_package_root_is_the_yate_package() -> None:
    root = paths.package_root()
    assert root.is_dir(), root
    assert (root / "paths.py").resolve() == Path(paths.__file__).resolve()


def test_frozen_package_root_uses_meipass(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # A PyInstaller process sets sys.frozen and sys._MEIPASS; the bundled
    # data is collected under <_MEIPASS>/yate.
    bundle_root = tmp_path
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle_root), raising=False)
    assert paths.package_root() == bundle_root / "yate"
    # extensions dir is derived from the frozen root too
    assert paths.bundled_extensions_dir() == bundle_root / "yate" / "extensions"


def test_frozen_without_usable_meipass_falls_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    normal_root = Path(paths.__file__).resolve().parent
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", 123, raising=False)
    assert paths.package_root() == normal_root


# --- shipped data -----------------------------------------------------------


def test_bundled_extensions_ship_inside_package() -> None:
    directory = paths.bundled_extensions_dir()
    assert directory.is_dir(), directory
    names = {p.name for p in directory.glob("*.py")}
    assert "__init__.py" in names
    assert "python_lsp.py" in names
    assert "csharp_highlight.py" in names
    # the example template must not be auto-loaded as a script
    assert (directory / "example_ext.py.example").is_file()
    assert "example_ext.py" not in names


def test_shipped_data_presence_contract() -> None:
    # Bilingual guides and the rc template are plain shipped data (no code
    # helper needed); pin their presence so a packaging change cannot
    # silently drop them.
    root = paths.package_root()
    for guide in ("extensions", "lsp", "themes", "yaterc"):
        assert (root / "docs" / f"{guide}.zh.md").is_file()
        assert (root / "docs" / f"{guide}.en.md").is_file()
    assert (root / "yaterc.example").is_file()
