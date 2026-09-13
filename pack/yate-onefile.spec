# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for a single-file yate executable (onefile).

Build with (after ``pip install -e ".[build,ts]"``), from the repository root::

    pyinstaller pack/yate-onefile.spec

The output is the standalone dist/yate.exe (Windows) or dist/yate (Linux). At
every launch the bootloader extracts the bundle into a temporary directory
(``sys._MEIPASS``) and removes it on exit, so there is nothing to ship next to
the executable.

Runtime resource reads are unaffected: yate.paths checks ``sys._MEIPASS`` and
resolves the package tree at ``<tmp>/yate``. The data layout below must mirror
the source tree so that the on-disk paths (docs, bundled extensions loaded via
importlib, fonts, manuals, yaterc.example) keep working after extraction.

Trade-offs vs. the one-folder build (``pack/yate.spec``): a single portable
file, but slower startup (extraction on every run) and some antivirus software
is stricter with onefile exes.

This spec lives in pack/, one level below the repository root. PyInstaller
resolves every source path in the spec relative to the spec's own directory
(SPECPATH), so PROJECT_ROOT is derived explicitly and all entry/data paths are
absolute; the destination prefixes still mirror the ``yate/...`` source tree.

Note: ``*.spec`` is git-ignored by default; this file is tracked on purpose
(``git add -f pack/yate-onefile.spec``).
"""

import importlib.util
import os
import sys

from PyInstaller.building.datastruct import Tree
from PyInstaller.utils.hooks import (
    collect_dynamic_libs,
    collect_submodules,
    copy_metadata,
)

# SPECPATH is injected by PyInstaller: the directory containing this file
# (…/pack). The actual sources and resources sit one level above it.
PROJECT_ROOT = os.path.dirname(os.path.abspath(SPECPATH))

# Make the package importable regardless of the directory pyinstaller was
# invoked from (collect_submodules below resolves "yate" via sys.path).
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def pkg_path(*parts: str) -> str:
    """Absolute path to a file or directory inside the yate source tree."""
    return os.path.join(PROJECT_ROOT, "yate", *parts)


# yate's own submodules are statically imported; collect the full package so a
# newly added screen/service never silently drops out of a frozen build.
hiddenimports = collect_submodules("yate")

# The optional tree-sitter backend loads tree_sitter and the built-in grammar
# packs lazily via importlib.import_module (see
# yate.editor_syntax.ts_backend.languages), which static analysis cannot
# follow -- without this the frozen app reports the grammars "not installed".
# The packages come from the [ts] extra; when it is absent in the build
# environment the executable simply ships regex-only (the loop skips them).
ts_binaries = []
ts_datas = []
for _ts_pkg in ("tree_sitter", "tree_sitter_python", "tree_sitter_bash"):
    if importlib.util.find_spec(_ts_pkg) is None:
        continue
    hiddenimports += collect_submodules(_ts_pkg)
    ts_binaries += collect_dynamic_libs(_ts_pkg)
    # dist-info metadata: importlib.metadata.version() probes (yate --diag
    # and the Windows blocked-version guard) rely on it.
    ts_datas += copy_metadata(_ts_pkg)

# Bundled extensions are loaded from disk at runtime via
# importlib.util.spec_from_file_location (not normal imports), so the .py
# scripts must ship as data files -- as must every non-code resource. Tree
# (rather than a plain directory tuple) keeps development bytecode caches out
# of the distributable.  The destination prefix "yate/..." mirrors the source
# layout and is what yate.paths.package_root() expects inside sys._MEIPASS.
extensions_tree = Tree(
    pkg_path("extensions"),
    prefix="yate/extensions",
    excludes=["__pycache__", "*.pyc", "*.pyo"],
)
datas = [
    (pkg_path("resources"), "yate/resources"),
    (pkg_path("docs"), "yate/docs"),
    # tree-sitter highlight queries are package data read via Path(__file__);
    # PyInstaller only collects code from the package, so ship them explicitly.
    (
        pkg_path("editor_syntax", "ts_backend", "queries"),
        "yate/editor_syntax/ts_backend/queries",
    ),
    (pkg_path("yaterc.example"), "yate"),
]

a = Analysis(
    [pkg_path("__main__.py")],
    pathex=[PROJECT_ROOT],
    binaries=ts_binaries,
    datas=datas + ts_datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
a.datas += extensions_tree
pyz = PYZ(a.pure)

# Onefile: binaries and datas are embedded in the exe itself (no COLLECT step).
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="yate",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
)
