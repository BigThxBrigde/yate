"""Hex view scenarios (tags: ``files``, ``command``).

Covers the two hex-view entry points end to end: ``:e`` on a binary file
routes into the hex dump screen (the DocumentFlows callback handoff), and
``:hex`` toggles the dump for the active document (open, close, reopen,
escape close).  The dump itself is verified through the SVG text rows
(offset + hex + ASCII columns); screen state goes through the stack.
"""

from __future__ import annotations

from pathlib import Path
from typing import cast

from tools.smoke_test.harness import (
    Check,
    Scenario,
    ScenarioResult,
    new_app,
    snapshot_svg,
)
from tools.smoke_test.scenarios._base import run_command, wait_until
from yate.editor_view.hexview import HexScreen

__all__ = ["SCENARIOS"]


def _hex_screen(app: object) -> HexScreen | None:
    """The top screen when it is a :class:`HexScreen`, else ``None``."""
    screen = getattr(app, "screen", None)
    return screen if isinstance(screen, HexScreen) else None


def _has_offset_row(rows: dict[int, str]) -> bool:
    """Whether any rendered row shows a hex dump offset (``00000000:``)."""
    return any("00000000:" in text for text in rows.values())


async def _hex_view_binary_open(tmp: Path) -> ScenarioResult:
    """``:e thing.bin`` routes the binary file into the hex dump screen.

    The open runs through the async ``:e`` worker, so the wait uses
    :func:`wait_until`; the dump must show the offset:hex:ASCII row and
    ``q`` must return to the editor.
    """
    (tmp / "a.txt").write_text("alpha\nbravo\n", encoding="utf-8")
    (tmp / "thing.bin").write_bytes(b"\x00\x01\x02\x03binary\xff\x00\x01")
    app = new_app(target=tmp / "a.txt")
    checks: list[Check] = []
    async with app.run_test(size=(110, 32)) as pilot:
        await pilot.pause()
        await run_command(pilot, "e thing.bin")
        checks.append(Check(
            "hex_screen_pushed", True,
            await wait_until(pilot, lambda: _hex_screen(app) is not None),
        ))
        screen = _hex_screen(app)
        checks.append(Check("stack_at_two", 2, len(app.screen_stack)))
        # the bytes round-trip through the flow handoff (HexScreen._data)
        data = cast(bytes, getattr(screen, "_data", b""))
        checks.append(Check("screen_carries_bytes", True,
                            data == b"\x00\x01\x02\x03binary\xff\x00\x01"))
        rows = snapshot_svg(app, tmp)
        checks.append(Check("svg_shows_offset_hex_ascii", True,
                            _has_offset_row(rows)))
        await pilot.press("q")
        await pilot.pause()
        checks.append(Check("q_closes", 1, len(app.screen_stack)))
        checks.append(Check("back_to_editor", True, _hex_screen(app) is None))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("hex_view_binary_open", checks, rows)


async def _hex_view_toggle_text(tmp: Path) -> ScenarioResult:
    """``:hex`` toggles the dump for the active document.

    Open for the text startup target, close with ``q``, reopen, close with
    ``escape``: both keys must land on the hex screen's own handler and
    return the stack to the editor.
    """
    (tmp / "a.txt").write_text("alpha\nbravo\n", encoding="utf-8")
    app = new_app(target=tmp / "a.txt")
    checks: list[Check] = []
    async with app.run_test(size=(110, 32)) as pilot:
        await pilot.pause()
        await run_command(pilot, "hex")
        checks.append(Check("hex_screen_pushed", 2, len(app.screen_stack)))
        checks.append(Check("screen_is_hex", True, _hex_screen(app) is not None))
        rows = snapshot_svg(app, tmp)
        checks.append(Check("svg_shows_offset_hex_ascii", True,
                            _has_offset_row(rows)))
        await pilot.press("q")
        await pilot.pause()
        checks.append(Check("q_closes", 1, len(app.screen_stack)))
        await run_command(pilot, "hex")
        checks.append(Check("hex_reopens", 2, len(app.screen_stack)))
        await pilot.press("escape")
        await pilot.pause()
        checks.append(Check("escape_closes", 1, len(app.screen_stack)))
        checks.append(Check("back_to_editor", True, _hex_screen(app) is None))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("hex_view_toggle_text", checks, rows)


SCENARIOS: list[Scenario] = [
    Scenario("hex_view_binary_open", _hex_view_binary_open, ("files", "command")),
    Scenario("hex_view_toggle_text", _hex_view_toggle_text, ("files", "command")),
]
