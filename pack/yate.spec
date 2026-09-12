# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build spec for the standalone yate executable (one-folder).

Build with (after ``pip install -e ".[build]"``), from the repository root::

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

import os
import sys

from PyInstaller.utils.hooks import collect_submodules

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

# Bundled extensions are loaded from disk at runtime via
# importlib.util.spec_from_file_location (not normal imports), so the .py
# scripts must ship as data files -- as must every non-code resource.
datas = [
    (pkg_path("resources"), "yate/resources"),
    (pkg_path("docs"), "yate/docs"),
    (pkg_path("extensions"), "yate/extensions"),
    (pkg_path("yaterc.example"), "yate"),
]

a = Analysis(
    [pkg_path("__main__.py")],
    pathex=[PROJECT_ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="yate",
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
