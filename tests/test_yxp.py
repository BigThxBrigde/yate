"""Tests for extension packages (yate.services.yxp).

Every test runs against ``tmp_path`` directories -- the service takes an
explicit ``base_dir`` so the real ``~/.yate/extensions`` is never touched.
The helpers build real ``.yxp`` zip archives, so verification, extraction
and record keeping are exercised end to end.
"""

# pyright: reportPrivateUsage=false

from __future__ import annotations

import io
import json
import logging
import os
import zipfile
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

import pytest

from conftest import make_yxp
from yate.commands import register_commands
from yate.registries import CommandRegistry
from yate.services import yxp


# ------------------------------------------------------------- zip builder


def _record_path(base: Path, name: str) -> Path:
    return base / yxp.RECORDS_DIRNAME / f"{name}{yxp.RECORD_SUFFIX}"


# ------------------------------------------------------------- read_package


def test_read_package_happy_path(tmp_path: Path) -> None:
    pkg = make_yxp(tmp_path / "hello.yxp", {"hello.py": b"print('hi')\n"})
    package = yxp.read_package(pkg)
    assert package.manifest.name == "hello"
    assert package.manifest.version == "1.0.0"
    assert package.manifest.description == "greets"
    assert package.manifest.author == "tester"
    assert package.manifest.files == ("hello.py",)
    assert package.checksums == {"hello.py": sha256(b"print('hi')\n").hexdigest()}


def test_read_package_without_checksum_member(tmp_path: Path) -> None:
    pkg = make_yxp(tmp_path / "hello.yxp", {"hello.py": b"x"}, checksum=None)
    assert yxp.read_package(pkg).checksums is None


def test_read_package_missing_manifest(tmp_path: Path) -> None:
    path = tmp_path / "bare.yxp"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("hello.py", "x")
    with pytest.raises(yxp.YxpError, match="manifest"):
        yxp.read_package(path)


@pytest.mark.filterwarnings("ignore:Duplicate name")
def test_read_package_duplicate_manifest(tmp_path: Path) -> None:
    pkg = make_yxp(
        tmp_path / "hello.yxp",
        {"hello.py": b"x"},
        extra_members={"manifest": json.dumps({"name": "dup", "files": []})},
    )
    with pytest.raises(yxp.YxpError, match="exactly one"):
        yxp.read_package(pkg)


@pytest.mark.filterwarnings("ignore:Duplicate name")
def test_read_package_duplicate_checksum(tmp_path: Path) -> None:
    pkg = make_yxp(
        tmp_path / "hello.yxp",
        {"hello.py": b"x"},
        extra_members={"checksum": "{}"},
    )
    with pytest.raises(yxp.YxpError, match="at most one"):
        yxp.read_package(pkg)


def test_read_package_bad_manifest_json(tmp_path: Path) -> None:
    pkg = make_yxp(
        tmp_path / "hello.yxp", {"hello.py": b"x"}, manifest={"name": "x"}
    )
    # Overwrite the manifest member with invalid JSON.
    good = zipfile.ZipFile(pkg)
    names = good.namelist()
    blobs = {n: good.read(n) for n in names}
    good.close()
    with zipfile.ZipFile(pkg, "w") as zf:
        for name in names:
            zf.writestr(name, b"{not json" if name == "manifest" else blobs[name])
    with pytest.raises(yxp.YxpError, match="not valid JSON"):
        yxp.read_package(pkg)


def test_read_package_manifest_not_object(tmp_path: Path) -> None:
    pkg = make_yxp(tmp_path / "hello.yxp", {"hello.py": b"x"}, manifest=[1, 2])
    with pytest.raises(yxp.YxpError, match="JSON object"):
        yxp.read_package(pkg)


@pytest.mark.parametrize("name", ["", "bad name", "a/b", "x*y"])
def test_read_package_invalid_name(tmp_path: Path, name: str) -> None:
    pkg = make_yxp(
        tmp_path / "hello.yxp",
        {"hello.py": b"x"},
        manifest={"name": name, "files": ["hello.py"]},
    )
    with pytest.raises(yxp.YxpError, match="'name'"):
        yxp.read_package(pkg)


def test_read_package_version_defaults(tmp_path: Path) -> None:
    pkg = make_yxp(
        tmp_path / "hello.yxp",
        {"hello.py": b"x"},
        manifest={"name": "hello", "files": ["hello.py"]},
    )
    assert yxp.read_package(pkg).manifest.version == "0.1.0"


def test_read_package_files_must_be_string_list(tmp_path: Path) -> None:
    pkg = make_yxp(
        tmp_path / "hello.yxp",
        {"hello.py": b"x"},
        manifest={"name": "hello", "files": "hello.py"},
    )
    with pytest.raises(yxp.YxpError, match="'files'"):
        yxp.read_package(pkg)


