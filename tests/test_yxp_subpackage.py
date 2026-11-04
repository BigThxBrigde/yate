"""Structural tests for the yxp subpackage (big-module-split-2 wave-3).

Guards the facade contract that the unchanged yxp test suite depends on:
absolute imports only, per-file size, ASCII comments/docstrings, the
frozen submodule logger name, and the patch surface -- every
``monkeypatch.setattr(yxp, ...)`` target, ``patch("yate.services.yxp...")
`` string target and ``yxp.<attr>`` reference in the yxp test files must
stay resolvable on the facade namespace.
"""

from __future__ import annotations

# pyright: reportPrivateUsage=false
# The loggers asserted below are private module attributes of the
# submodules; asserting their frozen name is the point.
import ast
from pathlib import Path

#: Every ``monkeypatch.setattr(yxp, ...)`` / ``patch("yate.services.yxp...")
#: `` target and every ``yxp.<attr>`` reference in the yxp test files and
#: consumers, enumerated 2026-11-04 before the split (write targets cite
#: their test locations).  ``__all__`` on the facade must equal this set:
#: the plan correction freezes ``__all__`` to the re-exported, importable
#: surface, of which this patch surface is the exhaustive inventory.
PATCH_SURFACE: frozenset[str] = frozenset({
    # write targets (patched on the facade namespace)
    "_write_record",           # tests/test_yxp.py L346, L365
    "read_package",            # tests/test_yxp.py L392; tests/test_tools_yxp.py L225
    "os",                      # tests/test_yxp.py L419 patches yxp.os.replace
    "MAX_MEMBER_BYTES",        # tests/test_yxp.py L627, L646
    "default_extensions_dir",  # tests/test_yxp.py L897/L913/L927/L955; tools L373
    "uninstall_package",       # tests/test_cli.py L657 string patch
    # read references in tests/test_yxp.py
    "_read_member",            # L656
    "_rollback_files",         # L700
    "_restore_stale_files",    # L726
    "RECORDS_DIRNAME",
    "RECORD_SUFFIX",
    "InstallReport",
    "UninstallReport",
    "InstalledPackage",
    "YxpError",
    "YxpPackage",
    "install_package",
    "list_packages",
    "format_install_report",
    "format_uninstall_report",
    "format_package_list",
    # public names referenced by yate/commands.py, yate/cli.py,
    # tools/yxp/cli.py, tests/test_cli.py
    "MANIFEST_NAME",
    "CHECKSUM_NAME",
    "NAME_RE",
    "YxpManifest",
    # remaining public name of the original module
    "MAX_PAYLOAD_BYTES",
})

_PKG = Path("yate/services/yxp")


def test_yxp_subpackage_no_relative_imports() -> None:
    """Every .py in yate/services/yxp/ uses absolute imports only."""
    for py in sorted(_PKG.glob("*.py")):
        src = py.read_text(encoding="utf-8")
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert node.level == 0, (
                    f"{py}: relative import found: {ast.dump(node)}"
                )


def test_yxp_subpackage_all_files_under_threshold() -> None:
    """Every file in the subpackage is under 800 lines."""
    for py in sorted(_PKG.glob("*.py")):
        lines = len(py.read_text(encoding="utf-8").splitlines())
        assert lines <= 800, f"{py}: {lines} lines (over 800)"


def test_yxp_facade_preserves_import_path() -> None:
    """``from yate.services import yxp`` still works."""
    from yate.services import yxp

    assert hasattr(yxp, "read_package")
    assert hasattr(yxp, "install_package")
    assert hasattr(yxp, "uninstall_package")
    assert hasattr(yxp, "list_packages")
    assert hasattr(yxp, "YxpError")
    assert hasattr(yxp, "YxpManifest")
    assert hasattr(yxp, "YxpPackage")


def test_yxp_facade_direct_import() -> None:
    """``from yate.services.yxp import YxpError`` still works."""
    from yate.services.yxp import YxpError, YxpManifest, read_package

    assert YxpError is not None
    assert YxpManifest is not None
    assert read_package is not None


def test_yxp_facade_all_names_resolve() -> None:
    """``__all__`` equals the enumerated patch surface and every name
    resolves on the facade (plan correction 3: exact reconciliation)."""
    from yate.services import yxp

    assert set(yxp.__all__) == PATCH_SURFACE
    for name in yxp.__all__:
        assert hasattr(yxp, name), name


def test_yxp_submodule_loggers_use_frozen_name() -> None:
    """Every submodule logs under "yate.services.yxp", not ``__name__``:
    tests/test_yxp.py asserts caplog records on that frozen logger name."""
    import yate.services.yxp.install as install_mod
    import yate.services.yxp.manifest as manifest_mod
    import yate.services.yxp.records as records_mod

    for module in (manifest_mod, install_mod, records_mod):
        assert module.log.name == "yate.services.yxp", module


def test_yxp_subpackage_ascii_comments() -> None:
    """All new files carry ASCII-only comments and docstrings."""
    for py in sorted(_PKG.glob("*.py")):
        src = py.read_text(encoding="utf-8")
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(
                node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
            ):
                doc = ast.get_docstring(node)
                if doc is not None:
                    assert doc.isascii(), (py, doc[:60])
        for line in src.splitlines():
            stripped = line.lstrip()
            if stripped.startswith("#"):
                comment = stripped[1:].strip()
                assert comment.isascii(), (py, comment)
