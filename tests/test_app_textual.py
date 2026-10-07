"""Headless shell-behavior tests for the Textual UI (run via pilot, no real terminal).

Domain-specific suites were split into sibling modules:
test_app_explorer.py, test_app_palette.py, test_app_terminal.py, test_app_panes.py,
test_app_find.py, test_app_manual.py, test_app_lsp.py, test_app_render.py."""

# tests legitimately poke at internals:
# pyright: reportPrivateUsage=false

from __future__ import annotations

import asyncio
import contextlib
from pathlib import Path
from typing import Any, cast
import pytest
from textual.strip import Strip
from yate.app import YateApp, textual_key_to_raw
from yate.editor_syntax.tokens import Token
from yate.editor_view.icons import LOCK
from yate.keymaps.base import ActionContext
from yate.keyproto.legacy import event_to_raw
from conftest import message_text, wait_until

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
    # Legacy terminals deliver \x1f as Textual's "ctrl+underscore"; kitty
    # CSI-u ones as "ctrl+slash".  Both spellings map to the same byte.
    assert textual_key_to_raw("ctrl+underscore") == "\x1f"
    assert textual_key_to_raw("ctrl+slash") == "\x1f"
    assert textual_key_to_raw("alt+u") == "\x1bu"


def test_event_to_raw_c0_fallback_covers_driver_name_drift() -> None:
    """Names observed on a real Windows Terminal (IKH1RA trace): the win32
    driver spells ctrl+punctuation with long names the table does not know,
    while event.character still carries the true C0 byte."""
    assert event_to_raw("ctrl+right_square_bracket", "\x1d") == "\x1d"
    assert event_to_raw("ctrl+circumflex_accent", "\x1e") == "\x1e"
    # canonical names keep using the table (fallback is last resort)
    assert event_to_raw("ctrl+]", "\x1d") == "\x1d"
    # printable characters never satisfy the fallback: ctrl+digit stays
    # physically unmappable on legacy terminals
    assert event_to_raw("ctrl+1", "1") is None


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


def _status_strip(app: YateApp) -> str:
    """The status bar's rendered text as one plain string."""
    return "".join(seg.text for seg in app.editor.status_bar.render_line(0))


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
            strip = _status_strip(app)
            assert LOCK in strip
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
            strip = _status_strip(app)
            assert LOCK not in strip
            await pilot.press("x")
            # startup cursor sits at (0, 0), so the typing lands at the top
            assert app.editor.session.buffer.get_text() == "xkeep"

    asyncio.run(scenario())


def test_readonly_statusbar_lock_keeps_right_block_visible(tmp_path: Path) -> None:
    """A lock plus a truncated long filename must not clip the right block."""

    async def scenario() -> None:
        target = tmp_path / ("a-very-long-file-name-" + "x" * 70 + ".txt")
        app = YateApp(target=target, readonly=True)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            strip = _status_strip(app)
            assert LOCK in strip
            # the right block (… "F1") still ends exactly at the bar's edge
            assert strip.rstrip().endswith("F1")

    asyncio.run(scenario())


def test_readonly_session_applies_to_later_opens(tmp_path: Path) -> None:
    """In a --readonly session, :e opens the next file read-only too."""

    async def scenario() -> None:
        first = tmp_path / "first.txt"
        first.write_text("one", encoding="utf-8")
        second = tmp_path / "second.txt"
        second.write_text("two", encoding="utf-8")
        app = YateApp(target=first, readonly=True)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            app.editor.run_command(f"e {second}")
            # :e opens through an exclusive "open" worker -- poll, don't assume
            # a single pause is enough (raced on loaded CI boxes)
            assert await wait_until(
                pilot, lambda: app.editor.session.doc.path == second,
            )
            assert app.editor.session.buffer.read_only
            # unlock the second document, hop back to the (still locked)
            # startup file, then return: a reused document is NOT re-locked
            app.editor.run_command("set readonly=false")
            app.editor.run_command(f"e {first}")
            assert await wait_until(
                pilot, lambda: app.editor.session.doc.path == first,
            )
            assert app.editor.session.buffer.read_only
            app.editor.run_command(f"e {second}")
            assert await wait_until(
                pilot, lambda: app.editor.session.doc.path == second,
            )
            assert not app.editor.session.buffer.read_only

    asyncio.run(scenario())


