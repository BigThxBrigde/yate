"""Tests for the extension UI contribution point (status bar segments).

Bridge-level tests cover the pull-model registry (dedup / removal /
sorted snapshot / A13 rollback); pilot-level tests cover the StatusBar
rendering side (left/right placement, failing-provider placeholder and
None/empty hiding).
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from yate.app import YateApp
from yate.config import YateConfig
from yate.editor_lsp.manager import LspManager
from yate.keymaps.base import Keymap
from yate.keymaps.registry import KeymapSet
from yate.registries import ActionRegistry, CommandRegistry
from yate.session import EditorSession
from yate.services.extension_bridges import StatusSegment
from yate.services.extensions import ExtensionAPI, ExtensionContext
from yate.services.workspace import Workspace


@pytest.fixture
def api() -> ExtensionAPI:
    """An ExtensionAPI over real registries (the test_extension_api shape)."""
    session = EditorSession(YateConfig())
    session.new_buffer()
    ctx = ExtensionContext(
        session=session,
        workspace=Workspace(),
        lsp=LspManager(),
        keymaps=KeymapSet({"vsc": Keymap(), "vim": Keymap()}, "vsc"),
        actions=ActionRegistry(),
        commands=CommandRegistry(),
        message=lambda _text: None,
        run_shell=lambda _command, _show: None,
        open_path=lambda _path: None,
        save=lambda: None,
    )
    return ExtensionAPI(ctx)


# ------------------------------------------------------- bridge (pull registry)


def test_segment_registration_dedup_and_removal(api: ExtensionAPI) -> None:
    """Duplicate ids raise; removal drops the segment; unknown removal raises."""
    api.ui.add_status_segment(StatusSegment(id="a", provider=lambda: "A"))
    with pytest.raises(ValueError):
        api.ui.add_status_segment(StatusSegment(id="a", provider=lambda: "A2"))
    api.ui.remove_status_segment("a")
    assert api.ui.segments("left") == []
    assert api.ui.segments("right") == []
    with pytest.raises(KeyError):
        api.ui.remove_status_segment("a")


def test_segments_snapshot_sorted_by_priority(api: ExtensionAPI) -> None:
    """segments() filters by align and sorts by (-priority, registration order)."""
    api.ui.add_status_segment(
        StatusSegment(id="r1", provider=lambda: None, align="right")
    )
    api.ui.add_status_segment(
        StatusSegment(id="r9", provider=lambda: None, align="right", priority=9)
    )
    api.ui.add_status_segment(
        StatusSegment(id="r5a", provider=lambda: None, align="right", priority=5)
    )
    api.ui.add_status_segment(
        StatusSegment(id="r5b", provider=lambda: None, align="right", priority=5)
    )
    api.ui.add_status_segment(
        StatusSegment(id="l1", provider=lambda: None, align="left")
    )
    assert [seg.id for seg in api.ui.segments("right")] == [
        "r9", "r5a", "r5b", "r1",
    ]
    assert [seg.id for seg in api.ui.segments("left")] == ["l1"]


def test_segment_registration_rolls_back(api: ExtensionAPI) -> None:
    """A failing setup's segment add/remove calls are undone (A13)."""
    api.ui.add_status_segment(StatusSegment(id="kept", provider=lambda: "kept"))
    api.start_scope()
    api.ui.add_status_segment(
        StatusSegment(id="dropped", provider=lambda: "dropped")
    )
    api.ui.remove_status_segment("kept")
    api.rollback_scope()
    # the pre-scope registration is restored, the in-scope one is gone
    assert [seg.id for seg in api.ui.segments("right")] == ["kept"]
    assert api.ui.segments("left") == []


# ------------------------------------------------------- status bar rendering


def _status_strip(app: YateApp) -> str:
    """The status bar's rendered text as one plain string."""
    return "".join(seg.text for seg in app.editor.status_bar.render_line(0))


def test_statusbar_renders_extension_segments(tmp_path: Path) -> None:
    """Left/right extension segments land on their bar halves."""

    async def scenario() -> None:
        target = tmp_path / "seg.txt"
        target.write_text("x\n", encoding="utf-8")
        app = YateApp(target=target)
        app.editor.extension_api.ui.add_status_segment(
            StatusSegment(id="l", provider=lambda: "EXT-L", align="left")
        )
        app.editor.extension_api.ui.add_status_segment(
            StatusSegment(id="r", provider=lambda: "EXT-R", align="right")
        )
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            app.editor.status_bar.refresh_status()
            await pilot.pause()
            strip = _status_strip(app)
            assert "EXT-L" in strip
            assert "EXT-R" in strip
            # left extension trails the mode chip, right one leads the
            # position block of the existing right content
            assert strip.index("EXT-L") > strip.index("VSC")
            assert strip.index("EXT-R") < strip.index("Ln 1")

    asyncio.run(scenario())


def test_failing_provider_shows_placeholder_and_hides(tmp_path: Path) -> None:
    """A raising provider renders ``!`` without dropping the other segments."""

    async def scenario() -> None:
        target = tmp_path / "boom.txt"
        target.write_text("x\n", encoding="utf-8")
        app = YateApp(target=target)

        def boom() -> str | None:
            raise RuntimeError("boom")

        bridge = app.editor.extension_api.ui
        bridge.add_status_segment(
            StatusSegment(id="bad", provider=boom, align="right")
        )
        bridge.add_status_segment(
            StatusSegment(id="good", provider=lambda: "EXT-G", align="right")
        )
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            app.editor.status_bar.refresh_status()
            await pilot.pause()
            strip = _status_strip(app)
            # placeholder first (bad registered before good), then the
            # healthy segment, then the ordinary right block: one broken
            # provider neither crashes the app nor hides its neighbours
            assert strip.index("!") < strip.index("EXT-G")
            assert strip.index("EXT-G") < strip.index("Ln 1")
            assert app.is_running

    asyncio.run(scenario())


def test_none_provider_hides_segment(tmp_path: Path) -> None:
    """None/empty provider output hides the segment for that pass."""

    async def scenario() -> None:
        target = tmp_path / "none.txt"
        target.write_text("x\n", encoding="utf-8")
        app = YateApp(target=target)
        value: list[str | None] = [None]
        app.editor.extension_api.ui.add_status_segment(
            StatusSegment(id="maybe", provider=lambda: value[0], align="right")
        )
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            status_bar = app.editor.status_bar
            status_bar.refresh_status()
            await pilot.pause()
            assert "EXT-M" not in _status_strip(app)
            # once the provider has something to say, the next pull shows it
            value[0] = "EXT-M"
            status_bar.refresh_status()
            await pilot.pause()
            assert "EXT-M" in _status_strip(app)
            # an empty string hides it again
            value[0] = ""
            status_bar.refresh_status()
            await pilot.pause()
            assert "EXT-M" not in _status_strip(app)

    asyncio.run(scenario())
