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
from yate.services import clipboard as clipboard_module
from yate.services.events import EditorEvent, EventHub
from yate.services.extensions import loader as ext_loader
from yate.services.extensions import ExtensionAPI, ExtensionContext, ExtensionLoader
from yate.services.extensions.lua.library import lua_api_library_source
from yate.services.extensions.lua.runtime import create_runtime

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
# Explicit setup(a) runs after the whole top level: the chunk flips
# top_ran to true *after* defining setup, so the message proves the order.
_SETUP_AFTER_TOP_LUA: str = (
    "top_ran = false\n"
    "function setup(a)\n"
    "  a.message('setup:' .. tostring(top_ran))\n"
    "end\n"
    "top_ran = true\n"
)
_SETUP_TEARDOWN_LUA: str = (
    "function setup(api)\n"
    "  api.message('setup ran')\n"
    "end\n"
    "function teardown(api)\n"
    "  api.message('bye from hooks')\n"
    "end\n"
)
_SETUP_BOOM_LUA: str = (
    "function setup(api)\n"
    "  api.register_command('setup-boom', function() end)\n"
    "  error('setup boom')\n"
    "end\n"
)


class _ApiBundle:
    """ExtensionAPI over *real* registries plus captured message texts.

    Real ``CommandRegistry`` / ``ActionRegistry`` / ``KeymapSet`` objects so
    the tests can assert registration results, not just mocks.
    """

    def __init__(self) -> None:
        self.messages: list[str] = []
        self.theme_calls: list[str] = []
        self.run_action_calls: list[str] = []
        session = EditorSession(YateConfig())
        session.new_buffer()
        self.keymaps = KeymapSet({"vsc": Keymap(), "vim": Keymap()}, "vsc")
        self.actions = ActionRegistry()
        self.commands = CommandRegistry()
        # A real hub shared with the API so tests can count listeners.
        self.hub = EventHub()
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
            run_action=self._run_action,
            set_theme=self.theme_calls.append,
            active_theme_name=lambda: "mocha",
        )
        self.api = ExtensionAPI(ctx, self.hub)

    def _run_action(self, name: str) -> bool:
        """Record the dispatch; the bool mirrors a registered action hit."""
        self.run_action_calls.append(name)
        return self.actions.get(name) is not None


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
    assert entry.description == "echo cmd"
    entry.func("hi")
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
    runtime = create_runtime(bundle.api, lua_api_library_source())

    assert runtime.eval("type(yate)") == "table"
    assert runtime.eval("type(yate.register_command)") == "function"
    assert runtime.eval("type(yate.bind_key)") == "function"
    assert runtime.eval("yate.api ~= nil")


# --- setup/teardown mirror hooks (plan-b) -------------------------------------


@requires_lupa
def test_explicit_setup_hook_called_after_chunk(
    bundle: _ApiBundle, loader: ExtensionLoader, tmp_path: Path
) -> None:
    """An explicit setup(api) runs once, after the chunk's top level."""
    script = tmp_path / "hooked.lua"
    script.write_text(_SETUP_AFTER_TOP_LUA, encoding="utf-8")

    record = loader.load_file(script)

    assert record.error is None
    # top_ran is flipped to true by the top level *after* setup is defined,
    # so "setup:true" proves setup ran after the whole chunk.
    assert "setup:true" in bundle.messages
    assert record.teardown is None


@requires_lupa
def test_toplevel_only_script_still_loads(
    bundle: _ApiBundle, loader: ExtensionLoader, tmp_path: Path
) -> None:
    """A chunk without a setup global keeps the top-level-is-setup behavior."""
    script = tmp_path / "classic.lua"
    script.write_text(_ECHO_LUA, encoding="utf-8")

    record = loader.load_file(script)

    assert record.error is None
    assert bundle.commands.get("lua-echo") is not None
    assert record.teardown is None


@requires_lupa
def test_setup_failure_rolls_back_registrations(
    bundle: _ApiBundle, loader: ExtensionLoader, tmp_path: Path
) -> None:
    """A failing explicit setup records the error and undoes its registrations."""
    script = tmp_path / "setupboom.lua"
    script.write_text(_SETUP_BOOM_LUA, encoding="utf-8")

    record = loader.load_file(script)

    assert record.error is not None
    assert "LuaError" in record.error
    assert bundle.commands.get("setup-boom") is None


