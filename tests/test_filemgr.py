"""Pilot tests for the L2 FileManagerScreen (file-manager plan-d).

Screen-level tests following the test_palette.py ``_Host`` precedent: a
minimal host app pushes the screen wired with a tmp workspace and
recording stub callbacks, then the pilot drives keys / mouse and the
tests assert on the DOM, screen state and the file system.
"""

# tests legitimately poke at screen internals:
# pyright: reportPrivateUsage=false

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from textual.app import App
from textual.color import Color
from textual.widgets import Input, Static

from yate.config import FilePreviewConfig
from yate.editor_view import theme
from yate.editor_view import filemgr_keys
from yate.editor_view.filemgr import FileManagerScreen, _FileListView
from yate.editor_view.preview import PreviewLog
from yate.services.workspace import Workspace

from conftest import plain_text, wait_until


class _Host(App[None]):
    """Minimal host app that pushes the FileManagerScreen under test."""

    ENABLE_COMMAND_PALETTE = False

    def __init__(self, screen: FileManagerScreen) -> None:
        super().__init__()
        self._screen = screen

    def on_mount(self) -> None:
        self.push_screen(self._screen)


def _screen(
    tmp_path: Path,
    open_calls: list[list[Path]],
    close_calls: list[bool],
    *,
    fullscreen: bool = False,
    initial_dir: Path | None = None,
) -> FileManagerScreen:
    """A FileManagerScreen over *tmp_path* with recording stub callbacks."""
    return FileManagerScreen(
        workspace=Workspace(tmp_path),
        preview=FilePreviewConfig(),
        open_selected=open_calls.append,
        close=lambda: close_calls.append(True),
        fullscreen=fullscreen,
        initial_dir=initial_dir,
    )


def _list(screen: FileManagerScreen) -> _FileListView:
    """The middle-pane list of *screen*."""
    return screen.query_one("#filemgr-list", _FileListView)


def _entry_names(screen: FileManagerScreen) -> list[str]:
    """Names of the middle-pane entries in display order."""
    return [entry.name for entry in screen._entries]


def _status_text(screen: FileManagerScreen) -> str:
    """Plain text of the status bar."""
    return plain_text(screen.query_one("#filemgr-status", Static).content)


def _input_visible(screen: FileManagerScreen) -> bool:
    """Whether the bottom input line is currently shown."""
    return screen.query_one("#filemgr-input", Input).has_class("active")


def _preview_text(screen: FileManagerScreen) -> str:
    """Rendered plain text of the preview pane."""
    pane = screen.query_one("#filemgr-preview", PreviewLog)
    return "\n".join(strip.text for strip in pane.lines)


def _make_tree(tmp_path: Path) -> None:
    """Two directories and two text files, deterministic listing order."""
    (tmp_path / "sub").mkdir()
    (tmp_path / "other").mkdir()
    (tmp_path / "alpha.txt").write_text("alpha\n", encoding="utf-8")
    (tmp_path / "beta.txt").write_text("beta\n", encoding="utf-8")


def test_filemgr_renders_three_panes_and_status(tmp_path: Path) -> None:
    """Push mounts the three panes and the status bar; rows match list_dir."""
    _make_tree(tmp_path)

    async def scenario() -> None:
        app = _Host(_screen(tmp_path, [], []))
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, FileManagerScreen)
            assert screen.query("#filemgr-parent")
            assert screen.query("#filemgr-list")
            assert screen.query("#filemgr-preview")
            assert screen.query("#filemgr-status")
            expected = len(Workspace(tmp_path).list_dir(tmp_path))
            assert await wait_until(
                pilot, lambda: len(list(_list(screen).children)) == expected
            )
            assert _status_text(screen) != ""

    asyncio.run(scenario())


