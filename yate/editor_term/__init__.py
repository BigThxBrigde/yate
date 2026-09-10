"""Integrated terminal subsystem (PTY backend, VT emulator, shell lookup).

The package is UI independent: :mod:`yate.editor_view.terminal` renders the
emulator state in Textual and feeds key bytes back in.
"""

from .emulator import Cell, TerminalEmulator, key_to_terminal
from .pty_proc import PtyProcess, PtyProcessError
from .shells import resolve_shell, shell_label

__all__ = [
    "Cell",
    "PtyProcess",
    "PtyProcessError",
    "TerminalEmulator",
    "key_to_terminal",
    "resolve_shell",
    "shell_label",
]
