"""Advanced vim key map scenarios (tags: ``edit``, ``select``).

Three scenarios cover the parts of :mod:`yate.keymaps.vim` the basic
``edit.py`` vim scenarios do not reach: the visual / visual-line selection
operators (``v`` / ``V`` / ``y`` / ``d`` / ``>`` / ``<``), the register +
text-object side of NORMAL mode (``"ayy`` / ``"ap`` / ``daw`` / ``3dd`` /
``ciw``) and the blockwise (column) visual mode (``ctrl+v`` rectangle
yank + paste, plan IKJSRW).

All enter and leave the key map the way a user does -- ``:vim`` to
switch, ``:vsc`` to restore -- so the app is back on the vsc key map with
a clean buffer state when the harness invariant sweep runs.
"""

from __future__ import annotations

from pathlib import Path

from yate.app import YateApp
from yate.keymaps.vim import VimMode

from ..harness import Check, Scenario, ScenarioResult, new_app, snapshot_svg
from ._base import run_command, type_text

__all__ = ["SCENARIOS"]


def _leading_spaces(line: str) -> int:
    """Number of leading space characters in *line* (indent width probe)."""
    return len(line) - len(line.lstrip(" "))


def _vim_state(app: YateApp, field: str) -> object:
    """Read the vim key map's *field* state, or ``None`` when it is gone.

    ``keymaps.get("vim")`` is statically a ``Keymap | None`` -- the base
    class does not declare the vim-only chord state -- while the values
    themselves are plain public attributes set in ``VimKeymap.__init__``:
    ``mode``, ``op``, ``op_count``, ``obj_scope``, ``count_str`` and
    ``pending_register``.  Reading them by name keeps the probe honest
    (a missing attribute shows up as ``None`` in the check) instead of
    casting the base class to a subclass the registry never promised.
    """
    vim = app.editor.keymaps.get("vim")
    return getattr(vim, field, None)


async def _vim_visual_mode_ops(tmp: Path) -> ScenarioResult:
    """``v`` / ``V`` selection operators, then normal-mode ``>`` / ``<``."""
    target = tmp / "visual.txt"
    target.write_text("alpha beta\ngamma delta\nepsilon zeta", encoding="utf-8")
    app = new_app(target=target)
    checks: list[Check] = []
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await run_command(pilot, "vim")
        checks.append(Check("keymap", "vim", app.editor.keymaps.name))
        checks.append(Check("mode_normal", "NORMAL", app.editor.mode_label()[0]))
        buffer = app.editor.session.buffer

        # v enters characterwise visual: the anchor sits on the cursor, so
        # nothing is selected yet and has_selection() stays False.
        await pilot.press("v")
        await pilot.pause()
        checks.append(Check("visual_label", "VISUAL", app.editor.mode_label()[0]))
        checks.append(Check("visual_mode", VimMode.VISUAL, _vim_state(app, "mode")))
        checks.append(Check("visual_anchor", (0, 0), buffer.anchor))
        checks.append(Check("visual_empty", False, buffer.has_selection()))

        # l l w extend the selection to the start of the second word.
        await pilot.press("l", "l", "w")
        await pilot.pause()
        checks.append(Check("extended", True, buffer.has_selection()))
        checks.append(Check("extended_text", "alpha ", buffer.selected_text()))
        checks.append(Check("still_visual", VimMode.VISUAL, _vim_state(app, "mode")))

        # y copies the selection into the unnamed register, lands on the
        # selection start and drops the selection (vim's behaviour).
        await pilot.press("y")
        await pilot.pause()
        checks.append(Check("yanked", "alpha ", buffer.register))
        checks.append(Check("yank_cursor", (0, 0), buffer.cursor))
        checks.append(Check("yank_cleared", False, buffer.has_selection()))
        checks.append(Check("after_yank_normal", "NORMAL", app.editor.mode_label()[0]))
        checks.append(Check("lines_intact", 3, buffer.line_count))

        # V is linewise: the anchor goes to column 0 and the cursor to the
        # line end, and the mode chip reads V-LINE (not VISUAL).
        await pilot.press("V")
        await pilot.pause()
        checks.append(Check("vline_label", "V-LINE", app.editor.mode_label()[0]))
        checks.append(Check("vline_mode", VimMode.VISUAL_LINE, _vim_state(app, "mode")))
        checks.append(Check("vline_span", ((0, 0), (0, 10)), buffer.selection()))

        # j grows the linewise span, and _fix_linewise keeps it column-anchored.
        await pilot.press("j")
        await pilot.pause()
        checks.append(Check("vline_rows", (0, 1), buffer.selected_rows()))
        checks.append(Check(
            "vline_text", "alpha beta\ngamma delta", buffer.selected_text()))

        # d deletes both lines whole (the register gains the trailing "\n").
        await pilot.press("d")
        await pilot.pause()
        checks.append(Check("line_count", 1, buffer.line_count))
        checks.append(Check("lines_left", ["epsilon zeta"], list(buffer.lines)))
        checks.append(Check("deleted_register", "alpha beta\ngamma delta\n",
                            buffer.register))
        checks.append(Check("after_delete_normal", "NORMAL",
                            app.editor.mode_label()[0]))
        checks.append(Check("delete_cleared", False, buffer.has_selection()))

        # NORMAL-mode > / < shift the cursor row and leave no selection.
        await pilot.press(">")
        await pilot.pause()
        checks.append(Check("indented", "    epsilon zeta", buffer.lines[0]))
        checks.append(Check("indent_width", 4, _leading_spaces(buffer.lines[0])))
        checks.append(Check("indent_cleared", False, buffer.has_selection()))
        await pilot.press("<")
        await pilot.pause()
        checks.append(Check("outdented", "epsilon zeta", buffer.lines[0]))
        checks.append(Check("outdent_width", 0, _leading_spaces(buffer.lines[0])))

        # esc leaves visual mode and drops the selection.
        await pilot.press("v")
        await pilot.pause()
        checks.append(Check("re_entered_visual", VimMode.VISUAL,
                            _vim_state(app, "mode")))
        await pilot.press("escape")
        await pilot.pause()
        checks.append(Check("esc_back_to_normal", "NORMAL",
                            app.editor.mode_label()[0]))
        checks.append(Check("esc_mode_obj", VimMode.NORMAL, _vim_state(app, "mode")))
        checks.append(Check("esc_cleared", False, buffer.has_selection()))

        await run_command(pilot, "vsc")
        checks.append(Check("keymap_restored", "vsc", app.editor.keymaps.name))
        checks.append(Check("label_restored", "VSC", app.editor.mode_label()[0]))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("vim_visual_mode_ops", checks, rows)


