"""Live-lua tests for the shared game engine (``extensions/lib/game_engine.lua``).

The module is loaded through the real runtime (``create_runtime`` with the
bundled ``lib/*.lua`` sources), so these tests cover the exact contract every
bundled game builds on: the JSON codec, the per-game document store, the high
score board, the ``:game`` dispatcher, the canvas session lifecycle, the
layout helpers, the direction mapping, the deterministic RNG and the UTF-8
glyph helper.
"""

from __future__ import annotations

from typing import Any, cast

import pytest

from lua_game_harness import (
    FakeApi,
    engine_runtime,
    lua_to_python,
    requires_lupa,
)
from yate.paths import bundled_extensions_dir
from yate.services.extensions.lua.library import (
    lua_api_library_source,
    lua_module_sources,
)
from yate.services.extensions.lua.runtime import create_runtime

#: Four registered game actions, so the dispatcher lists a stable catalogue.
_GAME_NAMES: tuple[str, ...] = ("nethack", "pacman", "snake", "tetris")

#: An ``engine.open`` spec whose draw callback paints a fixed two-line grid.
_OPEN_PROBE = """
probe = engine.open{
  name = "probe",
  cols = 5,
  rows = 3,
  draw = function() return "ab\\ncd", { ["a"] = "#ff0000" } end,
}
"""


def _dispatcher() -> tuple[Any, FakeApi]:
    """A runtime with ``games.lua`` loaded over a recording api."""
    api = FakeApi()
    runtime: Any = create_runtime(
        api, lua_api_library_source(), lua_module_sources()
    )
    module: Any = runtime.execute(
        (bundled_extensions_dir() / "games.lua").read_text(encoding="utf-8")
    )
    module.setup(api)
    return runtime, api


def _with_games(api: FakeApi) -> None:
    """Register one no-op action per bundled game name."""

    def _noop(_ctx: Any) -> None:
        return None

    for name in _GAME_NAMES:
        api.actions.registry[f"game-{name}"] = _noop


@requires_lupa
def test_games_extension_registers_the_game_command() -> None:
    """``games.lua`` registers exactly one ``game`` command with its help."""
    _runtime, api = _dispatcher()

    assert set(api.commands) == {"game"}
    _handler, description = api.commands["game"]
    assert description == "launch a bundled game"


@requires_lupa
def test_dispatch_reports_usage_with_the_available_games() -> None:
    """No argument (or blanks only) prints the frozen usage line."""
    _runtime, api = _dispatcher()
    _with_games(api)
    handler, _description = api.commands["game"]

    handler("")
    handler("   ")

    expected = "usage: :game <name> (games: nethack pacman snake tetris)"
    assert api.messages == [expected, expected]


@requires_lupa
def test_dispatch_reports_unknown_game_and_lists_available() -> None:
    """An unknown name names itself and lists the catalogue."""
    _runtime, api = _dispatcher()
    _with_games(api)
    handler, _description = api.commands["game"]

    handler("chess")

    assert api.messages == [
        "unknown game: chess (available: nethack pacman snake tetris)"
    ]
    assert api.actions.calls == []


@requires_lupa
def test_dispatch_runs_the_registered_action() -> None:
    """A known name runs the matching ``game-<name>`` action."""
    _runtime, api = _dispatcher()
    _with_games(api)
    handler, _description = api.commands["game"]

    handler("snake")

    assert api.actions.calls == ["game-snake"]


@requires_lupa
def test_player_query_and_set() -> None:
    """``:game player`` reads the name; ``:game player bob`` persists it."""
    _runtime, api = _dispatcher()
    handler, _description = api.commands["game"]

    handler("player")
    handler("player bob")
    handler("player")

    assert api.messages[0].startswith("player: ")
    assert api.messages[-2:] == ["player: bob", "player: bob"]
    assert "bob" in api.data.files["games/profile.json"]


