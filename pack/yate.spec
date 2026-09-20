# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build spec for the standalone yate executable (one-folder).

Build with (after ``pip install -e ".[build,ts]"``), from the repository root::

    pyinstaller pack/yate.spec

The output is dist/yate/yate.exe (a one-folder build). Resources are located
at runtime through yate.paths, which checks sys._MEIPASS, so the data layout
below must mirror the source tree (everything lands inside a top-level
``yate`` package folder in the bundle).

For a single self-extracting exe instead, use ``pack/yate-onefile.spec``.

This spec lives in pack/, one level below the repository root. PyInstaller
resolves every source path in the spec relative to the spec's own directory
(SPECPATH), so PROJECT_ROOT is derived explicitly and all entry/data paths are
absolute; the destination prefixes still mirror the ``yate/...`` source tree.

Note: ``*.spec`` is git-ignored by default; this file is tracked on purpose
(``git add -f pack/yate.spec``).
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


# Executable icon: PyInstaller takes a .ico on Windows (a .icns on macOS) --
# the JPEG logo cannot be passed directly, so yate/yate.jpg is converted into
# pack/yate.ico by "python -m tools.pack icon" (re-run after the logo changes).
# Linux builds (pack/pack.sh) get no icon; EXE(icon=None) is the default.
ICON = (
    os.path.join(os.path.abspath(SPECPATH), "yate.ico")
    if sys.platform == "win32"
    else None
)


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
# of the distributable.
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

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="yate",
    icon=ICON,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="yate",
)
