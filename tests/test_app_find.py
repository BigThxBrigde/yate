"""Prompt bar, command line, goto and completion headless Textual UI tests (run via pilot, no real terminal)."""

# tests legitimately poke at internals:
# pyright: reportPrivateUsage=false

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import cast
from unittest.mock import patch
import pytest
from yate.app import YateApp
from yate.flows.prompt_completion import prompt_completions
from yate.keymaps.vim import VimKeymap
from conftest import message_text, wait_until
from manual_doc_fixture import MANUAL_DOC_FIXTURE

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
            assert vim.op == "d"
            await pilot.press("ctrl+/")
            await pilot.pause()
            assert app.editor.keymaps.name == "vsc"
            assert vim.op is None
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
    re-query the candidates via ``CompletionFlows.after_editor_key``.
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
            matches = prompt_completions(
                "w", "command", commands=app.editor.commands,
                session=app.editor.session, workspace=app.editor.workspace,
            )
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
            def completions(text: str, mode: str) -> list[str]:
                return prompt_completions(
                    text, mode, commands=app.editor.commands,
                    session=app.editor.session,
                    workspace=app.editor.workspace,
                )

            assert completions("set filetype=pyt", "command") == [
                "set filetype=python"
            ]
            # "r" prefix matches the "rb" / "rs" extension keys and the
            # "ruby" / "rust" language names.
            assert sorted(completions("filetype r", "command")) == [
                "filetype rb", "filetype rs", "filetype ruby", "filetype rust"
            ]
            vals = completions("set ft=", "command")
            assert "set ft=auto" in vals
            assert "set ft=python" in vals
            assert completions("set file", "command") == [
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
            app.editor.prompt_flows.goto_prompt()
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
    command: str, cls_name: str, tmp_path: Path
) -> None:
    # The previous command's message used to outlive an overlay command
    # (:manual/:help/:files/:palette): the overlay hides the line while
    # open and the stale text reappeared on close, so success looked
    # silent. Pushing an overlay resets the line to its idle hint.
    async def scenario() -> None:
        app = YateApp()
        # :manual / :changelog render a bundled markdown doc; the small
        # fixture keeps the screen-push semantics identical without paying
        # the real document's parse/render cost (help/files/palette never
        # load a doc, so the patch is inert for them).
        with patch(
            "yate.editor_view.manual.load_doc_markdown",
            return_value=MANUAL_DOC_FIXTURE,
        ):
            async with app.run_test(size=(100, 30)) as pilot:
                await pilot.pause()
                # PaletteScreen builds its file index lazily from the workspace
                # root; without a target it walks Path.cwd() (the whole worktree
                # including .venv).  Redirect to an empty dir so :files/:palette
                # index instantly and only the message behaviour is under test.
                app.editor.workspace.set_root(tmp_path)
                app.editor.message("stale note from before")
                app.editor.run_command(command)
                await pilot.pause()
                assert type(app.screen).__name__ == cls_name
                assert "stale note" not in message_text(app)
                await pilot.press("escape")
                await pilot.pause()
                assert "stale note" not in message_text(app)

    asyncio.run(scenario())


def test_cycle_tab_with_single_tab_is_silent_noop() -> None:
    # N10: cycling with a single tab used to warn on every keypress;
    # it is now a silent no-op -- repeated cycles in both directions
    # leave the message line untouched and never raise.
    async def scenario() -> None:
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            baseline = message_text(app)
            assert "only one tab" not in baseline

            app.editor.run_command("bn")
            await pilot.pause()
            app.editor.run_command("bp")
            await pilot.pause()
            app.editor.document_flows.cycle_tab(1)
            app.editor.document_flows.cycle_tab(-1)
            await pilot.pause()
            assert message_text(app) == baseline
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
            app.editor.document_flows.open_path(beta)
            await pilot.pause()
            app.editor.document_flows.cycle_tab(-1)
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
            app.editor.document_flows.cycle_tab(1)
            await pilot.pause()
            assert app.editor.session.doc.name == "beta.txt"
            assert app.editor.session.search.matches == []
            assert app.editor.session.search.query == ""

            # ``n`` must not jump to the old document's out-of-range coords.
            app.editor.prompt_flows.find_next(True)
            await pilot.pause()
            row, _col = app.editor.session.buffer.cursor
            assert 0 <= row < app.editor.session.buffer.line_count

            # Switching back is harmless and the state stays reset.
            app.editor.document_flows.cycle_tab(-1)
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
            app.editor.document_flows.open_path(b)
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


def test_setting_commands_confirm_success() -> None:
    async def scenario() -> None:
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            app.editor.run_command("set keymap=vim")
            await pilot.pause()
            assert "keymap:" in message_text(app)
            app.editor.run_command("set theme=latte")
            await pilot.pause()
            assert "theme:" in message_text(app)
            app.editor.run_command("set filetype=python")
            await pilot.pause()
            assert "filetype set to" in message_text(app)

    asyncio.run(scenario())
