"""Runtime tests for the ctrl+p file preview pane (PaletteScreen).

Pilot-driven (headless Textual): a minimal host app pushes the palette
screen, then the tests drive the cursor and assert on the preview pane's
DOM order, worker cache, degradation notes and legacy-DOM preservation.
"""

# tests legitimately poke at screen internals:
# pyright: reportPrivateUsage=false

from __future__ import annotations

import asyncio
from dataclasses import replace
from pathlib import Path

import pytest
from textual.app import App
from textual.color import Color
from textual.containers import Horizontal
from textual.widgets import Static

from yate.config import FilePreviewConfig
from yate.editor_syntax.tokens import SYNTAX_KINDS
from yate.editor_view import theme
from yate.editor_view.palette import (
    PREVIEW_CACHE_SIZE,
    PaletteScreen,
    PreviewLog,
    _PreviewData,
)
from yate.editor_view.scrollbars import SlimScrollBarRender
from yate.registries import ActionRegistry, CommandRegistry
from yate.services.workspace import Workspace

from conftest import wait_until


class _Host(App[None]):
    """Minimal host app that pushes the PaletteScreen under test."""

    # The real YateApp disables Textual's built-in command palette; without
    # this a ctrl+p press would open that stock palette instead of reaching
    # PaletteScreen.on_key (the cursor-up path would never be exercised).
    ENABLE_COMMAND_PALETTE = False

    def __init__(self, screen: PaletteScreen) -> None:
        super().__init__()
        self._screen = screen

    def on_mount(self) -> None:
        self.push_screen(self._screen)


def _palette(
    root: Path,
    mode: str = "files",
    preview: FilePreviewConfig | None = None,
) -> PaletteScreen:
    """A PaletteScreen over *root* wired with inert collaborators."""
    return PaletteScreen(
        mode,
        workspace=Workspace(root),
        commands=CommandRegistry(),
        actions=ActionRegistry(),
        open_path=lambda _p: None,
        focus_editor=lambda: None,
        execute_action=lambda _name: True,
        run_command=lambda _name: None,
        refresh=lambda: None,
        preview=FilePreviewConfig() if preview is None else preview,
    )


def _preview_plain(screen: PaletteScreen) -> str:
    """Rendered plain text of the preview pane (strip text joined)."""
    pane = screen.query_one("#palette-preview", PreviewLog)
    return "\n".join(strip.text for strip in pane.lines)


ALPHA_SOURCE = "def hello():\n    return 'world'\n"


def test_files_mode_composes_preview_pane(tmp_path: Path) -> None:
    """Enabled files mode mounts the pane inside #palette-body, tagged."""
    (tmp_path / "alpha.py").write_text(ALPHA_SOURCE, encoding="utf-8")

    async def scenario() -> None:
        app = _Host(_palette(tmp_path))
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, PaletteScreen)
            assert screen.query("#palette-preview")
            assert screen.has_class("with-preview")
            body = screen.query_one("#palette-body", Horizontal)
            assert body.query("#palette-results")
            assert body.query(PreviewLog)

    asyncio.run(scenario())


def test_preview_pane_scrollbar_palette(tmp_path: Path) -> None:
    """Pane scrollbars mount slim-rendered with the explorer palette (IKJUU2)."""
    (tmp_path / "alpha.py").write_text(ALPHA_SOURCE, encoding="utf-8")

    async def scenario() -> None:
        app = _Host(_palette(tmp_path))
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, PaletteScreen)
            pane = screen.query_one("#palette-preview", PreviewLog)
            # slim partial-block renderer on both bars, injected per widget
            assert pane.vertical_scrollbar.renderer is SlimScrollBarRender
            assert pane.horizontal_scrollbar.renderer is SlimScrollBarRender
            # the full explorer palette (IKINF3): transparent track and corner
            # so only the sliver shows -- the default opaque track is what the
            # issue reports as a "thick" horizontal scrollbar
            t = theme.active()
            s = pane.styles
            assert s.scrollbar_background == Color(0, 0, 0, 0)
            assert s.scrollbar_background_hover == Color.parse(t.surface).with_alpha(0.35)
            assert s.scrollbar_color == Color.parse(t.border)
            assert s.scrollbar_color_hover == Color.parse(t.fg_dim)
            assert s.scrollbar_color_active == Color.parse(t.accent)
            assert s.scrollbar_corner_color == Color(0, 0, 0, 0)

    asyncio.run(scenario())


