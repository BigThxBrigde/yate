"""Lupa-backed Lua runtime bridge for ``*.lua`` extension scripts.

This module is the single place in yate that touches the ``lupa`` package:
lupa ships no ``py.typed``/stubs, so it is imported dynamically through
:func:`importlib.import_module` (which sidesteps missing-stub diagnostics)
and every value crossing the bridge is annotated ``Any`` with a reason
comment.  There is no static ``import lupa`` -- an installation without
lupa imports this module (and :mod:`yate.services.extensions`) at zero
cost, and only the optional ``yate[lua]`` extra needs the real package.

Shape of the bridge (the library itself lives in
``yate/extensions/_yate.lua``):

* :func:`create_runtime` builds one Lua runtime per extension (scripts are
  isolated from each other), exposes the concrete
  :class:`~yate.services.extensions.ExtensionAPI` object as the ``api``
  global, compiles the bundled Lua API library with the Lua-native
  ``assert(load(source, chunkname))`` and publishes the returned module
  table as ``package.preload["yate"]`` plus the global ``yate``;
* :func:`run_extension` executes a user chunk and mirrors the Python hook
  model: an explicit global ``setup(api)`` is called with the runtime's
  ``api`` global after the chunk's top level has run, while a chunk
  without one keeps the legacy "top-level code *is* the setup" behavior;
  the chunk's global ``teardown`` function is returned when it defined one.

The ``api`` parameter is typed ``object`` on purpose: this module never
calls into it (only Lua code consumes it), so ``object`` is the precise
"opaque handoff" type, not an ``Any`` escape hatch.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable
from typing import Any, cast

#: Lua module name the bundled API library is registered under: every
#: extension runtime can ``require("yate")`` and read the global ``yate``.
_LIBRARY_MODULE: str = "yate"

#: Global the chunk source is parked in while Lua-native ``load`` compiles
#: it (cleared right after, so user chunks never see it).
_CHUNK_SOURCE_GLOBAL: str = "_YATE_CHUNK_SOURCE"

#: Lua chunknames (the ``=`` prefix marks a custom name shown in traces).
_LIBRARY_CHUNK_NAME: str = "=yate.api"
_EXTENSION_CHUNK_NAME: str = "=extension"


def _compile_chunk(
    runtime: Any,  # noqa: Any - lupa ships no stubs
    source: str,
    chunkname: str,
) -> Any:  # noqa: Any - lupa ships no stubs
    """Compile a Lua source string into a callable chunk (Lua-native load).

    The source is parked in a global, compiled with
    ``assert(load(source, chunkname))`` -- ``load`` fails lazily, so
    ``assert`` turns a syntax error into a :class:`lupa.LuaError` naming
    the chunk -- and the parking global is dropped again.
    """
    globals_ = runtime.globals()
    globals_[_CHUNK_SOURCE_GLOBAL] = source
    try:
        return runtime.eval(f'assert(load({_CHUNK_SOURCE_GLOBAL}, "{chunkname}"))')
    finally:
        globals_[_CHUNK_SOURCE_GLOBAL] = None  # assigning nil removes it


def create_runtime(
    api: object,
    library_source: str,
) -> Any:  # noqa: Any - lupa ships no stubs
    """Create an isolated Lua runtime with the yate API library preloaded.

    Every extension gets its own runtime (scripts cannot see each other's
    globals).  The concrete :class:`~yate.services.extensions.ExtensionAPI`
    object is exposed as the ``api`` global for Lua code to call, and the
    compiled library module table is published twice: as
    ``package.preload["yate"]`` (so ``require("yate")`` works) and as the
    global ``yate``.
    """
    lupa = importlib.import_module("lupa")
    runtime = lupa.LuaRuntime(unpack_returned_tuples=True)
    globals_ = runtime.globals()
    globals_["api"] = api
    # The compiled library chunk doubles as the require() loader (preload
    # entries must be callable); requiring it once caches the module table
    # in package.loaded and publishes the global alias.  The assignment is
    # parenthesized: Lua 5.5 require returns a second "stop" value which
    # must be truncated before the table is stored.
    preload = _compile_chunk(runtime, library_source, _LIBRARY_CHUNK_NAME)
    globals_["package"]["preload"][_LIBRARY_MODULE] = preload
    runtime.execute(f'{_LIBRARY_MODULE} = (require("{_LIBRARY_MODULE}"))')
    return runtime


def run_extension(
    runtime: Any,  # noqa: Any - lupa ships no stubs
    source: str,
) -> Callable[[object], None] | None:
    """Execute a user chunk, mirroring the Python setup/teardown hook model.

    An explicit global ``setup(api)`` is called with the runtime's ``api``
    global after the chunk's top level has run; the loader's rollback scope
    covers the call, so a failing setup undoes its registrations.  A chunk
    that defines no ``setup`` global keeps the legacy behavior where the
    top-level code *is* the setup (byte-for-byte identical to the
    pre-mirror semantics).  Returns the chunk's global ``teardown``
    function when it defined a callable one, else ``None``.  Stale
    ``setup`` / ``teardown`` globals are dropped before the chunk runs, so
    the extraction only ever sees what *this* chunk defined.  A failing
    chunk or setup raises the original :class:`lupa.LuaError`; the loader
    records it on the extension record.
    """
    runtime.execute("teardown = nil; setup = nil")  # a previous chunk must not leak its hooks
    chunk = _compile_chunk(runtime, source, _EXTENSION_CHUNK_NAME)
    chunk()
    setup: Any = runtime.eval("setup")  # noqa: Any - lupa ships no stubs
    if callable(setup):
        api: Any = runtime.eval("api")  # noqa: Any - lupa ships no stubs
        setup(api)
    teardown: Any = runtime.eval("teardown")  # noqa: Any - lupa ships no stubs
    if callable(teardown):
        return cast(Callable[[object], None], teardown)
    return None
