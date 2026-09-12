"""Headless smoke tests for the Textual UI (run via pilot, no real terminal)."""

from __future__ import annotations

import asyncio
import os
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Awaitable, Callable, cast

from textual.strip import Strip

# The bundled extensions/ directory is auto-loaded with every YateApp; make
# sure the Python LSP extension never probes PATH or spawns a real server
# while the UI test suite runs.
os.environ["YATE_PYTHON_LSP"] = "off"

from yate.app import YateApp, textual_key_to_raw
from yate.editor_view.manual import ManualScreen


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


class KeyAdapterTests(unittest.TestCase):
    def test_named_keys(self):
        self.assertEqual(textual_key_to_raw("enter"), "\r")
        self.assertEqual(textual_key_to_raw("escape"), "\x1b")
        self.assertEqual(textual_key_to_raw("backspace"), "\x7f")
        self.assertEqual(textual_key_to_raw("up"), "\x1b[A")
        self.assertEqual(textual_key_to_raw("f1"), "\x1bOP")
        self.assertEqual(textual_key_to_raw("space"), " ")

    def test_ctrl_and_alt(self):
        self.assertEqual(textual_key_to_raw("ctrl+s"), "\x13")
        self.assertEqual(textual_key_to_raw("ctrl+c"), "\x03")
        self.assertEqual(textual_key_to_raw("ctrl+]"), "\x1d")
        self.assertEqual(textual_key_to_raw("ctrl+/"), "\x1f")
        self.assertEqual(textual_key_to_raw("alt+u"), "\x1bu")

    def test_modified_arrows(self):
        self.assertEqual(textual_key_to_raw("ctrl+right"), "\x1b[1;5C")
        self.assertEqual(textual_key_to_raw("shift+left"), "\x1b[1;2D")
        self.assertEqual(textual_key_to_raw("ctrl+pageup"), "\x1b[5;5~")

    def test_printable_passthrough(self):
        self.assertEqual(textual_key_to_raw("a"), "a")
        self.assertEqual(textual_key_to_raw(":"), ":")
        self.assertIsNone(textual_key_to_raw(""))


class TextualAppSmokeTests(unittest.IsolatedAsyncioTestCase):
    async def test_type_save_find_help_keymap(self):
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "notes.txt"
            app = YateApp(target=target)
            self.assertEqual(app.keymap_name, "vsc")
            async with app.run_test(size=(100, 30)) as pilot:
                # widgets exist once mounted; narrow the Optional widget attrs
                prompt_bar = app.prompt_bar
                assert prompt_bar is not None

                # --- type text into the buffer
                await pilot.press("h", "e", "l", "l", "o")
                self.assertEqual(app.buffer.lines[0], "hello")
                self.assertTrue(app.doc.modified)

                # --- save with ctrl+s
                await pilot.press("ctrl+s")
                self.assertTrue(target.exists())
                self.assertFalse(app.doc.modified)
                self.assertEqual(target.read_text(encoding="utf-8"), "hello")

                # --- find prompt + live search
                await pilot.press("ctrl+f")
                self.assertEqual(prompt_bar.active_mode, "find")
                await pilot.press("l", "l")
                await pilot.press("enter")
                self.assertEqual(app.search.query, "ll")
                self.assertGreaterEqual(len(app.search.matches), 1)
                self.assertEqual(app.focused, app.editor_view)

                # --- switch keymap to vim via the vsc toggle (the ":" ex
                # command line is vim-only; vsc mode types ":" literally)
                await pilot.press("ctrl+/")
                self.assertEqual(app.keymap_name, "vim")

                # --- vim append-at-line-end then escape (clear the search
                # selection first, otherwise insert replaces it by design)
                app.buffer.clear_selection()
                await pilot.press("A", "!", "escape")
                self.assertEqual(app.buffer.lines[0], "hello!")

                # --- help modal opens via :help and closes
                await pilot.press("colon")
                self.assertEqual(prompt_bar.active_mode, "command")
                for ch in "help":
                    await pilot.press(ch)
                await pilot.press("enter")
                await pilot.pause()
                self.assertEqual(len(app.screen_stack), 2)
                await pilot.press("q")
                await pilot.pause()
                self.assertEqual(len(app.screen_stack), 1)

                # --- tab bar shows the file name
                self.assertIn("notes.txt", app.render_tabbar(100).plain)

                # --- breadcrumbs: folder chevron crumbs + file name; the
                # file name stays visible even on a very narrow bar
                crumbs = app.render_breadcrumbs(100).plain
                self.assertIn("notes.txt", crumbs)
                self.assertIn("\uf054", crumbs)  # chevron separator
                self.assertIn("notes.txt", app.render_breadcrumbs(12).plain)

    async def test_syntax_highlight_and_theme_switch(self):
        from yate.editor_view import theme

        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "script.py"
            target.write_text("def foo():\n    return 42\n", encoding="utf-8")
            app = YateApp(target=target)
            async with app.run_test(size=(100, 30)) as pilot:
                await pilot.pause()
                editor = app.editor_view
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
                self.assertIn(mocha.syn_keyword.lower(), colors)
                self.assertIn(mocha.syn_function.lower(), colors)
                # number 42 on line 2 -> number color
                self.assertIn(mocha.syn_number.lower(), seg_colors(editor.render_line(1)))

                # switch theme via the app action (the ":" ex line is
                # vim-only; the same command is reached via the vsc palette)
                app.set_theme("latte")
                await pilot.pause()
                self.assertEqual(theme.active().name, "latte")
                theme.set_theme("mocha")  # restore default for other tests

    async def test_highlight_cache_survives_cursor_movement(self):
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "script.py"
            target.write_text("def foo():\n    return 42\n", encoding="utf-8")
            app = YateApp(target=target)
            async with app.run_test(size=(100, 30)) as pilot:
                editor = app.editor_view
                assert editor is not None
                hl = cast(Any, editor)
                # wait for the background tokenizer to paint colors
                ready = await wait_until(
                    pilot, lambda: hl._hl_tokens is not None, timeout=5.0
                )
                self.assertTrue(ready)
                tokens = hl._hl_tokens

                def colors_at(row: int) -> set[str]:
                    return {
                        seg.style.color.name.lower()
                        for seg in editor.render_line(row)
                        if seg.style is not None and seg.style.color is not None
                    }

                from yate.editor_view import theme
                mocha = theme.active()
                before = colors_at(0)
                self.assertIn(mocha.syn_keyword.lower(), before)

                # moving the cursor must not discard the token cache: the
                # keyword color stays without waiting for a new tokenizer
                await pilot.press("down")
                self.assertIs(hl._hl_tokens, tokens)
                self.assertIn(mocha.syn_keyword.lower(), colors_at(0))

                # editing invalidates the cache; a fresh tokenizer pass runs
                await pilot.press("x")
                refreshed = await wait_until(
                    pilot,
                    lambda: hl._hl_tokens is not None
                    and hl._hl_tokens is not tokens
                    and hl._hl_version == app.buffer.content_version,
                    timeout=5.0,
                )
                self.assertTrue(refreshed)

    async def test_explorer_open_file(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.txt").write_text("alpha\n", encoding="utf-8")
            (root / "b.py").write_text("print('beta')\n", encoding="utf-8")
            app = YateApp(target=root)
            async with app.run_test(size=(100, 30)) as pilot:
                await pilot.pause()
                explorer = app.explorer_tree
                assert explorer is not None
                self.assertTrue(explorer.display)
                # ctrl+e focuses the explorer; j moves down; l opens
                await pilot.press("ctrl+e")
                self.assertIs(app.focused, app.explorer_tree)
                await pilot.press("j", "l")
                await pilot.pause()
                opened = {d.name for d in app.docs if d.path is not None}
                self.assertTrue(opened & {"a.txt", "b.py"})
                # esc returns focus to the editor
                await pilot.press("escape")
                self.assertIs(app.focused, app.editor_view)


class WalkFilesTests(unittest.TestCase):
    def test_collects_nested_files_and_prunes_noise(self):
        from yate.services.workspace import Workspace

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "src" / "main.py").write_text("x = 1\n", encoding="utf-8")
            (root / "src" / "util.py").write_text("y = 2\n", encoding="utf-8")
            (root / "readme.md").write_text("# hi\n", encoding="utf-8")
            (root / "__pycache__").mkdir()
            (root / "__pycache__" / "junk.pyc").write_text("x", encoding="utf-8")

            ws = Workspace(root)
            names = {p.name for p in ws.walk_files()}
            self.assertEqual(names, {"main.py", "util.py", "readme.md"})

    def test_no_root_returns_empty(self):
        from yate.services.workspace import Workspace

        self.assertEqual(Workspace(None).walk_files(), [])

    def test_limit(self):
        from yate.services.workspace import Workspace

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            for i in range(10):
                (root / f"f{i}.txt").write_text("x\n", encoding="utf-8")
            self.assertEqual(len(Workspace(root).walk_files(limit=3)), 3)


