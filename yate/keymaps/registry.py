"""The keymaps of a session and the active one.

``KeymapSet`` is a small concrete model (no UI, no Textual): it maps keymap
names to :class:`~yate.keymaps.base.Keymap` instances and remembers which one
dispatches keys.  Widgets, actions, commands, extensions and the status bar
all share this object instead of passing a bare ``dict`` plus a name string.
"""

from __future__ import annotations

from typing import Iterator, Optional

from yate.keymaps.base import Keymap


class KeymapSet:
    """Every loaded keymap plus the name of the active one."""

    def __init__(self, keymaps: dict[str, Keymap], name: str) -> None:
        self._keymaps = dict(keymaps)
        if name in self._keymaps:
            self._name = name
        elif self._keymaps:
            self._name = next(iter(self._keymaps))
        else:
            raise ValueError("no keymaps registered")

    # ------------------------------------------------------------- lookups

    def get(self, name: str) -> Optional[Keymap]:
        return self._keymaps.get(name)

    def __getitem__(self, name: str) -> Keymap:
        return self._keymaps[name]

    def __iter__(self) -> Iterator[str]:
        return iter(self._keymaps)

    def names(self) -> list[str]:
        """Every registered keymap name (sorted)."""
        return sorted(self._keymaps)

    # -------------------------------------------------------------- active

    @property
    def name(self) -> str:
        """Name of the keymap currently dispatching keys."""
        return self._name

    @property
    def active(self) -> Keymap:
        """The keymap currently dispatching keys."""
        return self._keymaps[self._name]

    def select(self, name: str) -> bool:
        """Activate *name*; ``False`` when it is not a known keymap."""
        if name not in self._keymaps:
            return False
        self._name = name
        return True

    def toggle(self) -> str:
        """Activate the other registered keymap; returns the new name."""
        others = [n for n in self.names() if n != self._name]
        if others:
            self._name = others[0]
        return self._name
