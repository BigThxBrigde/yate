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

import re
from functools import partial
from pathlib import Path
from typing import Any

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.events import Key
from textual.screen import Screen

from yate import __version__
from yate.completion import CompletionFlows
from yate.config import YateConfig
from yate.document_flows import DocumentFlows
from yate.editor_core import BufferReadOnlyError
from yate.editor_lsp import LspManager
from yate.editor_syntax import available_filetypes, language_name, resolve_filetype
from yate.editor_view import theme
from yate.editor_view.chrome import Breadcrumbs, SidebarHead, TabBar
from yate.editor_view.commandline import PromptBar
from yate.editor_view.completion import CompletionPopup
from yate.editor_view.editor import EditorView
from yate.editor_view.explorer import ExplorerTree
from yate.editor_view.panes import PaneHost, PaneManager
from yate.editor_view.statusbar import StatusBar, mode_chip
from yate.editor_view.terminal import TOGGLE_KEYS, TerminalPanel
from yate.extension_flows import ExtensionFlows
from yate.keymaps.base import ActionContext, KeyUi
from yate.keymaps.registry import KeymapSet
from yate.keymaps.vsc import VscKeymap
from yate.keymaps.vim import VimKeymap
from yate.keyproto.legacy import event_to_raw
from yate.logs import tracing
from yate.lsp_sync import LspSync
from yate.overlays import OverlayFlows
from yate.prompt_completion import prompt_completions
from yate.prompt_flows import PromptFlows
from yate.registries import ActionRegistry, CommandRegistry
from yate.services.extensions import ExtensionAPI, ExtensionContext, ExtensionLoader
from yate.services.workspace import Workspace
from yate.session import EditorSession
from yate.shell_flows import ShellFlows
from yate.window_flows import WindowFlows

#: Trace logger ("yate.editor"); silent unless yate_trace is on.
log = tracing.get_logger(__name__)


# ------------------------------------------------------------------- assembly

def _build_models(ed: Editor, keymap: str | None) -> None:
    """Create the models and services the editor operations work on.

    Module-level factory (review 20260926 #5): keeps :meth:`Editor.__init__`
    a readable sequence of build steps.  Callbacks are bound methods of the
    not-yet-fully-initialized *ed*; they only fire after construction, so
    the half-built state is never observed.
    """
    ed.session = EditorSession(
        ed.config, on_closed=lambda docs: ed.lsp_sync.documents_closed(docs)
    )
    ed.workspace = Workspace()
    # propagate the yaterc show_hidden default to the workspace
    ed.workspace.show_hidden = ed.config.show_hidden
    ed.explorer_visible = True
    # Language Server Protocol: registered servers come from extensions
    # and the yaterc ``language_servers`` option; the manager is UI
    # independent and safe to keep even with no server.  It is created
    # before the extension API, which wires ``api.lsp`` straight to it.
    # The event callback defers through lsp_sync, which is built with the
    # pane stack (it needs the widgets); both callbacks only fire later.
    ed.lsp = LspManager(
        workspace_root=lambda: ed.workspace.root,
        on_event=lambda event: ed.lsp_sync.on_event(event),
    )
    ed.keymaps = KeymapSet(
        {"vsc": VscKeymap(), "vim": VimKeymap()},
        keymap if keymap is not None else ed.config.keymap,
    )
    # Empty tables: the built-in action / command modules import the
    # editor, so only the shell may load them (R5/R7 -- see YateApp).
    ed.actions = ActionRegistry()
    ed.commands = CommandRegistry()
    ed.extension_api = ExtensionAPI(ed.extension_context())
    ed.extension_loader = ExtensionLoader(ed.extension_api)
    ed.extension_flows = ExtensionFlows(
        ed.extension_loader,
        ed.extension_api,
        ed.config,
        ed.ext_dirs,
        ed.ext_files,
        message=ed.message,
    )


