"""Terminal panel headless Textual UI tests (run via pilot, no real terminal)."""

# tests legitimately poke at internals:
# pyright: reportPrivateUsage=false

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, cast, override
from yate.app import YateApp
from yate.editor_term.pty_proc import ExitFn, OutputFn
from conftest import message_text, wait_until

def test_set_terminal_height_reports_and_validates() -> None:
    async def scenario() -> None:
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            app.editor.run_command("set terminal_height=20")
            await pilot.pause()
            assert app.editor.config.terminal_height == 20
            assert "terminal height: 20 rows" in message_text(app)

            app.editor.run_command("set terminal_height=99")
            await pilot.pause()
            assert app.editor.config.terminal_height == 20  # rejected
            assert "between 3 and 40" in message_text(app)

            app.editor.run_command("set terminal_height=abc")
            await pilot.pause()
            assert "integer" in message_text(app)

    asyncio.run(scenario())


def test_termclose_without_open_terminal_warns() -> None:
    async def scenario() -> None:
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            assert not app.editor.terminal_panel.is_visible
            app.editor.run_command("termclose")
            await pilot.pause()
            assert "already hidden" in message_text(app)

    asyncio.run(scenario())


def test_term_commands_report_shown_and_hidden() -> None:
    async def scenario() -> None:
        app = YateApp()
        app.editor.terminal_panel.view_factory = _FakePty
        _FakePty.instances = []
        async with app.run_test(size=(100, 30)) as pilot:
            panel = app.editor.terminal_panel
            assert panel is not None
            app.editor.run_command("term")
            await wait_until(pilot, lambda: panel.view.proc is not None)
            assert "terminal shown" in message_text(app)
            app.editor.run_command("termclose")
            await pilot.pause()
            assert not panel.display
            assert "terminal hidden" in message_text(app)

    asyncio.run(scenario())


# --------------------------------------------------------------------- fake PTY


class _FakePty:
    """In-memory PTY substitute used by the terminal UI tests."""

    instances: list[_FakePty] = []

    def __init__(self, argv: list[str], cwd: Any, cols: int, rows: int) -> None:
        self.argv = list(argv)
        self.cwd = cwd
        self.cols, self.rows = cols, rows
        self.sent: list[bytes] = []
        self.started = False
        self.exited = False
        self._on_output: OutputFn | None = None
        self._on_exit: ExitFn | None = None
        _FakePty.instances.append(self)

    async def start(
        self, on_output: OutputFn,
        on_exit: ExitFn,
    ) -> None:
        """Fake counterpart of :meth:`PtyProcess.start` recording the callbacks."""
        self.started = True
        self._on_output = on_output
        self._on_exit = on_exit

    def write(self, data: bytes) -> None:
        """Fake counterpart of :meth:`PtyProcess.write` recording the bytes."""
        self.sent.append(data)

    def resize(self, cols: int, rows: int) -> None:
        """Fake counterpart of :meth:`PtyProcess.resize` storing the size."""
        self.cols, self.rows = cols, rows

    def exit(self, code: int = 0) -> None:
        """Fake child exit: fires the exit callback at most once."""
        if not self.exited and self._on_exit is not None:
            self.exited = True
            self._on_exit(code)

    def emit_output(self, data: bytes) -> None:
        """Fake counterpart of :meth:`PtyProcess.emit_output` for tests."""
        if self._on_output is not None:
            self._on_output(data)

    def terminate(self) -> None:
        """Fake terminate: delegates to the fake exit with code 0."""
        self.exit(0)

    async def wait_closed(self) -> None:
        """Fake wait: returns once the fake child has exited."""
        for _ in range(200):
            if self.exited:
                return
            await asyncio.sleep(0.01)


# ----------------------------------------------------------------- terminal UI


async def _press_toggle(pilot: Any) -> None:
    # Textual key names for grave vary; the app accepts both spellings.
    await pilot.press("ctrl+`")


