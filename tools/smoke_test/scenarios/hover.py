"""Hover-docs smoke scenarios (tag: ``hover``).

Two scenarios exercise the silent paths of the LSP hover feature without a
real language server (the harness never starts one):

* ``hover_docs_key_is_silent_without_a_server_in_both_keymaps`` -- pressing
  the shared hover key (``<f7>`` in both keymap tables) with no server
  must be silent: no card, no message, no placeholder text, no buffer edit.
  The key is pressed in the default vsc keymap and again after switching
  to vim, covering the AC2 key plumbing and the AC5 silent path.
* ``hover_docs_non_drag_mouse_move_is_not_consumed`` -- a non-drag
  ``MouseMove`` routed through the view's ``handle_mouse`` path must return
  ``False`` (the event is not stopped), leave the cursor/buffer untouched,
  show no card and write no message (AC3 mouse plumbing).  A second app
  built with ``support_mouse=False`` must never deliver a buffer position
  to the hover callback (the gate: no hover payload can be requested).

Both scenarios poll with :func:`wait_until`; no fixed sleeps.
"""

from __future__ import annotations

from pathlib import Path

from textual.events import MouseMove

from yate.config import YateConfig
from yate.editor_core.buffer import Pos

from tools.smoke_test.harness import (
    Check,
    Scenario,
    ScenarioResult,
    new_app,
    snapshot_svg,
)
from tools.smoke_test.scenarios._base import message_text, wait_until

__all__ = ["SCENARIOS"]

#: Textual key name behind ``HOVER_DOC_KEY`` ("f7" -> raw "\x1b[18~").
_HOVER_KEY: str = "f7"

#: Text column offset of the editor gutter in the headless layout
#: (same geometry assumption as ``tests/test_app_mouse.py``).
_GUTTER: int = 6


async def _hover_docs_key_is_silent_without_a_server_in_both_keymaps(
    tmp: Path,
) -> ScenarioResult:
    """f7 in vsc and vim without a server: silent, no card, no edit."""
    app = new_app(target=tmp / "hover.txt")
    checks: list[Check] = []
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        popup = app.editor.hover_popup
        await wait_until(pilot, lambda: popup.is_mounted)
        message_before = message_text(app)
        lines_before = list(app.editor.session.doc.buffer.lines)

        # Phase 1: default vsc keymap.
        await pilot.press(_HOVER_KEY)
        await wait_until(pilot, lambda: not popup.is_open)
        checks.append(Check("card_vsc", False, popup.is_open))
        checks.append(Check("message_vsc", message_before, message_text(app)))
        checks.append(
            Check(
                "lines_vsc",
                lines_before,
                list(app.editor.session.doc.buffer.lines),
            )
        )
        checks.append(
            Check(
                "no_placeholder_vsc",
                False,
                "no documentation" in message_text(app).lower(),
            )
        )

        # Phase 2: switch to vim, press the same key again.
        await pilot.press("ctrl+/")
        await pilot.pause()
        checks.append(Check("keymap", "vim", app.editor.keymaps.name))
        # The toggle itself reports "keymap: Vim (modal)" on the message
        # slot; snapshot again so the f7 silence check stays isolated.
        message_before = message_text(app)
        await pilot.press(_HOVER_KEY)
        await wait_until(pilot, lambda: not popup.is_open)
        checks.append(Check("card", False, popup.is_open))
        checks.append(Check("message", message_before, message_text(app)))
        checks.append(
            Check(
                "lines",
                lines_before,
                list(app.editor.session.doc.buffer.lines),
            )
        )
        checks.append(
            Check(
                "no_placeholder",
                False,
                "no documentation" in message_text(app).lower(),
            )
        )
        rows = snapshot_svg(app, tmp)
    return ScenarioResult(
        "hover_docs_key_is_silent_without_a_server_in_both_keymaps",
        checks,
        rows,
    )


