"""Lupa-backed Lua extension bridge (``*.lua`` extension scripts).

Split from the former single-module ``yate.services.lua_extensions`` to
mirror the Python-side extension layering: :mod:`yate.services.lua.library`
owns availability probing and the bundled API library source (light),
:mod:`yate.services.lua.runtime` owns runtime lifecycle, chunk compilation
and the setup/teardown hook extraction (heavy).

Submodules are deliberately **not** re-exported (services-package rule,
architecture boundaries §三.5): import from the submodule that defines the
symbol (``from yate.services.lua.runtime import run_extension``).
"""

from __future__ import annotations
