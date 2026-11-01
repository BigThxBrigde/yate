"""File manager flows: overlay/fullscreen open points and workspace switching.

Constructed by :class:`yate.editor.Editor` with explicit collaborators and
callbacks; like every flow module it never imports upward and holds no App
handle -- the screen-stack verbs, the state queries and the fullscreen exit
verb arrive as injected callables.  The orchestration of a selection
(dirty gate -> close the old workspace -> hand the target to
:class:`~yate.flows.document_flows.DocumentFlows`) lives here, so the
:class:`~yate.editor_view.filemgr.FileManagerScreen` itself stays a pure
browsing component (R3).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from yate.config import YateConfig
from yate.editor_view.commandline import PromptBar
from yate.editor_view.explorer import ExplorerTree
from yate.editor_view.filemgr import FileManagerScreen
from yate.flows import MessageFn, OpenSelectedFn, StateQuery
from yate.flows.document_flows import DocumentFlows
from yate.logs import tracing
from yate.services.workspace import Workspace
from yate.session import EditorSession

log = tracing.get_logger(__name__)


class FileManagerFlows:
    """Opens the file manager and orchestrates the workspace switch."""

    def __init__(
        self,
        *,
        push_screen: Callable[..., object],
        pop_screen: Callable[[], object],
        session: EditorSession,
        workspace: Workspace,
        explorer_tree: ExplorerTree,
        documents: DocumentFlows,
        prompt_bar: PromptBar,
        message: MessageFn,
        report: MessageFn,
        refresh_ui: Callable[[], None],
        mounted: StateQuery,
        focus_editor: Callable[[], None],
        config: YateConfig,
    ) -> None:
        # Screen-stack verbs and the mount query, injected as bound methods
        # / callables by the editor (no App handle is held here); the types
        # follow the OverlayFlows precedent (App.push_screen / pop_screen
        # return awaitables, so a ``-> None`` shape would not fit).
        self._push_screen = push_screen
        self._pop_screen = pop_screen
        self._session = session
        self._workspace = workspace
        self._explorer_tree = explorer_tree
        self._documents = documents
        self._prompt_bar = prompt_bar
        self._message = message
        self._report = report
        self._refresh_ui = refresh_ui
        self._mounted = mounted
        self._focus_editor = focus_editor
        self._config = config
        #: Fullscreen exit verb; ``None`` until :meth:`bind_exit` (the app
        #: shell binds it on mount, ``bind_hex_opener`` precedent).
        self._exit_app: Callable[[], None] | None = None

    def bind_exit(self, exit_app: Callable[[], None]) -> None:
        """Bind the fullscreen exit verb (late-bound, ``bind_hex_opener`` style).

        The editor never holds ``App.exit`` (App handle boundary), so the
        L4 shell forwards it here once on mount; until then the fullscreen
        close callback degrades to a plain screen pop.
        """
        self._exit_app = exit_app

    def open_overlay(self) -> None:
        """Open the file manager as a modal overlay over the editor."""
        if not self._mounted():
            return
        self._prompt_bar.idle()
        self._push_screen(
            self._build_screen(
                fullscreen=False, initial_dir=None, close=self._pop_screen_call
            )
        )

    def open_fullscreen(self, initial_dir: Path) -> None:
        """Open the file manager fullscreen (``--file-manager`` startup form).

        ``close`` is the bound exit verb (the app quits when the user
        leaves); without a binding (defensive, L4 always binds on mount)
        it degrades to popping the screen and a warning is logged.
        """
        if not self._mounted():
            return
        if not initial_dir.exists():
            self._message(f"path does not exist: {initial_dir}", "error")
            return
        # ``_probe_is_dir`` semantics (document_flows): a path that exists
        # but is not a directory (or hits an unreadable ACL / racing delete)
        # must never become the browsing cwd -- report and stay put.
        try:
            is_dir = initial_dir.is_dir()
        except OSError:
            is_dir = False
        if not is_dir:
            self._message(f"not a directory: {initial_dir}", "error")
            return
        if self._exit_app is None:
            log.warning("filemanager exit verb not bound; closing pops instead")
            close: Callable[[], None] = self._pop_screen_call
        else:
            close = self._exit_app
        self._prompt_bar.idle()
        self._push_screen(
            self._build_screen(fullscreen=True, initial_dir=initial_dir, close=close)
        )

    def _build_screen(
        self,
        *,
        fullscreen: bool,
        initial_dir: Path | None,
        close: Callable[[], None],
    ) -> FileManagerScreen:
        """Build the screen with the injected collaborators (R3)."""
        open_selected: OpenSelectedFn = self._open_selected
        return FileManagerScreen(
            workspace=self._workspace,
            preview=self._config.file_preview,
            open_selected=open_selected,
            close=close,
            on_renamed=self._on_renamed,
            on_deleted=self._on_deleted,
            on_show_hidden_changed=self._on_show_hidden_changed,
            fullscreen=fullscreen,
            initial_dir=initial_dir,
        )

    def _on_renamed(self, old: Path, new: Path) -> None:
        """Keep tabs and the file tree in sync after a rename (M2).

        Mirrors the explorer precedent: retarget every session tab that
        pointed at *old* onto *new*, then refresh the tree so it stops
        listing the stale name (explorer.py ``submit_rename``).
        """
        self._session.retarget(old, new)
        self._explorer_tree.refresh_tree()

    def _on_deleted(self, path: Path) -> None:
        """Keep tabs and the file tree in sync after a delete (M2).

        Closes every session tab whose file lived under *path* so a later
        save cannot resurrect the deleted file, then refreshes the tree
        (explorer.py ``submit_delete`` precedent).
        """
        self._session.close_under(path)
        self._explorer_tree.refresh_tree()

    def _on_show_hidden_changed(self, value: bool) -> None:
        """Refresh the file tree after the hidden-files toggle (m5).

        The workspace-wide ``show_hidden`` flag is shared with the
        explorer; *value* is the new state, the tree just needs a reload
        to drop or pick up hidden entries.
        """
        self._explorer_tree.refresh_tree()

    def _pop_screen_call(self) -> None:
        """Call the injected pop verb, dropping its awaitable result."""
        self._pop_screen()

    def _open_selected(self, paths: list[Path]) -> None:
        """Switch the workspace to the selected path set (Q1/Q2/Q3).

        An empty set is a no-op.  A set containing directories enters only
        the first one (cursor order = list order) and ignores everything
        else (Q2: one workspace root, so multiple directories cannot
        enter).  A pure file set switches the workspace to the first
        file's parent directory, then opens every file in order with the
        first one active (the rest stay as background tabs).  The screen
        has already dismissed itself when this runs, so a refused switch
        can only leave its warning on the message line.
        """
        if not paths:
            return
        dirs = [p for p in paths if p.is_dir()]
        if dirs:
            if len(paths) > 1:
                self._report(
                    "multiple entries selected - entering the first directory only",
                    "info",
                )
            self._switch_workspace(dirs[0])
            return
        if not self._switch_workspace(paths[0].parent):
            return
        for path in paths:
            self._documents.open_path(path)
        if len(paths) > 1:
            # Reactivate the first file: every open activates its document,
            # so the last one would otherwise end up in front.
            self._documents.open_path(paths[0])
        self._focus_editor()
        self._refresh_ui()

    def _switch_workspace(self, target: Path) -> bool:
        """Close the old workspace, then hand *target* to the document flows.

        The dirty gate runs first (Q1): any modified buffer refuses the
        switch with a warning -- nothing is ever silently dropped, the
        user saves or discards explicitly (``:q`` blocking precedent).
        Closing pops tabs until only the pathless scratch buffer remains
        (``close_active`` always appends a fresh scratch when the last
        tab closes, so the returned fallback can never terminate the
        loop).  Returns ``True`` when the switch went through.
        """
        dirty = sum(1 for doc in self._session.docs if doc.modified)
        if dirty:
            self._report(f"{dirty} unsaved changes - save or discard first", "warn")
            log.info("workspace switch blocked: %d unsaved changes", dirty)
            return False
        while not (
            len(self._session.docs) == 1 and self._session.docs[0].path is None
        ):
            self._session.close_active()
        self._workspace.invalidate()
        # Directory branch: set_root + refresh_tree + reveal; file branch:
        # plain open -- both are DocumentFlows' own orchestration, not
        # re-implemented here.
        self._documents.open_path(target)
        return True