@requires_lupa
def test_teardown_global_extracted(
    bundle: _ApiBundle, loader: ExtensionLoader, tmp_path: Path
) -> None:
    """A global teardown(api) is extracted alongside an explicit setup."""
    script = tmp_path / "hooks.lua"
    script.write_text(_SETUP_TEARDOWN_LUA, encoding="utf-8")

    record = loader.load_file(script)
    assert record.error is None
    assert record.teardown is not None

    loader.teardown_all()
    assert "setup ran" in bundle.messages
    assert "bye from hooks" in bundle.messages


# --- module-table entry form (plan-e) ------------------------------------------


_MODULE_OK_LUA: str = (
    "local mod = {}\n"
    "function mod.setup(a)\n"
    "  a.register_command('mod-echo', function() end)\n"
    "  a.message('mod setup ran')\n"
    "end\n"
    "function mod.teardown(a)\n"
    "  a.message('mod bye')\n"
    "end\n"
    "return mod\n"
)
_MODULE_NO_SETUP_LUA: str = "local mod = { version = 1 }\nreturn mod\n"
_MODULE_SETUP_BOOM_LUA: str = (
    "local mod = {}\n"
    "function mod.setup(a)\n"
    "  a.register_command('mod-boom', function() end)\n"
    "  error('mod setup boom')\n"
    "end\n"
    "return mod\n"
)
_MODULE_WINS_OVER_GLOBAL_LUA: str = (
    "function setup(a)\n"
    "  a.message('global setup ran')\n"
    "end\n"
    "local mod = {}\n"
    "function mod.setup(a)\n"
    "  a.message('mod setup ran')\n"
    "end\n"
    "function mod.teardown(a)\n"
    "  a.message('mod bye')\n"
    "end\n"
    "return mod\n"
)
_MODULE_TEARDOWN_WINS_LUA: str = (
    "teardown = function(a)\n"
    "  a.message('global bye')\n"
    "end\n"
    "local mod = {}\n"
    "function mod.setup(a) end\n"
    "function mod.teardown(a)\n"
    "  a.message('mod bye')\n"
    "end\n"
    "return mod\n"
)
# A non-table return (``return`` must close a Lua block, so the setup
# global is defined first) falls back to the global/top-level semantics.
_NON_TABLE_RETURN_LUA: str = (
    "function setup(a)\n"
    "  a.message('global setup ran')\n"
    "end\n"
    "return 42\n"
)


@requires_lupa
def test_lua_module_table_setup_and_teardown_full_cycle(
    bundle: _ApiBundle, loader: ExtensionLoader, tmp_path: Path
) -> None:
    """A returned module table's setup(api) runs and teardown is extracted."""
    script = tmp_path / "mod.lua"
    script.write_text(_MODULE_OK_LUA, encoding="utf-8")

    record = loader.load_file(script)

    assert record.error is None
    assert "mod setup ran" in bundle.messages
    assert bundle.commands.get("mod-echo") is not None
    assert record.teardown is not None

    loader.teardown_all()
    assert "mod bye" in bundle.messages


@requires_lupa
def test_lua_module_table_without_setup_is_a_loud_error(
    bundle: _ApiBundle, loader: ExtensionLoader, tmp_path: Path
) -> None:
    """A returned table without a callable setup is a loud authoring error."""
    script = tmp_path / "nosetup.lua"
    script.write_text(_MODULE_NO_SETUP_LUA, encoding="utf-8")

    record = loader.load_file(script)

    assert record.error is not None
    assert "no setup(api) function" in record.error
    assert record.teardown is None


@requires_lupa
def test_lua_module_table_setup_failure_rolls_back(
    bundle: _ApiBundle, loader: ExtensionLoader, tmp_path: Path
) -> None:
    """A failing mod.setup records the error and undoes its registrations."""
    script = tmp_path / "modboom.lua"
    script.write_text(_MODULE_SETUP_BOOM_LUA, encoding="utf-8")

    record = loader.load_file(script)

    assert record.error is not None
    assert "LuaError" in record.error
    assert bundle.commands.get("mod-boom") is None


@requires_lupa
def test_lua_module_table_takes_precedence_over_global_setup(
    bundle: _ApiBundle, loader: ExtensionLoader, tmp_path: Path
) -> None:
    """When both exist, the returned table's setup wins over the global."""
    script = tmp_path / "both.lua"
    script.write_text(_MODULE_WINS_OVER_GLOBAL_LUA, encoding="utf-8")

    record = loader.load_file(script)

    assert record.error is None
    assert "mod setup ran" in bundle.messages
    assert "global setup ran" not in bundle.messages


