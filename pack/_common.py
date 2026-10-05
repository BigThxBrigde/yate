# -*- mode: python ; coding: utf-8 -*-
"""Shared PyInstaller build logic for ``pack/yate.spec`` and ``pack/yate-onefile.spec``.

The two spec files keep only their ``Analysis`` / ``EXE`` / ``COLLECT``
differences; every other build step (icon resolution, hidden imports, the
excluded-modules inventory, tree-sitter binaries, dist-info metadata, data
files and the bundled extensions ``Tree``) is gathered once by :func:`collect`
and handed to the spec as a :class:`SpecInputs`.

PyInstaller exec's spec files as plain scripts (not imports), so each spec
puts its own directory (``SPECPATH``) on ``sys.path`` before doing
``import _common``.  PyInstaller ships no type stubs, hence its modules are
imported dynamically here and the opaque values they return are typed as
``Any`` -- the same documented escape hatch :mod:`tools.pack.icon` uses for
the optional Pillow dependency.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from dataclasses import dataclass
from typing import Any

#: Icon consumed by ``EXE(icon=...)``: built by ``python -m tools.pack icon``
#: (re-run after the logo changes).  Linux builds (pack/pack.sh) get no icon;
#: ``EXE(icon=None)`` is the default.
_ICON_NAME: str = "yate.ico"

#: The optional tree-sitter backend loads these packages lazily via
#: importlib.import_module (see yate.editor_syntax.ts_backend.languages),
#: which static analysis cannot follow -- they must be collected explicitly.
#: The packages come from the [ts] extra; when it is absent in the build
#: environment the executable simply ships regex-only (the loop skips them).
_TS_PACKAGES: tuple[str, ...] = (
    "tree_sitter",
    "tree_sitter_python",
    "tree_sitter_bash",
    "tree_sitter_c",
    "tree_sitter_cpp",
    "tree_sitter_c_sharp",
    "tree_sitter_rust",
    "tree_sitter_go",
    "tree_sitter_java",
    "tree_sitter_javascript",
    "tree_sitter_typescript",
    "tree_sitter_html",
    "tree_sitter_css",
    "tree_sitter_xml",
    "tree_sitter_json",
    "tree_sitter_toml",
    "tree_sitter_yaml",
    "tree_sitter_sql",
    "tree_sitter_lua",
    "tree_sitter_make",
    "tree_sitter_powershell",
    "tree_sitter_php",
    "tree_sitter_ruby",
    "tree_sitter_markdown",
    "tree_sitter_zig",
)

#: Third-party packages dropped from the frozen graph (issue IKJPVB).  They are
#: pulled in transitively but never touched at runtime, so shipping them is
#: pure payload: ``PIL`` arrives through ``pygments.formatters.img``, whose
#: ``try: from PIL import Image, ImageDraw, ImageFont`` only needs an image
#: formatter yate never uses -- and yate itself imports Pillow solely to
#: regenerate the committed ``pack/yate.ico`` (``tools/pack/icon.py`` imports
#: it dynamically, outside the frozen entry point).  Measured on the one-folder
#: bundle: PIL cost 13.1 MiB of 60.6 MiB.  ``numpy`` is Pillow's optional array
#: backend (``PIL._typing`` imports it conditionally), excluded with it.
#: Re-derive the inventory from ``build/<name>/xref-<name>.html`` and
#: ``warn-<name>.txt`` after a build before adding anything here.
EXCLUDES: tuple[str, ...] = (
    "PIL",
    "numpy",
)


@dataclass(frozen=True)
class SpecInputs:
    """Everything a spec needs besides its own Analysis/EXE/COLLECT block."""

    #: Repository root (the parent of the spec's directory).
    project_root: str
    #: Absolute icon path on Windows, ``None`` elsewhere.
    icon: str | None
    #: yate's own submodules plus the tree-sitter packages, when installed.
    hiddenimports: list[str]
    #: Modules PyInstaller must not pull in -- see :data:`EXCLUDES`.
    excludes: list[str]
    # PyInstaller returns untyped values (no stubs shipped); they are passed
    # through to Analysis/EXE verbatim, so Any is the honest annotation.
    ts_binaries: list[Any]  # noqa: Any - PyInstaller has no type stubs
    ts_datas: list[Any]  # noqa: Any - PyInstaller has no type stubs
    yate_datas: list[Any]  # noqa: Any - PyInstaller has no type stubs
    datas: list[Any]  # noqa: Any - PyInstaller has no type stubs
    #: The bundled-extensions Tree, appended to ``a.datas`` by the spec.
    extensions_tree: Any  # noqa: Any - PyInstaller has no type stubs

    def pkg_path(self, *parts: str) -> str:
        """Absolute path to a file or directory inside the yate source tree."""
        return os.path.join(self.project_root, "yate", *parts)


def _pkg_path(project_root: str, *parts: str) -> str:
    """Absolute path to a file or directory inside the yate source tree."""
    return os.path.join(project_root, "yate", *parts)


def collect(specpath: str) -> SpecInputs:
    """Gather the shared build inputs for a spec living in *specpath*.

    *specpath* is PyInstaller's injected ``SPECPATH`` (the directory holding
    the spec file); the repository root is its parent.  The caller must have
    put the repository root on ``sys.path`` already, because the ``yate``
    package is imported here for its dist metadata.
    """
    building = importlib.import_module("PyInstaller.building.datastruct")
    hooks = importlib.import_module("PyInstaller.utils.hooks")
    project_root = os.path.dirname(os.path.abspath(specpath))
    icon: str | None = (
        os.path.join(os.path.abspath(specpath), _ICON_NAME)
        if sys.platform == "win32"
        else None
    )
    # yate's own submodules are statically imported; collect the full package
    # so a newly added screen/service never silently drops out of a frozen
    # build (collect_submodules resolves "yate" via sys.path).
    hiddenimports: list[str] = list(hooks.collect_submodules("yate"))
    ts_binaries: list[Any] = []  # noqa: Any - PyInstaller has no type stubs
    ts_datas: list[Any] = []  # noqa: Any - PyInstaller has no type stubs
    for ts_pkg in _TS_PACKAGES:
        if importlib.util.find_spec(ts_pkg) is None:
            continue
        hiddenimports += hooks.collect_submodules(ts_pkg)
        ts_binaries += hooks.collect_dynamic_libs(ts_pkg)
        # dist-info metadata: importlib.metadata.version() probes (yate --diag
        # and the Windows blocked-version guard) rely on it.
        ts_datas += hooks.copy_metadata(ts_pkg)
    # yate's own + core dependencies' dist-info: diagnostics._section_packages
    # derives the [packages] inventory from importlib.metadata.requires("yate")
    # and probes the versions with importlib.metadata.version() -- both read
    # dist-info metadata that must ship inside the frozen app.  Core
    # dependencies derive from yate's own dist metadata (same parser as
    # yate.diagnostics): whatever pyproject lists without an extra marker
    # ships its dist-info, so a new core dep never needs a spec edit;
    # duplicate datas entries are deduplicated by PyInstaller.
    yate_datas: list[Any] = list(hooks.copy_metadata("yate"))  # noqa: Any
    dist_meta = importlib.import_module("yate.dist_meta")
    for core_pkg in sorted(dist_meta.requirement_groups().get("core", {}).values()):
        yate_datas += hooks.copy_metadata(core_pkg)
    # Bundled extensions are loaded from disk at runtime via
    # importlib.util.spec_from_file_location (not normal imports), so the .py
    # scripts must ship as data files -- as must every non-code resource.  Tree
    # (rather than a plain directory tuple) keeps development bytecode caches
    # out of the distributable.  The destination prefix "yate/..." mirrors the
    # source layout and is what yate.paths.package_root() expects inside
    # sys._MEIPASS.
    extensions_tree: Any = building.Tree(  # noqa: Any - PyInstaller has no stubs
        _pkg_path(project_root, "extensions"),
        prefix="yate/extensions",
        excludes=["__pycache__", "*.pyc", "*.pyo"],
    )
    datas: list[Any] = [  # noqa: Any - PyInstaller has no type stubs
        (_pkg_path(project_root, "resources"), "yate/resources"),
        (_pkg_path(project_root, "docs"), "yate/docs"),
        # tree-sitter highlight queries are package data read via
        # Path(__file__); PyInstaller only collects code from the package,
        # so ship them explicitly.
        (
            _pkg_path(project_root, "editor_syntax", "ts_backend", "queries"),
            "yate/editor_syntax/ts_backend/queries",
        ),
        (_pkg_path(project_root, "yaterc.example"), "yate"),
    ]
    return SpecInputs(
        project_root=project_root,
        icon=icon,
        hiddenimports=hiddenimports,
        excludes=list(EXCLUDES),
        ts_binaries=ts_binaries,
        ts_datas=ts_datas,
        yate_datas=yate_datas,
        datas=datas,
        extensions_tree=extensions_tree,
    )