def test_filemgr_navigate_enter_dir_and_back_lands_on_origin(tmp_path: Path) -> None:
    """l enters a directory; h returns and the cursor lands on it (lf)."""
    _make_tree(tmp_path)
    (tmp_path / "sub" / "inner.txt").write_text("inner\n", encoding="utf-8")

    async def scenario() -> None:
        open_calls: list[list[Path]] = []
        app = _Host(_screen(tmp_path, open_calls, []))
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, FileManagerScreen)
            # dirs sort first: "other" < "sub", cursor starts on "other"
            await pilot.press("j")  # cursor onto "sub"
            assert _list(screen).index == 1
            await pilot.press("l")
            assert await wait_until(
                pilot, lambda: _entry_names(screen) == ["inner.txt"]
            )
            await pilot.press("h")
            assert await wait_until(
                pilot,
                lambda: _entry_names(screen)
                == ["other", "sub", "alpha.txt", "beta.txt"],
            )
            # the cursor landed back on the directory just left
            assert _list(screen).index == 1
            assert open_calls == []

    asyncio.run(scenario())


def test_filemgr_filter_narrows_and_esc_clears(tmp_path: Path) -> None:
    """``/`` opens filter mode; typing narrows; Esc restores the full list."""
    _make_tree(tmp_path)

    async def scenario() -> None:
        app = _Host(_screen(tmp_path, [], []))
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, FileManagerScreen)
            assert await wait_until(pilot, lambda: len(_entry_names(screen)) == 4)
            await pilot.press("slash")
            assert _input_visible(screen)
            await pilot.press("a")  # "a" matches alpha/beta, not the dirs
            assert await wait_until(pilot, lambda: len(_entry_names(screen)) == 2)
            await pilot.press("escape")
            assert not _input_visible(screen)
            assert await wait_until(pilot, lambda: len(_entry_names(screen)) == 4)
            assert screen._filter is None

    asyncio.run(scenario())


def test_filemgr_sort_cycles_with_dirs_first(tmp_path: Path) -> None:
    """``s`` cycles name -> size -> mtime in the status bar; dirs stay first."""
    (tmp_path / "zdir").mkdir()
    (tmp_path / "big.txt").write_text("x" * 1000, encoding="utf-8")
    (tmp_path / "small.txt").write_text("x", encoding="utf-8")

    async def scenario() -> None:
        app = _Host(_screen(tmp_path, [], []))
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, FileManagerScreen)
            assert await wait_until(pilot, lambda: len(_entry_names(screen)) == 3)
            await pilot.press("s")
            assert "size asc" in _status_text(screen)
            assert _entry_names(screen) == ["zdir", "small.txt", "big.txt"]
            await pilot.press("s")
            assert "mtime asc" in _status_text(screen)
            await pilot.press("s")
            assert "name asc" in _status_text(screen)
            assert _entry_names(screen) == ["zdir", "big.txt", "small.txt"]
            # the directory always stays first across the whole cycle
            assert screen._entries[0].is_dir

    asyncio.run(scenario())


def test_filemgr_toggle_hidden_and_refresh(tmp_path: Path) -> None:
    """``H`` reveals dotfiles; ``r`` rebuilds the same listing."""
    (tmp_path / "visible.txt").write_text("v\n", encoding="utf-8")
    (tmp_path / ".dotfile").write_text("d\n", encoding="utf-8")

    async def scenario() -> None:
        app = _Host(_screen(tmp_path, [], []))
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, FileManagerScreen)
            assert await wait_until(
                pilot, lambda: _entry_names(screen) == ["visible.txt"]
            )
            await pilot.press("H")
            assert await wait_until(
                pilot, lambda: _entry_names(screen) == [".dotfile", "visible.txt"]
            )
            assert screen.workspace.show_hidden is True
            await pilot.press("r")
            assert await wait_until(
                pilot, lambda: _entry_names(screen) == [".dotfile", "visible.txt"]
            )

    asyncio.run(scenario())