def test_read_package_files_mismatch_both_ways(tmp_path: Path) -> None:
    pkg = make_yxp(
        tmp_path / "hello.yxp",
        {"hello.py": b"x", "extra.txt": b"y"},
        manifest={"name": "hello", "files": ["hello.py", "ghost.py"]},
    )
    with pytest.raises(yxp.YxpError, match="mismatch"):
        yxp.read_package(pkg)


@pytest.mark.parametrize(
    "rel", ["../escape.py", "C:/evil.py", "/abs.py", "a\\b.py", "_manifests/x.json"]
)
def test_read_package_rejects_unsafe_names(tmp_path: Path, rel: str) -> None:
    pkg = make_yxp(
        tmp_path / "hello.yxp",
        {"hello.py": b"x"},
        manifest={"name": "hello", "files": ["hello.py", rel]},
    )
    with pytest.raises(yxp.YxpError):
        yxp.read_package(pkg)


def test_read_package_rejects_case_colliding_names(tmp_path: Path) -> None:
    # On case-insensitive filesystems these members would overwrite each
    # other on disk, so the manifest must be rejected up front. Per-segment
    # casefolding also catches nested pairs like sub/x.py vs SUB/X.py.
    flat = make_yxp(
        tmp_path / "flat.yxp",
        {"a.py": b"1", "A.py": b"2"},
        manifest={"name": "flat", "files": ["a.py", "A.py"]},
    )
    with pytest.raises(yxp.YxpError, match="case-colliding"):
        yxp.read_package(flat)
    nested = make_yxp(
        tmp_path / "nested.yxp",
        {"sub/x.py": b"1", "SUB/X.py": b"2"},
        manifest={"name": "nested", "files": ["sub/x.py", "SUB/X.py"]},
    )
    with pytest.raises(yxp.YxpError, match="case-colliding"):
        yxp.read_package(nested)


def test_read_package_checksum_keys_mismatch(tmp_path: Path) -> None:
    pkg = make_yxp(
        tmp_path / "hello.yxp",
        {"hello.py": b"x"},
        checksum={"hello.py": "0" * 64, "ghost.py": "0" * 64},
    )
    with pytest.raises(yxp.YxpError, match="checksum list mismatch"):
        yxp.read_package(pkg)


def test_read_package_checksum_bad_digest_format(tmp_path: Path) -> None:
    pkg = make_yxp(
        tmp_path / "hello.yxp", {"hello.py": b"x"}, checksum={"hello.py": "zz"}
    )
    with pytest.raises(yxp.YxpError, match="hex digest"):
        yxp.read_package(pkg)


def test_read_package_tampered_payload(tmp_path: Path) -> None:
    pkg = make_yxp(tmp_path / "hello.yxp", {"hello.py": b"original"})
    # Rewrite the payload, keep the recorded digest.
    with zipfile.ZipFile(pkg) as zf:
        blobs = {n: zf.read(n) for n in zf.namelist()}
    blobs["hello.py"] = b"tampered"
    with zipfile.ZipFile(pkg, "w") as zf:
        for name, data in blobs.items():
            zf.writestr(name, data)
    with pytest.raises(yxp.YxpError, match="checksum mismatch"):
        yxp.read_package(pkg)


def test_read_package_not_a_zip(tmp_path: Path) -> None:
    path = tmp_path / "bad.yxp"
    path.write_bytes(b"definitely not a zip")
    with pytest.raises(yxp.YxpError, match="not a valid zip"):
        yxp.read_package(path)


def test_read_package_unreadable_file(tmp_path: Path) -> None:
    with pytest.raises(yxp.YxpError, match="cannot read package"):
        yxp.read_package(tmp_path / "missing.yxp")


# ------------------------------------------------------------ install_package


def test_install_extracts_payload_and_writes_record(tmp_path: Path) -> None:
    base = tmp_path / "home" / ".yate" / "extensions"
    pkg = make_yxp(tmp_path / "hello.yxp", {"hello.py": b"print('hi')\n"})
    report = yxp.install_package(pkg, base)
    assert report.name == "hello"
    assert report.files == ("hello.py",)
    assert report.stale_removed == ()
    assert report.target_dir == base
    assert (base / "hello.py").read_bytes() == b"print('hi')\n"
    record = json.loads(_record_path(base, "hello").read_text(encoding="utf-8"))
    assert record["name"] == "hello"
    assert record["version"] == "1.0.0"
    assert record["files"] == ["hello.py"]
    assert record["installed_at"]


