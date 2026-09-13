"""The yate application: a Textual App wiring editor_core, keymaps, services.

The UI is built with Textual (Rich rendering).  All editor logic lives in
``editor_core`` / ``keymaps`` / ``services`` and is UI independent; this class
only composes widgets, routes keys to the active keymap and implements the
callbacks that actions / extensions invoke.
"""

from __future__ import annotations

import asyncio
import os
import re
from pathlib import Path
from typing import Any, Callable, Optional

from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.events import Key
from textual.screen import Screen
from textual.widgets import Input, Static

from yate import __version__
from yate.actions import ActionRegistry, populate
from yate.app_features import explorer, terminal
from yate.app_features.commands import CommandRegistry, register_commands
from yate.app_features.completion import CompletionController
from yate.config import YateConfig
from yate.editor_core import Document, SearchEngine
from yate.editor_core.buffer import TextBuffer
from yate.editor_lsp import LspManager
from yate.editor_syntax import available_filetypes, language_name, resolve_filetype
from yate.editor_view import theme
from yate.editor_view.commandline import PromptBar
from yate.editor_view.completion import CompletionPopup
from yate.editor_view.editor import EditorView
from yate.editor_view.explorer import ExplorerTree
from yate.editor_view.icons import CHEVRON_RIGHT, FOLDER, icon_for_path
from yate.editor_view.keys import event_to_raw, textual_key_to_raw
from yate.editor_view.manual import ManualScreen
from yate.editor_view.modals import HelpScreen, OutputScreen
from yate.editor_view.palette import PaletteScreen
from yate.editor_view.panes import Axis, Leaf, PaneHost, PaneManager
from yate.editor_view.statusbar import StatusBar
from yate.editor_view.terminal import TOGGLE_KEYS, TerminalPanel
from yate.keymaps.base import ActionContext, Keymap
from yate.keymaps.vsc import VscKeymap
from yate.keymaps.vim import VimKeymap, VimMode
from yate.paths import bundled_extensions_dir
from yate.services import fonts
from yate.services.extensions import ExtensionAPI, ExtensionLoader, LoadedExtension
from yate.services.shell import ShellResult, run_shell, shell_name
from yate.services.workspace import Workspace


# `textual_key_to_raw` lives in yate.editor_view.keys to avoid import cycles
# and is re-exported here for convenience/tests.
__all__ = ["textual_key_to_raw", "CommandRegistry", "YateApp"]


# --------------------------------------------------------------- commands
# CommandRegistry lives in yate.app_features.commands and is re-exported here
# (it is part of this module's public surface for extensions and tests).