def test_preview_pane_scrollbar_follows_theme_change(tmp_path: Path) -> None:
    """A theme switch repaints the pane while mounted, not after unmount."""
    (tmp_path / "alpha.py").write_text(ALPHA_SOURCE, encoding="utf-8")
    # captured before any switch: restored in the finally block and used to
    # derive the switch target, so the restore broadcast differs from *other*
    original = theme.active().name

    async def scenario() -> None:
        app = _Host(_palette(tmp_path))
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, PaletteScreen)
            pane = screen.query_one("#palette-preview", PreviewLog)
            other = "latte" if original != "latte" else "mocha"
            theme.set_theme(other)
            assert pane.styles.scrollbar_color == Color.parse(theme.active().border)
            # popping the screen unmounts the pane and detaches the listener
            app.pop_screen()
            await pilot.pause()
        unmounted_color = pane.styles.scrollbar_color
        # the captured original differs from *other* by construction: a live
        # pane would repaint, keeping the negative assertion below meaningful
        theme.set_theme(original)
        # unmounted: the broadcast must no longer touch the pane
        assert pane.styles.scrollbar_color == unmounted_color

    try:
        asyncio.run(scenario())
    finally:
        theme.set_theme(original)


def test_disabled_preview_keeps_legacy_dom(tmp_path: Path) -> None:
    """enable=False: no pane widget, no class, results list untouched."""
    (tmp_path / "alpha.py").write_text(ALPHA_SOURCE, encoding="utf-8")

    async def scenario() -> None:
        app = _Host(_palette(tmp_path, preview=FilePreviewConfig(enable=False)))
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, PaletteScreen)
            assert not screen.query("#palette-preview")
            assert not screen.has_class("with-preview")
            # the index still fills the same filtered list as before
            assert await wait_until(pilot, lambda: screen.filtered_count == 1)

    asyncio.run(scenario())


def test_commands_mode_has_no_preview(tmp_path: Path) -> None:
    """Commands mode ignores the preview config entirely."""
    (tmp_path / "alpha.py").write_text(ALPHA_SOURCE, encoding="utf-8")

    async def scenario() -> None:
        app = _Host(_palette(tmp_path, mode="commands"))
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, PaletteScreen)
            assert not screen.query("#palette-preview")
            assert not screen.has_class("with-preview")

    asyncio.run(scenario())


def test_preview_follows_cursor(tmp_path: Path) -> None:
    """Moving the cursor re-previews the newly highlighted file."""
    alpha = tmp_path / "alpha.py"
    beta = tmp_path / "beta.md"
    alpha.write_text(ALPHA_SOURCE, encoding="utf-8")
    beta.write_text("second file\n", encoding="utf-8")

    async def scenario() -> None:
        app = _Host(_palette(tmp_path))
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, PaletteScreen)
            assert await wait_until(
                pilot, lambda: screen._preview_cache.get(alpha) is not None
            )
            await pilot.press("down")
            assert await wait_until(
                pilot, lambda: screen._preview_cache.get(beta) is not None
            )
            data = screen._preview_cache[beta]
            assert data.path == beta
            assert data.lines == ["second file"]
            assert screen._selected_path() == beta

    asyncio.run(scenario())