async def _vim_registers_text_objects(tmp: Path) -> ScenarioResult:
    """Named registers (``"ayy`` / ``"ap``) plus the ``daw`` / ``3dd`` / ``ciw``
    operator family, each ending with the chord state back at rest."""
    target = tmp / "registers.txt"
    target.write_text(
        "alpha beta\ngamma delta\nepsilon zeta\neta theta\niota kappa",
        encoding="utf-8",
    )
    app = new_app(target=target)
    checks: list[Check] = []
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await run_command(pilot, "vim")
        checks.append(Check("keymap", "vim", app.editor.keymaps.name))
        buffer = app.editor.session.buffer

        # "ayy: the register letter is consumed by the operator, so the
        # unnamed register stays empty -- a named yank never mirrors.
        await pilot.press('"', "a", "y", "y")
        await pilot.pause()
        checks.append(Check("named_register", {"a": "alpha beta\n"},
                            dict(buffer.named_registers)))
        checks.append(Check("unnamed_untouched", "", buffer.register))
        checks.append(Check("yank_keeps_lines", 5, buffer.line_count))
        checks.append(Check("yank_cursor", (0, 0), buffer.cursor))
        checks.append(Check("register_consumed", None,
                            _vim_state(app, "pending_register")))

        # j then "ap: the linewise paste lands *below* the cursor row, and
        # TextBuffer.paste leaves the cursor on the last pasted row
        # (move_line_end / move_left) rather than on the pasted text.
        await pilot.press("j")
        await pilot.pause()
        checks.append(Check("moved_down", (1, 0), buffer.cursor))
        before_paste = buffer.line_count
        await pilot.press('"', "a", "p")
        await pilot.pause()
        checks.append(Check("paste_grew", before_paste + 1, buffer.line_count))
        checks.append(Check("pasted_line", "alpha beta", buffer.lines[2]))
        checks.append(Check("paste_kept_register", {"a": "alpha beta\n"},
                            dict(buffer.named_registers)))
        checks.append(Check("paste_cursor_row", 3, buffer.cursor[0]))

        # daw on that row: word plus the whitespace behind it.
        await pilot.press("0")
        await pilot.pause()
        checks.append(Check("line_start", (3, 0), buffer.cursor))
        await pilot.press("d", "a", "w")
        await pilot.pause()
        checks.append(Check("daw_line", "zeta", buffer.lines[3]))
        checks.append(Check("daw_lines_kept", before_paste + 1, buffer.line_count))
        checks.append(Check("daw_register", "epsilon ", buffer.register))
        checks.append(Check("modified", True, app.editor.session.doc.modified))

        # 3dd: the count typed before the operator is the line count
        # (op_count 3 times the dd motion count 1), so three whole rows go.
        before_dd = buffer.line_count
        await pilot.press("3", "d", "d")
        await pilot.pause()
        checks.append(Check("dd_dropped", before_dd - 3, buffer.line_count))
        checks.append(Check("dd_lines", ["alpha beta", "gamma delta", "alpha beta"],
                            list(buffer.lines)))
        checks.append(Check("dd_register", "zeta\neta theta\niota kappa\n",
                            buffer.register))

        # ciw on the second word of the first line: delete, INSERT, retype.
        # gg rather than k: after 3dd the cursor is clamped to the new last
        # row, so one k would only land on the middle line.
        await pilot.press("g", "g", "w")
        await pilot.pause()
        checks.append(Check("on_second_word", (0, 6), buffer.cursor))
        await pilot.press("c", "i", "w")
        await pilot.pause()
        checks.append(Check("ciw_insert_mode", "INSERT", app.editor.mode_label()[0]))
        checks.append(Check("ciw_mode_obj", VimMode.INSERT, _vim_state(app, "mode")))
        checks.append(Check("ciw_cleared_word", "alpha ", buffer.lines[0]))
        await type_text(pilot, "delta")
        checks.append(Check("ciw_typed", "alpha delta", buffer.lines[0]))
        await pilot.press("escape")
        await pilot.pause()
        checks.append(Check("ciw_back_to_normal", "NORMAL",
                            app.editor.mode_label()[0]))
        checks.append(Check("ciw_register", "beta", buffer.register))

        # Every half-finished chord is consumed: the key map is at rest.
        checks.append(Check("op_reset", None, _vim_state(app, "op")))
        checks.append(Check("op_count_reset", None, _vim_state(app, "op_count")))
        checks.append(Check("obj_scope_reset", None, _vim_state(app, "obj_scope")))
        checks.append(Check("count_str_reset", "", _vim_state(app, "count_str")))
        checks.append(Check("register_pending_reset", None,
                            _vim_state(app, "pending_register")))

        await run_command(pilot, "vsc")
        checks.append(Check("keymap_restored", "vsc", app.editor.keymaps.name))
        checks.append(Check("label_restored", "VSC", app.editor.mode_label()[0]))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("vim_registers_text_objects", checks, rows)


