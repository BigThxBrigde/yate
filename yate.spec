# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build spec for the standalone yate executable.

Build with (after ``pip install -e ".[build]"``)::

    pyinstaller yate.spec

The output is dist/yate/yate.exe (a one-folder build). Resources are located
at runtime through yate.paths, which checks sys._MEIPASS, so the data layout
below must mirror the source tree (everything lands inside a top-level
``yate`` package folder in the bundle).

For a single self-extracting exe instead, use ``yate-onefile.spec``.

Note: ``*.spec`` is git-ignored by default; this file is tracked on purpose
(``git add -f yate.spec``).
"""

from PyInstaller.utils.hooks import collect_submodules

# yate's own submodules are statically imported; collect the full package so a
# newly added screen/service never silently drops out of a frozen build.
hiddenimports = collect_submodules("yate")

# Bundled extensions are loaded from disk at runtime via
# importlib.util.spec_from_file_location (not normal imports), so the .py
# scripts must ship as data files -- as must every non-code resource.
datas = [
    ("yate/resources", "yate/resources"),
    ("yate/docs", "yate/docs"),
    ("yate/extensions", "yate/extensions"),
    ("yate/yaterc.example", "yate"),
]

a = Analysis(
    ["yate/__main__.py"],
    pathex=[],
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
