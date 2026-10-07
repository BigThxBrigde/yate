"""Window pane flows: splits, closing, resizing and the vim ctrl+w chord.

Extracted from :mod:`yate.editor`.  Every multi-pane operation (``:sp`` /
``:vs`` / ``:only`` / ``ctrl+w q``, the resize chords) and the vim
``ctrl+w`` two-key state machine lives here.  Like the other ``*Flows``
modules it is constructed by the editor and never imports upward:
collaborators are concrete objects (:class:`PaneManager`,
:class:`~yate.flows.document_flows.DocumentFlows`, ...), and editor-owned state
(modal screens, focus) is reached through injected callables.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import partial
from pathlib import Path

from textual.events import Key

from yate.flows import MessageFn, SpawnFn, StateQuery
from yate.flows.document_flows import DocumentFlows
from yate.editor_view.commandline import PromptBar
from yate.editor_view.panes import PaneManager
from yate.keymaps.registry import KeymapSet
from yate.keymaps.vim import VimKeymap, VimMode
from yate.logs import tracing
from yate.session import Axis, EditorSession

log = tracing.get_logger(__name__)

#: The keys accepted as the second half of a vim ``ctrl+w`` chord.
_WINDOW_KEYS: frozenset[str] = frozenset(
    {"h", "j", "k", "l", "s", "v", "q", "o",
     "+", "plus", "-", "minus",
     "<", "less_than_sign", ">", "greater_than_sign",
     "=", "equals_sign", "ctrl+w"}
)


class WindowFlows:
    """Owns pane splits / closing / resizing and the ctrl+w chord state."""

    def __init__(
        self,
        spawn: SpawnFn,
        session: EditorSession,
        panes: PaneManager,
        keymaps: KeymapSet,
        document_flows: DocumentFlows,
        prompt_bar: PromptBar,
        message: MessageFn,
        has_modal_screen: StateQuery,
        focus_editor: Callable[[], None],
        focus_explorer: Callable[[], None],
        after_pane_focus: Callable[[], None],
        explorer_focused: StateQuery,
    ) -> None:
        # Bound ``App.run_worker``: the background-work verb injected by the
        # editor (this module never holds the App handle itself).
        self._spawn = spawn
        self.session = session
        self.panes = panes
        self.keymaps = keymaps
        self.document_flows = document_flows
        self.prompt_bar = prompt_bar
        self._message = message
        self._has_modal_screen = has_modal_screen
        self._focus_editor = focus_editor
        self._focus_explorer = focus_explorer
        self._after_pane_focus = after_pane_focus
        self._explorer_focused = explorer_focused
        self._window_pending = False

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
            self.document_flows.open_path(path)
            return
        self._spawn(
            partial(self._split_pane_worker, axis, path),
            group="pane", exclusive=True, exit_on_error=False,
        )

    def _split_pane(self, axis: Axis) -> None:
        self._spawn(
            partial(self._split_pane_worker, axis, None),
            group="pane", exclusive=True, exit_on_error=False,
        )

    async def _split_pane_worker(self, axis: Axis, path: Path | None) -> None:
        if path is not None:
            # split first (the new pane becomes active), then open the file
            # into the active pane
            await self.panes.split_active(axis)
            opened = await self.document_flows.open_path_async(path)
            if not opened:
                # The open failed (e.g. not a text file): roll the split
                # back so a failed command leaves the layout untouched.
                await self.panes.close_active()
                return
        else:
            await self.panes.split_active(axis)
            self._after_pane_focus()

    def only_pane(self) -> None:
        """``:only``: keep the active pane, close the others."""
        self._spawn(
            # coroutine *functions* (partial), never built coroutines: an
            # eager coroutine leaks when the worker never starts
            partial(self.panes.only_active),
            group="pane", exclusive=True, exit_on_error=False,
        )

    def close_pane(self) -> None:
        """``ctrl+w q``: close the active pane (documents stay open)."""
        if self.panes.leaf_count <= 1:
            self._message("only one pane open (use :q to quit)", "warn")
            return
        self._spawn(
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
            self._message("pane already at its minimum size", "warn")

    @property
    def window_pending(self) -> bool:
        """True while a vim ``ctrl+w`` window chord awaits its second key."""
        return self._window_pending

    def try_window_prefix(self, event: Key) -> bool:
        """Handle the vim ``ctrl+w`` window chord; True when consumed.

        Called from the explorer tree *before* keymap dispatch (the vim
        keymap swallows unmapped keys, so the shell would never see them)
        and from :meth:`yate.editor.Editor.handle_key` for the other
        focused widgets.
        """
        if self._has_modal_screen():
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
                self._message(
                    "ctrl+w-  (s/:split v/:vsplit q close o :only  "
                    "h j k l move, ctrl+w cycle  + - < > = resize)",
                    "info",
                )
                return True
        return False

    def _window_command(self, key: str) -> None:
        """Execute the second key of a vim ``ctrl+w`` window chord."""
        if key == "ctrl+w":  # round-robin: explorer <-> every editor pane
            self.panes.cycle_focus(explorer_focused=self._explorer_focused())
            return
        if self._explorer_focused():
            # The explorer plays the left-neighbour pane: only ctrl+w l/j/k
            # returns to an editor pane from it.
            if key in ("l", "j", "k"):
                self._focus_editor()
            return
        if key == "h":
            if not self.panes.focus_direction("h"):
                self._focus_explorer()
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
