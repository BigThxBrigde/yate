"""Coverage for the ``wrap`` option surface (soft-wrap Plan C).

The option lives in three places that must agree: the yaterc loader
(:mod:`yate.yaterc_options` folds ``wrap`` into a real
:class:`~yate.config.YateConfig` field), the ``:set`` table
(:data:`yate.config.SET_OPTION_SPECS` -> ``commands._apply_wrap``) and the
runtime toggle action (``editor.toggle_soft_wrap`` via the action table).
Default is off, so existing yaterc files need no migration.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import cast

from yate.app import YateApp
from yate.commands import register_commands
from yate.config import YateConfig
from yate.editor import Editor
from yate.registries import CommandRegistry
from yate.yaterc import load_config
from yate.yaterc_options import _extract_options


def test_default_wrap_is_off() -> None:
    """A fresh config keeps soft wrap off (no-wrap is the status quo)."""
    assert YateConfig().wrap is False


def test_yaterc_wrap_true_parses_on(tmp_path: Path) -> None:
    """``wrap = True`` in a yaterc file lands on the config, error-free."""
    rc = tmp_path / "yaterc"
    rc.write_text("wrap = True\n", encoding="utf-8")

    config = load_config([rc])

    assert config.sources == [rc]
    assert config.wrap is True
    assert config.errors == []


def test_yaterc_wrap_invalid_value_reports_error(tmp_path: Path) -> None:
    """A non-bool ``wrap`` is reported and the option keeps its default."""

    def scenario(name: str, source: str) -> None:
        rc = tmp_path / name
        rc.write_text(source, encoding="utf-8")

        config = load_config([rc])

        assert config.sources == [rc]
        assert config.errors, f"{source.strip()!r} must be reported"
        assert any("wrap must be True or False" in error for error in config.errors)
        assert config.wrap is False

    scenario("yaterc-str", 'wrap = "maybe"\n')
    scenario("yaterc-int", "wrap = 1\n")


def test_extract_options_rejects_non_bool_wrap() -> None:
    """The scalar validator reports non-bool values and keeps the default."""
    config = YateConfig()
    _extract_options({"wrap": 1}, config)
    assert any("wrap must be True or False" in error for error in config.errors)
    assert config.wrap is False


# --- :set dispatch ------------------------------------------------------------


class _SetEditor:
    """Editor stand-in for ``:set`` dispatch: real config, recorded flips."""

    def __init__(self) -> None:
        self.config = YateConfig()
        self.flips: list[bool] = []

    def set_soft_wrap(self, enabled: bool) -> None:
        """Mirror the real editor: store the value, record the flip."""
        self.config.wrap = enabled
        self.flips.append(enabled)

    def message(self, text: str, kind: str = "") -> None:
        """Accept a message-line write (not asserted here)."""


def test_set_wrap_on_flips_config() -> None:
    """``:set wrap=on`` flips the config switch through the editor hook."""
    editor = _SetEditor()
    registry = CommandRegistry()
    register_commands(registry, cast(Editor, editor))
    entry = registry.get("set")
    assert entry is not None

    entry.func("wrap=on")

    assert editor.config.wrap is True
    assert editor.flips == [True]


# --- toggle action ------------------------------------------------------------


def _doc(tmp_path: Path) -> Path:
    doc = tmp_path / "note.txt"
    doc.write_text("hello soft wrap\n", encoding="utf-8")
    return doc


def test_toggle_soft_wrap_action_flips_twice_back(tmp_path: Path) -> None:
    """The toggle action flips ``config.wrap``; two flips return to the start."""

    async def scenario() -> None:
        app = YateApp(target=_doc(tmp_path))
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            start = app.editor.config.wrap
            assert start is False

            app.editor.execute_action("toggle_soft_wrap")
            await pilot.pause()
            assert app.editor.config.wrap is True

            app.editor.execute_action("toggle_soft_wrap")
            await pilot.pause()
            assert app.editor.config.wrap is False

    asyncio.run(scenario())
