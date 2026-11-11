"""Runtime tests for the post-build zip archive helper (``tools.pack.zip_dist``)."""

from __future__ import annotations

import hashlib
import os
import stat
import time
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


def test_archive_stage_when_checksum_rows_contain_non_ascii_bytes_preserves_them(
    stage: Path,
) -> None:
    dist = stage.parent
    (dist / "SHA256SUMS.txt").write_bytes(b"caf\xe9  other.zip\nold  yate-0.2.18-windows-x64.zip\n")
    result = zip_dist.archive_stage(stage, dist)
    content = (dist / "SHA256SUMS.txt").read_bytes()
    assert b"caf\xe9  other.zip" in content
    rows = [line for line in content.splitlines() if b"yate-0.2.18-windows-x64.zip" in line]
    assert rows == [f"{result.digest}  yate-0.2.18-windows-x64.zip".encode("ascii")]
    assert len(content.splitlines()) == 2


def test_archive_stage_when_directory_entries_are_written_uses_fixed_epoch(stage: Path) -> None:
    os.utime(stage / "yate.exe", (1700000000, 1700000000))
    result = zip_dist.archive_stage(stage, stage.parent)
    with zipfile.ZipFile(result.path) as zf:
        top = zf.getinfo(f"{stage.name}/")
        runtime = zf.getinfo(f"{stage.name}/runtime/")
        file_info = zf.getinfo(f"{stage.name}/yate.exe")
    assert top.date_time == (1980, 1, 1, 0, 0, 0)
    assert runtime.date_time == (1980, 1, 1, 0, 0, 0)
    assert file_info.date_time == time.localtime(1700000000)[:6]
    assert file_info.create_system == 3


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


def test_archive_stage_when_stage_is_dot_raises_zip_dist_error(tmp_path: Path) -> None:
    with pytest.raises(zip_dist.ZipDistError, match="invalid stage directory name"):
        zip_dist.archive_stage(Path("."), tmp_path)
    assert list(tmp_path.glob("*.zip")) == []
    assert list(tmp_path.glob("*.tmp")) == []
    assert list(tmp_path.glob(".*")) == []


def test_archive_stage_when_stage_is_parent_segment_raises_zip_dist_error(tmp_path: Path) -> None:
    with pytest.raises(zip_dist.ZipDistError, match="invalid stage directory name"):
        zip_dist.archive_stage(tmp_path / "release" / "..", tmp_path)
    assert list(tmp_path.glob("*.zip")) == []
    assert list(tmp_path.glob("*.tmp")) == []
    assert list(tmp_path.glob(".*")) == []


def test_archive_stage_when_stage_name_is_resolved_top_level_prefix(stage: Path) -> None:
    result = zip_dist.archive_stage(stage, stage.parent)
    with zipfile.ZipFile(result.path) as zf:
        names = zf.namelist()
    prefix = f"{stage.resolve().name}/"
    assert all(name.startswith(prefix) for name in names)
    assert all(not name.startswith("/") and ".." not in name for name in names)


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


def test_archive_stage_when_stage_name_has_non_ascii_chars_writes_matching_checksum_row(
    tmp_path: Path,
) -> None:
    stage = tmp_path / "yate-0.2.18-发布"
    stage.mkdir()
    (stage / "yate.exe").write_bytes(b"exe")
    result = zip_dist.archive_stage(stage, tmp_path)
    content = (tmp_path / "SHA256SUMS.txt").read_bytes()
    assert content.endswith(os.fsencode(f"{stage.name}.zip") + b"\n")
    rows = [line for line in content.splitlines() if os.fsencode(stage.name + ".zip") in line]
    assert len(rows) == 1
    assert rows[0] == f"{result.digest}  {stage.name}.zip".encode("utf-8")


def test_archive_stage_when_checksum_row_has_trailing_unicode_space_replaces_it(stage: Path) -> None:
    dist = stage.parent
    (dist / "SHA256SUMS.txt").write_bytes(
        b"dead  yate-0.2.18-windows-x64.zip\xe3\x80\x80\nh1  other.zip\n"
    )
    result = zip_dist.archive_stage(stage, dist)
    lines = (dist / "SHA256SUMS.txt").read_bytes().splitlines()
    assert b"h1  other.zip" in lines
    rows = [line for line in lines if b"yate-0.2.18-windows-x64.zip" in line]
    assert rows == [f"{result.digest}  yate-0.2.18-windows-x64.zip".encode("ascii")]


