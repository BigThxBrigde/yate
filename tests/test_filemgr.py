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
import sys
from pathlib import Path

import pytest
from textual.app import App
from textual.color import Color
from textual.widgets import Input, ListView, Static

from yate.config import FilePreviewConfig
from yate.editor_view import theme
from yate.editor_view import filemgr
from yate.editor_view.filemgr import FileManagerScreen, _FileListView
from yate.editor_view.preview import PreviewLog
from yate.services.workspace import Entry, EntryStat, Workspace

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
    renamed_calls: list[tuple[Path, Path]] | None = None,
    deleted_calls: list[Path] | None = None,
    hidden_calls: list[bool] | None = None,
) -> FileManagerScreen:
    """A FileManagerScreen over *tmp_path* with recording stub callbacks.

    The three sync callbacks (M2 / m5) record into the given lists when
    provided, otherwise into throwaway ones.
    """
    renamed = renamed_calls if renamed_calls is not None else []
    deleted = deleted_calls if deleted_calls is not None else []
    hidden = hidden_calls if hidden_calls is not None else []
    return FileManagerScreen(
        workspace=Workspace(tmp_path),
        preview=FilePreviewConfig(),
        open_selected=open_calls.append,
        close=lambda: close_calls.append(True),
        on_renamed=lambda old, new: renamed.append((old, new)),
        on_deleted=deleted.append,
        on_show_hidden_changed=hidden.append,
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


def _parent_texts(screen: FileManagerScreen) -> list[str]:
    """Plain texts of the left-pane rows."""
    pane = screen.query_one("#filemgr-parent", ListView)
    texts: list[str] = []
    for item in pane.children:
        for child in item.children:
            if isinstance(child, Static):
                texts.append(plain_text(child.content))
    return texts


def _input_visible(screen: FileManagerScreen) -> bool:
    """Whether the bottom input line is currently shown."""
    return screen.query_one("#filemgr-input", Input).has_class("active")


def _no_drives(self: Workspace) -> list[Entry]:
    """POSIX stand-in for ``Workspace.list_drives``: no drives (M1)."""
    return []


def _one_q_drive(self: Workspace) -> list[Entry]:
    """``Workspace.list_drives`` stand-in listing a single fake ``Q:``."""
    return [Entry(Path("Q:\\"), "Q:", True)]


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
    # the screen compares against its own by-value import (filemgr.py does
    # ``from filemgr_keys import DOUBLE_CLICK_WINDOW``), so the patch must
    # target the consumer module binding, not the source module attribute.
    monkeypatch.setattr(filemgr, "DOUBLE_CLICK_WINDOW", 30.0)
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


def test_filemgr_half_page_scrolls_cursor_down_and_up(tmp_path: Path) -> None:
    """ctrl+d / ctrl+u move the cursor by half a viewport, clamped."""
    for i in range(20):
        (tmp_path / f"f{i:02}.txt").write_text("x\n", encoding="utf-8")

    async def scenario() -> None:
        app = _Host(_screen(tmp_path, [], []))
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, FileManagerScreen)
            assert await wait_until(pilot, lambda: len(_entry_names(screen)) == 20)
            assert _list(screen).index == 0
            await pilot.press("ctrl+d")
            down = _list(screen).index
            assert down is not None and down > 0
            await pilot.press("ctrl+u")
            assert _list(screen).index == 0

    asyncio.run(scenario())


def test_filemgr_gg_prefix_jumps_to_top(tmp_path: Path) -> None:
    """``g`` ``g`` within the timeout jumps to the first row (lf semantics)."""
    _make_tree(tmp_path)

    async def scenario() -> None:
        app = _Host(_screen(tmp_path, [], []))
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, FileManagerScreen)
            assert await wait_until(pilot, lambda: len(_entry_names(screen)) == 4)
            await pilot.press("G")
            assert _list(screen).index == 3
            await pilot.press("g")
            await pilot.press("g")
            assert _list(screen).index == 0

    asyncio.run(scenario())


