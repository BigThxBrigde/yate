"""The ``:`` command registry and the built-in ex command table.

Extracted from :mod:`yate.app`: :class:`CommandRegistry` is the plain
name -> handler store (also used by the extension API), while
:func:`register_commands` wires the built-in commands against a
:class:`~yate.app.YateApp` instance.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Callable, Optional

from yate.editor_syntax import available_filetypes, language_name
from yate.editor_view import theme

if TYPE_CHECKING:
    from yate.app import YateApp

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


def register_commands(app: "YateApp") -> None:
    """Register the built-in ex commands on *app*'s registry."""
    reg = app.commands.register
    reg("w", lambda args: app.save_document(), "save the current file")
    reg("write", lambda args: app.save_document(), "save the current file")
    reg("q", lambda args: app.quit(), "quit yate")
    reg("quit", lambda args: app.quit(), "alias for :q")
    reg("q!", lambda args: app.quit(force=True), "quit, discarding changes")

    def _wq(args: str) -> None:
        app.save_document()
        # Only quit once the text is safely on disk: a failed save (I/O
        # error) or a still-pending save-as prompt leaves the document
        # modified, and force-quitting then would discard the work.
        if app.doc.modified:
            return
        app.quit(force=True)

    reg("wq", _wq, "save and quit")

    def _split(args: str) -> None:
        app._split_with_path("horizontal", args)

    def _vsplit(args: str) -> None:
        app._split_with_path("vertical", args)

    reg("split", _split, "split the window horizontally (:sp [file])")
    reg("sp", _split, "alias for :split")
    reg("vsplit", _vsplit, "split the window vertically (:vs [file])")
    reg("vs", _vsplit, "alias for :vsplit")
    reg("only", lambda args: app._only_pane(),
        "close every other pane, keep the active one")
    reg("close", lambda args: app._close_pane(),
        "close the active pane (no-op on the last one; use :q to quit)")
    reg("cl", lambda args: app._close_pane(), "alias for :close")

    def _edit(args: str) -> None:
        args = args.strip()
        if args:
            app.open_path_later(Path(args))
        else:
            app.prompt_open()

    reg("e", _edit, "open a file or directory by path")
    reg("edit", _edit, "open a file or directory by path")
    reg("enew", lambda args: app.new_buffer(), "open a new empty buffer")
    reg("welcome", lambda args: app.show_welcome(),
        "show the welcome page again (on an empty unnamed buffer)")
    reg("bn", lambda args: app.cycle_tab(1), "next buffer/tab")
    reg("bnext", lambda args: app.cycle_tab(1), "next buffer/tab")
    reg("bp", lambda args: app.cycle_tab(-1), "previous buffer/tab")
    reg("bprev", lambda args: app.cycle_tab(-1), "previous buffer/tab")
    reg("bd", lambda args: app.close_tab(), "close current buffer/tab")
    reg("files", lambda args: app.open_file_palette(), "fuzzy quick file open (ctrl+p)")
    reg("palette", lambda args: app.open_command_palette(),
        "command palette (alt+shift+p)")

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
    reg("vim", lambda args: app.select_keymap("vim"), "switch to vim key map")
    reg("vsc", lambda args: app.select_keymap("vsc"), "switch to the vsc key map")
    reg("normal", lambda args: app.select_keymap("vsc"), "alias for :vsc")
    reg("help", lambda args: app.show_help(), "show key map help")
    reg("manual", lambda args: app.show_manual(args or "en"),
        "open the user manual (:manual zh|en, default en)")
    reg("changelog", lambda args: app.show_changelog(args or "en"),
        "open the changelog (:changelog zh|en, default en)")
    reg("explorer", lambda args: app.toggle_explorer(), "toggle the file explorer")
    reg("term", lambda args: app.open_terminal(), "open/focus the integrated terminal")
    reg("terminal", lambda args: app.open_terminal(),
        "alias for :term (Ctrl+` toggles)")
    reg("termclose", lambda args: app.close_terminal(), "hide the integrated terminal")
    reg("diagnostics", lambda args: app.show_diagnostics(),
        "list language server diagnostics for the current file")
    reg("font", lambda args: app._font_command(), "install the bundled Nerd Font")
