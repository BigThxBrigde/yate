"""Tests for the on-disk resource-location authority (yate.paths)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from yate import logs, paths


# --- user home --------------------------------------------------------------


def test_yate_home_under_os_home(isolated_home: Path) -> None:
    # The per-user root is a single authoritative spelling under the OS home
    # (the autouse ``isolated_home`` fixture patches Path.home to a temp dir).
    assert paths.yate_home() == Path.home() / ".yate"
    # The directory itself is not created by the resolver.
    assert not paths.yate_home().exists()


def test_logs_dirs_restrict_on_posix(
    monkeypatch: pytest.MonkeyPatch, isolated_home: Path
) -> None:
    if os.name != "posix":
        pytest.skip("POSIX permission bits only")
    assert logs.crash_data_dir().stat().st_mode & 0o777 == 0o700
    assert logs.logs_dir().stat().st_mode & 0o777 == 0o700


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
    # csharp highlighting is built-in now: the bundled script is gone
    assert "csharp_highlight.py" not in names
    assert names == {"__init__.py", "python_lsp.py"}
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