def _build_widgets(ed: Editor) -> None:
    """Create the widget tree members and keep the references ops need."""
    ed.prompt_bar = PromptBar(
        partial(
            prompt_completions,
            commands=ed.commands,
            session=ed.session,
            workspace=ed.workspace,
        ),
        cancel_hook=ed.cancel_prompt,
        focus_editor=ed.focus_editor,
        refresh=ed.refresh_ui,
    )
    ed.breadcrumbs = Breadcrumbs(ed.session, ed.workspace, id="breadcrumbs")
    ed.completion_popup = CompletionPopup()
    ed.terminal_panel = TerminalPanel(
        ed.config, ed.workspace, ed.prompt_bar,
        focus_editor=ed.focus_editor, id="terminal-dock",
    )
    ed.explorer_tree = ExplorerTree(
        ed.session,
        ed.workspace,
        ed.prompt_bar,
        focus_editor=ed.focus_editor,
        id="explorer",
    )
    ed.status_bar = StatusBar(
        ed.session, ed.lsp, ed.keymaps, ed.prompt_bar,
        ed.extension_loader, id="statusbar",
    )
    ed.sidebar = Vertical(id="sidebar")
    ed.sidebar_head = SidebarHead(id="sidebar-head")
    ed.editor_col = Vertical(id="editor-col")
    # Document flows need the widgets above; the tab bar needs the flows
    # (tab clicks activate documents), so it is built right after them.
    # The pane stack does not exist yet -- the first pane leaf seeds from
    # the startup document -- so those collaborators arrive via
    # ``attach_pane_stack`` in ``_build_pane_stack``.
    ed.document_flows = DocumentFlows(
        spawn=ed.app.run_worker,
        session=ed.session,
        workspace=ed.workspace,
        lsp=ed.lsp,
        explorer_tree=ed.explorer_tree,
        prompt_bar=ed.prompt_bar,
        message=ed.message,
        report=ed.report,
        refresh_ui=ed.refresh_ui,
        mounted=lambda: ed.mounted,
        reveal_explorer=ed.reveal_explorer,
        startup_readonly=ed.startup_readonly,
    )
    ed.tabbar = TabBar(ed.session, ed.document_flows.activate_doc, id="tabbar")
    # The explorer is built before the flows; its open callback (fire only
    # on user interaction, never during this synchronous construction) and
    # the ctrl+w prefix hook are bound late in ``_build_pane_stack``.
    ed.explorer_tree.open_path = ed.document_flows.open_path_later


def _open_startup_target(ed: Editor, target: str | Path | None) -> None:
    """Open the startup target (file or directory) and seed an empty buffer."""
    if target is not None:
        kind = ed.document_flows.open_target(Path(target))
        # A directory argument opens in browse mode (explorer visible);
        # a file argument opens in edit mode (explorer hidden; Ctrl+B /
        # :explorer reveals it later). With no argument the workspace
        # root is None and the explorer stays hidden regardless.
        ed.explorer_visible = kind == "dir"
    if not ed.session.docs:
        ed.session.new_buffer()


def _build_pane_stack(ed: Editor) -> None:
    """Build the pane tree, its host widget and the flow controllers.

    The controllers (:class:`LspSync` / :class:`OverlayFlows` /
    :class:`ShellFlows` / :class:`CompletionFlows`) own the multi-step
    flows; callers invoke them directly.  DocumentFlows (built earlier,
    without the pane stack) receives its pane-stack collaborators here,
    and WindowFlows is constructed once the stack exists.
    """
    # The pane tree owns editor windows; it starts with one leaf on the
    # startup document and grows with :split / :vsplit.
    ed.panes = PaneManager(
        ed.session,
        ed.session.doc,
        is_mounted=lambda: ed.mounted,
        after_pane_focus=ed.after_pane_focus,
        focus_explorer=ed.focus_explorer,
    )
    ed.pane_host = PaneHost(ed.panes, ed.make_view)
    ed.prompt_flows = PromptFlows(
        ed.session,
        ed.panes,
        ed.prompt_bar,
        message=ed.message,
        readonly_notice=ed.readonly_notice,
        refresh=ed.refresh_ui,
    )
    # Overlays is built before its consumers: LspSync / ShellFlows receive
    # ``push_overlay`` (the shared pre-clear-prompt-then-push verb).
    ed.overlays = OverlayFlows(
        push_screen=ed.app.push_screen,
        pop_screen=ed.app.pop_screen,
        current_screen=ed.current_screen,
        config=ed.config,
        keymaps=ed.keymaps,
        commands=ed.commands,
        actions=ed.actions,
        workspace=ed.workspace,
        prompt=ed.prompt_bar,
        message=ed.message,
        mounted=lambda: ed.mounted,
        open_path=ed.document_flows.open_path_later,
        focus_editor=ed.focus_editor,
        execute_action=ed.execute_action,
        run_command=ed.run_command,
        refresh=ed.refresh_ui,
    )
    ed.lsp_sync = LspSync(
        spawn=ed.app.run_worker,
        lsp=ed.lsp,
        session=ed.session,
        panes=ed.panes,
        status_bar=ed.status_bar,
        prompt=ed.prompt_bar,
        message=ed.message,
        mounted=lambda: ed.mounted,
        push_overlay=ed.overlays.push,
    )
    ed.shell = ShellFlows(
        spawn=ed.app.run_worker,
        session=ed.session,
        workspace=ed.workspace,
        prompt=ed.prompt_bar,
        message=ed.message,
        mounted=lambda: ed.mounted,
        focus_editor=ed.focus_editor,
        refresh=ed.refresh_ui,
        push_overlay=ed.overlays.push,
    )
    ed.completion = CompletionFlows(
        spawn=ed.app.run_worker,
        session=ed.session,
        lsp=ed.lsp,
        workspace=ed.workspace,
        keymaps=ed.keymaps,
        panes=ed.panes,
        popup=ed.completion_popup,
        prompt=ed.prompt_bar,
        refresh=ed.refresh_ui,
        readonly_notice=ed.readonly_notice,
        has_modal_screen=ed.has_modal_screen,
    )
    ed.document_flows.attach_pane_stack(ed.panes, ed.completion)
    # Window flows need the pane stack, the document flows (``:sp <dir>``
    # opens a directory) and the widgets; the explorer's ctrl+w prefix hook
    # is late-bound here for the same construction-order reason.
    ed.window_flows = WindowFlows(
        spawn=ed.app.run_worker,
        session=ed.session,
        panes=ed.panes,
        keymaps=ed.keymaps,
        document_flows=ed.document_flows,
        prompt_bar=ed.prompt_bar,
        message=ed.message,
        has_modal_screen=ed.has_modal_screen,
        focus_editor=ed.focus_editor,
        focus_explorer=ed.focus_explorer,
        after_pane_focus=ed.after_pane_focus,
        explorer_focused=ed.explorer_focused,
    )
    ed.explorer_tree.window_prefix = ed.window_flows.try_window_prefix