class FuzzyMatchTests(unittest.TestCase):
    def test_empty_query_matches(self):
        from yate.editor_view.palette import fuzzy_match

        self.assertIsNotNone(fuzzy_match("", "anything"))

    def test_subsequence_order(self):
        from yate.editor_view.palette import fuzzy_match

        self.assertIsNotNone(fuzzy_match("wt", "write"))
        self.assertIsNone(fuzzy_match("tw", "write"))
        self.assertIsNotNone(fuzzy_match("bp", "bprev"))
        self.assertIsNone(fuzzy_match("xyz", "bprev"))

    def test_consecutive_ranks_better_than_gap(self):
        from yate.editor_view.palette import fuzzy_match

        tight = fuzzy_match("set", "set")
        gappy = fuzzy_match("set", "reset")  # r-e-**s**-**e**-**t**: gap match
        assert tight is not None and gappy is not None
        self.assertLess(tight[0], gappy[0])

    def test_returns_matched_indices(self):
        from yate.editor_view.palette import fuzzy_match

        match = fuzzy_match("bprev", "bprev")
        assert match is not None
        self.assertEqual(match[1], [0, 1, 2, 3, 4])


class PaletteSmokeTests(unittest.IsolatedAsyncioTestCase):
    async def test_ctrl_p_chord_opens_file_palette(self):
        from yate.editor_view.palette import PaletteScreen

        with TemporaryDirectory() as tmp:
            (Path(tmp) / "notes.txt").write_text("hi\n", encoding="utf-8")
            app = YateApp(target=Path(tmp))
            async with app.run_test(size=(100, 30)) as pilot:
                await pilot.press("ctrl+p")
                await pilot.pause()
                screen = app.screen
                assert isinstance(screen, PaletteScreen)
                self.assertEqual(screen.mode, "files")
                # escape dismisses
                await pilot.press("escape")
                await pilot.pause()
                self.assertEqual(len(app.screen_stack), 1)

    async def test_file_palette_filters_and_opens(self):
        from yate.editor_view.palette import PaletteScreen

        with TemporaryDirectory() as tmp:
            (Path(tmp) / "notes.txt").write_text("hi\n", encoding="utf-8")
            (Path(tmp) / "data.txt").write_text("data\n", encoding="utf-8")
            app = YateApp(target=Path(tmp))
            async with app.run_test(size=(100, 30)) as pilot:
                app.open_file_palette()
                await pilot.pause()
                self.assertIsInstance(app.screen, PaletteScreen)
                for ch in "note":
                    await pilot.press(ch)
                await pilot.pause()
                screen = app.screen
                assert isinstance(screen, PaletteScreen)
                # only notes.txt matches "note"
                self.assertEqual(screen.filtered_count, 1)
                await pilot.press("enter")
                await pilot.pause()
                self.assertEqual(len(app.screen_stack), 1)
                self.assertEqual(app.doc.name, "notes.txt")

    async def test_command_palette_runs_command(self):
        from yate.editor_view.palette import PaletteScreen

        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            # alt+shift+p is the default: ctrl+shift+p clashes with Windows
            # Terminal's own command palette, ctrl+shift+a with other
            # terminal emulators.
            await pilot.press("alt+shift+p")
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, PaletteScreen)
            self.assertEqual(screen.mode, "commands")
            for ch in "vim":
                await pilot.press(ch)
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            self.assertEqual(app.keymap_name, "vim")

    async def test_command_palette_alt_shift_p_binding(self):
        from yate.editor_view.palette import PaletteScreen

        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            # the vsc keymap advertises the binding and the chord opens the
            # palette even while the editor widget has focus
            binding = app.active_keymap.lookup("\x1bP")
            assert binding is not None
            self.assertEqual(binding.action, "command_palette")
            await pilot.press("alt+shift+p")
            await pilot.pause()
            self.assertIsInstance(app.screen, PaletteScreen)

    async def test_command_palette_lists_all_commands_and_actions(self):
        from yate.editor_view.palette import PaletteScreen

        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            # as an extension would: one new command and one new action
            app.commands.register("zzz_palette_cmd", lambda args: None,
                                  "zz palette command")
            app.actions.register(
                "zzz_palette_action", lambda ctx: None, "zz palette action")
            app.open_command_palette()
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, PaletteScreen)
            entries = cast(Any, screen)._entries
            by_name = {name: payload for name, _hint, payload in entries}

            # built-in : commands and raw keymap actions are both present,
            # each with its full name
            self.assertEqual(by_name["write"], ("command", "write"))
            self.assertEqual(by_name["move_left"], ("action", "move_left"))
            self.assertEqual(by_name["command_palette"],
                             ("action", "command_palette"))
            # extension-registered items show up too
            self.assertEqual(by_name["zzz_palette_cmd"],
                             ("command", "zzz_palette_cmd"))
            self.assertEqual(by_name["zzz_palette_action"],
                             ("action", "zzz_palette_action"))
            # a name registered in both tables appears once and resolves
            # to the : command spelling
            self.assertEqual(by_name["quit"], ("command", "quit"))
            # every row has a non-empty name and (for built-ins) a hint
            self.assertTrue(all(name for name, _h, _p in entries))
            hinted = {name: hint for name, hint, _p in entries}
            self.assertEqual(hinted["write"], "save the current file")
            self.assertEqual(hinted["move_left"], "Move left")

    async def test_command_palette_runs_action_by_full_name(self):
        from yate.editor_view.palette import PaletteScreen

        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            self.assertEqual(app.keymap_name, "vsc")
            app.open_command_palette()
            await pilot.pause()
            self.assertIsInstance(app.screen, PaletteScreen)
            for ch in "toggle_keymap":
                await pilot.press(ch)
            await pilot.pause()
            screen = cast(Any, app.screen)
            # the action is found by its full name and is the top hit
            self.assertEqual(
                screen._entries[screen._filtered[0][2]][2],
                ("action", "toggle_keymap"),
            )
            await pilot.press("enter")
            await pilot.pause()
            self.assertEqual(len(app.screen_stack), 1)
            self.assertEqual(app.keymap_name, "vim")

    async def test_command_palette_searches_descriptions(self):
        from yate.editor_view.palette import PaletteScreen

        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            app.open_command_palette()
            await pilot.pause()
            for ch in "switch color theme":
                await pilot.press(ch)
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, PaletteScreen)
            # no command is *named* "switch color theme"; it matches the
            # description of :theme, and the row is selectable
            self.assertGreater(screen.filtered_count, 0)
            top = cast(Any, screen)._entries[
                cast(Any, screen)._filtered[0][2]]
            self.assertEqual(top[2], ("command", "theme"))
            await pilot.press("enter")
            await pilot.pause()
            self.assertEqual(len(app.screen_stack), 1)

    async def test_palette_down_cursor_moves(self):
        from yate.editor_view.palette import PaletteScreen

        with TemporaryDirectory() as tmp:
            for name in ("a.txt", "b.txt", "c.txt"):
                (Path(tmp) / name).write_text("x\n", encoding="utf-8")
            app = YateApp(target=Path(tmp))
            async with app.run_test(size=(100, 30)) as pilot:
                app.open_file_palette()
                await pilot.pause()
                screen = app.screen
                assert isinstance(screen, PaletteScreen)
                await pilot.press("down")
                self.assertEqual(screen.cursor_index, 1)


class EditorScrollTests(unittest.IsolatedAsyncioTestCase):
    async def test_viewport_follows_cursor_and_scrolls_back(self):
        """Regression: moving past the visible area must scroll the view."""
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "big.txt"
            p.write_text(
                "\n".join(f"line {i}" for i in range(1, 61)) + "\n",
                encoding="utf-8",
            )
            app = YateApp(target=p)
            async with app.run_test(size=(100, 30)) as pilot:
                await pilot.pause()
                editor = app.editor_view
                assert editor is not None
                self.assertEqual(editor.scroll_offset.y, 0)

                for _ in range(45):
                    await pilot.press("down")
                await pilot.pause()
                top = editor.scroll_offset.y
                self.assertGreater(top, 0)
                # first visible row shows buffer line top+1
                first = "".join(seg.text for seg in editor.render_line(0))
                self.assertEqual(first.split()[0], str(top + 1))
                # cursor row stays inside the visible window
                buf_row = app.buffer.row
                self.assertGreaterEqual(buf_row - top, 0)
                self.assertLess(buf_row - top, editor.size.height)

                for _ in range(45):
                    await pilot.press("up")
                await pilot.pause()
                self.assertEqual(editor.scroll_offset.y, 0)

    async def test_scrolled_view_renders_buffer_rows(self):
        """Regression: render_line must honour the scroll offset (wheel path)."""
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "big.txt"
            p.write_text(
                "\n".join(f"line {i}" for i in range(1, 61)) + "\n",
                encoding="utf-8",
            )
            app = YateApp(target=p)
            async with app.run_test(size=(100, 30)) as pilot:
                await pilot.pause()
                editor = app.editor_view
                assert editor is not None
                # this is where Textual's mouse-wheel handling lands
                editor.scroll_down(animate=False)
                await pilot.pause()
                self.assertEqual(editor.scroll_offset.y, 1)
                first = "".join(seg.text for seg in editor.render_line(0))
                self.assertEqual(first.split()[0], "2")
                self.assertIn("line 2", first)


