"""The ``:`` command registry and the built-in ex command table.

:class:`CommandRegistry` is the plain name -> handler store (also used by
the extension API); :func:`register_commands` wires the built-in commands
against a :class:`CommandHost` -- the narrow application surface the ex
command table drives.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional, Protocol

from yate.config import YateConfig
from yate.editor_core import Document
from yate.editor_syntax import available_filetypes, language_name
from yate.editor_view.pane_types import Axis


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


class CommandHost(Protocol):
    """The application surface the built-in ex commands drive."""

    commands: CommandRegistry
    config: YateConfig

    @property
    def doc(self) -> Document: ...

    def message(self, text: str, kind: str = "info") -> None: ...

    def save_document(self) -> None: ...

    def quit(self, force: bool = False) -> None: ...

    def split_with_path(self, axis: Axis, args: str) -> None: ...

    def only_pane(self) -> None: ...

    def close_pane(self) -> None: ...

    def open_path_later(self, path: Path) -> None: ...

    def prompt_open(self) -> None: ...

    def new_buffer(self, show: bool = True) -> None: ...

    def show_welcome(self) -> None: ...

    def cycle_tab(self, delta: int) -> None: ...

    def close_tab(self) -> None: ...

    def open_file_palette(self) -> None: ...

    def open_command_palette(self) -> None: ...

    def set_filetype(self, value: str) -> None: ...

    def select_keymap(self, name: str) -> None: ...

    def set_theme(self, name: str) -> None: ...

    def theme_label(self) -> str: ...

    def theme_names(self) -> list[str]: ...

    def apply_terminal_height(self, height: int) -> None: ...

    def set_show_hidden(self, flag: bool) -> None: ...

    def toggle_explorer(self) -> None: ...

    def open_terminal(self) -> None: ...

    def close_terminal(self) -> None: ...

    def show_diagnostics(self) -> None: ...

    def install_font(self) -> None: ...

    def show_help(self) -> None: ...

    def show_manual(self, lang: str = "en") -> None: ...

    def show_changelog(self, lang: str = "en") -> None: ...


def register_commands(host: CommandHost) -> None:
    """Register the built-in ex commands on *host*'s registry."""
    reg = host.commands.register

    # ---- save / quit -------------------------------------------------------

    def _w(args: str) -> None:
        host.save_document()

    def _q(args: str) -> None:
        host.quit()

    def _qbang(args: str) -> None:
        host.quit(force=True)

    def _wq(args: str) -> None:
        host.save_document()
        # Only quit once the text is safely on disk: a failed save (I/O
        # error) or a still-pending save-as prompt leaves the document
        # modified, and force-quitting then would discard the work.
        if host.doc.modified:
            return
        host.quit()

    reg("w", _w, "save the current file")
    reg("write", _w, "save the current file")
    reg("q", _q, "quit yate")
    reg("quit", _q, "alias for :q")
    reg("q!", _qbang, "quit, discarding changes")
    reg("wq", _wq, "save and quit")

    # ---- panes -------------------------------------------------------------

    def _split(args: str) -> None:
        host.split_with_path("horizontal", args)

    def _vsplit(args: str) -> None:
        host.split_with_path("vertical", args)

    def _only(args: str) -> None:
        host.only_pane()

    def _close(args: str) -> None:
        host.close_pane()

    reg("split", _split, "split the window horizontally (:sp [file])")
    reg("sp", _split, "alias for :split")
    reg("vsplit", _vsplit, "split the window vertically (:vs [file])")
    reg("vs", _vsplit, "alias for :vsplit")
    reg("only", _only,
        "close every other pane, keep the active one")
    reg("close", _close,
        "close the active pane (no-op on the last one; use :q to quit)")
    reg("cl", _close, "alias for :close")

    # ---- open / buffers ----------------------------------------------------

    def _edit(args: str) -> None:
        args = args.strip()
        if args:
            host.open_path_later(Path(args))
        else:
            host.prompt_open()

    def _enew(args: str) -> None:
        host.new_buffer()

    def _welcome(args: str) -> None:
        host.show_welcome()

    def _bn(args: str) -> None:
        host.cycle_tab(1)

    def _bp(args: str) -> None:
        host.cycle_tab(-1)

    def _bd(args: str) -> None:
        host.close_tab()

    def _files(args: str) -> None:
        host.open_file_palette()

    def _palette(args: str) -> None:
        host.open_command_palette()

    reg("e", _edit, "open a file or directory by path")
    reg("edit", _edit, "open a file or directory by path")
    reg("enew", _enew, "open a new empty buffer")
    reg("welcome", _welcome,
        "show the welcome page again (on an empty unnamed buffer)")
    reg("bn", _bn, "next buffer/tab")
    reg("bnext", _bn, "next buffer/tab")
    reg("bp", _bp, "previous buffer/tab")
    reg("bprev", _bp, "previous buffer/tab")
    reg("bd", _bd, "close current buffer/tab")
    reg("files", _files, "fuzzy quick file open (ctrl+p)")
    reg("palette", _palette, "command palette (alt+shift+p)")

    # ---- options / appearance ---------------------------------------------

    def _set(args: str) -> None:
        args = args.strip()
        if "=" not in args:
            host.message(
                "usage: :set keymap=vsc|vim  theme=mocha  shell=powershell  "
                "terminal_height=12  filetype=py (auto = detect)  "
                "show_hidden=on|off",
                kind="warn",
            )
            return
        key, _, value = args.partition("=")
        key = key.strip()
        value = value.strip()
        if key in ("filetype", "ft", "language", "lang"):
            host.set_filetype(value)
        elif key == "keymap":
            host.select_keymap(value)
        elif key == "theme":
            host.set_theme(value)
        elif key == "shell":
            host.config.shell = value
            host.message(
                "shell set; the new value applies to the next terminal "
                "(restart it with any key after exit)",
                kind="ok",
            )
        elif key == "terminal_height":
            try:
                height = int(value)
            except ValueError:
                host.message("terminal_height must be an integer 3..40",
                             kind="warn")
                return
            if not 3 <= height <= 40:
                host.message("terminal_height must be between 3 and 40",
                             kind="warn")
                return
            host.config.terminal_height = height
            host.apply_terminal_height(height)
            host.message(f"terminal height: {height} rows", kind="ok")
        elif key == "show_hidden":
            val = value.lower() in ("on", "true", "1", "yes")
            host.set_show_hidden(val)
            host.message(
                f"hidden files {'shown' if val else 'hidden'}", kind="ok"
            )
        else:
            host.message(f"unknown option: {key}", kind="warn")

    def _theme(args: str) -> None:
        args = args.strip()
        if not args:
            host.message(
                f"theme: {host.theme_label()} · "
                f"available: {', '.join(host.theme_names())}"
            )
            return
        host.set_theme(args)

    def _filetype(args: str) -> None:
        args = args.strip()
        if not args:
            doc = host.doc
            source = "manual override" if doc.filetype_override else "from path"
            label = language_name(doc.filetype)
            shown = f"{doc.filetype} ({label})" if label else doc.filetype
            host.message(
                f"filetype: {shown} [{source}] · "
                f"available: {', '.join(available_filetypes())}"
            )
            return
        host.set_filetype(args)

    reg("set", _set,
        "set an option (keymap, theme, shell, terminal_height, filetype)")
    reg("filetype", _filetype,
        "set syntax/filetype (:filetype python; auto = detect; no arg lists all)")
    reg("ft", _filetype, "alias for :filetype")
    reg("language", _filetype, "alias for :filetype")
    reg("theme", _theme, "switch color theme by name (:theme lists all)")
    reg("colorscheme", _theme, "alias for :theme")

    # ---- keymap / help ----------------------------------------------------

    def _vim(args: str) -> None:
        host.select_keymap("vim")

    def _vsc(args: str) -> None:
        host.select_keymap("vsc")

    def _help(args: str) -> None:
        host.show_help()

    def _manual(args: str) -> None:
        host.show_manual(args or "en")

    def _changelog(args: str) -> None:
        host.show_changelog(args or "en")

    reg("vim", _vim, "switch to vim key map")
    reg("vsc", _vsc, "switch to the vsc key map")
    reg("normal", _vsc, "alias for :vsc")
    reg("help", _help, "show key map help")
    reg("manual", _manual,
        "open the user manual (:manual zh|en, default en)")
    reg("changelog", _changelog,
        "open the changelog (:changelog zh|en, default en)")

    # ---- explorer / terminal / diagnostics -------------------------------

    def _explorer(args: str) -> None:
        host.toggle_explorer()

    def _term(args: str) -> None:
        host.open_terminal()

    def _termclose(args: str) -> None:
        host.close_terminal()

    def _diagnostics(args: str) -> None:
        host.show_diagnostics()

    def _font(args: str) -> None:
        host.install_font()

    reg("explorer", _explorer, "toggle the file explorer")
    reg("term", _term, "open/focus the integrated terminal")
    reg("terminal", _term, "alias for :term (Ctrl+` toggles)")
    reg("termclose", _termclose, "hide the integrated terminal")
    reg("diagnostics", _diagnostics,
        "list language server diagnostics for the current file")
    reg("font", _font, "install the bundled Nerd Font")