def _build_key_ui(ed: Editor) -> None:
    """Build the keymap UI record once the flow modules exist.

    ``find_prompt`` / ``goto_prompt`` bind straight to
    :class:`PromptFlows` (the editor keeps no delegates), so this runs
    last -- after :func:`_build_pane_stack` has created them.
    """
    ed.key_ui = KeyUi(
        execute_action=ed.execute_action,
        message=ed.message,
        command_prompt=ed.command_prompt,
        find_prompt=ed.prompt_flows.find_prompt,
        goto_prompt=ed.prompt_flows.goto_prompt,
        toggle_keymap=ed.toggle_keymap,
    )


class Editor:
    """The running editor: models, widgets and the operations that tie them."""

    # Attributes assembled by the module-level _build_* factories above;
    # declared here because pyright strict cannot infer instance attributes
    # assigned outside the class methods.
    session: EditorSession
    workspace: Workspace
    lsp: LspManager
    keymaps: KeymapSet
    actions: ActionRegistry
    commands: CommandRegistry
    extension_api: ExtensionAPI
    extension_loader: ExtensionLoader
    key_ui: KeyUi
    prompt_bar: PromptBar
    tabbar: TabBar
    breadcrumbs: Breadcrumbs
    completion_popup: CompletionPopup
    terminal_panel: TerminalPanel
    explorer_tree: ExplorerTree
    status_bar: StatusBar
    sidebar: Vertical
    sidebar_head: SidebarHead
    editor_col: Vertical
    explorer_visible: bool
    panes: PaneManager
    pane_host: PaneHost
    lsp_sync: LspSync
    overlays: OverlayFlows
    shell: ShellFlows
    completion: CompletionFlows
    prompt_flows: PromptFlows
    document_flows: DocumentFlows
    window_flows: WindowFlows
    extension_flows: ExtensionFlows

    def __init__(
        self,
        app: App[None],
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
        # ``--readonly`` startup flag: only the *file* argument is opened
        # read-only (a directory argument keeps its normal behavior).
        self.startup_readonly = readonly
        self._ext_messages: list[str] = [
            f"yaterc: {err}" for err in self.config.errors
        ]
        _build_models(self, keymap)
        _build_widgets(self)
        _open_startup_target(self, target)
        _build_pane_stack(self)
        _build_key_ui(self)

    # ================================================================ wiring

    def extension_context(self) -> ExtensionContext:
        """Build the :class:`ExtensionContext` handed to extensions."""
        return ExtensionContext(
            session=self.session,
            workspace=self.workspace,
            lsp=self.lsp,
            keymaps=self.keymaps,
            actions=self.actions,
            commands=self.commands,
            message=self.message,
            # document_flows is built with the widgets (after this factory
            # runs); resolve it on first call like the shell callback above
            run_shell=lambda command, show_output=True: self.shell.run(
                command, show_output
            ),
            open_path=lambda path: self.document_flows.open_path_later(path),
            save=lambda: self.document_flows.save_document(),
        )

    def make_view(self, leaf_id: int) -> EditorView:
        """Build the :class:`EditorView` widget for one pane leaf."""
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
        # buffer the loader warnings BEFORE registering the servers, so a
        # registration failure cannot lose them (baseline on_mount ordering)
        self._ext_messages.extend(self.extension_flows.load_extensions())
        self.extension_flows.register_configured_servers()
        await self.editor_col.mount(self.completion_popup)
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

    def explorer_focused(self) -> bool:
        """True while the explorer tree widget holds the focus."""
        return self.app.focused is self.explorer_tree

    def current_screen(self) -> Screen[Any]:
        """The screen currently on top of the shell's screen stack."""
        return self.app.screen

    def report(self, text: str, kind: str = "info") -> None:
        """Report *text* on the message line (buffered before the first mount).

        The buffered variant handed to :class:`~yate.document_flows.DocumentFlows`
        so pre-mount warnings (binary files, ...) surface on first mount.
        """
        if self.mounted:
            self.message(text, kind)
        else:
            self._ext_messages.append(text)

    def message(self, text: str, kind: str = "info") -> None:
        """Write *text* on the message line and refresh the status chip.

        Dropped before the first mount (nothing is composed yet); callers that
        must not lose a pre-mount message go through :meth:`report`, which
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
        self.lsp_sync.doc_shown_later()
        self.lsp.notify_edit(self.session.doc)
        self.lsp_sync.update_echo()

    # ============================================================== key routing

    def handle_key(self, event: Key) -> bool:
        """Dispatch one key event; returns ``True`` when it was consumed.

        Called both by the editor view (keys typed in a pane) and by the
        application shell (keys that bubble up from other widgets).  The
        dispatch is not side-effect free: the window flows arm and clear
        the ``ctrl+w`` pending chord (``window_flows.try_window_prefix``)
        and the completion-popup branch commits the highlighted candidate
        (``completion.accept``).  A ``True`` return means the caller must
        stop the event (R10) instead of letting it bubble into a second
        dispatch.
        """
        if self.has_modal_screen():
            return False  # a modal screen owns input
        # Entry-level evidence: YATE_TRACE turns this into the ground truth of
        # what event.key names a real terminal actually delivers (field reports
        # and pilot synthesis can disagree; the log settles which side erred).
        log.debug(
            "key event: key=%s character=%r focused=%s",
            event.key,
            event.character,
            type(self.app.focused).__name__ if self.app.focused else None,
        )
        editor_focused = isinstance(self.app.focused, EditorView)
        # Ctrl+Space = manual completion. Checked BEFORE the terminal toggle.
        # The NUL byte splits by driver: the legacy conhost path collapses
        # Ctrl+Space / Ctrl+` / Ctrl+2 into one NUL byte that Textual names
        # "ctrl+@" -- ambiguous, so with the editor focused it favors
        # completion (Ctrl+` still closes the panel while the terminal is
        # focused).  The chord driver keeps the chords distinct -- it names
        # Ctrl+Space "ctrl+space" and the Ctrl+@ key (what the grave chord
        # looks like on layouts where the physical ` sits on Shift+2)
        # "ctrl+2"/"ctrl+shift+2"; those toggle the terminal via TOGGLE_KEYS
        # below.
        nul_keys = ("ctrl+space", "ctrl+@")
        if event.key in nul_keys:
            if editor_focused or event.key == "ctrl+space":
                self.completion.request(manual=True)
                return True
        if event.key in TOGGLE_KEYS and event.key not in nul_keys:
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
                self.completion.accept()
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
        if self.window_flows.try_window_prefix(event):
            return True
        # Global chords that raw byte dispatch cannot represent reliably.
        # alt+shift+p is the default: Windows Terminal reserves ctrl+shift+p
        # for its own command palette, and ctrl+shift+a clashes with other
        # terminal emulators; alt+shift+p is unbound in both.
        if event.key == "alt+shift+p":
            self.overlays.open_command_palette()
            return True
        if self.prompt_bar.active_mode:
            # command line is editing; enter must bubble so the Input's own
            # enter->submit binding can fire
            return False
        # alt+shift+s toggles the screensaver: alt+shift combos have no raw
        # byte form (keyproto.legacy maps only single-modifier alt chords),
        # so like alt+shift+p this must be intercepted by key name.  Kept
        # below the prompt check: typing a :command must never toggle it.
        if event.key == "alt+shift+s":
            self.execute_action("toggle_screensaver")
            return True
        # vscode-style pane focus chords (CSI-u encodings, not in the raw
        # byte table)
        if event.key == "ctrl+shift+e":
            self.focus_explorer()
            return True
        if event.key == "ctrl+1":
            self.focus_editor()
            return True
        if event.key == "ctrl+p":
            self.overlays.open_file_palette()
            return True
        if self.explorer_focused():
            return False  # explorer consumes its own keys
        raw = event_to_raw(event.key, event.character)
        if raw is None:
            # Unmapped names are normal (exotic terminals, widgets without a
            # raw form), so this stays a debug log: YATE_TRACE turns it into
            # evidence when chasing missing-key reports.
            log.debug("unmapped key event: %s (character=%r)", event.key, event.character)
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
            self.readonly_notice()
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
            handled = self.actions.execute(
                name, ActionContext(self.session, self.key_ui)
            )
            if not handled:
                log.debug("action not found: %s", name)
            return handled
        except BufferReadOnlyError:
            self.readonly_notice()
            # the refused action may have moved the cursor / changed anchors
            # before raising; repaint so the view never goes stale
            self.refresh_ui()
            return True

    def readonly_notice(self) -> None:
        """User feedback for an edit refused on a read-only buffer."""
        self.message(
            "buffer is read-only (:set readonly=false to unlock)", kind="warn"
        )

    def insert_char(self, ch: str) -> None:
        """Insert one character at the cursor (keymap ``insert_char``)."""
        self.session.buffer.insert_text(ch)

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
        self.completion.close()
        self.refresh_ui()

    # =============================================================== prompts

    def cancel_prompt(self) -> None:
        """Prompt cancelled (esc): clear live search highlights."""
        if self.session.search.query:
            self.session.search.update("", self.session.buffer)

    def command_prompt(self) -> None:
        """Open the ex command line (``:``)."""
        self.prompt_bar.activate(
            "command",
            placeholder="type a command, :help for list",
            on_submit=self.run_command,
        )

    def page(self, direction: int, half: bool = False) -> None:
        """Scroll the active view by (half) a page."""
        view = self.panes.active_view
        if view is None:
            return
        rows = view.page_delta(half) * direction
        buf = self.session.buffer
        target = max(0, min(buf.row + rows, buf.line_count - 1))
        buf.cursor = (target, min(buf.col, len(buf.lines[target])))

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
        self.message(f"theme: {selected.label}", kind="ok")

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

    def run_command(self, text: str) -> None:
        """``:`` command line: dispatch one ex command."""
        text = text.strip()
        if not text:
            return
        if text.startswith("!"):
            self.shell.run_later(text[1:])
            return
        # A bare number is a line jump (vim's :42, same as VS Code's
        # Ctrl+G -> go to line). An optional sign makes it relative: :+5.
        if re.fullmatch(r"[+-]?\d+", text):
            self.prompt_flows.goto_line_command(text)
            return
        parts = text.split()
        name, args = parts[0], " ".join(parts[1:])
        entry = self.commands.get(name)
        if entry is None:
            log.warning("command not found: %s", name)
            self.message(f"not an editor command: {name} (try :help)", kind="warn")
            return
        log.debug("command: %s (args=%r)", name, args)
        entry[0](args)

    def quit(self, force: bool = False) -> None:
        """``:q``: leave yate (blocked while a buffer is modified)."""
        if not force and any(doc.modified for doc in self.session.docs):
            self.message("unsaved changes — :q! to quit anyway", kind="warn")
            log.info("quit blocked: unsaved changes")
            return
        log.info("quit (force=%s)", force)
        if self.mounted:
            self.app.exit()

    # ============================================================== explorer

    def set_show_hidden(self, flag: bool) -> None:
        """Show/hide dotfiles in the explorer and refresh the tree."""
        self.workspace.show_hidden = flag
        self.explorer_tree.refresh_tree()

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

    def reveal_explorer(self) -> None:
        """Show the sidebar (document flows reveal it on directory opens)."""
        self.explorer_visible = True
        self.sync_explorer_visibility()

    def sync_explorer_visibility(self) -> None:
        """Apply the explorer visibility to the sidebar widgets."""
        visible = self.explorer_visible and self.workspace.root is not None
        self.explorer_tree.display = visible
        self.sidebar.display = visible
