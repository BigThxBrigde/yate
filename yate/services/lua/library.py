"""Light half of the Lua bridge: availability probe and library source.

This module never imports ``lupa``: it only probes for the package with
:func:`importlib.util.find_spec` (so merely asking never pays the
C-extension import cost) and reads the bundled Lua API library from the
package resources.  The runtime half lives in
:mod:`yate.services.lua.runtime` -- the single place in yate that touches
the ``lupa`` package itself.
"""

from __future__ import annotations

import importlib.util

from yate.paths import bundled_extensions_dir


def is_lua_available() -> bool:
    """True when the ``lupa`` package is importable.

    Probed with :func:`importlib.util.find_spec` instead of a real import so
    merely asking never pays the C-extension import cost; a probe error
    (e.g. a broken half-install) counts as "not available".
    """
    try:
        return importlib.util.find_spec("lupa") is not None
    except (ImportError, ValueError):
        return False


def lua_api_library_source() -> str:
    """Read the bundled Lua API library ``_yate.lua`` (one read per call).

    An unreadable resource means a broken installation: fail fast the same
    way :func:`yate.paths.load_tcss` does instead of confusing the user
    with an unrelated Lua error later.
    """
    path = bundled_extensions_dir() / "_yate.lua"
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(
            f"bundled resource {path} could not be read; "
            "the yate installation is broken"
        ) from exc