@requires_lupa
def test_rng_is_deterministic_for_a_seed() -> None:
    """The same seed replays the same sequence; another seed diverges."""
    runtime, _api = engine_runtime()

    first = runtime.execute(
        "local r = engine.rng(7) return r.int(100), r.int(100), r.int(100)"
    )
    again = runtime.execute(
        "local r = engine.rng(7) return r.int(100), r.int(100), r.int(100)"
    )
    other = runtime.execute(
        "local r = engine.rng(8) return r.int(100), r.int(100), r.int(100)"
    )

    assert first == again
    assert first != other
    assert all(1 <= value <= 100 for value in first)


@requires_lupa
def test_json_roundtrip_keeps_nesting_and_escapes() -> None:
    """Objects, arrays, empty tables and escapes survive encode -> decode."""
    runtime, _api = engine_runtime()

    encoded = runtime.execute(
        'return engine.json.encode({a = 1, b = {"x", "y"}, c = {}, d = \'q"z\'})'
    )
    decoded = runtime.execute(f'return engine.json.decode({_lua_quote(encoded)})')
    value = cast(dict[str, Any], lua_to_python(decoded))

    assert encoded == '{"a":1,"b":["x","y"],"c":[],"d":"q\\"z"}'
    assert value == {"a": 1, "b": ["x", "y"], "c": {}, "d": 'q"z'}


@requires_lupa
def test_json_encodes_an_empty_table_as_an_array() -> None:
    """Documents round-trip except for ``{}`` vs ``[]``, which is documented."""
    runtime, _api = engine_runtime()

    assert runtime.execute("return engine.json.encode({})") == "[]"
    decoded = lua_to_python(runtime.execute('return engine.json.decode("[]")'))

    assert decoded == {}


@requires_lupa
def test_json_decode_reports_errors() -> None:
    """A malformed document yields ``nil`` plus a ``json:`` message."""
    runtime, _api = engine_runtime()

    result = runtime.execute('return engine.json.decode("{oops")')

    assert isinstance(result, tuple)
    assert result[0] is None
    assert isinstance(result[1], str) and result[1].startswith("json:")


@requires_lupa
def test_store_roundtrip_and_bad_json_falls_back_to_nil() -> None:
    """Saved documents reload; an unparsable file reads as "no data"."""
    runtime, api = engine_runtime()

    runtime.execute(
        'engine.store("probe").save({version = 1, score = 7, tags = {"a"}})'
    )
    loaded = cast(dict[str, Any], lua_to_python(runtime.execute(
        'return engine.store("probe").load()'
    )))

    assert loaded == {"version": 1, "score": 7, "tags": ["a"]}
    assert "games/probe.json" in api.data.files

    api.data.files["games/broken.json"] = "not json at all"
    assert runtime.execute('return engine.store("broken").load()') is None


@requires_lupa
def test_scores_keep_the_top_five_with_players() -> None:
    """Six scores keep the five best, descending, with player and time."""
    runtime, api = engine_runtime()

    for score in (10, 50, 30, 90, 20, 70):
        runtime.execute(
            f'engine.scores("probe").add({score})'
        )

    entries = cast(
        list[dict[str, Any]], lua_to_python(runtime.execute(
            'return engine.scores("probe").entries()'
        ))
    )

    assert [entry["score"] for entry in entries] == [90, 70, 50, 30, 20]
    assert all(isinstance(entry["player"], str) for entry in entries)
    assert all("T" in entry["at"] for entry in entries)
    assert "games/probe.json" in api.data.files
    assert runtime.execute('return engine.scores("probe").best()') == 90


@requires_lupa
def test_frame_and_panel_pad_every_line() -> None:
    """Every framed line has the same display width and rounded corners."""
    runtime, _api = engine_runtime()

    lines = cast(
        list[str],
        lua_to_python(runtime.execute('return engine.frame("t", 5, {"a", "bb"})')),
    )

    assert len(lines) == 4
    assert {len(line) for line in lines} == {7}
    assert lines[0].startswith("╭") and lines[-1].startswith("╰")
    assert lines[1] == "│a    │"
    assert lines[2] == "│bb   │"


