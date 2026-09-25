"""Tests for the integrated terminal: emulator, shell resolution, PTY lifecycle."""

from __future__ import annotations

import asyncio
import os
import sys
import threading
from pathlib import Path
from typing import Any, cast

from collections.abc import Callable

import pytest

from yate.editor_term import (
    PtyProcess,
    PtyProcessError,
    TerminalEmulator,
    key_to_terminal,
    resolve_shell,
    shell_label,
)
from yate.editor_term import pty_proc
from yate.editor_view.terminal import TerminalView


def _text(emu: TerminalEmulator) -> str:
    return "\n".join(
        "".join(cell.char for cell in line).rstrip()
        for line in emu.view_lines(0)
    )


# --- key encoding -----------------------------------------------------------


def test_printable_and_named() -> None:
    assert key_to_terminal("a", "a") == "a"
    assert key_to_terminal("enter") == "\r"
    assert key_to_terminal("backspace") == "\x7f"
    assert key_to_terminal("up") == "\x1b[A"
    assert key_to_terminal("f1") == "\x1bOP"
    assert key_to_terminal("tab") == "\t"


def test_ctrl_letters() -> None:
    assert key_to_terminal("ctrl+c") == "\x03"
    assert key_to_terminal("ctrl+z") == "\x1a"
    assert key_to_terminal("ctrl+space") == "\x00"
    assert key_to_terminal("ctrl+]") == "\x1d"


def test_alt_prefix() -> None:
    assert key_to_terminal("alt+x") == "\x1bx"


def test_shift_tab() -> None:
    assert key_to_terminal("shift+tab") == "\x1b[Z"


def test_unknown() -> None:
    assert key_to_terminal("super+x") is None


# --- emulator basics --------------------------------------------------------


def test_print_cr_lf_and_wrap() -> None:
    emu = TerminalEmulator(5, 3)
    emu.feed(b"abcde\r\nf")
    screen = _text(emu)
    assert screen.startswith("abcde\n")
    assert "f" in screen.splitlines()[1]


def test_backspace_and_tab() -> None:
    emu = TerminalEmulator(20, 2)
    emu.feed(b"ab\x08c")
    assert _text(emu).splitlines()[0] == "ac"
    emu = TerminalEmulator(20, 2)
    emu.feed(b"1\tx")
    line = _text(emu).splitlines()[0]
    assert line.index("x") == 8


def test_cursor_movement() -> None:
    emu = TerminalEmulator(10, 2)
    emu.feed(b"abcde\x1b[2Dx\x1b[1;4Hy")
    line = _text(emu).splitlines()[0]
    # CSI 2D from col 5 lands on col 3 (x); CSI 1;4H places y on col 3
    assert line == "abcye"
    assert line[3] == "y"
    rows = emu.view_lines(0)
    assert len(rows) == 2
    assert all(cell.char in (" ", "") for cell in rows[1])


def test_erase_line_and_display() -> None:
    emu = TerminalEmulator(6, 2)
    emu.feed(b"hello\r\x1b[0K")
    assert _text(emu).splitlines()[0] == ""
    emu.feed(b"abc")
    emu.feed(b"\r\n\x1b[1A\x1b[2K")  # back up, erase the whole line
    assert _text(emu).splitlines()[0] == ""


def test_scrollback() -> None:
    emu = TerminalEmulator(4, 2)
    emu.feed(b"aaaa\r\nbbbb\r\ncccc\r\ndddd\r\n")
    assert emu.max_scroll() >= 2
    back = emu.view_lines(emu.max_scroll())
    joined = "".join(cell.char for line in back for cell in line)
    assert "aaaa" in joined


def test_scroll_region_keeps_history() -> None:
    emu = TerminalEmulator(6, 4)
    emu.feed(b"top")
    emu.feed(b"\x1b[2;3r")  # DECSTBM rows 2..3
    for _ in range(3):
        emu.feed(b"\r\n\x1b[2Hx")
    emu.feed(b"\x1b[r")
    line0 = _text(emu).splitlines()[0]
    assert "top" in line0


def test_alt_screen_1049_restores_primary() -> None:
    emu = TerminalEmulator(10, 3)
    emu.feed(b"primary")
    emu.feed(b"\x1b[?1049h")
    emu.feed(b"alt-content")
    assert emu.in_alt
    assert "primary" not in _text(emu)
    emu.feed(b"\x1b[?1049l")
    assert not emu.in_alt
    assert "primary" in _text(emu)


def test_sgr_colors() -> None:
    emu = TerminalEmulator(4, 1)
    emu.feed(b"\x1b[31mA\x1b[38;5;196mB\x1b[38;2;1;2;3mC\x1b[0mD")
    line = emu.view_lines(0)[0]
    assert line[0].fg == (204, 0, 0)
    assert line[1].fg == (255, 0, 0)
    assert line[2].fg == (1, 2, 3)
    assert line[3].fg is None


