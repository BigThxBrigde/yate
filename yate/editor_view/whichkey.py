"""The which-key panel: a floating right-edge box with self-owned theme.

The widget paints whatever the L3 flow module pushes into it via
:meth:`WhichKeyPanel.show_entries` -- a pending chord header plus the
single-column list of next-key candidates -- and hides itself again on
:meth:`WhichKeyPanel.clear`.  It holds no keymap and computes no
candidates: data flow belongs to the flow module.

Visual contract:

- absolute positioned, anchored to the right edge of its parent
  (#editor-col) via :meth:`_place` (Textual 8.2.8 cannot reach the right
  edge with CSS alone -- ``apply_absolute`` resets to the container
  origin and ``align-*`` does not apply to absolute children);
- rounded border with a theme-tinted ``border_title`` carrying the
  current chord / keymap name; theme variables come from
  :mod:`yate.editor_view.themes`;
- single-column entries with a content-adaptive key column; pinned
  category rows render as ``\u25B8 <name>``.

Ownership notes:

- Theme (R13): the widget attaches to :mod:`yate.editor_view.theme` on
  mount and repaints itself on every broadcast; the bundled stylesheet
  only carries structure and theme-variable colours, key-label and
  description colours still come from ``theme.active()``.
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
from textual.widget import Widget
from textual.widgets import Static

from yate.paths import load_tcss

from yate.editor_view import theme


#: One row of the which-key grid: a display key label and its description.
@dataclass(frozen=True)
class ChordEntry:
    key: str  # display label, e.g. "dd" or "<ctrl-d>"
    desc: str  # short description
    category: str = ""  # group header in pinned-sheet mode


#: Maximum rendered rows before the overflow hint line kicks in.
MAX_ROWS: int = 12

#: Default horizontal gap between the panel's right edge and the parent's
#: right edge (one cell keeps the border off the parent's frame).
_RIGHT_MARGIN_CELLS: int = 1

#: Minimum vertical offset so the panel never overlaps the tabbar /
#: breadcrumbs strip at the top of the editor column (1 row tabbar + 1
#: row breadcrumbs).
_TOP_GUARD_CELLS: int = 2


class WhichKeyPanel(Static):
    """The which-key popup: pending chord header plus single-column grid.

    Pure renderer: :meth:`show_entries` receives precomputed entries
    from the L3 flow module and paints a single-column list; the chord
    header is rendered into :attr:`border_title` so the content area
    only carries the rows.  :meth:`clear` blanks the title and the
    content and hides the panel.  The widget never takes focus and
    never consumes key events (R10).
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
        """Join the theme broadcast, start hidden, and re-anchor."""
        theme.attach(self, self._repaint)
        self.display = False
        # First place run -- measure regions once the widget has one.
        self.call_after_refresh(self._place)

    def on_unmount(self) -> None:
        """Detach from the theme broadcast."""
        theme.detach(self)

    def on_resize(self) -> None:
        """Re-anchor when our size or the container size changes."""
        self._place()

    def show_entries(
        self, header: str, entries: Sequence[ChordEntry]
    ) -> None:
        """Render *entries* under *header* (border title) and reveal."""
        self._header = header
        self._entries = tuple(entries)
        self.border_title = header
        self._repaint()
        self.display = True
        # The container may have just resized to fit the new content.
        self.call_after_refresh(self._place)

    def clear(self) -> None:
        """Drop the pushed data, blank content + title and hide."""
        self._header = ""
        self._entries = ()
        self.border_title = ""
        self.update("")
        self.display = False

    def _place(self) -> None:
        """Anchor the panel to the right edge, vertically centered.

        Textual 8.2.8 places absolute children at the container origin
        and ignores parent ``align-*`` for them -- right anchoring
        therefore requires us to compute the offset from
        ``self.parent.region.size`` and write it back.  The top guard
        keeps the panel out of the tabbar / breadcrumbs strip.
        """
        parent = self.parent
        if not isinstance(parent, Widget) or self.display is False:
            return
        parent_size = parent.region.size
        if parent_size.width <= 0 or parent_size.height <= 0:
            return
        own_size = self.region.size
        if own_size.width <= 0 or own_size.height <= 0:
            return
        x = max(0, parent_size.width - own_size.width - _RIGHT_MARGIN_CELLS)
        y = max(
            _TOP_GUARD_CELLS,
            (parent_size.height - own_size.height) // 2,
        )
        # Idempotent write -- on_resize can fire repeatedly.
        self.styles.offset = (x, y)

    def _repaint(self) -> None:
        """Rebuild the panel text from the last pushed data (theme-aware).

        Entries are grouped by ``category`` in first-seen order; an empty
        category renders its rows without a group header.  At most
        :data:`MAX_ROWS` rows are drawn -- the rest collapse into one
        muted hint pointing at the full reference (F1).  The chord
        header is rendered as the ``border_title`` and is NOT drawn
        inside the content area.
        """
        t = theme.active()
        text = Text()
        groups: dict[str, list[ChordEntry]] = {}
        for entry in self._entries:
            groups.setdefault(entry.category, []).append(entry)

        shown = 0
        if self._entries:
            # Adaptive key-column width (longest key + 2 cell padding).
            max_key = max(len(entry.key) for entry in self._entries)
            key_width = max_key + 2
            for category, entries in groups.items():
                room = MAX_ROWS - shown
                if room <= 0:
                    break
                visible = entries[:room]
                if category and visible:
                    text.append(f"\u25B8 {category}", style=f"bold {t.accent2}")
                    text.append("\n")
                for entry in visible:
                    text.append(entry.key.ljust(key_width), style=t.green)
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