async def _vim_column_mode_ops(tmp: Path) -> ScenarioResult:
    """Blockwise visual mode (``ctrl+v``): rectangle yank and paste.

    Enters vim, draws a two-row single-column rectangle with ``l`` / ``j``,
    yanks it (chip back to NORMAL, ``register_block`` set), moves down and
    pastes it as a rectangle, then restores the vsc key map.
    """
    target = tmp / "column.txt"
    target.write_text("alpha beta\ngamma delta\nepsilon zeta", encoding="utf-8")
    app = new_app(target=target)
    checks: list[Check] = []
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await run_command(pilot, "vim")
        checks.append(Check("keymap", "vim", app.editor.keymaps.name))
        checks.append(Check("mode_normal", "NORMAL", app.editor.mode_label()[0]))
        buffer = app.editor.session.buffer

        # ctrl+v enters blockwise visual anchored at the cursor, so the
        # rectangle is zero-width and nothing is selected yet.
        await pilot.press("ctrl+v")
        await pilot.pause()
        checks.append(Check("column_label", "V-COLUMN",
                            app.editor.mode_label()[0]))
        checks.append(Check("column_mode", VimMode.VISUAL_BLOCK,
                            _vim_state(app, "mode")))
        checks.append(Check("anchor_at_cursor", buffer.cursor, buffer.anchor))

        # l j extend the rectangle to rows 0..1, column 0 (half-open right).
        await pilot.press("l", "j")
        await pilot.pause()
        checks.append(Check("block_region", (0, 0, 1, 1),
                            buffer.block_region()))
        checks.append(Check("still_block", VimMode.VISUAL_BLOCK,
                            _vim_state(app, "mode")))

        # y yanks the rectangle ("a" / "g"), lands on its top-left corner
        # and drops the selection -- the chip is back to NORMAL.
        await pilot.press("y")
        await pilot.pause()
        checks.append(Check("after_yank_normal", "NORMAL",
                            app.editor.mode_label()[0]))
        checks.append(Check("block_register", "a\ng", buffer.register))
        checks.append(Check("register_is_block", True, buffer.register_block))
        checks.append(Check("yank_cleared", False, buffer.has_selection()))

        # j p pastes the rectangle back.  The block yank lands via
        # set_cursor, which drops the vertical goal column set by the
        # earlier l, so j returns to column 0 (vim semantics).
        await pilot.press("j")
        await pilot.pause()
        checks.append(Check("paste_cursor", (1, 0), buffer.cursor))
        await pilot.press("p")
        await pilot.pause()
        checks.append(Check("pasted_rect",
                            ["alpha beta", "agamma delta", "gepsilon zeta"],
                            list(buffer.lines)))
        checks.append(Check("paste_kept_block_flag", True,
                            buffer.register_block))

        await run_command(pilot, "vsc")
        checks.append(Check("keymap_restored", "vsc", app.editor.keymaps.name))
        checks.append(Check("label_restored", "VSC",
                            app.editor.mode_label()[0]))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("vim_column_mode_ops", checks, rows)


SCENARIOS: list[Scenario] = [
    Scenario("vim_visual_mode_ops", _vim_visual_mode_ops, ("edit", "select")),
    Scenario("vim_registers_text_objects", _vim_registers_text_objects,
             ("edit",)),
    Scenario("vim_column_mode_ops", _vim_column_mode_ops, ("edit",)),
]
