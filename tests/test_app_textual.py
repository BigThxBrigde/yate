"""Headless smoke tests for the Textual UI (run via pilot, no real terminal)."""

# tests legitimately poke at internals:
# pyright: reportPrivateUsage=false

from __future__ import annotations

import asyncio
import contextlib
import os
import time
from pathlib import Path
from typing import Any, cast, override

from collections.abc import Awaitable, Callable

import pytest

from textual.strip import Strip
from textual.widget import Widget
from textual.widgets.tree import TreeNode

# The bundled yate/extensions/ directory is auto-loaded with every YateApp;
# make sure the Python LSP extension never probes PATH or spawns a real server
# while the UI test suite runs.
os.environ["YATE_PYTHON_LSP"] = "off"

from yate.app import YateApp, textual_key_to_raw
from yate.editor_view.editor import EditorView
from yate.editor_view.manual import MarkdownDocScreen
from yate.keymaps.base import ActionContext
from yate.keymaps.vim import VimKeymap
from yate.session import Split as PaneSplit
from yate.session import leaves as pane_leaves


async def wait_until(
    pilot: Any, predicate: Callable[[], bool],
    timeout: float = 5.0, step: float = 0.05,
) -> bool:
    """Pause until *predicate* holds; False on timeout (for worker tests)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        # pilot.pause lets background workers/to_thread callbacks progress
        result: Awaitable[None] = pilot.pause(step)
        await result
        if predicate():
            return True
    return predicate()


def plain_text(content: Any) -> str:
    """Plain text of a widget renderable (rich Text, str, or other)."""
    plain = getattr(content, "plain", None)
    return plain if isinstance(plain, str) else str(content)


# ------------------------------------------------------------------ key mapping


def test_named_keys() -> None:
    assert textual_key_to_raw("enter") == "\r"
    assert textual_key_to_raw("escape") == "\x1b"
    assert textual_key_to_raw("backspace") == "\x7f"
    assert textual_key_to_raw("up") == "\x1b[A"
    assert textual_key_to_raw("f1") == "\x1bOP"
    assert textual_key_to_raw("space") == " "


def test_ctrl_and_alt() -> None:
    assert textual_key_to_raw("ctrl+s") == "\x13"
    assert textual_key_to_raw("ctrl+c") == "\x03"
    assert textual_key_to_raw("ctrl+]") == "\x1d"
    assert textual_key_to_raw("ctrl+/") == "\x1f"
    assert textual_key_to_raw("alt+u") == "\x1bu"


def test_modified_arrows() -> None:
    assert textual_key_to_raw("ctrl+right") == "\x1b[1;5C"
    assert textual_key_to_raw("shift+left") == "\x1b[1;2D"
    assert textual_key_to_raw("ctrl+pageup") == "\x1b[5;5~"


def test_printable_passthrough() -> None:
    assert textual_key_to_raw("a") == "a"
    assert textual_key_to_raw(":") == ":"
    assert textual_key_to_raw("") is None


# ------------------------------------------------------------- headless app smoke


def test_type_save_find_help_keymap(tmp_path: Path) -> None:
    async def scenario() -> None:
        target = tmp_path / "notes.txt"
        app = YateApp(target=target)
        assert app.editor.keymaps.name == "vsc"
        async with app.run_test(size=(100, 30)) as pilot:
            # widgets exist once mounted; narrow the Optional widget attrs
            prompt_bar = app.editor.prompt_bar
            assert prompt_bar is not None

            # --- type text into the buffer
            await pilot.press("h", "e", "l", "l", "o")
            assert app.editor.session.buffer.lines[0] == "hello"
            assert app.editor.session.doc.modified

            # --- save with ctrl+s
            await pilot.press("ctrl+s")
            assert target.exists()
            assert not app.editor.session.doc.modified
            assert target.read_text(encoding="utf-8") == "hello"

            # --- find prompt + live search
            await pilot.press("ctrl+f")
            assert prompt_bar.active_mode == "find"
            await pilot.press("l", "l")
            await pilot.press("enter")
            assert app.editor.session.search.query == "ll"
            assert len(app.editor.session.search.matches) >= 1
            assert app.focused == app.editor.panes.active_view

            # --- switch keymap to vim via the vsc toggle (the ":" ex
            # command line is vim-only; vsc mode types ":" literally)
            await pilot.press("ctrl+/")
            assert app.editor.keymaps.name == "vim"

            # --- vim append-at-line-end then escape (clear the search
            # selection first, otherwise insert replaces it by design)
            app.editor.session.buffer.clear_selection()
            await pilot.press("A", "!", "escape")
            assert app.editor.session.buffer.lines[0] == "hello!"

            # --- help modal opens via :help and closes
            await pilot.press("colon")
            assert prompt_bar.active_mode == "command"
            for ch in "help":
                await pilot.press(ch)
            await pilot.press("enter")
            await pilot.pause()
            assert len(app.screen_stack) == 2
            await pilot.press("q")
            await pilot.pause()
            assert len(app.screen_stack) == 1

            # --- tab bar shows the file name
            assert "notes.txt" in app.editor.tabbar.build(100)[0].plain

            # --- breadcrumbs: folder chevron crumbs + file name; the
            # file name stays visible even on a very narrow bar
            crumbs = app.editor.breadcrumbs.build(100).plain
            assert "notes.txt" in crumbs
            assert "\uf054" in crumbs  # chevron separator
            assert "notes.txt" in app.editor.breadcrumbs.build(12).plain

    asyncio.run(scenario())


def test_readonly_blocks_edits_saves_and_unlocks(tmp_path: Path) -> None:
    """--readonly starts locked; edits/saves are refused; :set unlocks."""

    async def scenario() -> None:
        target = tmp_path / "locked.txt"
        target.write_text("keep", encoding="utf-8")
        app = YateApp(target=target, readonly=True)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            assert app.editor.session.buffer.read_only
            # the status bar shows the lock glyph while read-only
            strip = "".join(
                seg.text for seg in app.editor.status_bar.render_line(0)
            )
            assert "\uf023" in strip
            # typing is refused (key consumed, buffer unchanged)
            await pilot.press("x")
            assert app.editor.session.buffer.get_text() == "keep"
            # ctrl+s refuses to write the file
            await pilot.press("ctrl+s")
            assert target.read_text(encoding="utf-8") == "keep"
            # :set readonly=false unlocks through the full command path
            await pilot.press("f5")
            await pilot.pause()
            await pilot.press(*"set")
            await pilot.press("space")
            await pilot.press(*"readonly=false")
            await pilot.press("enter")
            await pilot.pause()
            assert not app.editor.session.buffer.read_only
            # the lock glyph is gone once unlocked
            strip = "".join(
                seg.text for seg in app.editor.status_bar.render_line(0)
            )
            assert "\uf023" not in strip
            await pilot.press("x")
            # startup cursor sits at (0, 0), so the typing lands at the top
            assert app.editor.session.buffer.get_text() == "xkeep"

    asyncio.run(scenario())


def test_readonly_startup_flag_ignores_directory_target(tmp_path: Path) -> None:
    """``--readonly`` only applies to a file argument, never a directory."""

    async def scenario() -> None:
        app = YateApp(target=tmp_path, readonly=True)
        assert app.editor.startup_readonly
        # a directory target seeds a normal (writable) buffer
        assert not app.editor.session.buffer.read_only

    asyncio.run(scenario())


def test_syntax_highlight_and_theme_switch(tmp_path: Path) -> None:
    from yate.editor_view import theme

    async def scenario() -> None:
        target = tmp_path / "script.py"
        target.write_text("def foo():\n    return 42\n", encoding="utf-8")
        app = YateApp(target=target)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            editor = app.editor.panes.active_view
            assert editor is not None
            mocha = theme.active()

            # render the "def foo():" line and collect segment colors
            def seg_colors(strip: Strip) -> set[str]:
                return {
                    seg.style.color.name.lower()
                    for seg in strip
                    if seg.style is not None and seg.style.color is not None
                }

            colors = seg_colors(editor.render_line(0))
            # "def" -> keyword color, "foo" -> function color must appear
            assert mocha.syn_keyword.lower() in colors
            assert mocha.syn_function.lower() in colors
            # number 42 on line 2 -> number color
            assert mocha.syn_number.lower() in seg_colors(editor.render_line(1))

            # switch theme via the app action (the ":" ex line is
            # vim-only; the same command is reached via the vsc palette)
            app.editor.set_theme("latte")
            await pilot.pause()
            assert theme.active().name == "latte"
            theme.set_theme("mocha")  # restore default for other tests

    asyncio.run(scenario())


def test_highlight_cache_survives_cursor_movement(tmp_path: Path) -> None:
    async def scenario() -> None:
        target = tmp_path / "script.py"
        target.write_text("def foo():\n    return 42\n", encoding="utf-8")
        app = YateApp(target=target)
        async with app.run_test(size=(100, 30)) as pilot:
            editor = app.editor.panes.active_view
            assert editor is not None
            # wait for the background tokenizer to paint colors
            ready = await wait_until(
                pilot, lambda: editor.highlight_probe().tokens is not None,
                timeout=5.0,
            )
            assert ready
            tokens = editor.highlight_probe().tokens

            def colors_at(row: int) -> set[str]:
                return {
                    seg.style.color.name.lower()
                    for seg in editor.render_line(row)
                    if seg.style is not None and seg.style.color is not None
                }

            from yate.editor_view import theme
            mocha = theme.active()
            before = colors_at(0)
            assert mocha.syn_keyword.lower() in before

            # moving the cursor must not discard the token cache: the
            # keyword color stays without waiting for a new tokenizer
            await pilot.press("down")
            assert editor.highlight_probe().tokens is tokens
            assert mocha.syn_keyword.lower() in colors_at(0)

            # editing invalidates the cache; a fresh tokenizer pass runs
            await pilot.press("x")
            refreshed = await wait_until(
                pilot,
                lambda: editor.highlight_probe().tokens is not None
                and editor.highlight_probe().tokens is not tokens
                and editor.highlight_probe().version
                == app.editor.session.buffer.content_version,
                timeout=5.0,
            )
            assert refreshed

    asyncio.run(scenario())


def test_edit_keeps_colors_instead_of_flashing(tmp_path: Path) -> None:
    async def scenario() -> None:
        target = tmp_path / "script.py"
        target.write_text("def foo():\n    return 42\n", encoding="utf-8")
        app = YateApp(target=target)
        async with app.run_test(size=(100, 30)) as pilot:
            editor = app.editor.panes.active_view
            assert editor is not None
            assert await wait_until(
                pilot, lambda: editor.highlight_probe().tokens is not None,
                timeout=5.0,
            )
            assert editor.tokens_for(0)

            from yate.editor_view import theme
            mocha = theme.active()

            def colors_at(row: int) -> set[str]:
                return {
                    seg.style.color.name.lower()
                    for seg in editor.render_line(row)
                    if seg.style is not None and seg.style.color is not None
                }

            assert mocha.syn_keyword.lower() in colors_at(0)

            # An edit must NOT drop the colors while the debounced
            # tokenize pass is pending: the stale tokens keep coloring
            # the view right after the keypress (no uncolored frame).
            await pilot.press("x")
            assert editor.tokens_for(0)
            assert mocha.syn_keyword.lower() in colors_at(0)

            # Exactly one debounced pass is pending for the latest
            # version, and repeated renders for the same version reuse
            # the same timer. Checked synchronously after a direct
            # buffer edit: race-free even on a loaded machine.
            app.editor.session.buffer.insert_text("y")
            assert editor.tokens_for(0)
            probe = editor.highlight_probe()
            timer = probe.timer
            key = probe.scheduled_key
            assert timer is not None
            assert key is not None
            assert key[2] == app.editor.session.buffer.content_version
            editor.tokens_for(0)
            editor.tokens_for(1)
            probe = editor.highlight_probe()
            assert probe.timer is timer
            assert probe.scheduled_key == key

            # ...and the pending pass converges to the latest version
            assert await wait_until(
                pilot,
                lambda: editor.highlight_probe().tokens is not None
                and editor.highlight_probe().version
                == app.editor.session.buffer.content_version
                and editor.highlight_probe().scheduled_key is None,
                timeout=5.0,
            )

    asyncio.run(scenario())


def test_stale_highlight_not_reused_on_filetype_or_document_switch(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        target = tmp_path / "script.py"
        target.write_text("def foo():\n    return 42\n", encoding="utf-8")
        app = YateApp(target=target)
        async with app.run_test(size=(100, 30)) as pilot:
            editor = app.editor.panes.active_view
            assert editor is not None
            assert await wait_until(
                pilot, lambda: editor.highlight_probe().tokens is not None,
                timeout=5.0,
            )
            assert editor.tokens_for(0)

            # filetype switch: python tokens must not color the file
            app.editor.run_command("set filetype=plaintext")
            assert editor.tokens_for(0) == []
            assert await wait_until(
                pilot,
                lambda: editor.highlight_probe().filetype == "plaintext"
                and editor.highlight_probe().version
                == app.editor.session.buffer.content_version,
                timeout=5.0,
            )

            # document switch: the old document's tokens must not leak
            old_doc = editor.doc
            app.editor.run_command("enew")
            assert editor.doc is not old_doc
            assert editor.tokens_for(0) == []
            assert await wait_until(
                pilot,
                lambda: editor.highlight_probe().doc is editor.doc
                and editor.highlight_probe().version
                == app.editor.session.buffer.content_version,
                timeout=5.0,
            )

    asyncio.run(scenario())


def test_explorer_open_file(tmp_path: Path) -> None:
    async def scenario() -> None:
        root = tmp_path
        (root / "a.txt").write_text("alpha\n", encoding="utf-8")
        (root / "b.py").write_text("print('beta')\n", encoding="utf-8")
        app = YateApp(target=root)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            explorer = app.editor.explorer_tree
            assert explorer is not None
            assert explorer.display
            # ctrl+e focuses the explorer; j moves down; l opens
            await pilot.press("ctrl+e")
            assert app.focused is app.editor.explorer_tree
            await pilot.press("j", "l")
            await pilot.pause()
            opened = {d.name for d in app.editor.session.docs if d.path is not None}
            assert opened & {"a.txt", "b.py"}
            # esc returns focus to the editor
            await pilot.press("escape")
            assert app.focused is app.editor.panes.active_view

    asyncio.run(scenario())


# -------------------------------------------------------- workspace file walking


def test_collects_nested_files_and_prunes_noise(tmp_path: Path) -> None:
    from yate.services.workspace import Workspace

    root = tmp_path
    (root / "src").mkdir()
    (root / "src" / "main.py").write_text("x = 1\n", encoding="utf-8")
    (root / "src" / "util.py").write_text("y = 2\n", encoding="utf-8")
    (root / "readme.md").write_text("# hi\n", encoding="utf-8")
    (root / "__pycache__").mkdir()
    (root / "__pycache__" / "junk.pyc").write_text("x", encoding="utf-8")

    ws = Workspace(root)
    names = {p.name for p in ws.walk_files()}
    assert names == {"main.py", "util.py", "readme.md"}


def test_no_root_returns_empty() -> None:
    from yate.services.workspace import Workspace

    assert Workspace(None).walk_files() == []


def test_limit(tmp_path: Path) -> None:
    from yate.services.workspace import Workspace

    root = tmp_path
    for i in range(10):
        (root / f"f{i}.txt").write_text("x\n", encoding="utf-8")
    assert len(Workspace(root).walk_files(limit=3)) == 3


# ----------------------------------------------------------------- fuzzy match


def test_empty_query_matches() -> None:
    from yate.editor_view.palette import fuzzy_match

    assert fuzzy_match("", "anything") is not None


def test_subsequence_order() -> None:
    from yate.editor_view.palette import fuzzy_match

    assert fuzzy_match("wt", "write") is not None
    assert fuzzy_match("tw", "write") is None
    assert fuzzy_match("bp", "bprev") is not None
    assert fuzzy_match("xyz", "bprev") is None


def test_consecutive_ranks_better_than_gap() -> None:
    from yate.editor_view.palette import fuzzy_match

    tight = fuzzy_match("set", "set")
    gappy = fuzzy_match("set", "reset")  # r-e-**s**-**e**-**t**: gap match
    assert tight is not None and gappy is not None
    assert tight[0] < gappy[0]


def test_returns_matched_indices() -> None:
    from yate.editor_view.palette import fuzzy_match

    match = fuzzy_match("bprev", "bprev")
    assert match is not None
    assert match[1] == [0, 1, 2, 3, 4]


# --------------------------------------------------------------------- palette


def test_ctrl_p_chord_opens_file_palette(tmp_path: Path) -> None:
    from yate.editor_view.palette import PaletteScreen

    async def scenario() -> None:
        (tmp_path / "notes.txt").write_text("hi\n", encoding="utf-8")
        app = YateApp(target=tmp_path)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.press("ctrl+p")
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, PaletteScreen)
            assert screen.mode == "files"
            # escape dismisses
            await pilot.press("escape")
            await pilot.pause()
            assert len(app.screen_stack) == 1

    asyncio.run(scenario())


def test_file_palette_filters_and_opens(tmp_path: Path) -> None:
    from yate.editor_view.palette import PaletteScreen

    async def scenario() -> None:
        (tmp_path / "notes.txt").write_text("hi\n", encoding="utf-8")
        (tmp_path / "data.txt").write_text("data\n", encoding="utf-8")
        app = YateApp(target=tmp_path)
        async with app.run_test(size=(100, 30)) as pilot:
            app.editor.open_file_palette()
            await pilot.pause()
            assert isinstance(app.screen, PaletteScreen)
            for ch in "note":
                await pilot.press(ch)
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, PaletteScreen)
            # only notes.txt matches "note"
            assert screen.filtered_count == 1
            await pilot.press("enter")
            await pilot.pause()
            assert len(app.screen_stack) == 1
            assert app.editor.session.doc.name == "notes.txt"

    asyncio.run(scenario())


def test_command_palette_runs_command() -> None:
    from yate.editor_view.palette import PaletteScreen

    async def scenario() -> None:
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            # alt+shift+p is the default: ctrl+shift+p clashes with Windows
            # Terminal's own command palette, ctrl+shift+a with other
            # terminal emulators.
            await pilot.press("alt+shift+p")
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, PaletteScreen)
            assert screen.mode == "commands"
            for ch in "vim":
                await pilot.press(ch)
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            assert app.editor.keymaps.name == "vim"

    asyncio.run(scenario())


def test_command_palette_alt_shift_p_binding() -> None:
    from yate.editor_view.palette import PaletteScreen

    async def scenario() -> None:
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            # the vsc keymap advertises the binding and the chord opens the
            # palette even while the editor widget has focus
            binding = app.editor.keymaps.active.lookup("\x1bP")
            assert binding is not None
            assert binding.action == "command_palette"
            await pilot.press("alt+shift+p")
            await pilot.pause()
            assert isinstance(app.screen, PaletteScreen)

    asyncio.run(scenario())


def test_command_palette_lists_all_commands_and_actions() -> None:
    from yate.editor_view.palette import PaletteScreen

    async def scenario() -> None:
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            # as an extension would: one new command and one new action
            def _cmd(args: str) -> None:
                pass

            def _act(ctx: object) -> None:
                pass

            app.editor.commands.register("zzz_palette_cmd", _cmd,
                                  "zz palette command")
            app.editor.actions.register(
                "zzz_palette_action", _act, "zz palette action")
            app.editor.open_command_palette()
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, PaletteScreen)
            entries = cast(Any, screen)._entries
            by_name = {name: payload for name, _hint, payload in entries}

            # built-in : commands and raw keymap actions are both present,
            # each with its full name
            assert by_name["write"] == ("command", "write")
            assert by_name["move_left"] == ("action", "move_left")
            assert by_name["command_palette"] == ("action", "command_palette")
            # extension-registered items show up too
            assert by_name["zzz_palette_cmd"] == ("command", "zzz_palette_cmd")
            assert by_name["zzz_palette_action"] == (
                "action", "zzz_palette_action")
            # a name registered in both tables appears once and resolves
            # to the : command spelling
            assert by_name["quit"] == ("command", "quit")
            # every row has a non-empty name and (for built-ins) a hint
            assert all(name for name, _h, _p in entries)
            hinted = {name: hint for name, hint, _p in entries}
            assert hinted["write"] == "save the current file"
            assert hinted["move_left"] == "Move left"

    asyncio.run(scenario())


def test_command_palette_runs_action_by_full_name() -> None:
    from yate.editor_view.palette import PaletteScreen

    async def scenario() -> None:
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            assert app.editor.keymaps.name == "vsc"
            app.editor.open_command_palette()
            await pilot.pause()
            assert isinstance(app.screen, PaletteScreen)
            for ch in "toggle_keymap":
                await pilot.press(ch)
            await pilot.pause()
            screen = cast(Any, app.screen)
            # the action is found by its full name and is the top hit
            assert screen._entries[screen._filtered[0][2]][2] == (
                "action", "toggle_keymap",
            )
            await pilot.press("enter")
            await pilot.pause()
            assert len(app.screen_stack) == 1
            assert app.editor.keymaps.name == "vim"

    asyncio.run(scenario())


def test_command_palette_searches_descriptions() -> None:
    from yate.editor_view.palette import PaletteScreen

    async def scenario() -> None:
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            app.editor.open_command_palette()
            await pilot.pause()
            for ch in "switch color theme":
                await pilot.press(ch)
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, PaletteScreen)
            # no command is *named* "switch color theme"; it matches the
            # description of :theme, and the row is selectable
            assert screen.filtered_count > 0
            top = cast(Any, screen)._entries[cast(Any, screen)._filtered[0][2]]
            assert top[2] == ("command", "theme")
            await pilot.press("enter")
            await pilot.pause()
            assert len(app.screen_stack) == 1

    asyncio.run(scenario())


def test_palette_down_cursor_moves(tmp_path: Path) -> None:
    from yate.editor_view.palette import PaletteScreen

    async def scenario() -> None:
        for name in ("a.txt", "b.txt", "c.txt"):
            (tmp_path / name).write_text("x\n", encoding="utf-8")
        app = YateApp(target=tmp_path)
        async with app.run_test(size=(100, 30)) as pilot:
            app.editor.open_file_palette()
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, PaletteScreen)
            # the input grabs focus in on_mount; under full-suite load that
            # can land after the press, which then sinks into the editor
            # beneath the modal instead of bubbling to the screen
            assert await wait_until(
                pilot,
                lambda: app.focused is not None
                and app.focused.id == "palette-input",
                timeout=5.0,
            )
            await pilot.press("down")
            # poll instead of asserting after one pause: under full-suite
            # load the key event can land one pump cycle late
            assert await wait_until(
                pilot, lambda: screen.cursor_index == 1, timeout=5.0
            )

    asyncio.run(scenario())


# ------------------------------------------------------------- editor scrolling


def test_viewport_follows_cursor_and_scrolls_back(tmp_path: Path) -> None:
    """Regression: moving past the visible area must scroll the view."""

    async def scenario() -> None:
        p = tmp_path / "big.txt"
        p.write_text(
            "\n".join(f"line {i}" for i in range(1, 61)) + "\n",
            encoding="utf-8",
        )
        app = YateApp(target=p)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            editor = app.editor.panes.active_view
            assert editor is not None
            assert editor.scroll_offset.y == 0

            for _ in range(45):
                await pilot.press("down")
            await pilot.pause()
            top = editor.scroll_offset.y
            assert top > 0
            # first visible row shows buffer line top+1
            first = "".join(seg.text for seg in editor.render_line(0))
            assert first.split()[0] == str(top + 1)
            # cursor row stays inside the visible window
            buf_row = app.editor.session.buffer.row
            assert buf_row - top >= 0
            assert buf_row - top < editor.size.height

            for _ in range(45):
                await pilot.press("up")
            await pilot.pause()
            assert editor.scroll_offset.y == 0

    asyncio.run(scenario())


def test_scrolled_view_renders_buffer_rows(tmp_path: Path) -> None:
    """Regression: render_line must honour the scroll offset (wheel path)."""

    async def scenario() -> None:
        p = tmp_path / "big.txt"
        p.write_text(
            "\n".join(f"line {i}" for i in range(1, 61)) + "\n",
            encoding="utf-8",
        )
        app = YateApp(target=p)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            editor = app.editor.panes.active_view
            assert editor is not None
            # this is where Textual's mouse-wheel handling lands
            editor.scroll_down(animate=False)
            await pilot.pause()
            assert editor.scroll_offset.y == 1
            first = "".join(seg.text for seg in editor.render_line(0))
            assert first.split()[0] == "2"
            assert "line 2" in first

    asyncio.run(scenario())


# ---------------------------------------------------------------- welcome page


def test_welcome_shown_then_hidden_on_type() -> None:
    async def scenario() -> None:
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            editor = app.editor.panes.active_view
            assert editor is not None

            def screen_text() -> str:
                parts: list[str] = []
                for row in range(26):
                    parts.extend(seg.text for seg in editor.render_line(row))
                return "".join(parts)

            welcome = screen_text()
            assert "\u2588\u2588\u2557   \u2588\u2588\u2557" in welcome  # "Y" head
            assert "\u255a\u2550\u2550\u2550\u2550\u2550\u2550\u255d" in welcome  # "E" foot
            assert "yate" in welcome
            assert "quick open" in welcome
            # default (vsc) welcome must not advertise the vim-only ":" prompt
            assert "ex command prompt" not in welcome
            # typing dismisses the welcome page
            await pilot.press("h", "i")
            await pilot.pause()
            assert "\u2588" not in screen_text()

    asyncio.run(scenario())


def test_welcome_advertises_colon_only_in_vim_keymap() -> None:
    async def scenario() -> None:
        app = YateApp(keymap="vim")
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            editor = app.editor.panes.active_view
            assert editor is not None
            parts: list[str] = []
            for row in range(26):
                parts.extend(seg.text for seg in editor.render_line(row))
            assert "ex command prompt" in "".join(parts)

    asyncio.run(scenario())


def test_enew_dismisses_welcome_and_it_does_not_return() -> None:
    async def scenario() -> None:
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            editor = app.editor.panes.active_view
            assert editor is not None

            def screen_text() -> str:
                parts: list[str] = []
                for row in range(26):
                    parts.extend(seg.text for seg in editor.render_line(row))
                return "".join(parts)

            assert "\u2588" in screen_text()  # welcome banner at startup
            initial_index = app.editor.session.index

            # :enew creates another empty scratch buffer -- the welcome page
            # must be cleared immediately, never to return on its own.
            app.editor.run_command("enew")
            await pilot.pause()
            assert not app.editor.session.welcome_visible
            assert "\u2588" not in screen_text()

            # switching back to the still-pristine startup buffer must not
            # bring the welcome page back
            app.editor.run_command("bp")
            await pilot.pause()
            assert app.editor.session.index == initial_index
            assert "\u2588" not in screen_text()

            # ...until the user explicitly asks for it with :welcome
            app.editor.run_command("welcome")
            await pilot.pause()
            assert app.editor.session.welcome_visible
            assert "\u2588" in screen_text()

    asyncio.run(scenario())


def test_internal_seed_buffer_keeps_welcome_enabled() -> None:
    # Startup seeds the initial buffer via new_buffer(show=False); that
    # internal path must not dismiss the welcome page.
    async def scenario() -> None:
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            assert app.editor.session.welcome_visible
            editor = app.editor.panes.active_view
            assert editor is not None
            parts: list[str] = []
            for row in range(26):
                parts.extend(seg.text for seg in editor.render_line(row))
            assert "yate" in "".join(parts)

    asyncio.run(scenario())


# ------------------------------------------------------------------ prompt bar


def test_command_input_shows_typed_text() -> None:
    """Regression: focused height-1 Input must not gain a tall border
    that collapses its content region and hides typed characters."""

    async def scenario() -> None:
        app = YateApp(keymap="vim")
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.press(":")
            await pilot.pause()
            await pilot.press(*"wp")
            await pilot.pause()
            prompt_bar = app.editor.prompt_bar
            assert prompt_bar is not None
            inp = prompt_bar.input
            assert inp.value == "wp"
            assert inp.scrollable_content_region.height == 1
            strip_text = "".join(seg.text for seg in inp.render_line(0))
            assert "wp" in strip_text

    asyncio.run(scenario())


def test_colon_types_literally_in_vsc_keymap() -> None:
    """The ex command prompt is vim-only; vsc mode inserts ':' as text."""

    async def scenario() -> None:
        app = YateApp()  # default keymap is vsc
        async with app.run_test(size=(100, 30)) as pilot:
            prompt_bar = app.editor.prompt_bar
            assert prompt_bar is not None
            await pilot.press(":", "w", "q")
            await pilot.pause()
            assert prompt_bar.active_mode is None
            assert app.editor.session.doc.buffer.get_text() == ":wq"

    asyncio.run(scenario())


def test_f5_opens_command_prompt_in_vsc_keymap() -> None:
    """F5 activates the ex command line; Esc dismisses it."""

    async def scenario() -> None:
        app = YateApp()  # default keymap is vsc
        async with app.run_test(size=(100, 30)) as pilot:
            prompt_bar = app.editor.prompt_bar
            assert prompt_bar is not None
            await pilot.press("f5")
            await pilot.pause()
            assert prompt_bar.active_mode == "command"
            # typing still lands in the prompt, not the buffer
            await pilot.press(*"w")
            await pilot.pause()
            assert prompt_bar.input.value == "w"
            assert app.editor.session.doc.buffer.get_text() == ""
            # Esc closes the prompt and returns focus to the editor
            await pilot.press("escape")
            await pilot.pause()
            assert prompt_bar.active_mode is None
            assert app.focused is app.editor.panes.active_view

    asyncio.run(scenario())


def test_command_line_closes_without_a_message() -> None:
    """A command that reports nothing must not leave the prompt open.

    ``:bn`` (and friends) produce no message; the prompt used to stay in
    command mode with the stale text, and because the Input keeps focus it
    swallowed the next F5 -- the command line became unusable.
    """

    async def scenario() -> None:
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            prompt_bar = app.editor.prompt_bar
            assert prompt_bar is not None
            await pilot.press("ctrl+n")  # a second tab, so :bn has a target
            await pilot.pause()
            await pilot.press("f5")
            await pilot.pause()
            await pilot.press(*"bn")
            await pilot.press("enter")
            await pilot.pause()
            assert prompt_bar.active_mode is None
            await pilot.press("f5")
            await pilot.pause()
            assert prompt_bar.active_mode == "command"

    asyncio.run(scenario())


def test_ctrl_slash_toggles_back_from_vim_keymap() -> None:
    """``ctrl+/`` is bidirectional: the vim keymap must return to vsc.

    The manual promises a two-way toggle, so the binding is not vsc-only.
    """

    async def scenario() -> None:
        app = YateApp(keymap="vim")
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            assert app.editor.keymaps.name == "vim"
            binding = app.editor.keymaps.active.lookup("\x1f")
            assert binding is not None
            assert binding.action == "toggle_keymap"
            await pilot.press("ctrl+/")
            await pilot.pause()
            assert app.editor.keymaps.name == "vsc"
            # and back the other way, now through the vsc keymap
            await pilot.press("ctrl+/")
            await pilot.pause()
            assert app.editor.keymaps.name == "vim"

    asyncio.run(scenario())


def test_ctrl_slash_drops_pending_vim_state() -> None:
    """Toggling from vim must not leave a half-finished operator behind."""

    async def scenario() -> None:
        app = YateApp(keymap="vim")
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            await pilot.press("d")  # pending delete operator
            await pilot.pause()
            vim = cast(VimKeymap, app.editor.keymaps.active)
            assert vim.pending == "d"
            await pilot.press("ctrl+/")
            await pilot.pause()
            assert app.editor.keymaps.name == "vsc"
            assert vim.pending == ""
            assert vim.count_str == ""

    asyncio.run(scenario())


def test_colon_opens_prompt_in_vim_keymap() -> None:
    async def scenario() -> None:
        app = YateApp(keymap="vim")
        async with app.run_test(size=(100, 30)) as pilot:
            prompt_bar = app.editor.prompt_bar
            assert prompt_bar is not None
            await pilot.press(":")
            await pilot.pause()
            assert prompt_bar.active_mode == "command"

    asyncio.run(scenario())


def test_breadcrumb_blank_for_untitled_doc() -> None:
    """Untitled buffers must not repeat the tab label in breadcrumbs."""

    async def scenario() -> None:
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            assert app.editor.breadcrumbs.build(80).plain.strip() == ""

    asyncio.run(scenario())


# ----------------------------------------------------- rc-declared extensions


def test_rc_declared_file_and_directory_extensions_load(tmp_path: Path) -> None:
    from yate.config import load_config

    async def scenario() -> None:
        root = tmp_path
        # a single-file extension registering a :command
        (root / "myext.py").write_text(
            "def setup(api):\n"
            '    @api.command("rcping", "rc test command")\n'
            "    def rcping(args):\n"
            '        api.message("pong")\n',
            encoding="utf-8",
        )
        # a directory extension
        bundle = root / "bundle"
        bundle.mkdir()
        (bundle / "dir_ext.py").write_text(
            "def setup(api):\n"
            '    api.register_action("rc-action", lambda: None)\n',
            encoding="utf-8",
        )
        rc = root / "yaterc"
        rc.write_text('extensions = ["myext.py", "bundle"]\n', encoding="utf-8")

        config = load_config([rc])
        assert config.errors == []
        app = YateApp(config=config)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            assert "rcping" in app.editor.commands.names()
            loaded = {rec.name for rec in app.editor.extension_loader.loaded}
            assert "myext" in loaded
            assert "dir_ext" in loaded
            assert all(rec.error is None for rec in app.editor.extension_loader.loaded)

    asyncio.run(scenario())


# ----------------------------------------------------------- explorer operations


def test_file_target_starts_with_explorer_hidden(tmp_path: Path) -> None:
    """A file argument focuses on editing: the explorer starts hidden
    (Ctrl+B / :explorer reveals it); a directory starts with it shown,
    and a not-yet-created file path behaves like a file argument."""

    async def scenario() -> None:
        root = tmp_path
        alpha = root / "alpha.txt"
        alpha.write_text("alpha\n", encoding="utf-8")

        app = YateApp(target=alpha)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            explorer = app.editor.explorer_tree
            assert explorer is not None
            assert not explorer.display
            # the workspace root is still the file's parent, so showing
            # the explorer later works without reopening anything
            await pilot.press("ctrl+b")
            await pilot.pause()
            assert explorer.display

        app_dir = YateApp(target=root)
        async with app_dir.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            explorer_dir = app_dir.editor.explorer_tree
            assert explorer_dir is not None
            assert explorer_dir.display

        app_new = YateApp(target=root / "brand_new.txt")
        async with app_new.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            explorer_new = app_new.editor.explorer_tree
            assert explorer_new is not None
            assert not explorer_new.display

    asyncio.run(scenario())


def test_ctrl_b_toggles_explorer(tmp_path: Path) -> None:
    async def scenario() -> None:
        app = YateApp(target=tmp_path)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            explorer = app.editor.explorer_tree
            assert explorer is not None
            assert explorer.display
            await pilot.press("ctrl+b")
            await pilot.pause()
            assert not explorer.display
            await pilot.press("ctrl+b")
            await pilot.pause()
            assert explorer.display

    asyncio.run(scenario())


def test_new_file_and_folder_from_explorer(tmp_path: Path) -> None:
    async def scenario() -> None:
        root = tmp_path
        (root / "seed.txt").write_text("seed\n", encoding="utf-8")
        app = YateApp(target=root)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            # cursor sits on the root: "a" creates a file at the top level
            await pilot.press("ctrl+e")
            await pilot.press("a")
            await pilot.pause()
            prompt_bar = app.editor.prompt_bar
            assert prompt_bar is not None
            assert prompt_bar.active_mode == "new_file"
            await pilot.press(*"made.txt")
            await pilot.press("enter")
            await pilot.pause()
            assert (root / "made.txt").exists()
            # new files open right away (VS Code behavior)
            opened = {d.name for d in app.editor.session.docs if d.path is not None}
            assert "made.txt" in opened
            # "A" creates a folder; creation target is the selected dir
            await pilot.press("ctrl+e")
            await pilot.press("A")
            await pilot.pause()
            assert prompt_bar.active_mode == "new_dir"
            await pilot.press(*"subdir")
            await pilot.press("enter")
            await pilot.pause()
            assert (root / "subdir").is_dir()

    asyncio.run(scenario())


def test_open_nested_file_keeps_expansion_and_cursor(tmp_path: Path) -> None:
    """Regression: refresh_tree collapsed second-level directories and
    the cursor jumped to the last row after opening a nested file."""

    async def scenario() -> None:
        root = tmp_path
        sub = root / "sub"
        deep = sub / "deep"
        deep.mkdir(parents=True)
        (root / "top.txt").write_text("t\n", encoding="utf-8")
        (sub / "inner.txt").write_text("i\n", encoding="utf-8")
        (deep / "leaf.txt").write_text("l\n", encoding="utf-8")
        app = YateApp(target=root)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            tree = app.editor.explorer_tree
            assert tree is not None

            def find(
                node: TreeNode[Path | None], name: str
            ) -> TreeNode[Path | None] | None:
                for c in node.children:
                    if c.data is not None and Path(c.data).name == name:
                        return c
                    if c.is_expanded:
                        r = find(c, name)
                        if r is not None:
                            return r
                return None

            # expand sub, then deep (two levels), then open leaf.txt
            sub_node = find(tree.root, "sub")
            assert sub_node is not None
            tree.select_node(sub_node)
            await pilot.pause()
            await pilot.pause()
            deep_node = find(tree.root, "deep")
            assert deep_node is not None
            tree.select_node(deep_node)
            await pilot.pause()
            await pilot.pause()
            leaf = find(tree.root, "leaf.txt")
            assert leaf is not None
            tree.select_node(leaf)
            for _ in range(12):
                await pilot.pause()

            # sub AND deep must still be expanded after the refresh
            # triggered by opening the file
            assert sub_node.is_expanded, "first-level dir collapsed"
            assert deep_node.is_expanded, "nested dir collapsed"
            # cursor/highlight must sit on the opened file, not the
            # last row of the tree
            await pilot.press("ctrl+e")
            await pilot.pause()
            cur = tree.cursor_node
            assert cur is not None and cur.data is not None
            assert Path(cur.data).name == "leaf.txt"
            assert app.editor.session.doc.path is not None
            assert app.editor.session.doc.path.name == "leaf.txt"

    asyncio.run(scenario())


def test_rename_updates_open_document_path(tmp_path: Path) -> None:
    async def scenario() -> None:
        root = tmp_path
        (root / "old.txt").write_text("data\n", encoding="utf-8")
        app = YateApp(target=root)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            await pilot.press("ctrl+e", "j", "l")  # focus, move, open old.txt
            await pilot.pause()
            doc = app.editor.session.doc
            assert doc.path is not None
            await pilot.press("ctrl+e")
            await pilot.press("j")  # cursor onto old.txt
            await pilot.press("r")
            await pilot.pause()
            prompt_bar = app.editor.prompt_bar
            assert prompt_bar is not None
            assert prompt_bar.active_mode == "rename"
            assert prompt_bar.input.value == "old.txt"
            await pilot.press(*"new.txt")
            await pilot.press("enter")
            await pilot.pause()
            assert not (root / "old.txt").exists()
            assert (root / "new.txt").exists()
            assert app.editor.session.doc.path == (root / "new.txt").resolve()

    asyncio.run(scenario())


def test_delete_requires_confirmation(tmp_path: Path) -> None:
    async def scenario() -> None:
        root = tmp_path
        victim = root / "gone.txt"
        victim.write_text("bye\n", encoding="utf-8")
        app = YateApp(target=root)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            await pilot.press("ctrl+e", "j")
            await pilot.press("d")
            await pilot.pause()
            prompt_bar = app.editor.prompt_bar
            assert prompt_bar is not None
            assert prompt_bar.active_mode == "delete"
            assert victim.exists()
            # anything but y cancels
            await pilot.press("n")
            await pilot.press("enter")
            await pilot.pause()
            assert victim.exists()
            # d again, confirm with y
            await pilot.press("ctrl+e", "j", "d")
            await pilot.press(*"y")
            await pilot.press("enter")
            await pilot.pause()
            assert not victim.exists()

    asyncio.run(scenario())


def test_refresh_tree_keeps_expanded_dirs(tmp_path: Path) -> None:
    from yate.editor_view.explorer import ExplorerTree

    async def scenario() -> None:
        # workspace stores the resolved root; on Windows TEMP may be an
        # 8.3 short name (e.g. RUNNER~1), so canonicalize before comparing
        root = tmp_path.resolve()
        sub = root / "sub"
        sub.mkdir()
        (sub / "inner.txt").write_text("i\n", encoding="utf-8")
        app = YateApp(target=root)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            explorer = app.editor.explorer_tree
            assert explorer is not None
            # expand "sub" via the tree: focus root, j to sub, l to expand
            await pilot.press("ctrl+e", "j", "l")
            await pilot.pause()
            sub_node = next(n for n in explorer.root.children
                            if isinstance(n.data, Path) and n.data == sub)
            assert sub_node.is_expanded
            # any refresh (e.g. opening a file elsewhere) must not collapse
            explorer.refresh_tree()
            sub_node2 = next(n for n in explorer.root.children
                             if isinstance(n.data, Path) and n.data == sub)
            assert sub_node2.is_expanded
            assert ExplorerTree in type(explorer).__mro__

    asyncio.run(scenario())


# ------------------------------------------------------ editor background color


def test_every_editor_cell_has_explicit_bg(tmp_path: Path) -> None:
    """Regression: None bgcolor would let the terminal's own background
    bleed through next to cells painted with theme.bg."""
    from rich.color import Color

    from yate.editor_view import theme as theme_mod

    async def scenario() -> None:
        p = tmp_path / "doc.py"
        p.write_text('"""doc"""\n\nx = 1\n', encoding="utf-8")
        app = YateApp(target=p)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            editor = app.editor.panes.active_view
            assert editor is not None
            t = theme_mod.active()
            allowed = {repr(Color.parse(t.bg)), repr(Color.parse(t.surface))}
            checked = 0
            for row in range(min(4, app.editor.session.buffer.line_count)):
                for seg in editor.render_line(row):
                    bg = getattr(seg.style, "bgcolor", None)
                    assert bg is not None, \
                        f"bg=None cell at row {row}: {seg.text!r}"
                    assert repr(bg) in allowed
                    checked += 1
            assert checked > 12

    asyncio.run(scenario())


# ------------------------------------------------------ manual / markdown doc


def test_f8_opens_manual_and_esc_closes() -> None:
    from textual.widgets import Markdown, Static

    from yate.editor_view.manual import load_manual_markdown

    async def scenario() -> None:
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            await pilot.press("f8")
            await pilot.pause()
            assert isinstance(app.screen, MarkdownDocScreen)
            md = app.screen.query_one("#doc-md", Markdown)
            loading = app.screen.query_one("#doc-loading", Static)
            # the markdown worker reads/parses off the loop; poll until the
            # load completes before asserting content -- a loaded CI box can
            # still be mid-read after the first pause (asserting the source
            # immediately once raced as '' != manual there)
            assert await wait_until(
                pilot, lambda: not loading.display, timeout=15.0
            )
            # F8 opens the default (english) manual
            assert md.source == load_manual_markdown("en")
            # the viewer follows the active yate theme via the bridge -- no
            # per-screen theme switch happens
            assert app.theme == "yate-mocha"
            # f8 again must not stack a second viewer
            await pilot.press("f8")
            await pilot.pause()
            assert len(app.screen_stack) == 2
            await pilot.press("escape")
            await pilot.pause()
            assert not isinstance(app.screen, MarkdownDocScreen)
            # ... and the theme is still yate-mocha afterwards (no restore)
            assert app.theme == "yate-mocha"

    asyncio.run(scenario())


def test_startup_selects_yate_bridge_theme() -> None:
    async def scenario() -> None:
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            # startup defaults to the mocha yate theme -> yate-mocha bridge
            assert app.theme == "yate-mocha"
            assert app.get_theme("yate-mocha") is not None

    asyncio.run(scenario())


def test_set_theme_switches_textual_theme_and_overlay_border() -> None:
    async def scenario() -> None:
        from textual.color import Color

        from yate.editor_view import theme as yate_theme

        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            # switch to latte -> app.theme becomes yate-latte, the overlay
            # border token ($primary) resolves to latte's accent2 (mauve)
            app.editor.run_command("set theme=latte")
            await pilot.pause()
            await pilot.pause()
            assert app.theme == "yate-latte"
            # open the help overlay and inspect its border color -- it must
            # follow the latte palette, not the textual-dark blue.  The border
            # shorthand returns an Edges NamedTuple of (type, Color) per side.
            await pilot.press("f1")
            await pilot.pause()
            overlay = app.screen.query_one("#overlay")
            border_color = overlay.styles.border.top[1]
            expected = Color.parse(yate_theme.THEMES["latte"].accent2)
            assert border_color.hex == expected.hex
            await pilot.press("escape")
            await pilot.pause()

            # one non-Mocha dark theme proves the textual-dark blue is gone
            app.editor.run_command("set theme=onedark")
            await pilot.pause()
            await pilot.pause()
            assert app.theme == "yate-onedark"
            await pilot.press("f1")
            await pilot.pause()
            overlay = app.screen.query_one("#overlay")
            border_color = overlay.styles.border.top[1]
            expected = Color.parse(yate_theme.THEMES["onedark"].accent2)
            assert border_color.hex == expected.hex

    asyncio.run(scenario())


def test_startup_falls_back_to_mocha_when_selected_theme_bridge_fails() -> None:
    """A yate theme with an unusable bridge must not crash startup."""
    from dataclasses import fields as dc_fields

    from yate.editor_view.theme import THEMES, Theme, set_theme

    async def scenario() -> None:
        base = THEMES["mocha"]
        d = {f.name: getattr(base, f.name) for f in dc_fields(base)}
        d["name"] = "broken-bridge"
        d["bg"] = "#gggggg"  # invalid -> to_textual_theme raises
        broken = Theme(**d)  # type: ignore[arg-type]
        THEMES["broken-bridge"] = broken
        try:
            app = YateApp(theme_name="broken-bridge")
            async with app.run_test(size=(100, 30)) as pilot:
                await pilot.pause()
                # bridge failed for 'broken-bridge'; startup fell back to mocha
                assert app.theme == "yate-mocha"
                assert any("broken-bridge" in e for e in app.editor.config.errors)
        finally:
            THEMES.pop("broken-bridge", None)
            set_theme("mocha")

    asyncio.run(scenario())


def test_valid_custom_yate_theme_gets_working_bridge() -> None:
    from dataclasses import fields as dc_fields

    from textual.color import Color

    from yate.editor_view.theme import THEMES, Theme, set_theme

    async def scenario() -> None:
        base = THEMES["mocha"]
        d = {f.name: getattr(base, f.name) for f in dc_fields(base)}
        d["name"] = "custom-ok"
        d["accent2"] = "#ff00ff"  # distinct so the bridge border is testable
        custom = Theme(**d)  # type: ignore[arg-type]
        THEMES["custom-ok"] = custom
        try:
            app = YateApp(theme_name="custom-ok")
            async with app.run_test(size=(100, 30)) as pilot:
                await pilot.pause()
                assert app.theme == "yate-custom-ok"
                assert app.get_theme("yate-custom-ok") is not None
                # the overlay border follows the custom theme's accent2
                await pilot.press("f1")
                await pilot.pause()
                overlay = app.screen.query_one("#overlay")
                border_color = overlay.styles.border.top[1]
                assert border_color.hex == Color.parse("#ff00ff").hex
        finally:
            THEMES.pop("custom-ok", None)
            set_theme("mocha")

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "cmd_arg,lang",
    [("zh", "zh"), ("en", "en"), ("bogus", "en")],
    ids=["zh", "en", "bogus"],
)
def test_manual_command_selects_language(cmd_arg: str, lang: str) -> None:
    async def scenario() -> None:
        from textual.widgets import Markdown

        from yate.editor_view.manual import load_manual_markdown

        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            app.editor.run_command(f"manual {cmd_arg}".strip())
            await pilot.pause()
            assert isinstance(app.screen, MarkdownDocScreen)
            md = app.screen.query_one("#doc-md", Markdown)
            assert md.source == load_manual_markdown(lang)

    asyncio.run(scenario())


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_both_language_files_bundled(lang: str) -> None:
    from yate.editor_view.manual import load_manual_markdown

    text = load_manual_markdown(lang)
    assert len(text) > 1000
    assert text.lstrip().startswith("# yate")


def test_manual_search_filters_and_cycles_matches() -> None:
    from textual.containers import Horizontal
    from textual.widgets import Input, Markdown, Static
    from yate.editor_view.manual import _widget_plain_text

    async def scenario() -> None:
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            await pilot.press("f8")
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, MarkdownDocScreen)
            bar = screen.query_one("#doc-search-bar", Horizontal)
            field = screen.query_one("#doc-search-input", Input)
            status = screen.query_one("#doc-search-status", Static)
            md = screen.query_one("#doc-md", Markdown)

            def footer_text() -> str:
                return _widget_plain_text(
                    screen.query_one("#doc-footer", Static)
                )

            assert not bar.display
            # bar hidden: footer advertises n/N to repeat a search
            assert "n/N" in footer_text()
            # ctrl+f reveals the search bar and focuses it
            await pilot.press("ctrl+f")
            await pilot.pause()
            assert bar.display
            assert screen.focused is field
            # bar open: footer must advertise Enter / Shift+Enter (typing
            # n/N there are search characters, not navigation)
            search_footer = footer_text()
            assert "enter" in search_footer.lower()
            assert "shift+enter" in search_footer.lower()
            assert "repeat last match" not in search_footer
            # typing live-marks every block containing the query
            await pilot.press("y", "a", "t", "e")
            await pilot.pause()
            private = cast(Any, screen)
            assert len(private._hits) >= 2
            assert private._hit_index == 0
            assert len(list(md.query(".doc-hit-current"))) == 1
            assert len(list(md.query(".doc-hit"))) >= 1
            assert "1/" in str(status.content)
            # enter advances to the next match, shift+enter goes back
            await pilot.press("enter")
            await pilot.pause()
            assert private._hit_index == 1
            assert "2/" in str(status.content)
            await pilot.press("shift+enter")
            await pilot.pause()
            assert private._hit_index == 0
            # escape while typing closes only the bar (manual stays open)…
            await pilot.press("escape")
            await pilot.pause()
            assert not bar.display
            assert isinstance(app.screen, MarkdownDocScreen)
            # footer switches back to the browse hints (n/N repeat)
            assert "n/N" in footer_text()
            assert "repeat last match" in footer_text()
            # …and n/N repeat the last search with highlights still present
            await pilot.press("n")
            await pilot.pause()
            assert private._hit_index == 1
            await pilot.press("N")
            await pilot.pause()
            assert private._hit_index == 0
            # escape with the bar closed dismisses the manual itself
            await pilot.press("escape")
            await pilot.pause()
            assert not isinstance(app.screen, MarkdownDocScreen)

    asyncio.run(scenario())


def test_manual_search_step_lands_on_exact_rendered_row() -> None:
    """Regression: n/N stepped the counter but did not scroll when
    several matches lived in one wrapped widget (scroll was widget
    level); table cells were not searchable at all."""
    from textual.containers import VerticalScroll

    async def scenario() -> None:
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            await pilot.press("f8")
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, MarkdownDocScreen)
            md = screen.query_one("Markdown")
            # layout readiness, not just child count: _run_search scans
            # widget.region.height, which is 0 for every widget until the
            # refresh cycle lays the screen out (flaky under full-suite
            # load, where that cycle lands after the search below)
            await wait_until(
                pilot,
                lambda: len(list(md.walk_children())) > 20
                and any(w.region.height > 0 for w in md.walk_children(Widget)),
            )
            private = cast(Any, screen)
            scroll = screen.query_one("#doc-scroll", VerticalScroll)

            # table cell content is now searched too
            private._run_search("item")
            assert private._hits
            widget_types = {type(w).__name__ for w, _r, _c, _l in private._hits}
            assert "MarkdownTableCellContents" in widget_types

            # matches inside one wrapped widget must land on distinct rows:
            # measure each target from the same baseline (top), so the row
            # offset is the only thing that differs
            private._run_search("ctrl")
            assert len(private._hits) > 10
            moved = 0
            for i in range(1, len(private._hits)):
                w0, r0, _c0, _l0 = private._hits[i - 1]
                w1, r1, _c1, _l1 = private._hits[i]
                if w0 is w1 and r0 != r1:
                    scroll.scroll_to(y=0, animate=False, immediate=True)
                    private._hit_index = i - 1
                    private._goto_current_hit()
                    y0 = float(scroll.scroll_target_y)
                    scroll.scroll_to(y=0, animate=False, immediate=True)
                    private._hit_index = i
                    private._goto_current_hit()
                    y1 = float(scroll.scroll_target_y)
                    if y0 == y1 == float(scroll.max_scroll_y):
                        continue  # bottom clamp: both rows already visible
                    assert y0 != y1, (
                        f"same-widget rows {r0}/{r1} share a scroll target"
                    )
                    assert abs((y1 - y0) - (r1 - r0)) <= 1
                    moved += 1
            assert moved > 0

    asyncio.run(scenario())


def test_manual_search_no_matches_then_slash_reopens() -> None:
    from textual.containers import Horizontal
    from textual.widgets import Input, Markdown, Static

    async def scenario() -> None:
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            await pilot.press("f8")
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, MarkdownDocScreen)
            # "/" (textual key name "slash") also opens the search bar
            await pilot.press("slash")
            await pilot.pause()
            bar = screen.query_one("#doc-search-bar", Horizontal)
            field = screen.query_one("#doc-search-input", Input)
            status = screen.query_one("#doc-search-status", Static)
            md = screen.query_one("#doc-md", Markdown)
            assert bar.display
            assert screen.focused is field
            # a query present nowhere reports "no matches" and tints nothing
            await pilot.press("z", "q", "z", "q", "w", "x")
            await pilot.pause()
            private = cast(Any, screen)
            assert private._hits == []
            assert private._hit_index == -1
            assert len(list(md.query(".doc-hit"))) == 0
            assert "no matches" in str(status.content)
            # clearing the query removes the error state
            await pilot.press(*(("backspace",) * 10))
            await pilot.pause()
            assert field.value == ""
            assert private._hits == []
            assert "type to search" in str(status.content)
            assert isinstance(app.screen, MarkdownDocScreen)

    asyncio.run(scenario())


# ----------------------------------------------------- async background workers


def test_manual_paints_before_content_loads() -> None:
    from unittest.mock import patch

    from textual.widgets import Markdown, Static

    from yate.editor_view import manual as manual_mod

    original = manual_mod.load_doc_markdown

    def slow_load(kind: str, lang: str = "en") -> str:
        time.sleep(1.5)
        return original(kind, lang)

    async def scenario() -> None:
        app = YateApp()
        with patch(
            "yate.editor_view.manual.load_doc_markdown", side_effect=slow_load
        ):
            async with app.run_test(size=(100, 30)) as pilot:
                await pilot.pause()
                await pilot.press("f8")
                # while the worker thread is still reading: screen + loading
                # line are already on screen, the markdown itself is empty
                await pilot.pause(0.15)
                assert isinstance(app.screen, MarkdownDocScreen)
                md = app.screen.query_one("#doc-md", Markdown)
                loading = app.screen.query_one("#doc-loading", Static)
                assert md.source == ""
                assert loading.display
                # content then arrives without dismissing the screen
                loaded = await wait_until(
                    pilot,
                    lambda: bool(md.source) and not loading.display,
                    timeout=30.0,
                )
                assert loaded
                assert md.source == original("manual", "en")
                assert not loading.display
                assert isinstance(app.screen, MarkdownDocScreen)

    asyncio.run(scenario())


def test_shell_command_runs_without_freezing_ui() -> None:
    from unittest.mock import patch

    from yate.editor_view.modals import OutputScreen
    from yate.services.shell import ShellResult

    def slow_shell(command: str, cwd: object = None,
                   timeout: float = 60.0) -> ShellResult:
        # long enough that headless message-pump slowness cannot let it
        # finish before the responsiveness assertions run
        time.sleep(2.0)
        return ShellResult(command, 0, "yate-async-marker", Path.cwd())

    async def scenario() -> None:
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            prompt_bar = app.editor.prompt_bar
            assert prompt_bar is not None
            with patch("yate.editor.run_shell", side_effect=slow_shell):
                # F2 opens the shell prompt in vsc mode (":" is vim-only)
                await pilot.press("f2")
                assert prompt_bar.active_mode == "shell"
                for ch in "echo hi":
                    await pilot.press(ch)
                await pilot.press("enter")
                # command dispatched: prompt closed, no output screen yet,
                # focus back in the editor while the thread is running
                await pilot.pause(0.15)
                assert len(app.screen_stack) == 1
                assert app.focused is app.editor.panes.active_view
                # the TUI stays responsive: F1 help opens over the running job
                await pilot.press("f1")
                await pilot.pause(0.1)
                assert len(app.screen_stack) == 2
                await pilot.press("escape")
                await pilot.pause(0.1)
            # the output screen appears when the worker finishes
            shown = await wait_until(
                pilot, lambda: isinstance(app.screen, OutputScreen),
                timeout=10.0,
            )
            assert shown
            out = cast(OutputScreen, app.screen)
            assert "yate-async-marker" in out.output_text
            assert out.exit_code == 0

    asyncio.run(scenario())


def test_file_palette_indexes_in_background(tmp_path: Path) -> None:
    from unittest.mock import patch

    from rich.text import Text
    from textual.widgets import Static

    from yate.editor_view.palette import PaletteScreen
    from yate.services.workspace import Workspace

    root = tmp_path
    (root / "notes.txt").write_text("x\n", encoding="utf-8")
    app = YateApp(target=root)

    async def scenario() -> None:
        def slow_walk(self: Workspace, limit: int = 5000) -> list[Path]:
            time.sleep(1.5)
            return [root / "notes.txt"]

        def status_text() -> str:
            content = palette.query_one("#palette-results", Static).content
            return content.plain if isinstance(content, Text) else ""

        with patch.object(Workspace, "walk_files", slow_walk):
            async with app.run_test(size=(100, 30)) as pilot:
                await pilot.press("ctrl+p")
                await pilot.pause(0.15)
                assert isinstance(app.screen, PaletteScreen)
                palette = cast(PaletteScreen, app.screen)
                assert "indexing" in status_text()
                done = await wait_until(
                    pilot, lambda: palette.filtered_count == 1,
                    timeout=10.0,
                )
                assert done
                assert "notes.txt" in status_text()

    asyncio.run(scenario())


# --------------------------------------- window focus / pane focus switching


@pytest.fixture
def pane_root(tmp_path: Path) -> Path:
    """Workspace root pre-seeded with the files the pane tests open."""
    (tmp_path / "alpha.txt").write_text(
        "alpha\nbeta\ngamma\n", encoding="utf-8")
    (tmp_path / "bravo.txt").write_text(
        "bravo one\nbravo two\n", encoding="utf-8")
    return tmp_path


def test_vsc_chords_focus_panes(pane_root: Path) -> None:
    async def scenario() -> None:
        app = YateApp(target=pane_root)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            # initial focus is the editor; ctrl+shift+e moves to the explorer
            assert app.focused is app.editor.panes.active_view
            await pilot.press("ctrl+shift+e")
            await pilot.pause()
            assert app.focused is app.editor.explorer_tree
            # vscode-style: ctrl+1 focuses the editor again
            await pilot.press("ctrl+1")
            await pilot.pause()
            assert app.focused is app.editor.panes.active_view
            # ... and ctrl+shift+e focuses the explorer once more
            await pilot.press("ctrl+shift+e")
            await pilot.pause()
            assert app.focused is app.editor.explorer_tree
            await pilot.press("ctrl+1")
            await pilot.pause()
            assert app.focused is app.editor.panes.active_view

    asyncio.run(scenario())


def test_vim_ctrl_w_prefix_switches_panes(pane_root: Path) -> None:
    async def scenario() -> None:
        app = YateApp(target=pane_root)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            app.editor.select_keymap("vim")
            await pilot.pause()
            # ctrl+w arms the prefix, h goes to the left pane (explorer)
            await pilot.press("ctrl+w")
            await pilot.pause()
            assert app.editor.window_pending
            await pilot.press("h")
            await pilot.pause()
            assert not app.editor.window_pending
            assert app.focused is app.editor.explorer_tree
            # l goes back to the right pane (editor)
            await pilot.press("ctrl+w")
            await pilot.press("l")
            await pilot.pause()
            assert app.focused is app.editor.panes.active_view
            # ctrl+w ctrl+w cycles between the two panes
            await pilot.press("ctrl+w")
            await pilot.press("ctrl+w")
            await pilot.pause()
            assert app.focused is app.editor.explorer_tree

    asyncio.run(scenario())


def test_vim_window_prefix_cancelled_by_other_keys(pane_root: Path) -> None:
    async def scenario() -> None:
        app = YateApp(target=pane_root)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            app.editor.select_keymap("vim")
            await pilot.pause()
            await pilot.press("ctrl+w")
            await pilot.pause()
            assert app.editor.window_pending
            # an unrelated key cancels the prefix and is processed normally
            before = app.editor.session.buffer.lines[0]
            await pilot.press("x")
            await pilot.pause()
            assert not app.editor.window_pending
            assert app.editor.session.buffer.lines[0] == before[1:]  # x deleted a char

    asyncio.run(scenario())


def test_vim_insert_mode_ctrl_w_not_intercepted(pane_root: Path) -> None:
    async def scenario() -> None:
        app = YateApp(target=pane_root)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            app.editor.select_keymap("vim")
            await pilot.pause()
            await pilot.press("i")  # INSERT
            await pilot.pause()
            await pilot.press("ctrl+w")
            await pilot.pause()
            assert not app.editor.window_pending

    asyncio.run(scenario())


# ---------------------------------------------------------- buffer completions


def test_buffer_words_complete_without_lsp(tmp_path: Path) -> None:
    async def scenario() -> None:
        doc = tmp_path / "note.txt"
        # "alpha" appears twice so it surfaces as a completion candidate;
        # the half-typed word on the cursor line is excluded.
        doc.write_text(
            "alpha bravo charlie\nalpha delta\n", encoding="utf-8"
        )
        app = YateApp(target=doc)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            popup = app.editor.completion_popup
            assert popup is not None
            # no language server for .txt
            assert not app.editor.lsp.supports(app.editor.session.doc)
            # move to a new line and start typing "al"
            app.editor.session.buffer.move_doc_end()
            app.editor.session.buffer.insert_text("\nal")
            # cursor now sits at the end of the freshly typed "al"
            app.editor.refresh_ui()
            await pilot.press("ctrl+space")
            shown = await wait_until(pilot, lambda: popup.is_open)
            assert shown
            labels = [item.label for item in popup.items]
            assert "alpha" in labels
            # "al" prefix excludes the other words
            assert "bravo" not in labels

    asyncio.run(scenario())


def test_buffer_completion_accepts_word(tmp_path: Path) -> None:
    async def scenario() -> None:
        doc = tmp_path / "note.txt"
        doc.write_text("banana bandana\n", encoding="utf-8")
        app = YateApp(target=doc)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            popup = app.editor.completion_popup
            assert popup is not None
            app.editor.session.buffer.move_doc_end()
            app.editor.session.buffer.insert_text("\nba")
            app.editor.refresh_ui()
            await pilot.press("ctrl+space")
            await wait_until(pilot, lambda: popup.is_open)
            # pick the first match and accept with tab
            await pilot.press("tab")
            await pilot.pause()
            assert not popup.is_open
            # "ba" replaced by the accepted word
            last_line = app.editor.session.buffer.lines[-1]
            assert last_line.startswith("ban")

    asyncio.run(scenario())


def test_completion_popup_keeps_typing_and_filters(tmp_path: Path) -> None:
    """Typing must fall through while the completion popup is open.

    Regression guard for the popup swallowing every keypress: previously an
    open popup consumed all keys (``return True``), so the user could neither
    keep typing to refine the candidates nor use global chords.  Only the
    popup-owned keys (tab / enter / up / down / escape) may be consumed; every
    other key must reach the normal dispatch, insert its character and
    re-query the candidates via ``CompletionController.after_editor_key``.
    """

    async def scenario() -> None:
        doc = tmp_path / "note.txt"
        # "alpha" is repeated so it becomes a buffer-word candidate.
        doc.write_text(
            "alpha bravo charlie\nalpha delta\n", encoding="utf-8"
        )
        app = YateApp(target=doc)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            popup = app.editor.completion_popup
            assert popup is not None
            # move to a new line and start typing "al"
            app.editor.session.buffer.move_doc_end()
            app.editor.session.buffer.insert_text("\nal")
            app.editor.refresh_ui()
            await pilot.press("ctrl+space")
            shown = await wait_until(pilot, lambda: popup.is_open)
            assert shown
            labels = [item.label for item in popup.items]
            assert "alpha" in labels
            # "al" prefix excludes the other words
            assert "bravo" not in labels

            # A plain character must not be swallowed by the open popup: it is
            # inserted into the buffer and the candidates are re-queried.
            await pilot.press("p")
            await pilot.pause()
            assert app.editor.session.buffer.lines[-1] == "alp"
            assert popup.is_open
            assert await wait_until(pilot, lambda: popup.is_open)
            labels = [item.label for item in popup.items]
            assert "alpha" in labels

            # The buffer keeps growing with the next typed character.
            await pilot.press("h")
            await pilot.pause()
            assert app.editor.session.buffer.lines[-1] == "alph"

            # The popup still owns tab: it accepts "alpha" and closes.
            await pilot.press("tab")
            await pilot.pause()
            assert not popup.is_open
            assert app.editor.session.buffer.lines[-1].startswith("alpha")

    asyncio.run(scenario())


# ---------------------------------------------------- palette tab completion


def test_tab_cycles_and_single_match_auto_chooses() -> None:
    from yate.editor_view.palette import PaletteScreen

    async def scenario() -> None:
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.press("alt+shift+p")
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, PaletteScreen)
            # multiple matches: tab cycles the cursor (does not dismiss)
            for ch in "set":
                await pilot.press(ch)
            await pilot.pause()
            before = screen.cursor_index
            await pilot.press("tab")
            await pilot.pause()
            assert screen.cursor_index == (before + 1) % screen.filtered_count
            assert isinstance(app.screen, PaletteScreen)
            # narrow to a single unique match: tab chooses it immediately
            for ch in "theme":
                await pilot.press(ch)
            await pilot.pause()
            assert screen.filtered_count == 1
            await pilot.press("tab")
            await pilot.pause()
            # palette dismissed and :theme ran (prints theme info)
            assert not isinstance(app.screen, PaletteScreen)

    asyncio.run(scenario())


# ------------------------------------------------- command line tab completion


def test_tab_completes_unique_command_name() -> None:
    async def scenario() -> None:
        app = YateApp(keymap="vim")
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.press(":")
            await pilot.pause()
            # "writ" -> only "write" matches
            await pilot.press(*"writ")
            await pilot.pause()
            await pilot.press("tab")
            await pilot.pause()
            inp = app.editor.prompt_bar.input if app.editor.prompt_bar else None
            assert inp is not None
            assert inp.value == "write"

    asyncio.run(scenario())


def test_tab_cycles_multiple_command_matches() -> None:
    async def scenario() -> None:
        app = YateApp(keymap="vim")
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.press(":")
            await pilot.pause()
            # "w" matches several commands (w / words / wq / write ...); the
            # common prefix is just "w" so tab cycles through the matches.
            await pilot.press("w")
            await pilot.pause()
            inp = app.editor.prompt_bar.input if app.editor.prompt_bar else None
            assert inp is not None
            matches = app.editor.prompt_completions("w", "command")
            assert len(matches) > 1
            await pilot.press("tab")
            await pilot.pause()
            first = inp.value
            assert first in matches
            await pilot.press("tab")
            await pilot.pause()
            assert inp.value in matches
            assert inp.value != first

    asyncio.run(scenario())


def test_tab_completes_theme_argument() -> None:
    async def scenario() -> None:
        app = YateApp(keymap="vim")
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.press(":")
            await pilot.pause()
            await pilot.press(*"theme mac")
            await pilot.pause()
            await pilot.press("tab")
            await pilot.pause()
            inp = app.editor.prompt_bar.input if app.editor.prompt_bar else None
            assert inp is not None
            assert inp.value.endswith("macchiato")

    asyncio.run(scenario())


def test_tab_completes_path_for_edit_command(tmp_path: Path) -> None:
    async def scenario() -> None:
        (tmp_path / "alpha.py").write_text("x\n", encoding="utf-8")
        (tmp_path / "beta.py").write_text("x\n", encoding="utf-8")
        app = YateApp(keymap="vim", target=tmp_path)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.press(":")
            await pilot.pause()
            await pilot.press(*"e al")
            await pilot.pause()
            await pilot.press("tab")
            await pilot.pause()
            inp = app.editor.prompt_bar.input if app.editor.prompt_bar else None
            assert inp is not None
            assert inp.value.endswith("alpha.py")

    asyncio.run(scenario())


# ----------------------------------------------------------- filetype commands


def test_set_filetype_by_name_or_extension_and_auto_reset() -> None:
    async def scenario() -> None:
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            doc = app.editor.session.doc
            assert doc.path is None
            assert doc.filetype == "plaintext"

            app.editor.run_command("set filetype=python")  # language name
            assert doc.filetype_override == "py"
            assert doc.filetype == "py"

            app.editor.run_command("ft .rs")               # alias + dot prefix
            assert doc.filetype == "rs"

            app.editor.run_command("language typescript")  # vscode-style name
            assert doc.filetype == "ts"

            app.editor.run_command("set language=auto")    # back to detection
            assert doc.filetype_override is None
            assert doc.filetype == "plaintext"
            await pilot.pause()

    asyncio.run(scenario())


def test_unknown_filetype_is_kept_without_highlighter() -> None:
    async def scenario() -> None:
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            app.editor.run_command("set ft=zig")
            assert app.editor.session.doc.filetype_override == "zig"
            assert app.editor.session.doc.filetype == "zig"
            app.editor.run_command("filetype auto")
            assert app.editor.session.doc.filetype_override is None
            await pilot.pause()

    asyncio.run(scenario())


def test_highlighting_follows_the_override() -> None:
    async def scenario() -> None:
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            editor = app.editor.panes.active_view
            assert editor is not None
            app.editor.session.buffer.insert_text("def foo():\n    pass\n")
            # Plain-text detection for an unnamed buffer -> no tokens.
            # Wait for the background pass: a direct buffer edit does not
            # refresh the view, and the startup pass for the pre-edit
            # (empty) buffer is discarded, so a single pilot.pause() does
            # not guarantee the pass has stored its result.
            assert await wait_until(
                pilot,
                lambda: editor.highlight_probe().filetype == "plaintext",
                timeout=5.0,
            )

            app.editor.run_command("set filetype=python")
            changed = await wait_until(
                pilot,
                lambda: editor.highlight_probe().filetype == "py",
                timeout=5.0,
            )
            assert changed
            pairs = [
                (t.kind, "def foo():"[t.start:t.end])
                for t in editor.tokens_for(0)
            ]
            assert ("keyword", "def") in pairs
            assert ("function", "foo") in pairs

    asyncio.run(scenario())


def test_tab_completions_for_filetype() -> None:
    async def scenario() -> None:
        app = YateApp(keymap="vim")
        async with app.run_test(size=(100, 30)) as pilot:
            assert app.editor.prompt_completions("set filetype=pyt", "command") == [
                "set filetype=python"
            ]
            # "r" prefix matches both the "rs" extension key and the
            # "rust" language name.
            assert sorted(app.editor.prompt_completions("filetype r", "command")) == [
                "filetype rs", "filetype rust"
            ]
            vals = app.editor.prompt_completions("set ft=", "command")
            assert "set ft=auto" in vals
            assert "set ft=python" in vals
            assert app.editor.prompt_completions("set file", "command") == [
                "set filetype"
            ]
            await pilot.pause()

    asyncio.run(scenario())


# ------------------------------------------------------------------- goto line


def _seed_goto(app: YateApp, lines: int = 6) -> None:
    app.editor.session.buffer.set_text("\n".join(f"line {i + 1}" for i in range(lines)))
    app.editor.session.buffer.set_cursor((0, 0))


def test_bare_number_jumps_to_line() -> None:
    async def scenario() -> None:
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            _seed_goto(app)
            app.editor.run_command("4")
            await pilot.pause()
            assert app.editor.session.buffer.row == 3  # 1-based input -> 0-based row
            assert app.editor.session.buffer.anchor is None

    asyncio.run(scenario())


def test_line_number_is_clamped() -> None:
    async def scenario() -> None:
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            _seed_goto(app)
            app.editor.run_command("999")
            await pilot.pause()
            assert app.editor.session.buffer.row == 5
            app.editor.run_command("0")
            await pilot.pause()
            assert app.editor.session.buffer.row == 0

    asyncio.run(scenario())


def test_signed_numbers_are_relative() -> None:
    async def scenario() -> None:
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            _seed_goto(app)
            app.editor.session.buffer.set_cursor((0, 0))
            app.editor.run_command("+2")
            await pilot.pause()
            assert app.editor.session.buffer.row == 2
            app.editor.run_command("-1")
            await pilot.pause()
            assert app.editor.session.buffer.row == 1

    asyncio.run(scenario())


def test_non_numeric_unknown_command_still_warns() -> None:
    async def scenario() -> None:
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            _seed_goto(app)
            app.editor.run_command("12abc")
            await pilot.pause()
            assert app.editor.session.buffer.row == 0  # did not jump
            prompt_bar = app.editor.prompt_bar
            assert prompt_bar is not None
            msg = "".join(
                seg.text for seg in prompt_bar.message.render_line(0)
            )
            assert "not an editor command" in msg

    asyncio.run(scenario())


def test_ctrl_g_opens_goto_prompt_in_vsc_keymap() -> None:
    async def scenario() -> None:
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            _seed_goto(app)
            prompt_bar = app.editor.prompt_bar
            assert prompt_bar is not None
            await pilot.press("ctrl+g")
            await pilot.pause()
            assert prompt_bar.active_mode == "goto"
            await pilot.press("2", "enter")
            await pilot.pause()
            assert prompt_bar.active_mode is None
            assert app.editor.session.buffer.row == 1
            assert app.focused is app.editor.panes.active_view

    asyncio.run(scenario())


def test_ctrl_g_opens_goto_prompt_in_vim_normal_mode() -> None:
    async def scenario() -> None:
        app = YateApp(keymap="vim")
        async with app.run_test(size=(100, 30)) as pilot:
            _seed_goto(app)
            prompt_bar = app.editor.prompt_bar
            assert prompt_bar is not None
            await pilot.press("ctrl+g")
            await pilot.pause()
            assert prompt_bar.active_mode == "goto"
            await pilot.press("5", "enter")
            await pilot.pause()
            assert app.editor.session.buffer.row == 4

    asyncio.run(scenario())


def test_goto_prompt_rejects_non_numeric() -> None:
    async def scenario() -> None:
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            _seed_goto(app)
            app.editor.goto_prompt()
            await pilot.pause()
            prompt_bar = app.editor.prompt_bar
            assert prompt_bar is not None
            prompt_bar.input.value = "abc"
            await pilot.press("enter")
            await pilot.pause()
            assert app.editor.session.buffer.row == 0
            msg = "".join(
                seg.text for seg in prompt_bar.message.render_line(0)
            )
            assert "not a line number" in msg

    asyncio.run(scenario())


# ------------------------------------------------------------- command feedback


def _message_text(app: YateApp) -> str:
    assert app.editor.prompt_bar is not None
    return plain_text(app.editor.prompt_bar.message.content)


@pytest.mark.parametrize(
    "command,cls_name",
    [
        ("manual", "MarkdownDocScreen"),
        ("changelog", "MarkdownDocScreen"),
        ("help", "HelpScreen"),
        ("files", "PaletteScreen"),
        ("palette", "PaletteScreen"),
    ],
    ids=["manual", "changelog", "help", "files", "palette"],
)
def test_overlay_commands_clear_stale_message(
    command: str, cls_name: str
) -> None:
    # The previous command's message used to outlive an overlay command
    # (:manual/:help/:files/:palette): the overlay hides the line while
    # open and the stale text reappeared on close, so success looked
    # silent. Pushing an overlay resets the line to its idle hint.
    async def scenario() -> None:
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            app.editor.message("stale note from before")
            app.editor.run_command(command)
            await pilot.pause()
            assert type(app.screen).__name__ == cls_name
            assert "stale note" not in _message_text(app)
            await pilot.press("escape")
            await pilot.pause()
            assert "stale note" not in _message_text(app)

    asyncio.run(scenario())


def test_cycle_tab_with_single_tab_is_silent_noop() -> None:
    # N10: cycling with a single tab used to warn on every keypress;
    # it is now a silent no-op -- repeated cycles in both directions
    # leave the message line untouched and never raise.
    async def scenario() -> None:
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            baseline = _message_text(app)
            assert "only one tab" not in baseline

            app.editor.run_command("bn")
            await pilot.pause()
            app.editor.run_command("bp")
            await pilot.pause()
            app.editor.cycle_tab(1)
            app.editor.cycle_tab(-1)
            await pilot.pause()
            assert _message_text(app) == baseline
            assert app.editor.session.doc is app.editor.session.docs[0]

    asyncio.run(scenario())


def test_cycle_tab_resets_the_previous_search(tmp_path: Path) -> None:
    """Regression: ``:bn`` left the previous tab's ``(row, start, end)`` match
    spans in the session, so the new document painted stale highlights and
    ``n`` jumped to out-of-range coordinates.  Switching tabs must drop them.
    """

    async def scenario() -> None:
        alpha = tmp_path / "alpha.txt"
        beta = tmp_path / "beta.txt"
        alpha.write_text("needle one\nfiller\nneedle two\n", encoding="utf-8")
        beta.write_text("unrelated\n", encoding="utf-8")

        app = YateApp(str(alpha))
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()

            # Open a second tab, then return to alpha so the search lands on
            # the first document and a later ``:bn`` moves away from it.
            app.editor.open_path(beta)
            await pilot.pause()
            app.editor.cycle_tab(-1)
            await pilot.pause()
            first = app.editor.session.doc
            assert first.name == "alpha.txt"

            # Run a live search on the first document: two matches in view.
            await pilot.press("ctrl+f")
            await pilot.pause()
            for ch in "needle":
                await pilot.press(ch)
            await pilot.press("enter")
            await pilot.pause()
            assert app.editor.session.search.query == "needle"
            assert len(app.editor.session.search.matches) == 2

            # ``:bn`` switches tabs and must drop the previous tab's spans.
            app.editor.cycle_tab(1)
            await pilot.pause()
            assert app.editor.session.doc.name == "beta.txt"
            assert app.editor.session.search.matches == []
            assert app.editor.session.search.query == ""

            # ``n`` must not jump to the old document's out-of-range coords.
            app.editor.find_next(True)
            await pilot.pause()
            row, _col = app.editor.session.buffer.cursor
            assert 0 <= row < app.editor.session.buffer.line_count

            # Switching back is harmless and the state stays reset.
            app.editor.cycle_tab(-1)
            await pilot.pause()
            assert app.editor.session.doc is first
            assert app.editor.session.search.matches == []

    asyncio.run(scenario())


def test_click_tab_switches_document(tmp_path: Path) -> None:
    async def scenario() -> None:
        a = tmp_path / "alpha.txt"
        b = tmp_path / "beta.txt"
        a.write_text("alpha\n", encoding="utf-8")
        b.write_text("beta\n", encoding="utf-8")
        app = YateApp(str(a))
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            app.editor.open_path(b)
            await pilot.pause()
            assert len(app.editor.session.docs) == 2
            assert app.editor.session.index == 1  # b is active after open

            # Build the tab line and find the cell span of the first tab.
            _, regions = app.editor.tabbar.build(100)
            assert len(regions) >= 2
            start, end, doc_idx = regions[0]
            assert doc_idx == 0
            click_x = start + (end - start) // 2
            await pilot.click("#tabbar", offset=(click_x, 0))
            await pilot.pause()
            assert app.editor.session.index == 0
            assert app.editor.session.doc.name == "alpha.txt"

            # Clicking the already-active tab is a no-op.
            assert app.editor.session.index == 0
            await pilot.click("#tabbar", offset=(click_x, 0))
            await pilot.pause()
            assert app.editor.session.index == 0

    asyncio.run(scenario())


def test_set_terminal_height_reports_and_validates() -> None:
    async def scenario() -> None:
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            app.editor.run_command("set terminal_height=20")
            await pilot.pause()
            assert app.editor.config.terminal_height == 20
            assert "terminal height: 20 rows" in _message_text(app)

            app.editor.run_command("set terminal_height=99")
            await pilot.pause()
            assert app.editor.config.terminal_height == 20  # rejected
            assert "between 3 and 40" in _message_text(app)

            app.editor.run_command("set terminal_height=abc")
            await pilot.pause()
            assert "integer" in _message_text(app)

    asyncio.run(scenario())


def test_termclose_without_open_terminal_warns() -> None:
    async def scenario() -> None:
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            assert not app.editor.terminal_panel.is_visible
            app.editor.run_command("termclose")
            await pilot.pause()
            assert "already hidden" in _message_text(app)

    asyncio.run(scenario())


def test_term_commands_report_shown_and_hidden() -> None:
    async def scenario() -> None:
        app = YateApp()
        app.editor.terminal_panel.view_factory = _FakePty
        _FakePty.instances = []
        async with app.run_test(size=(100, 30)) as pilot:
            panel = app.editor.terminal_panel
            assert panel is not None
            app.editor.run_command("term")
            await wait_until(pilot, lambda: panel.view.proc is not None)
            assert "terminal shown" in _message_text(app)
            app.editor.run_command("termclose")
            await pilot.pause()
            assert not panel.display
            assert "terminal hidden" in _message_text(app)

    asyncio.run(scenario())


def test_setting_commands_confirm_success() -> None:
    async def scenario() -> None:
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            app.editor.run_command("set keymap=vim")
            await pilot.pause()
            assert "keymap:" in _message_text(app)
            app.editor.run_command("set theme=latte")
            await pilot.pause()
            assert "theme:" in _message_text(app)
            app.editor.run_command("set filetype=python")
            await pilot.pause()
            assert "filetype set to" in _message_text(app)

    asyncio.run(scenario())


# ---------------------------------------------------------- bundled extensions


def test_bundled_extensions_load_regardless_of_cwd(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    async def scenario() -> None:
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            records = {
                r.name: r for r in app.editor.extension_loader.loaded
            }
            assert "python_lsp" in records
            assert "csharp_highlight" in records
            # the .example template is never auto-loaded
            assert "example_ext" not in records
            assert records["python_lsp"].error is None
            assert records["csharp_highlight"].error is None

    monkeypatch.chdir(tmp_path)
    asyncio.run(scenario())


def test_disabled_extensions_skip_bundled_not_project_dir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from yate.config import YateConfig
    from yate.services import trust

    root = tmp_path
    project_ext = root / "extensions"
    project_ext.mkdir()
    (project_ext / "myext.py").write_text(
        "def setup(api):\n    pass\n", encoding="utf-8"
    )
    config = YateConfig(
        disabled_extensions=["python_lsp", "csharp_highlight"]
    )
    monkeypatch.setattr(trust, "TRUST_FILE", root / "trusted_workspaces")

    async def scenario() -> None:
        app = YateApp(config=config)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            names = {r.name for r in app.editor.extension_loader.loaded}
            assert "python_lsp" not in names
            assert "csharp_highlight" not in names
            # an untrusted workspace must not run its project scripts
            assert "myext" not in names
            assert any(
                "skipped untrusted" in message
                for message in app.editor._ext_messages
            )
            # and no Python server got registered while LSP was off
            assert app.editor.lsp.config_for("py") is None
            # :trust is the explicit confirmation that loads them now
            app.editor.trust_cwd_extensions()
            await pilot.pause()
            names = {r.name for r in app.editor.extension_loader.loaded}
            assert "myext" in names
        assert (root / "trusted_workspaces").exists()

    monkeypatch.chdir(root)
    asyncio.run(scenario())


def test_rc_same_stem_extension_is_named_as_shadowed(tmp_path: Path) -> None:
    # An rc-declared script with a bundled default's stem loads first, but
    # the last-write-wins registrars would let the bundled default take
    # over: the conflict must surface as a startup warning.
    from yate.config import YateConfig

    root = tmp_path
    rc_dir = root / "rc_extensions"
    rc_dir.mkdir()
    (rc_dir / "csharp_highlight.py").write_text(
        "def setup(api):\n    pass\n", encoding="utf-8"
    )
    config = YateConfig(extension_paths=[rc_dir])

    async def scenario() -> None:
        app = YateApp(config=config)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            messages = app.editor._ext_messages
            assert any(
                "csharp_highlight" in m
                and "shadowed by the bundled default" in m
                for m in messages
            ), messages

    asyncio.run(scenario())


def test_disabled_bundled_extension_does_not_warn_shadow(
    tmp_path: Path,
) -> None:
    # Disabling the bundled default removes the collision entirely.
    from yate.config import YateConfig

    root = tmp_path
    rc_dir = root / "rc_extensions"
    rc_dir.mkdir()
    (rc_dir / "csharp_highlight.py").write_text(
        "def setup(api):\n    pass\n", encoding="utf-8"
    )
    config = YateConfig(
        extension_paths=[rc_dir],
        disabled_extensions=["csharp_highlight"],
    )

    async def scenario() -> None:
        app = YateApp(config=config)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            messages = app.editor._ext_messages
            assert not any(
                "shadowed by the bundled default" in m for m in messages
            ), messages

    asyncio.run(scenario())


def test_rc_declaring_the_bundled_dir_does_not_warn_shadow(
    tmp_path: Path,
) -> None:
    # An rc extension_paths entry that *is* the bundled directory loads the
    # same scripts; de-duplication hands back the identical record, which
    # must not be reported as shadowing itself.
    from yate.config import YateConfig
    from yate.paths import bundled_extensions_dir

    config = YateConfig(extension_paths=[bundled_extensions_dir()])

    async def scenario() -> None:
        app = YateApp(config=config)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            messages = app.editor._ext_messages
            assert not any(
                "shadowed by the bundled default" in m for m in messages
            ), messages

    asyncio.run(scenario())


# ----------------------------------------------------------------- LSP UI fake


def _install_fake_server(
    app: YateApp, completions: list[dict[str, Any]] | None = None
) -> list[Any]:
    from yate.editor_lsp.client import ServerConfig

    created: list[Any] = []
    completions = completions if completions is not None else [
        {"label": "barbell", "insertText": "barbell", "kind": 3,
         "detail": "(object)"},
        {"label": "baritone", "insertText": "baritone", "kind": 3},
        {"label": "baz", "insertText": "baz", "kind": 5},
    ]

    class UiFakeClient:
        def __init__(self, config: Any, root: Any) -> None:
            self.config = config
            self.root_path = root
            from yate.editor_lsp import ServerState
            self.state = ServerState.READY
            self.error = ""
            self.trigger_characters: tuple[str, ...] = (".",)
            self.opened: list[Any] = []
            created.append(self)

        async def start(self) -> None:
            return None

        async def stop(self) -> None:
            from yate.editor_lsp import ServerState
            self.state = ServerState.STOPPED

        async def notify(self, method: str, params: Any) -> None:
            if method == "textDocument/didOpen":
                self.opened.append(params)

        async def request(self, method: str, params: Any) -> Any:
            return {"isIncomplete": False, "items": completions}

        async def start_request(self, method: str, params: Any) -> Any:
            import asyncio
            future: asyncio.Future[Any] = asyncio.get_running_loop().create_future()
            future.set_result({"isIncomplete": False, "items": completions})
            return 1, future

        async def send_cancel(self, request_id: int) -> None:
            return None

        def publish_diagnostics(
            self, manager: Any, uri: str, entries: list[dict[str, Any]]
        ) -> None:
            manager.handle_notification(
                "textDocument/publishDiagnostics",
                {"uri": uri, "diagnostics": entries},
            )

    def factory(config: Any, root: Any) -> Any:
        return UiFakeClient(config, root)

    app.editor.lsp.register_server(ServerConfig(
        name="python", command="fake", filetypes=["py"],
    ))
    # factory must be installed on the manager after registration; the
    # manager keeps it independent of config replacement
    app.editor.lsp.set_client_factory(factory)
    return created


def test_completion_popup_navigate_accept_and_ctrl_space(tmp_path: Path) -> None:
    async def scenario() -> None:
        py = tmp_path / "m.py"
        py.write_text("ba\n", encoding="utf-8")
        app = YateApp(target=py)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            _install_fake_server(app)
            app.editor.refresh_ui()  # schedules didOpen on the freshly registered server
            await pilot.pause()

            def is_ready() -> bool:
                state = app.editor.lsp.state_for_doc(app.editor.session.doc)
                return state is not None and state.value == "ready"

            ready = await wait_until(pilot, is_ready)
            assert ready
            popup = app.editor.completion_popup
            assert popup is not None
            # cursor sits at doc start after open; move to end of "ba"
            app.editor.session.buffer.cursor = (0, 2)
            app.editor.refresh_ui()
            # manual trigger via ctrl+space at the end of "ba"
            await pilot.press("ctrl+space")
            shown = await wait_until(pilot, lambda: popup.is_open)
            assert shown
            assert popup.item_count == 3
            first = popup.selected()
            assert first is not None
            assert first.label == "barbell"
            # down wraps through the list, esc closes
            await pilot.press("down")
            second = popup.selected()
            assert second is not None
            assert second.label == "baritone"
            await pilot.press("escape")
            assert not popup.is_open
            # reopen and accept the second entry with tab
            await pilot.press("ctrl+space")
            await wait_until(pilot, lambda: popup.is_open)
            await pilot.press("down", "tab")
            await pilot.pause()
            assert not popup.is_open
            assert app.editor.session.buffer.lines[0] == "baritone"
            assert app.editor.session.doc.modified

    asyncio.run(scenario())


def test_diagnostic_render_status_echo_and_command(tmp_path: Path) -> None:
    from yate.editor_lsp import protocol
    from yate.editor_view.modals import OutputScreen

    async def scenario() -> None:
        py = tmp_path / "diag.py"
        py.write_text("x = 1\n", encoding="utf-8")
        app = YateApp(target=py)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            created = _install_fake_server(app)
            app.editor.refresh_ui()
            await pilot.pause()
            await wait_until(pilot, lambda: bool(created and created[0].opened))
            fake = created[0]
            uri = protocol.path_to_uri(py.resolve())
            fake.publish_diagnostics(app.editor.lsp, uri, [
                {"range": {"start": {"line": 0, "character": 0},
                           "end": {"line": 0, "character": 5}},
                 "severity": 1, "message": "undefined name 'x'",
                 "source": "pyright"},
            ])
            await pilot.pause()
            editor = app.editor.panes.active_view
            assert editor is not None
            line0 = "".join(seg.text for seg in editor.render_line(0))
            assert "✖" in line0  # gutter mark
            underlined = [
                seg for seg in editor.render_line(0)
                if seg.style is not None and seg.style.underline
            ]
            assert underlined
            # status bar carries the error count
            status_bar = app.editor.status_bar
            assert status_bar is not None
            assert "✖ 1" in plain_text(status_bar.content)
            # message line echoes the diagnostic under the cursor
            prompt_bar = app.editor.prompt_bar
            assert prompt_bar is not None
            app.editor.refresh_ui()
            assert "undefined name" in plain_text(prompt_bar.message.content)
            # :diagnostics opens the listing screen
            app.editor.run_command("diagnostics")
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, OutputScreen)
            assert "undefined name" in cast(OutputScreen, screen).output_text

    asyncio.run(scenario())


def test_builtin_python_extension_loads_cleanly() -> None:
    # The auto-loaded extension registers a (disabled) python server and
    # setup must neither print nor spawn nor record an error.
    async def scenario() -> None:
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            assert "python" in app.editor.lsp.config_names()
            rec = next(r for r in app.editor.extension_loader.loaded
                       if r.name == "python_lsp")
            assert rec.error is None

    asyncio.run(scenario())


def test_rc_configured_server_auto_activates_on_matching_file(
    tmp_path: Path,
) -> None:
    from yate.config import LanguageServerSpec, YateConfig

    rs = tmp_path / "main.rs"
    rs.write_text("fn main() {}\n", encoding="utf-8")
    config = YateConfig(language_servers=[LanguageServerSpec(
        name="rc-rust",
        command="fake-rust-analyzer",
        filetypes=["rs"],
        language_ids={"rs": "rust"},
        root_markers=["Cargo.toml", ".git"],
    )])
    created: list[Any] = []

    def factory(config: Any, root: Any) -> Any:
        return _RcClientShim(created, config, root)

    async def scenario() -> None:
        app = YateApp(target=rs, config=config)
        # factory must be in place before on_mount registers/opens docs
        app.editor.lsp.set_client_factory(factory)
        async with app.run_test(size=(100, 30)) as pilot:
            opened = await wait_until(pilot, lambda: app.editor.lsp.is_open(app.editor.session.doc))
            assert opened
            registered = app.editor.lsp.config_for("rs")
            assert registered is not None
            assert registered.name == "rc-rust"
            state = app.editor.lsp.state_for_doc(app.editor.session.doc)
            assert state is not None
            assert state.value == "ready"
            assert len(created) == 1
            params = created[0].opened[0]
            assert params["textDocument"]["languageId"] == "rust"

    asyncio.run(scenario())


def test_rc_configured_server_activates_on_later_open(tmp_path: Path) -> None:
    from yate.config import LanguageServerSpec, YateConfig

    rs = tmp_path / "later.rs"
    rs.write_text("let x = 1;\n", encoding="utf-8")
    config = YateConfig(language_servers=[LanguageServerSpec(
        name="rc-rust-late", command="fake-rust", filetypes=["rs"],
    )])

    async def scenario() -> None:
        app = YateApp(config=config)
        created: list[Any] = []

        def factory(config: Any, root: Any) -> Any:
            return _RcClientShim(created, config, root)

        app.editor.lsp.set_client_factory(factory)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            # unnamed scratch buffer: registered but nothing spawned
            assert created == []
            assert not app.editor.lsp.is_open(app.editor.session.doc)
            registered = app.editor.lsp.config_for("rs")
            assert registered is not None
            assert registered.name == "rc-rust-late"
            # omitted root_markers fall back to the built-in defaults
            from yate.editor_lsp.client import DEFAULT_ROOT_MARKERS
            assert registered.root_markers == list(DEFAULT_ROOT_MARKERS)
            # opening the matching file activates the server
            app.editor.open_path(rs)
            await pilot.pause()
            activated = await wait_until(
                pilot, lambda: bool(created) and created[0].opened
            )
            assert activated
            assert app.editor.lsp.is_open(app.editor.session.doc)

    asyncio.run(scenario())


def test_rc_python_entry_overrides_builtin_extension(tmp_path: Path) -> None:
    # The bundled python_lsp extension registers a "python" server with
    # an empty command (YATE_PYTHON_LSP=off for the suite). A same-named
    # rc entry registered after extensions must replace it: opening a
    # .py file then talks to the rc server, not the disabled builtin one.
    from yate.config import LanguageServerSpec, YateConfig

    py = tmp_path / "app.py"
    py.write_text("print('hi')\n", encoding="utf-8")
    config = YateConfig(language_servers=[LanguageServerSpec(
        name="python",
        command="fake-pyright",
        args=["--stdio"],
        filetypes=["py", "pyi"],
        language_ids={"py": "python", "pyi": "python"},
        initialization_options={"diagnostics": True},
        settings={"python": {"version": "3"}},
        env={"FAKE_ENV": "1"},
        root_markers=["pyproject.toml", ".git"],
    )])

    async def scenario() -> None:
        app = YateApp(target=py, config=config)
        created: list[Any] = []

        def factory(config: Any, root: Any) -> Any:
            return _RcClientShim(created, config, root)

        app.editor.lsp.set_client_factory(factory)
        async with app.run_test(size=(100, 30)) as pilot:
            registered = await wait_until(
                pilot, lambda: app.editor.lsp.is_open(app.editor.session.doc)
            )
            assert registered
            cfg = app.editor.lsp.config_for("py")
            assert cfg is not None
            assert cfg.command == "fake-pyright"
            assert cfg.args == ["--stdio"]
            assert cfg.env == {"FAKE_ENV": "1"}
            assert cfg.root_markers == ["pyproject.toml", ".git"]
            assert cfg.initialization_options == {"diagnostics": True}
            assert cfg.settings == {"python": {"version": "3"}}
            assert cfg.language_id("pyi") == "python"
            assert len(created) == 1
            params = created[0].opened[0]
            assert params["textDocument"]["languageId"] == "python"
            # the disabled builtin registration left no failed client
            state = app.editor.lsp.state_for_doc(app.editor.session.doc)
            assert state is not None
            assert state.value == "ready"

    asyncio.run(scenario())


# ------------------------------------------------------------- fake LSP client


class _RcClientShim:
    """Module-level fake client built by the rc-server tests' factory."""

    def __init__(self, created: list[Any], config: Any, root: Any) -> None:
        from yate.editor_lsp import ServerState
        self.config = config
        self.root_path = root
        self.state = ServerState.READY
        self.error = ""
        self.trigger_characters: tuple[str, ...] = ()
        self.opened: list[Any] = []
        created.append(self)

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        from yate.editor_lsp import ServerState
        self.state = ServerState.STOPPED

    async def notify(self, method: str, params: Any) -> None:
        if method == "textDocument/didOpen":
            self.opened.append(params)

    async def request(self, method: str, params: Any) -> Any:
        return None

    async def start_request(self, method: str, params: Any) -> Any:
        future: asyncio.Future[Any] = asyncio.get_running_loop().create_future()
        future.set_result(None)
        return 1, future

    async def send_cancel(self, request_id: int) -> None:
        return None


