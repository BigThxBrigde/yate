"""Single authoritative entry point for yate's on-disk resource locations.

Read-only data shipped with the program (manuals, fonts, bundled extensions,
docs, the yaterc template) lives inside the package tree.  Resolving those
paths through this module -- instead of ``Path(__file__)`` math scattered
around the code base -- keeps one story for three run modes:

* source checkout / editable install -- the real ``yate/`` directory;
* wheel install -- the installed package directory;
* PyInstaller bundle (``sys.frozen``) -- the extracted ``yate/`` folder
  inside ``sys._MEIPASS`` (onefile) or next to the executable (onedir).

Writable, user-edited data (``~/.yate/yaterc``, themes, user extensions) is
*not* here; it is resolved by :mod:`yate.config` and the CLI.
"""

from __future__ import annotations

import sys
from pathlib import Path

#: Folder name of the bundled-extension directory inside the package.
EXTENSIONS_DIRNAME = "extensions"
#: Folder name of the bundled bilingual documentation inside the package.
DOCS_DIRNAME = "docs"
#: Filename of the shipped yaterc template (copy it to ``~/.yate/yaterc``).
EXAMPLE_RC_FILENAME = "yaterc.example"


def package_root() -> Path:
    """Directory containing the package's read-only data.

    Under a PyInstaller build the package data is collected under
    ``<bundle>/yate``; everywhere else it is the directory holding this
    module.
    """
    meipass = getattr(sys, "_MEIPASS", None)
    if getattr(sys, "frozen", False) and isinstance(meipass, str):
        return Path(meipass) / "yate"
    return Path(__file__).resolve().parent


def bundled_extensions_dir() -> Path:
    """The directory of extensions shipped with yate (auto-loaded)."""
    return package_root() / EXTENSIONS_DIRNAME


def bundled_docs_dir() -> Path:
    """The directory of bundled bilingual ``*.md`` guides."""
    return package_root() / DOCS_DIRNAME


def bundled_doc(name: str) -> Path:
    """Path of a bundled guide, e.g. ``bundled_doc("lsp.en.md")``."""
    return bundled_docs_dir() / name


def example_rc_path() -> Path:
    """The shipped ``yaterc.example`` template path."""
    return package_root() / EXAMPLE_RC_FILENAME