class WelcomeScreenTests(unittest.IsolatedAsyncioTestCase):
    async def test_welcome_shown_then_hidden_on_type(self):
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            editor = app.editor_view
            assert editor is not None

            def screen_text() -> str:
                parts: list[str] = []
                for row in range(26):
                    parts.extend(seg.text for seg in editor.render_line(row))
                return "".join(parts)

            welcome = screen_text()
            self.assertIn("\u2588\u2588\u2557   \u2588\u2588\u2557", welcome)  # "Y" head
            self.assertIn("\u255a\u2550\u2550\u2550\u2550\u2550\u2550\u255d", welcome)  # "E" foot
            self.assertIn("yate", welcome)
            self.assertIn("quick open", welcome)
            # default (vsc) welcome must not advertise the vim-only ":" prompt
            self.assertNotIn("ex command prompt", welcome)
            # typing dismisses the welcome page
            await pilot.press("h", "i")
            await pilot.pause()
            self.assertNotIn("\u2588", screen_text())

    async def test_welcome_advertises_colon_only_in_vim_keymap(self):
        app = YateApp(keymap="vim")
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            editor = app.editor_view
            assert editor is not None
            parts: list[str] = []
            for row in range(26):
                parts.extend(seg.text for seg in editor.render_line(row))
            self.assertIn("ex command prompt", "".join(parts))

    async def test_enew_dismisses_welcome_and_it_does_not_return(self):
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            editor = app.editor_view
            assert editor is not None

            def screen_text() -> str:
                parts: list[str] = []
                for row in range(26):
                    parts.extend(seg.text for seg in editor.render_line(row))
                return "".join(parts)

            self.assertIn("\u2588", screen_text())  # welcome banner at startup
            initial_index = app.doc_index

            # :enew creates another empty scratch buffer -- the welcome page
            # must be cleared immediately, never to return on its own.
            app.run_command("enew")
            await pilot.pause()
            self.assertFalse(app.welcome_visible)
            self.assertNotIn("\u2588", screen_text())

            # switching back to the still-pristine startup buffer must not
            # bring the welcome page back
            app.run_command("bp")
            await pilot.pause()
            self.assertEqual(app.doc_index, initial_index)
            self.assertNotIn("\u2588", screen_text())

            # ...until the user explicitly asks for it with :welcome
            app.run_command("welcome")
            await pilot.pause()
            self.assertTrue(app.welcome_visible)
            self.assertIn("\u2588", screen_text())

    async def test_internal_seed_buffer_keeps_welcome_enabled(self):
        # Startup seeds the initial buffer via new_buffer(show=False); that
        # internal path must not dismiss the welcome page.
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            self.assertTrue(app.welcome_visible)
            editor = app.editor_view
            assert editor is not None
            parts: list[str] = []
            for row in range(26):
                parts.extend(seg.text for seg in editor.render_line(row))
            self.assertIn("yate", "".join(parts))


class PromptBarTests(unittest.IsolatedAsyncioTestCase):
    async def test_command_input_shows_typed_text(self):
        """Regression: focused height-1 Input must not gain a tall border
        that collapses its content region and hides typed characters."""
        app = YateApp(keymap="vim")
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.press(":")
            await pilot.pause()
            await pilot.press(*"wp")
            await pilot.pause()
            prompt_bar = app.prompt_bar
            assert prompt_bar is not None
            inp = prompt_bar.input
            self.assertEqual(inp.value, "wp")
            self.assertEqual(inp.scrollable_content_region.height, 1)
            strip_text = "".join(seg.text for seg in inp.render_line(0))
            self.assertIn("wp", strip_text)

    async def test_colon_types_literally_in_vsc_keymap(self):
        """The ex command prompt is vim-only; vsc mode inserts ':' as text."""
        app = YateApp()  # default keymap is vsc
        async with app.run_test(size=(100, 30)) as pilot:
            prompt_bar = app.prompt_bar
            assert prompt_bar is not None
            await pilot.press(":", "w", "q")
            await pilot.pause()
            self.assertIsNone(prompt_bar.active_mode)
            self.assertEqual(app.doc.buffer.get_text(), ":wq")

    async def test_f5_opens_command_prompt_in_vsc_keymap(self):
        """F5 activates the ex command line; Esc dismisses it."""
        app = YateApp()  # default keymap is vsc
        async with app.run_test(size=(100, 30)) as pilot:
            prompt_bar = app.prompt_bar
            assert prompt_bar is not None
            await pilot.press("f5")
            await pilot.pause()
            self.assertEqual(prompt_bar.active_mode, "command")
            # typing still lands in the prompt, not the buffer
            await pilot.press(*"w")
            await pilot.pause()
            self.assertEqual(prompt_bar.input.value, "w")
            self.assertEqual(app.doc.buffer.get_text(), "")
            # Esc closes the prompt and returns focus to the editor
            await pilot.press("escape")
            await pilot.pause()
            self.assertIsNone(prompt_bar.active_mode)
            self.assertIs(app.focused, app.editor_view)

    async def test_colon_opens_prompt_in_vim_keymap(self):
        app = YateApp(keymap="vim")
        async with app.run_test(size=(100, 30)) as pilot:
            prompt_bar = app.prompt_bar
            assert prompt_bar is not None
            await pilot.press(":")
            await pilot.pause()
            self.assertEqual(prompt_bar.active_mode, "command")

    async def test_breadcrumb_blank_for_untitled_doc(self):
        """Untitled buffers must not repeat the tab label in breadcrumbs."""
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            self.assertEqual(app.render_breadcrumbs(80).plain.strip(), "")


class RcExtensionTests(unittest.IsolatedAsyncioTestCase):
    async def test_rc_declared_file_and_directory_extensions_load(self):
        from yate.config import load_config

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
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
            self.assertEqual(config.errors, [])
            app = YateApp(config=config)
            async with app.run_test(size=(100, 30)) as pilot:
                await pilot.pause()
                self.assertIn("rcping", app.commands.names())
                loaded = {rec.name for rec in app.extension_loader.loaded}
                self.assertIn("myext", loaded)
                self.assertIn("dir_ext", loaded)
                self.assertTrue(
                    all(rec.error is None for rec in app.extension_loader.loaded)
                )