def test_preview_shows_syntax_tokens(tmp_path: Path) -> None:
    """A python file tokenizes into SYNTAX_KINDS spans (def/return keywords)."""
    alpha = tmp_path / "alpha.py"
    alpha.write_text(ALPHA_SOURCE, encoding="utf-8")

    async def scenario() -> None:
        app = _Host(_palette(tmp_path))
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, PaletteScreen)
            assert await wait_until(
                pilot, lambda: screen._preview_cache.get(alpha) is not None
            )
            data = screen._preview_cache[alpha]
            assert data.tokens
            kinds = {tok.kind for row in data.tokens for tok in row}
            assert "keyword" in kinds
            assert kinds <= set(SYNTAX_KINDS)

    asyncio.run(scenario())


def test_preview_truncates_large_file(tmp_path: Path) -> None:
    """A 3000-line file is cut at max_lines and flagged in the pane."""
    alpha = tmp_path / "alpha.py"
    alpha.write_text(
        "\n".join(f"x{i} = {i}" for i in range(3000)), encoding="utf-8"
    )

    async def scenario() -> None:
        app = _Host(_palette(tmp_path))
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, PaletteScreen)
            assert await wait_until(
                pilot, lambda: screen._preview_cache.get(alpha) is not None
            )
            data = screen._preview_cache[alpha]
            assert data.truncated
            assert len(data.lines) == screen.preview.max_lines
            assert "truncated" in screen._preview_text(data).plain

    asyncio.run(scenario())


def test_preview_reports_binary(tmp_path: Path) -> None:
    """A binary file degrades to the (binary file) note in the pane."""
    alpha = tmp_path / "blob.bin"
    alpha.write_bytes(b"\x00\x01\x02binary stuff\x00")

    async def scenario() -> None:
        app = _Host(_palette(tmp_path))
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, PaletteScreen)
            assert await wait_until(
                pilot, lambda: "(binary file)" in _preview_plain(screen)
            )

    asyncio.run(scenario())


def test_preview_reports_oversize(tmp_path: Path) -> None:
    """A file over max_size degrades to the 'file too large' note."""
    alpha = tmp_path / "alpha.py"
    alpha.write_text("payload = " + "x" * 200, encoding="utf-8")

    async def scenario() -> None:
        app = _Host(_palette(tmp_path, preview=FilePreviewConfig(max_size=64)))
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, PaletteScreen)
            assert await wait_until(
                pilot, lambda: "file too large" in _preview_plain(screen)
            )

    asyncio.run(scenario())


