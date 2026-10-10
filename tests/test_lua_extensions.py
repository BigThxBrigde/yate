"""Tests for Lua extension loading (discovery, rollback, teardown, degradation).

Live-lua tests (marked ``@requires_lupa``) exercise the real lupa bridge and
skip when the optional package is absent; the degradation and resource tests
run everywhere.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, cast
from unittest.mock import MagicMock

import pytest

from yate.config import YateConfig
from yate.keymaps.base import Keymap, parse_key
from yate.keymaps.registry import KeymapSet
from yate.paths import bundled_extensions_dir
from yate.registries import ActionRegistry, CommandRegistry
from yate.session import EditorSession
from yate.services import extensions as ext_service
from yate.services import lua_extensions
from yate.services.extensions import ExtensionAPI, ExtensionContext, ExtensionLoader

#: Live-lua marker: skip when the optional lupa package is not installed.
_lua_missing = importlib.util.find_spec("lupa") is None
requires_lupa = pytest.mark.skipif(
    _lua_missing, reason="lupa is not installed (live-lua group)"
)

_ECHO_LUA: str = (
    "yate.register_command('lua-echo', function(args)\n"
    "  yate.message('echo:' .. (args or ''))\n"
    "end, 'echo cmd')\n"
)
_BOOM_LUA: str = (
    "yate.register_command('lua-boom', function() end)\n"
    "error('boom')\n"
)
_TEARDOWN_LUA: str = (
    "teardown = function(a)\n"
    "  a.message('bye from lua')\n"
    "end\n"
)
_OK_LUA: str = "local _ = 1\n"
_SETUP_OK: str = "def setup(api):\n    pass\n"


class _ApiBundle:
    """ExtensionAPI over *real* registries plus captured message texts.

    Real ``CommandRegistry`` / ``ActionRegistry`` / ``KeymapSet`` objects so
    the tests can assert registration results, not just mocks.
    """

    def __init__(self) -> None:
        self.messages: list[str] = []
        session = EditorSession(YateConfig())
        session.new_buffer()
        self.keymaps = KeymapSet({"vsc": Keymap(), "vim": Keymap()}, "vsc")
        self.actions = ActionRegistry()
        self.commands = CommandRegistry()
        ctx = ExtensionContext(
            session=session,
            workspace=cast(Any, MagicMock()),
            lsp=cast(Any, MagicMock()),
            keymaps=self.keymaps,
            actions=self.actions,
            commands=self.commands,
            message=self.messages.append,
            run_shell=lambda _command, _show: None,
            open_path=lambda _path: None,
            save=lambda: None,
        )
        self.api = ExtensionAPI(ctx)


@pytest.fixture
def bundle() -> _ApiBundle:
    """The real-registry API bundle."""
    return _ApiBundle()


@pytest.fixture
def loader(bundle: _ApiBundle) -> ExtensionLoader:
    """An ExtensionLoader over the bundle's API."""
    return ExtensionLoader(bundle.api)


# --- live-lua group: loading and the API bridge ------------------------------


@requires_lupa
def test_lua_extension_registers_command_and_receives_args(
    bundle: _ApiBundle, loader: ExtensionLoader, tmp_path: Path
) -> None:
    """A loaded .lua command lands in the registry and runs with its args."""
    script = tmp_path / "echo.lua"
    script.write_text(_ECHO_LUA, encoding="utf-8")

    record = loader.load_file(script)

    assert record.error is None
    entry = bundle.commands.get("lua-echo")
    assert entry is not None
    assert entry[1] == "echo cmd"
    entry[0]("hi")
    assert "echo:hi" in bundle.messages


@requires_lupa
def test_lua_extension_chunk_error_rolls_back_registrations(
    bundle: _ApiBundle, loader: ExtensionLoader, tmp_path: Path
) -> None:
    """A failing chunk records a LuaError and undoes its registrations."""
    script = tmp_path / "boom.lua"
    script.write_text(_BOOM_LUA, encoding="utf-8")

    record = loader.load_file(script)

    assert record.error is not None
    assert "LuaError" in record.error
    assert bundle.commands.get("lua-boom") is None