def test_nul_byte_from_windows_ctrl_grave_matches_toggle() -> None:
    # Windows conhost encodes Ctrl+grave as a NUL byte (ToUnicodeEx
    # yields no character); Textual names that key "ctrl+@", and it
    # must be one of the accepted toggle keys.
    from textual._xterm_parser import XTermParser

    from yate.editor_view.terminal import TOGGLE_KEYS

    names = [
        getattr(m, "key", None) for m in XTermParser().feed("\x00")
    ]
    assert names == ["ctrl+@"]
    assert "ctrl+@" in TOGGLE_KEYS


def test_early_pty_output_survives_first_layout() -> None:
    # Regression: a shell that prints its banner before Textual has
    # laid out the panel used to spawn at the 80x24 fallback size; the
    # first lines were discarded when the viewport shrank on layout.
    class _ImmediatePty(_FakePty):
        @override
        async def start(
            self, on_output: OutputFn,
            on_exit: ExitFn,
        ) -> None:
            """Fake start that emits a banner before the first layout."""
            await super().start(on_output, on_exit)
            loop = asyncio.get_running_loop()
            loop.call_soon(
                lambda: on_output(b"YATE_EARLY_BANNER\r\n")
            )

    async def scenario() -> None:
        app = YateApp()
        app.editor.terminal_panel.view_factory = _ImmediatePty
        _FakePty.instances = []
        async with app.run_test(size=(100, 30)) as pilot:
            panel = app.editor.terminal_panel
            assert panel is not None
            await _press_toggle(pilot)

            def banner_visible() -> bool:
                return "YATE_EARLY_BANNER" in "".join(
                    cell.char
                    for row in panel.view.emulator.view_lines(0)
                    for cell in row
                )

            assert await wait_until(pilot, banner_visible)
            proc = _FakePty.instances[0]
            # spawned at the laid-out size, not the 24-row fallback
            assert proc.rows < 24
            assert proc.cols == 100

    asyncio.run(scenario())


def test_ctrl_grave_toggles_focuses_and_forwards() -> None:
    async def scenario() -> None:
        app = YateApp()
        app.editor.terminal_panel.view_factory = _FakePty
        _FakePty.instances = []
        async with app.run_test(size=(100, 30)) as pilot:
            panel = app.editor.terminal_panel
            assert panel is not None
            assert not panel.display

            await _press_toggle(pilot)
            shown = await wait_until(pilot, lambda: panel.view.proc is not None)
            assert shown
            assert panel.display
            assert app.focused is panel.view
            proc = _FakePty.instances[0]
            assert proc.started
            assert proc.argv  # a default shell was resolved
            assert proc.cols == 100
            assert proc.rows >= 8

            # PTY output lands in the emulator and renders
            proc.emit_output(b"YATE_FAKE_OUTPUT\r\n")
            await pilot.pause()
            painted = "".join(
                cell.char
                for row in panel.view.emulator.view_lines(0)
                for cell in row
            )
            assert "YATE_FAKE_OUTPUT" in painted

            # keys typed in the panel are forwarded byte-for-byte
            await pilot.press("l", "s")
            assert b"".join(proc.sent) == b"ls"

            # the dock hugs the bottom, above the status/prompt strip
            bottom = app.query_one("#bottom")
            assert bottom.region.bottom == 30
            assert panel.region.bottom <= bottom.region.y

            # toggle again hides it and returns focus to the editor
            await _press_toggle(pilot)
            await pilot.pause()
            assert not panel.display
            assert app.focused is app.editor.panes.active_view

            # reopening reuses the still-alive shell process
            await _press_toggle(pilot)
            await wait_until(pilot, lambda: app.editor.terminal_panel.is_visible)
            assert panel.display
            assert cast(Any, panel.view).proc is proc

    asyncio.run(scenario())


def test_terminal_focused_ctrl1_returns_focus_to_editor() -> None:
    # N19: the terminal view used to swallow every key once focused;
    # ctrl+1 must hand focus back to the editor without the shell
    # input stream seeing the key (one keypress, one dispatch -- R10).
    async def scenario() -> None:
        app = YateApp()
        app.editor.terminal_panel.view_factory = _FakePty
        _FakePty.instances = []
        async with app.run_test(size=(100, 30)) as pilot:
            panel = app.editor.terminal_panel
            assert panel is not None
            await _press_toggle(pilot)
            shown = await wait_until(pilot, lambda: panel.view.proc is not None)
            assert shown
            assert app.focused is panel.view
            proc = _FakePty.instances[0]
            assert proc.started

            await pilot.press("ctrl+1")
            await pilot.pause()
            assert app.focused is app.editor.panes.active_view
            assert b"".join(proc.sent) == b""

    asyncio.run(scenario())