def test_readonly_saveas_writes_elsewhere_and_unlocks(tmp_path: Path) -> None:
    """:saveas persists a read-only buffer to a new path and unlocks it."""

    async def scenario() -> None:
        source = tmp_path / "source.txt"
        source.write_text("protected", encoding="utf-8")
        dest = tmp_path / "copy.txt"
        app = YateApp(target=source, readonly=True)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            assert app.editor.session.buffer.read_only
            app.editor.run_command(f"saveas {dest}")
            await pilot.pause()
            assert dest.read_text(encoding="utf-8") == "protected"
            # the original file is untouched and the buffer is unlocked now
            assert source.read_text(encoding="utf-8") == "protected"
            assert not app.editor.session.buffer.read_only
            # a plain :w now targets the new path, not the source
            await pilot.press("x")
            app.editor.run_command("w")
            await pilot.pause()
            assert dest.read_text(encoding="utf-8") == "xprotected"
            assert source.read_text(encoding="utf-8") == "protected"

    asyncio.run(scenario())


def test_readonly_saveas_unexpected_error_restores_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed :saveas re-locks the buffer, even on unexpected errors."""

    async def scenario() -> None:
        from yate.editor_core.document import Document

        source = tmp_path / "source.txt"
        source.write_text("protected", encoding="utf-8")
        app = YateApp(target=source, readonly=True)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            assert app.editor.session.buffer.read_only
            real_save = Document.save

            def boom(doc: Document, path: Path | str | None = None) -> Path:
                raise RuntimeError("boom")

            monkeypatch.setattr(Document, "save", boom)

            # an unexpected error propagates to the caller without taking
            # the app down, and the finally re-locks the buffer
            with pytest.raises(RuntimeError):
                app.editor.run_command(f"saveas {tmp_path / 'copy.txt'}")
            assert app.editor.session.buffer.read_only
            assert app.is_running

            # expected failures (OSError) still report "save failed" and
            # restore the lock too
            monkeypatch.setattr(Document, "save", real_save)
            blocked = tmp_path / "no-such-dir" / "out.txt"
            app.editor.run_command(f"saveas {blocked}")
            await pilot.pause()
            assert "save failed" in message_text(app)
            assert app.editor.session.buffer.read_only
            assert not blocked.exists()

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
            try:
                app.editor.set_theme("latte")
                await pilot.pause()
                assert theme.active().name == "latte"
            finally:
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
            # tokenize pass is pending: the resynced tokens keep the row
            # syntax-colored right after the keypress (no uncolored
            # frame). The default vsc keymap inserts "x", so "def" merges
            # into the identifier "xdef" and legitimately loses its
            # keyword token; the function color of "foo" proves the row
            # is still colored, not plain.
            await pilot.press("x")
            assert editor.tokens_for(0)
            assert mocha.syn_function.lower() in colors_at(0)

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


# ---------------------------------------------------- row-level token resync


def test_line_resync_updates_keyword_boundary_on_edit(tmp_path: Path) -> None:
    """Editing inside a keyword resyncs token boundaries in the same frame."""

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
            buf = app.editor.session.buffer
            # "def" -> "deXf": the stale keyword token (0, 3) would keep
            # coloring the shifted text for one debounce window; the row
            # resync must drop it immediately and move the function token
            # past the inserted character.
            buf.cursor = (0, 2)
            buf.insert_text("X")
            toks = editor.tokens_for(0)
            assert toks
            assert Token(0, 3, "keyword") not in toks
            assert Token(5, 8, "function") in toks
            # the debounced worker still converges to the edited version
            assert await wait_until(
                pilot,
                lambda: editor.highlight_probe().version
                == buf.content_version
                and editor.highlight_probe().scheduled_key is None,
                timeout=5.0,
            )

    asyncio.run(scenario())


def test_line_resync_updates_string_boundary_on_edit(tmp_path: Path) -> None:
    """Typing before a closing quote extends the string token immediately."""

    async def scenario() -> None:
        target = tmp_path / "script.py"
        target.write_text('msg = "hello"\n', encoding="utf-8")
        app = YateApp(target=target)
        async with app.run_test(size=(100, 30)) as pilot:
            editor = app.editor.panes.active_view
            assert editor is not None
            assert await wait_until(
                pilot, lambda: editor.highlight_probe().tokens is not None,
                timeout=5.0,
            )
            buf = app.editor.session.buffer
            # "hello" -> "helloX": the stale string token (6, 13) would
            # leave the moved closing quote uncolored; the resync must
            # cover the whole literal right away.
            buf.cursor = (0, 12)
            buf.insert_text("X")
            toks = editor.tokens_for(0)
            assert toks
            assert Token(6, 13, "string") not in toks
            assert Token(6, 14, "string") in toks
            assert await wait_until(
                pilot,
                lambda: editor.highlight_probe().version
                == buf.content_version
                and editor.highlight_probe().scheduled_key is None,
                timeout=5.0,
            )

    asyncio.run(scenario())


def test_line_resync_updates_number_boundary_on_edit(tmp_path: Path) -> None:
    """Extending a number resyncs the number token in the same frame."""

    async def scenario() -> None:
        target = tmp_path / "script.py"
        target.write_text("    return 42\n", encoding="utf-8")
        app = YateApp(target=target)
        async with app.run_test(size=(100, 30)) as pilot:
            editor = app.editor.panes.active_view
            assert editor is not None
            assert await wait_until(
                pilot, lambda: editor.highlight_probe().tokens is not None,
                timeout=5.0,
            )
            buf = app.editor.session.buffer
            # 42 -> 423: the stale number token (11, 13) would leave the
            # typed digit in default foreground until the worker lands.
            buf.cursor = (0, 13)
            buf.insert_text("3")
            toks = editor.tokens_for(0)
            assert toks
            assert Token(11, 13, "number") not in toks
            assert Token(11, 14, "number") in toks
            assert await wait_until(
                pilot,
                lambda: editor.highlight_probe().version
                == buf.content_version
                and editor.highlight_probe().scheduled_key is None,
                timeout=5.0,
            )

    asyncio.run(scenario())


def test_line_resync_updates_decorator_boundary_on_edit(
    tmp_path: Path,
) -> None:
    """Extending a decorator resyncs the decorator token immediately."""

    async def scenario() -> None:
        target = tmp_path / "script.py"
        target.write_text("@property\nx = 1\n", encoding="utf-8")
        app = YateApp(target=target)
        async with app.run_test(size=(100, 30)) as pilot:
            editor = app.editor.panes.active_view
            assert editor is not None
            assert await wait_until(
                pilot, lambda: editor.highlight_probe().tokens is not None,
                timeout=5.0,
            )
            buf = app.editor.session.buffer
            # @property -> @propertyX: the stale decorator token (0, 9)
            # would leave the typed character uncolored for one window.
            buf.cursor = (0, 9)
            buf.insert_text("X")
            toks = editor.tokens_for(0)
            assert toks
            assert Token(0, 9, "decorator") not in toks
            assert Token(0, 10, "decorator") in toks
            assert await wait_until(
                pilot,
                lambda: editor.highlight_probe().version
                == buf.content_version
                and editor.highlight_probe().scheduled_key is None,
                timeout=5.0,
            )

    asyncio.run(scenario())


def test_line_resync_updates_block_comment_boundary_on_edit(
    tmp_path: Path,
) -> None:
    """Typing inside a C block comment extends the comment token at once."""

    async def scenario() -> None:
        target = tmp_path / "code.c"
        target.write_text("/* comment */\nint main(void) {}\n", encoding="utf-8")
        app = YateApp(target=target)
        async with app.run_test(size=(100, 30)) as pilot:
            editor = app.editor.panes.active_view
            assert editor is not None
            assert await wait_until(
                pilot, lambda: editor.highlight_probe().tokens is not None,
                timeout=5.0,
            )
            buf = app.editor.session.buffer
            # /* comment */ -> /* comment X*/: the stale comment token
            # (0, 13) would drop the shifted terminator out of the span.
            buf.cursor = (0, 12)
            buf.insert_text("X")
            toks = editor.tokens_for(0)
            assert toks
            assert Token(0, 13, "comment") not in toks
            assert Token(0, 14, "comment") in toks
            # the line below the comment is untouched and stays colored
            assert editor.tokens_for(1)
            assert await wait_until(
                pilot,
                lambda: editor.highlight_probe().version
                == buf.content_version
                and editor.highlight_probe().scheduled_key is None,
                timeout=5.0,
            )

    asyncio.run(scenario())


def test_line_resync_reuses_snapshot_on_cursor_movement(
    tmp_path: Path,
) -> None:
    """Cursor movement neither rebuilds nor reschedules the token cache."""

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
            probe = editor.highlight_probe()
            tokens = probe.tokens
            assert tokens is not None
            version = probe.version
            snapshot = editor._hl_line_snapshot
            assert snapshot is not None
            # moving the cursor never bumps content_version: the cached
            # tokens and the row snapshot are reused exactly as stored
            # (arrow keys only -- letters would type in the vsc keymap)
            await pilot.press("down", "right")
            probe = editor.highlight_probe()
            assert probe.tokens is tokens
            assert probe.version == version
            assert probe.scheduled_key is None
            assert probe.timer is None
            assert editor.tokens_for(0) is tokens[0]
            assert editor._hl_line_snapshot == tuple(
                app.editor.session.buffer.lines
            )

    asyncio.run(scenario())


def test_line_resync_keeps_construct_below_inserted_line(
    tmp_path: Path,
) -> None:
    """Rows below an inserted line reuse their token objects unchanged."""

    async def scenario() -> None:
        target = tmp_path / "script.py"
        target.write_text('x = 1\nmsg = """\nhello\nworld\n"""\n', encoding="utf-8")
        app = YateApp(target=target)
        async with app.run_test(size=(100, 30)) as pilot:
            editor = app.editor.panes.active_view
            assert editor is not None
            assert await wait_until(
                pilot, lambda: editor.highlight_probe().tokens is not None,
                timeout=5.0,
            )
            buf = app.editor.session.buffer
            hello_row = editor.tokens_for(2)
            world_row = editor.tokens_for(3)
            # inserting a line shifts the triple-string body down one row;
            # the shift-aware snapshot mapping must reuse those rows as-is
            # (object identity) instead of re-tokenizing the whole tail
            buf.cursor = (0, 5)
            buf.insert_text("\n# spacer")
            assert editor.tokens_for(1) == [Token(0, 8, "comment")]
            assert editor.tokens_for(3) is hello_row
            assert editor.tokens_for(4) is world_row
            assert editor.tokens_for(3) == [Token(0, 5, "string")]
            assert editor._hl_line_snapshot == tuple(buf.lines)
            assert await wait_until(
                pilot,
                lambda: editor.highlight_probe().version
                == buf.content_version
                and editor.highlight_probe().scheduled_key is None,
                timeout=5.0,
            )

    asyncio.run(scenario())


def test_line_resync_repaints_construct_opened_by_inserted_line(
    tmp_path: Path,
) -> None:
    """An inserted triple-quote opener repaints the rows below it."""

    async def scenario() -> None:
        target = tmp_path / "script.py"
        target.write_text("x = 1\ny = 2\nz = 3\n", encoding="utf-8")
        app = YateApp(target=target)
        async with app.run_test(size=(100, 30)) as pilot:
            editor = app.editor.panes.active_view
            assert editor is not None
            assert await wait_until(
                pilot, lambda: editor.highlight_probe().tokens is not None,
                timeout=5.0,
            )
            buf = app.editor.session.buffer
            stale_row = editor.tokens_for(1)
            # inserting an opener shifts "y = 2" / "z = 3" into a triple
            # string; the state guard must forbid reusing their stale code
            # tokens and repaint both rows as string immediately
            buf.cursor = (0, 5)
            buf.insert_text('\ns = """')
            assert editor.tokens_for(2) is not stale_row
            assert editor.tokens_for(2) == [Token(0, 5, "string")]
            assert editor.tokens_for(3) == [Token(0, 5, "string")]
            assert await wait_until(
                pilot,
                lambda: editor.highlight_probe().version
                == buf.content_version
                and editor.highlight_probe().scheduled_key is None,
                timeout=5.0,
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
                    assert bg is not None, f"bg=None cell at row {row}: {seg.text!r}"
                    assert repr(bg) in allowed
                    checked += 1
            assert checked > 12

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


# ---------------------------------------------- action_quit registry routing


async def _wait_quit(app: YateApp, pilot: Any) -> None:
    """Pump the pilot until *app* exits (mirrors the :q tests above).

    After the pump loop the app must have exited cleanly: ``_exception``
    being set would mean the shutdown crashed rather than quit, and that
    must not pass silently as a successful quit.
    """
    for _ in range(5):
        with contextlib.suppress(Exception):
            await pilot.pause()
        if not app.is_running:
            break
    for _ in range(3):
        await asyncio.sleep(0)
    assert app._exception is None


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
