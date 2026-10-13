"""Mechanical drift guards for the Lua API surface (plan_b, ext-api-parity).

Three surfaces must stay in lockstep, and only the library itself is
executable, so these guards parse text (no lupa required):

* the ``function yate.*`` definitions in ``_yate.lua`` (the shipped library);
* the mirrored declarations in ``_yate.d.lua`` (the lua-language-server
  definition file users' IDEs read);
* the ``api.<name>`` Python members the library forwards to (a new
  ``ExtensionAPI`` capability without a Lua wrapper must turn red).

Any drift -- a function added to one Lua file but not the other, a deleted
function without cleanup, or a Lua reference to a member outside the
frozen Python surface -- fails here instead of in a user's editor.
"""

from __future__ import annotations

import re
from pathlib import Path

#: Repository root -- this module lives in ``tests/``, one level below it.
_REPO_ROOT: Path = Path(__file__).resolve().parents[1]

#: The bundled extension directory holding both Lua files.
_EXTENSIONS_DIR: Path = _REPO_ROOT / "yate" / "extensions"

#: Every ``function yate.<path>(`` the bundled Lua library must define
#: (dot paths, nested namespaces included).  The plain-assignment lines
#: that create the namespace tables themselves (``yate.events = {}``) and
#: the raw bridge passthroughs (``yate.api = api``) are deliberately not
#: part of this surface: they are not functions.
LUA_SURFACE: frozenset[str] = frozenset({
    "message",
    "register_command",
    "register_action",
    "bind_key",
    "bind_action",
    "unbind_key",
    "shell",
    "open_path",
    "save",
    "buffer",
    "doc",
    "workspace",
    "events.subscribe",
    "ui.add_segment",
    "theme.set",
    "theme.active",
    "clipboard.set",
    "clipboard.get",
    "docs.all",
    "docs.is_open",
    "actions.run",
    "actions.names",
    "actions.has",
})

#: Every Python ``ExtensionAPI`` member the Lua library must forward to:
#: the top-level registrars and services, plus the bridge namespaces
#: (reached as ``api.theme.set``, ``api.ui.add_segment``, ...).
PYTHON_SURFACE: frozenset[str] = frozenset({
    "message",
    "register_command",
    "register_action",
    "bind_key",
    "bind_action",
    "unbind_key",
    "shell",
    "open_path",
    "save",
    "buffer",
    "doc",
    "workspace",
    "theme",
    "clipboard",
    "docs",
    "actions",
    "events",
    "ui",
    "keymaps",
    "highlight",
    "sprites",
    "lsp",
    "syntax",
})

#: ``function yate.<path>(`` at line start, dotted paths included.
_YATE_FUNC_RE = re.compile(r"^function\s+yate\.([A-Za-z_][\w.]*)\s*\(", re.MULTILINE)

#: ``api.<name>`` member references anywhere in the library source.
_API_REF_RE = re.compile(r"api\.(\w+)")


def _read_lua(name: str) -> str:
    """One bundled Lua file's source text."""
    return (_EXTENSIONS_DIR / name).read_text(encoding="utf-8")


def test_yate_lua_defines_exactly_the_frozen_surface() -> None:
    """_yate.lua's function set equals LUA_SURFACE (no more, no fewer)."""
    defined = set(_YATE_FUNC_RE.findall(_read_lua("_yate.lua")))
    assert defined == set(LUA_SURFACE), (
        f"surface drift in _yate.lua: missing={sorted(set(LUA_SURFACE) - defined)}, "
        f"extra={sorted(defined - set(LUA_SURFACE))}"
    )


def test_yate_d_lua_declares_exactly_the_same_surface() -> None:
    """_yate.d.lua declares every library function (meta file in lockstep)."""
    declared = set(_YATE_FUNC_RE.findall(_read_lua("_yate.d.lua")))
    assert declared == set(LUA_SURFACE), (
        f"surface drift in _yate.d.lua: "
        f"missing={sorted(set(LUA_SURFACE) - declared)}, "
        f"extra={sorted(declared - set(LUA_SURFACE))}"
    )


def test_yate_lua_references_every_python_api_member() -> None:
    """Every PYTHON_SURFACE member is reached as ``api.<name>`` somewhere."""
    referenced = set(_API_REF_RE.findall(_read_lua("_yate.lua")))
    missing = set(PYTHON_SURFACE) - referenced
    assert not missing, f"_yate.lua never references api.{sorted(missing)}"