# --------------------------------------------------------------------- fake PTY


class _FakePty:
    """In-memory PTY substitute used by the terminal UI tests."""

    instances: list[_FakePty] = []

    def __init__(self, argv: list[str], cwd: Any, cols: int, rows: int) -> None:
        self.argv = list(argv)
        self.cwd = cwd
        self.cols, self.rows = cols, rows
        self.sent: list[bytes] = []
        self.started = False
        self.exited = False
        self._on_output: Callable[[bytes], None] | None = None
        self._on_exit: Callable[[int | None], None] | None = None
        _FakePty.instances.append(self)

    async def start(
        self, on_output: Callable[[bytes], None],
        on_exit: Callable[[int | None], None],
    ) -> None:
        self.started = True
        self._on_output = on_output
        self._on_exit = on_exit

    def write(self, data: bytes) -> None:
        self.sent.append(data)

    def resize(self, cols: int, rows: int) -> None:
        self.cols, self.rows = cols, rows

    def exit(self, code: int = 0) -> None:
        if not self.exited and self._on_exit is not None:
            self.exited = True
            self._on_exit(code)

    def emit_output(self, data: bytes) -> None:
        if self._on_output is not None:
            self._on_output(data)

    def terminate(self) -> None:
        self.exit(0)

    async def wait_closed(self) -> None:
        for _ in range(200):
            if self.exited:
                return
            await asyncio.sleep(0.01)