def test_install_creates_nested_dirs(tmp_path: Path) -> None:
    base = tmp_path / "base"
    pkg = make_yxp(tmp_path / "hello.yxp", {"sub/impl.py": b"x"})
    report = yxp.install_package(pkg, base)
    assert report.files == ("sub/impl.py",)
    assert (base / "sub" / "impl.py").read_bytes() == b"x"


def test_install_without_checksum_installs_unverified(tmp_path: Path) -> None:
    base = tmp_path / "base"
    pkg = make_yxp(tmp_path / "hello.yxp", {"hello.py": b"x"}, checksum=None)
    assert yxp.install_package(pkg, base).files == ("hello.py",)


def test_install_refuses_unowned_collision(tmp_path: Path) -> None:
    base = tmp_path / "base"
    base.mkdir(parents=True)
    (base / "hello.py").write_bytes(b"user's own file")
    pkg = make_yxp(tmp_path / "hello.yxp", {"hello.py": b"packaged"})
    with pytest.raises(yxp.YxpError, match="already exist"):
        yxp.install_package(pkg, base)
    assert (base / "hello.py").read_bytes() == b"user's own file"


def test_install_refuses_tampered_package_without_side_effects(
    tmp_path: Path,
) -> None:
    base = tmp_path / "base"
    pkg = make_yxp(tmp_path / "hello.yxp", {"hello.py": b"original"})
    with zipfile.ZipFile(pkg) as zf:
        blobs = {n: zf.read(n) for n in zf.namelist()}
    blobs["hello.py"] = b"tampered"
    with zipfile.ZipFile(pkg, "w") as zf:
        for name, data in blobs.items():
            zf.writestr(name, data)
    with pytest.raises(yxp.YxpError, match="checksum mismatch"):
        yxp.install_package(pkg, base)
    assert not (base / "hello.py").exists()
    assert not _record_path(base, "hello").exists()


def test_install_upgrade_overwrites_and_removes_stale(tmp_path: Path) -> None:
    base = tmp_path / "base"
    make_yxp(tmp_path / "v1.yxp", {"hello.py": b"v1", "old.py": b"old"})
    yxp.install_package(tmp_path / "v1.yxp", base)
    make_yxp(tmp_path / "v2.yxp", {"hello.py": b"v2"})
    report = yxp.install_package(tmp_path / "v2.yxp", base)
    assert (base / "hello.py").read_bytes() == b"v2"
    assert report.stale_removed == ("old.py",)
    assert not (base / "old.py").exists()
    record = json.loads(_record_path(base, "hello").read_text(encoding="utf-8"))
    assert record["files"] == ["hello.py"]


def test_install_failure_rolls_back_partial_extraction(tmp_path: Path) -> None:
    base = tmp_path / "base"
    # "a.py/bad.txt" cannot be extracted: "a.py" is written as a file first,
    # so creating the parent directory fails mid-way.
    pkg = make_yxp(tmp_path / "broken.yxp", {"a.py": b"x", "a.py/bad.txt": b"y"})
    with pytest.raises(yxp.YxpError, match="extraction failed"):
        yxp.install_package(pkg, base)
    assert not (base / "a.py").exists()
    assert not _record_path(base, "broken").exists()


def test_failed_upgrade_extraction_restores_previous_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mid-extraction I/O failure on an upgrade puts v1 back untouched."""
    base = tmp_path / "base"
    v1 = make_yxp(tmp_path / "v1.yxp", {"hello.py": b"v1", "old.py": b"o1"})
    yxp.install_package(v1, base)
    v2 = make_yxp(tmp_path / "v2.yxp", {"hello.py": b"v2", "new.py": b"n2"})
    real_write = Path.write_bytes

    def flaky_write(self: Path, data: bytes) -> None:
        if self.name == "new.py":  # first payload file lands, then boom
            raise OSError("disk full")
        real_write(self, data)

    monkeypatch.setattr(Path, "write_bytes", flaky_write)
    with pytest.raises(yxp.YxpError, match="extraction failed"):
        yxp.install_package(v2, base)
    monkeypatch.undo()
    assert (base / "hello.py").read_bytes() == b"v1"  # old content restored
    assert not (base / "new.py").exists()  # fresh file dropped
    assert (base / "old.py").read_bytes() == b"o1"  # stale cleanup never ran
    record = json.loads(_record_path(base, "hello").read_text(encoding="utf-8"))
    assert record["files"] == ["hello.py", "old.py"]  # v1 record intact


def test_failed_record_write_restores_previous_installation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A record-write failure on an upgrade restores the v1 installation."""
    base = tmp_path / "base"
    v1 = make_yxp(tmp_path / "v1.yxp", {"hello.py": b"v1", "old.py": b"o1"})
    yxp.install_package(v1, base)
    v2 = make_yxp(tmp_path / "v2.yxp", {"hello.py": b"v2", "fresh.py": b"f"})

    def boom(records: Path, package: yxp.YxpPackage) -> None:
        raise yxp.YxpError("cannot write install record")

    monkeypatch.setattr(yxp, "_write_record", boom)
    with pytest.raises(yxp.YxpError, match="cannot write install record"):
        yxp.install_package(v2, base)
    assert (base / "hello.py").read_bytes() == b"v1"  # overwrite undone
    assert not (base / "fresh.py").exists()  # fresh file dropped
    assert (base / "old.py").read_bytes() == b"o1"  # stale removal undone
    record = json.loads(_record_path(base, "hello").read_text(encoding="utf-8"))
    assert record["files"] == ["hello.py", "old.py"]


