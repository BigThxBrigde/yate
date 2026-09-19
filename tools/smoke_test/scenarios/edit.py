"""Editing and selection scenarios (tags: ``edit``, ``select``)."""

from __future__ import annotations

from pathlib import Path

from ..harness import Check, Scenario, ScenarioResult, new_app, snapshot_svg
from ._base import run_command, type_text
from yate.keymaps.vim import VimMode

__all__ = ["SCENARIOS"]


async def _undo_redo(tmp: Path) -> ScenarioResult:
    """Type -> ctrl+z -> ctrl+y, tracking ``doc.modified``."""
    target = tmp / "note.txt"
    app = new_app(target=target)
    checks: list[Check] = []
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await type_text(pilot, "hello")
        checks.append(Check("typed", "hello", app.buffer.get_text()))
        checks.append(Check("dirty", True, app.doc.modified))
        await pilot.press("ctrl+z")
        await pilot.pause()
        checks.append(Check("after_undo", "", app.buffer.get_text()))
        checks.append(Check("clean_after_undo", False, app.doc.modified))
        await pilot.press("ctrl+y")
        await pilot.pause()
        checks.append(Check("after_redo", "hello", app.buffer.get_text()))
        checks.append(Check("dirty_after_redo", True, app.doc.modified))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("undo_redo", checks, rows)


async def _duplicate_delete_line(tmp: Path) -> ScenarioResult:
    """ctrl+d duplicates the line, ctrl+shift+k deletes it again."""
    target = tmp / "lines.txt"
    target.write_text("one\ntwo", encoding="utf-8")
    app = new_app(target=target)
    checks: list[Check] = []
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await pilot.press("ctrl+d")
        await pilot.pause()
        checks.append(Check("duplicated", ["one", "one", "two"], list(app.buffer.lines)))
        # "ctrl+shift+k" has no raw translation; the keymap folds shift into
        # the ctrl code, so the binding is reached with ctrl+k.
        await pilot.press("ctrl+k")
        await pilot.pause()
        checks.append(Check("deleted", ["one", "two"], list(app.buffer.lines)))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("duplicate_delete_line", checks, rows)


async def _move_line_block(tmp: Path) -> ScenarioResult:
    """alt+down / alt+up move the current line."""
    target = tmp / "lines.txt"
    target.write_text("one\ntwo", encoding="utf-8")
    app = new_app(target=target)
    checks: list[Check] = []
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await pilot.press("alt+down")
        await pilot.pause()
        checks.append(Check("moved_down", ["two", "one"], list(app.buffer.lines)))
        await pilot.press("alt+up")
        await pilot.pause()
        checks.append(Check("moved_up", ["one", "two"], list(app.buffer.lines)))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("move_line_block", checks, rows)


async def _indent_outdent(tmp: Path) -> ScenarioResult:
    """ctrl+] indents, shift+tab outdents (tab_width = 4 spaces)."""
    target = tmp / "lines.txt"
    target.write_text("one", encoding="utf-8")
    app = new_app(target=target)
    checks: list[Check] = []
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await pilot.press("ctrl+]")
        await pilot.pause()
        checks.append(Check("indented", "    one", app.buffer.lines[0]))
        await pilot.press("shift+tab")
        await pilot.pause()
        checks.append(Check("outdented", "one", app.buffer.lines[0]))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("indent_outdent", checks, rows)


async def _join_lines(tmp: Path) -> ScenarioResult:
    """ctrl+j joins the current line with the next one."""
    target = tmp / "lines.txt"
    target.write_text("one\ntwo", encoding="utf-8")
    app = new_app(target=target)
    checks: list[Check] = []
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await pilot.press("ctrl+j")
        await pilot.pause()
        checks.append(Check("line_count", 1, app.buffer.line_count))
        checks.append(Check("joined", "one two", app.buffer.lines[0]))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("join_lines", checks, rows)


async def _clipboard_roundtrip(tmp: Path) -> ScenarioResult:
    """Copy a selection, paste it back, then cut the whole line."""
    target = tmp / "clip.txt"
    target.write_text("hello", encoding="utf-8")
    app = new_app(target=target)
    checks: list[Check] = []
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await pilot.press("shift+right", "shift+right")
        await pilot.pause()
        checks.append(Check("has_selection", True, app.buffer.has_selection()))
        checks.append(Check("selected_text", "he", app.buffer.selected_text()))
        await pilot.press("ctrl+c")
        await pilot.pause()
        checks.append(Check("register", "he", app.buffer.register))
        await pilot.press("escape", "ctrl+end")
        await pilot.pause()
        checks.append(Check("selection_cleared", False, app.buffer.has_selection()))
        await pilot.press("ctrl+v")
        await pilot.pause()
        checks.append(Check("pasted", "hellohe", app.buffer.lines[0]))
        await pilot.press("ctrl+x")
        await pilot.pause()
        checks.append(Check("cut_line", [""], list(app.buffer.lines)))
        checks.append(Check("register_line", "hellohe\n", app.buffer.register))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("clipboard_roundtrip", checks, rows)


