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
from collections.abc import Callable, Mapping
from functools import partial
from pathlib import Path
from typing import cast

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.events import Key, MouseEvent
from textual.screen import Screen

from yate import __version__
from yate.editor_compose import (
    _build_key_ui as _build_key_ui,
    _build_models as _build_models,
    _build_pane_stack as _build_pane_stack,
    _build_widgets as _build_widgets,
    _open_startup_target as _open_startup_target,
)
from yate.config import YateConfig
from yate.editor_core import BufferReadOnlyError, Document
from yate.editor_lsp.manager import LspManager
from yate.editor_syntax import (
    format_filetype_candidates,
    language_name,
    resolve_filetype,
)
from yate.editor_components import theme
from yate.editor_components.canvas_screen import CanvasScreen
from yate.editor_components.chrome import Breadcrumbs, SidebarHead, TabBar
from yate.editor_components.commandline import PromptBar
from yate.editor_components.completion import CompletionPopup
from yate.editor_components.editor import EditorView
from yate.editor_components.explorer import ExplorerTree
from yate.editor_components.panes import PaneHost, PaneManager
from yate.editor_components.statusbar import StatusBar, mode_chip
from yate.editor_components.terminal import TOGGLE_KEYS, TerminalPanel
from yate.editor_components.whichkey import EditorColumn, WhichKeyPanel
from yate.flows.chunked_flows import ChunkedFlows
from yate.flows.completion_flows import CompletionFlows
from yate.flows.document_flows import DocumentFlows
from yate.flows.extension_flows import ExtensionFlows
from yate.flows.file_manager_flows import FileManagerFlows
from yate.flows.lsp_sync import LspSync
from yate.flows.mouse_flows import MouseFlows
from yate.flows.overlay_flows import OverlayFlows
from yate.flows.prompt_flows import PromptFlows
from yate.flows.shell_flows import ShellFlows
from yate.flows.whichkey_flows import WhichKeyFlows
from yate.flows.window_flows import WindowFlows
from yate.keymaps.base import ActionContext, KeyUi
from yate.keymaps.registry import KeymapSet
from yate.keyproto.legacy import event_to_raw
from yate.logs import tracing
from yate.registries import ActionRegistry, CommandRegistry
from yate.services.events import (
    DocumentClosed,
    EditorEvent,
    EventHub,
    KeymapChanged,
    ThemeChanged,
)
from yate.services.extensions import ExtensionAPI, ExtensionContext, ExtensionLoader
from yate.services.workspace import Workspace
from yate.session import EditorSession