def test_filemgr_toggle_hidden_notifies_show_hidden_changed(tmp_path: Path) -> None:
    """``H`` flips the flag and reports every change to the injected hook (m5)."""
    (tmp_path / "visible.txt").write_text("v\n", encoding="utf-8")
    hidden_calls: list[bool] = []

    async def scenario() -> None:
        app = _Host(_screen(tmp_path, [], [], hidden_calls=hidden_calls))
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, FileManagerScreen)
            assert await wait_until(
                pilot, lambda: _entry_names(screen) == ["visible.txt"]
            )
            await pilot.press("H")
            assert hidden_calls == [True]
            assert screen.workspace.show_hidden is True
            await pilot.press("H")
            assert hidden_calls == [True, False]
            assert screen.workspace.show_hidden is False

    asyncio.run(scenario())


def test_filemgr_yank_then_paste_copies_entry(tmp_path: Path) -> None:
    """``y`` + ``p`` copies into the entered directory: source kept."""
    (tmp_path / "sub").mkdir()
    (tmp_path / "alpha.txt").write_text("alpha\n", encoding="utf-8")

    async def scenario() -> None:
        app = _Host(_screen(tmp_path, [], []))
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, FileManagerScreen)
            assert await wait_until(pilot, lambda: len(_entry_names(screen)) == 2)
            await pilot.press("j")  # cursor onto alpha.txt
            await pilot.press("y")  # yank
            await pilot.press("k")  # back onto sub
            await pilot.press("l")  # enter sub
            assert await wait_until(pilot, lambda: screen._cwd == tmp_path / "sub")
            await pilot.press("p")
            assert await wait_until(
                pilot, lambda: (tmp_path / "sub" / "alpha.txt").exists()
            )
            assert (tmp_path / "alpha.txt").read_text(encoding="utf-8") == "alpha\n"
            assert (
                (tmp_path / "sub" / "alpha.txt").read_text(encoding="utf-8")
                == "alpha\n"
            )
            # a copy buffer survives the paste
            assert screen._clipboard is not None

    asyncio.run(scenario())


def test_filemgr_yank_paste_copies_directory_recursively(tmp_path: Path) -> None:
    """Pasting a yanked directory copies the whole tree (copytree)."""
    (tmp_path / "srcdir").mkdir()
    (tmp_path / "srcdir" / "inner.txt").write_text("inner\n", encoding="utf-8")
    (tmp_path / "sub").mkdir()

    async def scenario() -> None:
        app = _Host(_screen(tmp_path, [], []))
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, FileManagerScreen)
            assert await wait_until(pilot, lambda: len(_entry_names(screen)) == 2)
            # cursor starts on srcdir (dirs first, name asc)
            await pilot.press("y")  # yank srcdir
            await pilot.press("j")  # onto sub
            await pilot.press("l")  # enter sub
            assert await wait_until(pilot, lambda: screen._cwd == tmp_path / "sub")
            await pilot.press("p")
            assert await wait_until(
                pilot, lambda: (tmp_path / "sub" / "srcdir" / "inner.txt").exists()
            )
            assert (
                (tmp_path / "sub" / "srcdir" / "inner.txt").read_text(
                    encoding="utf-8"
                )
                == "inner\n"
            )
            assert (tmp_path / "srcdir" / "inner.txt").exists()

    asyncio.run(scenario())


def test_filemgr_cut_then_paste_moves_entry_and_consumes_buffer(
    tmp_path: Path,
) -> None:
    """``x`` + ``p`` moves the source; the second paste reports an empty buffer."""
    (tmp_path / "sub").mkdir()
    (tmp_path / "alpha.txt").write_text("alpha\n", encoding="utf-8")

    async def scenario() -> None:
        app = _Host(_screen(tmp_path, [], []))
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, FileManagerScreen)
            assert await wait_until(pilot, lambda: len(_entry_names(screen)) == 2)
            await pilot.press("j")  # cursor onto alpha.txt
            await pilot.press("x")  # cut
            await pilot.press("k")  # back onto sub
            await pilot.press("l")  # enter sub
            assert await wait_until(pilot, lambda: screen._cwd == tmp_path / "sub")
            await pilot.press("p")
            assert await wait_until(
                pilot,
                lambda: (tmp_path / "sub" / "alpha.txt").exists()
                and not (tmp_path / "alpha.txt").exists(),
            )
            # the cut buffer was consumed by the move
            assert screen._clipboard is None
            await pilot.press("p")
            assert await wait_until(pilot, lambda: _input_visible(screen))
            input_widget = screen.query_one("#filemgr-input", Input)
            assert "clipboard is empty" in input_widget.placeholder
            await pilot.press("escape")
            assert not _input_visible(screen)

    asyncio.run(scenario())