def test_attributes_and_reverse() -> None:
    emu = TerminalEmulator(4, 1)
    emu.feed(b"\x1b[1;4;7mA\x1b[0mB")
    cell = emu.view_lines(0)[0][0]
    assert cell.bold and cell.underline and cell.reverse
    assert not emu.view_lines(0)[0][1].bold


def test_dsr_and_da_responses() -> None:
    replies: list[bytes] = []
    emu = TerminalEmulator(10, 3, on_response=replies.append)
    emu.feed(b"\x1b[6n")
    assert replies[-1].endswith(b"R")
    emu.feed(b"\x1b[c")
    assert replies[-1] == b"\x1b[?1;2c"
    emu.feed(b"\x1b[5n")
    assert replies[-1] == b"\x1b[0n"


def test_osc_title() -> None:
    emu = TerminalEmulator(10, 2)
    emu.feed(b"\x1b]2;my shell\x07")
    assert emu.title == "my shell"
    emu.feed(b"\x1b]0;other\x1b\\")
    assert emu.title == "other"


def test_resize_keeps_bottom() -> None:
    emu = TerminalEmulator(10, 3)
    emu.feed(b"one\r\ntwo\r\nthree")
    emu.resize(10, 2)
    screen = _text(emu)
    assert "two" in screen
    assert "three" in screen
    assert "one" not in screen


def test_resize_shrink_moves_top_rows_to_scrollback() -> None:
    emu = TerminalEmulator(10, 3)
    emu.feed(b"one\r\ntwo\r\nthree")
    emu.resize(10, 2)
    # bottom rows stay on screen ...
    screen = _text(emu)
    assert "two" in screen
    assert "one" not in screen
    # ... and the dropped top row is reachable as history
    history = "".join(
        cell.char for row in emu.view_lines(1) for cell in row
    )
    assert "one" in history


def test_resize_alt_screen_does_not_add_scrollback() -> None:
    emu = TerminalEmulator(10, 3)
    emu.feed(b"one\r\ntwo\r\nthree")
    emu.feed(b"\x1b[?1049h")
    emu.resize(10, 2)
    assert emu.scrollback == []


def test_wide_character() -> None:
    emu = TerminalEmulator(6, 1)
    emu.feed("中x".encode())
    line = emu.view_lines(0)[0]
    assert line[0].char == "中"
    assert line[1].char == ""  # continuation column
    assert line[2].char == "x"


def test_hide_cursor() -> None:
    emu = TerminalEmulator(4, 1)
    assert emu.cursor_visible
    emu.feed(b"\x1b[?25l")
    assert not emu.cursor_visible
    emu.feed(b"\x1b[?25h")
    assert emu.cursor_visible


def test_bracketed_paste_mode() -> None:
    emu = TerminalEmulator(4, 1)
    emu.feed(b"\x1b[?2004h")
    assert emu.bracketed_paste
    emu.feed(b"\x1b[?2004l")
    assert not emu.bracketed_paste


# --- shell resolution -------------------------------------------------------


def test_configured_command_is_split() -> None:
    argv = resolve_shell("zsh -l")
    assert argv[0] == "zsh"
    assert "-l" in argv


def test_configured_existing_windows_path_verbatim() -> None:
    if not sys.platform.startswith("win"):
        pytest.skip("windows path semantics")
    argv = resolve_shell(sys.executable)
    assert argv == [sys.executable]


def test_default_shell_is_usable() -> None:
    argv = resolve_shell("")
    assert argv
    assert argv[0]
    if sys.platform.startswith("win"):
        joined = " ".join(argv).lower()
        assert "powershell" in joined or "cmd" in joined


def test_label() -> None:
    assert shell_label(["/usr/bin/bash", "-l"]) == "bash"
    if sys.platform.startswith("win"):
        assert shell_label([r"C:\x\pwsh.exe"]) == "pwsh.exe"
    assert shell_label([]) == "shell"


# --- PTY process lifecycle --------------------------------------------------


class _FakePtyImpl:
    """Stand-in for the platform PTY backend used by PtyProcess."""

    instances: list[_FakePtyImpl] = []

    def __init__(self, owner: PtyProcess) -> None:
        self.owner = owner
        self.spawned = False
        self.sent: list[bytes] = []
        self.resizes: list[tuple[int, int]] = []
        self.terminated = False
        self.closed = False
        self.proceed = threading.Event()
        _FakePtyImpl.instances.append(self)

    def spawn(self) -> None:
        self.spawned = True

    def read_loop(self) -> None:
        self.owner.emit_output(b"welcome\r\n")
        self.proceed.wait(timeout=2)
        self.owner.process_finished(0 if self.terminated else 7)

    def write(self, data: bytes) -> None:
        self.sent.append(data)

    def resize(self, cols: int, rows: int) -> None:
        self.resizes.append((cols, rows))

    def terminate(self) -> None:
        self.terminated = True
        self.proceed.set()

    def close(self) -> None:
        self.closed = True


