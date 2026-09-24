"""The bottom status bar: mode, file, position, hints (Rich Text).

Flat VS Code style: one solid accent-colored line with a mode chip on the
left and position/meta information right-aligned.

The bar is self-contained: it reads the document session, the language
servers, the keymap set and the prompt bar (whose active mode owns the chip)
directly, so no host protocol is involved.
"""

from __future__ import annotations

from typing import Any

from rich.text import Text
from textual.widgets import Static

from yate.editor_core import Document
from yate.editor_lsp import LspManager, ServerState
from yate.keymaps.registry import KeymapSet
from yate.keymaps.vim import VimKeymap, VimMode
from yate.services.extensions import ExtensionLoader
from yate.session import EditorSession

from . import theme
from .commandline import PromptBar
from .icons import DOT, KEYBOARD, PENCIL, PLUG, TERMINAL


def mode_chip(prompt: PromptBar, keymaps: KeymapSet) -> tuple[str, str]:
    """``(label, background color)`` for the status bar mode chip."""
    t = theme.active()
    if prompt.active_mode:
        mode = prompt.active_mode
        if mode == "shell":
            return "SHELL", t.mode_insert_bg
        if mode in ("find", "find_back", "replace_find", "replace_with"):
            return "SEARCH", t.match_active_bg
        return "COMMAND", t.mode_command_bg
    if keymaps.name == "vim":
        vim = keymaps.get("vim")
        if isinstance(vim, VimKeymap):
            mapping = {
                VimMode.NORMAL: ("NORMAL", t.mode_normal_bg),
                VimMode.INSERT: ("INSERT", t.mode_insert_bg),
                VimMode.VISUAL: ("VISUAL", t.mode_visual_bg),
                VimMode.VISUAL_LINE: ("V-LINE", t.mode_visual_bg),
            }
            return mapping.get(vim.mode, ("NORMAL", t.mode_normal_bg))
    return "VSC", t.mode_normal_bg


class StatusBar(Static):
    """One line of context information, flat VS Code styled."""

    DEFAULT_CSS = """
    StatusBar {
        height: 1;
        padding: 0;
    }
    """

    def __init__(
        self,
        session: EditorSession,
        lsp: LspManager,
        keymaps: KeymapSet,
        prompt: PromptBar,
        extension_loader: ExtensionLoader,
        **kwargs: Any,
    ) -> None:
        super().__init__("", **kwargs)
        self.session = session
        self.lsp = lsp
        self.keymaps = keymaps
        self.prompt = prompt
        self.extension_loader = extension_loader

    def on_mount(self) -> None:
        self.refresh_status()

    def refresh_status(self) -> None:
        """Rebuild the one-line status text from the current editor state."""
        t = theme.active()
        doc = self.session.doc
        buf = doc.buffer
        width = self.size.width or 80
        # VS Code status bars use the theme accent as the bar background.
        self.styles.background = t.accent
        bar = f"on {t.accent}"

        mode, chip_bg = mode_chip(self.prompt, self.keymaps)
        chip = f" {mode} "
        chip_len = theme.cell_len(chip)

        pos_plain = f"Ln {buf.row + 1}, Col {buf.col + 1}"
        meta_plain = f"{buf.line_count} lines · {doc.filetype} · {doc.encoding}"
        lsp_plain, lsp_style = self._lsp_segment(doc)
        hints_plain = (
            f"{PLUG} {len(self.extension_loader.loaded)}  {TERMINAL} :!  "
            f"{KEYBOARD} F1"
        )
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

    def _lsp_segment(self, doc: Document) -> tuple[str, str]:
        """Status-bar text for the active document's LSP server/diagnostics."""
        t = theme.active()
        bar = f"on {t.accent}"
        state = self.lsp.state_for_doc(doc)
        if state is None:
            return "", ""
        errors, warnings = self.lsp.counts_for(doc)
        if state is ServerState.READY:
            name = "LSP"
            cfg = self.lsp.config_for(doc.filetype)
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
