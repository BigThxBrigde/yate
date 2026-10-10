"""Integrated terminal subsystem (PTY backend, VT emulator, shell lookup).

The package is UI independent: :mod:`yate.editor_view.terminal` renders the
emulator state in Textual and feeds key bytes back in.

The re-exports below are the documented public API exception
(architecture-boundaries rule 3.5): pure-leaf packages may re-export their
public surface; UI/service packages may not.
"""

from __future__ import annotations

from yate.editor_term.emulator import Cell, TerminalEmulator
from yate.editor_term.keys import key_to_terminal
from yate.editor_term.pty_proc import PtyProcess, PtyProcessError
from yate.editor_term.shells import resolve_shell, shell_label

__all__ = [
    "Cell",
    "PtyProcess",
    "PtyProcessError",
    "TerminalEmulator",
    "key_to_terminal",
    "resolve_shell",
    "shell_label",
]
