"""The static chrome around the editor: the tab line and the breadcrumbs.

Both are self-contained widgets: they read the shared
:class:`~yate.session.EditorSession` (plus the workspace for the path crumbs)
and render themselves, so the application never builds their Rich text.
The tab bar reports clicks through the ``on_activate`` callback the editor
wires in; nothing here knows about the application class.
"""

from __future__ import annotations

from typing import Any, Callable

from rich.text import Text
from textual.events import MouseDown, Resize
from textual.widgets import Static

from yate.editor_core import Document
from yate.services.workspace import Workspace
from yate.session import EditorSession

from . import theme
from .icons import CHEVRON_RIGHT, FOLDER, icon_for_path


class TabBar(Static):
    """Flat VS Code-style tab line that supports click-to-switch.

    The bar is rendered as a single Rich Text line (kept for the VS Code look),
    but each rendered tab also records its cell span so a mouse click can be
    mapped back to a document index.
    """

    def __init__(
        self,
        session: EditorSession,
        on_activate: Callable[[Document], None],
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.session = session
        self.on_activate = on_activate
        # [(start_cell, end_cell_exclusive, doc_index), ...] for the last
        # rendered line; used by on_mouse_down for hit testing.
        self._regions: list[tuple[int, int, int]] = []

    # --------------------------------------------------------------- data

    def build(self, width: int) -> tuple[Text, list[tuple[int, int, int]]]:
        """Build the flat tab line and its hit-test regions.

        Inactive tabs sit on the panel background; the active tab uses the
        editor background so it visually merges with the editor below.

        Returns the rendered text and a list of ``(start, end, doc_index)``
        cell spans (end exclusive) so :meth:`on_mouse_down` can map mouse
        clicks back to documents.
        """
        session = self.session
        t = theme.active()
        text = Text()
        regions: list[tuple[int, int, int]] = []
        used = 0
        for i, doc in enumerate(session.docs):
            name = theme.truncate_to_cells(doc.name, 24)
            active = i == session.index
            # " <icon> <name>" + optional " ●" + trailing space
            seg_cells = 1 + 1 + 1 + theme.cell_len(name) + (2 if doc.modified else 0) + 1
            if used + seg_cells > width:
                break
            bg = t.bg if active else t.panel
            name_style = f"bold {t.fg_bright}" if active else t.fg_dim
            icon = icon_for_path(doc.name, False)
            text.append(" ", style=f"on {bg}")
            text.append(icon, style=f"{t.accent if active else t.fg_dim} on {bg}")
            text.append(f" {name}", style=f"{name_style} on {bg}")
            if doc.modified:
                text.append(" ●", style=f"bold {t.orange} on {bg}")
            text.append(" ", style=f"on {bg}")
            regions.append((used, used + seg_cells, i))
            used += seg_cells
        if used < width:
            text.append(" " * (width - used), style=f"on {t.panel}")
        return text, regions

    def render_content(self, width: int) -> None:
        """Rebuild the tab text and its hit-test regions."""
        text, regions = self.build(width)
        self._regions = regions
        self.styles.background = theme.active().panel
        self.update(text)

    def refresh_tabs(self) -> None:
        """Re-render at the widget's current width."""
        self.render_content(self.size.width or 80)

    # ------------------------------------------------------------- events

    def on_resize(self, _event: Resize) -> None:
        self.refresh_tabs()

    def on_mouse_down(self, event: MouseDown) -> None:
        """Switch to the tab under the cursor, if any."""
        x = event.x
        for start, end, doc_idx in self._regions:
            if start <= x < end:
                if doc_idx != self.session.index:
                    self.on_activate(self.session.docs[doc_idx])
                event.stop()
                return


class Breadcrumbs(Static):
    """VS Code-style breadcrumb line above the editor (the active file path)."""

    def __init__(self, session: EditorSession, workspace: Workspace, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.session = session
        self.workspace = workspace

    # --------------------------------------------------------------- data

    def crumb_parts(self) -> list[tuple[str, str, bool]]:
        """(icon, label, is_file) crumbs for the active document's path."""
        doc = self.session.doc
        if doc.path is None:
            # Untitled buffer: the tab already shows the name -- a second
            # copy here would look like a permanent two-row tab bar.
            return []
        path = doc.path
        root = self.workspace.root
        parts: list[str]
        if root is not None:
            try:
                parts = [root.name, *path.resolve().relative_to(root.resolve()).parts]
            except ValueError:
                parts = list(path.parts)
        else:
            parts = list(path.parts)
        crumbs: list[tuple[str, str, bool]] = []
        for i, part in enumerate(parts):
            is_file = i == len(parts) - 1
            icon = icon_for_path(part, False) if is_file else FOLDER
            crumbs.append((icon, part, is_file))
        return crumbs

    def build(self, width: int) -> Text:
        """Build the breadcrumb line (path crumbs above the editor)."""
        t = theme.active()
        crumbs = self.crumb_parts()

        def crumb_text(crumb: tuple[str, str, bool], style: str) -> Text:
            icon, label, is_file = crumb
            piece = Text()
            piece.append(icon + " ", style=style)
            piece.append(label, style=style if not is_file else f"bold {t.fg_bright}")
            return piece

        # Render from the last crumb backwards until the width budget runs out,
        # keeping the file name always visible (left truncation, like VS Code).
        chosen: list[tuple[str, str, bool]] = []
        used = 1  # leading space
        for crumb in reversed(crumbs):
            label = crumb[1]
            extra = 1 + 1 + theme.cell_len(label)  # icon + space + label
            if chosen:
                extra += 3  # " <chevron> " separator
            if used + extra > width and chosen:
                break
            chosen.insert(0, crumb)
            used += extra

        text = Text()
        text.append(" ", style=f"on {t.bg}")
        if len(chosen) < len(crumbs):
            text.append("… ", style=f"{t.fg_dim} on {t.bg}")
        for i, crumb in enumerate(chosen):
            if i > 0:
                text.append(f" {CHEVRON_RIGHT} ", style=f"{t.fg_dim} on {t.bg}")
            text.append(crumb_text(crumb, t.fg_dim))
        used_cells = theme.cell_len(text.plain)
        if used_cells < width:
            text.append(" " * (width - used_cells), style=f"on {t.bg}")
        return text

    def refresh_crumbs(self) -> None:
        """Re-render at the widget's current width."""
        self.styles.background = theme.active().bg
        self.update(self.build(self.size.width or 80))

    def on_resize(self, _event: Resize) -> None:
        self.refresh_crumbs()


#: The sidebar title ("EXPLORER"), kept with the rest of the static chrome.
SIDEBAR_TITLE = " EXPLORER"


def sidebar_head_text() -> Text:
    """Rich text for the sidebar header line."""
    t = theme.active()
    return Text(SIDEBAR_TITLE, style=f"bold {t.fg_dim}")