#: Trace logger ("yate.editor"); silent unless yate_trace is on.
log = tracing.get_logger(__name__)


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
    events: EventHub
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
    which_key_panel: WhichKeyPanel
    whichkey: WhichKeyFlows
    sidebar: Vertical
    sidebar_head: SidebarHead
    editor_col: EditorColumn
    explorer_visible: bool
    panes: PaneManager
    pane_host: PaneHost
    lsp_sync: LspSync
    overlays: OverlayFlows
    shell: ShellFlows
    completion: CompletionFlows
    prompt_flows: PromptFlows
    document_flows: DocumentFlows
    file_manager_flows: FileManagerFlows
    window_flows: WindowFlows
    extension_flows: ExtensionFlows
    mouse_flows: MouseFlows
    chunked_flows: ChunkedFlows

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
        # Pending flag for refresh_ui_soon (coalesced refresh scheduling).
        self._refresh_pending = False
        # ``--readonly`` startup flag: only the *file* argument is opened
        # read-only (a directory argument keeps its normal behavior).
        self.startup_readonly = readonly
        self._ext_messages: list[str] = [
            f"yaterc: {err}" for err in self.config.errors
        ]
        # Assembly order: chunked_flows is built with the models (the
        # session's on_opened attach hook fires for the startup document
        # in _open_startup_target); whichkey needs keymaps / window_flows /
        # which_key_panel ready; the window chord observer is bound right
        # after WhichKeyFlows exists (see _build_pane_stack).  The file
        # manager flows are built with the pane stack (overlays precedent);
        # their fullscreen exit verb is bound by the app shell on mount
        # (bind_file_manager_exit).
        _build_models(self, keymap)
        _build_widgets(self)
        _open_startup_target(self, target)
        _build_pane_stack(self)
        _build_key_ui(self)

    # ================================================================ wiring

    def bind_file_manager_exit(self, exit_app: Callable[[], None]) -> None:
        """Forward the app-exit verb to the file manager flows (L4 on_mount)."""
        self.file_manager_flows.bind_exit(exit_app)

    def extension_context(self) -> ExtensionContext:
        """Build the :class:`ExtensionContext` handed to extensions."""
        # ``theme.set_theme`` returns the new Theme, but the context wants a
        # plain switch (Callable[[str], None]): adapt here, since pyright
        # strict rejects a value-returning lambda in a None slot.
        def _set_theme(name: str) -> None:
            theme.set_theme(name)

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
            run_action=lambda name: self.key_ui.execute_action(name),
            set_theme=_set_theme,
            active_theme_name=lambda: theme.active().name,
            open_canvas=self._open_canvas,
        )

    def _open_canvas(
        self,
        cols: int,
        rows: int,
        on_key: Callable[[str], None],
        on_tick: Callable[[], None],
        on_close: Callable[[], None],
    ) -> tuple[
        Callable[[str, Mapping[str, str]], None],
        Callable[[str], None],
        Callable[[], None],
    ]:
        """Push the extension canvas screen and hand back its controls.

        Returns the raw ``(draw, set_status, close)`` callback triple; the
        UI bridge wraps it into the extension-facing handle, so this method
        never names a type from the extension machinery (R14: the editor
        imports the facade only).  The screen (L2) owns rendering, the tick
        clock and key consumption.  The close callback rides the push
        callback, so both a self ``dismiss()`` and an external pop reach
        *on_close*.  The thunks flip a local ``closed`` flag first: a tick
        that races the dismissal then finds a dead handle instead of a dead
        widget.
        """
        closed = False

        def mark_closed() -> None:
            nonlocal closed
            if closed:
                return
            closed = True
            on_close()

        screen = CanvasScreen(cols, rows, on_key, on_tick, mark_closed)
        self.app.push_screen(screen, callback=lambda _result: mark_closed())

        def draw(grid: str, palette: Mapping[str, str]) -> None:
            if not closed:
                screen.draw(grid, palette)

        def set_status(text: str) -> None:
            if not closed:
                screen.set_status(text)

        def close() -> None:
            if not closed:
                # mark_closed flips the flag synchronously and fires on_close
                # once, so a script closing its own canvas cannot race a
                # pending tick against an already-popped screen.
                mark_closed()
                screen.dismiss()

        return draw, set_status, close

    def documents_closed(self, docs: list[Document]) -> None:
        """Session hook for closed documents: emit, then notify the servers.

        The DOCUMENT_CLOSED event fires before the LSP didClose dispatch --
        listeners observe a consistent "just left the session" state either
        way, and the LSP call is only deferred to a worker.
        """
        self.events.emit(
            EditorEvent.DOCUMENT_CLOSED, DocumentClosed(tuple(docs))
        )
        self.lsp_sync.documents_closed(docs)

    def make_view(self, leaf_id: int) -> EditorView:
        """Build the :class:`EditorView` widget for one pane leaf."""
        return EditorView(
            leaf_id,
            panes=self.panes,
            session=self.session,
            lsp=self.lsp,
            keymaps=self.keymaps,
            handle_key=self.handle_key,
            handle_mouse=partial(self._on_view_mouse, leaf_id),
            ensure_row=partial(self._ensure_chunked_row, leaf_id),
        )

    def _ensure_chunked_row(self, leaf_id: int, row: int) -> None:
        """Route a rendered row of leaf *leaf_id* to the chunked flows.

        Installed as every view's ``ensure_row`` callback; a no-op unless
        the leaf's document is a chunked one (the O(1) document check keeps
        the per-row render cost flat for plain documents).
        """
        leaf = self.panes.leaf_for(leaf_id)
        if leaf is None:
            return
        doc = leaf.doc
        if doc.chunked is not None:
            self.chunked_flows.ensure_row(doc, row)

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
                # The which-key panel is absolutely positioned inside
                # #editor-col (see resources/which-key.tcss): yielding it
                # here keeps it on the layer above pane_host while #bottom
                # (statusbar / prompt) no longer competes for vertical
                # space -- the bug fix for "always shows VIM".
                yield self.which_key_panel
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

        # Chunked documents opened before mount (the startup target) start
        # their background scan workers here; post-mount opens spawn from
        # ChunkedFlows.attach directly.
        for opened in self.session.docs:
            if opened.chunked is not None:
                self.chunked_flows.start_scan(opened)

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
        # A binary startup target opened before the overlays existed defers
        # to here (take_pending_hex); call_after_refresh lets the base
        # screen finish its first layout pass before the modal screen is
        # pushed (same safety layer as the --diff handoff in app.on_mount).
        pending_hex = self.document_flows.take_pending_hex()
        if pending_hex is not None:
            self.app.call_after_refresh(
                self.overlays.open_hex_view, pending_hex
            )

    async def on_unmount(self) -> None:
        """Tear the extension hooks, terminal and LSP services down in order."""
        # Each teardown is isolated: a failing terminal/LSP shutdown must not
        # leave the other background service (and its threads) untouched.
        # Extension hooks run first (sync, while editor state is still
        # intact); they release resources the extension owns, e.g. spawned
        # subprocesses or timers. teardown_all isolates per extension, but
        # even if the loader state itself is broken the call must not block
        # the terminal/LSP cleanup below.
        try:
            self.extension_loader.teardown_all()
        except Exception:  # noqa: BLE001 - teardown must reach terminal/LSP
            log.exception("extension teardown failed")
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

    def current_screen(self) -> Screen[None]:
        """The screen currently on top of the shell's screen stack."""
        # Every screen yate pushes is a ModalScreen[None]; App.screen is
        # declared Screen[object] upstream, so the narrower type is asserted
        # here at that third-party boundary (cast over ignore).
        return cast(Screen[None], self.app.screen)

    def report(self, text: str, kind: str = "info") -> None:
        """Report *text* on the message line (buffered before the first mount).

        The buffered variant handed to :class:`~yate.flows.document_flows.DocumentFlows`
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

    def refresh_ui_soon(self) -> None:
        """Coalesce a :meth:`refresh_ui` onto the next refresh cycle.

        High-frequency producers (mouse drag moves fire hundreds of
        MouseMove per second) schedule through here instead of repainting
        synchronously: a pending schedule short-circuits, so a burst of N
        moves costs at most one full repaint per frame.  The flag clears
        when the scheduled callback runs, re-arming for the next burst.
        """
        if self._refresh_pending or not self.mounted:
            return
        self._refresh_pending = True
        self.app.call_after_refresh(self._flush_refresh_soon)

    def _flush_refresh_soon(self) -> None:
        """Scheduled :meth:`refresh_ui_soon` callback: clear, then repaint."""
        self._refresh_pending = False
        self.refresh_ui()

    def _refresh_views(self) -> None:
        """Repaint the active pane always, stale inactive panes on demand.

        The active view is unconditionally repainted (cursor movement and
        rendering state are not versioned).  Inactive panes only repaint
        when :attr:`EditorView.content_stale` holds -- their document
        binding changed (rebind / close) or the buffer's ``content_version``
        moved -- so multi-pane sessions skip repainting panes whose content
        did not change.  Explicit paths (LSP events, highlight worker,
        mouse flows, theme broadcast) do not go through this gate.
        """
        active = self.panes.active_view
        if active is not None:
            active.content_changed()
        for view in self.panes.all_views():
            if view is not active and view.content_stale:
                view.content_changed()

    def _refresh_chrome(self) -> None:
        """Refresh the chrome widgets: status bar, tab bar, breadcrumbs, which-key."""
        self.status_bar.refresh_status()
        self.tabbar.refresh_tabs()
        self.breadcrumbs.refresh_crumbs()
        self.whichkey.refresh()

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
        # The command line owns its Input: ctrl+space must not open the
        # completion popup over it and must keep flowing to the prompt bar
        # (the active_mode branch below hands the event back to the Input).
        if event.key in nul_keys and not self.prompt_bar.active_mode:
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
        # chords so the prefix is consumed wherever focus currently is.
        # The panel follows via window_flows.on_chord_change -- no manual
        # refresh here, the chord state owner notifies on every flip.
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
        # alt+shift+f opens the file manager overlay: same alt+shift shape
        # as the two chords above (no raw byte form, keymap row is
        # help-only), so the real dispatch is by key name here.  The call
        # itself goes through the action registry, so rebinding/wrapping
        # the "file_manager" action takes effect.
        if event.key == "alt+shift+f":
            self.execute_action("file_manager")
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
        # Unconsumed keys pay nothing: only a handled key changed editor
        # state worth repainting (plan-f P3).  The completion feed stays
        # unconditional -- the popup needs every raw key even when the
        # keymap ignored it.
        if handled:
            self.refresh_ui()
        self.completion.after_editor_key(raw)
        return handled

    def _on_view_mouse(self, leaf_id: int, event: MouseEvent) -> bool:
        """Dispatch one mouse event for the view of *leaf_id*."""
        view = self.panes.views.get(leaf_id)
        if view is None:
            return False
        return self.mouse_flows.handle_view_mouse(view, event)

    def cancel_mouse_state(self) -> None:
        """Drop every in-flight mouse interaction (``:set support_mouse
        off`` mid-drag): the app gate now drops all mouse events, so no
        MouseUp path can release captures or clear drag flags."""
        self.app.capture_mouse(None)  # view or PaneHost capture, whoever holds it
        self.mouse_flows.cancel_drag()
        host = self.panes.host
        if host is not None:
            host.cancel_drag()

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

    def reveal_match(self, path: Path, row: int, col: int) -> None:
        """Open *path* if needed and put the cursor on a project-search hit.

        The find & replace screen has already scheduled the async open
        worker (``open_path_later``) for *path* before calling this, so a
        deferred cursor write would race the worker and its ``apply_doc``
        would restore the pane's saved view state over the reveal.  A
        synchronous open here lands the document on screen first; the
        reveal result (cursor + scroll) is then written back into the
        leaf's view state, so that same worker ``apply_doc`` -- its
        ``is_open`` short-circuits -- restores exactly the revealed
        position instead of clobbering it.
        """
        doc = self.session.is_open(path)
        if doc is None:
            self.document_flows.open_path(path)
            doc = self.session.is_open(path)
        if doc is None:
            return
        if doc is not self.session.doc:
            self.document_flows.activate_doc(doc)
        buf = doc.buffer
        buf.anchor = None
        # the hit row comes from a disk scan; an open buffer with unsaved
        # line deletions may have fewer lines by now -- clamp before the
        # subscript, set_cursor's own clamp would come too late
        row = min(row, len(buf.lines) - 1)
        buf.set_cursor((row, min(col, len(buf.lines[row]))))
        view = self.panes.active_view
        if view is not None:
            view.reveal_cursor()
            state = self.panes.active.state_for(doc)
            state.cursor = buf.cursor
            state.anchor = None
            state.scroll_col = view.scroll_col
            state.scroll_row = view.scroll_offset.y
        self.refresh_ui()

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
        """Prompt cancelled (esc): drop the pending sweep, clear highlights."""
        self.prompt_flows.cancel_live_search()
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
        self.events.emit(EditorEvent.KEYMAP_CHANGED, KeymapChanged(name))
        self.refresh_ui()

    def toggle_keymap(self) -> None:
        """Flip between the vsc and vim key maps."""
        self.select_keymap(self.keymaps.toggle())

    def mode_label(self) -> tuple[str, str]:
        """``(label, background color)`` for the status bar mode chip.

        Delegated to the status bar's pure helper so the widget and the
        smoke scripts share a single implementation.
        """
        return mode_chip(self.prompt_bar, self.keymaps, self.session.buffer)

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
        # Normalization (strip / lower) is single-sourced in
        # editor_components.theme.set_theme; the shell forwards the raw input.
        # Capture before set_theme: afterwards active().name always equals
        # *selected.name*, so the re-select case is no longer distinguishable
        # there.
        previous = theme.active().name
        try:
            selected = theme.set_theme(name)
        except KeyError:
            self.message(
                f"unknown theme: {name!r} ({', '.join(theme.available())})",
                kind="error",
            )
            return
        reselected = selected.name == previous
        # Lazily ensure the Textual bridge exists (an extension may have
        # registered a yate theme after startup); register_theme is
        # idempotent when the name already exists.
        textual_name = theme.textual_theme_name(selected.name)
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
        # Re-selecting the active theme is a no-op at the Textual reactive
        # (the same-value repaint is skipped), so the event is guarded to
        # keep listeners in sync with what actually re-rendered; the
        # confirmation message is emitted either way (pre-branch behavior).
        if not reselected:
            self.events.emit(
                EditorEvent.THEME_CHANGED, ThemeChanged(selected.name)
            )
        self.message(f"theme: {selected.label}", kind="ok")

    def set_readonly(self, value: bool) -> None:
        """Set the active buffer's read-only flag (``:set readonly=``).

        The value is also recorded on the document as the explicit
        read-only intent (:attr:`Document.read_only_pinned`), so a later
        ``:fullload`` promotion keeps it.
        """
        doc = self.session.doc
        doc.buffer.read_only = value
        doc.read_only_pinned = value
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
                    f"(available: {format_filetype_candidates()})",
                    kind="warn",
                )
            else:
                doc.filetype_override = resolved
                label = language_name(resolved) or resolved
                self.message(f"filetype set to {resolved} ({label})", kind="ok")
        # Rebind the LSP document (close on the old server, open on the new)
        # and force a repaint so highlighting and the status bar update.
        # The re-open rides in the same worker AFTER the close: the
        # synchronous refresh below reaches doc_shown_later() before this
        # worker pops the didOpen state, so scheduling the open alongside
        # the close would see is_open() still true and skip the rebind.
        async def _rebind() -> None:
            await self.lsp.on_document_closed(doc)
            self.lsp_sync.doc_shown_later()

        self.app.run_worker(
            _rebind, group="lsp-sync", exclusive=False, exit_on_error=False,
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
        parts = text.split(maxsplit=1)
        name, args = parts[0], parts[1] if len(parts) > 1 else ""
        entry = self.commands.get(name)
        if entry is None:
            log.warning("command not found: %s", name)
            self.message(f"not an editor command: {name} (try :help)", kind="warn")
            return
        log.debug("command: %s (args=%r)", name, args)
        entry.func(args)

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