# ----------------------------------------------------------------- terminal UI


async def _press_toggle(pilot: Any) -> None:
    # Textual key names for grave vary; the app accepts both spellings.
    await pilot.press("ctrl+`")


def test_nul_byte_from_windows_ctrl_grave_matches_toggle() -> None:
    # Windows conhost encodes Ctrl+grave as a NUL byte (ToUnicodeEx
    # yields no character); Textual names that key "ctrl+@", and it
    # must be one of the accepted toggle keys.
    from textual._xterm_parser import XTermParser

    from yate.editor_view.terminal import TOGGLE_KEYS

    names = [
        getattr(m, "key", None) for m in XTermParser().feed("\x00")
    ]
    assert names == ["ctrl+@"]
    assert "ctrl+@" in TOGGLE_KEYS


def test_early_pty_output_survives_first_layout() -> None:
    # Regression: a shell that prints its banner before Textual has
    # laid out the panel used to spawn at the 80x24 fallback size; the
    # first lines were discarded when the viewport shrank on layout.
    class _ImmediatePty(_FakePty):
        @override
        async def start(
            self, on_output: Callable[[bytes], None],
            on_exit: Callable[[int | None], None],
        ) -> None:
            await super().start(on_output, on_exit)
            loop = asyncio.get_running_loop()
            loop.call_soon(
                lambda: on_output(b"YATE_EARLY_BANNER\r\n")
            )

    async def scenario() -> None:
        app = YateApp()
        app.editor.terminal_panel.view_factory = _ImmediatePty
        _FakePty.instances = []
        async with app.run_test(size=(100, 30)) as pilot:
            panel = app.editor.terminal_panel
            assert panel is not None
            await _press_toggle(pilot)

            def banner_visible() -> bool:
                return "YATE_EARLY_BANNER" in "".join(
                    cell.char
                    for row in panel.view.emulator.view_lines(0)
                    for cell in row
                )

            assert await wait_until(pilot, banner_visible)
            proc = _FakePty.instances[0]
            # spawned at the laid-out size, not the 24-row fallback
            assert proc.rows < 24
            assert proc.cols == 100

    asyncio.run(scenario())


