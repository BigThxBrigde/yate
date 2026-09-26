"""The running editor: session, services, widgets and the operations on them.

:class:`Editor` is the layer everything below the application talks to:

* it owns the document session, the workspace, the language servers, the
  keymaps and the two registries (actions / commands);
* it builds the widget tree (returned by :meth:`Editor.compose`) and keeps
  the references the operations need;
* it implements the editor-level operations -- open / save / close, panes,
  prompts, key dispatch, shell, themes, overlays, completion, extensions.

Widgets and the built-in tables only ever call these operations; the
``YateApp`` shell mounts the widgets and forwards app-level events, and is
the only module behind ``cli.py``.  No host protocol is involved: every
collaborator is a concrete object or a plain callable.
"""

from __future__ import annotations

import asyncio
import re
from functools import partial
from pathlib import Path
from typing import Any

from collections.abc import Callable

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.events import Key
from textual.screen import Screen
from textual.widgets import Static

from yate import __version__
from yate.completion import CompletionController
from yate.config import YateConfig
from yate.editor_core import BufferReadOnlyError, Document
from yate.editor_lsp import LspManager
from yate.editor_syntax import available_filetypes, language_name, resolve_filetype
from yate.editor_view import theme
from yate.editor_view.chrome import Breadcrumbs, TabBar, sidebar_head_text
from yate.editor_view.commandline import PromptBar
from yate.editor_view.completion import CompletionPopup
from yate.editor_view.editor import EditorView
from yate.editor_view.explorer import ExplorerTree
from yate.editor_view.keys import event_to_raw
from yate.editor_view.manual import MarkdownDocScreen
from yate.editor_view.modals import HelpScreen, OutputScreen
from yate.editor_view.palette import PaletteScreen
from yate.editor_view.panes import PaneHost, PaneManager
from yate.editor_view.statusbar import StatusBar, mode_chip
from yate.editor_view.terminal import TOGGLE_KEYS, TerminalPanel
from yate.keymaps.base import ActionContext, KeyUi
from yate.keymaps.registry import KeymapSet
from yate.keymaps.vsc import VscKeymap
from yate.keymaps.vim import VimKeymap, VimMode
from yate.logs import tracing
from yate.prompt_completion import prompt_completions
from yate.registries import ActionRegistry, CommandRegistry
from yate.services import fonts
from yate.services.extensions import (
    ExtensionAPI,
    ExtensionContext,
    ExtensionLoader,
    load_startup_extensions,
)
from yate.services.shell import ShellResult, run_shell, shell_name
from yate.services.trust import trust_workspace
from yate.services.workspace import Workspace
from yate.session import Axis, EditorSession, Leaf

#: Trace logger ("yate.editor"); silent unless yate_trace is on.
log = tracing.get_logger(__name__)

#: The keys accepted as the second half of a vim ``ctrl+w`` chord.
_WINDOW_KEYS = frozenset(
    {"h", "j", "k", "l", "s", "v", "q", "o",
     "+", "plus", "-", "minus",
     "<", "less_than_sign", ">", "greater_than_sign",
     "=", "equals_sign", "ctrl+w"}
)


