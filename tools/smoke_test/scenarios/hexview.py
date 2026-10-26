"""Hex view scenarios (tags: ``files``, ``command``).

Covers the two hex-view entry points end to end: ``:e`` on a binary file
routes into the hex dump screen (the DocumentFlows callback handoff), and
``:hex`` toggles the dump for the active document (open, close, reopen,
escape close).  A third scenario drives the goto-address input (``g`` +
address + ``enter``) and verifies the dump shows the target offset row.
A fourth scenario edits the first byte in place (``e`` + nibble keys) and
writes it back with ``w``.  The dump itself is verified through the SVG
text rows (offset + hex + ASCII columns); screen state goes through the
stack.
"""

from __future__ import annotations

from pathlib import Path

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


def _has_offset_row(rows: dict[int, str], row: int = 0) -> bool:
    """Whether any rendered row shows the offset of content *row*.

    *row* counts 16-byte content rows (row 1 renders the ``00000010:``
    offset prefix), following the hex view's xxd layout.
    """
    prefix = f"{row * 16:08x}:"
    return any(prefix in text for text in rows.values())


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
        # the file round-trips through the flow handoff (chunked source,
        # plan-c: HexScreen carries a ChunkedBinaryFile, no pre-read blob)
        source = getattr(screen, "_source", None)
        checks.append(Check(
            "screen_carries_bytes", True,
            source is not None
            and source.read(0, source.size)
            == b"\x00\x01\x02\x03binary\xff\x00\x01",
        ))
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


async def _hex_view_goto_address(tmp: Path) -> ScenarioResult:
    """``g`` + address + ``enter`` jumps the dump to the target offset.

    The goto input opens on ``g``; the typed ``0x10`` address parses to
    byte offset 16 and the dump must show the ``00000010:`` offset row
    afterwards (the file is sized so that row exists).
    """
    (tmp / "a.txt").write_text("alpha\n" * 8, encoding="utf-8")
    app = new_app(target=tmp / "a.txt")
    checks: list[Check] = []
    async with app.run_test(size=(110, 32)) as pilot:
        await pilot.pause()
        await run_command(pilot, "hex")
        checks.append(Check("hex_screen_pushed", 2, len(app.screen_stack)))
        await pilot.press("g")
        await pilot.press("0", "x", "1", "0")
        await pilot.press("enter")
        await pilot.pause()
        rows = snapshot_svg(app, tmp)
        checks.append(Check(
            "svg_shows_offset_row_10", True,
            _has_offset_row(rows, row=1),
        ))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("hex_view_goto_address", checks, rows)


async def _hex_view_edit_and_save(tmp: Path) -> ScenarioResult:
    """Edit the first byte in the hex view and write it back with ``w``.

    ``e edit.bin`` routes the binary file into the hex dump screen (the
    file is not open as a text document, so the write-back conflict gate
    lets it through -- unlike ``:hex`` on the active text document, whose
    path is always open in the editor); ``e`` enters edit mode, ``4`` +
    ``1`` key the nibbles of 0x41 and ``w`` saves.  The byte on disk must
    read 0x41 afterwards and ``q`` must return to the editor.
    """
    (tmp / "a.txt").write_text("alpha\nbravo\n", encoding="utf-8")
    (tmp / "edit.bin").write_bytes(b"\x00" * 16)
    app = new_app(target=tmp / "a.txt")
    checks: list[Check] = []
    async with app.run_test(size=(110, 32)) as pilot:
        await pilot.pause()
        await run_command(pilot, "e edit.bin")
        checks.append(Check(
            "hex_screen_pushed", True,
            await wait_until(pilot, lambda: _hex_screen(app) is not None),
        ))
        await pilot.press("e")
        await pilot.press("4", "1")
        await pilot.press("w")
        await pilot.pause()
        checks.append(Check(
            "file_written", True,
            (tmp / "edit.bin").read_bytes()[0] == 0x41,
        ))
        await pilot.press("q")
        await pilot.pause()
        checks.append(Check("q_closes", 1, len(app.screen_stack)))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("hex_view_edit_and_save", checks, rows)


SCENARIOS: list[Scenario] = [
    Scenario("hex_view_binary_open", _hex_view_binary_open, ("files", "command")),
    Scenario("hex_view_toggle_text", _hex_view_toggle_text, ("files", "command")),
    Scenario("hex_view_goto_address", _hex_view_goto_address, ("files", "command")),
    Scenario("hex_view_edit_and_save", _hex_view_edit_and_save, ("files", "command")),
]