def test_failed_record_write_on_fresh_install_leaves_no_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    base = tmp_path / "base"
    pkg = make_yxp(tmp_path / "hello.yxp", {"hello.py": b"x"})

    def boom(records: Path, package: yxp.YxpPackage) -> None:
        raise yxp.YxpError("cannot write install record")

    monkeypatch.setattr(yxp, "_write_record", boom)
    with pytest.raises(yxp.YxpError, match="cannot write install record"):
        yxp.install_package(pkg, base)
    assert not (base / "hello.py").exists()
    assert not _record_path(base, "hello").exists()


def test_extraction_reverifies_swapped_payload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Payload swapped in between validation and extraction cannot land."""
    base = tmp_path / "base"
    pkg = make_yxp(tmp_path / "hello.yxp", {"hello.py": b"v1"})
    good = yxp.read_package(pkg)
    # rebuild the archive with different payload bytes but the original
    # manifest/checksum members -- what a mid-install file swap looks like
    with zipfile.ZipFile(pkg) as zf:
        members = {name: zf.read(name) for name in zf.namelist()}
    members["hello.py"] += b"\n# swapped in mid-install\n"
    with zipfile.ZipFile(pkg, "w") as zf:
        for name, data in members.items():
            zf.writestr(name, data)
    # read_package already passed on the good archive; the swap happened
    # before extraction reopens the file
    def passthrough(path: Path) -> yxp.YxpPackage:
        return good

    monkeypatch.setattr(yxp, "read_package", passthrough)
    with pytest.raises(yxp.YxpError, match="checksum mismatch"):
        yxp.install_package(pkg, base)
    assert not (base / "hello.py").exists()  # nothing extracted
    assert not _record_path(base, "hello").exists()


def test_install_leaves_no_temporary_record_files(tmp_path: Path) -> None:
    base = tmp_path / "base"
    pkg = make_yxp(tmp_path / "hello.yxp", {"hello.py": b"x"})
    yxp.install_package(pkg, base)
    records = base / yxp.RECORDS_DIRNAME
    assert sorted(entry.name for entry in records.iterdir()) == ["hello.json"]


def test_failed_record_replace_keeps_old_record_and_drops_temp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A crash between temp write and rename leaves the v1 record intact."""
    base = tmp_path / "base"
    v1 = make_yxp(tmp_path / "v1.yxp", {"hello.py": b"v1"})
    yxp.install_package(v1, base)
    v2 = make_yxp(tmp_path / "v2.yxp", {"hello.py": b"v2"})

    def boom(src: Path, dst: Path) -> None:
        raise OSError("disk went away")

    monkeypatch.setattr(yxp.os, "replace", boom)
    with pytest.raises(yxp.YxpError, match="cannot write install record"):
        yxp.install_package(v2, base)
    assert (base / "hello.py").read_bytes() == b"v1"  # upgrade rolled back
    record = json.loads(_record_path(base, "hello").read_text(encoding="utf-8"))
    assert record["files"] == ["hello.py"]  # v1 record intact
    tmp_record = base / yxp.RECORDS_DIRNAME / "hello.json.tmp"
    assert not tmp_record.exists()  # temp residue dropped


def test_install_refuses_symlinked_member_target(tmp_path: Path) -> None:
    """A symlinked member target fails the whole install, untouched."""
    base = tmp_path / "base"
    pkg = make_yxp(tmp_path / "hello.yxp", {"hello.py": b"packaged"})
    yxp.install_package(pkg, base)
    outside = tmp_path / "outside.txt"
    outside.write_bytes(b"precious")
    target = base / "hello.py"
    target.unlink()
    try:
        os.symlink(outside, target)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation unavailable")
    with pytest.raises(yxp.YxpError, match="symlink"):
        yxp.install_package(pkg, base)
    assert outside.read_bytes() == b"precious"  # never written through
    assert target.is_symlink()  # install dir state unchanged
    assert _record_path(base, "hello").exists()  # record intact