@requires_lupa
def test_lua_module_teardown_takes_precedence_over_global(
    bundle: _ApiBundle, loader: ExtensionLoader, tmp_path: Path
) -> None:
    """When both exist, mod.teardown wins over the global teardown."""
    script = tmp_path / "bothteardown.lua"
    script.write_text(_MODULE_TEARDOWN_WINS_LUA, encoding="utf-8")

    record = loader.load_file(script)

    assert record.error is None
    loader.teardown_all()
    assert "mod bye" in bundle.messages
    assert "global bye" not in bundle.messages


@requires_lupa
def test_lua_non_table_return_falls_back_to_global_setup(
    bundle: _ApiBundle, loader: ExtensionLoader, tmp_path: Path
) -> None:
    """A non-table return value ignores the module contract entirely."""
    script = tmp_path / "numret.lua"
    script.write_text(_NON_TABLE_RETURN_LUA, encoding="utf-8")

    record = loader.load_file(script)

    assert record.error is None
    assert "global setup ran" in bundle.messages


# --- package layout (no lupa needed) ------------------------------------------


def test_lua_package_import_paths() -> None:
    """The Lua bridge lives in yate.services.extensions.lua; the old module is gone."""
    from yate.services.extensions import lua as lua_package
    from yate.services.extensions.lua import library as lua_library
    from yate.services.extensions.lua import runtime as lua_runtime

    assert callable(lua_library.is_lua_available)
    assert callable(lua_library.lua_api_library_source)
    assert callable(lua_runtime.create_runtime)
    assert callable(lua_runtime.run_extension)
    # Services packages must not re-export (architecture rule section 3.5): the
    # package root exposes only its submodules.
    for symbol in (
        "is_lua_available",
        "lua_api_library_source",
        "create_runtime",
        "run_extension",
    ):
        assert not hasattr(lua_package, symbol)
    assert importlib.util.find_spec("yate.services.lua_extensions") is None


def test_services_package_root_does_not_reexport_submodule_symbols() -> None:
    """Neither service package root re-exports its submodule symbols."""
    import yate.services as services_package
    from yate.services import extensions as extensions_package

    for package in (services_package, extensions_package):
        for symbol in (
            "is_lua_available",
            "lua_api_library_source",
            "create_runtime",
            "run_extension",
        ):
            assert not hasattr(package, symbol)


def test_lua_availability_probe_swallows_probe_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A broken half-install makes is_lua_available() False, not a crash."""
    from yate.services.extensions.lua import library

    def boom(name: str) -> None:
        raise ValueError("broken spec")

    monkeypatch.setattr(library.importlib.util, "find_spec", boom)
    assert library.is_lua_available() is False


def test_library_source_fails_fast_on_unreadable_resource(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """An unreadable bundled library is an installation error, raised here."""
    from yate.services.extensions.lua import library

    # The source reader caches the healthy bundled resource per process;
    # clear it so this test's unreadable stand-in directory is consulted.
    library.lua_api_library_source.cache_clear()
    try:
        monkeypatch.setattr(library, "bundled_extensions_dir", lambda: tmp_path)
        with pytest.raises(RuntimeError):
            library.lua_api_library_source()
    finally:
        library.lua_api_library_source.cache_clear()


# --- degradation without lupa ------------------------------------------------


def test_lua_extension_without_lupa_records_install_hint(
    loader: ExtensionLoader,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without lupa the record carries the install hint, nothing raises."""
    script = tmp_path / "lazy.lua"
    script.write_text(_OK_LUA, encoding="utf-8")
    monkeypatch.setattr(ext_loader, "is_lua_available", lambda: False)

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
    assert lua_api_library_source() != ""


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


_BIND_LUA: str = "yate.bind_key('<f7>', function() end)\n"


@requires_lupa
def test_lua_bind_key_two_args_defaults_to_vsc(
    bundle: _ApiBundle, loader: ExtensionLoader, tmp_path: Path
) -> None:
    """A two-arg Lua bind_key binds in vsc (Lua nil keymap falls back)."""
    script = tmp_path / "bind.lua"
    script.write_text(_BIND_LUA, encoding="utf-8")

    record = loader.load_file(script)

    assert record.error is None
    km = bundle.keymaps.get("vsc")
    assert km is not None
    assert km.lookup(parse_key("<f7>")) is not None


