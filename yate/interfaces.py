"""Abstraction layer: Protocol definitions that low-level modules depend on.

This module deliberately has **zero runtime imports from** ``yate.app`` or any
module that transitively imports it.  At runtime it only pulls in the fully
leaf-level packages: ``editor_core``, ``editor_lsp``, and Textual (a
third-party library with no Yate dependencies).

The purpose of this file is to allow :mod:`keymaps`, :mod:`services`,
:mod:`editor_view`, :mod:`app_features` and :mod:`diagnostics` to annotate
their ``app`` parameters without importing :class:`yate.app.YateApp` (which
would create a circular import).  ``YateApp`` satisfies :class:`AppProtocol`
by structural subtyping -- no explicit inheritance is required, though the
app module *may* opt in later for IDE clarity.

All Yate-internal non-leaf types are imported under ``TYPE_CHECKING`` with
string forward refs.  Their parent packages' ``__init__.py`` files eagerly
import modules that depend on ``AppProtocol``, so a runtime import would
always cycle.  ``TYPE_CHECKING`` gives pyright full precision without
triggering the cycle.

The only ``Any`` usages that remain are Textual framework generic type
parameters (``Screen[Any]``, ``WorkType[Any]``, ``Worker[Any]``,
``Callable[[Any], None]``).  These match Textual's / YateApp's own
declarations and are required by Python's generic invariance -- any
concrete type argument would be too narrow to cover all call sites.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Optional, Protocol, TYPE_CHECKING

from textual.events import Key
from textual.screen import Screen
from textual.worker import WorkType, Worker

from yate.editor_core.buffer import TextBuffer
from yate.editor_core.document import Document
from yate.editor_core.search import SearchEngine
from yate.editor_lsp import LspManager

if TYPE_CHECKING:
    from yate.actions import ActionRegistry
    from yate.app_features.commands import CommandRegistry
    from yate.config import YateConfig
    from yate.editor_view.commandline import PromptBar
    from yate.editor_view.completion import CompletionPopup
    from yate.editor_view.editor import EditorView
    from yate.editor_view.explorer import ExplorerTree
    from yate.editor_view.panes import PaneManager
    from yate.editor_view.pane_types import Axis, Leaf
    from yate.editor_view.terminal import TerminalPanel
    from yate.keymaps.base import Keymap
    from yate.services.extensions import ExtensionLoader
    from yate.services.shell import ShellResult
    from yate.services.workspace import Workspace


class AppProtocol(Protocol):
    """Every member of ``YateApp`` that is accessed from a *lower* layer.

    Lower layers = anything under ``keymaps``, ``services``, ``editor_view``,
    ``app_features``, ``diagnostics``.  The protocol captures just what they
    actually touch -- no private state that the UI layer keeps to itself.
    """

    # ---- core editor state ------------------------------------------------
    # NOTE: ``buffer``, ``doc``, ``mounted``, ``active_keymap``, ``editor_view``,
    # ``screen``, ``screen_stack`` are declared as @property here because
    # YateApp implements them as properties, and pyright strict mode rejects
    # assigning a property to a plain attribute slot in a protocol.

    @property
    def buffer(self) -> TextBuffer: ...

    @property
    def doc(self) -> Document: ...

    docs: list[Document]
    doc_index: int

    # ---- services / singletons --------------------------------------------

    workspace: Workspace
    keymaps: dict[str, Keymap]
    keymap_name: str
    lsp: LspManager
    search: SearchEngine
    actions: ActionRegistry
    commands: CommandRegistry
    extension_loader: ExtensionLoader

    # ---- active keymap ----------------------------------------------------

    @property
    def active_keymap(self) -> Keymap: ...

    # ---- config -----------------------------------------------------------

    config: YateConfig

    # ---- completion / prompt UI -------------------------------------------

    completion_popup: Optional[CompletionPopup]
    prompt_bar: Optional[PromptBar]

    # ---- other widget pointers --------------------------------------------

    panes: Optional[PaneManager]

    @property
    def editor_view(self) -> Optional[EditorView]: ...

    explorer_tree: Optional[ExplorerTree]
    terminal_panel: Optional[TerminalPanel]

    # ---- booleans / tiny state -------------------------------------------

    @property
    def mounted(self) -> bool: ...

    welcome_visible: bool
    explorer_visible: bool

    @property
    def screen_stack(self) -> list[Screen[Any]]: ...

    @property
    def screen(self) -> Screen[object]: ...

    # ---- status bar helpers ----------------------------------------------

    def mode_label(self) -> tuple[str, str]: ...

    # ---- private / app-internal flags (accessed by app_features) ---------

    _terminal_visible: bool
    _terminal_starting: bool
    _terminal_factory: Optional[Callable[..., object]]
    _explorer_target: Optional[Path]
    _explorer_is_dir: bool
    @property
    def ext_dirs(self) -> list[Path]: ...

    @property
    def ext_files(self) -> list[Path]: ...

    # ---- core actions -----------------------------------------------------

    def execute_action(self, name: str) -> None: ...

    def insert_char(self, ch: str) -> None: ...

    def page(self, direction: int, half: bool = False) -> None: ...

    def handle_raw_key(self, raw: str) -> bool: ...

    def try_window_prefix(self, event: Key) -> bool: ...

    # ---- terminal ---------------------------------------------------------

    def toggle_terminal(self) -> None: ...

    def open_terminal(self) -> None: ...

    def close_terminal(self) -> None: ...

    # ---- messaging --------------------------------------------------------

    def message(self, text: str, kind: str = "info") -> None: ...

    # ---- focus ------------------------------------------------------------

    def focus_editor(self) -> None: ...

    def focus_explorer(self) -> None: ...

    def toggle_explorer(self) -> None: ...

    # ---- file I/O ---------------------------------------------------------

    def open_path(self, path: Path) -> None: ...

    def open_path_later(self, path: Path) -> None: ...

    def save_document(self) -> None: ...

    def new_buffer(self, show: bool = True) -> None: ...

    def close_tab(self) -> None: ...

    def cycle_tab(self, delta: int) -> None: ...

    def _open_document_path(
        self, path: Path, *, target_leaf: Optional[Leaf] = None
    ) -> Optional[Document]: ...

    # ---- search / replace -------------------------------------------------

    def find_prompt(self, forward: bool) -> None: ...

    def find_next(self, forward: bool) -> None: ...

    def replace_prompt(self) -> None: ...

    # ---- prompt / palette ------------------------------------------------

    def prompt_open(self) -> None: ...

    def command_prompt(self) -> None: ...

    def shell_prompt(self) -> None: ...

    def goto_prompt(self) -> None: ...

    def open_file_palette(self) -> None: ...

    def open_command_palette(self) -> None: ...

    # ---- command / palette -----------------------------------------------

    def run_command(self, text: str) -> None: ...

    def ui_refresh(self) -> None: ...

    def after_pane_focus(self) -> None: ...

    def quit(self, force: bool = False) -> None: ...

    # ---- completion -------------------------------------------------------

    def request_completion(self, manual: bool = False) -> None: ...

    def accept_completion(self) -> None: ...

    # ---- prompt -----------------------------------------------------------

    def prompt_completions(self, text: str, mode: str) -> list[str]: ...

    def on_prompt_cancel(self) -> None: ...

    # ---- Textual integration ---------------------------------------------

    def run_worker(
        self,
        work: WorkType[Any],
        name: Optional[str] = "",
        group: str = "default",
        description: str = "",
        exit_on_error: bool = True,
        start: bool = True,
        exclusive: bool = False,
        thread: bool = False,
    ) -> Worker[Any]: ...

    def _push_overlay(
        self,
        screen: Screen[Any],
        callback: Optional[Callable[[Any], None]] = None,
    ) -> None: ...

    # ---- explorer ops (thin delegates called by app_features.explorer) ---

    def explorer_new_file_prompt(self, directory: Optional[Path]) -> None: ...

    def explorer_new_dir_prompt(self, directory: Optional[Path]) -> None: ...

    def explorer_rename_prompt(self, path: Optional[Path]) -> None: ...

    def explorer_delete_prompt(self, path: Optional[Path]) -> None: ...

    # ---- help / docs ------------------------------------------------------

    def show_manual(self, lang: str = "en") -> None: ...

    def show_changelog(self, lang: str = "en") -> None: ...

    def show_help(self) -> None: ...

    def show_welcome(self) -> None: ...

    def show_diagnostics(self) -> None: ...

    # ---- keymap / theme ---------------------------------------------------

    def select_keymap(self, name: str) -> None: ...

    def toggle_keymap(self) -> None: ...

    def set_theme(self, name: str) -> None: ...

    def set_filetype(self, value: str) -> None: ...

    # ---- pane ops (called from app_features.commands) --------------------

    def _split_with_path(self, axis: Axis, args: str) -> None: ...

    def _only_pane(self) -> None: ...

    def _close_pane(self) -> None: ...

    def _font_command(self) -> None: ...

    # ---- shell service ----------------------------------------------------

    def run_shell_command(
        self, command: str, show_output: bool = True
    ) -> Optional[ShellResult]: ...
