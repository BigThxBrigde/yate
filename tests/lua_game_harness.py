"""Recording fakes for driving the bundled Lua games from pytest.

The games are executed by the real lupa runtime over an in-memory ``api``, so
the tests exercise the shipped Lua sources exactly as the editor loads them:
``create_runtime`` with the bundled API library and the shared ``lib/*.lua``
modules, then ``mod.setup(api)``.

Everything is isolated from the real user directory: :class:`FakeData` keeps
documents in a dict, so no test reads or writes ``~/.yate/data``.

Typical use::

    game = GameRuntime("snake")
    canvas = game.launch()
    game.press("up")
    game.tick(10)
    assert game.snapshot()["head_y"] == 8

Marked through :data:`requires_lupa`: the whole group skips without the
optional ``yate[lua]`` extra.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, cast

import pytest

from yate.paths import bundled_extensions_dir
from yate.services.extensions.lua.library import (
    lua_api_library_source,
    lua_module_sources,
)
from yate.services.extensions.lua.runtime import create_runtime

#: Live-lua marker: skip when the optional lupa package is not installed.
_lua_missing = importlib.util.find_spec("lupa") is None
requires_lupa = pytest.mark.skipif(
    _lua_missing, reason="lupa is not installed (live-lua group)"
)


class FakeCanvas:
    """Recording stand-in for the Python-side ``CanvasHandle``."""

    def __init__(self) -> None:
        self.cols: int = 0
        self.rows: int = 0
        self.grids: list[str] = []
        self.statuses: list[str] = []
        self.closed: bool = False
        # Lua closures handed over by open_canvas (opaque outside the runtime).
        self.key: Any = None
        self.tick: Any = None
        self.close_cb: Any = None

    @property
    def grid(self) -> str:
        """The most recently drawn newline-joined grid."""
        return self.grids[-1]

    @property
    def status(self) -> str:
        """The most recently pushed status line."""
        return self.statuses[-1]

    def draw(self, grid: str, palette: Any) -> None:
        """Record one frame (the palette is asserted on the library side)."""
        self.grids.append(grid)

    def set_status(self, text: str) -> None:
        """Record one status line."""
        self.statuses.append(text)

    def close(self) -> None:
        """Record that the host was asked to dismiss the canvas."""
        self.closed = True


class FakeActions:
    """``api.actions``: a name -> callable registry (0-based ``names``)."""

    def __init__(self) -> None:
        self.registry: dict[str, Any] = {}
        self.calls: list[str] = []

    def run(self, name: str) -> bool:
        """Dispatch *name* to its handler; ``False`` when unknown."""
        handler = self.registry.get(name)
        if handler is None:
            return False
        self.calls.append(name)
        handler(None)
        return True

    def names(self) -> list[str]:
        """Registered action names as a plain Python list (engine reads len)."""
        return list(self.registry)

    def has(self, name: str) -> bool:
        """True when *name* is registered."""
        return name in self.registry


class FakeData:
    """``api.data``: documents kept in a dict, never on disk."""

    def __init__(self) -> None:
        self.files: dict[str, str] = {}

    def read(self, name: str) -> str | None:
        """Return the stored document, or ``None``."""
        return self.files.get(name)

    def write(self, name: str, text: str) -> bool:
        """Store the document."""
        self.files[name] = text
        return True

    def remove(self, name: str) -> bool:
        """Drop the document; ``True`` when it existed."""
        return self.files.pop(name, None) is not None

    def list(self, prefix: str) -> list[str]:
        """List the documents under *prefix* (bare names, sorted)."""
        head = prefix.rstrip("/") + "/"
        return sorted(name[len(head) :] for name in self.files if name.startswith(head))


class FakeUi:
    """``api.ui``: records the canvas request, refuses segment traffic."""

    def __init__(self, api: FakeApi) -> None:
        self._api = api

    def open_canvas(
        self,
        cols: int,
        rows: int,
        on_key: Any,
        on_tick: Any,
        on_close: Any,
    ) -> FakeCanvas:
        """Build the recording canvas and keep the Lua callbacks."""
        canvas = FakeCanvas()
        canvas.cols = cols
        canvas.rows = rows
        canvas.key = on_key
        canvas.tick = on_tick
        canvas.close_cb = on_close
        self._api.canvas = canvas
        return canvas

    def add_status_segment(self, *_args: Any) -> None:
        """Games must not contribute a status bar segment."""
        raise AssertionError("a game added a status segment")

    def remove_status_segment(self, *_args: Any) -> None:
        """Games must not touch the status bar registry."""
        raise AssertionError("a game removed a status segment")


class FakeApi:
    """Recording stand-in for ``ExtensionAPI`` (only the used members)."""

    def __init__(self) -> None:
        self.messages: list[str] = []
        self.commands: dict[str, tuple[Any, str | None]] = {}
        self.canvas: FakeCanvas | None = None
        self.ui = FakeUi(self)
        self.actions = FakeActions()
        self.data = FakeData()
        # Raw passthrough namespaces the API library binds at load time.
        self.keymaps: Any = None
        self.highlight: Any = None
        self.sprites: Any = None
        self.lsp: Any = None
        self.syntax: Any = None

    def message(self, text: str) -> None:
        """Record one message-line hint."""
        self.messages.append(text)

    def register_command(
        self, name: str, fn: Any, description: str | None = None
    ) -> None:
        """Record one ``:`` command registration."""
        self.commands[name] = (fn, description)

    def register_action(
        self, name: str, fn: Any, description: str | None = None
    ) -> None:
        """Record one named action registration."""
        _ = description
        self.actions.registry[name] = fn


def bundled_source(name: str) -> str:
    """Read a bundled Lua file by module name (``snake``, ``games``, ...)."""
    return (bundled_extensions_dir() / f"{name}.lua").read_text(encoding="utf-8")


def lua_to_python(value: Any) -> Any:
    """Convert a Lua value (nested tables included) to plain Python data.

    A table whose keys are exactly ``1..n`` becomes a list, an empty table a
    dict, anything else a dict keyed by its Lua keys; ``engine.json.null``
    (an empty table) therefore reads back as an empty dict.
    """
    items: list[tuple[Any, Any]] = []
    try:
        pairs = value.items()
    except AttributeError:
        return value
    for key, item in pairs:
        items.append((key, lua_to_python(item)))
    if not items:
        return {}
    keys = [key for key, _unused in items]
    if all(isinstance(key, int) for key in keys) and sorted(keys) == list(
        range(1, len(keys) + 1)
    ):
        ordered = sorted(items, key=lambda entry: entry[0])
        return [item for _key, item in ordered]
    return dict(items)


class GameRuntime:
    """One bundled Lua extension loaded over a recording api.

    Runtimes are independent (as in the editor: one Lua runtime per script),
    but they may share one :class:`FakeApi` so the action registry, the data
    store and the command table behave like the real ones across scripts.
    """

    def __init__(self, game: str, api: FakeApi | None = None) -> None:
        self.game = game
        self.api = api if api is not None else FakeApi()
        self.runtime: Any = create_runtime(
            self.api, lua_api_library_source(), lua_module_sources()
        )
        self.module: Any = self.runtime.execute(bundled_source(game))
        self.module.setup(self.api)

    def load_entry(self) -> None:
        """Load ``games.lua`` over the same api (the ``:game`` dispatcher)."""
        entry: Any = self.runtime.execute(bundled_source("games"))
        entry.setup(self.api)

    def command(self, args: str) -> None:
        """Run the registered ``:game`` handler with *args*."""
        handler, _description = self.api.commands["game"]
        handler(args)

    def launch(self) -> FakeCanvas:
        """Run this game's action (what ``:game <name>`` ends up doing)."""
        assert self.api.actions.run(
            f"game-{self.game}"
        ), f"game-{self.game} is not registered"
        return self.require_canvas()

    def require_canvas(self) -> FakeCanvas:
        """The canvas opened so far; fails when none was opened."""
        canvas = self.api.canvas
        assert canvas is not None, "no canvas was opened"
        return canvas

    def press(self, *keys: str) -> None:
        """Deliver Textual key names to the canvas' on_key callback."""
        canvas = self.require_canvas()
        for key in keys:
            canvas.key(key)

    def tick(self, count: int = 1) -> None:
        """Fire *count* canvas clock ticks."""
        canvas = self.require_canvas()
        for _ in range(count):
            canvas.tick()

    def snapshot(self) -> dict[str, Any]:
        """The game's ``snapshot()`` table as plain Python data."""
        value = lua_to_python(self.module.snapshot())
        assert isinstance(value, dict), "snapshot() must return a table"
        return cast(dict[str, Any], value)

    def close(self) -> None:
        """Invoke the canvas close callback (as the screen does)."""
        self.require_canvas().close_cb()


def engine_runtime(api: FakeApi | None = None) -> tuple[Any, FakeApi]:
    """A lua runtime with the shared engine aliased as the global ``engine``."""
    holder = api if api is not None else FakeApi()
    runtime: Any = create_runtime(
        holder, lua_api_library_source(), lua_module_sources()
    )
    runtime.execute('engine = require("game_engine")')
    return runtime, holder


def read_module_file(path: Path) -> str:
    """Read one Lua file (helper for tests that inspect shared sources)."""
    return path.read_text(encoding="utf-8")
