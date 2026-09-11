"""Tests for the integrated terminal: emulator, shell resolution, PTY lifecycle."""

from __future__ import annotations

import asyncio
import os
import sys
import threading
import unittest
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

from yate.editor_term import (
    PtyProcess,
    PtyProcessError,
    TerminalEmulator,
    key_to_terminal,
    resolve_shell,
    shell_label,
)
from yate.editor_term import pty_proc


def _text(emu: TerminalEmulator) -> str:
    return "\n".join(
        "".join(cell.char for cell in line).rstrip()
        for line in emu.view_lines(0)
    )


class KeyEncodingTests(unittest.TestCase):
    def test_printable_and_named(self) -> None:
        self.assertEqual(key_to_terminal("a", "a"), "a")
        self.assertEqual(key_to_terminal("enter"), "\r")
        self.assertEqual(key_to_terminal("backspace"), "\x7f")
        self.assertEqual(key_to_terminal("up"), "\x1b[A")
        self.assertEqual(key_to_terminal("f1"), "\x1bOP")
        self.assertEqual(key_to_terminal("tab"), "\t")

    def test_ctrl_letters(self) -> None:
        self.assertEqual(key_to_terminal("ctrl+c"), "\x03")
        self.assertEqual(key_to_terminal("ctrl+z"), "\x1a")
        self.assertEqual(key_to_terminal("ctrl+space"), "\x00")
        self.assertEqual(key_to_terminal("ctrl+]"), "\x1d")

    def test_alt_prefix(self) -> None:
        self.assertEqual(key_to_terminal("alt+x"), "\x1bx")

    def test_shift_tab(self) -> None:
        self.assertEqual(key_to_terminal("shift+tab"), "\x1b[Z")

    def test_unknown(self) -> None:
        self.assertIsNone(key_to_terminal("super+x"))


