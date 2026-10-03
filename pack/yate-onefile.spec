# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for a single-file yate executable (onefile).

Build with (after ``pip install -e ".[build,ts]"``), from the repository root::

    pyinstaller pack/yate-onefile.spec

The output is the standalone dist/yate.exe (Windows) or dist/yate (Linux). At
every launch the bootloader extracts the bundle into a temporary directory
(``sys._MEIPASS``) and removes it on exit, so there is nothing to ship next to
the executable.

Runtime resource reads are unaffected: yate.paths checks ``sys._MEIPASS`` and
resolves the package tree at ``<tmp>/yate``. The data layout shared with
pack/_common.py must mirror the source tree so that the on-disk paths (docs,
bundled extensions loaded via importlib, fonts, manuals, yaterc.example) keep
working after extraction.

Trade-offs vs. the one-folder build (``pack/yate.spec``): a single portable
file, but slower startup (extraction on every run) and some antivirus software
is stricter with onefile exes.

Every build step the two specs share (icon, hidden imports, tree-sitter
binaries, dist-info metadata, data files, extensions Tree) lives in
``pack/_common.py``; this file keeps only the onefile Analysis/EXE
differences.

This spec lives in pack/, one level below the repository root. PyInstaller
resolves every source path in the spec relative to the spec's own directory
(SPECPATH), so PROJECT_ROOT is derived explicitly and all entry/data paths are
absolute; the destination prefixes still mirror the ``yate/...`` source tree.

Note: ``*.spec`` is git-ignored by default; this file is tracked on purpose
(``git add -f pack/yate-onefile.spec``).
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

# Onefile: binaries and datas are embedded in the exe itself (no COLLECT step).
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="yate",
    icon=inputs.icon,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
)