class YateApp(App[None]):
    """The yate Textual application and application state."""

    # ctrl+p is yate's own command prompt -- disable Textual's palette.
    ENABLE_COMMAND_PALETTE = False

    CSS = """
    #bottom-dock {
        dock: bottom;
        height: auto;
    }
    #bottom {
        height: 2;
    }
    #terminal-dock {
        height: 12;
        display: none;
    }
    #body {
        height: 1fr;
    }
    #sidebar {
        width: 34;
        min-width: 16;
        height: 1fr;
    }
    #sidebar-head {
        height: 1;
        padding: 0;
    }
    #explorer {
        height: 1fr;
    }
    #editor-col {
        width: 1fr;
        height: 1fr;
        layers: default lsp-popup;
    }
    #tabbar {
        height: 1;
        padding: 0;
    }
    #breadcrumbs {
        height: 1;
        padding: 0;
    }
    """

    def __init__(
        self,
        target: Optional[str | Path] = None,
        *,
        keymap: Optional[str] = None,
        theme_name: Optional[str] = None,
        config: Optional[YateConfig] = None,
        ext_files: Optional[list[str | Path]] = None,
        ext_dirs: Optional[list[str | Path]] = None,
    ) -> None:
        super().__init__()
        self.title = f"yate {__version__}"

        self.config = config if config is not None else YateConfig()
        # The color theme is process-global state (like vim's colorscheme).
        # An explicit selection (--theme) wins over the yaterc option.
        wanted_theme = theme_name if theme_name is not None else self.config.theme
        try:
            theme.set_theme(wanted_theme)
        except KeyError:
            self.config.errors.append(f"unknown theme: {wanted_theme!r}")

        self.actions = ActionRegistry()
        populate(self.actions)

        self.workspace = Workspace()
        self.docs: list[Document] = []
        self.doc_index = -1

        self.keymaps: dict[str, Keymap] = {"vsc": VscKeymap(), "vim": VimKeymap()}
        wanted = keymap if keymap is not None else self.config.keymap
        self.keymap_name = wanted if wanted in self.keymaps else "vsc"

        self.search = SearchEngine()
        self.commands = CommandRegistry()
        register_commands(self)

        self.focus_target = "editor"
        self.explorer_visible = True
        # propagate the yaterc show_hidden default to the workspace
        self.workspace.show_hidden = self.config.show_hidden

        self._ext_files = [Path(p) for p in (ext_files or [])]
        self._ext_dirs = [Path(p) for p in (ext_dirs or [])]
        self.extension_api = ExtensionAPI(self)
        self.extension_loader = ExtensionLoader(self.extension_api)
        self._ext_messages: list[str] = []
        self._ext_messages.extend(f"yaterc: {err}" for err in self.config.errors)

        # Language Server Protocol: registered servers come from extensions
        # and the yaterc ``language_servers`` option; the manager is UI
        # independent and safe to keep even with no server.
        self.lsp = LspManager(
            workspace_root=lambda: self.workspace.root,
            on_event=self._on_lsp_event,
        )
        self._message_owner = "idle"
        self.completion_ctl = CompletionController(self)

        self._replace_pending = ""
        self._prev_manual_theme: Optional[str] = None
        self._window_pending = False
        self._explorer_target: Optional[Path] = None
        self._explorer_is_dir = False
        # The welcome page is a one-time overlay for the pristine startup
        # buffer. Creating a user-requested buffer (:enew) dismisses it for
        # the rest of the session; the :welcome command turns it back on.
        self.welcome_visible = True

        # widgets (set in on_mount)
        self.sidebar: Optional[Vertical] = None
        self.sidebar_head: Optional[Static] = None
        self.tabbar: Optional[Static] = None
        self.breadcrumbs: Optional[Static] = None
        self.explorer_tree: Optional[ExplorerTree] = None
        # The active editor view is derived from the pane tree
        # (self.panes.active_view); a pane host widget is created in compose.
        self.panes: Optional[PaneManager] = None
        self.status_bar: Optional[StatusBar] = None
        self.prompt_bar: Optional[PromptBar] = None
        self.completion_popup: Optional[CompletionPopup] = None
        self.terminal_panel: Optional[TerminalPanel] = None
        self._terminal_visible = False
        self._terminal_starting = False
        # Tests inject a fake PTY factory here: (argv, cwd, cols, rows) -> proc
        self._terminal_factory: Optional[Callable[..., object]] = None

        # ------------------------------------------------------------- open
        if target is not None:
            kind = self._open_target(Path(target))
            # A directory argument opens in browse mode (explorer visible);
            # a file argument opens in edit mode (explorer hidden; Ctrl+B /
            # :explorer reveals it later). With no argument the workspace
            # root is None and the explorer stays hidden regardless.
            self.explorer_visible = kind == "dir"
        if not self.docs:
            self.new_buffer(show=False)

        # The pane tree owns editor windows; it starts with one leaf on the
        # startup document and grows with :split / :vsplit.
        self.panes = PaneManager(self, self.doc)

    # ================================================================== docs

    @property
    def doc(self) -> Document:
        return self.docs[self.doc_index]

    @property
    def buffer(self) -> TextBuffer:
        return self.doc.buffer

    @property
    def editor_view(self) -> Optional[EditorView]:
        """The widget of the currently active pane (``None`` before mount)."""
        if self.panes is None:
            return None
        return self.panes.active_view

    def _make_buffer(self, text: str = "") -> TextBuffer:
        """Create a buffer honoring the yaterc indentation options."""
        return TextBuffer(
            text,
            tab_width=self.config.tab_width,
            use_spaces=self.config.use_spaces,
        )

    def _apply_buffer_options(self, buf: TextBuffer) -> None:
        """Propagate the yaterc indentation options onto an existing buffer."""
        buf.tab_width = self.config.tab_width
        buf.use_spaces = self.config.use_spaces

    @property
    def active_keymap(self) -> Keymap:
        """The keymap currently used for key dispatch."""
        return self.keymaps[self.keymap_name]

    @property
    def mounted(self) -> bool:
        """True once widgets exist and the editor is on screen.

        (Textual's ``App.is_mounted`` is a method, not a boolean, so we derive
        the state from the pane host / active editor widget.)
        """
        if self.panes is None:
            return False
        host = self.panes.host
        view = self.panes.active_view
        return (
            host is not None
            and host.is_mounted
            and view is not None
            and view.is_mounted
        )

    def _open_target(self, path: Path) -> str:
        """Open the startup target and return its kind: ``"dir"`` or
        ``"file"`` (a not-yet-created path counts as a file)."""
        if not path.exists():
            # treat as a not-yet-created file
            self.workspace.set_root(path.parent if str(path.parent) else Path.cwd())
            self._open_document_path(path)
            return "file"
        kind = self.workspace.open_target(path)
        if kind == "file":
            self._open_document_path(path)
        return kind

    def _activate_doc(
        self, doc: Document, target_leaf: Optional[Leaf] = None
    ) -> None:
        """Show *doc* in a pane leaf (default: the active one) and keep
        ``doc_index`` in sync. Before the pane tree exists (startup) this
        only sets the global index."""
        if self.panes is None:
            self.doc_index = self.docs.index(doc)
            return
        leaf = target_leaf if target_leaf is not None else self.panes.active
        self.panes.show_doc(leaf, doc)

    def _open_document_path(
        self, path: Path, *, target_leaf: Optional[Leaf] = None
    ) -> Optional[Document]:
        """Open/reuse a document and bind it to *target_leaf*.

        Returns the document, or ``None`` when the path is a binary file
        (an error message is recorded).
        """
        resolved = path.resolve()
        for doc in self.docs:
            if doc.path is not None and doc.path.resolve() == resolved:
                self._activate_doc(doc, target_leaf)
                return doc
        if path.exists() and not Workspace.is_text_file(path):
            self._ext_messages.append(f"not a text file: {path.name}")
            return None
        if path.exists():
            doc = Document.open(path)
        else:
            doc = Document(path, self._make_buffer())
        self._apply_buffer_options(doc.buffer)
        self.docs.append(doc)
        self._activate_doc(doc, target_leaf)
        return doc

    async def _open_document_path_async(
        self, path: Path, *, target_leaf: Optional[Leaf] = None
    ) -> Optional[Document]:
        """Like :meth:`_open_document_path`, but disk reads run off the loop."""
        resolved = path.resolve()
        for doc in self.docs:
            if doc.path is not None and doc.path.resolve() == resolved:
                self._activate_doc(doc, target_leaf)
                return doc

        def _inspect() -> tuple[bool, bool]:
            return path.exists(), Workspace.is_text_file(path)

        exists, is_text = await asyncio.to_thread(_inspect)
        if exists and not is_text:
            self._ext_messages.append(f"not a text file: {path.name}")
            return None
        if exists:
            doc = await Document.open_async(path)
        else:
            doc = Document(path, self._make_buffer())
        self._apply_buffer_options(doc.buffer)
        self.docs.append(doc)
        self._activate_doc(doc, target_leaf)
        return doc

    def open_path(self, path: Path) -> None:
        try:
            if path.is_dir():
                self.workspace.set_root(path)
                if self.explorer_tree is not None:
                    self.explorer_tree.refresh_tree()
                self.explorer_visible = True
                self._sync_explorer_visibility()
                # focus the tree so keyboard nav works immediately
                self.focus_target = "explorer"
                if self.explorer_tree is not None:
                    self.explorer_tree.focus()
                self.message(f"opened folder {path}")
                return
        except OSError:
            pass
        self._open_document_path(path)
        if self.explorer_tree is not None:
            self.explorer_tree.refresh_tree()
        self.search = SearchEngine()
        self.close_completion()
        self.message(f"opened {self.doc.name}")
        self.ui_refresh()

    async def open_path_async(self, path: Path) -> None:
        """Open a file without blocking the UI (directory opens stay sync:
        the tree only lists the bounded root level)."""
        try:
            is_dir = path.is_dir()
        except OSError:
            is_dir = False
        if is_dir:
            self.open_path(path)
            return
        await self._open_document_path_async(path)
        if not self.mounted:
            return
        if self.explorer_tree is not None:
            self.explorer_tree.refresh_tree()
        self.search = SearchEngine()
        self.close_completion()
        self.message(f"opened {self.doc.name}")
        self.ui_refresh()

    def open_path_later(self, path: Path) -> None:
        """Schedule a non-blocking file open from a synchronous handler
        (palette, explorer, ``:e`` command)."""
        self.run_worker(
            self.open_path_async(path), group="open",
            exclusive=True, exit_on_error=False,
        )

    def new_buffer(self, show: bool = True) -> None:
        doc = Document(None, self._make_buffer())
        self.docs.append(doc)
        self._activate_doc(doc)
        self.search = SearchEngine()
        self.close_completion()
        if show:
            # A user-requested buffer (:enew / new tab) dismisses the
            # one-time welcome page for the rest of the session. Internal
            # replacements (startup seed, close-last-tab fallback) pass
            # show=False and leave the flag untouched.
            self.welcome_visible = False
            self.message("new buffer")
        self.ui_refresh()

    def show_welcome(self) -> None:
        """Re-enable the welcome page (``:welcome``).

        It renders on the current buffer when that buffer is an empty,
        unnamed, unmodified scratch buffer; otherwise the flag simply stays
        on until such a buffer is shown.
        """
        self.welcome_visible = True
        self.ui_refresh()
        self.message("welcome page enabled")

    def close_tab(self) -> None:
        if not self.docs:
            return
        closed = self.docs[self.doc_index]
        if closed.path is not None:
            self.run_worker(
                self.lsp.on_document_closed(closed),
                group="lsp-sync", exclusive=False, exit_on_error=False,
            )
        self.docs.pop(self.doc_index)
        if not self.docs:
            # Internal fallback scratch buffer (show=False keeps the welcome
            # flag untouched).
            fallback = Document(None, self._make_buffer())
            self.docs.append(fallback)
        else:
            fallback = self.docs[min(self.doc_index, len(self.docs) - 1)]
        # Every pane showing the closed document rebinds to the fallback;
        # other panes keep their documents and independent view states.
        if self.panes is not None:
            self.panes.document_closed(closed, fallback)
        else:
            self.doc_index = self.docs.index(fallback)
        self.search = SearchEngine()
        self.close_completion()
        self.message("closed tab")
        self.ui_refresh()

    def cycle_tab(self, delta: int) -> None:
        if len(self.docs) < 2:
            self.message("only one tab open", kind="warn")
            return
        index = (self.doc_index + delta) % len(self.docs)
        self._activate_doc(self.docs[index])
        self.search = SearchEngine()
        self.close_completion()
        self.ui_refresh()

    def save_document(self) -> None:
        doc = self.doc
        if doc.path is None:
            self.prompt_save_as()
            return
        try:
            doc.save()
            if self.explorer_tree is not None:
                self.explorer_tree.refresh_tree()
            self.run_worker(
                self.lsp.notify_saved(doc),
                group="lsp-sync", exclusive=False, exit_on_error=False,
            )
            self.message(f"saved {doc.path}", kind="ok")
        except OSError as exc:
            self.message(f"save failed: {exc}", kind="error")
        self.ui_refresh()

    def prompt_save_as(self) -> None:
        if self.prompt_bar is None:
            return
        current = str(self.doc.path) if self.doc.path else ""
        self.prompt_bar.activate("save", initial=current)

    def _do_save_as(self, text: str) -> None:
        text = text.strip()
        if not text:
            self.message("save cancelled")
            return
        path = Path(text)
        try:
            self.doc.save(path)
            self.workspace.set_root(path.parent)
            if self.explorer_tree is not None:
                self.explorer_tree.refresh_tree()
            self.message(f"saved {path}", kind="ok")
        except OSError as exc:
            self.message(f"save failed: {exc}", kind="error")

    # ================================================================ keymap

    def select_keymap(self, name: str) -> None:
        """Switch the active key map by name (``vsc`` / ``vim``).

        Named ``select_keymap`` rather than ``set_keymap`` to avoid shadowing
        Textual's own :meth:`~textual.app.App.set_keymap`.
        """
        if name not in self.keymaps:
            self.message(f"unknown keymap: {name} (vsc|vim)", kind="error")
            return
        self.keymap_name = name
        self.message(f"keymap: {self.active_keymap.label}", kind="ok")
        self.ui_refresh()

    def toggle_keymap(self) -> None:
        """Flip between the vsc and vim key maps."""
        self.select_keymap("vim" if self.keymap_name == "vsc" else "vsc")

    # ---------------------------------------------------------------- theme

    def set_theme(self, name: str) -> None:
        """Switch the active color theme (``mocha``, ``latte``, ...)."""
        name = name.strip().lower()
        try:
            selected = theme.set_theme(name)
        except KeyError:
            self.message(
                f"unknown theme: {name!r} ({', '.join(theme.available())})",
                kind="error",
            )
            return
        self.apply_theme()
        self.message(f"theme: {selected.label}", kind="ok")

    def apply_theme(self) -> None:
        """Push the active theme onto every widget and force a repaint."""
        if not self.mounted:
            return
        t = theme.active()
        self.screen.styles.background = t.bg
        if self.panes is not None:
            for view in self.panes.all_views():
                view.styles.background = t.bg
                view.content_changed()
        if self.explorer_tree is not None:
            self.explorer_tree.refresh_tree()
        if self.status_bar is not None:
            self.status_bar.refresh_status()
        if self.prompt_bar is not None:
            self.prompt_bar.styles.background = t.panel
            self.prompt_bar.refresh()
        self._update_sidebar_head()
        self.update_tabbar()
        self.update_breadcrumbs()

    def set_filetype(self, value: str) -> None:
        """Force the current document's syntax type (``:set filetype=``).

        Accepts an extension key (``py``) or a language name (``python``);
        ``auto`` / an empty value clears the override and re-detects the type
        from the file path. Unknown values are still applied (an LSP server
        may match them), they simply get no built-in highlighter.
        """
        doc = self.doc
        raw = value.strip().lower().lstrip(".")
        if not raw or raw == "auto":
            doc.filetype_override = None
            self.message(f"filetype reset to {doc.filetype} (auto from path)", kind="ok")
        else:
            resolved = resolve_filetype(raw)
            if resolved is None:
                doc.filetype_override = raw
                self.message(
                    f"filetype set to {raw!r} -- no built-in highlighter "
                    f"(available: {', '.join(available_filetypes())})",
                    kind="warn",
                )
            else:
                doc.filetype_override = resolved
                label = language_name(resolved) or resolved
                self.message(f"filetype set to {resolved} ({label})", kind="ok")
        # Rebind the LSP document (close on the old server, open on the new)
        # and force a repaint so highlighting and the status bar update.
        self.run_worker(
            self.lsp.on_document_closed(doc),
            group="lsp-sync", exclusive=False, exit_on_error=False,
        )
        self.ui_refresh()

    def mode_label(self) -> tuple[str, str]:
        """(label, background color) for the status bar mode chip."""
        t = theme.active()
        if self.prompt_bar is not None and self.prompt_bar.active_mode:
            mode = self.prompt_bar.active_mode
            if mode == "shell":
                return "SHELL", t.mode_insert_bg
            if mode in ("find", "find_back", "replace_find", "replace_with"):
                return "SEARCH", t.match_active_bg
            return "COMMAND", t.mode_command_bg
        if self.keymap_name == "vim":
            vim = self.keymaps["vim"]
            if isinstance(vim, VimKeymap):
                mapping = {
                    VimMode.NORMAL: ("NORMAL", t.mode_normal_bg),
                    VimMode.INSERT: ("INSERT", t.mode_insert_bg),
                    VimMode.VISUAL: ("VISUAL", t.mode_visual_bg),
                    VimMode.VISUAL_LINE: ("V-LINE", t.mode_visual_bg),
                }
                return mapping.get(vim.mode, ("NORMAL", t.mode_normal_bg))
        return "VSC", t.mode_normal_bg

    # =============================================================== actions

    def execute_action(self, name: str) -> None:
        self.actions.execute(name, ActionContext(self))

    def insert_char(self, ch: str) -> None:
        self.buffer.insert_text(ch)

    def message(self, text: str, kind: str = "info") -> None:
        self._message_owner = "app"
        if self.prompt_bar is not None and self.mounted:
            self.prompt_bar.show_message(text, kind=kind)
            if self.status_bar is not None:
                self.status_bar.refresh_status()

    def page(self, direction: int, half: bool = False) -> None:
        if self.editor_view is None:
            return
        rows = self.editor_view.page_delta(half) * direction
        buf = self.buffer
        target = max(0, min(buf.row + rows, buf.line_count - 1))
        buf.cursor = (target, min(buf.col, len(buf.lines[target])))

    def handle_raw_key(self, raw: str) -> bool:
        """Dispatch one raw key to the active keymap, then refresh the UI."""
        handled = self.active_keymap.handle_key(ActionContext(self), raw)
        self.ui_refresh()
        self._after_editor_key(raw)
        return handled

    def ui_refresh(self) -> None:
        if not self.mounted or self.panes is None:
            return
        # The active view first; inactive panes showing the same document
        # repaint too (shared edit/LSP state, independent cursor/scroll).
        active = self.panes.active_view
        if active is not None:
            active.content_changed()
        for view in self.panes.all_views():
            if view is not active:
                view.content_changed()
        if self.status_bar is not None:
            self.status_bar.refresh_status()
        self.update_tabbar()
        self.update_breadcrumbs()
        # LSP: lazily open newly shown documents and push debounced edits.
        # Both are cheap no-ops when no extension registered a server for the
        # active file type.
        self._lsp_doc_shown_later()
        self.lsp.notify_edit(self.doc)
        self._update_lsp_echo()

    # ============================================================ focus/keys

    def focus_explorer(self) -> None:
        if self.workspace.root is None:
            self.message("no folder is open — use :e <path>", kind="warn")
            return
        if not self.explorer_visible:
            self.toggle_explorer()
        self.focus_target = "explorer"
        if self.explorer_tree is not None:
            self.explorer_tree.focus()
        self.message(
            "explorer: j/k move, l open, h fold, a new file, "
            "A new folder, r rename, d delete, esc back"
        )

    def focus_editor(self) -> None:
        self.focus_target = "editor"
        view = self.editor_view
        if view is not None:
            view.focus()

    def after_pane_focus(self) -> None:
        """App-level sync after the active pane changed (pane manager hook)."""
        self.close_completion()
        self.ui_refresh()

    # ------------------------------------------------------- pane commands

    def _split_pane(self, axis: Axis) -> None:
        self.run_worker(
            self._split_pane_worker(axis, None),
            group="pane", exclusive=True, exit_on_error=False,
        )

    async def _split_pane_worker(
        self, axis: Axis, path: Optional[Path]
    ) -> None:
        if self.panes is None:
            return
        if path is not None:
            # split first (the new pane becomes active), then open the file
            # into the active pane
            await self.panes.split_active(axis)
            await self.open_path_async(path)
        else:
            await self.panes.split_active(axis)
            self.after_pane_focus()

    def _split_with_path(self, axis: Axis, args: str) -> None:
        text = args.strip()
        if not text:
            self._split_pane(axis)
            return
        path = Path(text).expanduser()
        if not path.is_absolute():
            # vim resolves :sp/:vs relative paths against the current file's
            # directory (falling back to cwd for unnamed buffers)
            base = self.doc.path.parent if self.doc.path else Path.cwd()
            path = base / path
        try:
            is_dir = path.is_dir()
        except OSError:
            is_dir = False
        if is_dir:
            self.open_path(path)
            return
        self.run_worker(
            self._split_pane_worker(axis, path),
            group="pane", exclusive=True, exit_on_error=False,
        )

    def _only_pane(self) -> None:
        if self.panes is None:
            return
        self.run_worker(
            self.panes.only_active(),
            group="pane", exclusive=True, exit_on_error=False,
        )

    def _close_pane(self) -> None:
        """``ctrl+w q``: close the active pane (documents stay open).

        With a single pane this is a no-op (use ``:q`` to leave yate).
        """
        if self.panes is None or self.panes.leaf_count <= 1:
            self.message("only one pane open (use :q to quit)", kind="warn")
            return
        self.run_worker(
            self.panes.close_active(),
            group="pane", exclusive=True, exit_on_error=False,
        )

    def _resize_pane(self, key: str) -> None:
        if self.panes is None:
            return
        if key in ("+", "plus"):
            moved = self.panes.resize("horizontal", 1)
        elif key in ("-", "minus"):
            moved = self.panes.resize("horizontal", -1)
        elif key in (">", "greater_than_sign"):
            moved = self.panes.resize("vertical", 1)
        elif key in ("=", "equals_sign"):
            self.panes.equalize()
            moved = True
        else:  # "<" / "less_than_sign"
            moved = self.panes.resize("vertical", -1)
        if not moved and key not in ("=", "equals_sign"):
            self.message("pane already at its minimum size", kind="warn")

    @property
    def window_pending(self) -> bool:
        """True while a vim ``ctrl+w`` window chord awaits its second key."""
        return self._window_pending

    def _window_command(self, key: str) -> None:
        """Execute the second key of a vim ``ctrl+w`` window chord."""
        if key == "ctrl+w":  # round-robin: explorer <-> every editor pane
            if self.panes is not None:
                self.panes.cycle_focus(
                    explorer_focused=self.focused is self.explorer_tree
                )
            return
        if self.focused is self.explorer_tree:
            # The explorer plays the left-neighbour pane: only ctrl+w l/j/k
            # returns to an editor pane from it.
            if key in ("l", "j", "k"):
                self.focus_editor()
            return
        if key == "h":
            if self.panes is not None and not self.panes.focus_direction("h"):
                self.focus_explorer()
        elif key in ("j", "k", "l"):
            if self.panes is not None:
                self.panes.focus_direction(key)
        elif key == "s":
            self._split_pane("horizontal")
        elif key == "v":
            self._split_pane("vertical")
        elif key == "q":
            self._close_pane()
        elif key == "o":
            self._only_pane()
        elif key in ("+", "minus", "-", "<", "less_than_sign", ">",
                     "greater_than_sign", "=", "equals_sign", "plus"):
            self._resize_pane(key)

    #: Keys accepted as the second half of ``ctrl+w``. Symbol keys carry
    #: Textual's canonical names (``minus`` / ``equals_sign`` / ...) but the
    #: raw symbols are accepted too.
    _WINDOW_KEYS = frozenset(
        {"h", "j", "k", "l", "s", "v", "q", "o",
         "+", "plus", "-", "minus",
         "<", "less_than_sign", ">", "greater_than_sign",
         "=", "equals_sign", "ctrl+w"}
    )

    def try_window_prefix(self, event: Key) -> bool:
        """Handle the vim ``ctrl+w`` window chord; True when consumed.

        Called from the editor view *before* keymap dispatch (the vim
        keymap swallows unmapped keys, so app.on_key would never see
        them) and from app.on_key for the other focused widgets.
        """
        if len(self.screen_stack) > 1:
            return False
        if self.prompt_bar is not None and self.prompt_bar.active_mode:
            return False
        if self._window_pending:
            self._window_pending = False
            if event.key in self._WINDOW_KEYS:
                self._window_command(event.key)
                return True
            return False  # any other key cancels and is processed normally
        if self.keymap_name == "vim" and event.key == "ctrl+w":
            km = self.keymaps["vim"]
            if isinstance(km, VimKeymap) and km.mode is VimMode.NORMAL:
                self._window_pending = True
                self.message(
                    "ctrl+w-  (s/:split v/:vsplit q close o :only  "
                    "h j k l move, ctrl+w cycle  + - < > = resize)"
                )
                return True
        return False

    def on_key(self, event: Key) -> None:
        """Fallback routing: keys not consumed by a focused widget."""
        if len(self.screen_stack) > 1:
            return  # modal screen owns input
        if event.key in TOGGLE_KEYS and event.key != "ctrl+@":
            # ctrl+@ is excluded: on Windows conhost it is also the byte for
            # Ctrl+Space, which must not open the terminal (it still closes
            # it when the terminal itself is focused, via terminal.py)
            event.stop()
            event.prevent_default()
            self.toggle_terminal()
            return
        # vim ctrl+w window chord (armed or pending); before the other
        # chords so the prefix is consumed wherever focus currently is
        if self.try_window_prefix(event):
            event.stop()
            event.prevent_default()
            return
        # Global chords that raw byte dispatch cannot represent reliably.
        # alt+shift+p is the default: Windows Terminal reserves ctrl+shift+p
        # for its own command palette, and ctrl+shift+a clashes with other
        # terminal emulators; alt+shift+p is unbound in both.
        if event.key == "alt+shift+p":
            event.stop()
            event.prevent_default()
            self.open_command_palette()
            return
        if self.prompt_bar is not None and self.prompt_bar.active_mode:
            return  # command line is editing; enter must bubble so the
            # Input's own enter->submit binding can fire
        # vscode-style pane focus chords (CSI-u encodings, not in the raw
        # byte table)
        if event.key == "ctrl+shift+e":
            event.stop()
            event.prevent_default()
            self.focus_explorer()
            return
        if event.key == "ctrl+1":
            event.stop()
            event.prevent_default()
            self.focus_editor()
            return
        if event.key == "ctrl+p":
            event.stop()
            event.prevent_default()
            self.open_file_palette()
            return
        if self.focused is self.explorer_tree:
            return  # explorer consumes its own keys
        raw = event_to_raw(event.key, event.character)
        if raw is None:
            return
        if self.handle_raw_key(raw):
            event.stop()
            event.prevent_default()

    def on_prompt_cancel(self) -> None:
        # leaving the find prompt clears live highlights
        if self.search.query:
            self.search.update("", self.buffer)
        if self.prompt_bar is not None:
            self.prompt_bar.idle()
        self.focus_editor()
        self.ui_refresh()

    # ------------------------------------------------------ explorer files

    # Explorer file operations live in yate.app_features.explorer; the
    # methods below keep the historical names as thin delegates (the keymap
    # actions and the explorer widget call them on the app).
    def explorer_new_file_prompt(self, directory: Optional[Path]) -> None:
        explorer.prompt_new_file(self, directory)

    def explorer_new_dir_prompt(self, directory: Optional[Path]) -> None:
        explorer.prompt_new_dir(self, directory)

    def _explorer_prompt_new(self, directory: Optional[Path], *, is_dir: bool) -> None:
        explorer.prompt_new(self, directory, is_dir=is_dir)

    def explorer_rename_prompt(self, path: Optional[Path]) -> None:
        explorer.prompt_rename(self, path)

    def explorer_delete_prompt(self, path: Optional[Path]) -> None:
        explorer.prompt_delete(self, path)

    def _explorer_create(self, directory: Optional[Path], name: str) -> None:
        explorer.create(self, directory, name)

    def _explorer_apply_rename(self, path: Optional[Path], name: str) -> None:
        explorer.apply_rename(self, path, name)

    def _explorer_apply_delete(self, path: Optional[Path], confirm: str) -> None:
        explorer.apply_delete(self, path, confirm)

    # ------------------------------------------------------------- prompts

    def prompt_open(self) -> None:
        if self.prompt_bar is None:
            return
        self.prompt_bar.activate("open", placeholder="path to a file or directory")

    def _submit_open(self, text: str) -> None:
        text = text.strip()
        if text:
            self.open_path_later(Path(text))

    def command_prompt(self) -> None:
        if self.prompt_bar is None:
            return
        self.prompt_bar.activate("command", placeholder="type a command, :help for list")

    def shell_prompt(self) -> None:
        if self.prompt_bar is None:
            return
        self.prompt_bar.activate("shell", placeholder="shell command")

    def find_prompt(self, forward: bool) -> None:
        if self.prompt_bar is None:
            return
        self.prompt_bar.activate(
            "find" if forward else "find_back",
            initial=self.search.query,
            placeholder="search pattern (enter to jump, esc to cancel)",
        )

    def _submit_search(self, text: str, forward: bool) -> None:
        if not text:
            return
        self.find_next(forward)

    def find_next(self, forward: bool) -> None:
        if not self.search.query:
            self.message("no active search — press / to start one", kind="warn")
            return
        match = self.search.next(self.buffer, forward=forward)
        if match is None:
            self.message(f"no matches for {self.search.query!r}", kind="warn")
        else:
            self.message(
                f"[{self.search.index + 1}/{len(self.search.matches)}] {self.search.query!r}"
            )

    def replace_prompt(self) -> None:
        if self.prompt_bar is None:
            return
        self.prompt_bar.activate("replace_find", placeholder="text to find")

    def _replace_find_step(self, find: str) -> None:
        find = find.strip()
        if not find:
            self.message("replace cancelled")
            return
        self._replace_pending = find
        if self.prompt_bar is not None:
            self.prompt_bar.activate("replace_with", placeholder="replacement text")

    def _do_replace(self, find: str, replacement: str) -> None:
        matches = self.search.update(find, self.buffer)
        if not matches:
            self.message(f"no matches for {find!r}", kind="warn")
            return
        count = self.search.replace_all(self.buffer, replacement)
        self.message(f"replaced {count} occurrence(s) of {find!r}", kind="ok")

    # ------------------------------------------------------ input messages

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if self.prompt_bar is None or event.input is not self.prompt_bar.input:
            return
        mode = self.prompt_bar.active_mode
        text = event.value
        self.prompt_bar.input.push_history(text)
        refocus_explorer = False

        if mode == "command":
            self.run_command(text)
        elif mode == "goto":
            text = text.strip()
            if re.fullmatch(r"[+-]?\d+", text):
                self.goto_line_command(text)
            elif text:
                self.message(f"not a line number: {text!r}", kind="warn")
        elif mode in ("find", "find_back"):
            self._submit_search(text, mode == "find")
        elif mode == "shell":
            self.run_shell_command_later(text)
        elif mode == "open":
            self._submit_open(text)
        elif mode == "save":
            self._do_save_as(text)
        elif mode == "replace_find":
            self._replace_find_step(text)
        elif mode == "replace_with":
            self._do_replace(self._replace_pending, text)
        elif mode in ("new_file", "new_dir"):
            self._explorer_create(self._explorer_target, text)
            # a newly created file was opened for editing -> focus the
            # editor; folders and other operations keep the explorer focus
            refocus_explorer = self._explorer_is_dir
        elif mode == "rename":
            self._explorer_apply_rename(self._explorer_target, text)
            refocus_explorer = True
        elif mode == "delete":
            self._explorer_apply_delete(self._explorer_target, text)
            refocus_explorer = True

        if self.prompt_bar.active_mode is not None:
            return  # a follow-up prompt is active (replace_with)
        if refocus_explorer and self.workspace.root is not None:
            self.focus_explorer()
        else:
            self.focus_editor()
        self.ui_refresh()

    def on_input_changed(self, event: Input.Changed) -> None:
        if self.prompt_bar is None or event.input is not self.prompt_bar.input:
            return
        mode = self.prompt_bar.active_mode
        if mode in ("find", "find_back"):
            self.search.update(event.value, self.buffer)
            if self.panes is not None:
                for view in self.panes.views_for(self.doc):
                    view.refresh()

    # ----------------------------------------------------- prompt completion

    # Commands whose single argument is a filesystem path.
    _PATH_COMMANDS = frozenset(
        {"e", "edit", "sp", "split", "vs", "vsplit"}
    )
    _SET_OPTIONS = (
        "filetype", "ft", "keymap", "lang", "language", "shell",
        "terminal_height", "theme", "show_hidden",
    )
    _FILETYPE_KEYS = frozenset({"filetype", "ft", "language", "lang"})
    _FILETYPE_COMMANDS = frozenset({"filetype", "ft", "language"})
    _MANUAL_LANGS = ("en", "zh")

    def prompt_completions(self, text: str, mode: str) -> list[str]:
        """Tab-completion candidates for the bottom prompt.

        *mode* is the active ``PromptBar`` mode (``"command"``, ``"open"``,
        ``"save"``, ...).  Returns strings that extend *text*; the caller
        decides how to cycle / apply the common prefix (bash-style).
        """
        if mode == "command":
            return self._command_completions(text)
        if mode in ("open", "save", "new_file", "rename", "delete"):
            return self._path_matches(text)
        if mode == "shell":
            return []
        return []

    def _command_completions(self, text: str) -> list[str]:
        if " " not in text:
            names = self.commands.names()
            return sorted(n for n in names if n.startswith(text))
        name, _, rest = text.partition(" ")
        name = name.strip()
        rest = rest.lstrip()
        if name in self._PATH_COMMANDS:
            return [f"{name} {c}" for c in self._path_matches(rest)]
        if name == "set":
            if "=" in rest:
                key, _, value = rest.partition("=")
                key = key.strip()
                if key == "keymap":
                    vals = ("vsc", "vim")
                elif key == "theme":
                    vals = tuple(theme.available())
                elif key in self._FILETYPE_KEYS:
                    vals = ("auto", *available_filetypes())
                elif key == "show_hidden":
                    vals = ("on", "off")
                else:
                    return []
                return [
                    f"{name} {key}={v}" for v in vals
                    if v.startswith(value) and v != value
                ]
            return [
                f"{name} {opt}" for opt in self._SET_OPTIONS
                if opt.startswith(rest) and opt != rest
            ]
        if name in self._FILETYPE_COMMANDS:
            vals = ("auto", *available_filetypes())
            return [
                f"{name} {v}" for v in vals
                if v.startswith(rest) and v != rest
            ]
        if name in ("theme", "colorscheme"):
            return [
                f"{name} {t}" for t in theme.available()
                if t.startswith(rest) and t != rest
            ]
        if name == "manual":
            return [
                f"{name} {l}" for l in self._MANUAL_LANGS
                if l.startswith(rest) and l != rest
            ]
        return []

    def _path_matches(self, prefix: str) -> list[str]:
        """Filesystem entries whose path starts with *prefix*.

        Relative paths are resolved against the workspace root (falling back
        to the process cwd), mirroring how ``:e`` and the open prompt treat
        paths.
        """
        expanded = os.path.expanduser(prefix)
        try:
            p = Path(expanded)
            parent = p.parent if p.name else p
            base = p.name
        except ValueError:
            return []
        if not parent.is_absolute() and self.workspace.root is not None:
            parent = self.workspace.root / parent
        if not parent.exists() or not parent.is_dir():
            return []
        try:
            entries = sorted(parent.iterdir(), key=lambda x: x.name.lower())
        except OSError:
            return []
        needle = base.lower()
        results: list[str] = []
        for entry in entries:
            if not entry.name.lower().startswith(needle):
                continue
            dir_part = prefix[: len(prefix) - len(base)] if base else prefix
            candidate = dir_part + entry.name
            if entry.is_dir():
                candidate += "/"
            if candidate != prefix:
                results.append(candidate)
        return results

    # ================================================================= shell

    def run_shell_command(self, command: str, show_output: bool = True) -> Optional[ShellResult]:
        """Run a shell command synchronously and capture its output.

        Blocking: used by the (synchronous) extension API.  Interactive
        callers go through :meth:`run_shell_command_async` so the TUI stays
        responsive while the command runs.
        """
        command = command.strip()
        if not command:
            return None
        cwd = self._shell_cwd()
        result = run_shell(command, cwd=cwd)
        if show_output and self.mounted:
            self._show_shell_result(command, result, cwd)
        return result

    def run_shell_command_later(self, command: str) -> None:
        """Schedule a non-blocking shell run from a sync handler."""
        command = command.strip()
        if not command:
            return
        # the prompt bar stays in its active mode until a command messages
        # back; the background job only reports when it finishes, so close
        # the prompt up front (otherwise focus vanishes when it hides)
        if self.prompt_bar is not None and self.prompt_bar.active_mode in (
            "shell", "command"
        ):
            self.prompt_bar.idle()
            self.focus_editor()
            self.ui_refresh()
        self.run_worker(
            self.run_shell_command_async(command),
            group="shell", exclusive=False, exit_on_error=False,
        )

    async def run_shell_command_async(
        self, command: str, show_output: bool = True
    ) -> Optional[ShellResult]:
        """Run a shell command in a worker thread (UI keeps responding)."""
        command = command.strip()
        if not command:
            return None
        cwd = self._shell_cwd()
        self.message(f"running: {command}", kind="info")
        result = await asyncio.to_thread(run_shell, command, cwd=cwd)
        if show_output and self.mounted:
            self._show_shell_result(command, result, cwd)
        return result

    def _shell_cwd(self) -> Path:
        return (
            self.workspace.root
            or (self.doc.path.parent if self.doc.path is not None else None)
            or Path.cwd()
        )

    def _show_shell_result(
        self, command: str, result: ShellResult, cwd: Path
    ) -> None:
        body = (
            f"(cwd: {cwd} · {shell_name()})\n\n"
            f"{result.output or '(no output)'}"
        )
        self._push_overlay(OutputScreen(self, f"$ {command}", body, result.returncode))

    # ================================================================== lsp

    # -------------------------------------------------------- document sync

    def _lsp_doc_shown_later(self) -> None:
        """Open the active document on its server once a server is registered."""
        doc = self.doc
        if not self.lsp.supports(doc) or self.lsp.is_open(doc):
            return
        self.run_worker(
            self.lsp.on_document_shown(doc),
            group="lsp-sync", exclusive=False, exit_on_error=False,
        )

    def _on_lsp_event(self, event: str) -> None:
        """Manager callback (event loop thread): repaint after LSP updates."""
        if not self.mounted or self.panes is None:
            return
        for view in self.panes.all_views():
            view.refresh()
        if self.status_bar is not None:
            self.status_bar.refresh_status()
        if event == "diagnostics":
            self._update_lsp_echo()

    def _update_lsp_echo(self) -> None:
        """Show the diagnostic under the cursor on the message line."""
        if self.prompt_bar is None or self.prompt_bar.active_mode is not None:
            return
        buf = self.buffer
        diag = self.lsp.diagnostic_at(self.doc, buf.row, buf.col)
        if diag is not None:
            glyph = "✖" if diag.is_error else ("▲" if diag.is_warning else "●")
            source = f"{diag.source}: " if diag.source else ""
            self._message_owner = "lsp"
            self.prompt_bar.show_message(
                f"{glyph} {source}{diag.message}",
                kind="error" if diag.is_error else "warn",
            )
        elif self._message_owner == "lsp":
            self._message_owner = "idle"
            self.prompt_bar.idle()

    # ------------------------------------------------------------ completion
    # The controller (yate.app_features.completion.CompletionController) owns
    # the debounce timer and the worker; the app forwards public calls so
    # keymaps, the editor view and extensions keep their entry points.

    def close_completion(self) -> None:
        self.completion_ctl.close()

    def _after_editor_key(self, raw: str) -> None:
        """Adjust the completion popup after a normal editor keystroke."""
        self.completion_ctl.after_editor_key(raw)

    def request_completion(
        self, manual: bool = True, trigger_ch: Optional[str] = None
    ) -> None:
        """Fetch completions and show the popup (worker; never blocks input)."""
        self.completion_ctl.request(manual, trigger_ch)

    def accept_completion(self) -> None:
        """Insert the selected completion at its reported range."""
        self.completion_ctl.accept()

    def show_diagnostics(self) -> None:
        """``:diagnostics`` -- list the active document's LSP diagnostics."""
        diags = self.lsp.diagnostics_for(self.doc)
        if not diags:
            self.message("no diagnostics", kind="ok")
            return
        labels = {1: "error", 2: "warning", 3: "info", 4: "hint"}
        lines = [
            f"L{d.start_row + 1}:{d.start_col + 1}  "
            f"{labels.get(d.severity, str(d.severity)).upper():7}  "
            f"{('[' + d.source + '] ') if d.source else ''}{d.message}"
            for d in diags
        ]
        errors, warnings = self.lsp.counts_for(self.doc)
        title = f"diagnostics — {errors} error(s), {warnings} warning(s)"
        self._push_overlay(OutputScreen(self, title, "\n".join(lines), 0))

    # ================================================================ modals

    def _push_overlay(
        self,
        screen: Screen[Any],
        callback: Optional[Callable[[Any], None]] = None,
    ) -> None:
        """Push a full-screen overlay, clearing the stale bottom message first.

        The prompt/message line is hidden behind the overlay while it is up,
        so reset it to the idle hint now; otherwise the previous command's
        message (e.g. "saved …") would reappear, untouched, once the overlay
        closes -- looking like the overlay command itself had no feedback.
        """
        if self.prompt_bar is not None:
            self.prompt_bar.idle()
        self.push_screen(screen, callback=callback)

    def show_help(self) -> None:
        """Open the keybinding reference overlay."""
        if self.mounted:
            self._push_overlay(HelpScreen(self))

    def show_manual(self, lang: str = "en") -> None:
        """Open the bundled user manual, rendered as read-only markdown."""
        if not self.mounted or isinstance(self.screen, ManualScreen):
            return
        # switch the textual design tokens before pushing so the first
        # frame of the markdown viewer is already themed (switching on
        # screen resume leaves an unthemed flash while markdown mounts)
        self._prev_manual_theme = self.theme
        self.theme = "catppuccin-mocha"
        self._push_overlay(
            ManualScreen(self, lang),
            callback=lambda _result: self._restore_manual_theme(),
        )

    def _restore_manual_theme(self) -> None:
        if self._prev_manual_theme is not None:
            self.theme = self._prev_manual_theme
            self._prev_manual_theme = None

    def open_file_palette(self) -> None:
        """Quick file open: fuzzy palette over the workspace files (ctrl+p)."""
        if self.mounted:
            self._push_overlay(PaletteScreen(self, "files"))

    def open_command_palette(self) -> None:
        """Command palette: fuzzy search over ``:`` commands (alt+shift+p)."""
        if self.mounted:
            self._push_overlay(PaletteScreen(self, "commands"))

    async def action_quit(self) -> None:
        """Textual's ctrl+q priority binding — route through our guard."""
        self.quit()

    # =============================================================== commands

    # Built-in ex commands are registered by
    # yate.app_features.commands.register_commands (called from __init__).

    def toggle_explorer(self) -> None:
        self.explorer_visible = not self.explorer_visible
        self._sync_explorer_visibility()
        if self.explorer_visible and self.workspace.root is not None:
            # focus the tree so keyboard nav works immediately on show;
            # defer until after the next layout pass -- a freshly shown
            # widget still has a 0x0 region and Textual refuses focus
            self.focus_target = "explorer"
            if self.explorer_tree is not None:
                self.explorer_tree.call_after_refresh(self.explorer_tree.focus)
            self.message("explorer: j/k move, l open, h fold, a new file, "
                         "A new folder, r rename, d delete, H toggle hidden, esc back")
        else:
            self.message(f"explorer {'shown' if self.explorer_visible else 'hidden'}")

    def _sync_explorer_visibility(self) -> None:
        visible = self.explorer_visible and self.workspace.root is not None
        if self.explorer_tree is not None:
            self.explorer_tree.display = visible
        if self.sidebar is not None:
            self.sidebar.display = visible

    # ============================================================ terminal
    # The panel lifecycle lives in yate.app_features.terminal; the app
    # keeps the flags (_terminal_visible/_terminal_starting/_terminal_factory)
    # and the historical method names.

    def toggle_terminal(self) -> None:
        """Show/focus or hide the integrated terminal (Ctrl+`)."""
        terminal.toggle_terminal(self)

    def open_terminal(self) -> None:
        """Reveal the bottom terminal and focus it, spawning the shell."""
        terminal.open_terminal(self)

    def close_terminal(self) -> None:
        """Hide the panel; the shell process itself stays alive."""
        terminal.close_terminal(self)

    def _spawn_terminal(self) -> None:
        terminal.spawn_shell(self)

    def _font_command(self) -> None:
        # registry lookups / font registration touch subprocess and would
        # freeze the TUI on some systems; run off the event loop
        self.message("checking Nerd Font…", kind="info")
        self.run_worker(
            self._font_command_async(), group="font",
            exclusive=True, exit_on_error=False,
        )

    async def _font_command_async(self) -> None:
        status = await asyncio.to_thread(fonts.ensure_font)
        if self.mounted:
            self.message(status.detail or ("Nerd Font ready" if status.has_nerd_font
                                           else "font setup failed"),
                         kind="ok" if status.has_nerd_font else "error")

    def run_command(self, text: str) -> None:
        text = text.strip()
        if not text:
            return
        if text.startswith("!"):
            self.run_shell_command_later(text[1:])
            return
        # A bare number is a line jump (vim's :42, same as VS Code's
        # Ctrl+G -> go to line). An optional sign makes it relative: :+5.
        if re.fullmatch(r"[+-]?\d+", text):
            self.goto_line_command(text)
            return
        parts = text.split()
        name, args = parts[0], " ".join(parts[1:])
        entry = self.commands.get(name)
        if entry is None:
            self.message(f"not an editor command: {name} (try :help)", kind="warn")
            return
        entry[0](args)

    def goto_line_command(self, text: str) -> None:
        """Jump to an absolute (``42``) or signed-relative (``+5``) line."""
        value = int(text)
        buf = self.buffer
        if text[:1] in ("+", "-"):
            target = buf.row + 1 + value  # 1-based current row + offset
        else:
            target = value
        self.goto_line(target)

    def goto_line(self, line: int) -> None:
        """Move the cursor to 1-based *line*, clamped to the document.

        The column is preserved (clamped to the destination line), matching
        VS Code's Go to Line; the selection is cleared and the view follows.
        """
        buf = self.buffer
        row = max(0, min(line - 1, buf.line_count - 1))
        col = min(buf.col, len(buf.lines[row]))
        buf.anchor = None
        buf.set_cursor((row, col))
        self.search.update("", buf)
        view = self.editor_view
        if view is not None:
            view.scroll_col = 0
            view.reveal_cursor()
        self.message(f"line {row + 1} of {buf.line_count}")
        self.ui_refresh()

    def goto_prompt(self) -> None:
        """Open the command line in go-to-line mode (Ctrl+G)."""
        if self.prompt_bar is None:
            return
        self.prompt_bar.activate(
            "goto", placeholder=f"line number (1-{self.buffer.line_count})"
        )

    # ================================================================== quit

    def quit(self, force: bool = False) -> None:
        if not force and any(doc.modified for doc in self.docs):
            self.message("unsaved changes — :q! to quit anyway", kind="warn")
            return
        if self.mounted:
            self.exit()

    # =============================================================== tab bar

    def render_tabbar(self, width: int) -> Text:
        """Build the flat VS Code-style tab line.

        Inactive tabs sit on the panel background; the active tab uses the
        editor background so it visually merges with the editor below.
        """
        t = theme.active()
        text = Text()
        used = 0
        for i, doc in enumerate(self.docs):
            name = theme.truncate_to_cells(doc.name, 24)
            active = i == self.doc_index
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
            used += seg_cells
        if used < width:
            text.append(" " * (width - used), style=f"on {t.panel}")
        return text

    def update_tabbar(self) -> None:
        """Refresh the tab bar contents and its themed background."""
        if self.tabbar is not None:
            self.tabbar.styles.background = theme.active().panel
            self.tabbar.update(self.render_tabbar(self.tabbar.size.width or 80))

    # =========================================================== breadcrumbs

    def _crumb_parts(self) -> list[tuple[str, str, bool]]:
        """(icon, label, is_file) crumbs for the active document's path."""
        doc = self.doc
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

    def render_breadcrumbs(self, width: int) -> Text:
        """Build the VS Code-style breadcrumb line (path crumbs above editor)."""
        t = theme.active()
        crumbs = self._crumb_parts()

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

    def update_breadcrumbs(self) -> None:
        """Refresh the breadcrumb line and its editor-colored background."""
        if self.breadcrumbs is not None:
            self.breadcrumbs.styles.background = theme.active().bg
            self.breadcrumbs.update(
                self.render_breadcrumbs(self.breadcrumbs.size.width or 80)
            )

    def _update_sidebar_head(self) -> None:
        """Paint the VS Code-style 'EXPLORER' sidebar title."""
        if self.sidebar_head is not None:
            t = theme.active()
            self.sidebar_head.styles.background = t.panel
            self.sidebar_head.update(Text(" EXPLORER", style=f"bold {t.fg_dim}"))

    # ============================================================== compose

    def compose(self) -> ComposeResult:
        with Horizontal(id="body"):
            with Vertical(id="sidebar"):
                yield Static(id="sidebar-head")
                yield ExplorerTree(self, id="explorer")
            with Vertical(id="editor-col"):
                yield Static(id="tabbar")
                yield Static(id="breadcrumbs")
                yield PaneHost(self.panes) if self.panes is not None else Static()
        # Both live in one docked container so the terminal always sits
        # directly above the status/prompt strip (VS Code layout).
        with Vertical(id="bottom-dock"):
            yield TerminalPanel(self, id="terminal-dock")
            with Vertical(id="bottom"):
                yield StatusBar(self, id="statusbar")
                yield PromptBar(self)

    async def on_mount(self) -> None:
        """Wire up widgets, load extensions and apply the initial theme."""
        self.sidebar = self.query_one("#sidebar", Vertical)
        self.sidebar_head = self.query_one("#sidebar-head", Static)
        self.tabbar = self.query_one("#tabbar", Static)
        self.breadcrumbs = self.query_one("#breadcrumbs", Static)
        self.explorer_tree = self.query_one("#explorer", ExplorerTree)
        self.status_bar = self.query_one("#statusbar", StatusBar)
        self.prompt_bar = self.query_one(PromptBar)
        self.terminal_panel = self.query_one("#terminal-dock", TerminalPanel)
        self.terminal_panel.styles.height = self.config.terminal_height
        self.terminal_panel.display = False

        self._load_extensions()
        self._register_configured_servers()
        self.completion_popup = CompletionPopup(self)
        await self.query_one("#editor-col", Vertical).mount(self.completion_popup)
        self.apply_theme()
        self.explorer_tree.refresh_tree()
        self._sync_explorer_visibility()
        initial_view = self.editor_view
        assert initial_view is not None
        initial_view.focus()

        if self._ext_messages:
            self.prompt_bar.show_message("; ".join(self._ext_messages), kind="warn")
        elif self.keymap_name == "vim":
            self.prompt_bar.idle("-- NORMAL --  (F1 help, : commands)")
        else:
            self.prompt_bar.idle(
                f"yate {__version__} — F1 help, Ctrl+P quick open, "
                "Alt+Shift+P command palette"
            )
        self.ui_refresh()

    async def on_unmount(self) -> None:
        # Each teardown is isolated: a failing terminal/LSP shutdown must not
        # leave the other background service (and its threads) untouched.
        # Extension hooks run first (sync, while app state is still intact);
        # they release resources the extension owns, e.g. spawned
        # subprocesses or timers. teardown_all isolates per extension.
        self.extension_loader.teardown_all()
        if self.terminal_panel is not None:
            try:
                await self.terminal_panel.view.shutdown()
            except Exception:
                pass
        try:
            await self.lsp.shutdown_all()
        except Exception:
            pass

    # ================================================================ run

    def _load_extensions(self) -> None:
        def _report(records: list[LoadedExtension]) -> None:
            for record in records:
                if record.error:
                    self._ext_messages.append(f"extension {record.name}: {record.error}")

        # rc-declared paths load first (user rc then project rc), followed by
        # the bundled defaults, project/user directories and explicit CLI
        # paths.
        for path in self.config.extension_paths:
            if path.is_dir():
                _report(self.extension_loader.load_directory(path))
            elif path.is_file():
                _report([self.extension_loader.load_file(path)])
            else:
                self._ext_messages.append(f"extension path not found: {path}")
        # Extensions shipped with yate (inside the package / the PyInstaller
        # bundle). Individual defaults can be switched off in yaterc with
        # ``disabled_extensions``; same-named scripts loaded afterwards from
        # a project or user directory get the last word on registrations.
        bundled = bundled_extensions_dir()
        if bundled.is_dir():
            # Registrars are last-write-wins, so a bundled default loading
            # *after* an rc-declared same-stem script would silently take over
            # its commands/highlight/server. Name the conflict and point at
            # the documented opt-out instead of letting the user script lose
            # without explanation.
            rc_owners = {r.name: r for r in self.extension_loader.loaded}
            records = self.extension_loader.load_directory(
                bundled,
                exclude=self.config.disabled_extensions,
            )
            for record in records:
                owner = rc_owners.get(record.name)
                if owner is not None and record.error is None:
                    self._ext_messages.append(
                        f"extension {record.name}: the rc-declared script "
                        f"{owner.path} is shadowed by the bundled default; "
                        f'add disabled_extensions = ["{record.name}"] to '
                        "yaterc to use the rc-declared version"
                    )
            _report(records)
        directories = [
            *self._ext_dirs,
            Path.cwd() / "extensions",
            Path.home() / ".yate" / "extensions",
        ]
        for directory in directories:
            _report(self.extension_loader.load_directory(directory))
        for file in self._ext_files:
            _report([self.extension_loader.load_file(file)])

    def _register_configured_servers(self) -> None:
        """Register LSP servers declared by the yaterc ``language_servers``
        option.

        Registration happens after extensions so an explicit rc entry with a
        server's name replaces a same-named extension registration. Nothing
        is spawned here: the manager starts the process lazily the first time
        a matching file is shown, so merely configuring a server is free.
        """
        bridge = self.extension_api.lsp
        for spec in self.config.language_servers:
            bridge.register_server(
                spec.name,
                command=spec.command,
                args=spec.args,
                filetypes=spec.filetypes,
                language_ids=spec.language_ids,
                initialization_options=spec.initialization_options,
                settings=spec.settings,
                env=spec.env,
                root_markers=spec.root_markers,
            )