@requires_lupa
def test_lua_extension_teardown_global_invoked_on_teardown_all(
    bundle: _ApiBundle, loader: ExtensionLoader, tmp_path: Path
) -> None:
    """A chunk-defined global teardown(api) hook runs on teardown_all."""
    script = tmp_path / "res.lua"
    script.write_text(_TEARDOWN_LUA, encoding="utf-8")

    record = loader.load_file(script)
    assert record.error is None
    assert record.teardown is not None

    loader.teardown_all()
    assert "bye from lua" in bundle.messages


@requires_lupa
def test_lua_extension_same_path_deduplicated(
    loader: ExtensionLoader, tmp_path: Path
) -> None:
    """Loading the same .lua path twice hands back the earlier record."""
    script = tmp_path / "once.lua"
    script.write_text(_OK_LUA, encoding="utf-8")

    first = loader.load_file(script)
    second = loader.load_file(script.resolve())

    assert first is second
    assert len(loader.loaded) == 1


@requires_lupa
def test_load_directory_loads_mixed_py_and_lua(
    loader: ExtensionLoader, tmp_path: Path
) -> None:
    """One directory scan loads both script kinds, sorted, underscore skipped."""
    (tmp_path / "a.py").write_text(_SETUP_OK, encoding="utf-8")
    (tmp_path / "b.lua").write_text(_OK_LUA, encoding="utf-8")
    (tmp_path / "_hidden.lua").write_text(_OK_LUA, encoding="utf-8")
    (tmp_path / "note.txt").write_text(_OK_LUA, encoding="utf-8")

    records = loader.load_directory(tmp_path)

    assert [r.name for r in records] == ["a", "b"]
    assert all(r.error is None for r in records)


@requires_lupa
def test_load_directory_exclude_applies_to_lua_stem(
    loader: ExtensionLoader, tmp_path: Path
) -> None:
    """disabled_extensions-style stem exclusion also skips .lua scripts."""
    (tmp_path / "keep.lua").write_text(_OK_LUA, encoding="utf-8")
    (tmp_path / "off.lua").write_text(_OK_LUA, encoding="utf-8")

    records = loader.load_directory(tmp_path, exclude=["off"])

    assert [r.name for r in records] == ["keep"]


@requires_lupa
def test_bundled_lua_library_compiles_into_runtime(
    bundle: _ApiBundle,
) -> None:
    """The shipped _yate.lua compiles and exposes the yate module table."""
    runtime = lua_extensions.create_runtime(
        bundle.api, lua_extensions.lua_api_library_source()
    )

    assert runtime.eval("type(yate)") == "table"
    assert runtime.eval("type(yate.register_command)") == "function"
    assert runtime.eval("type(yate.bind_key)") == "function"
    assert runtime.eval("yate.api ~= nil")


# --- degradation without lupa ------------------------------------------------


def test_lua_extension_without_lupa_records_install_hint(
    loader: ExtensionLoader,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without lupa the record carries the install hint, nothing raises."""
    script = tmp_path / "lazy.lua"
    script.write_text(_OK_LUA, encoding="utf-8")
    monkeypatch.setattr(ext_service, "is_lua_available", lambda: False)

    record = loader.load_file(script)  # must not raise

    assert record.error is not None
    assert "pip install yate[lua]" in record.error
    assert record.teardown is None


# --- bundled resources (no lupa needed) --------------------------------------


def test_bundled_lua_library_resources_ship_bundled() -> None:
    """_yate.lua and lua.example exist in the bundled extensions directory."""
    ext_dir = bundled_extensions_dir()
    assert (ext_dir / "_yate.lua").is_file()
    assert (ext_dir / "lua.example").is_file()
    assert lua_extensions.lua_api_library_source() != ""


# --- bind_key positional form (Python-side regression) ------------------------


def test_bind_key_positional_args_match_keyword_form(bundle: _ApiBundle) -> None:
    """Positional bind_key calls bind exactly like the keyword form."""

    def _noop(_ctx: object) -> None:
        pass

    bundle.api.bind_key("<f10>", _noop, "vim", "desc", "cat")
    bundle.api.bind_key(
        "<f11>", _noop, keymap="vim", description="desc", category="cat"
    )
    km = bundle.keymaps.get("vim")
    assert km is not None
    bound_positional = km.lookup(parse_key("<f10>"))
    bound_keyword = km.lookup(parse_key("<f11>"))
    assert bound_positional is not None
    assert bound_keyword is not None
    assert bound_positional.description == bound_keyword.description == "desc"
    assert bound_positional.category == bound_keyword.category == "cat"