def test_ctrl_grave_toggles_focuses_and_forwards() -> None:
    async def scenario() -> None:
        app = YateApp()
        app.editor.terminal_panel.view_factory = _FakePty
        _FakePty.instances = []
        async with app.run_test(size=(100, 30)) as pilot:
            panel = app.editor.terminal_panel
            assert panel is not None
            assert not panel.display

            await _press_toggle(pilot)
            shown = await wait_until(pilot, lambda: panel.view.proc is not None)
            assert shown
            assert panel.display
            assert app.focused is panel.view
            proc = _FakePty.instances[0]
            assert proc.started
            assert proc.argv  # a default shell was resolved
            assert proc.cols == 100
            assert proc.rows >= 8

            # PTY output lands in the emulator and renders
            proc.emit_output(b"YATE_FAKE_OUTPUT\r\n")
            await pilot.pause()
            painted = "".join(
                cell.char
                for row in panel.view.emulator.view_lines(0)
                for cell in row
            )
            assert "YATE_FAKE_OUTPUT" in painted

            # keys typed in the panel are forwarded byte-for-byte
            await pilot.press("l", "s")
            assert b"".join(proc.sent) == b"ls"

            # the dock hugs the bottom, above the status/prompt strip
            bottom = app.query_one("#bottom")
            assert bottom.region.bottom == 30
            assert panel.region.bottom <= bottom.region.y

            # toggle again hides it and returns focus to the editor
            await _press_toggle(pilot)
            await pilot.pause()
            assert not panel.display
            assert app.focused is app.editor.panes.active_view

            # reopening reuses the still-alive shell process
            await _press_toggle(pilot)
            await wait_until(pilot, lambda: app.editor.terminal_panel.is_visible)
            assert panel.display
            assert cast(Any, panel.view).proc is proc

    asyncio.run(scenario())