async def _word_motion_bounds(tmp: Path) -> ScenarioResult:
    """Word / line / document cursor motions stay inside the text."""
    target = tmp / "words.txt"
    target.write_text("hello world", encoding="utf-8")
    app = new_app(target=target)
    checks: list[Check] = []
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await pilot.press("ctrl+right")
        await pilot.pause()
        checks.append(Check("word_right_1", (0, 6), app.buffer.cursor))
        await pilot.press("ctrl+right")
        await pilot.pause()
        checks.append(Check("word_right_2", (0, 11), app.buffer.cursor))
        await pilot.press("ctrl+left")
        await pilot.pause()
        checks.append(Check("word_left", (0, 6), app.buffer.cursor))
        await pilot.press("home")
        await pilot.pause()
        checks.append(Check("home", (0, 0), app.buffer.cursor))
        await pilot.press("end")
        await pilot.pause()
        checks.append(Check("end", (0, 11), app.buffer.cursor))
        await pilot.press("ctrl+home")
        await pilot.pause()
        checks.append(Check("doc_start", (0, 0), app.buffer.cursor))
        await pilot.press("ctrl+end")
        await pilot.pause()
        checks.append(Check("doc_end", (0, 11), app.buffer.cursor))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("word_motion_bounds", checks, rows)


async def _autoindent_newline(tmp: Path) -> ScenarioResult:
    """Enter keeps the current indentation; tab inserts the next step."""
    target = tmp / "indent.txt"
    app = new_app(target=target)
    checks: list[Check] = []
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await type_text(pilot, "    x")
        checks.append(Check("typed", "    x", app.buffer.lines[0]))
        await pilot.press("enter")
        await pilot.pause()
        checks.append(Check("line_count", 2, app.buffer.line_count))
        checks.append(Check("kept_indent", "    ", app.buffer.lines[1]))
        await pilot.press("tab")
        await pilot.pause()
        checks.append(Check("tab_step", "        ", app.buffer.lines[1]))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("autoindent_newline", checks, rows)


async def _vim_modal_editing(tmp: Path) -> ScenarioResult:
    """:vim -> i -> text -> esc -> dd -> :w, all through the vim keymap."""
    target = tmp / "vim.txt"
    app = new_app(target=target)
    checks: list[Check] = []
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await run_command(pilot, "vim")
        checks.append(Check("keymap", "vim", app.keymap_name))
        checks.append(Check("mode_normal", "NORMAL", app.mode_label()[0]))
        await pilot.press("i")
        await pilot.pause()
        checks.append(Check("mode_insert", "INSERT", app.mode_label()[0]))
        await type_text(pilot, "hello")
        await pilot.press("escape")
        await pilot.pause()
        checks.append(Check("inserted", "hello", app.buffer.lines[0]))
        checks.append(Check("back_to_normal", "NORMAL", app.mode_label()[0]))
        await pilot.press("d", "d")
        await pilot.pause()
        checks.append(Check("deleted_line", [""], list(app.buffer.lines)))
        await pilot.press("i")
        await pilot.pause()
        await type_text(pilot, "saved")
        await pilot.press("escape")
        await pilot.pause()
        await run_command(pilot, "w")
        checks.append(Check("file_content", "saved", target.read_text(encoding="utf-8")))
        checks.append(Check("saved_flag", False, app.doc.modified))
        vim = app.keymaps["vim"]
        checks.append(Check("vim_mode_obj", VimMode.NORMAL, getattr(vim, "mode", None)))
        await run_command(pilot, "vsc")
        checks.append(Check("keymap_restored", "vsc", app.keymap_name))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("vim_modal_editing", checks, rows)


async def _selection_extend_clear(tmp: Path) -> ScenarioResult:
    """shift+arrow extends the selection, esc clears it."""
    target = tmp / "sel.txt"
    target.write_text("hello", encoding="utf-8")
    app = new_app(target=target)
    checks: list[Check] = []
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await pilot.press("shift+right", "shift+right", "shift+right")
        await pilot.pause()
        checks.append(Check("selected", True, app.buffer.has_selection()))
        checks.append(Check("selected_text", "hel", app.buffer.selected_text()))
        await pilot.press("escape")
        await pilot.pause()
        checks.append(Check("cleared", False, app.buffer.has_selection()))
        checks.append(Check("no_text", None, app.buffer.selected_text()))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("selection_extend_clear", checks, rows)


async def _select_all_indent(tmp: Path) -> ScenarioResult:
    """ctrl+a selects everything, ctrl+] indents the whole block."""
    target = tmp / "sel.txt"
    target.write_text("one\ntwo", encoding="utf-8")
    app = new_app(target=target)
    checks: list[Check] = []
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await pilot.press("ctrl+a")
        await pilot.pause()
        checks.append(Check("all_selected", True, app.buffer.has_selection()))
        await pilot.press("ctrl+]")
        await pilot.pause()
        checks.append(Check("indented", ["    one", "    two"], list(app.buffer.lines)))
        await pilot.press("escape")
        await pilot.pause()
        checks.append(Check("anchor_cleared", None, app.buffer.anchor))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("select_all_indent", checks, rows)


SCENARIOS: list[Scenario] = [
    Scenario("undo_redo", _undo_redo, ("edit",)),
    Scenario("duplicate_delete_line", _duplicate_delete_line, ("edit",)),
    Scenario("move_line_block", _move_line_block, ("edit",)),
    Scenario("indent_outdent", _indent_outdent, ("edit",)),
    Scenario("join_lines", _join_lines, ("edit",)),
    Scenario("clipboard_roundtrip", _clipboard_roundtrip, ("edit",)),
    Scenario("word_motion_bounds", _word_motion_bounds, ("edit",)),
    Scenario("autoindent_newline", _autoindent_newline, ("edit",)),
    Scenario("vim_modal_editing", _vim_modal_editing, ("edit",)),
    Scenario("selection_extend_clear", _selection_extend_clear, ("select",)),
    Scenario("select_all_indent", _select_all_indent, ("select",)),
]
