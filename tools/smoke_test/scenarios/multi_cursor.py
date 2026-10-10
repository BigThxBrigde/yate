"""Multi-cursor scenarios (tags: ``edit``, ``select``; issue IKKJHH).

Two scenarios cover the multi-cursor feature end to end through the
keymaps: the vim ``ALT+C`` entry with INSERT multi-point typing and the
vsc ``ALT+click`` entry with modeless multi-point typing.  The chip
assertions go through ``Editor.mode_label()`` (the shared status-bar
implementation) and the point-set assertions read the buffer directly.

Both enter and leave the key map the way a user does -- ``:vim`` to
switch, ``:vsc`` to restore -- so the app is back on the vsc key map with
a clean buffer state when the harness invariant sweep runs.
"""

from __future__ import annotations

from pathlib import Path

from yate.editor_view.editor import EditorView

from tools.smoke_test.harness import Check, Scenario, ScenarioResult, new_app, snapshot_svg
from tools.smoke_test.scenarios._base import run_command, type_text

__all__ = ["SCENARIOS"]

#: Same three-line document as ``vim_advanced``: gutter width is
#: max(3, len("3")) + 3 == 6 cells, so mouse x = gutter + col.
_GUTTER: int = 6


async def _vim_multi_cursor_ops(tmp: Path) -> ScenarioResult:
    """``ALT+C`` points, INSERT multi-point typing, ``Esc`` and motion."""
    target = tmp / "multi_vim.txt"
    target.write_text("alpha beta\ngamma delta\nepsilon zeta", encoding="utf-8")
    app = new_app(target=target)
    checks: list[Check] = []
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await run_command(pilot, "vim")
        checks.append(Check("keymap", "vim", app.editor.keymaps.name))
        buffer = app.editor.session.buffer

        # move to column 2 so both ALT+C points share that column
        await pilot.press("l", "l")
        await pilot.pause()
        checks.append(Check("cursor_col2", (0, 2), buffer.cursor))

        # ALT+C twice: one point per press, each one row below the
        # bottom-most point, all in column 2; the chip reads V-COLUMN.
        await pilot.press("alt+c")
        await pilot.press("alt+c")
        await pilot.pause()
        checks.append(Check("points", [(1, 2), (2, 2)],
                            list(buffer.extra_cursors)))
        checks.append(Check("chip_vcolumn", "V-COLUMN",
                            app.editor.mode_label()[0]))

        # INSERT mode typing lands at every point (chip stays V-COLUMN:
        # the multi-cursor state outranks the vim mode mapping).
        await pilot.press("i")
        await type_text(pilot, "X")
        checks.append(Check(
            "typed_all_rows",
            ["alXpha beta", "gaXmma delta", "epXsilon zeta"],
            list(buffer.lines),
        ))
        checks.append(Check("chip_still_vcolumn", "V-COLUMN",
                            app.editor.mode_label()[0]))

        # Esc collapses the points and returns to NORMAL; the whole
        # multi-point edit was ONE undo step.
        await pilot.press("escape")
        await pilot.pause()
        checks.append(Check("esc_points_gone", [], list(buffer.extra_cursors)))
        checks.append(Check("esc_label", "NORMAL",
                            app.editor.mode_label()[0]))
        buffer.undo()
        checks.append(Check(
            "undo_restored",
            ["alpha beta", "gamma delta", "epsilon zeta"],
            list(buffer.lines),
        ))
        # undo restores the point set from the snapshot too: drop it again
        # (Esc in NORMAL), then rebuild the points deterministically.
        await pilot.press("escape")
        await pilot.pause()
        checks.append(Check("points_reset", [], list(buffer.extra_cursors)))
        await pilot.press("alt+c", "alt+c")
        await pilot.pause()
        checks.append(Check("points_rebuilt", [(1, 2), (2, 2)],
                            list(buffer.extra_cursors)))

        # motions keep their single-cursor semantics: j moves only the
        # primary cursor, the point set is untouched.
        await pilot.press("j")
        await pilot.pause()
        checks.append(Check("motion_cursor", (1, 2), buffer.cursor))
        checks.append(Check("motion_points_kept", [(1, 2), (2, 2)],
                            list(buffer.extra_cursors)))

        await run_command(pilot, "vsc")
        checks.append(Check("keymap_restored", "vsc", app.editor.keymaps.name))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("vim_multi_cursor_ops", checks, rows)


async def _vsc_multi_cursor_mouse(tmp: Path) -> ScenarioResult:
    """``ALT+click`` points, multi-point typing, plain-click collapse."""
    target = tmp / "multi_vsc.txt"
    target.write_text("alpha beta\ngamma delta\nepsilon zeta", encoding="utf-8")
    app = new_app(target=target)
    checks: list[Check] = []
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        checks.append(Check("keymap", "vsc", app.editor.keymaps.name))
        buffer = app.editor.session.buffer

        # ALT+click on two different rows: meta=True is the Textual
        # mapping of the SGR Alt bit (the real terminal's ALT+click).
        await pilot.click(EditorView, offset=(_GUTTER + 2, 0), meta=True)
        await pilot.click(EditorView, offset=(_GUTTER + 2, 1), meta=True)
        await pilot.pause()
        checks.append(Check("points", [(0, 2), (1, 2)],
                            list(buffer.extra_cursors)))
        checks.append(Check("chip_vcolumn", "V-COLUMN",
                            app.editor.mode_label()[0]))

        # typing inserts at the primary cursor AND both points; Enter
        # would insert a bare newline everywhere (no auto-indent).
        await pilot.press("x")
        await pilot.pause()
        checks.append(Check(
            "typed_all_points",
            "xalxpha beta\ngaxmma delta\nepsilon zeta",
            buffer.get_text(),
        ))

        # Esc collapses the points (vsc maps <esc> to clear_selection).
        await pilot.press("escape")
        await pilot.pause()
        checks.append(Check("esc_points_gone", [], list(buffer.extra_cursors)))
        checks.append(Check("esc_label", "VSC", app.editor.mode_label()[0]))

        # undo: the whole multi-point edit was one step; the point set
        # rides the snapshot and comes back with the text.
        buffer.undo()
        checks.append(Check(
            "undo_restored",
            "alpha beta\ngamma delta\nepsilon zeta",
            buffer.get_text(),
        ))
        checks.append(Check("undo_points_restored", [(0, 2), (1, 2)],
                            list(buffer.extra_cursors)))

        # a plain left click collapses the surviving points and moves
        # the primary cursor (collapse via Esc first, re-add one point)
        await pilot.press("escape")
        await pilot.pause()
        await pilot.click(EditorView, offset=(_GUTTER + 2, 0), meta=True)
        await pilot.pause()
        checks.append(Check("point_readded", [(0, 2)],
                            list(buffer.extra_cursors)))
        await pilot.click(EditorView, offset=(_GUTTER + 5, 1))
        await pilot.pause()
        checks.append(Check("plain_click_cleared", [],
                            list(buffer.extra_cursors)))
        checks.append(Check("plain_click_moved", (1, 5), buffer.cursor))

        rows = snapshot_svg(app, tmp)
    return ScenarioResult("vsc_multi_cursor_mouse", checks, rows)


SCENARIOS: list[Scenario] = [
    Scenario("vim_multi_cursor_ops", _vim_multi_cursor_ops, ("edit", "select")),
    Scenario("vsc_multi_cursor_mouse", _vsc_multi_cursor_mouse, ("edit",)),
]