# --- api parity wrappers (plan_b / ext-api-parity wave 2) ---------------------


_EVENTS_LUA: str = (
    "_unsub = yate.events.subscribe('document_saved', function(payload)\n"
    "  api.message('saved event fired')\n"
    "end)\n"
    "function teardown()\n"
    "  _unsub()\n"
    "end\n"
)
_UNKNOWN_EVENT_LUA: str = "yate.events.subscribe('no_such_event', function() end)\n"
_SEGMENT_LUA: str = "yate.ui.add_segment('lua-seg', function() return 'seg' end)\n"
_THEME_LUA: str = (
    "yate.theme.set('solarized-dark')\n"
    "yate.message('theme:' .. yate.theme.active())\n"
)
_CLIPBOARD_LUA: str = (
    "local ok = yate.clipboard.set('hello')\n"
    "yate.message('cbset:' .. tostring(ok))\n"
    "yate.message('cbget:' .. tostring(yate.clipboard.get()))\n"
)
_DOCS_LUA: str = (
    "local docs = yate.docs.all()\n"
    "yate.message('docs:' .. tostring(python.builtins.len(docs)))\n"
    "yate.message('isopen:' .. tostring(yate.docs.is_open('no/such/file.py')))\n"
)
_ACTIONS_LUA: str = (
    "yate.register_action('my-lua-action', function() end)\n"
    "yate.message('ran:' .. tostring(yate.actions.run('my-lua-action')))\n"
    "yate.message('has:' .. tostring(yate.actions.has('my-lua-action')))\n"
    "yate.actions.names()\n"
)
_BIND_ACTION_LUA: str = (
    "yate.register_action('bindme', function() end)\n"
    "yate.bind_action('gq', 'bindme')\n"
)
_UNBIND_LUA: str = "yate.message('removed:' .. tostring(yate.unbind_key('gq')))\n"


@requires_lupa
def test_lua_events_subscribe_maps_name_and_round_trips(
    bundle: _ApiBundle, loader: ExtensionLoader, tmp_path: Path
) -> None:
    """The lowercase name maps to DOCUMENT_SAVED; teardown unsubscribes."""
    script = tmp_path / "events.lua"
    script.write_text(_EVENTS_LUA, encoding="utf-8")

    record = loader.load_file(script)

    assert record.error is None
    assert bundle.hub.listener_count(EditorEvent.DOCUMENT_SAVED) == 1
    bundle.hub.emit(EditorEvent.DOCUMENT_SAVED, object())
    assert "saved event fired" in bundle.messages

    loader.teardown_all()
    assert bundle.hub.listener_count(EditorEvent.DOCUMENT_SAVED) == 0


@requires_lupa
def test_lua_events_unknown_name_raises_loudly(
    bundle: _ApiBundle, loader: ExtensionLoader, tmp_path: Path
) -> None:
    """An unknown event name surfaces a Lua error mentioning unknown event."""
    script = tmp_path / "badevent.lua"
    script.write_text(_UNKNOWN_EVENT_LUA, encoding="utf-8")

    record = loader.load_file(script)

    assert record.error is not None
    assert "unknown event" in record.error


@requires_lupa
def test_lua_ui_add_segment_nil_args_fall_back_to_defaults(
    bundle: _ApiBundle, loader: ExtensionLoader, tmp_path: Path
) -> None:
    """nil align/priority land on the Python defaults (right half / 0)."""
    script = tmp_path / "segment.lua"
    script.write_text(_SEGMENT_LUA, encoding="utf-8")

    record = loader.load_file(script)

    assert record.error is None
    right = bundle.api.ui.segments("right")
    assert [segment.id for segment in right] == ["lua-seg"]
    assert right[0].align == "right"
    assert right[0].priority == 0
    assert bundle.api.ui.segments("left") == []


_MODULE_SEGMENT_LUA: str = (
    "local mod = {}\n"
    "function mod.setup(a)\n"
    "  a.ui.add_segment('reload-seg', function() return 'seg' end)\n"
    "end\n"
    "function mod.teardown(a)\n"
    "  yate.ui.remove_segment('reload-seg')\n"
    "end\n"
    "return mod\n"
)


