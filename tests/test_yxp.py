"""Tests for extension packages (yate.services.yxp).

Every test runs against ``tmp_path`` directories -- the service takes an
explicit ``base_dir`` so the real ``~/.yate/extensions`` is never touched.
The helpers build real ``.yxp`` zip archives, so verification, extraction
and record keeping are exercised end to end.
"""

from __future__ import annotations

import json
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
    entry[0](str(pkg))
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
    entry[0](str(tmp_path / "missing.yxp"))
    assert editor.messages[-1][1] == "warn"
    entry[0]("")
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
    entry[0]("hello")
    assert not (base / "hello.py").exists()
    assert any(
        "removed hello" in text and kind == "ok" for text, kind in editor.messages
    )
    entry[0]("hello")
    assert editor.messages[-1][1] == "warn"


def test_list_extension_command_empty_message() -> None:
    registry, editor = _editor_with_commands()
    entry = registry.get("list-extensions")
    assert entry is not None
    entry[0]("")
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
    entry[0]("")
    assert len(editor.outputs) == 1
    title, text = editor.outputs[0]
    assert title == "extension packages"
    assert "hello 1.0.0" in text