def test_terminal_click_focuses_view() -> None:
    # plan-d (issue IKJRFK): clicking the terminal view must focus it so
    # typed keys reach the shell (click-to-focus), VS Code style.
    from yate.editor_view.terminal import TerminalView

    async def scenario() -> None:
        app = YateApp()
        app.editor.terminal_panel.view_factory = _FakePty
        _FakePty.instances = []
        async with app.run_test(size=(100, 30)) as pilot:
            panel = app.editor.terminal_panel
            assert panel is not None
            await _press_toggle(pilot)
            shown = await wait_until(pilot, lambda: panel.view.proc is not None)
            assert shown

            # start from the editor so the click itself must move focus
            await pilot.press("ctrl+1")
            await pilot.pause()
            assert app.focused is app.editor.panes.active_view

            clicked = await pilot.click(TerminalView, offset=(5, 0))
            await pilot.pause()
            assert clicked
            assert app.focused is panel.view

    asyncio.run(scenario())


def test_terminal_click_does_not_write_shell() -> None:
    # plan-d (issue IKJRFK): a click focuses the terminal but must never
    # send input to the shell -- no bytes written, screen untouched.
    from yate.editor_view.terminal import TerminalView

    async def scenario() -> None:
        app = YateApp()
        app.editor.terminal_panel.view_factory = _FakePty
        _FakePty.instances = []
        async with app.run_test(size=(100, 30)) as pilot:
            panel = app.editor.terminal_panel
            assert panel is not None
            await _press_toggle(pilot)
            shown = await wait_until(pilot, lambda: panel.view.proc is not None)
            assert shown
            proc = _FakePty.instances[0]

            # make the emulator grid non-trivial before the click
            proc.emit_output(b"YATE_FAKE_OUTPUT\r\n")
            assert await wait_until(
                pilot,
                lambda: "YATE_FAKE_OUTPUT" in "".join(
                    cell.char
                    for row in panel.view.emulator.view_lines(0)
                    for cell in row
                ),
            )

            def rows() -> list[str]:
                return [
                    "".join(cell.char for cell in row)
                    for row in panel.view.emulator.view_lines(0)
                ]

            lines_before = rows()
            await pilot.press("ctrl+1")
            await pilot.pause()

            clicked = await pilot.click(TerminalView, offset=(5, 0))
            await pilot.pause()
            assert clicked
            assert b"".join(proc.sent) == b""
            assert rows() == lines_before

    asyncio.run(scenario())


def test_real_terminal_grave_key_names_toggle_panel() -> None:
    # Ctrl+grave is the NUL byte on Windows conhost / legacy xterm
    # (ToUnicodeEx yields no character), so Textual names it
    # "ctrl+@"; under the kitty keyboard protocol it is named
    # "ctrl+grave_accent". Neither used to match TOGGLE_KEYS, so the
    # panel could not be closed from a real Windows terminal.
    async def scenario() -> None:
        for close_key in ("ctrl+@", "ctrl+grave_accent"):
            app = YateApp()
            app.editor.terminal_panel.view_factory = _FakePty
            _FakePty.instances = []
            async with app.run_test(size=(100, 30)) as pilot:
                panel = app.editor.terminal_panel
                assert panel is not None
                view = panel.view

                await pilot.press("ctrl+`")
                await wait_until(pilot, lambda: view.proc is not None)
                assert panel.display
                assert app.focused is view
                proc = _FakePty.instances[0]

                # the real key name closes the panel while the terminal
                # has focus, and is not forwarded as a NUL byte
                await pilot.press(close_key)
                await pilot.pause()
                assert not panel.display, close_key
                assert b"\x00" not in b"".join(proc.sent)
                assert app.focused is app.editor.panes.active_view

                # same name reopens it now that the editor has focus.
                # ctrl+@ is also the NUL byte Ctrl+Space sends on Windows
                # conhost, so from the editor it means manual completion
                # and must not reopen the terminal -- the unambiguous
                # grave-accent name reopens it instead.
                if close_key == "ctrl+@":
                    await pilot.press("ctrl+@")
                    for _ in range(3):
                        await pilot.pause()
                    assert not panel.display
                    assert not app.editor.terminal_panel.is_visible
                    await pilot.press("ctrl+grave_accent")
                else:
                    await pilot.press(close_key)
                await wait_until(
                    pilot, lambda: app.editor.terminal_panel.is_visible)
                assert panel.display, close_key

    asyncio.run(scenario())


