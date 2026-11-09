"""Assembly factories for the Editor widget tree.

Module-level factories (review 20260926 #5): keeps ``Editor.__init__``
a readable sequence of build steps. Callbacks are bound methods of the
not-yet-fully-initialized editor; they only fire after construction, so
the half-built state is never observed.

The factories are editor-private (consumed only by :mod:`yate.editor`);
they are listed in ``__all__`` so importing them from editor.py reads as
deliberate to pyright (parsing.py ``__all__`` precedent), not as
``reportPrivateUsage`` violations.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import partial
from pathlib import Path
from typing import Literal

from textual.containers import Vertical

from yate.cmdline_completions import cmdline_completions
from yate.editor_components.chrome import Breadcrumbs, SidebarHead, TabBar
from yate.editor_components.commandline import PromptBar
from yate.editor_components.completion import CompletionPopup
from yate.editor_components.explorer import ExplorerTree
from yate.editor_components.hover_popup import HoverPopup
from yate.editor_components.panes import PaneHost, PaneManager
from yate.editor_components.statusbar import StatusBar
from yate.editor_components.terminal import TerminalPanel
from yate.editor_components.whichkey import EditorColumn, WhichKeyPanel
from yate.editor_lsp.manager import LspManager
from yate.flows.chunked_flows import ChunkedFlows
from yate.flows.completion_flows import CompletionFlows
from yate.flows.document_flows import DocumentFlows
from yate.flows.extension_flows import ExtensionFlows
from yate.flows.file_manager_flows import FileManagerFlows
from yate.flows.hover_flows import HoverFlows
from yate.flows.lsp_sync import LspSync
from yate.flows.mouse_flows import MouseFlows
from yate.flows.overlay_flows import OverlayFlows
from yate.flows.prompt_flows import PromptFlows
from yate.flows.shell_flows import ShellFlows
from yate.flows.whichkey_flows import WhichKeyFlows
from yate.flows.window_flows import WindowFlows
from yate.keymaps.base import KeyUi
from yate.keymaps.registry import KeymapSet
from yate.keymaps.vim import VimKeymap
from yate.keymaps.vsc import VscKeymap
from yate.registries import ActionRegistry, CommandRegistry
from yate.services.events import EventHub
from yate.services.extensions import ExtensionAPI, ExtensionLoader
from yate.services.workspace import Workspace
from yate.session import EditorSession

__all__ = [
    "_build_key_ui",
    "_build_models",
    "_build_pane_stack",
    "_build_widgets",
    "_open_startup_target",
]


def _build_models(ed: yate.editor.Editor, keymap: str | None) -> None:
    """Create the models and services the editor operations work on.

    Module-level factory (review 20260926 #5): keeps :meth:`Editor.__init__`
    a readable sequence of build steps.  Callbacks are bound methods of the
    not-yet-fully-initialized *ed*; they only fire after construction, so
    the half-built state is never observed.
    """
    ed.session = EditorSession(
        ed.config,
        on_closed=lambda docs: ed.documents_closed(docs),
        on_opened=lambda doc: ed.chunked_flows.attach(doc),
    )
    # Chunked loading flows: built with the models so the session's
    # on_opened hook (firing for the startup document during
    # _open_startup_target) already finds them.
    ed.chunked_flows = ChunkedFlows(
        ensure_view_refresh=ed.refresh_ui,
        message=ed.message,
        spawn=ed.app.run_worker,
        active_doc=lambda: ed.session.doc,
        mounted=lambda: ed.mounted,
    )
    ed.workspace = Workspace()
    # propagate the yaterc show_hidden default to the workspace
    ed.workspace.show_hidden = ed.config.show_hidden
    ed.explorer_visible = True
    # Extension event hub: one instance shared by the extension API
    # (``api.events``) and every emitter below; failures report through the
    # message line.  Created before the extension API, which wraps it.
    ed.events = EventHub(report_failure=lambda text: ed.message(text))
    # Language Server Protocol: registered servers come from extensions
    # and the yaterc ``language_servers`` option; the manager is UI
    # independent and safe to keep even with no server.  It is created
    # before the extension API, which wires ``api.lsp`` straight to it.
    # The event callback defers through lsp_sync, which is built with the
    # pane stack (it needs the widgets); both callbacks only fire later.
    ed.lsp = LspManager(
        workspace_root=lambda: ed.workspace.root,
        on_event=lambda event, doc=None: ed.lsp_sync.on_event(event, doc),
    )
    ed.keymaps = KeymapSet(
        {"vsc": VscKeymap(), "vim": VimKeymap()},
        keymap if keymap is not None else ed.config.keymap,
    )
    # Empty tables: the built-in action / command modules import the
    # editor, so only the shell may load them (R5/R7 -- see YateApp).
    ed.actions = ActionRegistry()
    ed.commands = CommandRegistry()
    ed.extension_api = ExtensionAPI(ed.extension_context(), ed.events)
    ed.extension_loader = ExtensionLoader(ed.extension_api)
    ed.extension_flows = ExtensionFlows(
        ed.extension_loader,
        ed.extension_api,
        ed.config,
        ed.ext_dirs,
        ed.ext_files,
        message=ed.message,
    )


def _build_widgets(ed: yate.editor.Editor) -> None:
    """Create the widget tree members and keep the references ops need."""
    ed.prompt_bar = PromptBar(
        partial(
            cmdline_completions,
            commands=ed.commands,
            workspace=ed.workspace,
        ),
        cancel_hook=ed.cancel_prompt,
        focus_editor=ed.focus_editor,
        refresh=ed.refresh_ui,
    )
    ed.breadcrumbs = Breadcrumbs(ed.session, ed.workspace, id="breadcrumbs")
    ed.completion_popup = CompletionPopup()
    ed.hover_popup = HoverPopup(id="hover-docs")
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
    def _extension_segment_rows(
        align: Literal["left", "right"],
    ) -> list[tuple[str, Callable[[], str | None]]]:
        # Adapt the L3 bridge objects into plain (id, provider) rows so the
        # status bar needs no import from the extension machinery.
        return [
            (segment.id, segment.provider)
            for segment in ed.extension_api.ui.segments(align)
        ]

    ed.status_bar = StatusBar(
        ed.session, ed.lsp, ed.keymaps, ed.prompt_bar,
        extension_segments=_extension_segment_rows,
        loaded_extensions=lambda: len(ed.extension_loader.loaded),
        id="statusbar",
    )
    ed.which_key_panel = WhichKeyPanel(id="which-key")
    ed.sidebar = Vertical(id="sidebar")
    ed.sidebar_head = SidebarHead(id="sidebar-head")
    # EditorColumn forwards its resizes to the floating which-key panel
    # (the absolute-positioned panel never sees its own region change).
    ed.editor_col = EditorColumn(id="editor-col")
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
        events=ed.events,
        message=ed.message,
        report=ed.report,
        refresh_ui=ed.refresh_ui,
        mounted=lambda: ed.mounted,
        reveal_explorer=ed.reveal_explorer,
        startup_readonly=ed.startup_readonly,
        open_hex_view=None,  # Bound late in _build_pane_stack (overlays not yet built)
    )
    ed.tabbar = TabBar(ed.session, ed.document_flows.activate_doc, id="tabbar")
    # The explorer is built before the flows; its open callback (fire only
    # on user interaction, never during this synchronous construction) and
    # the ctrl+w prefix hook are bound late in ``_build_pane_stack``.
    ed.explorer_tree.open_path = ed.document_flows.open_path_later


def _open_startup_target(ed: yate.editor.Editor, target: str | Path | None) -> None:
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


def _build_pane_stack(ed: yate.editor.Editor) -> None:
    """Build the pane tree, its host widget and the flow controllers.

    The controllers (:class:`LspSync` / :class:`OverlayFlows` /
    :class:`ShellFlows` / :class:`CompletionFlows` / :class:`HoverFlows` /
    :class:`MouseFlows`)
    own the multi-step flows; callers invoke them directly.  DocumentFlows
    (built earlier, without the pane stack) receives its pane-stack
    collaborators here, and WindowFlows is constructed once the stack
    exists.
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
    ed.hover = HoverFlows(
        spawn=ed.app.run_worker,
        lsp=ed.lsp,
        session=ed.session,
        panes=ed.panes,
        popup=ed.hover_popup,
        has_modal_screen=ed.has_modal_screen,
    )
    ed.mouse_flows = MouseFlows(
        keymaps=ed.keymaps,
        config=ed.config,
        refresh=ed.refresh_ui,
        # Drag moves coalesce through the deferred variant (plan P4); the
        # down/up/click interaction endpoints keep the synchronous repaint.
        refresh_soon=ed.refresh_ui_soon,
        on_hover_move=ed.hover.on_mouse_move,
    )
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
        session=ed.session,
        workspace=ed.workspace,
        prompt=ed.prompt_bar,
        message=ed.message,
        mounted=lambda: ed.mounted,
        open_path=ed.document_flows.open_path_later,
        reveal_match=ed.reveal_match,
        readonly_notice=ed.readonly_notice,
        focus_editor=ed.focus_editor,
        execute_action=ed.execute_action,
        run_command=ed.run_command,
        refresh=ed.refresh_ui,
    )
    # The hex opener rides DocumentFlows' binary-open branch; the overlays
    # exist only from the line above, so the callback is bound here (the
    # DocumentFlows construction happened earlier, without it).
    ed.document_flows.bind_hex_opener(ed.overlays.open_hex_view)
    # The file manager flows: overlay/fullscreen open points plus the
    # workspace-switch orchestration.  Its fullscreen exit verb is bound
    # later by the app shell (Editor.bind_file_manager_exit -> flows.bind_exit,
    # on_mount): the editor itself never holds App.exit (App handle boundary).
    ed.file_manager_flows = FileManagerFlows(
        push_screen=ed.app.push_screen,
        pop_screen=ed.app.pop_screen,
        session=ed.session,
        workspace=ed.workspace,
        explorer_tree=ed.explorer_tree,
        documents=ed.document_flows,
        prompt_bar=ed.prompt_bar,
        message=ed.message,
        report=ed.report,
        refresh_ui=ed.refresh_ui,
        mounted=lambda: ed.mounted,
        focus_editor=ed.focus_editor,
        config=ed.config,
    )
    ed.lsp_sync = LspSync(
        spawn=ed.app.run_worker,
        lsp=ed.lsp,
        session=ed.session,
        panes=ed.panes,
        status_bar=ed.status_bar,
        prompt=ed.prompt_bar,
        events=ed.events,
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
    ed.whichkey = WhichKeyFlows(
        keymaps=ed.keymaps,
        window_pending=lambda: ed.window_flows.window_pending,
        window_chord_hints=ed.window_flows.window_chord_hints,  # IKQ3IT
        panel=ed.which_key_panel,
        message=ed.message,
        which_key_enabled=lambda: ed.config.which_key,
    )
    # Late chord observer (same binding pattern as window_prefix above):
    # WindowFlows notifies on every ctrl+w flip, covering the explorer path
    # whose on_key never reaches Editor.handle_key.
    ed.window_flows.on_chord_change = ed.whichkey.refresh


def _build_key_ui(ed: yate.editor.Editor) -> None:
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


# Placed after the factories on purpose: editor.py imports these names at
# its top, so a direct `import yate.editor_compose` must not re-enter
# editor.py before they exist (import-cycle order safety).  The
# annotation references are lazy strings, so no earlier runtime binding
# is needed.
import yate.editor