def test_terminal_focused_ctrl1_returns_focus_to_editor() -> None:
    # N19: the terminal view used to swallow every key once focused;
    # ctrl+1 must hand focus back to the editor without the shell
    # input stream seeing the key (one keypress, one dispatch -- R10).
    async def scenario() -> None:
        app = YateApp()
        app.editor.terminal_panel.view_factory = _FakePty
        _FakePty.instances = []
        async with app.run_test(size=(100, 30)) as pilot:
            panel = app.editor.terminal_panel
            assert panel is not None
            await _press_toggle(pilot)
            shown = await wait_until(pilot, lambda: panel.view.proc is not None)
            assert shown
            assert app.focused is panel.view
            proc = _FakePty.instances[0]
            assert proc.started

            await pilot.press("ctrl+1")
            await pilot.pause()
            assert app.focused is app.editor.panes.active_view
            assert b"".join(proc.sent) == b""

    asyncio.run(scenario())


def test_real_terminal_grave_key_names_toggle_panel() -> None:
    # Ctrl+grave is the NUL byte on Windows conhost / legacy xterm
    # (ToUnicodeEx yields no character), so Textual names it
    # "ctrl+@"; under the kitty keyboard protocol it is named
    # "ctrl+grave_accent". Neither used to match TOGGLE_KEYS, so the
    # panel could not be closed from a real Windows terminal.
    async def scenario() -> None:
        for close_key in ("ctrl+@", "ctrl+grave_accent"):
            app = YateApp()
            app.editor.terminal_panel.view_factory = _FakePty
            _FakePty.instances = []
            async with app.run_test(size=(100, 30)) as pilot:
                panel = app.editor.terminal_panel
                assert panel is not None
                view = panel.view

                await pilot.press("ctrl+`")
                await wait_until(pilot, lambda: view.proc is not None)
                assert panel.display
                assert app.focused is view
                proc = _FakePty.instances[0]

                # the real key name closes the panel while the terminal
                # has focus, and is not forwarded as a NUL byte
                await pilot.press(close_key)
                await pilot.pause()
                assert not panel.display, close_key
                assert b"\x00" not in b"".join(proc.sent)
                assert app.focused is app.editor.panes.active_view

                # same name reopens it now that the editor has focus.
                # ctrl+@ is also the NUL byte Ctrl+Space sends on Windows
                # conhost, so from the editor it means manual completion
                # and must not reopen the terminal -- the unambiguous
                # grave-accent name reopens it instead.
                if close_key == "ctrl+@":
                    await pilot.press("ctrl+@")
                    for _ in range(3):
                        await pilot.pause()
                    assert not panel.display
                    assert not app.editor.terminal_panel.is_visible
                    await pilot.press("ctrl+grave_accent")
                else:
                    await pilot.press(close_key)
                await wait_until(
                    pilot, lambda: app.editor.terminal_panel.is_visible)
                assert panel.display, close_key

    asyncio.run(scenario())