def test_filemgr_mark_and_invert_and_open_collection(tmp_path: Path) -> None:
    """Space marks, v inverts, Enter hands the marked collection to the stub."""
    _make_tree(tmp_path)  # dirs other/sub, files alpha.txt/beta.txt

    async def scenario() -> None:
        open_calls: list[list[Path]] = []
        app = _Host(_screen(tmp_path, open_calls, []))
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, FileManagerScreen)
            assert await wait_until(pilot, lambda: len(_entry_names(screen)) == 4)
            # cursor starts on "other"; mark it, then jump to beta.txt
            await pilot.press("space")
            await pilot.press("G")
            assert screen._marked == {tmp_path / "other"}
            # invert: other off, sub/alpha/beta on; the cursor (beta) stays
            await pilot.press("v")
            assert screen._marked == {
                tmp_path / "sub",
                tmp_path / "alpha.txt",
                tmp_path / "beta.txt",
            }
            # wait for the rebuilt rows to restore the cursor on beta.txt
            assert await wait_until(pilot, lambda: _list(screen).index == 3)
            await pilot.press("enter")
            assert await wait_until(pilot, lambda: bool(open_calls))
            assert open_calls == [
                sorted(
                    [
                        tmp_path / "alpha.txt",
                        tmp_path / "beta.txt",
                        tmp_path / "sub",
                    ]
                )
            ]
            # the screen dismissed itself before calling the stub (Q3 order)
            assert not isinstance(app.screen, FileManagerScreen)

    asyncio.run(scenario())