def test_archive_stage_when_stage_contains_symlink_records_link_entry(
    stage: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "outside-secret.txt"
    target.write_bytes(b"secret")
    link = stage / "link.txt"
    link.write_bytes(b"placeholder")
    real_is_symlink = Path.is_symlink

    def fake_is_symlink(self: Path) -> bool:
        return self == link or real_is_symlink(self)

    monkeypatch.setattr(Path, "is_symlink", fake_is_symlink)
    def fake_readlink(path: Path) -> str:
        return str(target)

    monkeypatch.setattr(zip_dist.os, "readlink", fake_readlink)
    result = zip_dist.archive_stage(stage, stage.parent)
    with zipfile.ZipFile(result.path) as zf:
        names = zf.namelist()
        info = zf.getinfo(f"{stage.name}/link.txt")
        data = zf.read(f"{stage.name}/link.txt")
    assert f"{stage.name}/link.txt" in names
    assert (info.external_attr >> 16) & stat.S_IFLNK == stat.S_IFLNK
    assert data == os.fsencode(str(target))
    assert b"secret" not in result.path.read_bytes()


def test_archive_stage_when_symlink_points_outside_stage_does_not_read_target(
    stage: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "outside-secret.txt"
    target.write_bytes(b"secret")
    link = stage / "dangling-link"
    link.write_bytes(b"placeholder")
    real_is_symlink = Path.is_symlink

    def fake_is_symlink(self: Path) -> bool:
        return self == link or real_is_symlink(self)

    monkeypatch.setattr(Path, "is_symlink", fake_is_symlink)
    def fake_readlink2(path: Path) -> str:
        return str(target)

    monkeypatch.setattr(zip_dist.os, "readlink", fake_readlink2)
    result = zip_dist.archive_stage(stage, stage.parent)
    with zipfile.ZipFile(result.path) as zf:
        assert zf.testzip() is None
        data = zf.read(f"{stage.name}/dangling-link")
    assert data == os.fsencode(str(target))
    assert b"secret" not in result.path.read_bytes()


def test_archive_stage_when_archive_finishes_sets_readable_permissions(stage: Path) -> None:
    result = zip_dist.archive_stage(stage, stage.parent)
    zip_mode = result.path.stat().st_mode
    sums_mode = result.checksum_path.stat().st_mode
    if os.name == "posix":
        assert stat.S_IMODE(zip_mode) == 0o644
        assert stat.S_IMODE(sums_mode) == 0o644
    else:
        assert stat.S_IMODE(zip_mode) & stat.S_IWRITE
        assert stat.S_IMODE(sums_mode) & stat.S_IWRITE


def test_archive_stage_when_lock_file_exists_raises_and_keeps_lock(stage: Path) -> None:
    dist = stage.parent
    lock = dist / f".{stage.name}.lock"
    lock.write_bytes(b"")
    with pytest.raises(zip_dist.ZipDistError, match="in progress"):
        zip_dist.archive_stage(stage, dist)
    assert lock.exists()
    assert list(dist.glob("*.zip")) == []
    assert list(dist.glob("*.tmp")) == []
    assert list(dist.glob("*.bak")) == []


def test_archive_stage_when_checksum_replace_fails_restores_previous_zip(
    stage: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dist = stage.parent
    archive = dist / f"{stage.name}.zip"
    archive.write_bytes(b"old")
    sums_path = dist / "SHA256SUMS.txt"
    sums_path.write_text("oldhash  old.zip\n", encoding="ascii")
    real_replace = os.replace

    def fake_replace(src: Path, dst: Path, **kwargs: object) -> None:
        if dst == sums_path:
            raise OSError("mock failure")
        real_replace(src, dst)

    monkeypatch.setattr(zip_dist.os, "replace", fake_replace)
    with pytest.raises(OSError, match="mock failure"):
        zip_dist.archive_stage(stage, dist)
    assert archive.read_bytes() == b"old"
    assert sums_path.read_text(encoding="ascii") == "oldhash  old.zip\n"
    assert list(dist.glob("*.tmp")) == []
    assert list(dist.glob("*.bak")) == []
    assert list(dist.glob(".*")) == []


def test_archive_stage_when_zip_replace_fails_restores_previous_zip(
    stage: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dist = stage.parent
    archive = dist / f"{stage.name}.zip"
    archive.write_bytes(b"old")
    real_replace = os.replace

    def fake_replace(src: Path, dst: Path, **kwargs: object) -> None:
        if dst == archive and src.suffix == ".tmp":
            raise OSError("mock zip failure")
        real_replace(src, dst)

    monkeypatch.setattr(zip_dist.os, "replace", fake_replace)
    with pytest.raises(OSError, match="mock zip failure"):
        zip_dist.archive_stage(stage, dist)
    assert archive.read_bytes() == b"old"
    assert list(dist.glob("*.tmp")) == []
    assert list(dist.glob("*.bak")) == []
    assert list(dist.glob(".*")) == []


def test_archive_stage_when_stage_is_empty_releases_lock(tmp_path: Path) -> None:
    dist = tmp_path / "release"
    stage = dist / "empty-stage"
    stage.mkdir(parents=True)
    with pytest.raises(zip_dist.ZipDistError, match="no files"):
        zip_dist.archive_stage(stage, dist)
    assert list(dist.glob(".*.lock")) == []
    (stage / "yate.exe").write_bytes(b"exe")
    result = zip_dist.archive_stage(stage, dist)
    assert result.path.is_file()
    assert list(dist.glob(".*.lock")) == []


def test_archive_stage_when_stage_files_reject_entry_releases_lock(
    stage: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dist = stage.parent

    def reject(root: Path, name: str) -> list[tuple[Path, str, bool]]:
        raise zip_dist.ZipDistError(f"stage entry escapes stage root: {root}")

    monkeypatch.setattr(zip_dist, "_stage_files", reject)
    with pytest.raises(zip_dist.ZipDistError, match="escapes stage root"):
        zip_dist.archive_stage(stage, dist)
    assert list(dist.glob(".*.lock")) == []
    assert list(dist.glob("*.tmp")) == []
    assert list(dist.glob("*.bak")) == []


def test_archive_stage_when_mkstemp_fails_releases_lock(
    stage: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dist = stage.parent

    def fail_mkstemp(*args: object, **kwargs: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(zip_dist.tempfile, "mkstemp", fail_mkstemp)
    with pytest.raises(OSError, match="disk full"):
        zip_dist.archive_stage(stage, dist)
    assert list(dist.glob(".*.lock")) == []
    assert list(dist.glob("*.tmp")) == []
    assert list(dist.glob("*.bak")) == []


def test_archive_stage_when_zip_tmp_unlink_fails_still_releases_lock(
    stage: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dist = stage.parent
    real_unlink = Path.unlink

    def flaky_unlink(self: Path, missing_ok: bool = False) -> None:
        if self.suffix == ".tmp":
            raise PermissionError("busy temp file")
        real_unlink(self, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", flaky_unlink)
    result = zip_dist.archive_stage(stage, dist)
    assert result.path.is_file()
    assert list(dist.glob(".*.lock")) == []


def test_archive_stage_when_backup_unlink_fails_still_releases_lock(
    stage: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dist = stage.parent
    (dist / f"{stage.name}.zip").write_bytes(b"old")
    real_unlink = Path.unlink

    def flaky_backup_unlink(self: Path, missing_ok: bool = False) -> None:
        if self.suffix == ".bak":
            raise PermissionError("busy backup")
        real_unlink(self, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", flaky_backup_unlink)
    result = zip_dist.archive_stage(stage, dist)
    assert result.path.is_file()
    assert list(dist.glob(".*.lock")) == []


@pytest.mark.parametrize("inside", ["inside", "inside/nested"])
def test_archive_stage_when_dist_root_is_inside_stage_raises_zip_dist_error(
    stage: Path, inside: str
) -> None:
    target = stage / inside
    with pytest.raises(zip_dist.ZipDistError, match="inside the stage"):
        zip_dist.archive_stage(stage, target)
    assert not target.exists()
    assert list(stage.rglob("*.zip")) == []
    assert list(stage.rglob(".*lock")) == []
