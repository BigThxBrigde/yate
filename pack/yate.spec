# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build spec for the standalone yate executable (one-folder).

Build with (after ``pip install -e ".[build,ts]"``), from the repository root::

    pyinstaller pack/yate.spec

On Windows and on POSIX alike the output is dist/yate/ with the executable
next to a single contents directory::

    dist/yate/yate.exe          dist/yate/yate on Linux/macOS
    dist/yate/runtime/...       interpreter runtime, extension modules,
                                and the bundled ``yate`` package data

PyInstaller >=6 calls that directory ``_internal``; yate ships it as
``runtime`` instead, so both platforms end up with one identical layout and
the bundle does not read like a build-internal detail (issue IKJPVB, note
_51452120).  A *flat* layout -- runtime files right next to the executable --
is deliberately not used: a POSIX executable has no ``.exe`` suffix, so it
would be ``dist/yate/yate``, exactly the path the bundled ``yate/`` package
data has to occupy as a directory, and COLLECT aborts on that collision.

Resources are located at runtime through yate.paths, which checks
sys._MEIPASS; the bootloader points that at the contents directory, so the
data layout shared with pack/_common.py must mirror the source tree
(everything lands inside a top-level ``yate`` package folder in the bundle).

Modules that are dragged in transitively but never used at runtime (Pillow
and numpy) are dropped from the frozen graph via
``pack/_common.py``'s ``EXCLUDES``.

For a single self-extracting exe instead, use ``pack/yate-onefile.spec``.
Every build step the two specs share (icon, hidden imports, excludes,
tree-sitter binaries, dist-info metadata, data files, extensions Tree) lives
in ``pack/_common.py``; this file keeps only the one-folder Analysis/EXE/COLLECT
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

#: Name of the one contents directory this bundle keeps beside the executable.
#: PyInstaller >=6 defaults to ``_internal``; ``runtime`` is the cross-platform
#: name yate ships so that Windows and POSIX bundles have the same layout.  The
#: value is part of the product's layout contract (the docs quote the tree), and
#: tests/test_pack_spec.py pins both the name and the rules it has to obey.
CONTENTS_DIRNAME: str = "runtime"

a = Analysis(
    [inputs.pkg_path("__main__.py")],
    pathex=[PROJECT_ROOT],
    binaries=inputs.ts_binaries,
    datas=inputs.datas + inputs.ts_datas + inputs.yate_datas,
    hiddenimports=inputs.hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=inputs.excludes,
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
    # One contents directory on every platform (issue IKJPVB): PyInstaller >=6
    # defaults to a ``_internal/`` subdirectory, which reads like a build
    # detail, so the bundle ships it as ``runtime/`` instead -- identical on
    # Windows and POSIX.  COLLECT inherits this from EXE.
    #
    # The flat layout ("." -- files right next to the exe) stays off the table:
    # it is unreachable on POSIX, where the suffix-less executable would be
    # ``dist/yate/yate``, colliding with the bundled ``yate/`` package
    # directory COLLECT has to create (its makedirs turns that collision into a
    # hard SystemExit).  Renaming keeps both platforms alike instead.
    contents_directory=CONTENTS_DIRNAME,
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
