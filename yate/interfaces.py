"""Abstraction layer: Protocol definitions that low-level modules depend on.

This module deliberately has **zero imports from** ``yate.app`` or any module
that transitively imports it.  It only pulls in the fully-leaf packages
(``editor_core``, ``editor_lsp``) so it can reference concrete data types
(``Document``, ``TextBuffer``, ``LspManager``) in the protocol signatures.

The purpose of this file is to allow :mod:`keymaps`, :mod:`services`,
:mod:`editor_view`, :mod:`app_features` and :mod:`diagnostics` to annotate
their ``app`` parameters without importing :class:`yate.app.YateApp` (which
would create a circular import).  ``YateApp`` satisfies :class:`AppProtocol`
by structural subtyping -- no explicit inheritance is required, though the
app module *may* opt in later for IDE clarity.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Optional, Protocol

from yate.editor_core.buffer import TextBuffer
from yate.editor_core.document import Document
from yate.editor_core.search import SearchEngine
from yate.editor_lsp import LspManager


class AppProtocol(Protocol):
    """Every member of ``YateApp`` that is accessed from a *lower* layer.

    Lower layers = anything under ``keymaps``, ``services``, ``editor_view``,
    ``app_features``, ``diagnostics``.  The protocol captures just what they
    actually touch -- no private state that the UI layer keeps to itself.

    Types that live in packages that *do* import ``yate.app`` (e.g.
    ``Workspace``, ``Keymap``, ``PaneManager``, ``PromptBar``,
    ``CompletionPopup`` ...) are kept as ``Any`` or string forward refs so
    that ``interfaces.py`` stays leaf-level.
    """

    # ---- core editor state ------------------------------------------------
    # NOTE: ``buffer``, ``doc``, ``mounted``, ``active_keymap`` are declared
    # as @property here because YateApp implements them as properties, and
    # pyright strict mode rejects assigning a property to a plain attribute
    # slot in a protocol.

    @property
    def buffer(self) -> TextBuffer: ...

    @property
    def doc(self) -> Document: ...

    docs: list[Document]
    doc_index: int

    # ---- services / singletons --------------------------------------------

    workspace: Any          # yate.services.workspace.Workspace
    keymaps: dict[str, Any]  # dict[str, Keymap]
    keymap_name: str
    lsp: LspManager
    search: SearchEngine
    actions: Any            # yate.actions.ActionRegistry
    commands: Any           # yate.app_features.commands.CommandRegistry
    extension_loader: Any   # yate.services.extensions.ExtensionLoader

    # ---- active keymap ----------------------------------------------------

    @property
    def active_keymap(self) -> Any: ...  # Keymap

    # ---- config -----------------------------------------------------------

    config: Any              # yate.config.YateConfig

    # ---- completion / prompt UI -------------------------------------------

    completion_popup: Optional[Any]     # CompletionPopup
    prompt_bar: Optional[Any]           # PromptBar

    # ---- other widget pointers --------------------------------------------

    panes: Optional[Any]                 # PaneManager
    editor_view: Optional[Any]          # EditorView
    explorer_tree: Optional[Any]        # ExplorerTree
    terminal_panel: Optional[Any]       # TerminalPanel

    # ---- booleans / tiny state -------------------------------------------

    @property
    def mounted(self) -> bool: ...

    welcome_visible: bool
    explorer_visible: bool

    @property
    def screen_stack(self) -> list[Any]: ...

    @property
    def screen(self) -> Any: ...  # Textual screen

    # ---- status bar helpers ----------------------------------------------

    def mode_label(self) -> tuple[str, str]: ...

    # ---- private / app-internal flags (accessed by app_features) ---------

    _terminal_visible: bool
    _terminal_starting: bool
    _terminal_factory: Optional[Callable[..., Any]]
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

    def try_window_prefix(self, event: Any) -> bool: ...

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
        self, path: Path, *, target_leaf: Optional[Any] = None
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
        work: Any,
        name: Optional[str] = "",
        group: str = "default",
        description: str = "",
        exit_on_error: bool = True,
        start: bool = True,
        exclusive: bool = False,
        thread: bool = False,
    ) -> Any: ...

    def _push_overlay(self, screen: Any) -> None: ...

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

    def _split_with_path(self, axis: Any, args: str) -> None: ...

    def _only_pane(self) -> None: ...

    def _close_pane(self) -> None: ...

    def _font_command(self) -> None: ...

    # ---- shell service ----------------------------------------------------

    def run_shell_command(
        self, command: str, show_output: bool = True
    ) -> Any: ...