@pytest.fixture
def fake_pty(monkeypatch: pytest.MonkeyPatch) -> type[_FakePtyImpl]:
    """Swap in the fake PTY backend and reset its instance log."""
    _FakePtyImpl.instances = []
    attr = "_ConPty" if os.name == "nt" else "_UnixPty"
    monkeypatch.setattr(pty_proc, attr, _FakePtyImpl)
    return _FakePtyImpl


def test_start_write_resize_terminate(fake_pty: type[_FakePtyImpl]) -> None:
    async def _scenario() -> None:
        outputs: list[bytes] = []
        exits: list[int | None] = []
        proc = PtyProcess(["shell"], Path.cwd(), 80, 24)
        await proc.start(outputs.append, exits.append)
        proc.write(b"ls\r")
        proc.resize(100, 30)
        await asyncio.sleep(0.05)
        proc.terminate()
        code = await asyncio.wait_for(proc.wait_closed(), 3)
        impl = fake_pty.instances[0]
        assert impl.spawned
        assert impl.sent == [b"ls\r"]
        assert (100, 30) in impl.resizes
        assert impl.terminated
        assert code == 0
        assert exits == [0]
        assert any(b"welcome" in chunk for chunk in outputs)

    asyncio.run(_scenario())


def test_natural_exit_code(fake_pty: type[_FakePtyImpl]) -> None:
    async def _scenario() -> None:
        exits: list[int | None] = []
        proc = PtyProcess(["shell"], Path.cwd(), 80, 24)
        await proc.start(lambda _b: None, exits.append)
        fake_pty.instances[0].proceed.set()
        code = await asyncio.wait_for(proc.wait_closed(), 3)
        assert code == 7
        assert exits == [7]

    asyncio.run(_scenario())


def test_empty_argv_rejected(fake_pty: type[_FakePtyImpl]) -> None:
    with pytest.raises(PtyProcessError):
        PtyProcess([], Path.cwd(), 80, 24)


def test_write_after_terminate_is_noop(fake_pty: type[_FakePtyImpl]) -> None:
    async def _scenario() -> None:
        proc = PtyProcess(["shell"], Path.cwd(), 80, 24)
        await proc.start(lambda _b: None, lambda _c: None)
        proc.terminate()
        await asyncio.wait_for(proc.wait_closed(), 3)
        proc.write(b"x")  # must not raise
        assert fake_pty.instances[0].sent == []

    asyncio.run(_scenario())


def test_detach_drops_late_thread_events(fake_pty: type[_FakePtyImpl]) -> None:
    """A reader thread outliving teardown must neither call UI callbacks
    nor raise when the event loop is already closed."""

    async def _scenario() -> None:
        outputs: list[bytes] = []
        exits: list[int | None] = []
        proc = PtyProcess(["shell"], Path.cwd(), 80, 24)
        await proc.start(outputs.append, exits.append)
        await asyncio.sleep(0.05)
        proc.detach()
        # late events after detach touch neither callback ...
        proc.emit_output(b"late\r\n")
        proc.process_finished(9)
        await asyncio.sleep(0.05)
        assert not any(b"late" in chunk for chunk in outputs)
        assert 9 not in exits
        # ... and a closed loop cannot raise into the reader thread
        closed_loop = asyncio.new_event_loop()
        closed_loop.close()
        cast(Any, proc)._loop = closed_loop
        proc.emit_output(b"later\r\n")
        proc.process_finished(10)

    asyncio.run(_scenario())


# --- view spawn failure ------------------------------------------------------


class _FailingProc:
    """PtyProcess stand-in whose start always fails, like a dead ConPTY."""

    def __init__(self, argv: list[str], cwd: Path, cols: int, rows: int) -> None:
        self.argv = argv

    async def start(
        self,
        on_output: Callable[[bytes], None],
        on_exit: Callable[[int | None], None],
    ) -> None:
        raise PtyProcessError("no ConPTY here")


class _WorkingProc:
    """PtyProcess stand-in that starts fine and stays quiet."""

    def __init__(self, argv: list[str], cwd: Path, cols: int, rows: int) -> None:
        self.argv = argv

    async def start(
        self,
        on_output: Callable[[bytes], None],
        on_exit: Callable[[int | None], None],
    ) -> None:
        return None


def test_spawn_failure_marks_the_view_dead_and_revivable() -> None:
    """A failed spawn resets the view, so the revive path can fire again."""

    async def _scenario() -> None:
        view = TerminalView(cast(Any, None))
        with pytest.raises(PtyProcessError):
            await view.start(["shell"], Path.cwd(), factory=_FailingProc)
        assert view.proc is None
        assert view.dead
        assert not view.started  # open() / any key will spawn again

        # The revive path itself: a fresh start with a working process wins.
        await view.start(["shell"], Path.cwd(), factory=_WorkingProc)
        assert view.proc is not None
        assert not view.dead
        assert view.started

    asyncio.run(_scenario())