class ExplorerOpsTests(unittest.IsolatedAsyncioTestCase):
    async def test_ctrl_b_toggles_explorer(self):
        with TemporaryDirectory() as tmp:
            app = YateApp(target=Path(tmp))
            async with app.run_test(size=(100, 30)) as pilot:
                await pilot.pause()
                explorer = app.explorer_tree
                assert explorer is not None
                self.assertTrue(explorer.display)
                await pilot.press("ctrl+b")
                await pilot.pause()
                self.assertFalse(explorer.display)
                await pilot.press("ctrl+b")
                await pilot.pause()
                self.assertTrue(explorer.display)

    async def test_new_file_and_folder_from_explorer(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "seed.txt").write_text("seed\n", encoding="utf-8")
            app = YateApp(target=root)
            async with app.run_test(size=(100, 30)) as pilot:
                await pilot.pause()
                # cursor sits on the root: "a" creates a file at the top level
                await pilot.press("ctrl+e")
                await pilot.press("a")
                await pilot.pause()
                prompt_bar = app.prompt_bar
                assert prompt_bar is not None
                self.assertEqual(prompt_bar.active_mode, "new_file")
                await pilot.press(*"made.txt")
                await pilot.press("enter")
                await pilot.pause()
                self.assertTrue((root / "made.txt").exists())
                # new files open right away (VS Code behavior)
                opened = {d.name for d in app.docs if d.path is not None}
                self.assertIn("made.txt", opened)
                # "A" creates a folder; creation target is the selected dir
                await pilot.press("ctrl+e")
                await pilot.press("A")
                await pilot.pause()
                self.assertEqual(prompt_bar.active_mode, "new_dir")
                await pilot.press(*"subdir")
                await pilot.press("enter")
                await pilot.pause()
                self.assertTrue((root / "subdir").is_dir())

    async def test_rename_updates_open_document_path(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "old.txt").write_text("data\n", encoding="utf-8")
            app = YateApp(target=root)
            async with app.run_test(size=(100, 30)) as pilot:
                await pilot.pause()
                await pilot.press("ctrl+e", "j", "l")  # focus, move, open old.txt
                await pilot.pause()
                doc = app.doc
                self.assertIsNotNone(doc.path)
                await pilot.press("ctrl+e")
                await pilot.press("j")  # cursor onto old.txt
                await pilot.press("r")
                await pilot.pause()
                prompt_bar = app.prompt_bar
                assert prompt_bar is not None
                self.assertEqual(prompt_bar.active_mode, "rename")
                self.assertEqual(prompt_bar.input.value, "old.txt")
                await pilot.press(*"new.txt")
                await pilot.press("enter")
                await pilot.pause()
                self.assertFalse((root / "old.txt").exists())
                self.assertTrue((root / "new.txt").exists())
                self.assertEqual(app.doc.path, (root / "new.txt").resolve())

    async def test_delete_requires_confirmation(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            victim = root / "gone.txt"
            victim.write_text("bye\n", encoding="utf-8")
            app = YateApp(target=root)
            async with app.run_test(size=(100, 30)) as pilot:
                await pilot.pause()
                await pilot.press("ctrl+e", "j")
                await pilot.press("d")
                await pilot.pause()
                prompt_bar = app.prompt_bar
                assert prompt_bar is not None
                self.assertEqual(prompt_bar.active_mode, "delete")
                self.assertTrue(victim.exists())
                # anything but y cancels
                await pilot.press("n")
                await pilot.press("enter")
                await pilot.pause()
                self.assertTrue(victim.exists())
                # d again, confirm with y
                await pilot.press("ctrl+e", "j", "d")
                await pilot.press(*"y")
                await pilot.press("enter")
                await pilot.pause()
                self.assertFalse(victim.exists())

    async def test_refresh_tree_keeps_expanded_dirs(self):
        from yate.editor_view.explorer import ExplorerTree

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            sub = root / "sub"
            sub.mkdir()
            (sub / "inner.txt").write_text("i\n", encoding="utf-8")
            app = YateApp(target=root)
            async with app.run_test(size=(100, 30)) as pilot:
                await pilot.pause()
                explorer = app.explorer_tree
                assert explorer is not None
                # expand "sub" via the tree: focus root, j to sub, l to expand
                await pilot.press("ctrl+e", "j", "l")
                await pilot.pause()
                sub_node = next(n for n in explorer.root.children
                                if isinstance(n.data, Path) and n.data == sub)
                self.assertTrue(sub_node.is_expanded)
                # any refresh (e.g. opening a file elsewhere) must not collapse
                explorer.refresh_tree()
                sub_node2 = next(n for n in explorer.root.children
                                 if isinstance(n.data, Path) and n.data == sub)
                self.assertTrue(sub_node2.is_expanded)
                self.assertIn(ExplorerTree, type(explorer).__mro__)


class EditorBgTests(unittest.IsolatedAsyncioTestCase):
    async def test_every_editor_cell_has_explicit_bg(self):
        """Regression: None bgcolor would let the terminal's own background
        bleed through next to cells painted with theme.bg."""
        from rich.color import Color

        from yate.editor_view import theme as theme_mod

        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "doc.py"
            p.write_text('"""doc"""\n\nx = 1\n', encoding="utf-8")
            app = YateApp(target=p)
            async with app.run_test(size=(100, 30)) as pilot:
                await pilot.pause()
                editor = app.editor_view
                assert editor is not None
                t = theme_mod.active()
                allowed = {repr(Color.parse(t.bg)), repr(Color.parse(t.surface))}
                checked = 0
                for row in range(min(4, app.buffer.line_count)):
                    for seg in editor.render_line(row):
                        bg = getattr(seg.style, "bgcolor", None)
                        assert bg is not None, \
                            f"bg=None cell at row {row}: {seg.text!r}"
                        self.assertIn(repr(bg), allowed)
                        checked += 1
                self.assertGreater(checked, 12)


class ManualTests(unittest.IsolatedAsyncioTestCase):
    async def test_f8_opens_manual_and_esc_closes(self):
        from textual.widgets import Markdown, Static

        from yate.editor_view.manual import load_manual_markdown

        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            await pilot.press("f8")
            await pilot.pause()
            self.assertIsInstance(app.screen, ManualScreen)
            md = app.screen.query_one("#manual-md", Markdown)
            # F8 opens the default (english) manual
            self.assertEqual(md.source, load_manual_markdown("en"))
            # the loading placeholder is hidden once content is in
            loading = app.screen.query_one("#manual-loading", Static)
            self.assertFalse(loading.display)
            # theme is switched *before* the screen is pushed
            self.assertEqual(app.theme, "catppuccin-mocha")
            # f8 again must not stack a second viewer
            await pilot.press("f8")
            await pilot.pause()
            self.assertEqual(len(app.screen_stack), 2)
            await pilot.press("escape")
            await pilot.pause()
            self.assertNotIsInstance(app.screen, ManualScreen)
            # ... and the previous theme is restored afterwards
            self.assertEqual(app.theme, "textual-dark")

    async def test_manual_command_selects_language(self):
        from textual.widgets import Markdown

        from yate.editor_view.manual import load_manual_markdown

        for cmd_arg, lang in (("zh", "zh"), ("en", "en"), ("bogus", "en")):
            with self.subTest(cmd=cmd_arg):
                app = YateApp()
                async with app.run_test(size=(100, 30)) as pilot:
                    await pilot.pause()
                    app.run_command(f"manual {cmd_arg}".strip())
                    await pilot.pause()
                    self.assertIsInstance(app.screen, ManualScreen)
                    md = app.screen.query_one("#manual-md", Markdown)
                    self.assertEqual(md.source, load_manual_markdown(lang))

    async def test_both_language_files_bundled(self):
        from yate.editor_view.manual import load_manual_markdown

        for lang in ("en", "zh"):
            with self.subTest(lang=lang):
                text = load_manual_markdown(lang)
                self.assertGreater(len(text), 1000)
                self.assertTrue(text.lstrip().startswith("# yate"))

    async def test_manual_search_filters_and_cycles_matches(self):
        from textual.containers import Horizontal
        from textual.widgets import Input, Markdown, Static

        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            await pilot.press("f8")
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, ManualScreen)
            bar = screen.query_one("#manual-search-bar", Horizontal)
            field = screen.query_one("#manual-search-input", Input)
            status = screen.query_one("#manual-search-status", Static)
            md = screen.query_one("#manual-md", Markdown)
            self.assertFalse(bar.display)
            # ctrl+f reveals the search bar and focuses it
            await pilot.press("ctrl+f")
            await pilot.pause()
            self.assertTrue(bar.display)
            self.assertIs(screen.focused, field)
            # typing live-marks every block containing the query
            await pilot.press("y", "a", "t", "e")
            await pilot.pause()
            private = cast(Any, screen)
            self.assertGreaterEqual(len(private._hits), 2)
            self.assertEqual(private._hit_index, 0)
            self.assertEqual(len(list(md.query(".manual-hit-current"))), 1)
            self.assertGreaterEqual(len(list(md.query(".manual-hit"))), 1)
            self.assertIn("1/", str(status.content))
            # enter advances to the next match, shift+enter goes back
            await pilot.press("enter")
            await pilot.pause()
            self.assertEqual(private._hit_index, 1)
            self.assertIn("2/", str(status.content))
            await pilot.press("shift+enter")
            await pilot.pause()
            self.assertEqual(private._hit_index, 0)
            # escape while typing closes only the bar (manual stays open)…
            await pilot.press("escape")
            await pilot.pause()
            self.assertFalse(bar.display)
            self.assertIsInstance(app.screen, ManualScreen)
            # …and n/N repeat the last search with highlights still present
            await pilot.press("n")
            await pilot.pause()
            self.assertEqual(private._hit_index, 1)
            await pilot.press("N")
            await pilot.pause()
            self.assertEqual(private._hit_index, 0)
            # escape with the bar closed dismisses the manual itself
            await pilot.press("escape")
            await pilot.pause()
            self.assertNotIsInstance(app.screen, ManualScreen)

    async def test_manual_search_no_matches_then_slash_reopens(self):
        from textual.containers import Horizontal
        from textual.widgets import Input, Markdown, Static

        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            await pilot.press("f8")
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, ManualScreen)
            # "/" (textual key name "slash") also opens the search bar
            await pilot.press("slash")
            await pilot.pause()
            bar = screen.query_one("#manual-search-bar", Horizontal)
            field = screen.query_one("#manual-search-input", Input)
            status = screen.query_one("#manual-search-status", Static)
            md = screen.query_one("#manual-md", Markdown)
            self.assertTrue(bar.display)
            self.assertIs(screen.focused, field)
            # a query present nowhere reports "no matches" and tints nothing
            await pilot.press("z", "q", "z", "q", "w", "x")
            await pilot.pause()
            private = cast(Any, screen)
            self.assertEqual(private._hits, [])
            self.assertEqual(private._hit_index, -1)
            self.assertEqual(len(list(md.query(".manual-hit"))), 0)
            self.assertIn("no matches", str(status.content))
            # clearing the query removes the error state
            await pilot.press(*(("backspace",) * 10))
            await pilot.pause()
            self.assertEqual(field.value, "")
            self.assertEqual(private._hits, [])
            self.assertIn("type to search", str(status.content))
            self.assertIsInstance(app.screen, ManualScreen)