def test_term_command_exit_and_restart() -> None:
    async def scenario() -> None:
        app = YateApp(keymap="vim")  # ":" ex line is vim-only
        app.editor.terminal_panel.view_factory = _FakePty
        _FakePty.instances = []
        async with app.run_test(size=(100, 30)) as pilot:
            panel = app.editor.terminal_panel
            assert panel is not None

            # :term opens the panel
            await pilot.press("colon")
            for ch in "term":
                await pilot.press(ch)
            await pilot.press("enter")
            shown = await wait_until(pilot, lambda: panel.view.proc is not None)
            assert shown
            proc = _FakePty.instances[0]
            assert "running" in panel.header_text()

            # when the shell exits the panel shows the state and a hint
            proc.exit(0)
            await pilot.pause()
            assert panel.view.dead
            assert "exited" in panel.header_text()

            # any keypress revives the shell via the factory
            await pilot.press("a")
            revived = await wait_until(
                pilot,
                lambda: len(_FakePty.instances) == 2
                and cast(Any, panel.view).proc is _FakePty.instances[1]
                and bool(_FakePty.instances[1].started),
            )
            assert revived
            assert len(_FakePty.instances) == 2

            # :termclose hides the panel (invoked directly because focus is
            # inside the terminal and the prompt keys would be sent to the PTY)
            app.editor.run_command("termclose")
            await pilot.pause()
            assert not panel.display

    asyncio.run(scenario())


# ----------------------------------------------------------------- split panes


def test_close_command_closes_active_pane(pane_root: Path) -> None:
    """:close / :cl close the active pane; on the last pane they warn
    instead of quitting (use :q for that)."""

    async def scenario() -> None:
        app = YateApp(target=pane_root / "alpha.txt", keymap="vim")
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            panes = app.editor.panes
            assert panes is not None

            app.editor.run_command("sp")
            assert await wait_until(pilot, lambda: panes.leaf_count == 2)
            app.editor.run_command("close")
            assert await wait_until(pilot, lambda: panes.leaf_count == 1)
            # the last pane is never closed by :close
            app.editor.run_command("cl")
            await pilot.pause()
            assert panes.leaf_count == 1
            assert app.is_running

    asyncio.run(scenario())


