"""Light half of the Lua bridge: availability probe and library source.

This module never imports ``lupa``: it only probes for the package with
:func:`importlib.util.find_spec` (so merely asking never pays the
C-extension import cost) and reads the bundled Lua API library from the
package resources.  The runtime half lives in
:mod:`yate.services.extensions.lua.runtime` -- the single place in yate that touches
the ``lupa`` package itself.
"""

from __future__ import annotations

import functools
import importlib.util

from yate.paths import bundled_extensions_dir

#: Sub-directory of the bundled extensions holding requirable Lua modules.
#: Loader discovery only globs the top level of the bundled directory, so
#: nothing in here is ever auto-loaded as an extension.
LUA_LIB_DIRNAME: str = "lib"


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


@functools.lru_cache(maxsize=1)
def lua_api_library_source() -> str:
    """Read the bundled Lua API library ``_yate.lua`` (cached after first read).

    The bundled resource is read-only package data, so the source is read
    from disk once per process; every extension runtime reuses the same
    string instead of re-reading and re-reading per extension load.  An
    unreadable resource means a broken installation: fail fast the same
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


@functools.lru_cache(maxsize=1)
def lua_module_sources() -> dict[str, str]:
    """Read every bundled shared Lua module (``lib/*.lua``), keyed by stem.

    The modules are compiled into each extension runtime's
    ``package.preload`` table, so a script reaches them with
    ``require("<stem>")`` and gets a private copy per runtime.  A missing
    ``lib/`` directory is the normal case for older installations and yields
    an empty mapping; an unreadable file means a broken installation and
    fails fast, mirroring :func:`lua_api_library_source`.

    Cached after the first read: the bundled modules are read-only package
    data.  The returned mapping is shared between callers and must be
    treated as read-only (all current consumers pass it straight into
    :func:`yate.services.extensions.lua.runtime.create_runtime`, which only
    iterates it); each runtime still compiles its own private copies.
    """
    directory = bundled_extensions_dir() / LUA_LIB_DIRNAME
    if not directory.is_dir():
        return {}
    sources: dict[str, str] = {}
    for path in sorted(directory.glob("*.lua")):
        try:
            sources[path.stem] = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise RuntimeError(
                f"bundled Lua module {path} could not be read; "
                "the yate installation is broken"
            ) from exc
    return sources