class AsyncBackgroundTests(unittest.IsolatedAsyncioTestCase):
    """Blocking work (manual render, shell, file index) stays off the loop."""

    async def test_manual_paints_before_content_loads(self):
        from unittest.mock import patch

        from textual.widgets import Markdown, Static

        from yate.editor_view import manual as manual_mod

        original = manual_mod.load_manual_markdown

        def slow_load(lang: str) -> str:
            time.sleep(1.5)
            return original(lang)

        app = YateApp()
        with patch(
            "yate.editor_view.manual.load_manual_markdown", side_effect=slow_load
        ):
            async with app.run_test(size=(100, 30)) as pilot:
                await pilot.pause()
                await pilot.press("f8")
                # while the worker thread is still reading: screen + loading
                # line are already on screen, the markdown itself is empty
                await pilot.pause(0.15)
                self.assertIsInstance(app.screen, ManualScreen)
                md = app.screen.query_one("#manual-md", Markdown)
                loading = app.screen.query_one("#manual-loading", Static)
                self.assertEqual(md.source, "")
                self.assertTrue(loading.display)
                # content then arrives without dismissing the screen
                loaded = await wait_until(
                    pilot,
                    lambda: bool(md.source) and not loading.display,
                    timeout=30.0,
                )
                self.assertTrue(loaded)
                self.assertEqual(md.source, original("en"))
                self.assertFalse(loading.display)
                self.assertIsInstance(app.screen, ManualScreen)

    async def test_shell_command_runs_without_freezing_ui(self):
        from unittest.mock import patch

        from yate.editor_view.modals import OutputScreen
        from yate.services.shell import ShellResult

        def slow_shell(command: str, cwd: object = None,
                       timeout: float = 60.0) -> ShellResult:
            # long enough that headless message-pump slowness cannot let it
            # finish before the responsiveness assertions run
            time.sleep(2.0)
            return ShellResult(command, 0, "yate-async-marker", Path.cwd())

        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            prompt_bar = app.prompt_bar
            assert prompt_bar is not None
            with patch("yate.app.run_shell", side_effect=slow_shell):
                # F2 opens the shell prompt in vsc mode (":" is vim-only)
                await pilot.press("f2")
                self.assertEqual(prompt_bar.active_mode, "shell")
                for ch in "echo hi":
                    await pilot.press(ch)
                await pilot.press("enter")
                # command dispatched: prompt closed, no output screen yet,
                # focus back in the editor while the thread is running
                await pilot.pause(0.15)
                self.assertEqual(len(app.screen_stack), 1)
                self.assertIs(app.focused, app.editor_view)
                # the TUI stays responsive: F1 help opens over the running job
                await pilot.press("f1")
                await pilot.pause(0.1)
                self.assertEqual(len(app.screen_stack), 2)
                await pilot.press("escape")
                await pilot.pause(0.1)
            # the output screen appears when the worker finishes
            shown = await wait_until(
                pilot, lambda: isinstance(app.screen, OutputScreen),
                timeout=10.0,
            )
            self.assertTrue(shown)
            out = cast(OutputScreen, app.screen)
            self.assertIn("yate-async-marker", out.output_text)
            self.assertEqual(out.exit_code, 0)

    async def test_file_palette_indexes_in_background(self):
        from unittest.mock import patch

        from rich.text import Text
        from textual.widgets import Static

        from yate.editor_view.palette import PaletteScreen
        from yate.services.workspace import Workspace

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "notes.txt").write_text("x\n", encoding="utf-8")
            app = YateApp(target=root)

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
                    self.assertIsInstance(app.screen, PaletteScreen)
                    palette = cast(PaletteScreen, app.screen)
                    self.assertIn("indexing", status_text())
                    done = await wait_until(
                        pilot, lambda: palette.filtered_count == 1,
                        timeout=10.0,
                    )
                    self.assertTrue(done)
                    self.assertIn("notes.txt", status_text())


class WindowFocusTests(unittest.IsolatedAsyncioTestCase):
    """Pane switching between explorer and editor."""

    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        (root / "alpha.txt").write_text("hello\n", encoding="utf-8")
        self.root = root

    async def test_vsc_chords_focus_panes(self):
        app = YateApp(target=self.root)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            # initial focus is the editor; ctrl+shift+e moves to the explorer
            self.assertIs(app.focused, app.editor_view)
            await pilot.press("ctrl+shift+e")
            await pilot.pause()
            self.assertIs(app.focused, app.explorer_tree)
            # vscode-style: ctrl+1 focuses the editor again
            await pilot.press("ctrl+1")
            await pilot.pause()
            self.assertIs(app.focused, app.editor_view)
            # ... and ctrl+shift+e focuses the explorer once more
            await pilot.press("ctrl+shift+e")
            await pilot.pause()
            self.assertIs(app.focused, app.explorer_tree)
            await pilot.press("ctrl+1")
            await pilot.pause()
            self.assertIs(app.focused, app.editor_view)

    async def test_vim_ctrl_w_prefix_switches_panes(self):
        app = YateApp(target=self.root)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            app.select_keymap("vim")
            await pilot.pause()
            # ctrl+w arms the prefix, h goes to the left pane (explorer)
            await pilot.press("ctrl+w")
            await pilot.pause()
            self.assertTrue(app.window_pending)
            await pilot.press("h")
            await pilot.pause()
            self.assertFalse(app.window_pending)
            self.assertIs(app.focused, app.explorer_tree)
            # l goes back to the right pane (editor)
            await pilot.press("ctrl+w")
            await pilot.press("l")
            await pilot.pause()
            self.assertIs(app.focused, app.editor_view)
            # ctrl+w ctrl+w cycles between the two panes
            await pilot.press("ctrl+w")
            await pilot.press("ctrl+w")
            await pilot.pause()
            self.assertIs(app.focused, app.explorer_tree)

    async def test_vim_window_prefix_cancelled_by_other_keys(self):
        app = YateApp(target=self.root)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            app.select_keymap("vim")
            await pilot.pause()
            await pilot.press("ctrl+w")
            await pilot.pause()
            self.assertTrue(app.window_pending)
            # an unrelated key cancels the prefix and is processed normally
            before = app.buffer.lines[0]
            await pilot.press("x")
            await pilot.pause()
            self.assertFalse(app.window_pending)
            self.assertEqual(app.buffer.lines[0], before[1:])  # x deleted a char

    async def test_vim_insert_mode_ctrl_w_not_intercepted(self):
        app = YateApp(target=self.root)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            app.select_keymap("vim")
            await pilot.pause()
            await pilot.press("i")  # INSERT
            await pilot.pause()
            await pilot.press("ctrl+w")
            await pilot.pause()
            self.assertFalse(app.window_pending)


class BufferCompletionTests(unittest.IsolatedAsyncioTestCase):
    """Fallback completions (buffer words + paths) when no LSP is active."""

    async def test_buffer_words_complete_without_lsp(self):
        with TemporaryDirectory() as tmp:
            doc = Path(tmp) / "note.txt"
            # "alpha" appears twice so it surfaces as a completion candidate;
            # the half-typed word on the cursor line is excluded.
            doc.write_text(
                "alpha bravo charlie\nalpha delta\n", encoding="utf-8"
            )
            app = YateApp(target=doc)
            async with app.run_test(size=(100, 30)) as pilot:
                await pilot.pause()
                popup = app.completion_popup
                assert popup is not None
                # no language server for .txt
                self.assertFalse(app.lsp.supports(app.doc))
                # move to a new line and start typing "al"
                app.buffer.move_doc_end()
                app.buffer.insert_text("\nal")
                # cursor now sits at the end of the freshly typed "al"
                app.ui_refresh()
                await pilot.press("ctrl+space")
                shown = await wait_until(pilot, lambda: popup.is_open)
                self.assertTrue(shown)
                labels = [item.label for item in popup.items]
                self.assertIn("alpha", labels)
                # "al" prefix excludes the other words
                self.assertNotIn("bravo", labels)

    async def test_buffer_completion_accepts_word(self):
        with TemporaryDirectory() as tmp:
            doc = Path(tmp) / "note.txt"
            doc.write_text("banana bandana\n", encoding="utf-8")
            app = YateApp(target=doc)
            async with app.run_test(size=(100, 30)) as pilot:
                await pilot.pause()
                popup = app.completion_popup
                assert popup is not None
                app.buffer.move_doc_end()
                app.buffer.insert_text("\nba")
                app.ui_refresh()
                await pilot.press("ctrl+space")
                await wait_until(pilot, lambda: popup.is_open)
                # pick the first match and accept with tab
                await pilot.press("tab")
                await pilot.pause()
                self.assertFalse(popup.is_open)
                # "ba" replaced by the accepted word
                last_line = app.buffer.lines[-1]
                self.assertTrue(last_line.startswith("ban"))


