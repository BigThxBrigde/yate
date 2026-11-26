"""Regression tests for the ``zip_dist`` swap/rollback failure handling (m14).

``tests/test_pack_zip.py`` owns the general archive coverage; this module
pins review finding m14 only: a failed rollback must not silently delete the
backup of the previous archive, and best-effort cleanup failures must be
reported on stderr instead of passing silently.
"""

# zip_dist's swap internals are exercised through the same monkeypatch
# seams tests/test_pack_zip.py already uses (module-private but contractual).
# pyright: reportPrivateUsage=false

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from tools.pack import zip_dist


@pytest.fixture
def stage(tmp_path: Path) -> Path:
    """Build a minimal ``--dist`` stage directory under *tmp_path*."""
    dist_root = tmp_path / "release"
    stage = dist_root / "yate-0.2.18-windows-x64"
    stage.mkdir(parents=True)
    (stage / "yate.exe").write_bytes(b"exe")
    (stage / "SHA256SUMS.txt").write_text("abc  yate.exe\n", encoding="ascii")
    return stage


@pytest.fixture
def old_archive(stage: Path) -> Iterator[Path]:
    """The dist root with a first successful build (archive already exists)."""
    zip_dist.archive_stage(stage, stage.parent)
    yield stage.parent


def test_archive_stage_when_rollback_fails_keeps_backup(
    stage: Path, old_archive: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A double failure keeps the old-package backup on disk (m14)."""
    dist = old_archive
    archive = dist / f"{stage.name}.zip"
    archive_bytes = archive.read_bytes()
    real_replace = os.replace

    def failing_replace(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
        # Both the swap and its rollback target the archive: fail them all.
        if Path(dst) == archive:
            raise OSError("replace failed")
        real_replace(src, dst)

    monkeypatch.setattr(zip_dist.os, "replace", failing_replace)

    with pytest.raises(OSError, match="replace failed"):
        zip_dist.archive_stage(stage, dist)

    backups = list(dist.glob("*.zip.bak"))
    assert len(backups) == 1
    assert backups[0].read_bytes() == archive_bytes
    # The failed swap never replaced the published archive.
    assert archive.read_bytes() == archive_bytes


def test_archive_stage_when_rollback_fails_reports_on_stderr(
    stage: Path,
    old_archive: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The rollback failure explains on stderr that the backup is kept."""
    dist = old_archive
    archive = dist / f"{stage.name}.zip"
    real_replace = os.replace

    def failing_replace(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
        if Path(dst) == archive:
            raise OSError("replace failed")
        real_replace(src, dst)

    monkeypatch.setattr(zip_dist.os, "replace", failing_replace)

    with pytest.raises(OSError):
        zip_dist.archive_stage(stage, dist)

    err = capsys.readouterr().err
    assert "rollback failed" in err
    assert "backup" in err


def test_archive_stage_when_cleanup_fails_reports_and_keeps_result(
    stage: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A busy temporary file is reported on stderr but the archive still lands."""
    dist = stage.parent
    real_unlink = Path.unlink

    def busy_unlink(self: Path, missing_ok: bool = False) -> None:
        if self.name.startswith(f".{stage.name}"):
            raise OSError("file busy")
        real_unlink(self, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", busy_unlink)

    result = zip_dist.archive_stage(stage, dist)

    assert result.path.is_file()
    err = capsys.readouterr().err
    assert "could not remove temporary file" in err
