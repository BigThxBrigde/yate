"""The yate application: a Textual App wiring editor_core, keymaps, services.

The UI is built with Textual (Rich rendering).  All editor logic lives in
``editor_core`` / ``keymaps`` / ``services`` and is UI independent; this class
only composes widgets, routes keys to the active keymap and implements the
callbacks that actions / extensions invoke.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.events import Key
from textual.widgets import Input, Static

from yate import __version__
from yate.actions import ActionRegistry, populate
from yate.config import YateConfig
from yate.editor_core import Document, SearchEngine
from yate.editor_core.buffer import TextBuffer
from yate.editor_view import theme
from yate.editor_view.commandline import PromptBar
from yate.editor_view.editor import EditorView
from yate.editor_view.explorer import ExplorerTree
from yate.editor_view.icons import CHEVRON_RIGHT, FOLDER, icon_for_path
from yate.editor_view.keys import event_to_raw, textual_key_to_raw
from yate.editor_view.manual import ManualScreen
from yate.editor_view.modals import HelpScreen, OutputScreen
from yate.editor_view.palette import PaletteScreen
from yate.editor_view.statusbar import StatusBar
from yate.keymaps.base import ActionContext, Keymap
from yate.keymaps.vsc import VscKeymap
from yate.keymaps.vim import VimKeymap, VimMode
from yate.services import fonts
from yate.services.extensions import ExtensionAPI, ExtensionLoader, LoadedExtension
from yate.services.shell import ShellResult, run_shell, shell_name
from yate.services.workspace import Workspace


# `textual_key_to_raw` lives in yate.editor_view.keys to avoid import cycles
# and is re-exported here for convenience/tests.
__all__ = ["textual_key_to_raw", "CommandRegistry", "YateApp"]


# --------------------------------------------------------------- commands

class CommandRegistry:
    """``:`` commands, extendable by extensions."""

    def __init__(self) -> None:
        self._commands: dict[str, tuple[Callable[[str], object], str]] = {}

    def register(self, name: str, func: Callable[[str], object], description: str) -> None:
        self._commands[name] = (func, description)

    def get(self, name: str) -> Optional[tuple[Callable[[str], object], str]]:
        return self._commands.get(name)

    def names(self) -> list[str]:
        return sorted(self._commands)

    def describe(self, name: str) -> str:
        entry = self._commands.get(name)
        return entry[1] if entry else ""


class YateApp(App[None]):
    """The yate Textual application and application state."""

    # ctrl+p is yate's own command prompt -- disable Textual's palette.
    ENABLE_COMMAND_PALETTE = False

    CSS = """
    #bottom {
        dock: bottom;
        height: 2;
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
    }
    #tabbar {
        height: 1;
        padding: 0;
    }
    #breadcrumbs {
        height: 1;
        padding: 0;
    }
    #editor {
        height: 1fr;
    }
    """

    def __init__(
        self,
        target: Optional[str | Path] = None,
        *,
        keymap: Optional[str] = None,
        config: Optional[YateConfig] = None,
        ext_files: Optional[list[str | Path]] = None,
        ext_dirs: Optional[list[str | Path]] = None,
    ) -> None:
        super().__init__()
        self.title = f"yate {__version__}"

        self.config = config if config is not None else YateConfig()
        # The color theme is process-global state (like vim's colorscheme).
        try:
            theme.set_theme(self.config.theme)
        except KeyError:
            self.config.errors.append(f"unknown theme: {self.config.theme!r}")

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
        self._register_commands()

        self.focus_target = "editor"
        self.explorer_visible = True

        self._ext_files = [Path(p) for p in (ext_files or [])]
        self._ext_dirs = [Path(p) for p in (ext_dirs or [])]
        self.extension_api = ExtensionAPI(self)
        self.extension_loader = ExtensionLoader(self.extension_api)
        self._ext_messages: list[str] = []
        self._ext_messages.extend(f"yaterc: {err}" for err in self.config.errors)
        self._replace_pending = ""
        self._prev_manual_theme: Optional[str] = None
        self._explorer_target: Optional[Path] = None
        self._explorer_is_dir = False

        # widgets (set in on_mount)
        self.sidebar: Optional[Vertical] = None
        self.sidebar_head: Optional[Static] = None
        self.tabbar: Optional[Static] = None
        self.breadcrumbs: Optional[Static] = None
        self.explorer_tree: Optional[ExplorerTree] = None
        self.editor_view: Optional[EditorView] = None
        self.status_bar: Optional[StatusBar] = None
        self.prompt_bar: Optional[PromptBar] = None

        # ------------------------------------------------------------- open
        if target is not None:
            self._open_target(Path(target))
        if not self.docs:
            self.new_buffer(show=False)

    # ================================================================== docs

    @property
    def doc(self) -> Document:
        return self.docs[self.doc_index]

    @property
    def buffer(self) -> TextBuffer:
        return self.doc.buffer

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
        the state from the editor widget, which is a mounted Widget.)
        """
        return self.editor_view is not None and self.editor_view.is_mounted

    def _open_target(self, path: Path) -> None:
        if not path.exists():
            # treat as a not-yet-created file
            self.workspace.set_root(path.parent if str(path.parent) else Path.cwd())
            self._open_document_path(path)
            return
        kind = self.workspace.open_target(path)
        if kind == "file":
            self._open_document_path(path)

    def _open_document_path(self, path: Path) -> None:
        resolved = path.resolve()
        for i, doc in enumerate(self.docs):
            if doc.path is not None and doc.path.resolve() == resolved:
                self.doc_index = i
                return
        if path.exists() and not Workspace.is_text_file(path):
            self._ext_messages.append(f"not a text file: {path.name}")
            return
        if path.exists():
            doc = Document.open(path)
        else:
            doc = Document(path, self._make_buffer())
        self._apply_buffer_options(doc.buffer)
        self.docs.append(doc)
        self.doc_index = len(self.docs) - 1

    def open_path(self, path: Path) -> None:
        try:
            if path.is_dir():
                self.workspace.set_root(path)
                if self.explorer_tree is not None:
                    self.explorer_tree.refresh_tree()
                self.explorer_visible = True
                self._sync_explorer_visibility()
                self.message(f"opened folder {path}")
                return
        except OSError:
            pass
        self._open_document_path(path)
        if self.explorer_tree is not None:
            self.explorer_tree.refresh_tree()
        self.search = SearchEngine()
        if self.editor_view is not None:
            self.editor_view.scroll_col = 0
        self.message(f"opened {self.doc.name}")
        self.ui_refresh()

    def new_buffer(self, show: bool = True) -> None:
        self.docs.append(Document(None, self._make_buffer()))
        self.doc_index = len(self.docs) - 1
        self.search = SearchEngine()
        if self.editor_view is not None:
            self.editor_view.scroll_col = 0
        if show:
            self.message("new buffer")
        self.ui_refresh()

    def close_tab(self) -> None:
        if not self.docs:
            return
        self.docs.pop(self.doc_index)
        if not self.docs:
            self.new_buffer(show=False)
        self.doc_index = min(self.doc_index, len(self.docs) - 1)
        self.search = SearchEngine()
        self.message("closed tab")
        self.ui_refresh()

    def cycle_tab(self, delta: int) -> None:
        if len(self.docs) < 2:
            return
        self.doc_index = (self.doc_index + delta) % len(self.docs)
        self.search = SearchEngine()
        if self.editor_view is not None:
            self.editor_view.scroll_col = 0
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
        self.message(f"keymap: {self.active_keymap.label}")
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
        self.message(f"theme: {selected.label}")

    def apply_theme(self) -> None:
        """Push the active theme onto every widget and force a repaint."""
        if not self.mounted:
            return
        t = theme.active()
        self.screen.styles.background = t.bg
        if self.editor_view is not None:
            self.editor_view.styles.background = t.bg
            self.editor_view.content_changed()
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
        return handled

    def ui_refresh(self) -> None:
        if not self.mounted or self.editor_view is None:
            return
        self.editor_view.content_changed()
        if self.status_bar is not None:
            self.status_bar.refresh_status()
        self.update_tabbar()
        self.update_breadcrumbs()

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
        if self.editor_view is not None:
            self.editor_view.focus()

    def on_key(self, event: Key) -> None:
        """Fallback routing: keys not consumed by a focused widget."""
        if len(self.screen_stack) > 1:
            return  # modal screen owns input
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
            return  # command line is editing
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

    # -------------------------------------------------------- explorer ops

    def explorer_new_file_prompt(self, directory: Optional[Path]) -> None:
        self._explorer_prompt_new(directory, is_dir=False)

    def explorer_new_dir_prompt(self, directory: Optional[Path]) -> None:
        self._explorer_prompt_new(directory, is_dir=True)

    def _explorer_prompt_new(self, directory: Optional[Path], *, is_dir: bool) -> None:
        if directory is None:
            self.message("select a file or folder first", kind="warn")
            return
        if self.prompt_bar is None:
            return
        # on a file entry the sibling directory is the creation target
        if not directory.is_dir():
            directory = directory.parent
        self._explorer_target = directory
        self._explorer_is_dir = is_dir
        self.prompt_bar.activate(
            "new_dir" if is_dir else "new_file",
            placeholder=f"created inside {directory.name}/",
        )

    def explorer_rename_prompt(self, path: Optional[Path]) -> None:
        if path is None:
            self.message("select a file or folder first", kind="warn")
            return
        if self.prompt_bar is None:
            return
        self._explorer_target = path
        self.prompt_bar.activate("rename", initial=path.name,
                                 placeholder=f"renaming {path.name}")

    def explorer_delete_prompt(self, path: Optional[Path]) -> None:
        if path is None:
            self.message("select a file or folder first", kind="warn")
            return
        if self.prompt_bar is None:
            return
        self._explorer_target = path
        kind = "folder" if path.is_dir() else "file"
        self.prompt_bar.activate(
            "delete",
            placeholder=f"{kind} {path.name} — type y to confirm",
        )

    def _explorer_create(self, directory: Optional[Path], name: str) -> None:
        if directory is None:
            return
        try:
            target = self.workspace.create_entry(
                directory, name, is_dir=self._explorer_is_dir)
        except ValueError as exc:
            self.message(f"invalid name: {exc}", kind="error")
            return
        except FileExistsError as exc:
            self.message(str(exc), kind="error")
            return
        except OSError as exc:
            self.message(f"create failed: {exc}", kind="error")
            return
        if self.explorer_tree is not None:
            self.explorer_tree.refresh_tree()
        self.message(f"created {target.name}", kind="ok")
        if not self._explorer_is_dir:
            # VS Code behavior: a new file opens right away
            self._open_document_path(target)

    def _explorer_apply_rename(self, path: Optional[Path], name: str) -> None:
        if path is None:
            return
        try:
            new_path = self.workspace.rename_entry(path, name)
        except ValueError as exc:
            self.message(f"invalid name: {exc}", kind="error")
            return
        except FileExistsError as exc:
            self.message(str(exc), kind="error")
            return
        except OSError as exc:
            self.message(f"rename failed: {exc}", kind="error")
            return
        # keep tabs pointing at the moved document
        for doc in self.docs:
            if doc.path is not None and doc.path.resolve() == path.resolve():
                doc.path = new_path
        if self.explorer_tree is not None:
            self.explorer_tree.refresh_tree()
        self.message(f"renamed to {new_path.name}", kind="ok")

    def _explorer_apply_delete(self, path: Optional[Path], confirm: str) -> None:
        if path is None:
            return
        if confirm.strip().lower() not in ("y", "yes"):
            self.message("delete cancelled")
            return
        try:
            self.workspace.remove_entry(path)
        except OSError as exc:
            self.message(f"delete failed: {exc}", kind="error")
            return
        # close tabs whose file lived under the deleted path
        target = path.resolve()
        kept = [d for d in self.docs
                if d.path is None or not d.path.resolve().is_relative_to(target)]
        closed = len(self.docs) - len(kept)
        if closed:
            self.docs = kept
            if not self.docs:
                self.new_buffer(show=False)
            self.doc_index = max(0, min(self.doc_index, len(self.docs) - 1))
            self.search = SearchEngine()
            self.message(f"closed {closed} open tab(s)", kind="warn")
        if self.explorer_tree is not None:
            self.explorer_tree.refresh_tree()
        self.message(f"deleted {path.name}", kind="ok")

    # ------------------------------------------------------------- prompts

    def prompt_open(self) -> None:
        if self.prompt_bar is None:
            return
        self.prompt_bar.activate("open", placeholder="path to a file or directory")

    def _submit_open(self, text: str) -> None:
        text = text.strip()
        if text:
            self.open_path(Path(text))

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
        elif mode in ("find", "find_back"):
            self._submit_search(text, mode == "find")
        elif mode == "shell":
            self.run_shell_command(text)
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
            if self.editor_view is not None:
                self.editor_view.refresh()

    # ================================================================= shell

    def run_shell_command(self, command: str, show_output: bool = True) -> Optional[ShellResult]:
        command = command.strip()
        if not command:
            return None
        cwd = (
            self.workspace.root
            or (self.doc.path.parent if self.doc.path is not None else None)
            or Path.cwd()
        )
        result = run_shell(command, cwd=cwd)
        if show_output and self.mounted:
            body = (
                f"(cwd: {cwd} · {shell_name()})\n\n"
                f"{result.output or '(no output)'}"
            )
            self.push_screen(OutputScreen(self, f"$ {command}", body, result.returncode))
        return result

    # ================================================================ modals

    def show_help(self) -> None:
        """Open the keybinding reference overlay."""
        if self.mounted:
            self.push_screen(HelpScreen(self))

    def show_manual(self, lang: str = "en") -> None:
        """Open the bundled user manual, rendered as read-only markdown."""
        if not self.mounted or isinstance(self.screen, ManualScreen):
            return
        # switch the textual design tokens before pushing so the first
        # frame of the markdown viewer is already themed (switching on
        # screen resume leaves an unthemed flash while markdown mounts)
        self._prev_manual_theme = self.theme
        self.theme = "catppuccin-mocha"
        self.push_screen(
            ManualScreen(self, lang), callback=lambda _result: self._restore_manual_theme()
        )

    def _restore_manual_theme(self) -> None:
        if self._prev_manual_theme is not None:
            self.theme = self._prev_manual_theme
            self._prev_manual_theme = None

    def open_file_palette(self) -> None:
        """Quick file open: fuzzy palette over the workspace files (ctrl+p)."""
        if self.mounted:
            self.push_screen(PaletteScreen(self, "files"))

    def open_command_palette(self) -> None:
        """Command palette: fuzzy search over ``:`` commands (alt+shift+p)."""
        if self.mounted:
            self.push_screen(PaletteScreen(self, "commands"))

    async def action_quit(self) -> None:
        """Textual's ctrl+q priority binding — route through our guard."""
        self.quit()

    # =============================================================== commands

    def _register_commands(self) -> None:
        reg = self.commands.register
        reg("w", lambda args: self.save_document(), "save the current file")
        reg("write", lambda args: self.save_document(), "save the current file")
        reg("q", lambda args: self.quit(), "quit yate")
        reg("quit", lambda args: self.quit(), "quit yate")
        reg("q!", lambda args: self.quit(force=True), "quit, discarding changes")

        def _wq(args: str) -> None:
            self.save_document()
            self.quit(force=True)

        reg("wq", _wq, "save and quit")

        def _edit(args: str) -> None:
            args = args.strip()
            if args:
                self.open_path(Path(args))
            else:
                self.prompt_open()

        reg("e", _edit, "open a file or directory by path")
        reg("edit", _edit, "open a file or directory by path")
        reg("enew", lambda args: self.new_buffer(), "open a new empty buffer")
        reg("bn", lambda args: self.cycle_tab(1), "next buffer/tab")
        reg("bnext", lambda args: self.cycle_tab(1), "next buffer/tab")
        reg("bp", lambda args: self.cycle_tab(-1), "previous buffer/tab")
        reg("bprev", lambda args: self.cycle_tab(-1), "previous buffer/tab")
        reg("bd", lambda args: self.close_tab(), "close current buffer/tab")
        reg("files", lambda args: self.open_file_palette(), "fuzzy quick file open (ctrl+p)")
        reg("palette", lambda args: self.open_command_palette(),
            "command palette (alt+shift+p)")

        def _set(args: str) -> None:
            args = args.strip()
            if "=" not in args:
                self.message("usage: :set keymap=vsc|vim  |  :set theme=mocha", kind="warn")
                return
            key, _, value = args.partition("=")
            key = key.strip()
            if key == "keymap":
                self.select_keymap(value.strip())
            elif key == "theme":
                self.set_theme(value.strip())
            else:
                self.message(f"unknown option: {key}", kind="warn")

        def _theme(args: str) -> None:
            args = args.strip()
            if not args:
                current = theme.active()
                self.message(
                    f"theme: {current.label} ({current.name}) · "
                    f"available: {', '.join(theme.available())}"
                )
                return
            self.set_theme(args)

        reg("set", _set, "set an option (keymap=vsc|vim, theme=mocha)")
        reg("theme", _theme, "switch color theme (mocha|macchiato|frappe|latte)")
        reg("colorscheme", _theme, "alias for :theme")
        reg("vim", lambda args: self.select_keymap("vim"), "switch to vim key map")
        reg("vsc", lambda args: self.select_keymap("vsc"), "switch to the vsc key map")
        reg("normal", lambda args: self.select_keymap("vsc"), "alias for :vsc")
        reg("help", lambda args: self.show_help(), "show key map help")
        reg("manual", lambda args: self.show_manual(args or "en"),
            "open the user manual (:manual zh|en, default en)")
        reg("explorer", lambda args: self.toggle_explorer(), "toggle the file explorer")
        reg("font", lambda args: self._font_command(), "install the bundled Nerd Font")

    def toggle_explorer(self) -> None:
        self.explorer_visible = not self.explorer_visible
        self._sync_explorer_visibility()
        self.message(f"explorer {'shown' if self.explorer_visible else 'hidden'}")

    def _sync_explorer_visibility(self) -> None:
        visible = self.explorer_visible and self.workspace.root is not None
        if self.explorer_tree is not None:
            self.explorer_tree.display = visible
        if self.sidebar is not None:
            self.sidebar.display = visible

    def _font_command(self) -> None:
        status = fonts.ensure_font()
        self.message(status.detail or ("Nerd Font ready" if status.has_nerd_font
                                       else "font setup failed"),
                     kind="ok" if status.has_nerd_font else "error")

    def run_command(self, text: str) -> None:
        text = text.strip()
        if not text:
            return
        if text.startswith("!"):
            self.run_shell_command(text[1:])
            return
        parts = text.split()
        name, args = parts[0], " ".join(parts[1:])
        entry = self.commands.get(name)
        if entry is None:
            self.message(f"not an editor command: {name} (try :help)", kind="warn")
            return
        entry[0](args)

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
                yield EditorView(self, id="editor")
        with Vertical(id="bottom"):
            yield StatusBar(self, id="statusbar")
            yield PromptBar(self)

    def on_mount(self) -> None:
        """Wire up widgets, load extensions and apply the initial theme."""
        self.sidebar = self.query_one("#sidebar", Vertical)
        self.sidebar_head = self.query_one("#sidebar-head", Static)
        self.tabbar = self.query_one("#tabbar", Static)
        self.breadcrumbs = self.query_one("#breadcrumbs", Static)
        self.explorer_tree = self.query_one("#explorer", ExplorerTree)
        self.editor_view = self.query_one("#editor", EditorView)
        self.status_bar = self.query_one("#statusbar", StatusBar)
        self.prompt_bar = self.query_one(PromptBar)

        self._load_extensions()
        self.apply_theme()
        self.explorer_tree.refresh_tree()
        self._sync_explorer_visibility()
        self.editor_view.focus()

        if self._ext_messages:
            self.prompt_bar.show_message("; ".join(self._ext_messages), kind="warn")
        elif self.keymap_name == "vim":
            self.prompt_bar.idle("-- NORMAL --  (F1 help, : commands)")
        else:
            self.prompt_bar.idle(
                f"yate {__version__} — F1 help, Ctrl+P quick open, : for ex mode"
            )
        self.ui_refresh()

    # ================================================================ run

    def _load_extensions(self) -> None:
        def _report(records: list[LoadedExtension]) -> None:
            for record in records:
                if record.error:
                    self._ext_messages.append(f"extension {record.name}: {record.error}")

        # rc-declared paths load first (user rc then project rc), followed by
        # the default directories and explicit CLI paths.
        for path in self.config.extension_paths:
            if path.is_dir():
                _report(self.extension_loader.load_directory(path))
            elif path.is_file():
                _report([self.extension_loader.load_file(path)])
            else:
                self._ext_messages.append(f"extension path not found: {path}")
        directories = [
            *self._ext_dirs,
            Path.cwd() / "extensions",
            Path.home() / ".yate" / "extensions",
        ]
        for directory in directories:
            _report(self.extension_loader.load_directory(directory))
        for file in self._ext_files:
            _report([self.extension_loader.load_file(file)])