class Editor:
    """The running editor: models, widgets and the operations that tie them."""

    def __init__(
        self,
        app: App[Any],
        config: YateConfig,
        *,
        target: str | Path | None = None,
        keymap: str | None = None,
        readonly: bool = False,
        ext_files: list[str | Path] | None = None,
        ext_dirs: list[str | Path] | None = None,
    ) -> None:
        self.app = app
        self.config = config
        self.ext_files = [Path(p) for p in (ext_files or [])]
        self.ext_dirs = [Path(p) for p in (ext_dirs or [])]
        self._mounted = False
        self._window_pending = False
        # ``--readonly`` startup flag: only the *file* argument is opened
        # read-only (a directory argument keeps its normal behavior).
        self.startup_readonly = readonly
        self._ext_messages: list[str] = [
            f"yaterc: {err}" for err in self.config.errors
        ]

        # ------------------------------------------------------- models/services
        self.session = EditorSession(config, on_closed=self._lsp_documents_closed)
        self.workspace = Workspace()
        # propagate the yaterc show_hidden default to the workspace
        self.workspace.show_hidden = config.show_hidden
        self.explorer_visible = True
        # Language Server Protocol: registered servers come from extensions
        # and the yaterc ``language_servers`` option; the manager is UI
        # independent and safe to keep even with no server.  It is created
        # before the extension API, which wires ``api.lsp`` straight to it.
        self.lsp = LspManager(
            workspace_root=lambda: self.workspace.root,
            on_event=self._on_lsp_event,
        )
        self.keymaps = KeymapSet(
            {"vsc": VscKeymap(), "vim": VimKeymap()},
            keymap if keymap is not None else config.keymap,
        )
        # Empty tables: the built-in action / command modules import the
        # editor, so only the shell may load them (R5/R7 -- see YateApp).
        self.actions = ActionRegistry()
        self.commands = CommandRegistry()
        self.extension_api = ExtensionAPI(self._extension_context())
        self.extension_loader = ExtensionLoader(self.extension_api)
        self.key_ui = KeyUi(
            execute_action=self.execute_action,
            message=self.message,
            command_prompt=self.command_prompt,
            find_prompt=self.find_prompt,
            goto_prompt=self.goto_prompt,
            toggle_keymap=self.toggle_keymap,
        )

        # --------------------------------------------------------------- widgets
        self.prompt_bar = PromptBar(
            self.prompt_completions,
            cancel_hook=self._cancel_prompt,
            focus_editor=self.focus_editor,
            refresh=self.refresh_ui,
        )
        self.tabbar = TabBar(self.session, self.activate_doc, id="tabbar")
        self.breadcrumbs = Breadcrumbs(self.session, self.workspace, id="breadcrumbs")
        self.completion_popup = CompletionPopup()
        self.terminal_panel = TerminalPanel(
            config, self.workspace, self.prompt_bar,
            focus_editor=self.focus_editor, id="terminal-dock",
        )
        self.explorer_tree = ExplorerTree(
            self.session,
            self.workspace,
            self.prompt_bar,
            open_path=self.open_path_later,
            focus_editor=self.focus_editor,
            window_prefix=self.try_window_prefix,
            id="explorer",
        )
        self.status_bar = StatusBar(
            self.session, self.lsp, self.keymaps, self.prompt_bar,
            self.extension_loader, id="statusbar",
        )
        self.sidebar = Vertical(id="sidebar")
        self.sidebar_head = Static(id="sidebar-head")
        self.editor_col = Vertical(id="editor-col")

        # ------------------------------------------------------------ startup
        if target is not None:
            kind = self._open_target(Path(target))
            # A directory argument opens in browse mode (explorer visible);
            # a file argument opens in edit mode (explorer hidden; Ctrl+B /
            # :explorer reveals it later). With no argument the workspace
            # root is None and the explorer stays hidden regardless.
            self.explorer_visible = kind == "dir"
        if not self.session.docs:
            self.session.new_buffer()

        # The pane tree owns editor windows; it starts with one leaf on the
        # startup document and grows with :split / :vsplit.
        self.panes = PaneManager(
            self.session,
            self.session.doc,
            is_mounted=lambda: self.mounted,
            after_pane_focus=self.after_pane_focus,
            focus_explorer=self.focus_explorer,
        )
        self.pane_host = PaneHost(self.panes, self._make_view)
        self.completion = CompletionController(
            app,
            session=self.session,
            lsp=self.lsp,
            workspace=self.workspace,
            keymaps=self.keymaps,
            panes=self.panes,
            popup=self.completion_popup,
            prompt=self.prompt_bar,
            refresh=self.refresh_ui,
        )

    # ================================================================ wiring

    def _extension_context(self) -> ExtensionContext:
        return ExtensionContext(
            session=self.session,
            workspace=self.workspace,
            lsp=self.lsp,
            keymaps=self.keymaps,
            actions=self.actions,
            commands=self.commands,
            message=self.message,
            run_shell=self.run_shell_command,
            open_path=self.open_path_later,
            save=self.save_document,
        )

    def _make_view(self, leaf_id: int) -> EditorView:
        return EditorView(
            leaf_id,
            panes=self.panes,
            session=self.session,
            lsp=self.lsp,
            keymaps=self.keymaps,
            handle_key=self.handle_key,
        )

    def compose(self) -> ComposeResult:
        """The widget tree the application mounts."""
        with Horizontal(id="body"):
            with self.sidebar:
                yield self.sidebar_head
                yield self.explorer_tree
            with self.editor_col:
                yield self.tabbar
                yield self.breadcrumbs
                yield self.pane_host
        # Both live in one docked container so the terminal always sits
        # directly above the status/prompt strip (VS Code layout).
        with Vertical(id="bottom-dock"):
            yield self.terminal_panel
            with Vertical(id="bottom"):
                yield self.status_bar
                yield self.prompt_bar

    async def on_mount(self) -> None:
        """Load services, mount the popup and apply the initial state."""
        self._mounted = True
        self.terminal_panel.styles.height = self.config.terminal_height
        self.terminal_panel.display = False
        self.load_startup_services()
        await self.editor_col.mount(self.completion_popup)
        self.apply_theme()
        self.explorer_tree.refresh_tree()
        self.sync_explorer_visibility()
        view = self.panes.active_view
        if view is not None:
            view.focus()

        if self._ext_messages:
            self.prompt_bar.write("; ".join(self._ext_messages), kind="warn")
        elif self.keymaps.name == "vim":
            self.prompt_bar.idle("-- NORMAL --  (F1 help, : commands)")
        else:
            self.prompt_bar.idle(
                f"yate {__version__} — F1 help, Ctrl+P quick open, "
                "Alt+Shift+P command palette"
            )
        self.refresh_ui()

    async def on_unmount(self) -> None:
        # Each teardown is isolated: a failing terminal/LSP shutdown must not
        # leave the other background service (and its threads) untouched.
        # Extension hooks run first (sync, while editor state is still
        # intact); they release resources the extension owns, e.g. spawned
        # subprocesses or timers. teardown_all isolates per extension.
        self.extension_loader.teardown_all()
        try:
            await self.terminal_panel.view.shutdown()
        except Exception:  # noqa: BLE001 - teardown must reach the LSP manager
            log.exception("terminal panel shutdown failed")
        try:
            await self.lsp.shutdown_all()
        except Exception:  # noqa: BLE001 - last teardown step, nothing to defer to
            log.exception("LSP shutdown failed")

    @property
    def mounted(self) -> bool:
        """True once the widgets exist and the editor is on screen."""
        return self._mounted

    def has_modal_screen(self) -> bool:
        """True while an overlay screen (help, palette, output, ...) owns input."""
        return len(self.app.screen_stack) > 1

    def _report(self, text: str, kind: str = "info") -> None:
        """Report *text* on the message line (buffered before the first mount)."""
        if self.mounted:
            self.message(text, kind)
        else:
            self._ext_messages.append(text)

    def message(self, text: str, kind: str = "info") -> None:
        """Write *text* on the message line and refresh the status chip.

        Dropped before the first mount (nothing is composed yet); callers that
        must not lose a pre-mount message go through :meth:`_report`, which
        buffers them.
        """
        if not self.mounted:
            return
        self.prompt_bar.write(text, kind=kind)
        self.status_bar.refresh_status()

    def refresh_ui(self) -> None:
        """Repaint the editor: views, status bar, chrome and LSP state."""
        if not self.mounted:
            return
        self._refresh_views()
        self._refresh_chrome()
        self._refresh_lsp()

    def _refresh_views(self) -> None:
        """Notify all views that the document content has changed."""
        active = self.panes.active_view
        if active is not None:
            active.content_changed()
        for view in self.panes.all_views():
            if view is not active:
                view.content_changed()

    def _refresh_chrome(self) -> None:
        """Refresh the chrome widgets: status bar, tab bar and breadcrumbs."""
        self.status_bar.refresh_status()
        self.tabbar.refresh_tabs()
        self.breadcrumbs.refresh_crumbs()

    def _refresh_lsp(self) -> None:
        """Push debounced edits and update the LSP echo."""
        self._lsp_doc_shown_later()
        self.lsp.notify_edit(self.session.doc)
        self._update_lsp_echo()

    # ================================================================ target

    def _open_target(self, path: Path) -> str:
        """Open the startup target and return ``"dir"`` or ``"file"``."""
        if not path.exists():
            # treat as a not-yet-created file
            self.workspace.set_root(path.parent if str(path.parent) else Path.cwd())
            self._open_document(path)
            return "file"
        kind = self.workspace.open_target(path)
        if kind == "file":
            self._open_document(path)
        return kind

    def _apply_session_readonly(self, doc: Document | None) -> None:
        """Apply the ``--readonly`` session flag to a freshly opened document.

        Called from the document-open paths so every file opened during the
        session (``:e``, splits, the explorer, ...) starts read-only, not
        just the startup argument.  A no-op without the flag, for a failed
        open (binary files), and for already-open documents being re-activated
        (a user who unlocked one keeps it unlocked).
        """
        if doc is not None and self.startup_readonly:
            doc.buffer.read_only = True
            log.info("opened read-only: %s", doc.path)

    # =============================================================== documents

    def activate_doc(self, doc: Document, target_leaf: Leaf | None = None) -> None:
        """Show *doc* in a pane leaf (default: the active one)."""
        if not self.mounted:
            self.session.activate(doc)
            return
        leaf = target_leaf if target_leaf is not None else self.panes.active
        self.panes.show_doc(leaf, doc)

    def _open_document(
        self, path: Path, *, target_leaf: Leaf | None = None
    ) -> Document | None:
        """Open/reuse *path*; ``None`` when it is not a text file."""
        reused = self.session.is_open(path) is not None
        doc = self.session.open(path)
        if doc is None:
            self._report(f"not a text file: {path.name}", kind="warn")
            log.info("open skipped (binary): %s", path)
            return None
        if not reused:
            self._apply_session_readonly(doc)
        self.activate_doc(doc, target_leaf)
        log.info("opened: %s", path)
        return doc

    async def _open_document_async(
        self, path: Path, *, target_leaf: Leaf | None = None
    ) -> Document | None:
        """Like :meth:`_open_document`, but the disk read runs off the loop."""
        reused = self.session.is_open(path) is not None
        doc = await self.session.open_async(path)
        if doc is None:
            self._report(f"not a text file: {path.name}", kind="warn")
            return None
        if not reused:
            self._apply_session_readonly(doc)
        self.activate_doc(doc, target_leaf)
        log.info("opened (async): %s", path)
        return doc

    def open_document(self, path: Path) -> Document | None:
        """Open/reuse *path* in the active pane (explorer create flow)."""
        return self._open_document(path)

    def open_path(self, path: Path) -> None:
        """Open a file or switch the workspace to a directory (sync)."""
        try:
            if path.is_dir():
                log.info("opened folder: %s", path)
                self.workspace.set_root(path)
                self.explorer_tree.refresh_tree()
                self.explorer_visible = True
                self.sync_explorer_visibility()
                # focus the tree so keyboard nav works immediately
                self.explorer_tree.focus()
                self.message(f"opened folder {path}")
                return
        except OSError:
            pass
        if self._open_document(path) is None:
            return
        self.explorer_tree.refresh_tree()
        self.session.reset_search()
        self.close_completion()
        self.message(f"opened {self.session.doc.name}")
        self.refresh_ui()

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
        if await self._open_document_async(path) is None:
            return
        if not self.mounted:
            return
        self.explorer_tree.refresh_tree()
        self.session.reset_search()
        self.close_completion()
        self.message(f"opened {self.session.doc.name}")
        self.refresh_ui()

    def open_path_later(self, path: Path) -> None:
        """Schedule a non-blocking file open from a synchronous handler."""
        self.app.run_worker(
            partial(self.open_path_async, path),
            group="open", exclusive=True, exit_on_error=False,
        )

    def new_buffer(self, show: bool = True) -> None:
        """``:enew`` / new tab: append an empty buffer and make it active.

        ``show=False`` is for internal replacements (the startup seed, the
        fallback after closing the last tab): they must not dismiss the
        welcome page or print a message.
        """
        doc = self.session.new_buffer()
        if self.mounted:
            self.panes.show_doc(self.panes.active, doc)
        self.session.reset_search()
        self.close_completion()
        if show:
            # A user-requested buffer (:enew / new tab) dismisses the
            # one-time welcome page for the rest of the session. Internal
            # replacements (startup seed, close-last-tab fallback) pass
            # show=False and leave the flag untouched.
            self.session.welcome_visible = False
            self.message("new buffer")
        self.refresh_ui()

    def show_welcome(self) -> None:
        """Re-enable the welcome page (``:welcome``)."""
        self.session.welcome_visible = True
        self.refresh_ui()
        self.message("welcome page enabled")

    def close_tab(self) -> None:
        """``:bd``: close the active tab (LSP didClose is reported)."""
        if not self.session.docs:
            return
        closed, fallback = self.session.close_active()
        log.info("closing tab: %s", closed.path)
        if self.mounted:
            # Every pane showing the closed document rebinds to the fallback;
            # other panes keep their documents and independent view states.
            self.panes.document_closed(closed, fallback)
        self.session.reset_search()
        self.close_completion()
        self.message("closed tab")
        self.refresh_ui()

    def cycle_tab(self, delta: int) -> None:
        """``:bn`` / ``:bp``: activate the next/previous tab.

        With a single tab this is a silent no-op: cycling cannot move
        anywhere, so repeating the command must not spam the message
        line.
        """
        if len(self.session.docs) <= 1:
            return
        self.session.cycle(delta)
        if self.mounted:
            self.panes.show_doc(self.panes.active, self.session.doc)
        # The previous tab's matches are (row, start, end) spans of *its*
        # buffer: keeping them would paint stale highlights on the new
        # document and send ``n`` to out-of-range coordinates.
        self.session.reset_search()
        self.close_completion()
        self.refresh_ui()

    def save_document(self) -> None:
        """``:w``: write the active document to disk."""
        doc = self.session.doc
        if doc.buffer.read_only:
            self.message(
                "cannot save a read-only buffer; use :saveas to write elsewhere",
                kind="warn",
            )
            return
        if doc.path is None:
            log.info("save: unnamed buffer, prompting for a path")
            self.prompt_save_as()
            return
        try:
            doc.save()
            self.explorer_tree.refresh_tree()
            self.app.run_worker(
                partial(self.lsp.notify_saved, doc),
                group="lsp-sync", exclusive=False, exit_on_error=False,
            )
            self.message(f"saved {doc.path}", kind="ok")
            log.info("saved: %s", doc.path)
        except (OSError, UnicodeError) as exc:
            self.message(f"save failed: {exc}", kind="error")
            log.warning("save failed: %s: %s", doc.path, exc)
        self.refresh_ui()

    def prompt_save_as(self) -> None:
        """Prompt for the path of an unnamed buffer."""
        current = str(self.session.doc.path) if self.session.doc.path else ""
        self.prompt_bar.activate(
            "save", initial=current, on_submit=self._submit_save_as
        )

    def save_as(self, path: str | None = None) -> None:
        """``:saveas``: persist the buffer to *path* (prompt without one).

        The sanctioned escape hatch for a read-only buffer: writing to an
        explicitly chosen path lifts the flag (vim ``:sav`` semantics) while
        the original file stays untouched.
        """
        if path is not None and path.strip():
            self._submit_save_as(path)
            return
        self.prompt_save_as()

    def _submit_save_as(self, text: str) -> None:
        text = text.strip()
        if not text:
            self.message("save cancelled")
            return
        buf = self.session.doc.buffer
        locked = buf.read_only
        if locked:
            # ``:saveas`` is deliberate persistence: lift the flag so the
            # L0 ``Document.save`` guard lets the write through (vim ``:sav``
            # clears 'readonly' too).  Restored when the write fails.
            buf.read_only = False
        path = Path(text)
        try:
            self.session.doc.save(path)
            self.workspace.set_root(path.parent)
            self.explorer_tree.refresh_tree()
            self.message(f"saved {path}", kind="ok")
        except (OSError, UnicodeError) as exc:
            if locked:
                buf.read_only = True
            self.message(f"save failed: {exc}", kind="error")

    # ============================================================== key routing

    def handle_key(self, event: Key) -> bool:
        """Dispatch one key event; returns ``True`` when it was consumed.

        Called both by the editor view (keys typed in a pane) and by the
        application shell (keys that bubble up from other widgets).  The
        dispatch is not side-effect free: :meth:`try_window_prefix` arms
        and clears the ``ctrl+w`` pending chord (``_window_pending``) and
        the completion-popup branch commits the highlighted candidate
        (``accept_completion``).  A ``True`` return means the caller must
        stop the event (R10) instead of letting it bubble into a second
        dispatch.
        """
        if self.has_modal_screen():
            return False  # a modal screen owns input
        editor_focused = isinstance(self.app.focused, EditorView)
        # Ctrl+Space = manual completion. Checked BEFORE the terminal toggle:
        # on Windows conhost / legacy xterm Ctrl+Space and Ctrl+` share the
        # NUL byte (named "ctrl+@"), so there the NUL byte favors completion;
        # Ctrl+` still closes the terminal while it is focused, and :term /
        # the palette opens it.
        if event.key in ("ctrl+space", "ctrl+@"):
            if editor_focused or event.key == "ctrl+space":
                self.request_completion(manual=True)
                return True
        if event.key in TOGGLE_KEYS and event.key != "ctrl+@":
            self.terminal_panel.toggle()
            return True
        # The completion popup owns a handful of keys while it is open; it
        # never takes focus itself, so the keys arrive here.  Every other key
        # falls through to the normal dispatch below: typing keeps filtering
        # the candidates (``handle_raw_key`` ends in
        # ``completion.after_editor_key``, which re-queries) and the global
        # chords stay usable while the popup is up.
        popup = self.completion_popup
        if popup.is_open:
            if event.key in ("tab", "enter"):
                self.accept_completion()
                return True
            if event.key == "up":
                popup.select_prev()
                return True
            if event.key == "down":
                popup.select_next()
                return True
            if event.key == "escape":
                popup.close()
                return True
        # vim ctrl+w window chord (armed or pending); before the other
        # chords so the prefix is consumed wherever focus currently is
        if self.try_window_prefix(event):
            return True
        # Global chords that raw byte dispatch cannot represent reliably.
        # alt+shift+p is the default: Windows Terminal reserves ctrl+shift+p
        # for its own command palette, and ctrl+shift+a clashes with other
        # terminal emulators; alt+shift+p is unbound in both.
        if event.key == "alt+shift+p":
            self.open_command_palette()
            return True
        if self.prompt_bar.active_mode:
            # command line is editing; enter must bubble so the Input's own
            # enter->submit binding can fire
            return False
        # vscode-style pane focus chords (CSI-u encodings, not in the raw
        # byte table)
        if event.key == "ctrl+shift+e":
            self.focus_explorer()
            return True
        if event.key == "ctrl+1":
            self.focus_editor()
            return True
        if event.key == "ctrl+p":
            self.open_file_palette()
            return True
        if self.app.focused is self.explorer_tree:
            return False  # explorer consumes its own keys
        raw = event_to_raw(event.key, event.character)
        if raw is None:
            return False
        return self.handle_raw_key(raw)

    def handle_raw_key(self, raw: str) -> bool:
        """Dispatch one raw key to the active keymap, then refresh the UI."""
        try:
            handled = self.keymaps.active.handle_key(
                ActionContext(self.session, self.key_ui), raw
            )
        except BufferReadOnlyError:
            # Typing / vim operators / edit actions on a read-only buffer:
            # the key is consumed (R10) with a notice instead of an edit.
            self._readonly_notice()
            return True
        self.refresh_ui()
        self.completion.after_editor_key(raw)
        return handled

    def execute_action(self, name: str) -> bool:
        """Run a registered action by name; ``False`` when it is unknown.

        Called by keymaps (which report an unknown name and let the key fall
        through), the palette and the extension bridge.  A refused edit on a
        read-only buffer also reports ``True`` (the request was consumed,
        with a user notice) instead of propagating the error.
        """
        try:
            return self.actions.execute(name, ActionContext(self.session, self.key_ui))
        except BufferReadOnlyError:
            self._readonly_notice()
            # the refused action may have moved the cursor / changed anchors
            # before raising; repaint so the view never goes stale
            self.refresh_ui()
            return True

    def _readonly_notice(self) -> None:
        """User feedback for an edit refused on a read-only buffer."""
        self.message(
            "buffer is read-only (:set readonly=false to unlock)", kind="warn"
        )

    def insert_char(self, ch: str) -> None:
        """Insert one character at the cursor (keymap ``insert_char``)."""
        self.session.buffer.insert_text(ch)

    # ================================================================== panes

    def split_with_path(self, axis: Axis, args: str) -> None:
        """``:sp`` / ``:vs``: split a pane, optionally opening *args*."""
        text = args.strip()
        if not text:
            self._split_pane(axis)
            return
        path = Path(text).expanduser()
        if not path.is_absolute():
            # vim resolves :sp/:vs relative paths against the current file's
            # directory (falling back to cwd for unnamed buffers)
            doc = self.session.doc
            base = doc.path.parent if doc.path else Path.cwd()
            path = base / path
        try:
            is_dir = path.is_dir()
        except OSError:
            is_dir = False
        if is_dir:
            self.open_path(path)
            return
        self.app.run_worker(
            partial(self._split_pane_worker, axis, path),
            group="pane", exclusive=True, exit_on_error=False,
        )

    def _split_pane(self, axis: Axis) -> None:
        self.app.run_worker(
            partial(self._split_pane_worker, axis, None),
            group="pane", exclusive=True, exit_on_error=False,
        )

    async def _split_pane_worker(self, axis: Axis, path: Path | None) -> None:
        if path is not None:
            # split first (the new pane becomes active), then open the file
            # into the active pane
            await self.panes.split_active(axis)
            await self.open_path_async(path)
        else:
            await self.panes.split_active(axis)
            self.after_pane_focus()

    def only_pane(self) -> None:
        """``:only``: keep the active pane, close the others."""
        self.app.run_worker(
            # coroutine *functions* (partial), never built coroutines: an
            # eager coroutine leaks when the worker never starts
            partial(self.panes.only_active),
            group="pane", exclusive=True, exit_on_error=False,
        )

    def close_pane(self) -> None:
        """``ctrl+w q``: close the active pane (documents stay open)."""
        if self.panes.leaf_count <= 1:
            self.message("only one pane open (use :q to quit)", kind="warn")
            return
        self.app.run_worker(
            partial(self.panes.close_active),
            group="pane", exclusive=True, exit_on_error=False,
        )

    def resize_pane(self, key: str) -> None:
        """``ctrl+w + - < > =``: resize the panes around the active one."""
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

    def try_window_prefix(self, event: Key) -> bool:
        """Handle the vim ``ctrl+w`` window chord; True when consumed.

        Called from the editor view *before* keymap dispatch (the vim
        keymap swallows unmapped keys, so the shell would never see them)
        and from :meth:`handle_key` for the other focused widgets.
        """
        if self.has_modal_screen():
            return False
        if self.prompt_bar.active_mode:
            return False
        if self._window_pending:
            self._window_pending = False
            if event.key in _WINDOW_KEYS:
                self._window_command(event.key)
                return True
            return False  # any other key cancels and is processed normally
        if self.keymaps.name == "vim" and event.key == "ctrl+w":
            vim = self.keymaps.get("vim")
            if isinstance(vim, VimKeymap) and vim.mode is VimMode.NORMAL:
                self._window_pending = True
                self.message(
                    "ctrl+w-  (s/:split v/:vsplit q close o :only  "
                    "h j k l move, ctrl+w cycle  + - < > = resize)"
                )
                return True
        return False

    def _window_command(self, key: str) -> None:
        """Execute the second key of a vim ``ctrl+w`` window chord."""
        if key == "ctrl+w":  # round-robin: explorer <-> every editor pane
            self.panes.cycle_focus(
                explorer_focused=self.app.focused is self.explorer_tree
            )
            return
        if self.app.focused is self.explorer_tree:
            # The explorer plays the left-neighbour pane: only ctrl+w l/j/k
            # returns to an editor pane from it.
            if key in ("l", "j", "k"):
                self.focus_editor()
            return
        if key == "h":
            if not self.panes.focus_direction("h"):
                self.focus_explorer()
        elif key in ("j", "k", "l"):
            self.panes.focus_direction(key)
        elif key == "s":
            self._split_pane("horizontal")
        elif key == "v":
            self._split_pane("vertical")
        elif key == "q":
            self.close_pane()
        elif key == "o":
            self.only_pane()
        else:  # + - < > = (canonical and raw symbol names)
            self.resize_pane(key)

    # ================================================================== focus

    def focus_explorer(self) -> None:
        """Reveal and focus the explorer (``esc``/``ctrl+shift+e``)."""
        if self.workspace.root is None:
            self.message("no folder is open — use :e <path>", kind="warn")
            return
        if not self.explorer_visible:
            self.toggle_explorer()
        self.explorer_tree.focus()
        self.message(
            "explorer: j/k move, l open, h fold, a new file, "
            "A new folder, r rename, d delete, esc back"
        )

    def focus_editor(self) -> None:
        """Focus the active pane."""
        view = self.panes.active_view
        if view is not None:
            view.focus()

    def after_pane_focus(self) -> None:
        """Editor-level sync after the active pane changed."""
        self.close_completion()
        self.refresh_ui()

    # =============================================================== prompts

    def _cancel_prompt(self) -> None:
        """Prompt cancelled (esc): clear live search highlights."""
        if self.session.search.query:
            self.session.search.update("", self.session.buffer)

    def prompt_open(self) -> None:
        """``:e`` (no argument): ask for a path."""
        self.prompt_bar.activate(
            "open",
            placeholder="path to a file or directory",
            on_submit=self._submit_open,
        )

    def _submit_open(self, text: str) -> None:
        text = text.strip()
        if text:
            self.open_path_later(Path(text))

    def command_prompt(self) -> None:
        """Open the ex command line (``:``)."""
        self.prompt_bar.activate(
            "command",
            placeholder="type a command, :help for list",
            on_submit=self.run_command,
        )

    def shell_prompt(self) -> None:
        """Open the shell prompt (``:!`` / F2)."""
        self.prompt_bar.activate(
            "shell",
            placeholder="shell command",
            on_submit=lambda text: self.run_shell_command_later(text),
        )

    def find_prompt(self, forward: bool) -> None:
        """Open the search prompt (``/``, ``?``, ctrl+f)."""
        self.prompt_bar.activate(
            "find" if forward else "find_back",
            initial=self.session.search.query,
            placeholder="search pattern (enter to jump, esc to cancel)",
            on_submit=lambda text: self._submit_search(text, forward),
            on_changed=self._live_search,
        )

    def _live_search(self, text: str) -> None:
        """Highlight matches while the search prompt is being typed."""
        self.session.search.update(text, self.session.buffer)
        for view in self.panes.views_for(self.session.doc):
            view.refresh()

    def _submit_search(self, text: str, forward: bool) -> None:
        if not text:
            return
        self.find_next(forward)

    def find_next(self, forward: bool) -> None:
        """``n``/``N``: jump to the next / previous match."""
        search = self.session.search
        if not search.query:
            self.message("no active search — press / to start one", kind="warn")
            return
        match = search.next(self.session.buffer, forward=forward)
        if match is None:
            self.message(f"no matches for {search.query!r}", kind="warn")
        else:
            self.message(
                f"[{search.index + 1}/{len(search.matches)}] {search.query!r}"
            )

    def replace_prompt(self) -> None:
        """``:s`` style replace: ask for the search text."""
        self.prompt_bar.activate(
            "replace_find",
            placeholder="text to find",
            on_submit=self._replace_find_step,
        )

    def _replace_find_step(self, find: str) -> None:
        find = find.strip()
        if not find:
            self.message("replace cancelled")
            return
        self.prompt_bar.activate(
            "replace_with",
            placeholder="replacement text",
            on_submit=lambda replacement: self._do_replace(find, replacement),
        )

    def _do_replace(self, find: str, replacement: str) -> None:
        if self.session.buffer.read_only:
            self._readonly_notice()
            return
        matches = self.session.search.update(find, self.session.buffer)
        if not matches:
            self.message(f"no matches for {find!r}", kind="warn")
            return
        count = self.session.search.replace_all(self.session.buffer, replacement)
        self.message(f"replaced {count} occurrence(s) of {find!r}", kind="ok")

    def goto_prompt(self) -> None:
        """Open the command line in go-to-line mode (Ctrl+G)."""
        line_count = self.session.buffer.line_count
        self.prompt_bar.activate(
            "goto",
            placeholder=f"line number (1-{line_count})",
            on_submit=self.goto_line_command,
        )

    def goto_line_command(self, text: str) -> None:
        """Jump to an absolute (``42``) or signed-relative (``+5``) line."""
        text = text.strip()
        if not re.fullmatch(r"[+-]?\d+", text):
            self.message(f"not a line number: {text!r}", kind="warn")
            return
        value = int(text)
        buf = self.session.buffer
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
        buf = self.session.buffer
        row = max(0, min(line - 1, buf.line_count - 1))
        col = min(buf.col, len(buf.lines[row]))
        buf.anchor = None
        buf.set_cursor((row, col))
        self.session.search.update("", buf)
        view = self.panes.active_view
        if view is not None:
            view.scroll_col = 0
            view.reveal_cursor()
        self.message(f"line {row + 1} of {buf.line_count}")
        self.refresh_ui()

    def page(self, direction: int, half: bool = False) -> None:
        """Scroll the active view by (half) a page."""
        view = self.panes.active_view
        if view is None:
            return
        rows = view.page_delta(half) * direction
        buf = self.session.buffer
        target = max(0, min(buf.row + rows, buf.line_count - 1))
        buf.cursor = (target, min(buf.col, len(buf.lines[target])))

    # ----------------------------------------------------- prompt completion

    def prompt_completions(self, text: str, mode: str) -> list[str]:
        """Tab-completion candidates for the bottom prompt."""
        return prompt_completions(
            text,
            mode,
            commands=self.commands,
            session=self.session,
            workspace=self.workspace,
        )

    # ================================================================ keymap

    def select_keymap(self, name: str) -> None:
        """Switch the active key map by name (``vsc`` / ``vim``)."""
        if not self.keymaps.select(name):
            self.message(f"unknown keymap: {name} (vsc|vim)", kind="error")
            return
        self.message(f"keymap: {self.keymaps.active.label}", kind="ok")
        self.refresh_ui()

    def toggle_keymap(self) -> None:
        """Flip between the vsc and vim key maps."""
        self.select_keymap(self.keymaps.toggle())

    def mode_label(self) -> tuple[str, str]:
        """``(label, background color)`` for the status bar mode chip.

        Delegated to the status bar's pure helper so the widget and the
        smoke scripts share a single implementation.
        """
        return mode_chip(self.prompt_bar, self.keymaps)

    # ================================================================= theme

    def theme_label(self) -> str:
        """Current theme as ``label (name)`` for the ``:theme`` message."""
        current = theme.active()
        return f"{current.label} ({current.name})"

    def theme_names(self) -> list[str]:
        """Every registered theme name (``:theme`` listing)."""
        return list(theme.available())

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
        # Lazily ensure the Textual bridge exists (an extension may have
        # registered a yate theme after startup); register_theme is
        # idempotent when the name already exists.
        textual_name = theme.textual_theme_name(name)
        if self.app.get_theme(textual_name) is None:
            try:
                self.app.register_theme(theme.to_textual_theme(selected))
            except Exception as exc:  # noqa: BLE001 - report, never fatal
                self.message(
                    f"theme bridge for {name!r} failed: {exc}", kind="error"
                )
                return
        # The reactive watcher regenerates tokens and repaints every overlay.
        self.app.theme = textual_name
        self.apply_theme()
        self.message(f"theme: {selected.label}", kind="ok")

    def apply_theme(self) -> None:
        """Push the active theme onto every widget and force a repaint."""
        if not self.mounted:
            return
        t = theme.active()
        self.app.screen.styles.background = t.bg
        for view in self.panes.all_views():
            view.styles.background = t.bg
            view.apply_scrollbar_theme()
            view.content_changed()
        tree = self.explorer_tree
        tree.styles.scrollbar_background = t.border
        tree.styles.scrollbar_background_hover = t.surface
        tree.styles.scrollbar_color = t.fg_dim
        tree.styles.scrollbar_color_hover = t.fg_muted
        tree.styles.scrollbar_color_active = t.accent
        tree.refresh_tree()
        self.status_bar.refresh_status()
        self.prompt_bar.styles.background = t.panel
        self.prompt_bar.refresh()
        self.update_sidebar_head()
        self.tabbar.refresh_tabs()
        self.breadcrumbs.refresh_crumbs()

    def update_sidebar_head(self) -> None:
        """Paint the VS Code-style 'EXPLORER' sidebar title."""
        self.sidebar_head.styles.background = theme.active().panel
        self.sidebar_head.update(sidebar_head_text())

    def set_readonly(self, value: bool) -> None:
        """Set the active buffer's read-only flag (``:set readonly=``)."""
        buf = self.session.doc.buffer
        buf.read_only = value
        self.message(f"readonly: {'on' if value else 'off'}", kind="ok")
        self.refresh_ui()

    def set_filetype(self, value: str) -> None:
        """Force the current document's syntax type (``:set filetype=``)."""
        doc = self.session.doc
        raw = value.strip().lower().lstrip(".")
        if not raw or raw == "auto":
            doc.filetype_override = None
            self.message(
                f"filetype reset to {doc.filetype} (auto from path)", kind="ok"
            )
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
        self.app.run_worker(
            partial(self.lsp.on_document_closed, doc),
            group="lsp-sync", exclusive=False, exit_on_error=False,
        )
        self.refresh_ui()

    # ================================================================= shell

    def run_shell_command(
        self, command: str, show_output: bool = True
    ) -> ShellResult | None:
        """Run a shell command synchronously and capture its output.

        Blocking: used by the (synchronous) extension API.  Interactive
        callers go through :meth:`run_shell_command_later` so the TUI stays
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
        if self.prompt_bar.active_mode in ("shell", "command"):
            self.prompt_bar.idle()
            self.focus_editor()
            self.refresh_ui()
        self.app.run_worker(
            partial(self.run_shell_command_async, command),
            group="shell", exclusive=False, exit_on_error=False,
        )

    async def run_shell_command_async(
        self, command: str, show_output: bool = True
    ) -> ShellResult | None:
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
        doc = self.session.doc
        return (
            self.workspace.root
            or (doc.path.parent if doc.path is not None else None)
            or Path.cwd()
        )

    def _show_shell_result(
        self, command: str, result: ShellResult, cwd: Path
    ) -> None:
        body = (
            f"(cwd: {cwd} · {shell_name()})\n\n"
            f"{result.output or '(no output)'}"
        )
        self.push_overlay(OutputScreen(f"$ {command}", body, result.returncode))

    def run_command(self, text: str) -> None:
        """``:`` command line: dispatch one ex command."""
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

    def install_font(self) -> None:
        """``:font``: install the bundled Nerd Font (off the event loop)."""
        # registry lookups / font registration touch subprocess and would
        # freeze the TUI on some systems; run off the event loop
        self.message("checking Nerd Font…", kind="info")
        self.app.run_worker(
            self._font_command_async, group="font",
            exclusive=True, exit_on_error=False,
        )

    async def _font_command_async(self) -> None:
        status = await asyncio.to_thread(fonts.ensure_font)
        if self.mounted:
            self.message(
                status.detail or ("Nerd Font ready" if status.has_nerd_font
                                  else "font setup failed"),
                kind="ok" if status.has_nerd_font else "error",
            )

    def quit(self, force: bool = False) -> None:
        """``:q``: leave yate (blocked while a buffer is modified)."""
        if not force and any(doc.modified for doc in self.session.docs):
            self.message("unsaved changes — :q! to quit anyway", kind="warn")
            log.info("quit blocked: unsaved changes")
            return
        log.info("quit (force=%s)", force)
        if self.mounted:
            self.app.exit()

    # ============================================================= completion

    def close_completion(self) -> None:
        """Dismiss the completion popup if it is open."""
        self.completion.close()

    def request_completion(
        self, manual: bool = True, trigger_ch: str | None = None
    ) -> None:
        """Fetch completions and show the popup (worker; never blocks input)."""
        self.completion.request(manual, trigger_ch)

    def accept_completion(self) -> None:
        """Insert the selected completion at its reported range."""
        try:
            self.completion.accept()
        except BufferReadOnlyError:
            self._readonly_notice()
            self.refresh_ui()

    # =================================================================== lsp

    def _lsp_documents_closed(self, closed: list[Document]) -> None:
        """Session hook: tell the servers the documents were closed.

        Hand the worker the *bound coroutine function*, never the coroutine:
        an eagerly built coroutine lives outside the worker's lifecycle, so a
        worker that never starts (quit cancels the "lsp-sync" group) drops
        the didClose and leaks "coroutine was never awaited".
        """
        for doc in closed:
            self.app.run_worker(
                partial(self.lsp.on_document_closed, doc),
                group="lsp-sync", exclusive=False, exit_on_error=False,
            )

    def _lsp_doc_shown_later(self) -> None:
        """Open the active document on its server once a server is registered."""
        doc = self.session.doc
        if not self.lsp.supports(doc) or self.lsp.is_open(doc):
            return
        self.app.run_worker(
            partial(self.lsp.on_document_shown, doc),
            group="lsp-sync", exclusive=False, exit_on_error=False,
        )

    def _on_lsp_event(self, event: str) -> None:
        """Manager callback (event loop thread): repaint after LSP updates."""
        if not self.mounted:
            return
        for view in self.panes.all_views():
            view.refresh()
        self.status_bar.refresh_status()
        if event == "diagnostics":
            self._update_lsp_echo()

    def _update_lsp_echo(self) -> None:
        """Show the diagnostic under the cursor on the message line."""
        prompt = self.prompt_bar
        if prompt.active_mode is not None:
            return
        buf = self.session.buffer
        diag = self.lsp.diagnostic_at(self.session.doc, buf.row, buf.col)
        if diag is not None:
            glyph = "✖" if diag.is_error else ("▲" if diag.is_warning else "●")
            source = f"{diag.source}: " if diag.source else ""
            prompt.write(
                f"{glyph} {source}{diag.message}",
                kind="error" if diag.is_error else "warn",
                owner="lsp",
            )
        elif prompt.owner == "lsp":
            prompt.idle()

    def show_diagnostics(self) -> None:
        """``:diagnostics`` -- list the active document's LSP diagnostics."""
        doc = self.session.doc
        diags = self.lsp.diagnostics_for(doc)
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
        errors, warnings = self.lsp.counts_for(doc)
        title = f"diagnostics — {errors} error(s), {warnings} warning(s)"
        self.push_overlay(OutputScreen(title, "\n".join(lines), 0))

    # =============================================================== overlays

    def push_overlay(
        self,
        screen: Screen[Any],
        callback: Callable[[Any], None] | None = None,
    ) -> None:
        """Push a full-screen overlay, clearing the stale bottom message first.

        The prompt/message line is hidden behind the overlay while it is up,
        so reset it to the idle hint now; otherwise the previous command's
        message (e.g. "saved …") would reappear, untouched, once the overlay
        closes -- looking like the overlay command itself had no feedback.
        """
        self.prompt_bar.idle()
        self.app.push_screen(screen, callback=callback)

    def show_help(self) -> None:
        """Open the keybinding reference overlay."""
        if self.mounted:
            self.push_overlay(HelpScreen(self.keymaps, self.commands))

    def show_manual(self, lang: str = "en") -> None:
        """Open the bundled user manual, rendered as read-only markdown."""
        self._open_doc(kind="manual", lang=lang, title="user manual")

    def show_changelog(self, lang: str = "en") -> None:
        """Open the bundled bilingual changelog viewer."""
        self._open_doc(kind="changelog", lang=lang, title="changelog")

    def _open_doc(self, *, kind: str, lang: str, title: str) -> None:
        if not self.mounted or isinstance(self.app.screen, MarkdownDocScreen):
            return
        self.push_overlay(MarkdownDocScreen(kind=kind, lang=lang, title=title))

    def open_file_palette(self) -> None:
        """Quick file open: fuzzy palette over the workspace files (ctrl+p)."""
        if self.mounted:
            self.push_overlay(self._palette("files"))

    def open_command_palette(self) -> None:
        """Command palette: fuzzy search over commands (alt+shift+p)."""
        if self.mounted:
            self.push_overlay(self._palette("commands"))

    def _palette(self, mode: str) -> PaletteScreen:
        return PaletteScreen(
            mode,
            workspace=self.workspace,
            commands=self.commands,
            actions=self.actions,
            open_path=self.open_path_later,
            focus_editor=self.focus_editor,
            execute_action=self.execute_action,
            run_command=self.run_command,
            refresh=self.refresh_ui,
        )

    # ============================================================== explorer

    def refresh_explorer(self) -> None:
        """Rebuild the explorer tree (after create / rename / delete)."""
        self.explorer_tree.refresh_tree()

    def set_show_hidden(self, flag: bool) -> None:
        """Show/hide dotfiles in the explorer and refresh the tree."""
        self.workspace.show_hidden = flag
        self.refresh_explorer()

    def toggle_explorer(self) -> None:
        """``:explorer`` / ctrl+b: show or hide the sidebar."""
        self.explorer_visible = not self.explorer_visible
        self.sync_explorer_visibility()
        if self.explorer_visible and self.workspace.root is not None:
            # focus the tree so keyboard nav works immediately on show;
            # defer until after the next layout pass -- a freshly shown
            # widget still has a 0x0 region and Textual refuses focus
            self.explorer_tree.call_after_refresh(self.explorer_tree.focus)
            self.message("explorer: j/k move, l open, h fold, a new file, "
                         "A new folder, r rename, d delete, H toggle hidden, esc back")
        else:
            self.message(f"explorer {'shown' if self.explorer_visible else 'hidden'}")

    def sync_explorer_visibility(self) -> None:
        """Apply the explorer visibility to the sidebar widgets."""
        visible = self.explorer_visible and self.workspace.root is not None
        self.explorer_tree.display = visible
        self.sidebar.display = visible

    # ============================================================ extensions

    def load_startup_services(self) -> None:
        """Load extensions and register the yaterc-declared LSP servers.

        Headless safe: shared by ``on_mount`` and ``yate --diag`` so the
        diagnostics always show exactly what a real start would load.  No
        LSP process is spawned here (servers start lazily).
        """
        self._ext_messages.extend(
            load_startup_extensions(
                self.extension_loader,
                self.config,
                ext_dirs=self.ext_dirs,
                ext_files=self.ext_files,
            )
        )
        self._register_configured_servers()

    def trust_cwd_extensions(self) -> None:
        """Trust the current workspace and load its ``./extensions`` now.

        The explicit confirmation step of workspace trust: startup skips
        an untrusted project ``./extensions`` (opening a repository must
        not execute that repository's own code), and ``:trust`` both
        records the workspace in ``~/.yate/trusted_workspaces`` and loads
        the directory immediately.  Re-running is safe -- the loader
        de-duplicates by resolved path, so already-loaded scripts are
        skipped and only genuinely new ones run.
        """
        cwd = Path.cwd()
        if not trust_workspace(cwd):
            # S39 minimal hardening: a symlinked cwd is refused by the
            # store, and pretending otherwise (or still loading its
            # extensions) would defeat the guard.
            self.message(
                f"refused to trust {cwd}: it contains a symlink component; "
                "trust the resolved directory instead",
                kind="error",
            )
            return
        directory = cwd / "extensions"
        if not directory.is_dir():
            self.message(f"trusted {cwd}; no extensions directory to load")
            return
        records = self.extension_loader.load_directory(directory)
        failures = [record for record in records if record.error]
        loaded = len(records) - len(failures)
        self.message(
            f"trusted {cwd}; loaded {loaded} extension(s) from {directory}"
        )
        for record in failures:
            self.message(f"extension {record.name}: {record.error}",
                         kind="error")

    def _register_configured_servers(self) -> None:
        """Register LSP servers declared by the yaterc ``language_servers``.

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



