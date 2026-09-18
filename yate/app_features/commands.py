"""The ``:`` command registry and the built-in ex command table.

Extracted from :mod:`yate.app`: :class:`CommandRegistry` is the plain
name -> handler store (also used by the extension API), while
:func:`register_commands` wires the built-in commands against a
:class:`~yate.app.YateApp` instance.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from yate.editor_syntax import available_filetypes, language_name
from yate.editor_view import theme
from yate.interfaces import AppProtocol

# Extracted YateApp collaborator: touching the app's private helpers/state
# is this module's contract (Python has no friend classes).
# pyright: reportPrivateUsage=false


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


def register_commands(app: AppProtocol) -> None:
    """Register the built-in ex commands on *app*'s registry."""
    reg = app.commands.register

    # ---- save / quit -------------------------------------------------------

    def _w(args: str) -> None:
        app.save_document()

    def _q(args: str) -> None:
        app.quit()

    def _qbang(args: str) -> None:
        app.quit(force=True)

    def _wq(args: str) -> None:
        app.save_document()
        # Only quit once the text is safely on disk: a failed save (I/O
        # error) or a still-pending save-as prompt leaves the document
        # modified, and force-quitting then would discard the work.
        if app.doc.modified:
            return
        app.quit()

    reg("w", _w, "save the current file")
    reg("write", _w, "save the current file")
    reg("q", _q, "quit yate")
    reg("quit", _q, "alias for :q")
    reg("q!", _qbang, "quit, discarding changes")
    reg("wq", _wq, "save and quit")

    # ---- panes -------------------------------------------------------------

    def _split(args: str) -> None:
        app._split_with_path("horizontal", args)

    def _vsplit(args: str) -> None:
        app._split_with_path("vertical", args)

    def _only(args: str) -> None:
        app._only_pane()

    def _close(args: str) -> None:
        app._close_pane()

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
            app.open_path_later(Path(args))
        else:
            app.prompt_open()

    def _enew(args: str) -> None:
        app.new_buffer()

    def _welcome(args: str) -> None:
        app.show_welcome()

    def _bn(args: str) -> None:
        app.cycle_tab(1)

    def _bp(args: str) -> None:
        app.cycle_tab(-1)

    def _bd(args: str) -> None:
        app.close_tab()

    def _files(args: str) -> None:
        app.open_file_palette()

    def _palette(args: str) -> None:
        app.open_command_palette()

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
            app.message(
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
            app.set_filetype(value)
        elif key == "keymap":
            app.select_keymap(value)
        elif key == "theme":
            app.set_theme(value)
        elif key == "shell":
            app.config.shell = value
            app.message(
                "shell set; the new value applies to the next terminal "
                "(restart it with any key after exit)",
                kind="ok",
            )
        elif key == "terminal_height":
            try:
                height = int(value)
            except ValueError:
                app.message("terminal_height must be an integer 3..40",
                            kind="warn")
                return
            if not 3 <= height <= 40:
                app.message("terminal_height must be between 3 and 40",
                            kind="warn")
                return
            app.config.terminal_height = height
            if app.terminal_panel is not None and app._terminal_visible:
                app.terminal_panel.styles.height = height
            app.message(f"terminal height: {height} rows", kind="ok")
        elif key == "show_hidden":
            val = value.lower() in ("on", "true", "1", "yes")
            app.workspace.show_hidden = val
            if app.explorer_tree is not None:
                app.explorer_tree.refresh_tree()
            app.message(
                f"hidden files {'shown' if val else 'hidden'}", kind="ok"
            )
        else:
            app.message(f"unknown option: {key}", kind="warn")

    def _theme(args: str) -> None:
        args = args.strip()
        if not args:
            current = theme.active()
            app.message(
                f"theme: {current.label} ({current.name}) · "
                f"available: {', '.join(theme.available())}"
            )
            return
        app.set_theme(args)

    def _filetype(args: str) -> None:
        args = args.strip()
        if not args:
            doc = app.doc
            source = "manual override" if doc.filetype_override else "from path"
            label = language_name(doc.filetype)
            shown = f"{doc.filetype} ({label})" if label else doc.filetype
            app.message(
                f"filetype: {shown} [{source}] · "
                f"available: {', '.join(available_filetypes())}"
            )
            return
        app.set_filetype(args)

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
        app.select_keymap("vim")

    def _vsc(args: str) -> None:
        app.select_keymap("vsc")

    def _help(args: str) -> None:
        app.show_help()

    def _manual(args: str) -> None:
        app.show_manual(args or "en")

    def _changelog(args: str) -> None:
        app.show_changelog(args or "en")

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
        app.toggle_explorer()

    def _term(args: str) -> None:
        app.open_terminal()

    def _termclose(args: str) -> None:
        app.close_terminal()

    def _diagnostics(args: str) -> None:
        app.show_diagnostics()

    def _font(args: str) -> None:
        app._font_command()

    reg("explorer", _explorer, "toggle the file explorer")
    reg("term", _term, "open/focus the integrated terminal")
    reg("terminal", _term, "alias for :term (Ctrl+` toggles)")
    reg("termclose", _termclose, "hide the integrated terminal")
    reg("diagnostics", _diagnostics,
        "list language server diagnostics for the current file")
    reg("font", _font, "install the bundled Nerd Font")