def test_install_refuses_symlinked_parent_directory(tmp_path: Path) -> None:
    """A symlinked intermediate directory fails the install untouched."""
    base = tmp_path / "base"
    base.mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    try:
        os.symlink(outside, base / "sub", target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation unavailable")
    pkg = make_yxp(tmp_path / "hello.yxp", {"sub/x.py": b"payload"})
    with pytest.raises(yxp.YxpError, match="symlink"):
        yxp.install_package(pkg, base)
    assert list(outside.iterdir()) == []  # nothing written through
    assert not _record_path(base, "hello").exists()  # no record either


def test_install_refuses_symlinked_parent_on_stale_removal(
    tmp_path: Path,
) -> None:
    """A symlinked parent of a stale member refuses the upgrade, intact."""
    base = tmp_path / "base"
    v1 = make_yxp(tmp_path / "v1.yxp", {"sub/x.py": b"v1"})
    yxp.install_package(v1, base)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "keep.txt").write_bytes(b"keep")
    v2 = make_yxp(tmp_path / "v2.yxp", {"hello.py": b"v2"})
    (base / "sub" / "x.py").unlink()
    (base / "sub").rmdir()
    try:
        os.symlink(outside, base / "sub", target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation unavailable")
    with pytest.raises(yxp.YxpError, match="symlink"):
        yxp.install_package(v2, base)
    assert (outside / "keep.txt").read_bytes() == b"keep"  # not deleted
    record = json.loads(_record_path(base, "hello").read_text(encoding="utf-8"))
    assert record["files"] == ["sub/x.py"]  # v1 record intact
    assert not (base / "hello.py").exists()  # v2 extraction rolled back


def test_install_refuses_symlinked_stale_member_leaves_others(
    tmp_path: Path,
) -> None:
    """A symlinked stale member refuses the upgrade without partial deletes."""
    base = tmp_path / "base"
    v1 = make_yxp(tmp_path / "v1.yxp", {"a.py": b"a", "b.py": b"b", "zz.py": b"z"})
    yxp.install_package(v1, base)
    outside = tmp_path / "outside"
    outside.mkdir()
    v2 = make_yxp(tmp_path / "v2.yxp", {"d.py": b"d"})
    (base / "zz.py").unlink()
    try:
        os.symlink(outside, base / "zz.py")
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation unavailable")
    with pytest.raises(yxp.YxpError, match="symlink"):
        yxp.install_package(v2, base)
    assert (base / "a.py").read_bytes() == b"a"  # stale, not deleted
    assert (base / "b.py").read_bytes() == b"b"  # stale, not deleted
    record = json.loads(_record_path(base, "hello").read_text(encoding="utf-8"))
    assert record["files"] == ["a.py", "b.py", "zz.py"]  # matches disk
    assert not (base / "d.py").exists()  # v2 extraction rolled back


def test_uninstall_refuses_symlinked_parent_directory(tmp_path: Path) -> None:
    """Uninstall refuses to delete through a symlinked member parent."""
    base = tmp_path / "base"
    pkg = make_yxp(tmp_path / "hello.yxp", {"sub/x.py": b"x"})
    yxp.install_package(pkg, base)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "keep.txt").write_bytes(b"keep")
    (base / "sub" / "x.py").unlink()
    (base / "sub").rmdir()
    try:
        os.symlink(outside, base / "sub", target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation unavailable")
    with pytest.raises(yxp.YxpError, match="symlink"):
        yxp.uninstall_package("hello", base)
    assert (outside / "keep.txt").read_bytes() == b"keep"  # untouched
    assert _record_path(base, "hello").exists()  # record intact


def test_install_refuses_symlinked_records_directory(tmp_path: Path) -> None:
    """A symlinked records directory fails the install before any write."""
    base = tmp_path / "base"
    base.mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    try:
        os.symlink(
            outside, base / yxp.RECORDS_DIRNAME, target_is_directory=True
        )
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation unavailable")
    pkg = make_yxp(tmp_path / "hello.yxp", {"hello.py": b"x"})
    with pytest.raises(yxp.YxpError, match="symlink"):
        yxp.install_package(pkg, base)
    assert list(outside.iterdir()) == []  # nothing written through
    assert not (base / "hello.py").exists()  # no extraction either


def test_uninstall_refuses_symlinked_records_directory(tmp_path: Path) -> None:
    """A symlinked records directory fails the uninstall untouched."""
    base = tmp_path / "base"
    base.mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    try:
        os.symlink(
            outside, base / yxp.RECORDS_DIRNAME, target_is_directory=True
        )
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation unavailable")
    with pytest.raises(yxp.YxpError, match="symlink"):
        yxp.uninstall_package("hello", base)
    assert list(outside.iterdir()) == []  # nothing written through


def test_install_overwrites_regular_member_still_works(tmp_path: Path) -> None:
    """Reinstalling over a regular member file keeps overwriting."""
    base = tmp_path / "base"
    pkg = make_yxp(tmp_path / "hello.yxp", {"hello.py": b"new content"})
    yxp.install_package(pkg, base)
    report = yxp.install_package(pkg, base)
    assert isinstance(report, yxp.InstallReport)
    assert report.files == ("hello.py",)
    assert (base / "hello.py").read_bytes() == b"new content"


def test_install_without_checksum_logs_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Installing a checksum-less package logs a WARNING but succeeds."""
    monkeypatch.setattr(logging.getLogger("yate"), "propagate", True)
    base = tmp_path / "base"
    pkg = make_yxp(tmp_path / "hello.yxp", {"hello.py": b"x"}, checksum=None)
    with caplog.at_level(logging.WARNING, logger="yate.services.yxp"):
        yxp.install_package(pkg, base)
    assert (base / "hello.py").read_bytes() == b"x"
    assert any(
        record.name == "yate.services.yxp"
        and record.levelno == logging.WARNING
        and "without a checksum member" in record.getMessage()
        for record in caplog.records
    )


def test_install_with_checksum_no_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A checksummed package installs without the unverifiable warning."""
    monkeypatch.setattr(logging.getLogger("yate"), "propagate", True)
    base = tmp_path / "base"
    pkg = make_yxp(tmp_path / "hello.yxp", {"hello.py": b"x"})
    with caplog.at_level(logging.WARNING, logger="yate.services.yxp"):
        yxp.install_package(pkg, base)
    assert (base / "hello.py").read_bytes() == b"x"
    assert not any(
        record.name == "yate.services.yxp"
        and record.levelno == logging.WARNING
        and "without a checksum member" in record.getMessage()
        for record in caplog.records
    )


# --------------------------------------------------------- member size caps


def test_oversized_member_is_rejected_before_extraction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A member past the cap raises and never touches the install dir."""
    monkeypatch.setattr(yxp, "MAX_MEMBER_BYTES", 16)
    base = tmp_path / "base"
    pkg = make_yxp(tmp_path / "big.yxp", {"hello.py": b"x" * 4096})
    with pytest.raises(yxp.YxpError, match="exceeds the size cap"):
        yxp.install_package(pkg, base)
    assert not (base / "hello.py").exists()
    assert not _record_path(base, "big").exists()


def test_declared_small_but_actually_large_member_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A lying ``ZipInfo.file_size`` cannot slip past the byte counter.

    ``zipfile`` itself refuses to stream past the declared size (its CRC /
    size checks reject tampered archives), so the lie is injected on the
    stream: the member claims 16 bytes while the stream yields 4096.  The
    bounded reader must count the actual bytes and reject.
    """
    monkeypatch.setattr(yxp, "MAX_MEMBER_BYTES", 16)
    pkg = make_yxp(tmp_path / "liar.yxp", {"hello.py": b"x" * 16})
    with zipfile.ZipFile(pkg) as zf:
        assert zf.getinfo("hello.py").file_size == 16
        def lying_open(name: object, mode: str = "r") -> io.BytesIO:
            assert name == "hello.py"
            return io.BytesIO(b"x" * 4096)

        monkeypatch.setattr(zf, "open", lying_open)
        with pytest.raises(yxp.YxpError, match="exceeds the size cap"):
            yxp._read_member(zf, "hello.py", "liar.yxp")


def test_stale_file_whose_backup_fails_is_kept(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A stale file that cannot be backed up is kept, never deleted."""
    base = tmp_path / "base"
    v1 = make_yxp(tmp_path / "v1.yxp", {"hello.py": b"v1", "old.py": b"o1"})
    yxp.install_package(v1, base)
    v2 = make_yxp(tmp_path / "v2.yxp", {"hello.py": b"v2"})
    real_read = Path.read_bytes

    def flaky_read(self: Path) -> bytes:
        if self.name == "old.py":
            raise OSError("locked")
        return real_read(self)

    monkeypatch.setattr(Path, "read_bytes", flaky_read)
    report = yxp.install_package(v2, base)
    monkeypatch.undo()
    assert (base / "old.py").read_bytes() == b"o1"  # kept, not deleted
    assert "old.py" not in report.stale_removed


# ------------------------------------------ rollback / restore symlink skips


def test_rollback_skips_symlinked_member(
    tmp_path: Path, caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A member resolving through a symlink is skipped, not unlinked."""
    monkeypatch.setattr(logging.getLogger("yate"), "propagate", True)
    base = tmp_path / "base"
    base.mkdir()
    outside = tmp_path / "outside.py"
    outside.write_bytes(b"outside")
    target = base / "x.py"
    try:
        os.symlink(outside, target)
    except OSError:
        pytest.skip("symlink creation unavailable")
    with caplog.at_level(logging.WARNING, logger="yate.services.yxp"):
        yxp._rollback_files(["x.py"], {}, base)
    assert outside.read_bytes() == b"outside"  # not deleted through the link
    assert any(
        record.name == "yate.services.yxp"
        and record.levelno == logging.WARNING
        and "skipping rollback" in record.getMessage()
        for record in caplog.records
    )


def test_restore_stale_files_skips_symlinked_member(
    tmp_path: Path, caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A stale-file backup is not written through a symlinked member."""
    monkeypatch.setattr(logging.getLogger("yate"), "propagate", True)
    base = tmp_path / "base"
    base.mkdir()
    outside = tmp_path / "outside.py"
    outside.write_bytes(b"outside")
    target = base / "x.py"
    try:
        os.symlink(outside, target)
    except OSError:
        pytest.skip("symlink creation unavailable")
    with caplog.at_level(logging.WARNING, logger="yate.services.yxp"):
        yxp._restore_stale_files({"x.py": b"restored"}, base)
    assert outside.read_bytes() == b"outside"  # not written through the link
    assert any(
        record.name == "yate.services.yxp"
        and record.levelno == logging.WARNING
        and "skipping restore" in record.getMessage()
        for record in caplog.records
    )


# ---------------------------------------------------------- uninstall_package


def test_uninstall_removes_files_and_record(tmp_path: Path) -> None:
    base = tmp_path / "base"
    pkg = make_yxp(tmp_path / "hello.yxp", {"hello.py": b"x"})
    yxp.install_package(pkg, base)
    report = yxp.uninstall_package("hello", base)
    assert report.removed == ("hello.py",)
    assert report.missing == ()
    assert not (base / "hello.py").exists()
    assert not _record_path(base, "hello").exists()


def test_uninstall_missing_record(tmp_path: Path) -> None:
    with pytest.raises(yxp.YxpError, match="not installed"):
        yxp.uninstall_package("ghost", tmp_path / "base")


@pytest.mark.parametrize("name", ["../evil", "a/b", "", "a:b"])
def test_uninstall_rejects_invalid_names(tmp_path: Path, name: str) -> None:
    with pytest.raises(yxp.YxpError, match="invalid package name"):
        yxp.uninstall_package(name, tmp_path / "base")


def test_uninstall_tolerates_missing_files(tmp_path: Path) -> None:
    base = tmp_path / "base"
    pkg = make_yxp(tmp_path / "hello.yxp", {"hello.py": b"x"})
    yxp.install_package(pkg, base)
    (base / "hello.py").unlink()
    report = yxp.uninstall_package("hello", base)
    assert report.removed == ()
    assert report.missing == ("hello.py",)
    assert not _record_path(base, "hello").exists()


def test_uninstall_prunes_empty_parent_dirs(tmp_path: Path) -> None:
    base = tmp_path / "base"
    pkg = make_yxp(tmp_path / "hello.yxp", {"sub/impl.py": b"x"})
    yxp.install_package(pkg, base)
    yxp.uninstall_package("hello", base)
    assert not (base / "sub").exists()


# --------------------------------------------------------------- list_packages


def test_list_packages_empty(tmp_path: Path) -> None:
    assert yxp.list_packages(tmp_path / "base") == []


def test_list_packages_sorted_by_name(tmp_path: Path) -> None:
    base = tmp_path / "base"
    for name, payload in (("zeta", "x.py"), ("alpha", "y.py")):
        pkg = make_yxp(
            tmp_path / f"{name}.yxp",
            {payload: b"x"},
            manifest={"name": name, "files": [payload], "description": "d"},
        )
        yxp.install_package(pkg, base)
    packages = yxp.list_packages(base)
    assert [p.name for p in packages] == ["alpha", "zeta"]
    assert packages[0].description == "d"
    assert packages[0].file_count == 1
    assert packages[0].installed_at


def test_list_packages_reports_corrupt_record(tmp_path: Path) -> None:
    base = tmp_path / "base"
    records = base / yxp.RECORDS_DIRNAME
    records.mkdir(parents=True)
    (records / "broken.json").write_text("{nope", encoding="utf-8")
    packages = yxp.list_packages(base)
    assert len(packages) == 1
    assert packages[0].name == "broken"
    assert packages[0].error is not None


# ----------------------------------------------------------------- formatters


def test_format_install_report() -> None:
    report = yxp.InstallReport(
        name="hello", version="1.0.0", files=("a.py",),
        stale_removed=(), target_dir=Path("x"),
    )
    assert yxp.format_install_report(report) == (
        "installed hello 1.0.0: 1 file(s) -> x"
    )


def test_format_install_report_with_stale() -> None:
    report = yxp.InstallReport(
        name="hello", version="2.0.0", files=("a.py",),
        stale_removed=("old.py",), target_dir=Path("x"),
    )
    assert "removed stale: old.py" in yxp.format_install_report(report)


def test_format_uninstall_report() -> None:
    report = yxp.UninstallReport(name="hello", removed=("a.py",), missing=())
    assert yxp.format_uninstall_report(report) == "removed hello: 1 file(s)"
    missing = yxp.UninstallReport(name="hi", removed=(), missing=("a.py",))
    assert "already absent: a.py" in yxp.format_uninstall_report(missing)


def test_format_package_list() -> None:
    assert yxp.format_package_list([]) == "no extension packages installed"
    listing = yxp.format_package_list(
        [
            yxp.InstalledPackage(
                name="hello", version="1.0.0", description="greets",
                author="t", file_count=2, installed_at="now",
            ),
            yxp.InstalledPackage(
                name="bad", version="", description="", author="",
                file_count=0, installed_at="", error="invalid",
            ),
        ]
    )
    assert "hello 1.0.0 -- greets (2 file(s))" in listing
    assert "bad: unreadable install record" in listing


# --------------------------------------------------- builtin : commands -----


class _RecordingEditor:
    """Editor stand-in recording messages and output-overlay pushes."""

    def __init__(self) -> None:
        self.messages: list[tuple[str, str]] = []
        self.outputs: list[tuple[str, str]] = []
        self.overlays = self

    def message(self, text: str, kind: str = "info") -> None:
        """Record a message-line write."""
        self.messages.append((text, kind))

    def show_output(self, title: str, text: str) -> None:
        """Record an output overlay push."""
        self.outputs.append((title, text))


def _editor_with_commands() -> tuple[CommandRegistry, _RecordingEditor]:
    editor = _RecordingEditor()
    registry = CommandRegistry()
    register_commands(registry, cast(Any, editor))
    return registry, editor


def test_extension_package_commands_registered() -> None:
    registry, _ = _editor_with_commands()
    for name in ("install-extension", "uninstall-extension", "list-extensions"):
        assert name in registry.names()


def test_install_extension_command_installs_and_reports(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    base = tmp_path / "exts"
    monkeypatch.setattr(yxp, "default_extensions_dir", lambda: base)
    registry, editor = _editor_with_commands()
    pkg = make_yxp(tmp_path / "hello.yxp", {"hello.py": b"x"})
    entry = registry.get("install-extension")
    assert entry is not None
    entry.func(str(pkg))
    assert (base / "hello.py").exists()
    assert any(
        "installed hello 1.0.0" in text and kind == "ok"
        for text, kind in editor.messages
    )


def test_install_extension_command_reports_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(yxp, "default_extensions_dir", lambda: tmp_path / "exts")
    registry, editor = _editor_with_commands()
    entry = registry.get("install-extension")
    assert entry is not None
    entry.func(str(tmp_path / "missing.yxp"))
    assert editor.messages[-1][1] == "warn"
    entry.func("")
    assert "usage:" in editor.messages[-1][0]


def test_uninstall_extension_command_removes_and_reports(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    base = tmp_path / "exts"
    monkeypatch.setattr(yxp, "default_extensions_dir", lambda: base)
    registry, editor = _editor_with_commands()
    pkg = make_yxp(tmp_path / "hello.yxp", {"hello.py": b"x"})
    yxp.install_package(pkg, base)
    entry = registry.get("uninstall-extension")
    assert entry is not None
    entry.func("hello")
    assert not (base / "hello.py").exists()
    assert any(
        "removed hello" in text and kind == "ok" for text, kind in editor.messages
    )
    entry.func("hello")
    assert editor.messages[-1][1] == "warn"


def test_list_extension_command_empty_message() -> None:
    registry, editor = _editor_with_commands()
    entry = registry.get("list-extensions")
    assert entry is not None
    entry.func("")
    assert editor.messages == [("no extension packages installed", "info")]
    assert editor.outputs == []


def test_list_extension_command_pushes_output_overlay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    base = tmp_path / "exts"
    monkeypatch.setattr(yxp, "default_extensions_dir", lambda: base)
    registry, editor = _editor_with_commands()
    pkg = make_yxp(tmp_path / "hello.yxp", {"hello.py": b"x"})
    yxp.install_package(pkg, base)
    entry = registry.get("list-extensions")
    assert entry is not None
    entry.func("")
    assert len(editor.outputs) == 1
    title, text = editor.outputs[0]
    assert title == "extension packages"
    assert "hello 1.0.0" in text