def test_filemgr_paste_conflict_reports_and_keeps_both_files(tmp_path: Path) -> None:
    """A name conflict surfaces ``paste failed:`` and changes neither file."""
    (tmp_path / "sub").mkdir()
    (tmp_path / "alpha.txt").write_text("from\n", encoding="utf-8")
    (tmp_path / "sub" / "alpha.txt").write_text("existing\n", encoding="utf-8")

    async def scenario() -> None:
        app = _Host(_screen(tmp_path, [], []))
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, FileManagerScreen)
            assert await wait_until(pilot, lambda: len(_entry_names(screen)) == 2)
            await pilot.press("j")  # cursor onto alpha.txt
            await pilot.press("y")  # yank
            await pilot.press("k")  # back onto sub
            await pilot.press("l")  # enter sub
            assert await wait_until(pilot, lambda: screen._cwd == tmp_path / "sub")
            await pilot.press("p")
            assert await wait_until(pilot, lambda: _input_visible(screen))
            input_widget = screen.query_one("#filemgr-input", Input)
            assert "paste failed:" in input_widget.placeholder
            assert "already exists" in input_widget.placeholder
            # neither side was touched by the failed paste
            assert (tmp_path / "alpha.txt").read_text(encoding="utf-8") == "from\n"
            assert (
                (tmp_path / "sub" / "alpha.txt").read_text(encoding="utf-8")
                == "existing\n"
            )

    asyncio.run(scenario())


def test_filemgr_rename_conflict_keeps_input_and_retries(tmp_path: Path) -> None:
    """A rename error keeps the typed value and the pending op (m2)."""
    (tmp_path / "alpha.txt").write_text("a\n", encoding="utf-8")
    (tmp_path / "beta.txt").write_text("b\n", encoding="utf-8")
    renamed_calls: list[tuple[Path, Path]] = []

    async def scenario() -> None:
        app = _Host(_screen(tmp_path, [], [], renamed_calls=renamed_calls))
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, FileManagerScreen)
            assert await wait_until(pilot, lambda: len(_entry_names(screen)) == 2)
            input_widget = screen.query_one("#filemgr-input", Input)
            await pilot.press("R")  # rename alpha.txt (cursor starts there)
            assert input_widget.value == "alpha.txt"
            await pilot.press("ctrl+u")  # clear the prefilled name
            for ch in "beta.txt":
                await pilot.press(ch)
            await pilot.press("enter")
            # the error keeps the input open, value and kind intact
            assert await wait_until(
                pilot, lambda: "already exists" in input_widget.placeholder
            )
            assert _input_visible(screen)
            assert input_widget.value == "beta.txt"
            assert screen._prompt_kind == "rename"
            # retrying with a free name goes through and reports the rename
            await pilot.press("ctrl+u")
            for ch in "gamma.txt":
                await pilot.press(ch)
            await pilot.press("enter")
            assert await wait_until(pilot, lambda: (tmp_path / "gamma.txt").exists())
            assert not (tmp_path / "alpha.txt").exists()
            assert renamed_calls == [(tmp_path / "alpha.txt", tmp_path / "gamma.txt")]

    asyncio.run(scenario())


def test_filemgr_delete_cancel_then_confirm_reports_deleted(tmp_path: Path) -> None:
    """Non-``y`` input cancels; ``y`` deletes and reports to the hook (M2)."""
    (tmp_path / "alpha.txt").write_text("a\n", encoding="utf-8")
    deleted_calls: list[Path] = []

    async def scenario() -> None:
        app = _Host(_screen(tmp_path, [], [], deleted_calls=deleted_calls))
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, FileManagerScreen)
            assert await wait_until(pilot, lambda: _entry_names(screen) == ["alpha.txt"])
            # cancel: anything but y keeps the file and closes the line
            await pilot.press("d")
            assert _input_visible(screen)
            await pilot.press("n")
            await pilot.press("enter")
            assert await wait_until(pilot, lambda: not _input_visible(screen))
            assert (tmp_path / "alpha.txt").exists()
            assert deleted_calls == []
            # confirm: y deletes the file and reports the deleted path
            await pilot.press("d")
            await pilot.press("y")
            await pilot.press("enter")
            assert await wait_until(
                pilot, lambda: not (tmp_path / "alpha.txt").exists()
            )
            assert deleted_calls == [tmp_path / "alpha.txt"]

    asyncio.run(scenario())