class EmulatorBasicTests(unittest.TestCase):
    def test_print_cr_lf_and_wrap(self) -> None:
        emu = TerminalEmulator(5, 3)
        emu.feed(b"abcde\r\nf")
        screen = _text(emu)
        self.assertTrue(screen.startswith("abcde\n"))
        self.assertIn("f", screen.splitlines()[1])

    def test_backspace_and_tab(self) -> None:
        emu = TerminalEmulator(20, 2)
        emu.feed(b"ab\x08c")
        self.assertEqual(_text(emu).splitlines()[0], "ac")
        emu = TerminalEmulator(20, 2)
        emu.feed(b"1\tx")
        line = _text(emu).splitlines()[0]
        self.assertEqual(line.index("x"), 8)

    def test_cursor_movement(self) -> None:
        emu = TerminalEmulator(10, 2)
        emu.feed(b"abcde\x1b[2Dx\x1b[1;4Hy")
        line = _text(emu).splitlines()[0]
        # CSI 2D from col 5 lands on col 3 (x); CSI 1;4H places y on col 3
        self.assertEqual(line, "abcye")
        self.assertEqual(line[3], "y")
        rows = emu.view_lines(0)
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(cell.char in (" ", "") for cell in rows[1]))

    def test_erase_line_and_display(self) -> None:
        emu = TerminalEmulator(6, 2)
        emu.feed(b"hello\r\x1b[0K")
        self.assertEqual(_text(emu).splitlines()[0], "")
        emu.feed(b"abc")
        emu.feed(b"\r\n\x1b[1A\x1b[2K")  # back up, erase the whole line
        self.assertEqual(_text(emu).splitlines()[0], "")

    def test_scrollback(self) -> None:
        emu = TerminalEmulator(4, 2)
        emu.feed(b"aaaa\r\nbbbb\r\ncccc\r\ndddd\r\n")
        self.assertGreaterEqual(emu.max_scroll(), 2)
        back = emu.view_lines(emu.max_scroll())
        joined = "".join(cell.char for line in back for cell in line)
        self.assertIn("aaaa", joined)

    def test_scroll_region_keeps_history(self) -> None:
        emu = TerminalEmulator(6, 4)
        emu.feed(b"top")
        emu.feed(b"\x1b[2;3r")  # DECSTBM rows 2..3
        for _ in range(3):
            emu.feed(b"\r\n\x1b[2Hx")
        emu.feed(b"\x1b[r")
        line0 = _text(emu).splitlines()[0]
        self.assertIn("top", line0)

    def test_alt_screen_1049_restores_primary(self) -> None:
        emu = TerminalEmulator(10, 3)
        emu.feed(b"primary")
        emu.feed(b"\x1b[?1049h")
        emu.feed(b"alt-content")
        self.assertTrue(emu.in_alt)
        self.assertNotIn("primary", _text(emu))
        emu.feed(b"\x1b[?1049l")
        self.assertFalse(emu.in_alt)
        self.assertIn("primary", _text(emu))

    def test_sgr_colors(self) -> None:
        emu = TerminalEmulator(4, 1)
        emu.feed(b"\x1b[31mA\x1b[38;5;196mB\x1b[38;2;1;2;3mC\x1b[0mD")
        line = emu.view_lines(0)[0]
        self.assertEqual(line[0].fg, (204, 0, 0))
        self.assertEqual(line[1].fg, (255, 0, 0))
        self.assertEqual(line[2].fg, (1, 2, 3))
        self.assertIsNone(line[3].fg)

    def test_attributes_and_reverse(self) -> None:
        emu = TerminalEmulator(4, 1)
        emu.feed(b"\x1b[1;4;7mA\x1b[0mB")
        cell = emu.view_lines(0)[0][0]
        self.assertTrue(cell.bold and cell.underline and cell.reverse)
        self.assertFalse(emu.view_lines(0)[0][1].bold)

    def test_dsr_and_da_responses(self) -> None:
        replies: list[bytes] = []
        emu = TerminalEmulator(10, 3, on_response=replies.append)
        emu.feed(b"\x1b[6n")
        self.assertTrue(replies[-1].endswith(b"R"))
        emu.feed(b"\x1b[c")
        self.assertEqual(replies[-1], b"\x1b[?1;2c")
        emu.feed(b"\x1b[5n")
        self.assertEqual(replies[-1], b"\x1b[0n")

    def test_osc_title(self) -> None:
        emu = TerminalEmulator(10, 2)
        emu.feed(b"\x1b]2;my shell\x07")
        self.assertEqual(emu.title, "my shell")
        emu.feed(b"\x1b]0;other\x1b\\")
        self.assertEqual(emu.title, "other")

    def test_resize_keeps_bottom(self) -> None:
        emu = TerminalEmulator(10, 3)
        emu.feed(b"one\r\ntwo\r\nthree")
        emu.resize(10, 2)
        screen = _text(emu)
        self.assertIn("two", screen)
        self.assertIn("three", screen)
        self.assertNotIn("one", screen)

    def test_resize_shrink_moves_top_rows_to_scrollback(self) -> None:
        emu = TerminalEmulator(10, 3)
        emu.feed(b"one\r\ntwo\r\nthree")
        emu.resize(10, 2)
        # bottom rows stay on screen ...
        screen = _text(emu)
        self.assertIn("two", screen)
        self.assertNotIn("one", screen)
        # ... and the dropped top row is reachable as history
        history = "".join(
            cell.char for row in emu.view_lines(1) for cell in row
        )
        self.assertIn("one", history)

    def test_resize_alt_screen_does_not_add_scrollback(self) -> None:
        emu = TerminalEmulator(10, 3)
        emu.feed(b"one\r\ntwo\r\nthree")
        emu.feed(b"\x1b[?1049h")
        emu.resize(10, 2)
        self.assertEqual(emu.scrollback, [])

    def test_wide_character(self) -> None:
        emu = TerminalEmulator(6, 1)
        emu.feed("中x".encode("utf-8"))
        line = emu.view_lines(0)[0]
        self.assertEqual(line[0].char, "中")
        self.assertEqual(line[1].char, "")  # continuation column
        self.assertEqual(line[2].char, "x")

    def test_hide_cursor(self) -> None:
        emu = TerminalEmulator(4, 1)
        self.assertTrue(emu.cursor_visible)
        emu.feed(b"\x1b[?25l")
        self.assertFalse(emu.cursor_visible)
        emu.feed(b"\x1b[?25h")
        self.assertTrue(emu.cursor_visible)

    def test_bracketed_paste_mode(self) -> None:
        emu = TerminalEmulator(4, 1)
        emu.feed(b"\x1b[?2004h")
        self.assertTrue(emu.bracketed_paste)
        emu.feed(b"\x1b[?2004l")
        self.assertFalse(emu.bracketed_paste)