def test_preview_cache_hits_without_reread(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Revisiting a file serves from cache: no second _load_preview call."""
    alpha = tmp_path / "alpha.py"
    beta = tmp_path / "beta.md"
    alpha.write_text(ALPHA_SOURCE, encoding="utf-8")
    beta.write_text("second file\n", encoding="utf-8")

    calls: list[Path] = []
    original = PaletteScreen._load_preview

    def _counting(screen: PaletteScreen, path: Path) -> _PreviewData:
        calls.append(path)
        return original(screen, path)

    monkeypatch.setattr(PaletteScreen, "_load_preview", _counting)

    async def scenario() -> None:
        app = _Host(_palette(tmp_path))
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, PaletteScreen)
            # mount previews alpha; down selects beta; wrap + up revisit both
            assert await wait_until(
                pilot, lambda: screen._preview_cache.get(alpha) is not None
            )
            await pilot.press("down")
            assert await wait_until(
                pilot, lambda: screen._preview_cache.get(beta) is not None
            )
            assert screen.cursor_index == 1
            await pilot.press("ctrl+n")  # wraps back to alpha: cache hit
            assert screen.cursor_index == 0
            await pilot.press("ctrl+p")  # cursor-up path, back to beta
            await pilot.pause()
            assert screen.cursor_index == 1
            assert calls == [alpha, beta]

    asyncio.run(scenario())


def test_preview_position_left_reorders_dom(tmp_path: Path) -> None:
    """position=left composes the pane before the results list."""
    (tmp_path / "alpha.py").write_text(ALPHA_SOURCE, encoding="utf-8")

    async def scenario() -> None:
        app = _Host(_palette(tmp_path, preview=FilePreviewConfig(position="left")))
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, PaletteScreen)
            body = screen.query_one("#palette-body", Horizontal)
            children = list(body.children)
            assert isinstance(children[0], PreviewLog)
            assert isinstance(children[1], Static)

    asyncio.run(scenario())


# ------------------------------------------------- error / cache edge paths


def test_load_preview_reports_unreadable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A stat failure degrades to a note payload instead of raising."""

    def denied(self: Path, **_kw: object) -> int:
        raise OSError(13, "permission denied")

    monkeypatch.setattr(Path, "stat", denied)
    screen = _palette(tmp_path)
    data = screen._load_preview(tmp_path / "secret.txt")
    assert data.note is not None and "cannot read" in data.note
    assert data.lines == [] and data.tokens == []


def test_cache_store_evicts_oldest(tmp_path: Path) -> None:
    """Insertion order is the eviction order; capacity stays at the cap."""
    screen = _palette(tmp_path)
    paths = [tmp_path / f"p{i}.txt" for i in range(PREVIEW_CACHE_SIZE + 1)]

    def payload(i: int) -> _PreviewData:
        return _PreviewData(
            path=paths[i], lines=[], tokens=[], mtime_ns=i, size=0,
            truncated=False, note=None,
        )

    for i in range(len(paths)):
        screen._cache_store(payload(i))
    assert len(screen._preview_cache) == PREVIEW_CACHE_SIZE
    assert paths[0] not in screen._preview_cache
    assert paths[-1] in screen._preview_cache
    # re-storing an existing key must not evict anything
    screen._cache_store(payload(PREVIEW_CACHE_SIZE))
    assert len(screen._preview_cache) == PREVIEW_CACHE_SIZE


def test_cache_current_detects_stale(tmp_path: Path) -> None:
    """mtime/size probe validates entries; missing files read as stale."""
    target = tmp_path / "alpha.py"
    target.write_text(ALPHA_SOURCE, encoding="utf-8")
    screen = _palette(tmp_path)
    data = screen._load_preview(target)
    assert data.note is None
    assert screen._cache_current(data)
    target.write_text(ALPHA_SOURCE + "# touched\n", encoding="utf-8")
    assert not screen._cache_current(data)
    assert not screen._cache_current(replace(data, path=tmp_path / "gone.py"))


def test_preview_renders_plain_lines_when_tokenize_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A tokenizer crash degrades to the plain lines, not a blank pane."""

    def boom(lines: list[str], filetype: str) -> object:
        raise RuntimeError("tokenizer exploded")

    # patch the consumer-side name: palette.py from-imports tokenize_document
    monkeypatch.setattr("yate.editor_view.palette.tokenize_document", boom)
    alpha = tmp_path / "alpha.py"
    alpha.write_text(ALPHA_SOURCE, encoding="utf-8")

    async def scenario() -> None:
        app = _Host(_palette(tmp_path))
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, PaletteScreen)
            assert await wait_until(
                pilot, lambda: screen._preview_cache.get(alpha) is not None
            )
            plain = _preview_plain(screen)
            assert "def hello():" in plain
            assert "return 'world'" in plain

    asyncio.run(scenario())


def test_update_preview_passes_worker_callable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """_update_preview hands run_worker a callable, never an eager coroutine."""
    (tmp_path / "alpha.py").write_text(ALPHA_SOURCE, encoding="utf-8")
    (tmp_path / "beta.md").write_text("second file\n", encoding="utf-8")

    async def scenario() -> None:
        app = _Host(_palette(tmp_path))
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, PaletteScreen)
            captured: list[object] = []

            def _recorder(_screen: object, job: object, **_kw: object) -> None:
                captured.append(job)

            # on_mount already ran its index worker; the patch only watches
            # the preview spawns triggered from here on.
            monkeypatch.setattr(PaletteScreen, "run_worker", _recorder)
            await pilot.press("down")  # beta: cache miss -> _update_preview
            await pilot.pause()
            assert captured, "cursor move must spawn a preview worker"
            job = captured[0]
            assert callable(job)
            assert not asyncio.iscoroutine(job)

    asyncio.run(scenario())
