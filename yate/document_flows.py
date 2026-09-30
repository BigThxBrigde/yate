"""Document lifecycle flows: open, save, close and tab cycling.

Extracted from :mod:`yate.editor`.  Everything that turns a path into an
active document (startup target, ``:e``, splits, the explorer, the
extension API), keeps it on disk (``:w`` / ``:saveas``) and moves between
tab documents (``:bn`` / ``:bp`` / ``:bd``) lives here.  Like
:class:`~yate.prompt_flows.PromptFlows` the module is constructed by the
editor and never imports upward: collaborators are concrete objects, and
editor-owned state (mount flag, sidebar visibility, message buffering) is
reached through injected callables.

The pane stack is assembled *after* the startup document opens (the first
pane leaf seeds from it), so :class:`PaneManager` and
:class:`~yate.completion.CompletionFlows` arrive in a second phase via
:meth:`attach_pane_stack` -- mirroring ``PaneManager.attach``.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import partial
from pathlib import Path

from textual.app import App

from yate.completion import CompletionFlows
from yate.editor_core import Document
from yate.editor_lsp import LspManager
from yate.editor_view.commandline import PromptBar
from yate.editor_view.explorer import ExplorerTree
from yate.editor_view.panes import PaneManager
from yate.logs import tracing
from yate.session import EditorSession, Leaf
from yate.services.workspace import Workspace

log = tracing.get_logger(__name__)


class DocumentFlows:
    """Owns the open / save / close / cycle lifecycle of documents."""

    #: Bound only in :meth:`attach_pane_stack` (the pane tree seeds its
    #: first leaf from the startup document, so neither collaborator can
    #: exist at construction time); every use happens post-mount.
    panes: PaneManager
    completion: CompletionFlows

    def __init__(
        self,
        app: App[None],
        session: EditorSession,
        workspace: Workspace,
        lsp: LspManager,
        explorer_tree: ExplorerTree,
        prompt_bar: PromptBar,
        message: Callable[[str, str], None],
        report: Callable[[str, str], None],
        refresh_ui: Callable[[], None],
        mounted: Callable[[], bool],
        reveal_explorer: Callable[[], None],
        startup_readonly: bool,
    ) -> None:
        self.app = app
        self.session = session
        self.workspace = workspace
        self.lsp = lsp
        self.explorer_tree = explorer_tree
        self.prompt_bar = prompt_bar
        self._message = message
        self._report = report
        self._refresh_ui = refresh_ui
        self._mounted = mounted
        self._reveal_explorer = reveal_explorer
        self.startup_readonly = startup_readonly

    def attach_pane_stack(
        self, panes: PaneManager, completion: CompletionFlows
    ) -> None:
        """Bind the collaborators built with the pane stack.

        The pane tree seeds its first leaf from the startup document, so it
        cannot exist when this module is constructed (see the module
        docstring); every use of either collaborator happens post-mount,
        which is always after the editor finished assembling.
        """
        self.panes = panes
        self.completion = completion

    # ================================================================ target

    def open_target(self, path: Path) -> str:
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
        if not self._mounted():
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
            self._report(f"not a text file: {path.name}", "warn")
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
            self._report(f"not a text file: {path.name}", "warn")
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
            is_dir = path.is_dir()
        except OSError:
            is_dir = False
        if is_dir:
            log.info("opened folder: %s", path)
            # OSError past the probe surfaces to the caller (fail loudly)
            # instead of masquerading below as a failed file open
            self.workspace.set_root(path)
            self.explorer_tree.refresh_tree()
            self._reveal_explorer()
            # focus the tree so keyboard nav works immediately
            self.explorer_tree.focus()
            self._message(f"opened folder {path}", "info")
            return
        if self._open_document(path) is None:
            return
        self.explorer_tree.refresh_tree()
        self.session.reset_search()
        self.completion.close()
        self._message(f"opened {self.session.doc.name}", "info")
        self._refresh_ui()

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
        self.explorer_tree.refresh_tree()
        self.session.reset_search()
        self.completion.close()
        self._message(f"opened {self.session.doc.name}", "info")
        self._refresh_ui()

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
        if self._mounted():
            self.panes.show_doc(self.panes.active, doc)
        self.session.reset_search()
        self.completion.close()
        if show:
            # A user-requested buffer (:enew / new tab) dismisses the
            # one-time welcome page for the rest of the session. Internal
            # replacements (startup seed, close-last-tab fallback) pass
            # show=False and leave the flag untouched.
            self.session.welcome_visible = False
            self._message("new buffer", "info")
        self._refresh_ui()

    def show_welcome(self) -> None:
        """Re-enable the welcome page (``:welcome``)."""
        self.session.welcome_visible = True
        self._refresh_ui()
        self._message("welcome page enabled", "info")

    def close_tab(self) -> None:
        """``:bd``: close the active tab (LSP didClose is reported)."""
        if not self.session.docs:
            return
        closed, fallback = self.session.close_active()
        log.info("closing tab: %s", closed.path)
        if self._mounted():
            # Every pane showing the closed document rebinds to the fallback;
            # other panes keep their documents and independent view states.
            self.panes.document_closed(closed, fallback)
        self.session.reset_search()
        self.completion.close()
        self._message("closed tab", "info")
        self._refresh_ui()

    def cycle_tab(self, delta: int) -> None:
        """``:bn`` / ``:bp``: activate the next/previous tab.

        With a single tab this is a silent no-op: cycling cannot move
        anywhere, so repeating the command must not spam the message
        line.
        """
        if len(self.session.docs) <= 1:
            return
        self.session.cycle(delta)
        if self._mounted():
            self.panes.show_doc(self.panes.active, self.session.doc)
        # The previous tab's matches are (row, start, end) spans of *its*
        # buffer: keeping them would paint stale highlights on the new
        # document and send ``n`` to out-of-range coordinates.
        self.session.reset_search()
        self.completion.close()
        self._refresh_ui()

    def save_document(self) -> None:
        """``:w``: write the active document to disk."""
        doc = self.session.doc
        if doc.buffer.read_only:
            self._message(
                "cannot save a read-only buffer; use :saveas to write elsewhere",
                "warn",
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
            self._message(f"saved {doc.path}", "ok")
            log.info("saved: %s", doc.path)
        except (OSError, UnicodeError) as exc:
            self._message(f"save failed: {exc}", "error")
            log.warning("save failed: %s: %s", doc.path, exc)
        self._refresh_ui()

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
            self._message("save cancelled", "info")
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
            self._message(f"saved {path}", "ok")
        except (OSError, UnicodeError) as exc:
            if locked:
                buf.read_only = True
            self._message(f"save failed: {exc}", "error")

    # ============================================================== prompts

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
