"""The bottom status bar: mode, file, position, hints (Rich Text).

Flat VS Code style: one solid accent-colored line with a mode chip on the
left and position/meta information right-aligned.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from rich.text import Text
from textual.widgets import Static

from yate.editor_lsp import ServerState

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
        lsp_plain, lsp_style = self._lsp_segment()
        hints_plain = f"{PLUG} {len(app.extension_loader.loaded)}  {TERMINAL} :!  {KEYBOARD} F1"
        lsp_part = f"{lsp_plain}   " if lsp_plain else ""
        right_plain = f"{pos_plain}   {meta_plain}   {lsp_part}{hints_plain}"
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
            if lsp_plain:
                text.append(lsp_plain, style=lsp_style)
                text.append("   ", style=bar)
            text.append(hints_plain, style=f"{t.panel} {bar}")
        self.update(text)

    def _lsp_segment(self) -> tuple[str, str]:
        """Status-bar text for the active document's LSP server/diagnostics."""
        t = theme.active()
        app = self.yate
        bar = f"on {t.accent}"
        state = app.lsp.state_for_doc(app.doc)
        if state is None:
            return "", ""
        errors, warnings = app.lsp.counts_for(app.doc)
        if state is ServerState.READY:
            name = "LSP"
            cfg = app.lsp.config_for(app.doc.filetype)
            if cfg is not None:
                name = cfg.name
            label = name
            if errors:
                label += f" ✖ {errors}"
            if warnings:
                label += f" ▲ {warnings}"
            color = t.bg if (errors or warnings) else t.panel
            return label, f"bold {color} {bar}"
        if state is ServerState.STARTING:
            return "LSP…", f"{t.panel} {bar}"
        if state is ServerState.FAILED:
            return "LSP ✖", f"bold {t.bg} {bar}"
        return "", ""
