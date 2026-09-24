"""The built-in ``:`` command table.

The registry itself lives in :mod:`yate.registries` (a leaf module, also used
by the extension API); this module wires the built-in commands against a
concrete :class:`~yate.editor.Editor` -- the ex command line is the editor's
own command surface.
"""

from __future__ import annotations

from pathlib import Path

from yate.editor import Editor
from yate.editor_syntax import available_filetypes, language_name
from yate.registries import CommandRegistry

__all__ = ["CommandRegistry", "register_commands"]


def register_commands(registry: CommandRegistry, editor: Editor) -> None:
    """Register the built-in ex commands on *registry*."""
    reg = registry.register

    # ---- save / quit -------------------------------------------------------

    def _w(args: str) -> None:
        editor.save_document()

    def _q(args: str) -> None:
        editor.quit()

    def _qbang(args: str) -> None:
        editor.quit(force=True)

    def _wq(args: str) -> None:
        editor.save_document()
        # Only quit once the text is safely on disk: a failed save (I/O
        # error) or a still-pending save-as prompt leaves the document
        # modified, and force-quitting then would discard the work.
        if editor.session.doc.modified:
            return
        editor.quit()

    reg("w", _w, "save the current file")
    reg("write", _w, "save the current file")
    reg("q", _q, "quit yate")
    reg("quit", _q, "alias for :q")
    reg("q!", _qbang, "quit, discarding changes")
    reg("wq", _wq, "save and quit")

    # ---- panes -------------------------------------------------------------

    def _split(args: str) -> None:
        editor.split_with_path("horizontal", args)

    def _vsplit(args: str) -> None:
        editor.split_with_path("vertical", args)

    def _only(args: str) -> None:
        editor.only_pane()

    def _close(args: str) -> None:
        editor.close_pane()

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
            editor.open_path_later(Path(args))
        else:
            editor.prompt_open()

    def _enew(args: str) -> None:
        editor.new_buffer()

    def _welcome(args: str) -> None:
        editor.show_welcome()

    def _bn(args: str) -> None:
        editor.cycle_tab(1)

    def _bp(args: str) -> None:
        editor.cycle_tab(-1)

    def _bd(args: str) -> None:
        editor.close_tab()

    def _files(args: str) -> None:
        editor.open_file_palette()

    def _palette(args: str) -> None:
        editor.open_command_palette()

    def _trust(args: str) -> None:
        editor.trust_cwd_extensions()

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
    reg("trust", _trust,
        "trust the current workspace and load its ./extensions now")

    # ---- options / appearance ---------------------------------------------

    def _set(args: str) -> None:
        args = args.strip()
        if "=" not in args:
            editor.message(
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
            editor.set_filetype(value)
        elif key == "keymap":
            editor.select_keymap(value)
        elif key == "theme":
            editor.set_theme(value)
        elif key == "shell":
            editor.config.shell = value
            editor.message(
                "shell set; the new value applies to the next terminal "
                "(restart it with any key after exit)",
                kind="ok",
            )
        elif key == "terminal_height":
            try:
                height = int(value)
            except ValueError:
                editor.message("terminal_height must be an integer 3..40",
                               kind="warn")
                return
            if not 3 <= height <= 40:
                editor.message("terminal_height must be between 3 and 40",
                               kind="warn")
                return
            editor.config.terminal_height = height
            editor.terminal_panel.apply_height(height)
            editor.message(f"terminal height: {height} rows", kind="ok")
        elif key == "show_hidden":
            val = value.lower() in ("on", "true", "1", "yes")
            editor.set_show_hidden(val)
            editor.message(
                f"hidden files {'shown' if val else 'hidden'}", kind="ok"
            )
        else:
            editor.message(f"unknown option: {key}", kind="warn")

    def _theme(args: str) -> None:
        args = args.strip()
        if not args:
            editor.message(
                f"theme: {editor.theme_label()} · "
                f"available: {', '.join(editor.theme_names())}"
            )
            return
        editor.set_theme(args)

    def _filetype(args: str) -> None:
        args = args.strip()
        doc = editor.session.doc
        if not args:
            source = "manual override" if doc.filetype_override else "from path"
            label = language_name(doc.filetype)
            shown = f"{doc.filetype} ({label})" if label else doc.filetype
            editor.message(
                f"filetype: {shown} [{source}] · "
                f"available: {', '.join(available_filetypes())}"
            )
            return
        editor.set_filetype(args)

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
        editor.select_keymap("vim")

    def _vsc(args: str) -> None:
        editor.select_keymap("vsc")

    def _help(args: str) -> None:
        editor.show_help()

    def _manual(args: str) -> None:
        editor.show_manual(args or "en")

    def _changelog(args: str) -> None:
        editor.show_changelog(args or "en")

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
        editor.toggle_explorer()

    def _term(args: str) -> None:
        editor.terminal_panel.open()

    def _termclose(args: str) -> None:
        editor.terminal_panel.close()

    def _diagnostics(args: str) -> None:
        editor.show_diagnostics()

    def _font(args: str) -> None:
        editor.install_font()

    reg("explorer", _explorer, "toggle the file explorer")
    reg("term", _term, "open/focus the integrated terminal")
    reg("terminal", _term, "alias for :term (Ctrl+` toggles)")
    reg("termclose", _termclose, "hide the integrated terminal")
    reg("diagnostics", _diagnostics,
        "list language server diagnostics for the current file")
    reg("font", _font, "install the bundled Nerd Font")