class PaletteTabCompletionTests(unittest.IsolatedAsyncioTestCase):
    async def test_tab_cycles_and_single_match_auto_chooses(self):
        from yate.editor_view.palette import PaletteScreen

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
            self.assertEqual(screen.cursor_index, (before + 1) % screen.filtered_count)
            self.assertIsInstance(app.screen, PaletteScreen)
            # narrow to a single unique match: tab chooses it immediately
            for ch in "theme":
                await pilot.press(ch)
            await pilot.pause()
            self.assertEqual(screen.filtered_count, 1)
            await pilot.press("tab")
            await pilot.pause()
            # palette dismissed and :theme ran (prints theme info)
            self.assertNotIsInstance(app.screen, PaletteScreen)


class CommandTabCompletionTests(unittest.IsolatedAsyncioTestCase):
    async def test_tab_completes_unique_command_name(self):
        app = YateApp(keymap="vim")
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.press(":")
            await pilot.pause()
            # "writ" -> only "write" matches
            await pilot.press(*"writ")
            await pilot.pause()
            await pilot.press("tab")
            await pilot.pause()
            inp = app.prompt_bar.input if app.prompt_bar else None
            assert inp is not None
            self.assertEqual(inp.value, "write")

    async def test_tab_cycles_multiple_command_matches(self):
        app = YateApp(keymap="vim")
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.press(":")
            await pilot.pause()
            # "w" matches several commands (w / words / wq / write ...); the
            # common prefix is just "w" so tab cycles through the matches.
            await pilot.press("w")
            await pilot.pause()
            inp = app.prompt_bar.input if app.prompt_bar else None
            assert inp is not None
            matches = app.prompt_completions("w", "command")
            self.assertGreater(len(matches), 1)
            await pilot.press("tab")
            await pilot.pause()
            first = inp.value
            self.assertIn(first, matches)
            await pilot.press("tab")
            await pilot.pause()
            self.assertIn(inp.value, matches)
            self.assertNotEqual(inp.value, first)

    async def test_tab_completes_theme_argument(self):
        app = YateApp(keymap="vim")
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.press(":")
            await pilot.pause()
            await pilot.press(*"theme mac")
            await pilot.pause()
            await pilot.press("tab")
            await pilot.pause()
            inp = app.prompt_bar.input if app.prompt_bar else None
            assert inp is not None
            self.assertTrue(inp.value.endswith("macchiato"))

    async def test_tab_completes_path_for_edit_command(self):
        with TemporaryDirectory() as tmp:
            (Path(tmp) / "alpha.py").write_text("x\n", encoding="utf-8")
            (Path(tmp) / "beta.py").write_text("x\n", encoding="utf-8")
            app = YateApp(keymap="vim", target=Path(tmp))
            async with app.run_test(size=(100, 30)) as pilot:
                await pilot.press(":")
                await pilot.pause()
                await pilot.press(*"e al")
                await pilot.pause()
                await pilot.press("tab")
                await pilot.pause()
                inp = app.prompt_bar.input if app.prompt_bar else None
                assert inp is not None
                self.assertTrue(inp.value.endswith("alpha.py"))


class FiletypeCommandTests(unittest.IsolatedAsyncioTestCase):
    """:set filetype= / :filetype manual syntax selection."""

    async def test_set_filetype_by_name_or_extension_and_auto_reset(self):
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            doc = app.doc
            self.assertIsNone(doc.path)
            self.assertEqual(doc.filetype, "plaintext")

            app.run_command("set filetype=python")  # language name
            self.assertEqual(doc.filetype_override, "py")
            self.assertEqual(doc.filetype, "py")

            app.run_command("ft .rs")               # alias + dot prefix
            self.assertEqual(doc.filetype, "rs")

            app.run_command("language typescript")  # vscode-style name
            self.assertEqual(doc.filetype, "ts")

            app.run_command("set language=auto")    # back to detection
            self.assertIsNone(doc.filetype_override)
            self.assertEqual(doc.filetype, "plaintext")
            await pilot.pause()

    async def test_unknown_filetype_is_kept_without_highlighter(self):
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            app.run_command("set ft=zig")
            self.assertEqual(app.doc.filetype_override, "zig")
            self.assertEqual(app.doc.filetype, "zig")
            app.run_command("filetype auto")
            self.assertIsNone(app.doc.filetype_override)
            await pilot.pause()

    async def test_highlighting_follows_the_override(self):
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            editor = app.editor_view
            assert editor is not None
            hl_view = cast(Any, editor)
            app.buffer.insert_text("def foo():\n    pass\n")
            await pilot.pause()
            # Plain-text detection for an unnamed buffer -> no tokens.
            self.assertEqual(hl_view._hl_filetype, "plaintext")

            app.run_command("set filetype=python")
            changed = await wait_until(
                pilot, lambda: hl_view._hl_filetype == "py", timeout=5.0
            )
            self.assertTrue(changed)
            pairs = [
                (t.kind, "def foo():"[t.start:t.end])
                for t in hl_view._tokens_for(0)
            ]
            self.assertIn(("keyword", "def"), pairs)
            self.assertIn(("function", "foo"), pairs)

    async def test_tab_completions_for_filetype(self):
        app = YateApp(keymap="vim")
        async with app.run_test(size=(100, 30)) as pilot:
            self.assertEqual(
                app.prompt_completions("set filetype=pyt", "command"),
                ["set filetype=python"],
            )
            # "r" prefix matches both the "rs" extension key and the
            # "rust" language name.
            self.assertEqual(
                sorted(app.prompt_completions("filetype r", "command")),
                ["filetype rs", "filetype rust"],
            )
            vals = app.prompt_completions("set ft=", "command")
            self.assertIn("set ft=auto", vals)
            self.assertIn("set ft=python", vals)
            self.assertEqual(
                app.prompt_completions("set file", "command"),
                ["set filetype"],
            )
            await pilot.pause()


class GotoLineTests(unittest.IsolatedAsyncioTestCase):
    """Bare-number command line input (vim :42 / VS Code Ctrl+G)."""

    @staticmethod
    def _seed(app: YateApp, lines: int = 6) -> None:
        app.buffer.set_text("\n".join(f"line {i + 1}" for i in range(lines)))
        app.buffer.set_cursor((0, 0))

    async def test_bare_number_jumps_to_line(self):
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            self._seed(app)
            app.run_command("4")
            await pilot.pause()
            self.assertEqual(app.buffer.row, 3)  # 1-based input -> 0-based row
            self.assertIsNone(app.buffer.anchor)

    async def test_line_number_is_clamped(self):
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            self._seed(app)
            app.run_command("999")
            await pilot.pause()
            self.assertEqual(app.buffer.row, 5)
            app.run_command("0")
            await pilot.pause()
            self.assertEqual(app.buffer.row, 0)

    async def test_signed_numbers_are_relative(self):
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            self._seed(app)
            app.buffer.set_cursor((0, 0))
            app.run_command("+2")
            await pilot.pause()
            self.assertEqual(app.buffer.row, 2)
            app.run_command("-1")
            await pilot.pause()
            self.assertEqual(app.buffer.row, 1)

    async def test_non_numeric_unknown_command_still_warns(self):
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            self._seed(app)
            app.run_command("12abc")
            await pilot.pause()
            self.assertEqual(app.buffer.row, 0)  # did not jump
            prompt_bar = app.prompt_bar
            assert prompt_bar is not None
            msg = "".join(
                seg.text for seg in prompt_bar.message.render_line(0)
            )
            self.assertIn("not an editor command", msg)

    async def test_ctrl_g_opens_goto_prompt_in_vsc_keymap(self):
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            self._seed(app)
            prompt_bar = app.prompt_bar
            assert prompt_bar is not None
            await pilot.press("ctrl+g")
            await pilot.pause()
            self.assertEqual(prompt_bar.active_mode, "goto")
            await pilot.press("2", "enter")
            await pilot.pause()
            self.assertIsNone(prompt_bar.active_mode)
            self.assertEqual(app.buffer.row, 1)
            self.assertIs(app.focused, app.editor_view)

    async def test_ctrl_g_opens_goto_prompt_in_vim_normal_mode(self):
        app = YateApp(keymap="vim")
        async with app.run_test(size=(100, 30)) as pilot:
            self._seed(app)
            prompt_bar = app.prompt_bar
            assert prompt_bar is not None
            await pilot.press("ctrl+g")
            await pilot.pause()
            self.assertEqual(prompt_bar.active_mode, "goto")
            await pilot.press("5", "enter")
            await pilot.pause()
            self.assertEqual(app.buffer.row, 4)

    async def test_goto_prompt_rejects_non_numeric(self):
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            self._seed(app)
            app.goto_prompt()
            await pilot.pause()
            prompt_bar = app.prompt_bar
            assert prompt_bar is not None
            prompt_bar.input.value = "abc"
            await pilot.press("enter")
            await pilot.pause()
            self.assertEqual(app.buffer.row, 0)
            msg = "".join(
                seg.text for seg in prompt_bar.message.render_line(0)
            )
            self.assertIn("not a line number", msg)


