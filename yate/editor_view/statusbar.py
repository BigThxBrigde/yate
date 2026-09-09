"""The bottom status bar: mode, file, position, hints (Rich Text).

Flat VS Code style: one solid accent-colored line with a mode chip on the
left and position/meta information right-aligned.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from rich.text import Text
from textual.widgets import Static

from . import theme
from .icons import DOT, KEYBOARD, PENCIL, PLUG, TERMINAL

if TYPE_CHECKING:
    from yate.app import YateApp


class StatusBar(Static):
    """One line of context information, flat VS Code styled."""

    DEFAULT_CSS = """
    StatusBar {
        height: 1;
        padding: 0;
    }
    """

    def __init__(self, yate: YateApp, **kwargs: Any) -> None:
        super().__init__("", **kwargs)
        self.yate = yate

    def on_mount(self) -> None:
        self.refresh_status()

    def refresh_status(self) -> None:
        """Rebuild the one-line status text from the current app state."""
        t = theme.active()
        app = self.yate
        doc = app.doc
        buf = doc.buffer
        width = self.size.width or 80
        # VS Code status bars use the theme accent as the bar background.
        self.styles.background = t.accent
        bar = f"on {t.accent}"

        mode, chip_bg = app.mode_label()
        chip = f" {mode} "
        chip_len = theme.cell_len(chip)

        pos_plain = f"Ln {buf.row + 1}, Col {buf.col + 1}"
        meta_plain = f"{buf.line_count} lines · {doc.filetype} · {doc.encoding}"
        hints_plain = f"{PLUG} {len(app.extension_loader.loaded)}  {TERMINAL} :!  {KEYBOARD} F1"
        right_plain = f"{pos_plain}   {meta_plain}   {hints_plain}"
        right_len = theme.cell_len(right_plain)

        dot_cells = 2 if doc.modified else 0
        # minimum: chip + gap + a 4-cell name + gap + right block
        include_right = chip_len + 1 + 4 + dot_cells + 1 + right_len <= width
        budget = width - (1 + right_len if include_right else 0)

        text = Text()
        # Flat mode chip (hard color edge, no powerline triangle).
        text.append(chip, style=f"bold {t.on_accent} on {chip_bg}")

        name_budget = budget - chip_len - 3 - dot_cells  # gap, pencil+space
        name = doc.name
        if name_budget < 4:
            name = ""
        elif theme.cell_len(name) > name_budget:
            name = theme.truncate_to_cells(name, name_budget - 1) + "…"
        text.append(" ", style=bar)
        if name:
            text.append(f"{PENCIL} {name}", style=f"bold {t.on_accent} {bar}")
        if doc.modified:
            text.append(f" {DOT}", style=f"bold {t.yellow} {bar}")
        used = chip_len + 1 + (theme.cell_len(name) + 2 if name else 0) + dot_cells

        text.append(" " * max(0, width - used - (1 + right_len if include_right else 0)),
                    style=bar)
        if include_right:
            text.append(" ", style=bar)
            text.append(pos_plain, style=f"bold {t.on_accent} {bar}")
            text.append(f"   {meta_plain}   ", style=f"{t.on_accent} {bar}")
            text.append(hints_plain, style=f"{t.panel} {bar}")
        self.update(text)