@requires_lupa
def test_lua_ui_remove_segment_in_teardown_allows_reload(
    bundle: _ApiBundle, loader: ExtensionLoader, tmp_path: Path
) -> None:
    """teardown's yate.ui.remove_segment frees the id: a reload succeeds
    instead of hitting the duplicate-id ValueError on add_segment."""
    first = tmp_path / "seg.lua"
    first.write_text(_MODULE_SEGMENT_LUA, encoding="utf-8")

    record = loader.load_file(first)

    assert record.error is None
    right = bundle.api.ui.segments("right")
    assert [segment.id for segment in right] == ["reload-seg"]

    loader.teardown_all()
    assert bundle.api.ui.segments("right") == []

    # Same script content under a new name (the loader dedups by path):
    # the id was freed by teardown, so the reload must not raise.
    second = tmp_path / "seg-reload.lua"
    second.write_text(_MODULE_SEGMENT_LUA, encoding="utf-8")
    reloaded = loader.load_file(second)
    assert reloaded.error is None
    reloaded_right = bundle.api.ui.segments("right")
    assert [segment.id for segment in reloaded_right] == ["reload-seg"]


@requires_lupa
def test_lua_theme_set_and_active(
    bundle: _ApiBundle, loader: ExtensionLoader, tmp_path: Path
) -> None:
    """theme.set forwards the name; theme.active returns the active name."""
    script = tmp_path / "theme.lua"
    script.write_text(_THEME_LUA, encoding="utf-8")

    record = loader.load_file(script)

    assert record.error is None
    assert bundle.theme_calls == ["solarized-dark"]
    assert "theme:mocha" in bundle.messages


@requires_lupa
def test_lua_clipboard_set_and_get(
    bundle: _ApiBundle,
    loader: ExtensionLoader,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """clipboard.set/get round-trip through the clipboard service module."""
    script = tmp_path / "clipboard.lua"
    script.write_text(_CLIPBOARD_LUA, encoding="utf-8")

    def fake_copy(_text: str) -> bool:
        return True

    monkeypatch.setattr(clipboard_module, "copy_text", fake_copy)
    monkeypatch.setattr(clipboard_module, "paste_text", lambda: "cb-text")

    record = loader.load_file(script)

    assert record.error is None
    assert "cbset:true" in bundle.messages
    assert "cbget:cb-text" in bundle.messages


@requires_lupa
def test_lua_docs_all_and_is_open(
    bundle: _ApiBundle, loader: ExtensionLoader, tmp_path: Path
) -> None:
    """docs.all() sees the session documents; is_open answers for a path."""
    script = tmp_path / "docs.lua"
    script.write_text(_DOCS_LUA, encoding="utf-8")

    record = loader.load_file(script)

    assert record.error is None
    # The bundle's session opened exactly one (unnamed) buffer document.
    assert "docs:1" in bundle.messages
    assert "isopen:false" in bundle.messages


@requires_lupa
def test_lua_actions_run_names_and_has(
    bundle: _ApiBundle, loader: ExtensionLoader, tmp_path: Path
) -> None:
    """run dispatches via the editor callback; names/has read the registry."""
    script = tmp_path / "actions.lua"
    script.write_text(_ACTIONS_LUA, encoding="utf-8")

    record = loader.load_file(script)

    assert record.error is None
    assert "ran:true" in bundle.messages
    assert "has:true" in bundle.messages
    assert "my-lua-action" in bundle.actions.names()


@requires_lupa
def test_lua_bind_action_and_unbind_key_round_trip(
    bundle: _ApiBundle, loader: ExtensionLoader, tmp_path: Path
) -> None:
    """bind_action binds the action BY NAME; unbind_key removes it (True)."""
    script = tmp_path / "bindaction.lua"
    script.write_text(_BIND_ACTION_LUA, encoding="utf-8")

    record = loader.load_file(script)
    assert record.error is None
    km = bundle.keymaps.get("vsc")
    assert km is not None
    binding = km.lookup(parse_key("gq"))
    assert binding is not None
    assert binding.action == "bindme"

    unbind = tmp_path / "unbind.lua"
    unbind.write_text(_UNBIND_LUA, encoding="utf-8")
    record = loader.load_file(unbind)
    assert record.error is None
    assert km.lookup(parse_key("gq")) is None
    assert "removed:true" in bundle.messages
