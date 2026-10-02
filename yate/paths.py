"""Single authoritative entry point for yate's on-disk resource locations.

Read-only data whose path is needed from code (bundled auto-loaded extensions
and fonts) lives inside the package tree; resolving it through this module --
instead of ``Path(__file__)`` math scattered around the code base -- keeps one
story for three run modes:

* source checkout / editable install -- the real ``yate/`` directory;
* wheel install -- the installed package directory;
* PyInstaller bundle (``sys.frozen``) -- the extracted ``yate`` folder
  inside ``sys._MEIPASS`` (onefile) or next to the executable (onedir).

Other shipped data does not need a helper here, with one exception: the
bundled TCSS stylesheets are read through :func:`load_tcss` (the shell's
``app.tcss`` and the screensaver's ``screensaver.tcss`` -- one public loader
so every consumer shares the same fail-fast contract), while manuals are read
via ``importlib.resources.files("yate.resources")`` (see editor_view.manual)
and the ``docs`` guides plus the ``yaterc.example`` template are plain
shipped files users open/copy by their documented package-relative paths.

Writable, user-edited data (``~/.yate/yaterc``, themes, user extensions) is
*not* here; it is resolved by :mod:`yate.config` and the CLI.
"""

from __future__ import annotations

import sys
from importlib.resources import files
from pathlib import Path

#: Folder name of the bundled-extension directory inside the package.
EXTENSIONS_DIRNAME: str = "extensions"


def package_root() -> Path:
    """Directory containing the package's read-only data.

    Under a PyInstaller build the package data is collected under
    ``<bundle>/yate``; everywhere else it is the directory holding this
    module. A non-string (or missing) ``sys._MEIPASS`` falls back to the
    normal layout rather than raising.
    """
    meipass = getattr(sys, "_MEIPASS", None)
    if getattr(sys, "frozen", False) and isinstance(meipass, str):
        return Path(meipass) / "yate"
    return Path(__file__).resolve().parent


def bundled_extensions_dir() -> Path:
    """The directory of extensions shipped with yate (auto-loaded)."""
    return package_root() / EXTENSIONS_DIRNAME


def load_tcss(name: str) -> str:
    """Read a bundled TCSS stylesheet from ``yate/resources``.

    *name* is the file name (``"app.tcss"`` for the shell stylesheet,
    ``"screensaver.tcss"`` for the screensaver screen).  The stylesheets are
    bundled resources rather than inline literals so they get editor syntax
    highlighting and ship through the same packaging channels as every other
    file under ``yate/resources`` (hatchling wheel and both PyInstaller specs
    already collect that directory whole).  An unreadable resource means a
    broken installation: fail fast with an actionable message instead of a
    confusing stylesheet error later.
    """
    try:
        return files("yate.resources").joinpath(name).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise RuntimeError(
            f"bundled resource yate/resources/{name} could not be read; "
            "the yate installation is broken"
        ) from exc
