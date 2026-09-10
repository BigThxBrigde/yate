"""Headless smoke tests for the Textual UI (run via pilot, no real terminal)."""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from textual.strip import Strip

from yate.app import YateApp, textual_key_to_raw
from yate.editor_view.manual import ManualScreen


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
            # typing dismisses the welcome page
            await pilot.press("h", "i")
            await pilot.pause()
            self.assertNotIn("\u2588", screen_text())


class PromptBarTests(unittest.IsolatedAsyncioTestCase):
    async def test_command_input_shows_typed_text(self):
        """Regression: focused height-1 Input must not gain a tall border
        that collapses its content region and hides typed characters."""
        app = YateApp()
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
        from textual.widgets import Markdown

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


if __name__ == "__main__":
    unittest.main()