def test_pane_regions_stay_visible_after_split(pane_root: Path) -> None:
    """Regression: sizes set before mount resolved against an unknown
    parent, pushing every pane after the first off-screen."""

    async def scenario() -> None:
        app = YateApp(target=pane_root / "alpha.txt", keymap="vim")
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            panes = app.editor.panes
            assert panes is not None

            app.editor.run_command("sp")
            assert await wait_until(pilot, lambda: panes.leaf_count == 2)
            app.editor.run_command("vs")
            assert await wait_until(pilot, lambda: panes.leaf_count == 3)
            await pilot.pause()
            host = panes.host
            assert host is not None
            host_region = host.region
            views = panes.all_views()
            for view in views:
                region = view.region
                assert region.width > 5 and region.height > 2, (
                    f"pane collapsed: {region}"
                )
                assert host_region.contains_region(region), (
                    f"pane outside host: {region} vs {host_region}"
                )
            # dividers: after :sp the top pane has a bottom border; after
            # :vs the bottom-left pane has a right border; last panes none
            assert views[0].styles.border_bottom[0] not in ("", "none")
            assert views[0].styles.border_right[0] in ("", "none")
            assert views[1].styles.border_right[0] not in ("", "none")
            assert views[1].styles.border_bottom[0] in ("", "none")
            assert views[2].styles.border_bottom[0] in ("", "none")
            assert views[2].styles.border_right[0] in ("", "none")

    asyncio.run(scenario())


def test_split_independent_cursors_and_navigation(pane_root: Path) -> None:
    async def scenario() -> None:
        app = YateApp(target=pane_root / "alpha.txt", keymap="vim")
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            panes = app.editor.panes
            assert panes is not None

            app.editor.run_command("sp")
            assert await wait_until(pilot, lambda: panes.leaf_count == 2)
            root = panes.root
            assert isinstance(root, PaneSplit)
            assert root.axis == "horizontal"
            assert len(app.query(EditorView)) == 2

            # the new (bottom) pane is active: move its cursor to row 1
            await pilot.press("j")
            await pilot.pause()
            assert app.editor.session.buffer.cursor == (1, 0)

            # ctrl+w k jumps to the top pane: its cursor stayed at row 0
            await pilot.press("ctrl+w", "k")
            await pilot.pause()
            assert app.editor.session.buffer.cursor == (0, 0)
            # ctrl+w j returns to the bottom pane and its row-1 cursor
            await pilot.press("ctrl+w", "j")
            await pilot.pause()
            assert app.editor.session.buffer.cursor == (1, 0)

            # ctrl+w ctrl+w from the last editor pane wraps to the explorer,
            # then from the explorer back to the active editor pane
            await pilot.press("ctrl+w", "ctrl+w")
            await pilot.pause()
            assert app.focused is app.editor.explorer_tree
            assert app.editor.session.buffer.cursor == (1, 0)
            await pilot.press("ctrl+w", "ctrl+w")
            await pilot.pause()
            assert app.focused is app.editor.panes.active_view
            assert app.editor.session.buffer.cursor == (1, 0)

    asyncio.run(scenario())


def test_vsplit_with_file_and_only(pane_root: Path) -> None:
    async def scenario() -> None:
        app = YateApp(target=pane_root / "alpha.txt", keymap="vim")
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            panes = app.editor.panes
            assert panes is not None

            # relative path resolves against the current file's directory
            app.editor.run_command("vs bravo.txt")
            opened = await wait_until(
                pilot,
                lambda: panes.leaf_count == 2
                and app.editor.session.doc.path is not None
                and app.editor.session.doc.path.name == "bravo.txt",
            )
            assert opened
            root = panes.root
            assert isinstance(root, PaneSplit)
            assert root.axis == "vertical"
            assert app.editor.session.buffer.lines[0] == "bravo one"
            assert len(app.query(EditorView)) == 2

            # :sp on the bravo pane clones it -> 3 panes
            app.editor.run_command("split")
            assert await wait_until(pilot, lambda: panes.leaf_count == 3)
            # :only collapses back to the active (bravo) pane
            app.editor.run_command("only")
            assert await wait_until(pilot, lambda: panes.leaf_count == 1)
            assert len(app.query(EditorView)) == 1
            current = app.editor.session.doc
            assert current.path is not None
            assert current.path.name == "bravo.txt"

    asyncio.run(scenario())


def test_chord_split_resize_close_and_q(pane_root: Path) -> None:
    async def scenario() -> None:
        app = YateApp(target=pane_root / "alpha.txt", keymap="vim")
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            panes = app.editor.panes
            assert panes is not None

            await pilot.press("ctrl+w", "s")
            assert await wait_until(pilot, lambda: panes.leaf_count == 2)
            root = panes.root
            assert isinstance(root, PaneSplit)
            assert root.axis == "horizontal"

            # ctrl+w - shrinks the active (new) pane; ctrl+w = equalizes
            await pilot.press("ctrl+w", "minus")
            await pilot.pause()
            assert abs(root.sizes[1] - 0.42) <= 0.005
            await pilot.press("ctrl+w", "equals_sign")
            await pilot.pause()
            assert root.sizes == [0.5, 0.5]

            # a dirty document does not block closing a pane (the document
            # stays open as a hidden buffer)
            await pilot.press("i", "x", "escape")
            await pilot.pause()
            assert app.editor.session.doc.modified
            await pilot.press("ctrl+w", "q")
            assert await wait_until(pilot, lambda: panes.leaf_count == 1)
            assert app.is_running

            # single pane: :q is blocked by unsaved changes, :q! exits
            app.editor.run_command("q")
            await pilot.pause()
            assert app.is_running
            app.editor.run_command("q!")
            for _ in range(5):
                with contextlib.suppress(Exception):
                    await pilot.pause()
                if not app.is_running:
                    break
            # let any worker scheduled by the final shutdown render start
            # (so its coroutine is awaited rather than GC'd at loop close)
            for _ in range(3):
                await asyncio.sleep(0)
            assert not app.is_running

    asyncio.run(scenario())


def test_q_always_quits_whole_editor_with_panes(pane_root: Path) -> None:
    """:q must quit yate even when several panes are open -- it never
    just closes the active pane (use :close / :cl / Ctrl+W q for that).
    A dirty buffer blocks it like any other quit attempt."""

    async def scenario() -> None:
        app = YateApp(target=pane_root / "alpha.txt", keymap="vim")
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            panes = app.editor.panes
            assert panes is not None

            await pilot.press("ctrl+w", "s")
            assert await wait_until(pilot, lambda: panes.leaf_count == 2)
            # make the buffer dirty: :q is a whole-editor quit attempt and
            # the unsaved-changes guard blocks it; a pane close would not
            await pilot.press("i", "y", "escape")
            await pilot.pause()
            assert app.editor.session.doc.modified

            app.editor.run_command("q")
            await pilot.pause()
            # blocked: unsaved changes guard, and no pane was closed
            assert app.is_running
            assert panes.leaf_count == 2

            app.editor.run_command("quit")
            await pilot.pause()
            # :quit is a plain alias of :q and is blocked the same way
            assert app.is_running
            assert panes.leaf_count == 2

            app.editor.run_command("q!")  # discard and quit the whole editor
            for _ in range(5):
                with contextlib.suppress(Exception):
                    await pilot.pause()
                if not app.is_running:
                    break
            for _ in range(3):
                await asyncio.sleep(0)
            assert not app.is_running

    asyncio.run(scenario())


def test_q_quits_immediately_with_clean_panes(pane_root: Path) -> None:
    """With no unsaved changes :q exits yate straight away even with
    several panes open (it does not close them one by one)."""

    async def scenario() -> None:
        app = YateApp(target=pane_root / "alpha.txt", keymap="vim")
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            panes = app.editor.panes
            assert panes is not None

            await pilot.press("ctrl+w", "s")
            assert await wait_until(pilot, lambda: panes.leaf_count == 2)
            app.editor.run_command("q")
            for _ in range(5):
                with contextlib.suppress(Exception):
                    await pilot.pause()
                if not app.is_running:
                    break
            for _ in range(3):
                await asyncio.sleep(0)
            assert not app.is_running

    asyncio.run(scenario())


# --------------------------------------------------------------- :wq guarding


async def _wait_quit(app: YateApp, pilot: Any) -> None:
    """Pump the pilot until *app* exits (mirrors the :q tests above)."""
    for _ in range(5):
        with contextlib.suppress(Exception):
            await pilot.pause()
        if not app.is_running:
            break
    for _ in range(3):
        await asyncio.sleep(0)


def test_wq_saves_and_quits_when_save_succeeds(tmp_path: Path) -> None:
    """Happy path: :wq writes the dirty buffer to disk, clears the modified
    flag and then calls quit() without force (other-tab dirty checks still
    apply inside quit()).

    quit() is recorded instead of letting the app tear down: a real
    save-and-quit orphans the fire-and-forget LSP didSave worker (its
    coroutine is GC'd unawaited -- pre-existing app behavior that only
    shows up once the loop is gone). Keeping the app alive lets the
    worker drain while the recorder still proves the quit decision.
    """

    async def scenario() -> None:
        target = tmp_path / "notes.txt"
        app = YateApp(target=target, keymap="vim")
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            # dirty the buffer
            await pilot.press("i", "h", "i", "escape")
            await pilot.pause()
            assert app.editor.session.doc.modified

            quit_calls: list[bool] = []

            def _record_quit(force: bool = False) -> None:
                quit_calls.append(force)

            cast(Any, app.editor).quit = _record_quit
            app.editor.run_command("wq")
            await pilot.pause()
            await pilot.pause()

            assert quit_calls == [False]
            assert not app.editor.session.doc.modified
            assert target.read_text(encoding="utf-8") == "hi"

    asyncio.run(scenario())


def test_wq_does_not_quit_when_save_fails(tmp_path: Path) -> None:
    """Data-loss regression: when the write raises (here the path points at a
    directory), :wq must NOT force-quit -- the unsaved work stays in memory."""

    async def scenario() -> None:
        target = tmp_path / "notes.txt"
        app = YateApp(target=target, keymap="vim")
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            await pilot.press("i", "k", "e", "e", "p", "escape")
            await pilot.pause()
            assert app.editor.session.doc.modified

            # Aim the document at a directory so write_text() raises OSError.
            blocker = tmp_path / "blocker"
            blocker.mkdir()
            app.editor.session.doc.path = blocker

            app.editor.run_command("wq")
            await pilot.pause()

            # Still running: the failed save aborted the quit.
            assert app.is_running
            assert app.editor.session.doc.modified
            assert app.editor.session.doc.buffer.get_text() == "keep"
            assert "save failed" in _message_text(app)

    asyncio.run(scenario())


def test_wq_does_not_quit_for_unnamed_modified_buffer() -> None:
    """An unnamed (no path) dirty buffer routes :wq to the save-as prompt;
    the editor must stay open rather than force-quit and lose the text."""

    async def scenario() -> None:
        app = YateApp(keymap="vim")  # untitled scratch buffer
        async with app.run_test(size=(100, 30)) as pilot:
            prompt_bar = app.editor.prompt_bar
            assert prompt_bar is not None
            await pilot.press("i", "w", "o", "r", "k", "escape")
            await pilot.pause()
            assert app.editor.session.doc.path is None
            assert app.editor.session.doc.modified

            app.editor.run_command("wq")
            await pilot.pause()

            assert app.is_running
            assert app.editor.session.doc.modified
            assert app.editor.session.doc.buffer.get_text() == "work"
            # the save-as prompt was opened instead of quitting
            assert prompt_bar.active_mode == "save"

            # cancelling the prompt (empty submit) still must not quit
            await pilot.press("enter")
            await pilot.pause()
            assert app.is_running
            assert app.editor.session.doc.modified
            assert app.editor.session.doc.buffer.get_text() == "work"
            assert "save cancelled" in _message_text(app)

    asyncio.run(scenario())


def test_wq_quits_for_clean_unnamed_buffer() -> None:
    """A pristine unnamed buffer (welcome page / :enew) has nothing to lose:
    :wq exits straight away, matching the pre-guard behavior."""

    async def scenario() -> None:
        app = YateApp(keymap="vim")
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            assert app.editor.session.doc.path is None
            assert not app.editor.session.doc.modified

            app.editor.run_command("wq")
            await _wait_quit(app, pilot)

            assert not app.is_running

    asyncio.run(scenario())


def test_wq_quits_for_clean_named_buffer(tmp_path: Path) -> None:
    """No unsaved changes: :wq re-writes the (unchanged) file and quits.

    quit() is recorded rather than executed for the same LSP-worker reason
    as test_wq_saves_and_quits_when_save_succeeds above.
    """

    async def scenario() -> None:
        target = tmp_path / "clean.txt"
        target.write_text("already saved", encoding="utf-8")
        app = YateApp(target=target, keymap="vim")
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            assert not app.editor.session.doc.modified

            quit_calls: list[bool] = []

            def _record_quit(force: bool = False) -> None:
                quit_calls.append(force)

            cast(Any, app.editor).quit = _record_quit
            app.editor.run_command("wq")
            await pilot.pause()
            await pilot.pause()

            assert quit_calls == [False]
            assert target.read_text(encoding="utf-8") == "already saved"

    asyncio.run(scenario())


def test_wq_does_not_quit_when_other_tab_is_dirty(tmp_path: Path) -> None:
    """Current doc is saved successfully, but another tab has unsaved
    changes. :wq must call quit() *without* force so the internal
    any(dirty) guard blocks the exit (vim E37 semantics) instead of
    silently discarding the other tab's work."""

    async def scenario() -> None:
        saved = tmp_path / "saved.txt"
        other = tmp_path / "other.txt"
        saved.write_text("already", encoding="utf-8")
        other.write_text("pristine", encoding="utf-8")

        app = YateApp(target=saved, keymap="vim")
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            first = app.editor.session.docs[0]

            # open the second tab and dirty it
            app.editor.open_path(other)
            await pilot.pause()
            assert len(app.editor.session.docs) == 2
            assert app.editor.session.doc.path == other
            await pilot.press("i", "e", "d", "i", "t", "escape")
            await pilot.pause()
            assert app.editor.session.doc.modified

            # switch back to saved.txt (the first tab, clean)
            app.editor.activate_doc(first)
            assert app.editor.session.doc is first
            assert not app.editor.session.doc.modified

            # Wrap (don't replace) quit: record the force flag while still
            # running the real multi-tab dirty guard.
            quit_calls: list[bool] = []
            original_quit = app.editor.quit

            def _record_quit(force: bool = False) -> None:
                quit_calls.append(force)
                original_quit(force=force)

            cast(Any, app.editor).quit = _record_quit
            app.editor.run_command("wq")
            await pilot.pause()
            await pilot.pause()

            assert quit_calls == [False], f"expected non-force quit, got {quit_calls}"
            assert app.is_running
            # the dirty tab is untouched
            assert app.editor.session.docs[1].modified
            assert other.read_text(encoding="utf-8") == "pristine"
            assert "unsaved changes" in _message_text(app)

    asyncio.run(scenario())


def test_wq_does_not_crash_on_unicode_encode_error(tmp_path: Path) -> None:
    """When the file's detected encoding cannot represent the buffer
    content (cp1252 + emoji), :wq must surface a friendly error message
    and keep the editor alive -- NOT crash via Textual's exception
    handler and lose the in-memory buffers."""

    async def scenario() -> None:
        target = tmp_path / "cp1252.txt"
        # Bytes that are valid cp1252 but not UTF-8, so encoding sniffing
        # (utf-8 -> locale -> cp1252) lands on cp1252 on every platform.
        target.write_bytes("caf\xe9".encode("cp1252"))  # "café" in cp1252

        app = YateApp(target=target, keymap="vim")
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            assert app.editor.session.doc.encoding.lower().startswith(("cp1252", "windows-1252"))

            # Append an emoji -- cp1252 cannot encode it. Textual's Pilot
            # has no paste() helper, so insert straight into the buffer.
            app.editor.session.doc.buffer.move_doc_end()
            app.editor.session.doc.buffer.insert_text("\U0001f600")
            await pilot.pause()
            assert app.editor.session.doc.modified

            app.editor.run_command("wq")
            await pilot.pause()

            # save failed -> guard aborts the quit; editor stays alive and
            # the full unsaved content survives in memory, so the user can
            # still recover it via :saveas with a UTF-8-capable path. The
            # save itself is atomic (sibling temp file + os.replace, with
            # encoding done before anything is written), so the on-disk
            # bytes survive the failed write untouched.
            assert app.is_running
            assert app.editor.session.doc.modified
            assert "save failed" in _message_text(app)
            assert app.editor.session.doc.buffer.get_text() == "caf\u00e9\U0001f600"
            assert target.read_bytes() == "caf\xe9".encode("cp1252")

    asyncio.run(scenario())


def test_vertical_chord_and_geometry_navigation(pane_root: Path) -> None:
    async def scenario() -> None:
        app = YateApp(target=pane_root / "alpha.txt", keymap="vim")
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            panes = app.editor.panes
            assert panes is not None

            await pilot.press("ctrl+w", "v")
            assert await wait_until(pilot, lambda: panes.leaf_count == 2)
            root = panes.root
            assert isinstance(root, PaneSplit)
            assert root.axis == "vertical"
            ordered = pane_leaves(root)
            left_view = panes.views[ordered[0].id]

            # the new pane is the right one; h moves geometrically to the
            # editor pane on the left first ...
            await pilot.press("ctrl+w", "h")
            await pilot.pause()
            assert app.focused is left_view
            # ... and only then, with no editor further left, to the explorer
            await pilot.press("ctrl+w", "h")
            await pilot.pause()
            assert app.focused is app.editor.explorer_tree
            # l from the explorer returns to the active (right) editor pane
            await pilot.press("ctrl+w", "l")
            await pilot.pause()
            assert app.focused is app.editor.panes.active_view

    asyncio.run(scenario())


def test_bd_rebinds_every_pane_showing_the_document(pane_root: Path) -> None:
    async def scenario() -> None:
        app = YateApp(target=pane_root / "alpha.txt", keymap="vim")
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            panes = app.editor.panes
            assert panes is not None

            app.editor.run_command("sp")
            assert await wait_until(pilot, lambda: panes.leaf_count == 2)
            # the new pane opens bravo; the top pane keeps alpha
            app.editor.run_command("e bravo.txt")
            assert await wait_until(
                pilot,
                lambda: app.editor.session.doc.path is not None
                and app.editor.session.doc.path.name == "bravo.txt",
            )
            app.editor.run_command("bd")
            await pilot.pause()
            assert len(app.editor.session.docs) == 1
            for leaf in pane_leaves(panes.root):
                path = leaf.doc.path
                assert path is not None
                assert path.name == "alpha.txt"
            active_path = app.editor.session.doc.path
            assert active_path is not None
            assert active_path.name == "alpha.txt"

    asyncio.run(scenario())


