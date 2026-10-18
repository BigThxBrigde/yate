"""The which-key popup panel: a pure renderer with self-owned theme.

The panel paints whatever the L3 flow module pushes into it via
:meth:`WhichKeyPanel.show_entries` -- a pending chord header plus the grid
of next-key candidates -- and hides itself again on
:meth:`WhichKeyPanel.clear`.  It holds no keymap and computes no
candidates: data flow belongs to the flow module (plan-d), wiring to the
Editor (plan-e).

Ownership notes:

- Theme (R13): the widget attaches to :mod:`yate.editor_view.theme` on
  mount and repaints itself on every broadcast; the bundled stylesheet
  only carries structure, every text color comes from ``theme.active()``.
- Keys (R10): the panel never takes focus and never stops a key event,
  so presses keep flowing to the focused widget underneath.
- Layout id (R9): the ``#which-key`` widget id is assigned by the
  ``Editor`` at compose time, not by this module.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from rich.text import Text
from textual.widgets import Static

from yate.paths import load_tcss

from yate.editor_view import theme


#: One row of the which-key grid: a display key label and its description.
@dataclass(frozen=True)
class ChordEntry:
    key: str  # display label, e.g. "dd" or "<ctrl-d>"
    desc: str  # short description
    category: str = ""  # group header in pinned-sheet mode


#: Maximum rendered grid rows before the overflow hint line kicks in.
MAX_ROWS: int = 12

#: Cell width of the key column; descriptions start right after it.
GRID_KEY_WIDTH: int = 12


class WhichKeyPanel(Static):
    """The which-key popup: pending chord header plus next-key grid.

    Pure renderer: :meth:`show_entries` receives precomputed entries from
    the L3 flow module and paints a compact grid; :meth:`clear` hides it.
    The widget never takes focus and never consumes key events (R10).
    """

    DEFAULT_CSS = load_tcss("which-key.tcss")

    #: Unsubscribe hook from :func:`yate.editor_view.theme.attach`;
    #: ``None`` while not mounted.
    _theme_unsubscribe: theme.Unsubscribe | None = None

    def __init__(self, **kwargs: Any) -> None:
        super().__init__("", **kwargs)
        # Last pushed data, retained so a theme broadcast can repaint it.
        self._header: str = ""
        self._entries: Sequence[ChordEntry] = ()

    def on_mount(self) -> None:
        """Join the theme broadcast and start hidden (R13 self-painting)."""
        theme.attach(self, self._repaint)
        self.display = False

    def on_unmount(self) -> None:
        """Detach from the theme broadcast."""
        theme.detach(self)

    def show_entries(self, header: str, entries: Sequence[ChordEntry]) -> None:
        """Render *entries* below *header* and reveal the panel."""
        self._header = header
        self._entries = tuple(entries)
        self._repaint()
        self.display = True

    def clear(self) -> None:
        """Drop the pushed data, blank the content and hide the panel."""
        self._header = ""
        self._entries = ()
        self.update("")
        self.display = False

    def _repaint(self) -> None:
        """Rebuild the panel text from the last pushed data (theme-aware).

        Entries are grouped by :attr:`ChordEntry.category` in first-seen
        order; an empty category renders its rows without a group header.
        At most :data:`MAX_ROWS` rows are drawn -- the rest collapse into
        one muted hint pointing at the full reference (F1).
        """
        t = theme.active()
        text = Text()
        if self._header:
            text.append(self._header, style=f"bold {t.accent2}")
            text.append("\n")

        groups: dict[str, list[ChordEntry]] = {}
        for entry in self._entries:
            groups.setdefault(entry.category, []).append(entry)

        shown = 0
        for category, entries in groups.items():
            room = MAX_ROWS - shown
            if room <= 0:
                break
            visible = entries[:room]
            if category and visible:
                text.append(category, style=f"bold {t.accent2}")
                text.append("\n")
            for entry in visible:
                text.append(entry.key.ljust(GRID_KEY_WIDTH), style=t.green)
                text.append(entry.desc, style=t.fg_bright)
                text.append("\n")
            shown += len(visible)

        overflow = len(self._entries) - shown
        if overflow > 0:
            text.append(
                f"\N{HORIZONTAL ELLIPSIS} {overflow} more "
                "\N{EM DASH} F1 for the full map",
                style=t.fg_muted,
            )
            text.append("\n")
        self.update(text)
