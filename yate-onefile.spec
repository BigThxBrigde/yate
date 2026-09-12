# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for a single-file yate executable (onefile).

Build with (after ``pip install -e ".[build]"``)::

    pyinstaller yate-onefile.spec

The output is the standalone dist/yate.exe. At every launch the bootloader
extracts the bundle into a temporary directory (``sys._MEIPASS``) and removes
it on exit, so there is nothing to ship next to the exe.

Runtime resource reads are unaffected: yate.paths checks ``sys._MEIPASS`` and
resolves the package tree at ``<tmp>/yate``. The data layout below must mirror
the source tree so that the on-disk paths (docs, bundled extensions loaded via
importlib, fonts, manuals, yaterc.example) keep working after extraction.

Trade-offs vs. the one-folder build (``yate.spec``): a single portable file,
but slower startup (extraction on every run) and some antivirus software is
stricter with onefile exes.

Note: ``*.spec`` is git-ignored by default; this file is tracked on purpose
(``git add -f yate-onefile.spec``).
"""

from PyInstaller.utils.hooks import collect_submodules

# yate's own submodules are statically imported; collect the full package so a
# newly added screen/service never silently drops out of a frozen build.
hiddenimports = collect_submodules("yate")

# Bundled extensions are loaded from disk at runtime via
# importlib.util.spec_from_file_location (not normal imports), so the .py
# scripts must ship as data files -- as must every non-code resource.  The
# destination prefix "yate/..." mirrors the source layout and is what
# yate.paths.package_root() expects inside sys._MEIPASS.
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
