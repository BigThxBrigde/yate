"""One-shot probe: does CSI ?9001h (win32-input-mode) give conpty
full-fidelity key records (vk + modifier state) for the chords WT otherwise
legacy-encodes (ctrl+shift+letter, ctrl+digit)?

Run inside the terminal under test:

    d:\\Programming\\yate\\.venv\\Scripts\\python.exe .trae\\documents\\keybinding-fix-wt\\win32im_probe.py

Press, in order:  down, a, ctrl+shift+e, ctrl+1, ctrl+space, ctrl+q (quits).
Paste the printed lines back into the chat.

Baseline for comparison is the 2026-09-26 22:11 yate trace (no ?9001h):
down/a arrive as chars, ctrl+shift+e as \\x05, ctrl+1 as '1'.
"""

from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes

from textual.drivers import win32


def main() -> None:
    restore = win32.enable_application_mode()
    print("probe: press down, a, ctrl+shift+e, ctrl+1, ctrl+space, ctrl+q(quit)")
    print("baseline expectations (no 9001h): vk=0/state=0 for the chords")
    # Ask WT for win32-input-mode frames; conpty decodes them into records.
    sys.stdout.write("\x1b[?9001h")
    sys.stdout.flush()
    try:
        h_in = win32.GetStdHandle(win32.STD_INPUT_HANDLE)
        read_count = wintypes.DWORD(0)
        records = (win32.INPUT_RECORD * 16)()
        key_event_type = 0x0001
        while True:
            if win32.wait_for_handles([h_in], 200) is None:
                continue
            win32.KERNEL32.ReadConsoleInputW(
                h_in, ctypes.byref(records), 16, ctypes.byref(read_count)
            )
            for rec in records[: read_count.value]:
                if rec.EventType != key_event_type:
                    print(f"event type={rec.EventType}")
                    continue
                ke = rec.Event.KeyEvent
                if not ke.bKeyDown:
                    continue
                print(
                    f"vk=0x{ke.wVirtualKeyCode:02x} "
                    f"state=0x{ke.dwControlKeyState:04x} "
                    f"char={ke.uChar.UnicodeChar!r}"
                )
                if ke.wVirtualKeyCode == 0x51 and ke.dwControlKeyState & 0x000C:
                    return  # ctrl+q
    finally:
        sys.stdout.write("\x1b[?9001l")
        sys.stdout.flush()
        restore()


main()
