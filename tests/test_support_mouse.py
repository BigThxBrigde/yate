"""support_mouse master-switch headless tests (IKJRFK wave-3, run via pilot).

The gate lives in ``YateApp.on_event``: with ``support_mouse = False``
every mouse record is dropped before Textual forwards it to the screen,
so text-area clicks, tab-bar clicks, explorer clicks and terminal wheel
scrolling all become inert.  The enabled side is covered by
test_app_mouse.py / test_app_terminal.py; the positive control here only
proves the gate passes records through with the default config.

Injection note: the pilot's mouse helpers bypass ``App.on_event``
deliberately (they call ``screen._forward_event`` straight away,
textual/pilot.py), so they cannot exercise the shell-level gate.  The
disabled-side tests therefore deliver their mouse records through the
app queue -- the same path the real driver uses (message_pump dispatches
queued ``Event`` instances via ``on_event``).
"""

# tests legitimately poke at internals:
# pyright: reportPrivateUsage=false

from __future__ import annotations

import asyncio
from pathlib import Path

from textual.events import MouseDown, MouseScrollUp, MouseEvent, MouseUp
from textual.pilot import _get_mouse_message_arguments
from textual.widget import Widget
from yate.app import YateApp
from yate.config import YateConfig
from yate.editor_view.editor import EditorView
from conftest import wait_until
from test_app_terminal import _FakePty

# "hello world\nsecond line\n": a two-line document, so the gutter is
# max(3, len("2")) + 3 == 6 cells; cell x = mouse x - 6 (scroll_col 0).
_GUTTER: int = 6


def _driver_mouse(
    app: YateApp,
    target: Widget,
    offset: tuple[int, int],
    event_cls: type[MouseEvent],
    button: int = 0,
) -> None:
    """Post one mouse record through the app queue (the driver's path).

    The record must pass through ``YateApp.on_event`` for the gate to see
    it, which is where every real driver input arrives first.  Uses the
    Textual private helper ``_get_mouse_message_arguments`` (verified on
    8.2.8; revisit on upgrades, same containment discipline as
    keyproto/textual_internals.py).
    """
    kwargs = _get_mouse_message_arguments(target, offset, button=button)
    app.post_message(event_cls(**kwargs))


def _click(app: YateApp, target: Widget, offset: tuple[int, int]) -> None:
    """A driver-shaped click: MouseDown + MouseUp at *target*/*offset*."""
    _driver_mouse(app, target, offset, MouseDown, button=1)
    _driver_mouse(app, target, offset, MouseUp, button=1)


def test_support_mouse_disabled_click_does_not_move_cursor(tmp_path: Path) -> None:
    async def scenario() -> None:
        target = tmp_path / "mouse.txt"
        target.write_text("hello world\nsecond line\n", encoding="utf-8")
        app = YateApp(target=target, config=YateConfig(support_mouse=False))
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            view = app.editor.panes.active_view
            assert view is not None
            buf = app.editor.session.buffer
            assert buf.cursor == (0, 0)
            # x = _GUTTER + 5 would land on cell 5 of "hello world" if the
            # gate let the record through (plan-c click caliber)
            _click(app, view, (_GUTTER + 5, 0))
            await pilot.pause()
            assert buf.cursor == (0, 0)

    asyncio.run(scenario())


def test_support_mouse_disabled_click_does_not_switch_tab(tmp_path: Path) -> None:
    async def scenario() -> None:
        first = tmp_path / "one.txt"
        first.write_text("one\n", encoding="utf-8")
        second = tmp_path / "two.txt"
        second.write_text("two\n", encoding="utf-8")
        app = YateApp(target=first, config=YateConfig(support_mouse=False))
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            session = app.editor.session
            # open a second document through the real :e flow, then hop
            # back so the click below targets tab #2 (index stays 0)
            app.editor.run_command(f"e {second}")
            assert await wait_until(pilot, lambda: session.doc.path == second)
            app.editor.run_command("bp")
            assert await wait_until(pilot, lambda: session.index == 0)
            tabbar = app.editor.tabbar
            assert tabbar is not None
            # tab hit-testing uses the build() cell spans (chrome.py)
            _text, regions = tabbar.build(tabbar.size.width or 80)
            second_span = next(span for span in regions if span[2] == 1)
            _click(app, tabbar, (second_span[0], 0))
            await pilot.pause()
            assert session.index == 0

    asyncio.run(scenario())


def test_support_mouse_disabled_click_does_not_open_explorer_file(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        # the workspace stores the resolved root; on Windows TEMP may be an
        # 8.3 short name, so resolve before every node-path comparison
        root = tmp_path.resolve()
        (root / "a.txt").write_text("alpha\n", encoding="utf-8")
        app = YateApp(target=root, config=YateConfig(support_mouse=False))
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            tree = app.editor.explorer_tree
            assert tree is not None
            assert tree.display  # a directory target starts with it shown
            line = tree._line_of(root / "a.txt")
            assert line is not None
            docs_before = len(app.editor.session.docs)
            path_before = app.editor.session.doc.path
            _click(app, tree, (2, line))
            await pilot.pause()
            assert len(app.editor.session.docs) == docs_before
            assert app.editor.session.doc.path is path_before

    asyncio.run(scenario())


def test_support_mouse_enabled_click_moves_cursor(tmp_path: Path) -> None:
    """Positive control: the default config passes mouse records through.

    Uses the pilot's own click helper here: it forwards at screen level,
    so this case exercises the widget-side flow (MouseFlows) with the
    gate wide open -- complementing the app-queue path above.
    """

    async def scenario() -> None:
        target = tmp_path / "mouse.txt"
        target.write_text("hello world\nsecond line\n", encoding="utf-8")
        app = YateApp(target=target)  # support_mouse defaults to True
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            await pilot.click(EditorView, offset=(_GUTTER + 5, 0))
            await pilot.pause()
            assert app.editor.session.buffer.cursor == (0, 5)

    asyncio.run(scenario())


def test_support_mouse_disabled_wheel_does_not_scroll_terminal(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        app = YateApp(config=YateConfig(support_mouse=False))
        app.editor.terminal_panel.view_factory = _FakePty
        _FakePty.instances = []
        async with app.run_test(size=(100, 30)) as pilot:
            panel = app.editor.terminal_panel
            assert panel is not None
            await pilot.press("ctrl+`")
            shown = await wait_until(pilot, lambda: panel.view.proc is not None)
            assert shown
            proc = _FakePty.instances[0]
            # produce enough simulated output to create scrollback
            proc.emit_output(b"scroll me\r\n" * 40)
            assert await wait_until(
                pilot, lambda: panel.view.emulator.max_scroll() > 0,
            )
            view = panel.view
            assert view._scroll == 0
            _driver_mouse(app, view, (5, 0), MouseScrollUp)
            await pilot.pause()
            assert view._scroll == 0

    asyncio.run(scenario())
