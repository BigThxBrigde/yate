"""L2 status-bar recording indicator (macro feature, wave-1 plan-c).

The bar pulls its indicator text from an injected ``recording_label``
callable.  Tests construct a fresh, unmounted ``StatusBar`` over the
concrete collaborators of a running ``YateApp`` status bar (the same
pattern ``tests/test_ui_contributions.py`` uses), so no host protocol or
L3 wiring is involved.  Rendered text is read as ``str(bar.render())``.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import pytest

from yate.app import YateApp
from yate.editor_components import theme
from yate.editor_components.statusbar import StatusBar


def _target(tmp_path: Path, name: str) -> Path:
    """A single-line scratch file for a ``YateApp`` target."""
    path = tmp_path / name
    path.write_text("x\n", encoding="utf-8")
    return path


def test_statusbar_shows_recording_label_when_provider_returns_text(
    tmp_path: Path,
) -> None:
    """A provider returning ``rec @a`` paints the indicator by the mode chip."""

    async def scenario() -> None:
        target = _target(tmp_path, "show.txt")
        app = YateApp(target=target)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            real = app.editor.status_bar
            bar = StatusBar(
                real.session, real.lsp, real.keymaps, real.prompt,
                recording_label=lambda: "rec @a",
            )
            bar.refresh_status()
            rendered = str(bar.render())
            assert "rec @a" in rendered
            assert any(mode in rendered for mode in ("VSC", "NORMAL"))

    asyncio.run(scenario())


def test_statusbar_hides_recording_label_when_provider_returns_none(
    tmp_path: Path,
) -> None:
    """A ``None`` provider matches a bar built with no provider at all."""

    async def scenario() -> None:
        target = _target(tmp_path, "none.txt")
        app = YateApp(target=target)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            real = app.editor.status_bar
            with_none = StatusBar(
                real.session, real.lsp, real.keymaps, real.prompt,
                recording_label=lambda: None,
            )
            bare = StatusBar(real.session, real.lsp, real.keymaps, real.prompt)
            with_none.refresh_status()
            bare.refresh_status()
            rendered = str(with_none.render())
            assert "rec @" not in rendered
            assert rendered == str(bare.render())

    asyncio.run(scenario())


def test_statusbar_repaints_when_recording_label_changes(
    tmp_path: Path,
) -> None:
    """The label sits in the fingerprint, so a changed label forces a repaint."""

    async def scenario() -> None:
        target = _target(tmp_path, "repaint.txt")
        app = YateApp(target=target)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            real = app.editor.status_bar
            box: dict[str, str | None] = {"v": "rec @a"}
            bar = StatusBar(
                real.session, real.lsp, real.keymaps, real.prompt,
                recording_label=lambda: box["v"],
            )
            bar.refresh_status()
            first = str(bar.render())
            assert "rec @a" in first
            assert "rec @b" not in first
            box["v"] = "rec @b"
            bar.refresh_status()
            second = str(bar.render())
            assert "rec @b" in second
            assert "rec @a" not in second

    asyncio.run(scenario())


def test_statusbar_standalone_construction_without_provider(
    tmp_path: Path,
) -> None:
    """Omitting the parameter keeps the standalone construction working."""

    async def scenario() -> None:
        target = _target(tmp_path, "standalone.txt")
        app = YateApp(target=target)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            real = app.editor.status_bar
            bar = StatusBar(real.session, real.lsp, real.keymaps, real.prompt)
            assert bar.recording_label is None
            bar.refresh_status()
            assert "rec @" not in str(bar.render())

    asyncio.run(scenario())


def test_statusbar_raising_provider_degrades_gracefully(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A raising provider is logged, hidden, and leaves a clean fingerprint."""

    def boom() -> str | None:
        raise RuntimeError("boom")

    # The yate logger tree sets propagate = False, so caplog's root handler
    # only sees these records once propagation is re-enabled for the test.
    monkeypatch.setattr(logging.getLogger("yate"), "propagate", True)
    caplog.set_level(logging.DEBUG, logger="yate")

    async def scenario() -> None:
        target = _target(tmp_path, "boom.txt")
        app = YateApp(target=target)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            real = app.editor.status_bar
            bar = StatusBar(
                real.session, real.lsp, real.keymaps, real.prompt,
                recording_label=boom,
            )
            bar.refresh_status()
            assert "rec @" not in str(bar.render())
            # A failed pull must not poison the fingerprint: a later healthy
            # label still repaints the bar.
            bar.recording_label = lambda: "rec @a"
            bar.refresh_status()
            assert "rec @a" in str(bar.render())

    asyncio.run(scenario())
    assert "status recording label provider failed" in caplog.text


def test_statusbar_recording_indicator_counts_into_name_budget(
    tmp_path: Path,
) -> None:
    """A long indicator shrinks the name budget and never overflows width."""
    label = "rec @" + "a" * 25

    async def scenario() -> None:
        target = _target(tmp_path, "note.txt")
        app = YateApp(target=target)
        async with app.run_test(size=(40, 24)) as pilot:
            await pilot.pause()
            bar = app.editor.status_bar
            bar.refresh_status()
            without = str(bar.render())
            assert "note.txt" in without
            bar.recording_label = lambda: label
            bar.refresh_status()
            rendered = str(bar.render())
            assert label in rendered
            assert "note.txt" not in rendered
            assert theme.cell_len(rendered) <= 40

    asyncio.run(scenario())
