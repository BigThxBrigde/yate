"""Regression tests for the icon builder's atomic write (m16).

Pins review finding m16 only: ``pack/yate.ico`` is a git-tracked file and
must be written through a same-directory temporary file + ``os.replace`` so
a mid-save failure never leaves a truncated icon (the pattern
``tools/pack/zip_dist.py`` already uses).
"""

# pyright: reportMissingImports=false

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tools.pack import icon

pytest.importorskip("PIL", reason="Pillow is an optional [build] dependency")


@pytest.fixture
def source(tmp_path: Path) -> Path:
    """A small non-square JPEG so the crop path is exercised too."""
    image_module = pytest.importorskip("PIL")
    path = tmp_path / "yate.jpg"
    image_module.Image.new("RGB", (64, 32), "red").save(path, format="JPEG")
    return path


def test_build_icon_writes_the_target_through_a_temporary_file(
    tmp_path: Path, source: Path
) -> None:
    """The happy path lands a multi-resolution icon at *target*."""
    target = tmp_path / "out" / "yate.ico"

    result = icon.build_icon(source, target, sizes=(16, 32))

    assert result == target
    assert target.is_file()
    # No temporary files survive the run.
    assert [path.name for path in target.parent.iterdir()] == ["yate.ico"]


def test_build_icon_failure_leaves_no_truncated_target(
    tmp_path: Path, source: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failure inside the write leaves the target absent, not truncated."""

    def failing_square(image: Any) -> Any:
        raise OSError("save blew up mid-write")

    monkeypatch.setattr(icon, "square", failing_square)
    target = tmp_path / "out" / "yate.ico"

    with pytest.raises(OSError, match="mid-write"):
        icon.build_icon(source, target, sizes=(16,))

    assert not target.exists()
    assert not any(target.parent.iterdir())  # temp file cleaned up


def test_build_icon_failure_keeps_an_existing_target_intact(
    tmp_path: Path, source: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed rebuild must not damage the previously committed icon."""
    target = tmp_path / "out" / "yate.ico"
    icon.build_icon(source, target, sizes=(16,))
    committed = target.read_bytes()

    def failing_square(image: Any) -> Any:
        raise OSError("save blew up mid-write")

    monkeypatch.setattr(icon, "square", failing_square)

    with pytest.raises(OSError):
        icon.build_icon(source, target, sizes=(16,))

    assert target.read_bytes() == committed