@requires_lupa
def test_direction_maps_arrows_hjkl_and_wasd() -> None:
    """The eight movement keys map to steps; other keys return nothing."""
    runtime, _api = engine_runtime()

    mapped = {
        key: runtime.execute(f'return engine.direction("{key}")')
        for key in ("left", "h", "a", "right", "l", "d", "up", "k", "w",
                    "down", "j", "s")
    }
    unknown = runtime.execute('return engine.direction("space")')

    assert mapped["left"] == (-1, 0) and mapped["a"] == (-1, 0)
    assert mapped["right"] == (1, 0) and mapped["d"] == (1, 0)
    assert mapped["up"] == (0, -1) and mapped["w"] == (0, -1)
    assert mapped["down"] == (0, 1) and mapped["s"] == (0, 1)
    assert unknown is None


@requires_lupa
def test_utf8_char_returns_a_glyph_or_nil() -> None:
    """The nerd glyph helper yields a non-empty string on Lua 5.3+."""
    runtime, _api = engine_runtime()

    glyph = runtime.execute("return engine.utf8_char(0xf007)")
    empty = runtime.execute("return engine.utf8_char(0)")

    assert isinstance(glyph, str) and ord(glyph) == 0xF007
    assert isinstance(empty, str) and empty


@requires_lupa
def test_second_open_reports_already_running() -> None:
    """A second session for the same runtime is refused with the frozen text."""
    runtime, api = engine_runtime()

    runtime.execute(_OPEN_PROBE)
    assert api.canvas is not None
    runtime.execute(_OPEN_PROBE)

    assert api.messages == ["probe is already running"]
    first = api.canvas
    assert first is not None


@requires_lupa
def test_close_callback_deadens_the_session() -> None:
    """After the close callback a racing paint is ignored and open works again."""
    runtime, api = engine_runtime()
    runtime.execute(_OPEN_PROBE)
    canvas = api.canvas
    assert canvas is not None
    frames = len(canvas.grids)

    canvas.close_cb()
    runtime.execute("probe.paint()")

    assert len(canvas.grids) == frames
    runtime.execute(_OPEN_PROBE)
    assert api.canvas is not canvas


@requires_lupa
def test_status_appends_the_exit_hint_once() -> None:
    """``session.status`` adds the escape hint exactly once."""
    runtime, api = engine_runtime()
    runtime.execute(_OPEN_PROBE)

    runtime.execute('probe.status("score 3")')
    runtime.execute('probe.status("score 4  escape quits")')

    canvas = api.canvas
    assert canvas is not None
    assert canvas.statuses[0] == "score 3  escape quits"
    assert canvas.statuses[1] == "score 4  escape quits"


@requires_lupa
def test_lib_dir_is_not_discovered_as_an_extension() -> None:
    """Shared modules live in ``lib/`` and never enter extension discovery."""
    discovered = {path.name for path in bundled_extensions_dir().glob("*.lua")}

    assert "game_engine.lua" not in discovered
    assert (bundled_extensions_dir() / "lib" / "game_engine.lua").is_file()
    # the engine is split over three requirable modules (each well below the
    # 800-line guideline the Python guard applies to yate/)
    assert {"game_engine", "engine_json", "engine_layout"} <= set(
        lua_module_sources()
    )


@pytest.mark.parametrize("name", ["bad-name", "a.b", "1st"])
def test_create_runtime_rejects_unsafe_module_names(name: str) -> None:
    """A module name that cannot appear in a chunkname string is rejected."""
    api = FakeApi()

    with pytest.raises(ValueError, match="invalid shared Lua module name"):
        create_runtime(api, lua_api_library_source(), {name: "return {}"})


def _lua_quote(text: str) -> str:
    """Quote *text* as a single-quoted Lua string literal."""
    return "'" + text.replace("\\", "\\\\").replace("'", "\\'") + "'"
