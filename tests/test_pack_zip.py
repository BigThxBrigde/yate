"""Runtime tests for the post-build zip archive helper (``tools.pack.zip_dist``)."""

from __future__ import annotations

import hashlib
import stat
import zipfile
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
    (stage / "runtime").mkdir()
    (stage / "runtime" / "base.dll").write_bytes(b"dll")
    (stage / "SHA256SUMS.txt").write_text("abc  yate.exe\n", encoding="ascii")
    (stage / "smoke-out.txt").write_text("0.2.18\n", encoding="ascii")
    return stage


def test_archive_stage_when_stage_has_files_writes_top_level_dir_and_excludes_smoke_output(
    stage: Path,
) -> None:
    result = zip_dist.archive_stage(stage, stage.parent)
    with zipfile.ZipFile(result.path) as zf:
        names = zf.namelist()
        assert f"{stage.name}/" in names
        assert f"{stage.name}/yate.exe" in names
        assert f"{stage.name}/runtime/" in names
        assert f"{stage.name}/runtime/base.dll" in names
        assert f"{stage.name}/SHA256SUMS.txt" in names
        assert all("smoke-out.txt" not in name for name in names)
    assert result.path == stage.parent / f"{stage.name}.zip"
    assert result.size == result.path.stat().st_size
    assert result.digest == hashlib.sha256(result.path.read_bytes()).hexdigest()
    assert result.checksum_path == stage.parent / "SHA256SUMS.txt"


def test_archive_stage_when_sums_file_has_other_platform_rows_preserves_them(stage: Path) -> None:
    dist = stage.parent
    (dist / "SHA256SUMS.txt").write_text(
        "h1  yate-0.2.18-linux-x64.zip\nh2  yate-0.2.17-windows-x64.zip\n",
        encoding="ascii",
    )
    result = zip_dist.archive_stage(stage, dist)
    lines = (dist / "SHA256SUMS.txt").read_text(encoding="ascii").splitlines()
    assert "h1  yate-0.2.18-linux-x64.zip" in lines
    assert "h2  yate-0.2.17-windows-x64.zip" in lines
    assert lines[-1] == f"{result.digest}  {result.path.name}"
    assert len(lines) == 3


def test_archive_stage_when_rerun_replaces_zip_and_keeps_single_row(stage: Path) -> None:
    dist = stage.parent
    zip_dist.archive_stage(stage, dist)
    (stage / "runtime" / "extra.dll").write_bytes(b"extra")
    result = zip_dist.archive_stage(stage, dist)
    zips = list(dist.glob("*.zip"))
    assert zips == [dist / f"{stage.name}.zip"]
    with zipfile.ZipFile(result.path) as zf:
        assert f"{stage.name}/runtime/extra.dll" in zf.namelist()
    rows = [
        line
        for line in (dist / "SHA256SUMS.txt").read_text(encoding="ascii").splitlines()
        if line.split()[-1].lstrip("*") == result.path.name
    ]
    assert len(rows) == 1
    assert rows[0].split()[0] == result.digest
    assert (stage / "SHA256SUMS.txt").read_text(encoding="ascii") == "abc  yate.exe\n"


def test_archive_stage_when_posix_mode_flag_set_marks_executable_bit(
    stage: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_mode(path: Path) -> int:
        return 0o755

    monkeypatch.setattr(zip_dist, "_file_mode", fake_mode)
    result = zip_dist.archive_stage(stage, stage.parent, posix=True)
    with zipfile.ZipFile(result.path) as zf:
        info = zf.getinfo(f"{stage.name}/yate.exe")
        assert info.create_system == 3
        assert (info.external_attr >> 16) & 0o777 == 0o755
        top = zf.getinfo(f"{stage.name}/")
        assert (top.external_attr >> 16) & stat.S_IFDIR == stat.S_IFDIR


def test_archive_stage_when_nt_mode_flag_set_marks_only_executables(stage: Path) -> None:
    result = zip_dist.archive_stage(stage, stage.parent, posix=False)
    with zipfile.ZipFile(result.path) as zf:
        exe = (zf.getinfo(f"{stage.name}/yate.exe").external_attr >> 16) & 0o777
        sums = (zf.getinfo(f"{stage.name}/SHA256SUMS.txt").external_attr >> 16) & 0o777
        dll = (zf.getinfo(f"{stage.name}/runtime/base.dll").external_attr >> 16) & 0o777
    assert exe == 0o755
    assert sums == 0o644
    assert dll == 0o644


def test_archive_stage_when_write_fails_cleans_temp_files_and_keeps_old_zip(
    stage: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dist = stage.parent
    archive = dist / f"{stage.name}.zip"
    archive.write_bytes(b"old")
    (dist / "SHA256SUMS.txt").write_text("oldhash  old.zip\n", encoding="ascii")

    def fail(self: zipfile.ZipFile, info: object, data: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(zipfile.ZipFile, "writestr", fail)
    with pytest.raises(OSError, match="disk full"):
        zip_dist.archive_stage(stage, dist)
    assert archive.read_bytes() == b"old"
    assert (dist / "SHA256SUMS.txt").read_text(encoding="ascii") == "oldhash  old.zip\n"
    assert list(dist.glob("*.tmp")) == []
    assert list(dist.glob(".*")) == []


def test_archive_stage_when_stage_missing_raises_zip_dist_error(tmp_path: Path) -> None:
    dist = tmp_path / "release"
    dist.mkdir()
    with pytest.raises(zip_dist.ZipDistError, match="stage directory not found"):
        zip_dist.archive_stage(tmp_path / "missing-stage", dist)
    assert list(dist.glob("*.zip")) == []
    assert list(dist.glob("*.tmp")) == []


def test_archive_stage_when_stage_empty_raises_zip_dist_error(tmp_path: Path) -> None:
    dist = tmp_path / "release"
    stage = dist / "empty-stage"
    stage.mkdir(parents=True)
    with pytest.raises(zip_dist.ZipDistError, match="no files"):
        zip_dist.archive_stage(stage, dist)


def test_archive_stage_when_archived_zip_integrity_is_verified(stage: Path) -> None:
    result = zip_dist.archive_stage(stage, stage.parent)
    with zipfile.ZipFile(result.path) as zf:
        assert zf.testzip() is None


def test_main_when_invoked_with_stage_prints_path_and_digest_and_returns_zero(
    stage: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = zip_dist.main(["--stage", str(stage), "--dist-root", str(stage.parent)])
    out = capsys.readouterr()
    assert code == 0
    assert "ZIP ->" in out.out
    assert f"{stage.name}.zip" in out.out
    assert "MB" in out.out
    assert f"SHA256 {stage.name}.zip:" in out.out
    sums = (stage.parent / "SHA256SUMS.txt").read_text(encoding="ascii")
    digest = sums.split()[0]
    assert digest in out.out
    assert out.err == ""


def test_main_when_archive_fails_prints_readable_error_and_returns_one(
    stage: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(stage_path: Path, dist_root: Path, *, posix: bool | None = None) -> object:
        raise zip_dist.ZipDistError("boom")

    monkeypatch.setattr(zip_dist, "archive_stage", fail)
    code = zip_dist.main(["--stage", str(stage), "--dist-root", str(stage.parent)])
    out = capsys.readouterr()
    assert code == 1
    assert "error: zip archive failed: boom" in out.err
    assert out.out == ""


def test_main_when_arguments_missing_exits_two() -> None:
    with pytest.raises(SystemExit) as exc_info:
        zip_dist.main([])
    assert exc_info.value.code == 2
