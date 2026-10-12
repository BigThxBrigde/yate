"""The bottom status bar: mode, file, position, hints (Rich Text).

Flat VS Code style: one solid accent-colored line with a mode chip on the
left and position/meta information right-aligned.  Extensions contribute
extra text segments (``api.ui.add_status_segment``): the bar pulls them
from the injected :class:`~yate.services.extension_bridges.UiExtensionBridge`
on every refresh and paints them with its own segment styles.

The bar is self-contained: it reads the document session, the language
servers, the keymap set and the prompt bar (whose active mode owns the chip)
directly, so no host protocol is involved.
"""

from __future__ import annotations

from typing import Any

from rich.text import Text
from textual.widgets import Static

from yate.editor_core import Document
from yate.editor_core.buffer import TextBuffer
from yate.editor_lsp import ServerState
from yate.editor_lsp.manager import LspManager
from yate.keymaps.registry import KeymapSet
from yate.keymaps.vim import VimKeymap, VimMode
from yate.logs import tracing
from yate.paths import load_tcss
from yate.services.extension_bridges import UiExtensionBridge
from yate.services.extensions import ExtensionLoader
from yate.session import EditorSession

from yate.editor_view import theme
from yate.editor_view.commandline import PromptBar
from yate.editor_view.icons import DOT, KEYBOARD, LOCK, PENCIL, PLUG, TERMINAL

#: Trace logger ("yate.editor_view.statusbar"); silent unless yate_trace is on.
log = tracing.get_logger(__name__)


def mode_chip(prompt: PromptBar, keymaps: KeymapSet, buf: TextBuffer) -> tuple[str, str]:
    """``(label, background color)`` for the status bar mode chip.

    Priority: an active prompt wins first; a buffer with extra multi-cursor
    points shows ``V-COLUMN`` next (issue IKKJHH -- regardless of keymap or
    vim mode, color follows the visual family); the vim mode mapping and the
    ``VSC`` fallback come last.
    """
    t = theme.active()
    if prompt.active_mode:
        mode = prompt.active_mode
        if mode == "shell":
            return "SHELL", t.mode_insert_bg
        if mode in ("find", "find_back", "replace_find", "replace_with"):
            return "SEARCH", t.match_active_bg
        return "COMMAND", t.mode_command_bg
    if buf.has_extra_cursors():
        return "V-COLUMN", t.mode_visual_bg
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

    DEFAULT_CSS = load_tcss("status-bar.tcss")

    def __init__(
        self,
        session: EditorSession,
        lsp: LspManager,
        keymaps: KeymapSet,
        prompt: PromptBar,
        extension_loader: ExtensionLoader,
        ui: UiExtensionBridge | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__("", **kwargs)
        self.session = session
        self.lsp = lsp
        self.keymaps = keymaps
        self.prompt = prompt
        self.extension_loader = extension_loader
        #: Extension segment registry (``None`` = no contributed segments,
        #: keeps standalone constructions working).
        self.ui = ui

    #: unsubscribe hook from :func:`yate.editor_view.theme.subscribe`;
    #: ``None`` while not mounted.
    _theme_unsubscribe: theme.Unsubscribe | None = None

    def on_mount(self) -> None:
        """Initial render, then follow theme changes (self-painted)."""
        theme.attach(self, self.refresh_status)
        self.refresh_status()

    def on_unmount(self) -> None:
        """Detach from the theme broadcast."""
        theme.detach(self)

    def refresh_status(self) -> None:
        """Rebuild the one-line status text from the current editor state."""
        t = theme.active()
        doc = self.session.doc
        buf = doc.buffer
        width = self.size.width or 80
        # VS Code status bars use the theme accent as the bar background.
        self.styles.background = t.accent
        bar = f"on {t.accent}"

        mode, chip_bg = mode_chip(self.prompt, self.keymaps, buf)
        chip = f" {mode} "
        chip_len = theme.cell_len(chip)

        # Extension segments (pull model): left ones trail the existing left
        # content, right ones lead the existing right content.  They share
        # the surrounding segment styles (R13: the bar paints them itself;
        # extensions contribute text only).
        left_ext = "   ".join(self._extension_texts("left"))
        left_ext_len = theme.cell_len(left_ext) + (3 if left_ext else 0)
        right_ext = "".join(
            f"{part}   " for part in self._extension_texts("right")
        )

        pos_plain = f"Ln {buf.row + 1}, Col {buf.col + 1}"
        meta_plain = f"{buf.line_count} lines · {doc.filetype} · {doc.encoding}"
        lsp_plain, lsp_style = self._lsp_segment(doc)
        hints_plain = (
            f"{PLUG} {len(self.extension_loader.loaded)}  {TERMINAL} :!  "
            f"{KEYBOARD} F1"
        )
        lsp_part = f"{lsp_plain}   " if lsp_plain else ""
        right_plain = (
            f"{right_ext}{pos_plain}   {meta_plain}   {lsp_part}{hints_plain}"
        )
        right_len = theme.cell_len(right_plain)

        lock_cells = 2 if buf.read_only else 0
        dot_cells = 2 if doc.modified else 0
        # minimum: chip + gap + a 4-cell name + gap + extension + right block
        include_right = (
            chip_len + 1 + 4 + dot_cells + lock_cells + left_ext_len
            + 1 + right_len <= width
        )
        budget = width - (1 + right_len if include_right else 0)

        text = Text()
        # Flat mode chip (hard color edge, no powerline triangle).
        text.append(chip, style=f"bold {t.on_accent} on {chip_bg}")

        # gap, pencil+space, then the left extension segments' width
        name_budget = (
            budget - chip_len - 3 - dot_cells - lock_cells - left_ext_len
        )
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
        if buf.read_only:
            text.append(f" {LOCK}", style=f"bold {t.red} {bar}")
        if left_ext:
            text.append(f"   {left_ext}", style=f"bold {t.on_accent} {bar}")
        used = (
            chip_len + 1
            + (theme.cell_len(name) + 2 if name else 0)
            + dot_cells + lock_cells + left_ext_len
        )

        text.append(" " * max(0, width - used - (1 + right_len if include_right else 0)),
                    style=bar)
        if include_right:
            text.append(" ", style=bar)
            if right_ext:
                text.append(right_ext, style=f"{t.on_accent} {bar}")
            text.append(pos_plain, style=f"bold {t.on_accent} {bar}")
            text.append(f"   {meta_plain}   ", style=f"{t.on_accent} {bar}")
            if lsp_plain:
                text.append(lsp_plain, style=lsp_style)
                text.append("   ", style=bar)
            text.append(hints_plain, style=f"{t.panel} {bar}")
        self.update(text)

    def _extension_texts(self, align: str) -> list[str]:
        """Pull extension segment texts for bar half *align*.

        Pull model: every :meth:`refresh_status` pass calls each registered
        provider once.  A provider returning ``None`` or an empty string
        hides its segment for the pass; a raising provider degrades to a
        ``!`` placeholder (logged, never fatal) so one broken extension
        cannot take the rest of the bar down.
        """
        if self.ui is None:
            return []
        texts: list[str] = []
        for segment in self.ui.segments(align):
            try:
                value = segment.provider()
            except Exception:  # noqa: BLE001 - user code, never crash the bar
                log.exception("status segment %s provider failed", segment.id)
                texts.append("!")
                continue
            if value:
                texts.append(value)
        return texts

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
