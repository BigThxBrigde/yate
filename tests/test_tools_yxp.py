"""Tests for the ``tools.yxp`` packager (build / verify).

The exercises run the real CLI entry points (``tools.yxp.cli.main`` for
build/verify, ``yate.cli.main`` for install), and the install integration
against the isolated-home fixture from conftest.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from conftest import make_yxp
from tools.yxp import cli as yxp_tool
from yate.cli import main as yate_main
from yate.services import yxp

EXAMPLE_DIR = Path(__file__).resolve().parents[1] / "tools" / "yxp" / "example" / "hello_yxp"


# ------------------------------------------------------------ collect_payload


def test_collect_payload_skips_metadata_and_caches(tmp_path: Path) -> None:
    (tmp_path / "manifest").write_text("{}", encoding="utf-8")
    (tmp_path / "checksum").write_text("{}", encoding="utf-8")
    (tmp_path / "mod.py").write_text("x = 1", encoding="utf-8")
    (tmp_path / "__pycache__" / "mod.cpython-312.pyc").parent.mkdir()
    (tmp_path / "__pycache__" / "mod.cpython-312.pyc").write_bytes(b"bytecode")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "HEAD").write_text("ref", encoding="utf-8")
    (tmp_path / "data.txt").write_text("data", encoding="utf-8")
    pairs = yxp_tool.collect_payload(tmp_path)
    assert [rel for rel, _ in pairs] == ["data.txt", "mod.py"]


def test_collect_payload_is_recursive_and_sorted(tmp_path: Path) -> None:
    (tmp_path / "b").mkdir()
    (tmp_path / "a").mkdir()
    (tmp_path / "b" / "2.py").write_text("x", encoding="utf-8")
    (tmp_path / "a" / "1.py").write_text("x", encoding="utf-8")
    (tmp_path / "0.py").write_text("x", encoding="utf-8")
    assert [rel for rel, _ in yxp_tool.collect_payload(tmp_path)] == [
        "0.py", "a/1.py", "b/2.py",
    ]


# ------------------------------------------------------------- build_package


def test_build_requires_manifest(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "mod.py").write_text("x", encoding="utf-8")
    assert yxp_tool.main(["build", str(src)]) == 1
    assert "missing 'manifest'" in capsys.readouterr().err


def test_build_rejects_hand_written_files_field(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "manifest").write_text(
        json.dumps({"name": "x", "files": ["mod.py"]}), encoding="utf-8"
    )
    (src / "mod.py").write_text("x", encoding="utf-8")
    assert yxp_tool.main(["build", str(src)]) == 1
    assert "'files'" in capsys.readouterr().err


def test_build_rejects_missing_name(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "manifest").write_text("{}", encoding="utf-8")
    assert yxp_tool.main(["build", str(src)]) == 1
    assert "'name'" in capsys.readouterr().err


def test_build_rejects_missing_source_dir(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert yxp_tool.main(["build", str(tmp_path / "nope")]) == 1
    assert "not a directory" in capsys.readouterr().err


def test_build_refuses_overwrite_without_force(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "manifest").write_text(json.dumps({"name": "x"}), encoding="utf-8")
    (src / "mod.py").write_text("x", encoding="utf-8")
    out = tmp_path / "x.yxp"
    out.write_bytes(b"precious")
    assert yxp_tool.main(["build", str(src), "--output", str(out)]) == 1
    assert out.read_bytes() == b"precious"
    assert yxp_tool.main(["build", str(src), "--output", str(out), "--force"]) == 0
    assert out.read_bytes() != b"precious"


def test_build_writes_manifest_checksum_and_payload(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "manifest").write_text(
        json.dumps(
            {"name": "demo", "version": "2.1", "description": "d", "author": "a"}
        ),
        encoding="utf-8",
    )
    (src / "mod.py").write_bytes(b"x = 1\n")
    sub = src / "sub"
    sub.mkdir()
    (sub / "data.txt").write_bytes(b"payload")
    out = tmp_path / "demo.yxp"
    assert yxp_tool.main(["build", str(src), "--output", str(out)]) == 0
    package = yxp.read_package(out)
    assert package.manifest.name == "demo"
    assert package.manifest.version == "2.1"
    assert package.manifest.files == ("mod.py", "sub/data.txt")
    assert package.checksums is not None
    with zipfile.ZipFile(out) as zf:
        assert zf.read("mod.py") == b"x = 1\n"
        manifest = json.loads(zf.read("manifest"))
        assert manifest["files"] == ["mod.py", "sub/data.txt"]


def test_default_output_uses_package_name(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "manifest").write_text(json.dumps({"name": "demo"}), encoding="utf-8")
    (src / "mod.py").write_text("x", encoding="utf-8")
    assert yxp_tool.main(["build", str(src)]) == 0
    assert (Path.cwd() / "demo.yxp").exists()
    (Path.cwd() / "demo.yxp").unlink()


# ---------------------------------------------------------- verify subcommand


def test_verify_accepts_valid_package(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    pkg = make_yxp(tmp_path / "hello.yxp", {"hello.py": b"x"})
    assert yxp_tool.main(["verify", str(pkg)]) == 0
    out = capsys.readouterr().out
    assert "hello 1.0.0" in out
    assert "checksums verified" in out


def test_verify_rejects_bad_package(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bad = tmp_path / "bad.yxp"
    bad.write_bytes(b"nope")
    assert yxp_tool.main(["verify", str(bad)]) == 1
    assert "error:" in capsys.readouterr().err


# ------------------------------------------------- example package roundtrip


def test_example_directory_builds_and_installs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = tmp_path / "hello_yxp.yxp"
    assert yxp_tool.main(["build", str(EXAMPLE_DIR), "--output", str(out)]) == 0
    monkeypatch.setattr(yxp, "default_extensions_dir", lambda: tmp_path / "exts")
    assert yate_main(["--install-extension", str(out)]) == 0
    report = yxp.list_packages(tmp_path / "exts")[0]
    assert report.name == "hello_yxp"
    assert report.version == "1.0.0"
    assert report.file_count == 1