def test_term_command_exit_and_restart() -> None:
    async def scenario() -> None:
        app = YateApp(keymap="vim")  # ":" ex line is vim-only
        app.editor.terminal_panel.view_factory = _FakePty
        _FakePty.instances = []
        async with app.run_test(size=(100, 30)) as pilot:
            panel = app.editor.terminal_panel
            assert panel is not None

            # :term opens the panel
            await pilot.press("colon")
            for ch in "term":
                await pilot.press(ch)
            await pilot.press("enter")
            shown = await wait_until(pilot, lambda: panel.view.proc is not None)
            assert shown
            proc = _FakePty.instances[0]
            assert "running" in panel.header_text()

            # when the shell exits the panel shows the state and a hint
            proc.exit(0)
            await pilot.pause()
            assert panel.view.dead
            assert "exited" in panel.header_text()

            # any keypress revives the shell via the factory
            await pilot.press("a")
            revived = await wait_until(
                pilot,
                lambda: len(_FakePty.instances) == 2
                and cast(Any, panel.view).proc is _FakePty.instances[1]
                and bool(_FakePty.instances[1].started),
            )
            assert revived
            assert len(_FakePty.instances) == 2

            # :termclose hides the panel (invoked directly because focus is
            # inside the terminal and the prompt keys would be sent to the PTY)
            app.editor.run_command("termclose")
            await pilot.pause()
            assert not panel.display

    asyncio.run(scenario())


# ----------------------------------------------------------------- ctrl+space


def test_nul_byte_opens_completion_not_terminal(tmp_path: Path) -> None:
    async def scenario() -> None:
        (tmp_path / "a.txt").write_text("alpha\nalpha\n", encoding="utf-8")
        app = YateApp(target=tmp_path / "a.txt", keymap="vim")
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            popup = app.editor.completion_popup
            assert popup is not None
            # insert a prefix so the manual completion has candidates
            await pilot.press("i", "a", "l")
            await pilot.pause()
            await pilot.press("ctrl+@")  # NUL: Ctrl+Space on conhost
            shown = await wait_until(pilot, lambda: popup.is_open)
            assert shown
            assert not app.editor.terminal_panel.is_visible

    asyncio.run(scenario())


def test_ctrl_2_chord_names_toggle_terminal_not_completion() -> None:
    # The chord driver reports Ctrl+@ (what US layouts deliver as Ctrl+`)
    # as "ctrl+2" / "ctrl+shift+2" -- the names cover layouts where the
    # physical grave key sits on Shift+2.  Unlike the legacy NUL byte,
    # these chords are unambiguous, so they must toggle the terminal
    # even with the editor focused (completion stays on ctrl+space).
    async def scenario() -> None:
        app = YateApp()
        app.editor.terminal_panel.view_factory = _FakePty
        _FakePty.instances = []
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            panel = app.editor.terminal_panel
            popup = app.editor.completion_popup
            assert panel is not None
            assert popup is not None
            for chord_key in ("ctrl+2", "ctrl+shift+2"):
                await pilot.press(chord_key)
                assert await wait_until(pilot, lambda: panel.is_visible)
                await pilot.press(chord_key)
                assert await wait_until(pilot, lambda: not panel.is_visible)
            assert not popup.is_open

    asyncio.run(scenario())