def test_filemgr_filter_keystrokes_reuse_cached_counts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Filter edits reuse cached stats and child counts; ``r`` resets (M3)."""
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "inner.txt").write_text("i\n", encoding="utf-8")
    (tmp_path / "alpha.txt").write_text("a\n", encoding="utf-8")
    calls = {"counts": 0, "stats": 0}
    real_counts = filemgr.count_children
    real_stats = Workspace.stat_entry

    def counting(path: Path) -> int:
        """Counting stand-in for the consumer-module binding."""
        calls["counts"] += 1
        return real_counts(path)

    def stat_counting(self: Workspace, path: Path) -> EntryStat:
        """Counting stand-in for the class-level ``stat_entry``."""
        calls["stats"] += 1
        return real_stats(self, path)

    monkeypatch.setattr(filemgr, "count_children", counting)
    monkeypatch.setattr(Workspace, "stat_entry", stat_counting)

    async def scenario() -> None:
        app = _Host(_screen(tmp_path, [], []))
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, FileManagerScreen)
            # initial listing: 1 dir counted, 2 entries stat'ed
            assert await wait_until(pilot, lambda: len(_entry_names(screen)) == 2)
            assert calls == {"counts": 1, "stats": 2}
            # filter keystrokes neither rescan children nor re-stat
            await pilot.press("slash")
            await pilot.press("u")  # matches "sub" only
            assert await wait_until(pilot, lambda: _entry_names(screen) == ["sub"])
            assert calls == {"counts": 1, "stats": 2}
            await pilot.press("escape")  # clear the filter: still cached
            assert await wait_until(pilot, lambda: len(_entry_names(screen)) == 2)
            assert calls == {"counts": 1, "stats": 2}
            # ``r`` drops the cache: one recount and a full re-stat
            await pilot.press("r")
            assert await wait_until(pilot, lambda: calls["counts"] == 2)
            assert calls["stats"] == 4

    asyncio.run(scenario())


@pytest.mark.skipif(sys.platform != "win32", reason="drive letters are Windows-only")
def test_filemgr_drive_level_lists_drives_and_enters(tmp_path: Path) -> None:
    """A root start lands on the drive level; ``l`` enters, ``h`` returns (Q4)."""
    (tmp_path / "marker.txt").write_text("m\n", encoding="utf-8")

    async def scenario() -> None:
        app = _Host(_screen(tmp_path, [], [], initial_dir=Path(tmp_path.anchor)))
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, FileManagerScreen)
            drive_names = [entry.name for entry in Workspace(tmp_path).list_drives()]
            assert drive_names
            # the drive level: drives in the middle pane, placeholder left
            assert screen._cwd is None
            assert await wait_until(pilot, lambda: _entry_names(screen) == drive_names)
            assert _parent_texts(screen) == ["(no parent directory)"]
            # ``l`` enters the first drive like a normal directory
            drive_root = Path(f"{drive_names[0]}\\")
            await pilot.press("l")
            assert await wait_until(pilot, lambda: screen._cwd == drive_root)
            assert await wait_until(
                pilot,
                lambda: _entry_names(screen)
                == [e.name for e in Workspace(tmp_path).list_dir(drive_root)],
            )
            # ``h`` from a file-system root returns to the drive level
            await pilot.press("h")
            assert await wait_until(pilot, lambda: screen._cwd is None)
            assert await wait_until(pilot, lambda: _entry_names(screen) == drive_names)

    asyncio.run(scenario())


def test_filemgr_root_without_drives_stays_at_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No drives (POSIX): the file-system root has no drive level (M1).

    ``list_drives`` is patched empty, so the drive-letter virtual level
    must not exist: a root start stays on the real root and ``h`` at the
    root is a no-op, keeping the original listing.  With drives present
    ``h`` at the root still enters the drive level (Q4, Windows).
    """
    (tmp_path / "marker.txt").write_text("m\n", encoding="utf-8")
    monkeypatch.setattr(Workspace, "list_drives", _no_drives)

    async def scenario() -> None:
        app = _Host(_screen(tmp_path, [], [], initial_dir=Path(tmp_path.anchor)))
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, FileManagerScreen)
            # an empty drive list must not park the start on ``None``
            assert screen._cwd == Path(tmp_path.anchor)
            assert await wait_until(pilot, lambda: len(_entry_names(screen)) > 0)
            before = _entry_names(screen)
            # ``h`` at the root without drives: stay and keep the listing
            await pilot.press("h")
            assert await wait_until(pilot, lambda: _entry_names(screen) == before)
            assert screen._cwd == Path(tmp_path.anchor)
            # drives exist: ``h`` at the root enters the drive level
            monkeypatch.setattr(Workspace, "list_drives", _one_q_drive)
            await pilot.press("h")
            assert await wait_until(pilot, lambda: screen._cwd is None)
            assert await wait_until(pilot, lambda: _entry_names(screen) == ["Q:"])

    asyncio.run(scenario())


