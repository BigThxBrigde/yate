"""Regression tests for the icon builder's atomic write (m16).

Pins review finding m16 only: ``pack/yate.ico`` is a git-tracked file and
must be written through a same-directory temporary file + ``os.replace`` so
a mid-save failure never leaves a truncated icon (the pattern
``tools/pack/zip_dist.py`` already uses).  A fake Pillow module injects the
failure at ``image.save`` -- after a non-atomic writer has already touched
the target -- so the old implementation is genuinely red.
"""

from __future__ import annotations

from contextlib import nullcontext
from pathlib import Path
from typing import Any

import pytest

from tools.pack import icon

PAYLOAD = b"complete-icon-bytes"


class _FakeImage:
    """Minimal Pillow-shaped image with a controllable mid-save failure."""

    width = 64
    height = 32
    size = (64, 32)

    def __init__(self, fail: bool = False) -> None:
        self.fail = fail

    def crop(self, box: tuple[int, int, int, int]) -> _FakeImage:
        return _FakeImage(self.fail)

    def load(self) -> None:
        return None

    def save(self, path: Path, **kwargs: object) -> None:
        Path(path).write_bytes(b"partial")
        if self.fail:
            raise OSError("save blew up mid-write")
        Path(path).write_bytes(PAYLOAD)


class _FakePillow:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail

    def open(self, source: Path) -> Any:
        return nullcontext(_FakeImage(self.fail))


def _install_fake_pillow(monkeypatch: pytest.MonkeyPatch, fail: bool = False) -> None:
    def fake_import(name: str) -> Any:
        return _FakePillow(fail)

    monkeypatch.setattr(icon.importlib, "import_module", fake_import)


@pytest.fixture
def source(tmp_path: Path) -> Path:
    """A stub source image; the fake Pillow never parses its bytes."""
    path = tmp_path / "yate.jpg"
    path.write_bytes(b"not-a-real-jpeg")
    return path


def test_build_icon_writes_the_target_through_a_temporary_file(
    tmp_path: Path, source: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The happy path lands a complete icon at *target* with no temp residue."""
    _install_fake_pillow(monkeypatch)
    target = tmp_path / "out" / "yate.ico"

    result = icon.build_icon(source, target, sizes=(16, 32))

    assert result == target
    assert target.read_bytes() == PAYLOAD
    assert [path.name for path in target.parent.iterdir()] == ["yate.ico"]


def test_mid_save_failure_leaves_no_truncated_target(
    tmp_path: Path, source: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failure inside save leaves the target absent, not truncated."""
    _install_fake_pillow(monkeypatch, fail=True)
    target = tmp_path / "out" / "yate.ico"

    with pytest.raises(OSError, match="mid-write"):
        icon.build_icon(source, target, sizes=(16,))

    assert not target.exists()
    assert not any(target.parent.iterdir())  # temp file cleaned up


def test_mid_save_failure_keeps_an_existing_target_intact(
    tmp_path: Path, source: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed rebuild must not damage the previously committed icon."""
    _install_fake_pillow(monkeypatch)
    target = tmp_path / "out" / "yate.ico"
    icon.build_icon(source, target, sizes=(16,))
    committed = target.read_bytes()
    _install_fake_pillow(monkeypatch, fail=True)

    with pytest.raises(OSError):
        icon.build_icon(source, target, sizes=(16,))

    assert target.read_bytes() == committed
    assert [path.name for path in target.parent.iterdir()] == ["yate.ico"]
