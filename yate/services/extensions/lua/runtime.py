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
  model across three entry forms, in precedence order: a returned module
  table (``local mod = {} ... return mod`` with ``mod.setup(api)``), an
  explicit global ``setup(api)``, or the legacy top-level-is-setup chunk;
  the unload hook comes from ``mod.teardown`` or the global ``teardown``.

The ``api`` parameter is typed ``object`` on purpose: this module never
calls into it (only Lua code consumes it), so ``object`` is the precise
"opaque handoff" type, not an ``Any`` escape hatch.
"""

from __future__ import annotations

import importlib
import re
from collections.abc import Callable, Mapping
from typing import Any, cast

#: Lua module name the bundled API library is registered under: every
#: extension runtime can ``require("yate")`` and read the global ``yate``.
_LIBRARY_MODULE: str = "yate"

#: Prefix of the chunkname given to a shared module, e.g. ``=lib.game_engine``.
#: Chunknames are interpolated into a Lua string literal, so they are built
#: from names validated by :data:`_MODULE_NAME_RE` (ASCII, quote-free).
_MODULE_CHUNK_PREFIX: str = "lib."

#: A shared module name (``lib/*.lua`` file stem) that may safely appear in a
#: Lua chunkname string literal.
_MODULE_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

#: Global the chunk source is parked in while Lua-native ``load`` compiles
#: it (cleared right after, so user chunks never see it).
_CHUNK_SOURCE_GLOBAL: str = "_YATE_CHUNK_SOURCE"

#: Lua chunknames (the ``=`` prefix marks a custom name shown in traces).
#: Both must stay quote-free: they are interpolated into Lua string
#: literals by :func:`_compile_chunk`.
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
    modules: Mapping[str, str] | None = None,
) -> Any:  # noqa: Any - lupa ships no stubs
    """Create an isolated Lua runtime with the yate API library preloaded.

    Every extension gets its own runtime (scripts cannot see each other's
    globals).  The concrete :class:`~yate.services.extensions.ExtensionAPI`
    object is exposed as the ``api`` global for Lua code to call, and the
    compiled library module table is published twice: as
    ``package.preload["yate"]`` (so ``require("yate")`` works) and as the
    global ``yate``.

    *modules* maps shared Lua module names to their source (the bundled
    ``extensions/lib/*.lua`` files, read by
    :func:`yate.services.extensions.lua.library.lua_module_sources`).  Each is
    compiled here and published under ``package.preload[<name>]``, so a script
    uses ``require("<name>")`` and receives a copy private to its own runtime
    -- scripts still cannot observe each other's state.  The preload table is
    the only channel on purpose: no ``package.path`` entry and no Lua-side file
    I/O, which keeps module resolution working in frozen builds.

    The runtime is pinned to the Lua 5.4 build: under the Lua 5.5 runtime
    (lupa's default when shipped) the generational GC can collect a Python
    wrapper while a Lua callback is still using it -- observed as ``api.data``
    spontaneously reading as an unrelated bound method mid-game, which made
    every per-turn save fail.  Lua 5.4 does not have that defect.
    """
    lupa = importlib.import_module("lupa")
    runtime = lupa.lua54.LuaRuntime(unpack_returned_tuples=True)
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
    preload_table = globals_["package"]["preload"]
    shared: Mapping[str, str] = modules if modules is not None else {}
    for name in sorted(shared):
        if _MODULE_NAME_RE.match(name) is None:
            raise ValueError(f"invalid shared Lua module name: {name!r}")
        chunkname = f"={_MODULE_CHUNK_PREFIX}{name}"
        preload_table[name] = _compile_chunk(runtime, shared[name], chunkname)
    return runtime


def run_extension(
    runtime: Any,  # noqa: Any - lupa ships no stubs
    source: str,
) -> Callable[[object], None] | None:
    """Execute a user chunk, mirroring the Python setup/teardown hook model.

    Entry forms, in precedence order (first match wins):

    1. The chunk returns a table -- the module-table contract: its callable
       ``setup`` is called with the runtime's ``api`` global and its
       callable ``teardown`` becomes the unload hook.  A returned table
       without a callable ``setup`` is a loud authoring error (returning a
       table signals module intent, so a missing setup is a typo, not a
       reason to fall back silently).
    2. A callable global ``setup`` -- called with the ``api`` global after
       the top level has run.
    3. No setup anywhere -- the legacy behavior where the top-level code
       *is* the setup.

    The loader's rollback scope covers the setup call, so a failing setup
    undoes its registrations.  Stale ``setup`` / ``teardown`` globals are
    dropped before the chunk runs, so the extraction only ever sees what
    *this* chunk defined.  A failing chunk or setup raises the original
    :class:`lupa.LuaError`; the loader records it on the extension record.
    """
    runtime.execute("teardown = nil; setup = nil")  # a previous chunk must not leak its hooks
    chunk = _compile_chunk(runtime, source, _EXTENSION_CHUNK_NAME)
    module: Any = chunk()  # noqa: Any - lupa ships no stubs
    # Table detection via a Lua-side helper: nil, numbers, strings and
    # wrapped Python objects all read as non-tables, so only a real Lua
    # table enters the module contract.
    is_table = runtime.eval("function(v) return type(v) == 'table' end")
    setup: Any  # noqa: Any - lupa ships no stubs
    teardown: Any  # noqa: Any - lupa ships no stubs
    if is_table(module):
        setup = module.setup
        teardown = module.teardown
        if not callable(setup):
            raise RuntimeError(
                "extension module table has no setup(api) function; "
                "define mod.setup(api) or drop the return value"
            )
    else:
        setup = runtime.eval("setup")
        teardown = runtime.eval("teardown")
    if callable(setup):
        api: Any = runtime.eval("api")  # noqa: Any - lupa ships no stubs
        setup(api)
    if callable(teardown):
        return cast(Callable[[object], None], teardown)
    return None
