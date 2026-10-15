"""Tests for the ``tools.yxp`` packager (--create / --pack / --verify).

The exercises run the real CLI entry points (``tools.yxp.cli.main`` for
scaffold/pack/verify, ``yate.cli.main`` for install), and the install
integration against the isolated-home fixture from conftest.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path
from unittest.mock import patch

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


# ---------------------------------------------------------------- --create


def test_create_scaffolds_manifest_and_starter(tmp_path: Path) -> None:
    assert yxp_tool.main(["--create", "my_ext", "--dir", str(tmp_path)]) == 0
    manifest = json.loads((tmp_path / "my_ext" / "manifest").read_text("utf-8"))
    assert manifest["name"] == "my_ext"
    assert manifest["version"] == "0.1.0"
    starter = (tmp_path / "my_ext" / "my_ext.py").read_text("utf-8")
    assert "def setup(api: ExtensionAPI)" in starter
    assert '"hello-my-ext"' in starter


def test_create_rejects_invalid_name(tmp_path: Path) -> None:
    assert yxp_tool.main(["--create", "bad name", "--dir", str(tmp_path)]) == 1
    assert not (tmp_path / "bad name").exists()


@pytest.mark.parametrize("name", [".", ".."])
def test_create_rejects_dot_names_even_with_force(tmp_path: Path, name: str) -> None:
    # "." with --force would rmtree the parent directory
    (tmp_path / "precious.txt").write_text("keep", encoding="utf-8")
    assert yxp_tool.main(["--create", name, "--dir", str(tmp_path), "--force"]) == 1
    assert (tmp_path / "precious.txt").read_text("utf-8") == "keep"


def test_create_refuses_existing_dir_without_force(tmp_path: Path) -> None:
    (tmp_path / "my_ext").mkdir()
    (tmp_path / "my_ext" / "precious.txt").write_text("keep", encoding="utf-8")
    assert yxp_tool.main(["--create", "my_ext", "--dir", str(tmp_path)]) == 1
    assert (tmp_path / "my_ext" / "precious.txt").read_text("utf-8") == "keep"


def test_create_force_replaces_existing_dir(tmp_path: Path) -> None:
    (tmp_path / "my_ext").mkdir()
    assert yxp_tool.main(
        ["--create", "my_ext", "--dir", str(tmp_path), "--force"]
    ) == 0
    assert (tmp_path / "my_ext" / "manifest").exists()


def test_created_scaffold_packs_and_verifies(tmp_path: Path) -> None:
    src = tmp_path / "fresh"
    assert yxp_tool.main(["--create", "fresh", "--dir", str(src)]) == 0
    scaffold = src / "fresh"
    out = tmp_path / "fresh.yxp"
    assert yxp_tool.main(["--pack", str(scaffold), "--output", str(out)]) == 0
    assert yxp_tool.main(["--verify", str(out)]) == 0


# ---------------------------------------------------------------- --pack


def test_pack_requires_manifest(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "mod.py").write_text("x", encoding="utf-8")
    assert yxp_tool.main(["--pack", str(src)]) == 1
    assert "missing 'manifest'" in capsys.readouterr().err


def test_pack_rejects_hand_written_files_field(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "manifest").write_text(
        json.dumps({"name": "x", "files": ["mod.py"]}), encoding="utf-8"
    )
    (src / "mod.py").write_text("x", encoding="utf-8")
    assert yxp_tool.main(["--pack", str(src)]) == 1
    assert "'files'" in capsys.readouterr().err


def test_pack_rejects_missing_name(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "manifest").write_text("{}", encoding="utf-8")
    assert yxp_tool.main(["--pack", str(src)]) == 1
    assert "'name'" in capsys.readouterr().err


def test_pack_rejects_missing_source_dir(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert yxp_tool.main(["--pack", str(tmp_path / "nope")]) == 1
    assert "not a directory" in capsys.readouterr().err


def test_pack_rejects_name_outside_the_regex(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A manifest name like ``../evil`` cannot steer the default output."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "manifest").write_text(
        json.dumps({"name": "../evil"}), encoding="utf-8"
    )
    (src / "mod.py").write_text("x", encoding="utf-8")
    assert yxp_tool.main(["--pack", str(src)]) == 1
    assert "must match" in capsys.readouterr().err
    assert not (Path.cwd() / ".." / "evil.yxp").exists()


def test_pack_rejects_non_string_metadata_fields(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A numeric ``version`` would pack but never install -- reject it."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "manifest").write_text(
        json.dumps({"name": "demo", "version": 1.0}), encoding="utf-8"
    )
    (src / "mod.py").write_text("x", encoding="utf-8")
    out = tmp_path / "demo.yxp"
    assert yxp_tool.main(["--pack", str(src), "--output", str(out)]) == 1
    assert "'version' must be a string" in capsys.readouterr().err
    assert not out.exists()  # rejected before any archive is written


def test_pack_reverify_failure_leaves_no_archive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A post-write verification defect drops the freshly built archive."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "manifest").write_text(json.dumps({"name": "x"}), encoding="utf-8")
    (src / "mod.py").write_text("x", encoding="utf-8")
    out = tmp_path / "x.yxp"
    real = yxp.read_package

    def flaky(path: Path) -> yxp.YxpPackage:
        real(path)  # the written archive is fine; simulate a later defect
        raise yxp.YxpError("simulated verification failure")

    monkeypatch.setattr(yxp, "read_package", flaky)
    assert yxp_tool.main(["--pack", str(src), "--output", str(out)]) == 1
    assert not out.exists()  # uninstallable archive dropped


def test_pack_output_directory_is_rejected(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """``--output`` pointing at a directory fails cleanly, even with --force."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "manifest").write_text(json.dumps({"name": "x"}), encoding="utf-8")
    (src / "mod.py").write_text("x", encoding="utf-8")
    out = tmp_path / "out.yxp"
    out.mkdir()
    assert yxp_tool.main(["--pack", str(src), "--output", str(out), "--force"]) == 1
    assert "is a directory" in capsys.readouterr().err
    assert out.is_dir()  # the directory itself is untouched