def test_filemgr_cut_paste_directory_into_itself_reports_failure(
    tmp_path: Path,
) -> None:
    """Cut-pasting a directory into its own subtree fails (B1 companion).

    The move raises ``shutil.Error`` ("Cannot move a directory ... into
    itself"); the screen surfaces it as ``paste failed:`` on the input
    line and the source tree stays untouched.
    """
    (tmp_path / "srcdir").mkdir()
    (tmp_path / "srcdir" / "inner.txt").write_text("inner\n", encoding="utf-8")
    (tmp_path / "srcdir" / "sub").mkdir()

    async def scenario() -> None:
        app = _Host(_screen(tmp_path, [], []))
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, FileManagerScreen)
            assert await wait_until(pilot, lambda: _entry_names(screen) == ["srcdir"])
            await pilot.press("x")  # cut srcdir
            await pilot.press("l")  # enter srcdir
            assert await wait_until(pilot, lambda: screen._cwd == tmp_path / "srcdir")
            # the cursor rests on the top row: sub (dirs sort first)
            await pilot.press("l")  # enter sub
            assert await wait_until(
                pilot, lambda: screen._cwd == tmp_path / "srcdir" / "sub"
            )
            await pilot.press("p")
            assert await wait_until(pilot, lambda: _input_visible(screen))
            input_widget = screen.query_one("#filemgr-input", Input)
            assert "paste failed:" in input_widget.placeholder
            # the source tree was left untouched by the failed move
            assert (
                (tmp_path / "srcdir" / "inner.txt").read_text(encoding="utf-8")
                == "inner\n"
            )
            assert not (tmp_path / "srcdir" / "sub" / "srcdir").exists()

    asyncio.run(scenario())


def test_filemgr_nav_remapped_keys_drive_screen_actions(tmp_path: Path) -> None:
    """The six remapped keys reach the screen via nav() (m10).

    While the middle-pane list is focused, ``ScrollableContainer`` would
    swallow these keys; the remapped ``LIST_BINDINGS`` must forward each
    of them to the matching screen action: right enters the directory
    under the cursor, left returns to the parent with the cursor on the
    origin (lf), home/end jump to the first/last row and pageup/pagedown
    half-page (clamped to the list bounds here).
    """
    _make_tree(tmp_path)  # dirs other/sub, files alpha.txt/beta.txt
    (tmp_path / "sub" / "inner.txt").write_text("inner\n", encoding="utf-8")

    async def scenario() -> None:
        open_calls: list[list[Path]] = []
        app = _Host(_screen(tmp_path, open_calls, []))
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, FileManagerScreen)
            assert await wait_until(pilot, lambda: len(_entry_names(screen)) == 4)
            _list(screen).focus()
            await pilot.pause()
            # end / home: cursor to the last / first row
            await pilot.press("end")
            assert _list(screen).index == 3
            await pilot.press("home")
            assert _list(screen).index == 0
            # pagedown / pageup: half-page steps, clamped to the bounds
            await pilot.press("pagedown")
            assert _list(screen).index == 3
            await pilot.press("pageup")
            assert _list(screen).index == 0
            # right on the directory "sub" enters it (no open_selected)
            await pilot.press("j")  # cursor onto sub
            assert _list(screen).index == 1
            await pilot.press("right")
            assert await wait_until(pilot, lambda: screen._cwd == tmp_path / "sub")
            assert await wait_until(
                pilot, lambda: _entry_names(screen) == ["inner.txt"]
            )
            # left returns to the parent, cursor lands on the origin (lf)
            await pilot.press("left")
            assert await wait_until(
                pilot,
                lambda: _entry_names(screen)
                == ["other", "sub", "alpha.txt", "beta.txt"],
            )
            assert screen._cwd == tmp_path
            assert _list(screen).index == 1
            assert open_calls == []

    asyncio.run(scenario())