class LspUiTests(unittest.IsolatedAsyncioTestCase):
    """Completion popup + diagnostic rendering with an injected fake LSP."""

    def _install_fake_server(
        self, app: YateApp, completions: list[dict[str, Any]] | None = None
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

        app.lsp.register_server(ServerConfig(
            name="python", command="fake", filetypes=["py"],
        ))
        # factory must be installed on the manager after registration; the
        # manager keeps it independent of config replacement
        app.lsp.set_client_factory(factory)
        return created

    async def test_completion_popup_navigate_accept_and_ctrl_space(self):
        with TemporaryDirectory() as tmp:
            py = Path(tmp) / "m.py"
            py.write_text("ba\n", encoding="utf-8")
            app = YateApp(target=py)
            async with app.run_test(size=(100, 30)) as pilot:
                await pilot.pause()
                self._install_fake_server(app)
                app.ui_refresh()  # schedules didOpen on the freshly registered server
                await pilot.pause()

                def is_ready() -> bool:
                    state = app.lsp.state_for_doc(app.doc)
                    return state is not None and state.value == "ready"

                ready = await wait_until(pilot, is_ready)
                self.assertTrue(ready)
                popup = app.completion_popup
                assert popup is not None
                # cursor sits at doc start after open; move to end of "ba"
                app.buffer.cursor = (0, 2)
                app.ui_refresh()
                # manual trigger via ctrl+space at the end of "ba"
                await pilot.press("ctrl+space")
                shown = await wait_until(pilot, lambda: popup.is_open)
                self.assertTrue(shown)
                self.assertEqual(popup.item_count, 3)
                first = popup.selected()
                assert first is not None
                self.assertEqual(first.label, "barbell")
                # down wraps through the list, esc closes
                await pilot.press("down")
                second = popup.selected()
                assert second is not None
                self.assertEqual(second.label, "baritone")
                await pilot.press("escape")
                self.assertFalse(popup.is_open)
                # reopen and accept the second entry with tab
                await pilot.press("ctrl+space")
                await wait_until(pilot, lambda: popup.is_open)
                await pilot.press("down", "tab")
                await pilot.pause()
                self.assertFalse(popup.is_open)
                self.assertEqual(app.buffer.lines[0], "baritone")
                self.assertTrue(app.doc.modified)

    async def test_diagnostic_render_status_echo_and_command(self):
        from yate.editor_lsp import protocol
        from yate.editor_view.modals import OutputScreen

        with TemporaryDirectory() as tmp:
            py = Path(tmp) / "diag.py"
            py.write_text("x = 1\n", encoding="utf-8")
            app = YateApp(target=py)
            async with app.run_test(size=(100, 30)) as pilot:
                await pilot.pause()
                created = self._install_fake_server(app)
                app.ui_refresh()
                await pilot.pause()
                await wait_until(pilot, lambda: bool(created and created[0].opened))
                fake = created[0]
                uri = protocol.path_to_uri(py.resolve())
                fake.publish_diagnostics(app.lsp, uri, [
                    {"range": {"start": {"line": 0, "character": 0},
                               "end": {"line": 0, "character": 5}},
                     "severity": 1, "message": "undefined name 'x'",
                     "source": "pyright"},
                ])
                await pilot.pause()
                editor = app.editor_view
                assert editor is not None
                line0 = "".join(seg.text for seg in editor.render_line(0))
                self.assertIn("✖", line0)  # gutter mark
                underlined = [
                    seg for seg in editor.render_line(0)
                    if seg.style is not None and seg.style.underline
                ]
                self.assertTrue(underlined)
                # status bar carries the error count
                status_bar = app.status_bar
                assert status_bar is not None
                self.assertIn("✖ 1", plain_text(status_bar.content))
                # message line echoes the diagnostic under the cursor
                prompt_bar = app.prompt_bar
                assert prompt_bar is not None
                app.ui_refresh()
                self.assertIn(
                    "undefined name", plain_text(prompt_bar.message.content)
                )
                # :diagnostics opens the listing screen
                app.run_command("diagnostics")
                await pilot.pause()
                screen = app.screen
                self.assertIsInstance(screen, OutputScreen)
                self.assertIn("undefined name", cast(OutputScreen, screen).output_text)

    async def test_builtin_python_extension_loads_cleanly(self):
        # The auto-loaded extension registers a (disabled) python server and
        # setup must neither print nor spawn nor record an error.
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            self.assertIn("python", app.lsp.config_names())
            rec = next(r for r in app.extension_loader.loaded
                       if r.name == "python_lsp")
            self.assertIsNone(rec.error)

    async def test_rc_configured_server_auto_activates_on_matching_file(self):
        from yate.config import LanguageServerSpec, YateConfig

        with TemporaryDirectory() as tmp:
            rs = Path(tmp) / "main.rs"
            rs.write_text("fn main() {}\n", encoding="utf-8")
            config = YateConfig(language_servers=[LanguageServerSpec(
                name="rc-rust",
                command="fake-rust-analyzer",
                filetypes=["rs"],
                language_ids={"rs": "rust"},
                root_markers=["Cargo.toml", ".git"],
            )])
            app = YateApp(target=rs, config=config)
            created: list[Any] = []

            def factory(config: Any, root: Any) -> Any:
                return _RcClientShim(created, config, root)

            # factory must be in place before on_mount registers/opens docs
            app.lsp.set_client_factory(factory)
            async with app.run_test(size=(100, 30)) as pilot:
                opened = await wait_until(pilot, lambda: app.lsp.is_open(app.doc))
                self.assertTrue(opened)
                registered = app.lsp.config_for("rs")
                assert registered is not None
                self.assertEqual(registered.name, "rc-rust")
                state = app.lsp.state_for_doc(app.doc)
                self.assertIsNotNone(state)
                assert state is not None
                self.assertEqual(state.value, "ready")
                self.assertEqual(len(created), 1)
                params = created[0].opened[0]
                self.assertEqual(
                    params["textDocument"]["languageId"], "rust"
                )

    async def test_rc_configured_server_activates_on_later_open(self):
        from yate.config import LanguageServerSpec, YateConfig

        with TemporaryDirectory() as tmp:
            rs = Path(tmp) / "later.rs"
            rs.write_text("let x = 1;\n", encoding="utf-8")
            config = YateConfig(language_servers=[LanguageServerSpec(
                name="rc-rust-late", command="fake-rust", filetypes=["rs"],
            )])
            app = YateApp(config=config)
            created: list[Any] = []

            def factory(config: Any, root: Any) -> Any:
                return _RcClientShim(created, config, root)

            app.lsp.set_client_factory(factory)
            async with app.run_test(size=(100, 30)) as pilot:
                await pilot.pause()
                # unnamed scratch buffer: registered but nothing spawned
                self.assertEqual(created, [])
                self.assertFalse(app.lsp.is_open(app.doc))
                registered = app.lsp.config_for("rs")
                assert registered is not None
                self.assertEqual(registered.name, "rc-rust-late")
                # omitted root_markers fall back to the built-in defaults
                from yate.editor_lsp.client import DEFAULT_ROOT_MARKERS
                self.assertEqual(
                    registered.root_markers, list(DEFAULT_ROOT_MARKERS)
                )
                # opening the matching file activates the server
                app.open_path(rs)
                await pilot.pause()
                activated = await wait_until(
                    pilot, lambda: bool(created) and created[0].opened
                )
                self.assertTrue(activated)
                self.assertTrue(app.lsp.is_open(app.doc))

    async def test_rc_python_entry_overrides_builtin_extension(self):
        # The bundled python_lsp extension registers a "python" server with
        # an empty command (YATE_PYTHON_LSP=off for the suite). A same-named
        # rc entry registered after extensions must replace it: opening a
        # .py file then talks to the rc server, not the disabled builtin one.
        from yate.config import LanguageServerSpec, YateConfig

        with TemporaryDirectory() as tmp:
            py = Path(tmp) / "app.py"
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
            app = YateApp(target=py, config=config)
            created: list[Any] = []

            def factory(config: Any, root: Any) -> Any:
                return _RcClientShim(created, config, root)

            app.lsp.set_client_factory(factory)
            async with app.run_test(size=(100, 30)) as pilot:
                registered = await wait_until(
                    pilot, lambda: app.lsp.is_open(app.doc)
                )
                self.assertTrue(registered)
                cfg = app.lsp.config_for("py")
                assert cfg is not None
                self.assertEqual(cfg.command, "fake-pyright")
                self.assertEqual(cfg.args, ["--stdio"])
                self.assertEqual(cfg.env, {"FAKE_ENV": "1"})
                self.assertEqual(cfg.root_markers, ["pyproject.toml", ".git"])
                self.assertEqual(
                    cfg.initialization_options, {"diagnostics": True}
                )
                self.assertEqual(
                    cfg.settings, {"python": {"version": "3"}}
                )
                self.assertEqual(cfg.language_id("pyi"), "python")
                self.assertEqual(len(created), 1)
                params = created[0].opened[0]
                self.assertEqual(
                    params["textDocument"]["languageId"], "python"
                )
                # the disabled builtin registration left no failed client
                state = app.lsp.state_for_doc(app.doc)
                assert state is not None
                self.assertEqual(state.value, "ready")


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


class _FakePty:
    """In-memory PTY substitute used by the terminal UI tests."""

    instances: list["_FakePty"] = []

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


class TerminalUiTests(unittest.IsolatedAsyncioTestCase):
    async def _press_toggle(self, pilot: Any) -> None:
        # Textual key names for grave vary; the app accepts both spellings.
        await pilot.press("ctrl+`")

    def test_nul_byte_from_windows_ctrl_grave_matches_toggle(self) -> None:
        # Windows conhost encodes Ctrl+grave as a NUL byte (ToUnicodeEx
        # yields no character); Textual names that key "ctrl+@", and it
        # must be one of the accepted toggle keys.
        from textual._xterm_parser import XTermParser

        from yate.editor_view.terminal import TOGGLE_KEYS

        names = [
            getattr(m, "key", None) for m in XTermParser().feed("\x00")
        ]
        self.assertEqual(names, ["ctrl+@"])
        self.assertIn("ctrl+@", TOGGLE_KEYS)

    async def test_early_pty_output_survives_first_layout(self):
        # Regression: a shell that prints its banner before Textual has
        # laid out the panel used to spawn at the 80x24 fallback size; the
        # first lines were discarded when the viewport shrank on layout.
        class _ImmediatePty(_FakePty):
            async def start(
                self, on_output: Callable[[bytes], None],
                on_exit: Callable[[int | None], None],
            ) -> None:
                await super().start(on_output, on_exit)
                loop = asyncio.get_running_loop()
                loop.call_soon(
                    lambda: on_output(b"YATE_EARLY_BANNER\r\n")
                )

        app = YateApp()
        cast(Any, app)._terminal_factory = _ImmediatePty
        _FakePty.instances = []
        async with app.run_test(size=(100, 30)) as pilot:
            panel = app.terminal_panel
            assert panel is not None
            await self._press_toggle(pilot)

            def banner_visible() -> bool:
                return "YATE_EARLY_BANNER" in "".join(
                    cell.char
                    for row in panel.view.emulator.view_lines(0)
                    for cell in row
                )

            self.assertTrue(await wait_until(pilot, banner_visible))
            proc = _FakePty.instances[0]
            # spawned at the laid-out size, not the 24-row fallback
            self.assertLess(proc.rows, 24)
            self.assertEqual(proc.cols, 100)

    async def test_ctrl_grave_toggles_focuses_and_forwards(self):
        app = YateApp()
        cast(Any, app)._terminal_factory = _FakePty
        _FakePty.instances = []
        async with app.run_test(size=(100, 30)) as pilot:
            panel = app.terminal_panel
            assert panel is not None
            self.assertFalse(panel.display)

            await self._press_toggle(pilot)
            shown = await wait_until(pilot, lambda: panel.view.proc is not None)
            self.assertTrue(shown)
            self.assertTrue(panel.display)
            self.assertIs(app.focused, panel.view)
            proc = _FakePty.instances[0]
            self.assertTrue(proc.started)
            self.assertTrue(proc.argv)  # a default shell was resolved
            self.assertEqual(proc.cols, 100)
            self.assertGreaterEqual(proc.rows, 8)

            # PTY output lands in the emulator and renders
            proc.emit_output(b"YATE_FAKE_OUTPUT\r\n")
            await pilot.pause()
            painted = "".join(
                cell.char
                for row in panel.view.emulator.view_lines(0)
                for cell in row
            )
            self.assertIn("YATE_FAKE_OUTPUT", painted)

            # keys typed in the panel are forwarded byte-for-byte
            await pilot.press("l", "s")
            self.assertEqual(b"".join(proc.sent), b"ls")

            # the dock hugs the bottom, above the status/prompt strip
            bottom = app.query_one("#bottom")
            self.assertEqual(bottom.region.bottom, 30)
            self.assertLessEqual(panel.region.bottom, bottom.region.y)

            # toggle again hides it and returns focus to the editor
            await self._press_toggle(pilot)
            await pilot.pause()
            self.assertFalse(panel.display)
            self.assertIs(app.focused, app.editor_view)

            # reopening reuses the still-alive shell process
            await self._press_toggle(pilot)
            await wait_until(pilot, lambda: cast(Any, app)._terminal_visible)
            self.assertTrue(panel.display)
            self.assertIs(cast(Any, panel.view).proc, proc)

    async def test_real_terminal_grave_key_names_toggle_panel(self):
        # Ctrl+grave is the NUL byte on Windows conhost / legacy xterm
        # (ToUnicodeEx yields no character), so Textual names it
        # "ctrl+@"; under the kitty keyboard protocol it is named
        # "ctrl+grave_accent". Neither used to match TOGGLE_KEYS, so the
        # panel could not be closed from a real Windows terminal.
        for close_key in ("ctrl+@", "ctrl+grave_accent"):
            app = YateApp()
            cast(Any, app)._terminal_factory = _FakePty
            _FakePty.instances = []
            async with app.run_test(size=(100, 30)) as pilot:
                panel = app.terminal_panel
                assert panel is not None
                view = panel.view

                await pilot.press("ctrl+`")
                await wait_until(pilot, lambda: view.proc is not None)
                self.assertTrue(panel.display)
                self.assertIs(app.focused, view)
                proc = _FakePty.instances[0]

                # the real key name closes the panel while the terminal
                # has focus, and is not forwarded as a NUL byte
                await pilot.press(close_key)
                await pilot.pause()
                self.assertFalse(panel.display, close_key)
                self.assertNotIn(b"\x00", b"".join(proc.sent))
                self.assertIs(app.focused, app.editor_view)

                # same name reopens it now that the editor has focus
                await pilot.press(close_key)
                await wait_until(
                    pilot, lambda: cast(Any, app)._terminal_visible)
                self.assertTrue(panel.display, close_key)

    async def test_term_command_exit_and_restart(self):
        app = YateApp(keymap="vim")  # ":" ex line is vim-only
        cast(Any, app)._terminal_factory = _FakePty
        _FakePty.instances = []
        async with app.run_test(size=(100, 30)) as pilot:
            panel = app.terminal_panel
            assert panel is not None

            # :term opens the panel
            await pilot.press("colon")
            for ch in "term":
                await pilot.press(ch)
            await pilot.press("enter")
            shown = await wait_until(pilot, lambda: panel.view.proc is not None)
            self.assertTrue(shown)
            proc = _FakePty.instances[0]
            self.assertIn("running", panel.header_text())

            # when the shell exits the panel shows the state and a hint
            proc.exit(0)
            await pilot.pause()
            self.assertTrue(panel.view.dead)
            self.assertIn("exited", panel.header_text())

            # any keypress revives the shell via the factory
            await pilot.press("a")
            revived = await wait_until(
                pilot,
                lambda: len(_FakePty.instances) == 2
                and cast(Any, panel.view).proc is _FakePty.instances[1]
                and bool(_FakePty.instances[1].started),
            )
            self.assertTrue(revived)
            self.assertEqual(len(_FakePty.instances), 2)

            # :termclose hides the panel (invoked directly because focus is
            # inside the terminal and the prompt keys would be sent to the PTY)
            app.run_command("termclose")
            await pilot.pause()
            self.assertFalse(panel.display)


class HelpOverlayTests(unittest.IsolatedAsyncioTestCase):
    async def test_help_lists_terminal_key_and_commands(self):
        from yate.editor_view.modals import HelpScreen

        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.press("f1")
            await pilot.pause()
            screen = app.screen
            self.assertIsInstance(screen, HelpScreen)
            body = cast(str, cast(Any, screen)._body().plain)
            self.assertIn("GLOBAL KEYS", body)
            self.assertIn("ctrl+`", body)
            self.assertIn("integrated terminal", body)
            # the terminal commands are registered and listed with : prefix
            self.assertIn(":term", body)
            self.assertIn(":termclose", body)


if __name__ == "__main__":
    unittest.main()