class ShellResolutionTests(unittest.TestCase):
    def test_configured_command_is_split(self) -> None:
        argv = resolve_shell("zsh -l")
        self.assertEqual(argv[0], "zsh")
        self.assertIn("-l", argv)

    def test_configured_existing_windows_path_verbatim(self) -> None:
        if not sys.platform.startswith("win"):
            self.skipTest("windows path semantics")
        argv = resolve_shell(sys.executable)
        self.assertEqual(argv, [sys.executable])

    def test_default_shell_is_usable(self) -> None:
        argv = resolve_shell("")
        self.assertTrue(argv)
        self.assertTrue(argv[0])
        if sys.platform.startswith("win"):
            joined = " ".join(argv).lower()
            self.assertTrue("powershell" in joined or "cmd" in joined)

    def test_label(self) -> None:
        self.assertEqual(shell_label(["/usr/bin/bash", "-l"]), "bash")
        if sys.platform.startswith("win"):
            self.assertEqual(shell_label([r"C:\x\pwsh.exe"]), "pwsh.exe")
        self.assertEqual(shell_label([]), "shell")


class _FakePtyImpl:
    """Stand-in for the platform PTY backend used by PtyProcess."""

    instances: list["_FakePtyImpl"] = []

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


class PtyProcessLifecycleTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        _FakePtyImpl.instances = []
        self._attr = "_ConPty" if os.name == "nt" else "_UnixPty"

    async def test_start_write_resize_terminate(self) -> None:
        outputs: list[bytes] = []
        exits: list[int | None] = []
        with patch.object(pty_proc, self._attr, _FakePtyImpl):
            proc = PtyProcess(["shell"], Path.cwd(), 80, 24)
            await proc.start(outputs.append, exits.append)
            proc.write(b"ls\r")
            proc.resize(100, 30)
            await asyncio.sleep(0.05)
            proc.terminate()
            code = await asyncio.wait_for(proc.wait_closed(), 3)
        impl = _FakePtyImpl.instances[0]
        self.assertTrue(impl.spawned)
        self.assertEqual(impl.sent, [b"ls\r"])
        self.assertIn((100, 30), impl.resizes)
        self.assertTrue(impl.terminated)
        self.assertEqual(code, 0)
        self.assertEqual(exits, [0])
        self.assertTrue(any(b"welcome" in chunk for chunk in outputs))

    async def test_natural_exit_code(self) -> None:
        exits: list[int | None] = []
        with patch.object(pty_proc, self._attr, _FakePtyImpl):
            proc = PtyProcess(["shell"], Path.cwd(), 80, 24)
            await proc.start(lambda _b: None, exits.append)
            _FakePtyImpl.instances[0].proceed.set()
            code = await asyncio.wait_for(proc.wait_closed(), 3)
        self.assertEqual(code, 7)
        self.assertEqual(exits, [7])

    def test_empty_argv_rejected(self) -> None:
        with patch.object(pty_proc, self._attr, _FakePtyImpl):
            with self.assertRaises(PtyProcessError):
                PtyProcess([], Path.cwd(), 80, 24)

    async def test_write_after_terminate_is_noop(self) -> None:
        with patch.object(pty_proc, self._attr, _FakePtyImpl):
            proc = PtyProcess(["shell"], Path.cwd(), 80, 24)
            await proc.start(lambda _b: None, lambda _c: None)
            proc.terminate()
            await asyncio.wait_for(proc.wait_closed(), 3)
            proc.write(b"x")  # must not raise
        self.assertEqual(_FakePtyImpl.instances[0].sent, [])

    async def test_detach_drops_late_thread_events(self) -> None:
        """A reader thread outliving teardown must neither call UI callbacks
        nor raise when the event loop is already closed."""
        outputs: list[bytes] = []
        exits: list[int | None] = []
        with patch.object(pty_proc, self._attr, _FakePtyImpl):
            proc = PtyProcess(["shell"], Path.cwd(), 80, 24)
            await proc.start(outputs.append, exits.append)
            await asyncio.sleep(0.05)
            proc.detach()
            # late events after detach touch neither callback ...
            proc.emit_output(b"late\r\n")
            proc.process_finished(9)
            await asyncio.sleep(0.05)
            self.assertFalse(any(b"late" in chunk for chunk in outputs))
            self.assertNotIn(9, exits)
            # ... and a closed loop cannot raise into the reader thread
            closed_loop = asyncio.new_event_loop()
            closed_loop.close()
            cast(Any, proc)._loop = closed_loop
            proc.emit_output(b"later\r\n")
            proc.process_finished(10)


if __name__ == "__main__":
    unittest.main()
