# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build spec for the standalone yate executable (one-folder).

Build with (after ``pip install -e ".[build,ts]"``), from the repository root::

    pyinstaller pack/yate.spec

The output is dist/yate/yate.exe (a one-folder build). Resources are located
at runtime through yate.paths, which checks sys._MEIPASS, so the data layout
shared with pack/_common.py must mirror the source tree (everything lands
inside a top-level ``yate`` package folder in the bundle).

For a single self-extracting exe instead, use ``pack/yate-onefile.spec``.
Every build step the two specs share (icon, hidden imports, tree-sitter
binaries, dist-info metadata, data files, extensions Tree) lives in
``pack/_common.py``; this file keeps only the one-folder Analysis/EXE/COLLECT
differences.

This spec lives in pack/, one level below the repository root. PyInstaller
resolves every source path in the spec relative to the spec's own directory
(SPECPATH), so PROJECT_ROOT is derived explicitly and all entry/data paths are
absolute; the destination prefixes still mirror the ``yate/...`` source tree.

Note: ``*.spec`` is git-ignored by default; this file is tracked on purpose
(``git add -f pack/yate.spec``).
"""

import os
import sys

# SPECPATH is injected by PyInstaller: the directory containing this file
# (.../pack).  Spec files are exec'd as plain scripts, so the spec directory
# is put on sys.path explicitly before importing _common, and the repository
# root before _common imports the "yate" package for its dist metadata.
SPEC_DIR = os.path.abspath(SPECPATH)
if SPEC_DIR not in sys.path:
    sys.path.insert(0, SPEC_DIR)
PROJECT_ROOT = os.path.dirname(SPEC_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import _common  # noqa: E402

inputs = _common.collect(SPECPATH)

a = Analysis(
    [inputs.pkg_path("__main__.py")],
    pathex=[PROJECT_ROOT],
    binaries=inputs.ts_binaries,
    datas=inputs.datas + inputs.ts_datas + inputs.yate_datas,
    hiddenimports=inputs.hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
a.datas += inputs.extensions_tree
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="yate",
    icon=inputs.icon,
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