def test_filemgr_double_click_opens_via_selected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Single click moves the cursor only; a double click opens the file.

    Textual 8.2.8 posts ``ListView.Selected`` on every single item
    click, so the built-in double-click behavior does not exist and the
    plan's on_click + monotonic fallback is under test (the 300ms window
    is patched wide to keep the test off real-sleep timing).
    """
    monkeypatch.setattr(filemgr_keys, "DOUBLE_CLICK_WINDOW", 30.0)
    _make_tree(tmp_path)
    target = tmp_path / "alpha.txt"

    async def scenario() -> None:
        open_calls: list[list[Path]] = []
        app = _Host(_screen(tmp_path, open_calls, []))
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, FileManagerScreen)
            assert await wait_until(pilot, lambda: len(_entry_names(screen)) == 4)
            row = list(_list(screen).children)[2]  # alpha.txt row
            await pilot.click(row, offset=(2, 0))
            await pilot.pause()
            # a single click only moves the cursor onto the row
            assert open_calls == []
            assert _list(screen).index == 2
            await pilot.click(row, offset=(2, 0))
            assert await wait_until(pilot, lambda: bool(open_calls))
            assert open_calls == [[target]]
            assert not isinstance(app.screen, FileManagerScreen)

    asyncio.run(scenario())


def test_filemgr_preview_shows_tokens_and_binary_note(tmp_path: Path) -> None:
    """Text previews render highlighted lines; binary files degrade to a note."""
    (tmp_path / "code.py").write_text(
        "def hello():\n    return 'world'\n", encoding="utf-8"
    )
    (tmp_path / "blob.bin").write_bytes(b"\x00\x01\x02")

    async def scenario() -> None:
        app = _Host(_screen(tmp_path, [], []))
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, FileManagerScreen)
            # cursor starts on blob.bin (first file, no dirs): note payload
            assert await wait_until(
                pilot, lambda: "(binary file)" in _preview_text(screen)
            )
            await pilot.press("j")  # onto code.py
            assert await wait_until(pilot, lambda: "world" in _preview_text(screen))
            source = tmp_path / "code.py"
            entry = screen._preview_cache.get(
                source, source.stat().st_mtime_ns, source.stat().st_size
            )
            assert entry is not None
            assert entry.note is None
            assert any(tokens for tokens in entry.tokens)

    asyncio.run(scenario())


def test_filemgr_escape_exits_filter_then_marks_then_closes(tmp_path: Path) -> None:
    """Esc steps back level by level: filter, then marks, then close."""
    _make_tree(tmp_path)

    async def scenario() -> None:
        open_calls: list[list[Path]] = []
        close_calls: list[bool] = []
        app = _Host(_screen(tmp_path, open_calls, close_calls))
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, FileManagerScreen)
            assert await wait_until(pilot, lambda: len(_entry_names(screen)) == 4)
            # level 1: an active filter is cleared first, screen stays open
            await pilot.press("slash")
            await pilot.press("a")
            assert await wait_until(pilot, lambda: len(_entry_names(screen)) == 2)
            await pilot.press("escape")
            assert not _input_visible(screen)
            assert await wait_until(pilot, lambda: len(_entry_names(screen)) == 4)
            assert isinstance(app.screen, FileManagerScreen)
            # level 2: marks are cleared next
            await pilot.press("space")
            assert screen._marked
            await pilot.press("escape")
            assert not screen._marked
            assert close_calls == []
            # level 3: only then does the screen close through the callback
            await pilot.press("escape")
            assert close_calls == [True]

    asyncio.run(scenario())


def test_filemgr_theme_switch_repaints_rows(tmp_path: Path) -> None:
    """A theme switch repaints the rows with the new accent (and scrollbars)."""
    _make_tree(tmp_path)
    original = theme.active().name
    switched = "latte" if original != "latte" else "frappe"

    async def scenario() -> None:
        app = _Host(_screen(tmp_path, [], []))
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, FileManagerScreen)
            assert await wait_until(pilot, lambda: bool(screen._rows))
            try:
                before_accent = theme.active().accent
                theme.set_theme(switched)
                after_accent = theme.active().accent
                assert after_accent != before_accent
                # rows were rebuilt synchronously with the new accent
                dir_row = screen._rows[0]  # dirs sort first
                assert any(span.style == after_accent for span in dir_row.spans)
                # the middle-pane scrollbar palette followed the theme
                assert _list(screen).styles.scrollbar_color == Color.parse(
                    theme.active().border
                )
                await pilot.pause()
            finally:
                theme.set_theme(original)

    asyncio.run(scenario())


def test_filemgr_file_ops_create_rename_delete(tmp_path: Path) -> None:
    """a creates a file, R renames it, d + y deletes it (disk assertions)."""
    (tmp_path / "alpha.txt").write_text("a\n", encoding="utf-8")

    async def scenario() -> None:
        app = _Host(_screen(tmp_path, [], []))
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, FileManagerScreen)
            input_widget = screen.query_one("#filemgr-input", Input)
            # create
            await pilot.press("a")
            assert _input_visible(screen)
            for ch in "new.txt":
                await pilot.press(ch)
            await pilot.press("enter")
            assert await wait_until(pilot, lambda: (tmp_path / "new.txt").exists())
            assert not _input_visible(screen)
            # rename: move the cursor onto new.txt first
            assert await wait_until(pilot, lambda: "new.txt" in _entry_names(screen))
            await pilot.press("j")  # alpha.txt -> new.txt
            await pilot.press("R")
            assert input_widget.value == "new.txt"
            await pilot.press("ctrl+u")  # clear the prefilled name
            for ch in "renamed.txt":
                await pilot.press(ch)
            await pilot.press("enter")
            assert await wait_until(pilot, lambda: (tmp_path / "renamed.txt").exists())
            assert not (tmp_path / "new.txt").exists()
            # delete with confirmation: cursor onto renamed.txt first
            assert await wait_until(pilot, lambda: "renamed.txt" in _entry_names(screen))
            await pilot.press("j")  # alpha.txt -> renamed.txt
            await pilot.press("d")
            assert _input_visible(screen)
            assert "type y to confirm" in input_widget.placeholder
            await pilot.press("y")
            await pilot.press("enter")
            assert await wait_until(
                pilot, lambda: not (tmp_path / "renamed.txt").exists()
            )
            assert not _input_visible(screen)

    asyncio.run(scenario())


def test_filemgr_fullscreen_css_class_switches_layout(tmp_path: Path) -> None:
    """fullscreen=True adds the class and #filemgr covers the whole screen."""
    _make_tree(tmp_path)

    async def scenario() -> None:
        app = _Host(_screen(tmp_path, [], [], fullscreen=True))
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, FileManagerScreen)
            assert screen.has_class("fullscreen")
            container = screen.query_one("#filemgr")
            assert await wait_until(
                pilot, lambda: container.region.size == (100, 30)
            )

    asyncio.run(scenario())