# --------------------------------------------------------- wide char rendering


def test_cjk_line_renders_without_extra_gaps(tmp_path: Path) -> None:
    from rich.cells import cell_len

    async def scenario() -> None:
        path = tmp_path / "zh.txt"
        path.write_text("配置顺序 abc 加载\n", encoding="utf-8")
        app = YateApp(target=path)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            view = app.editor.panes.active_view
            assert view is not None
            strip = view.render_line(0)
            segs = getattr(strip, "_segments", None)
            assert segs is not None
            texts = [s.text for s in segs]
            joined = "".join(texts)
            # glyphs stay adjacent -- no inserted spaces between them
            assert "配置顺序" in joined
            assert "加载" in joined
            # the strip exactly fills the editor width (glyph 2 cells
            # plus placeholder 0, not glyph 2 plus an extra blank)
            assert sum(cell_len(t) for t in texts) == view.size.width

    asyncio.run(scenario())


def test_horizontal_scroll_clips_wide_glyph_with_blank(tmp_path: Path) -> None:
    from rich.cells import cell_len

    async def scenario() -> None:
        path = tmp_path / "zh.txt"
        path.write_text("配置x\n", encoding="utf-8")
        app = YateApp(target=path)
        async with app.run_test(size=(60, 20)) as pilot:
            await pilot.pause()
            view = app.editor.panes.active_view
            assert view is not None
            view.scroll_col = 1  # second cell of the first glyph
            await pilot.pause()
            strip = view.render_line(0)
            segs = getattr(strip, "_segments", None)
            assert segs is not None
            joined = "".join(s.text for s in segs)
            # the clipped half is replaced by a blank (first glyph
            # gone), the following glyph is not pulled left; strip
            # still fills the width
            assert "配" not in joined
            assert "置" in joined
            assert sum(cell_len(s.text) for s in segs) == view.size.width

    asyncio.run(scenario())


# ----------------------------------------------------------------- ctrl+space


def test_nul_byte_opens_completion_not_terminal(tmp_path: Path) -> None:
    async def scenario() -> None:
        (tmp_path / "a.txt").write_text("alpha\nalpha\n", encoding="utf-8")
        app = YateApp(target=tmp_path / "a.txt", keymap="vim")
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            popup = app.editor.completion_popup
            assert popup is not None
            # insert a prefix so the manual completion has candidates
            await pilot.press("i", "a", "l")
            await pilot.pause()
            await pilot.press("ctrl+@")  # NUL: Ctrl+Space on conhost
            shown = await wait_until(pilot, lambda: popup.is_open)
            assert shown
            assert not app.editor.terminal_panel.is_visible

    asyncio.run(scenario())


# ---------------------------------------------------------------- help overlay


def test_help_lists_terminal_key_and_commands() -> None:
    from yate.editor_view.modals import HelpScreen

    async def scenario() -> None:
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.press("f1")
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, HelpScreen)
            body = cast(str, cast(Any, screen)._body().plain)
            assert "GLOBAL KEYS" in body
            assert "ctrl+`" in body
            assert "integrated terminal" in body
            # the terminal commands are registered and listed with : prefix
            assert ":term" in body
            assert ":termclose" in body

    asyncio.run(scenario())


# ------------------------------------------------------ explorer filter smoke


def test_h_toggles_hidden_files_in_tree(tmp_path: Path) -> None:
    async def scenario() -> None:
        root = tmp_path
        (root / ".hidden.txt").write_text("h\n", encoding="utf-8")
        (root / "a.txt").write_text("a\n", encoding="utf-8")
        app = YateApp(target=root)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            tree = app.editor.explorer_tree
            assert tree is not None

            def shown() -> list[str]:
                return [
                    Path(c.data).name
                    for c in tree.root.children
                    if c.data is not None
                ]

            assert ".hidden.txt" not in shown()
            # hide the by-default-shown tree, then re-show it (focused)
            app.editor.run_command("explorer")
            for _ in range(4):
                await pilot.pause()
            app.editor.run_command("explorer")
            for _ in range(6):
                await pilot.pause()
            assert app.focused is tree
            await pilot.press("H")
            for _ in range(4):
                await pilot.pause()
            assert app.editor.workspace.show_hidden
            assert ".hidden.txt" in shown()
            await pilot.press("H")
            for _ in range(4):
                await pilot.pause()
            assert not app.editor.workspace.show_hidden
            assert ".hidden.txt" not in shown()

    asyncio.run(scenario())


def test_set_show_hidden_option_roundtrip(tmp_path: Path) -> None:
    async def scenario() -> None:
        root = tmp_path
        (root / ".dot").write_text("d\n", encoding="utf-8")
        app = YateApp(target=root)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            app.editor.run_command("set show_hidden=on")
            await pilot.pause()
            assert app.editor.workspace.show_hidden
            tree = app.editor.explorer_tree
            assert tree is not None
            names = [
                Path(c.data).name
                for c in tree.root.children
                if c.data is not None
            ]
            assert ".dot" in names
            app.editor.run_command("set show_hidden=off")
            await pilot.pause()
            assert not app.editor.workspace.show_hidden

    asyncio.run(scenario())


def test_explorer_toggle_focuses_tree(tmp_path: Path) -> None:
    """Regression: re-opening the explorer must hand focus to the tree so
    keyboard navigation works without a mouse click (the tree is shown
    by default at startup, so toggle once to hide, once to re-show)."""

    async def scenario() -> None:
        root = tmp_path
        (root / "a.txt").write_text("a\n", encoding="utf-8")
        (root / "b.txt").write_text("b\n", encoding="utf-8")
        app = YateApp(target=root)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            tree = app.editor.explorer_tree
            assert tree is not None
            app.editor.run_command("explorer")  # hide (shown by default)
            for _ in range(4):
                await pilot.pause()
            assert not tree.display
            app.editor.run_command("explorer")  # re-show
            for _ in range(6):
                await pilot.pause()
            assert tree.display
            assert app.focused is tree
            # keyboard navigation actually works (j moves the cursor)
            line = tree.cursor_line
            await pilot.press("j")
            await pilot.pause()
            assert tree.cursor_line == line + 1

    asyncio.run(scenario())


def test_palette_entries_exclude_palette_command() -> None:
    """Regression: the palette must not list the palette command itself
    (opening it from inside would be a no-op recursion)."""
    from yate.editor_view.palette import PaletteScreen

    async def scenario() -> None:
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            screen = PaletteScreen(
                "commands",
                workspace=app.editor.workspace,
                commands=app.editor.commands,
                actions=app.editor.actions,
                open_path=app.editor.open_path_later,
                focus_editor=app.editor.focus_editor,
                execute_action=app.editor.execute_action,
                run_command=app.editor.run_command,
                refresh=app.editor.refresh_ui,
            )
            screen._build_command_entries()
            kinds = {name for name, _d, (_k, _n) in screen._entries}
            assert "quit" in kinds  # sanity: commands are listed
            assert "palette" not in kinds

    asyncio.run(scenario())


def test_tree_helper_line_of_and_find_node(tmp_path: Path) -> None:
    # Workspace resolves its root, which on Windows also expands 8.3
    # short names (GitHub runners expose TEMP as C:\Users\RUNNER~1).
    # Resolve here too or every node-path comparison below fails.
    async def scenario() -> None:
        root = tmp_path.resolve()
        sub = root / "sub"
        sub.mkdir()
        (sub / "inner.txt").write_text("i\n", encoding="utf-8")
        (root / "top.txt").write_text("t\n", encoding="utf-8")
        app = YateApp(target=root)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            tree = app.editor.explorer_tree
            assert tree is not None
            top = sub.parent / "top.txt"
            # collapsed: sub's children are not visible
            assert tree._line_of(sub / "inner.txt") is None
            node = tree._find_node(tree.root, sub / "inner.txt")
            assert node is None
            # expand sub via select (toggle) and re-check
            snode = tree._find_node(tree.root, sub)
            assert snode is not None
            tree.select_node(snode)
            for _ in range(4):
                await pilot.pause()
            assert tree._find_node(tree.root, sub / "inner.txt") is not None
            # rows: 0=root, 1=sub, 2=inner.txt, 3=top.txt
            assert tree._line_of(sub / "inner.txt") == 2
            assert tree._line_of(top) == 3
            assert tree._line_of(root / "missing.txt") is None

    asyncio.run(scenario())


# ------------------------------------------- SP3 render-path regression guards


def test_render_line_queries_diagnostics_once_per_row(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """S12: render_line looks up the row's diagnostics exactly once.

    The gutter marks and the underline pass share one ``diagnostics_on_line``
    lookup per rendered row; the pre-fix code scanned the diagnostics twice
    for every row.
    """

    async def scenario() -> None:
        target = tmp_path / "diag.py"
        target.write_text(
            "x = 1\ny = 2\nz = 3\nw = 4\nv = 5\n", encoding="utf-8"
        )
        app = YateApp(target=target)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            from yate.editor_core.document import Document
            from yate.editor_lsp import Diagnostic, protocol

            app.editor.lsp.handle_notification(
                "textDocument/publishDiagnostics",
                {
                    "uri": protocol.path_to_uri(target.resolve()),
                    "diagnostics": [
                        {
                            "range": {
                                "start": {"line": 0, "character": 0},
                                "end": {"line": 0, "character": 1},
                            },
                            "severity": 1,
                            "message": "boom",
                            "source": "test",
                        },
                        {
                            "range": {
                                "start": {"line": 2, "character": 0},
                                "end": {"line": 2, "character": 1},
                            },
                            "severity": 2,
                            "message": "meh",
                            "source": "test",
                        },
                    ],
                },
            )
            await pilot.pause()
            editor = app.editor.panes.active_view
            assert editor is not None
            lsp = app.editor.lsp
            calls: list[int] = []
            real = lsp.diagnostics_on_line

            def counting(doc: Document, row: int) -> list[Diagnostic]:
                calls.append(row)
                return real(doc, row)

            monkeypatch.setattr(lsp, "diagnostics_on_line", counting)

            # exactly one lookup per rendered row, in row order
            for row in range(5):
                editor.render_line(row)
            assert calls == [0, 1, 2, 3, 4]

    asyncio.run(scenario())


def test_welcome_rows_cached_per_theme_and_keymap() -> None:
    """S13: welcome rows are reused until the theme or keymap changes."""

    async def scenario() -> None:
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            editor = app.editor.panes.active_view
            assert editor is not None
            from yate.editor_view import theme

            # same (theme, keymap) cache key: the same row list object
            first = editor._welcome_lines(theme.active(), vim_keys=False)
            assert editor._welcome_lines(theme.active(), vim_keys=False) is first

            # keymap switch changes the cache key -> rows rebuilt
            await pilot.press("ctrl+/")
            assert editor.keymaps.name == "vim"
            vim_rows = editor._welcome_lines(theme.active(), vim_keys=True)
            assert vim_rows is not first
            assert editor._welcome_lines(theme.active(), vim_keys=True) is vim_rows

            # theme switch changes the key too -> rebuilt under latte
            app.editor.set_theme("latte")
            await pilot.pause()
            latte_rows = editor._welcome_lines(theme.active(), vim_keys=True)
            assert latte_rows is not vim_rows
            theme.set_theme("mocha")  # restore default for other tests

    asyncio.run(scenario())


def test_discarded_highlight_pass_reschedules_immediately(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """S14: a stale (discarded) tokenize pass re-arms without debouncing."""

    async def scenario() -> None:
        target = tmp_path / "script.py"
        target.write_text("def foo():\n    return 42\n", encoding="utf-8")
        app = YateApp(target=target)
        async with app.run_test(size=(100, 30)) as pilot:
            editor = app.editor.panes.active_view
            assert editor is not None
            assert await wait_until(
                pilot, lambda: editor.highlight_probe().tokens is not None,
                timeout=5.0,
            )

            import threading

            import yate.editor_view.editor as editor_module
            from yate.editor_syntax.tokens import Token

            real_tokenize = editor_module.tokenize_document
            started = threading.Event()
            gate = threading.Event()

            def slow_tokenize(
                lines: list[str], filetype: str
            ) -> list[list[Token]]:
                # hold the in-flight pass until the test has bumped the
                # buffer version, making the pending result stale
                started.set()
                gate.wait(timeout=5.0)
                return real_tokenize(lines, filetype)

            monkeypatch.setattr(
                editor_module, "tokenize_document", slow_tokenize
            )
            delays: list[float] = []
            real_schedule = editor._schedule_highlight

            def tracking_schedule(delay: float) -> None:
                delays.append(delay)
                real_schedule(delay)

            monkeypatch.setattr(
                editor, "_schedule_highlight", tracking_schedule
            )

            # start a pass and let it block inside the tokenizer thread
            editor._schedule_highlight(0.0)
            assert await wait_until(pilot, started.is_set, timeout=5.0)
            delays.clear()

            # edit while the pass is in flight: its result is discarded and
            # the replacement pass must start immediately (delay 0.0) instead
            # of costing another debounce window on top
            app.editor.session.buffer.insert_text("x")
            gate.set()
            new_version = app.editor.session.buffer.content_version
            assert await wait_until(
                pilot,
                lambda: editor.highlight_probe().tokens is not None
                and editor.highlight_probe().version == new_version
                and editor.highlight_probe().scheduled_key is None,
                timeout=5.0,
            )
            assert delays and delays[0] == 0.0

    asyncio.run(scenario())


def test_render_line_computes_cursor_anchor_once_per_row(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """S15: one cursor/anchor lookup per rendered row (was three)."""

    async def scenario() -> None:
        target = tmp_path / "script.py"
        target.write_text("def foo():\n    return 42\n", encoding="utf-8")
        app = YateApp(target=target)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            editor = app.editor.panes.active_view
            assert editor is not None

            from yate.editor_core.buffer import Pos

            calls = 0
            real = editor._cursor_anchor

            def counting() -> tuple[Pos, Pos | None]:
                nonlocal calls
                calls += 1
                return real()

            monkeypatch.setattr(editor, "_cursor_anchor", counting)

            # the pair is computed once per row and shared by the cursor
            # paint, the selection and the style-range passes
            editor.render_line(0)
            assert calls == 1
            editor.render_line(1)
            assert calls == 2

    asyncio.run(scenario())


def test_doc_search_debounce_merges_rapid_typing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """S40: rapid doc-search typing merges into one debounced rebuild."""

    async def scenario() -> None:
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            await pilot.press("f8")
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, MarkdownDocScreen)
            from textual.widgets import Static

            loading = screen.query_one("#doc-loading", Static)
            assert await wait_until(
                pilot, lambda: not loading.display, timeout=15.0
            )
            # freeze the trailing window before touching the input: with a
            # 30s debounce the timer cannot fire mid-test no matter how the
            # runner schedules the presses (a loaded CI box once let the
            # real 0.12s window elapse between keystrokes and recorded an
            # intermediate rebuild, ['ke', 'key'])
            monkeypatch.setattr(screen, "_SEARCH_DEBOUNCE_S", 30.0)
            await pilot.press("slash")
            await pilot.pause()

            calls: list[str] = []
            real_search = screen._run_search

            def counting(query: str) -> None:
                calls.append(query)
                real_search(query)

            monkeypatch.setattr(screen, "_run_search", counting)

            # four keystrokes: zero rebuilds while typing (the merge), then
            # one rebuild carrying the final query when the window callback
            # runs
            keys = ("t", "h", "e", "m")
            await pilot.press(*keys)
            await pilot.pause()
            assert calls == []
            # the trailing window really is armed and pending (the manual
            # flush below only covers the callback body, not the arming)
            assert screen._search_timer is not None
            screen._flush_search()
            assert calls == ["".join(keys)]

    asyncio.run(scenario())


def test_doc_search_enter_flushes_pending_query_immediately(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """S40: submitting runs the pending query without waiting the window."""

    async def scenario() -> None:
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            await pilot.press("f8")
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, MarkdownDocScreen)
            from textual.widgets import Static

            loading = screen.query_one("#doc-loading", Static)
            assert await wait_until(
                pilot, lambda: not loading.display, timeout=15.0
            )
            # freeze the trailing window before touching the input: with a
            # 30s debounce no timer can fire, so the only way a search can
            # run is the enter flush itself
            monkeypatch.setattr(screen, "_SEARCH_DEBOUNCE_S", 30.0)
            await pilot.press("slash")
            await pilot.pause()

            calls: list[str] = []
            real_search = screen._run_search

            def counting(query: str) -> None:
                calls.append(query)
                real_search(query)

            monkeypatch.setattr(screen, "_run_search", counting)

            # type, then submit: enter must flush the pending query right
            # away instead of waiting the (frozen) window
            await pilot.press("k", "e", "y")
            await pilot.press("enter")
            await pilot.pause()
            assert calls == ["key"]

    asyncio.run(scenario())


# ---------------------------------------------- action_quit registry routing


def test_ctrl_q_routes_through_the_registered_quit_action(tmp_path: Path) -> None:
    """N18 (option 1): ctrl+q dispatches the registered ``quit`` action.

    ``action_quit`` used to call ``Editor.quit`` directly, leaving the
    registered ``quit`` action reachable only via ``execute_action``
    (palette / extensions / smoke's quit_action_dispatch). Re-registering
    ``quit`` with a spy proves the key path now goes through the registry.
    """

    async def scenario() -> None:
        target = tmp_path / "clean.txt"
        target.write_text("clean\n", encoding="utf-8")
        app = YateApp(target=target)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            hits: list[str] = []

            def spy_quit(ctx: ActionContext) -> None:
                hits.append(ctx.session.doc.name or "")
                app.editor.quit()

            app.editor.actions.register("quit", spy_quit, "spy quit")
            await pilot.press("ctrl+q")
            await _wait_quit(app, pilot)

        assert hits == ["clean.txt"]
        assert app.return_code == 0

    asyncio.run(scenario())