async def _hover_docs_non_drag_mouse_move_is_not_consumed(
    tmp: Path,
) -> ScenarioResult:
    """Non-drag MouseMove: not consumed, no state change; gate-off is silent."""
    app = new_app(target=tmp / "hover_mouse.txt")
    checks: list[Check] = []
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        popup = app.editor.hover_popup
        await wait_until(pilot, lambda: popup.is_mounted)
        view = app.editor.panes.active_view
        assert view is not None
        assert view.handle_mouse is not None
        message_before = message_text(app)
        lines_before = list(app.editor.session.doc.buffer.lines)
        cursor_before = app.editor.session.doc.buffer.cursor

        # Phase 1: support_mouse on, non-drag move through the view path.
        event = MouseMove(
            view, x=_GUTTER + 9, y=0, delta_x=0, delta_y=0,
            button=0, shift=False, meta=False, ctrl=False,
        )
        consumed = view.handle_mouse(event)
        await wait_until(pilot, lambda: not popup.is_open)
        checks.append(Check("consumed", False, consumed))
        checks.append(
            Check("cursor", cursor_before, app.editor.session.doc.buffer.cursor)
        )
        checks.append(
            Check(
                "lines",
                lines_before,
                list(app.editor.session.doc.buffer.lines),
            )
        )
        checks.append(Check("card", False, popup.is_open))
        checks.append(Check("message", message_before, message_text(app)))
        rows = snapshot_svg(app, tmp)

    # Phase 2: support_mouse off -- the gate must keep every buffer
    # position away from the hover callback (record what it receives).
    app_off = new_app(
        target=tmp / "hover_mouse_off.txt",
        config=YateConfig(support_mouse=False),
    )
    async with app_off.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        popup_off = app_off.editor.hover_popup
        await wait_until(pilot, lambda: popup_off.is_mounted)
        view_off = app_off.editor.panes.active_view
        assert view_off is not None
        assert view_off.handle_mouse is not None
        message_before = message_text(app_off)
        cursor_before = app_off.editor.session.doc.buffer.cursor
        received: list[Pos | None] = []
        # getattr/setattr keep the private attribute out of pyright's
        # reportPrivateUsage scope while still spying on the live callback.
        original = getattr(app_off.editor.mouse_flows, "_on_hover_move")
        assert callable(original)

        def _record(pos: Pos | None) -> None:
            """Spy on the injected hover callback (test-only wrapper)."""
            received.append(pos)
            original(pos)

        setattr(app_off.editor.mouse_flows, "_on_hover_move", _record)
        event = MouseMove(
            view_off, x=_GUTTER + 9, y=0, delta_x=0, delta_y=0,
            button=0, shift=False, meta=False, ctrl=False,
        )
        consumed = view_off.handle_mouse(event)
        await wait_until(pilot, lambda: not popup_off.is_open)
        checks.append(Check("consumed_gate_off", False, consumed))
        checks.append(
            Check(
                "hover_never_gets_a_position",
                [],
                [pos for pos in received if pos is not None],
            )
        )
        checks.append(
            Check("card_gate_off", False, popup_off.is_open)
        )
        checks.append(
            Check("message_gate_off", message_before, message_text(app_off))
        )
        checks.append(
            Check(
                "cursor_gate_off",
                cursor_before,
                app_off.editor.session.doc.buffer.cursor,
            )
        )
    return ScenarioResult("hover_docs_non_drag_mouse_move_is_not_consumed",
                          checks, rows)


SCENARIOS: list[Scenario] = [
    Scenario(
        "hover_docs_key_is_silent_without_a_server_in_both_keymaps",
        _hover_docs_key_is_silent_without_a_server_in_both_keymaps,
        ("hover",),
    ),
    Scenario(
        "hover_docs_non_drag_mouse_move_is_not_consumed",
        _hover_docs_non_drag_mouse_move_is_not_consumed,
        ("hover",),
    ),
]
