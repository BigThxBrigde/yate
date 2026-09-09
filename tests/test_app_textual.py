"""Headless smoke tests for the Textual UI (run via pilot, no real terminal)."""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from textual.strip import Strip

from yate.app import YateApp, textual_key_to_raw


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

                # --- command prompt: switch keymap to vim
                await pilot.press("colon")
                self.assertEqual(prompt_bar.active_mode, "command")
                for ch in "set keymap=vim":
                    await pilot.press(ch)
                await pilot.press("enter")
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

                # switch theme via :theme latte, expect active theme to change
                await pilot.press("colon")
                for ch in "theme latte":
                    await pilot.press(ch)
                await pilot.press("enter")
                await pilot.pause()
                self.assertEqual(theme.active().name, "latte")
                theme.set_theme("mocha")  # restore default for other tests

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
            await pilot.press("ctrl+shift+p")
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


class WelcomeScreenTests(unittest.IsolatedAsyncioTestCase):
    async def test_welcome_shown_then_hidden_on_type(self):
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            editor = app.editor_view
            assert editor is not None
            line2 = "".join(seg.text for seg in editor.render_line(2))
            self.assertIn("yate", line2)
            hints = "".join(seg.text for seg in editor.render_line(5))
            self.assertIn("quick open", hints)
            # typing dismisses the welcome page
            await pilot.press("h", "i")
            await pilot.pause()
            self.assertNotIn("yate", "".join(seg.text for seg in editor.render_line(2)))


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


if __name__ == "__main__":
    unittest.main()