def test_pack_refuses_overwrite_without_force(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "manifest").write_text(json.dumps({"name": "x"}), encoding="utf-8")
    (src / "mod.py").write_text("x", encoding="utf-8")
    out = tmp_path / "x.yxp"
    out.write_bytes(b"precious")
    assert yxp_tool.main(["--pack", str(src), "--output", str(out)]) == 1
    assert out.read_bytes() == b"precious"
    assert yxp_tool.main(
        ["--pack", str(src), "--output", str(out), "--force"]
    ) == 0
    assert out.read_bytes() != b"precious"


def test_pack_writes_manifest_checksum_and_payload(tmp_path: Path) -> None:
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
    assert yxp_tool.main(["--pack", str(src), "--output", str(out)]) == 0
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
    assert yxp_tool.main(["--pack", str(src)]) == 0
    assert (Path.cwd() / "demo.yxp").exists()
    (Path.cwd() / "demo.yxp").unlink()


def test_pack_uses_deflate_compression(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "manifest").write_text(json.dumps({"name": "big"}), encoding="utf-8")
    (src / "data.txt").write_bytes(b"A" * 10000)
    out = tmp_path / "big.yxp"
    assert yxp_tool.main(["--pack", str(src), "--output", str(out)]) == 0
    with zipfile.ZipFile(out) as zf:
        info = zf.getinfo("data.txt")
    assert info.compress_type == zipfile.ZIP_DEFLATED
    assert info.compress_size < info.file_size


def test_pack_reports_unreadable_payload_and_cleans_up(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "manifest").write_text(json.dumps({"name": "x"}), encoding="utf-8")
    (src / "mod.py").write_text("x", encoding="utf-8")
    out = tmp_path / "x.yxp"

    def boom(path: Path) -> str:
        raise OSError("payload vanished")

    monkeypatch.setattr(yxp_tool, "_digest", boom)
    with pytest.raises(yxp.YxpError, match="payload vanished"):
        yxp_tool.build_package(src, out)
    assert not out.exists()  # partial archive dropped


def test_create_hint_uses_posix_separators(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert yxp_tool.main(["--create", "my_ext", "--dir", str(tmp_path)]) == 0
    hint = capsys.readouterr().out.rsplit("next:", 1)[1]
    assert "\\" not in hint
    assert "my_ext" in hint


# ---------------------------------------------------------------- --verify


def test_verify_accepts_valid_package(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    pkg = make_yxp(tmp_path / "hello.yxp", {"hello.py": b"x"})
    assert yxp_tool.main(["--verify", str(pkg)]) == 0
    out = capsys.readouterr().out
    assert "hello 1.0.0" in out
    assert "checksums verified" in out


def test_verify_rejects_bad_package(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bad = tmp_path / "bad.yxp"
    bad.write_bytes(b"nope")
    assert yxp_tool.main(["--verify", str(bad)]) == 1
    assert "error:" in capsys.readouterr().err


def test_modes_are_mutually_exclusive() -> None:
    with pytest.raises(SystemExit):
        yxp_tool.build_parser().parse_args(
            ["--create", "x", "--pack", "y"]
        )


# ------------------------------------------------- example package roundtrip


def test_example_directory_packs_and_installs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = tmp_path / "hello_yxp.yxp"
    assert yxp_tool.main(["--pack", str(EXAMPLE_DIR), "--output", str(out)]) == 0
    monkeypatch.setattr(yxp, "default_extensions_dir", lambda: tmp_path / "exts")
    with patch("yate.logs.crash.install"):
        assert yate_main(["--install-extension", str(out)]) == 0
    report = yxp.list_packages(tmp_path / "exts")[0]
    assert report.name == "hello_yxp"
    assert report.version == "1.0.0"
    assert report.file_count == 1
