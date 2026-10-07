"""The built-in ``:`` command table.

The registry itself lives in :mod:`yate.registries` (a leaf module, also used
by the extension API); this module wires the built-in commands against a
concrete :class:`~yate.editor.Editor` -- the ex command line is the editor's
own command surface.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import cast

from yate.config import SET_OPTION_SPECS, SetOption
from yate.editor import Editor
from yate.editor_syntax import format_filetype_candidates, language_name
from yate.logs import tracing
from yate.registries import CommandRegistry

__all__ = ["CommandRegistry", "register_commands"]

log = tracing.get_logger(__name__)

#: ``:set`` lookup index: every accepted spelling -> its spec (A8 -- the
#: option knowledge lives in :data:`yate.config.SET_OPTION_SPECS` only).
#: Public so the guards in ``tests/test_set_options.py`` can pin the
#: table <-> apply contract without private access.
SET_OPTION_INDEX: dict[str, SetOption] = {
    spelling: spec
    for spec in SET_OPTION_SPECS
    for spelling in (spec.name, *spec.aliases)
}

#: The apply mapping: canonical option name -> how the editor applies the
#: parsed value (public for the same guard reason as
#: :data:`SET_OPTION_INDEX`).  Parsing and validation live in the option
#: table; this side effect layer (plus its success messages) is the L3
#: command duty.
SET_APPLY: dict[str, Callable[[Editor, object], None]] = {}


def _apply_filetype(editor: Editor, value: object) -> None:
    """Apply ``:set filetype`` (any spelling; empty/``auto`` re-detects)."""
    editor.set_filetype(cast(str, value))


def _apply_keymap(editor: Editor, value: object) -> None:
    """Apply ``:set keymap``."""
    editor.select_keymap(cast(str, value))


def _apply_theme(editor: Editor, value: object) -> None:
    """Apply ``:set theme``."""
    editor.set_theme(cast(str, value))


def _apply_shell(editor: Editor, value: object) -> None:
    """Apply ``:set shell`` (takes effect on the next terminal)."""
    editor.config.shell = cast(str, value)
    editor.message(
        "shell set; the new value applies to the next terminal "
        "(restart it with any key after exit)",
        kind="ok",
    )


def _apply_terminal_height(editor: Editor, value: object) -> None:
    """Apply ``:set terminal_height`` (rows, 3..40)."""
    height = cast(int, value)
    editor.config.terminal_height = height
    editor.terminal_panel.apply_height(height)
    editor.message(f"terminal height: {height} rows", kind="ok")


def _apply_show_hidden(editor: Editor, value: object) -> None:
    """Apply ``:set show_hidden``."""
    shown = cast(bool, value)
    editor.set_show_hidden(shown)
    editor.message(f"hidden files {'shown' if shown else 'hidden'}", kind="ok")


def _apply_readonly(editor: Editor, value: object) -> None:
    """Apply ``:set readonly`` (the view reports the state itself)."""
    editor.set_readonly(cast(bool, value))


def _apply_support_mouse(editor: Editor, value: object) -> None:
    """Apply ``:set support_mouse`` (the event gate reads it per dispatch)."""
    enabled = cast(bool, value)
    editor.config.support_mouse = enabled
    editor.message(f"mouse support {'on' if enabled else 'off'}", kind="ok")


SET_APPLY.update(
    filetype=_apply_filetype,
    keymap=_apply_keymap,
    theme=_apply_theme,
    shell=_apply_shell,
    terminal_height=_apply_terminal_height,
    show_hidden=_apply_show_hidden,
    readonly=_apply_readonly,
    support_mouse=_apply_support_mouse,
)


def _strip_quotes(text: str) -> str:
    """Strip one surrounding quote pair from *text* when present.

    Only a matching ``"`` or ``'`` pair that wraps the whole string is
    removed; an unpaired quote, a single character or an empty string is
    returned unchanged, so unquoted paths with spaces keep working.
    """
    if len(text) >= 2 and text[0] in "\"'" and text[0] == text[-1]:
        return text[1:-1]
    return text


def _split_paths(args: str) -> list[str]:
    """Split an ex argument string into path tokens, quote-aware.

    Whitespace separates tokens unless it sits inside a ``"`` or ``'``
    section; the quote characters themselves are stripped and never appear
    in a token.  An unclosed quote keeps everything up to the end of the
    line as a single token (best effort for a forgotten closing quote).
    Empty tokens produced by adjacent quotes are discarded.
    """
    tokens: list[str] = []
    buf: list[str] = []
    quote: str | None = None
    for ch in args:
        if quote is not None:
            if ch == quote:
                quote = None
            else:
                buf.append(ch)
        elif ch in "\"'":
            quote = ch
        elif ch.isspace():
            if buf:
                tokens.append("".join(buf))
                buf = []
        else:
            buf.append(ch)
    if buf:
        tokens.append("".join(buf))
    return tokens


def register_commands(registry: CommandRegistry, editor: Editor) -> None:
    """Register the built-in ex commands on *registry*."""
    reg = registry.register

    # ---- save / quit -------------------------------------------------------

    def _w(args: str) -> None:
        editor.document_flows.save_document()

    def _saveas(args: str) -> None:
        editor.document_flows.save_as(_strip_quotes(args.strip()) or None)

    def _q(args: str) -> None:
        editor.quit()

    def _qbang(args: str) -> None:
        editor.quit(force=True)

    def _wq(args: str) -> None:
        editor.document_flows.save_document()
        # Only quit once the text is safely on disk: a failed save (I/O
        # error) or a still-pending save-as prompt leaves the document
        # modified, and force-quitting then would discard the work.
        if editor.session.doc.modified:
            return
        editor.quit()

    reg("w", _w, "save the current file")
    reg("write", _w, "save the current file")
    reg("saveas", _saveas,
        "save the buffer under a new path (:saveas FILE; blank = prompt)")
    reg("q", _q, "quit yate")
    reg("quit", _q, "alias for :q")
    reg("q!", _qbang, "quit, discarding changes")
    reg("wq", _wq, "save and quit")

    # ---- panes -------------------------------------------------------------

    def _split(args: str) -> None:
        editor.window_flows.split_with_path("horizontal", _strip_quotes(args))

    def _vsplit(args: str) -> None:
        editor.window_flows.split_with_path("vertical", _strip_quotes(args))

    def _only(args: str) -> None:
        editor.window_flows.only_pane()

    def _close(args: str) -> None:
        editor.window_flows.close_pane()

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
        args = _strip_quotes(args.strip())
        if args:
            editor.document_flows.open_path_later(Path(args))
        else:
            editor.document_flows.prompt_open()

    def _enew(args: str) -> None:
        editor.document_flows.new_buffer()

    def _welcome(args: str) -> None:
        editor.document_flows.show_welcome()

    def _bn(args: str) -> None:
        editor.document_flows.cycle_tab(1)

    def _bp(args: str) -> None:
        editor.document_flows.cycle_tab(-1)

    def _bd(args: str) -> None:
        editor.document_flows.close_tab()

    def _files(args: str) -> None:
        editor.overlays.open_file_palette()

    def _palette(args: str) -> None:
        editor.overlays.open_command_palette()

    def _trust(args: str) -> None:
        editor.extension_flows.trust_cwd_extensions()

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
                "usage: :set " + "  ".join(spec.summary for spec in SET_OPTION_SPECS),
                kind="warn",
            )
            return
        key, _, value = args.partition("=")
        key = key.strip()
        value = value.strip()
        spec = SET_OPTION_INDEX.get(key)
        if spec is None:
            log.warning("set rejected: unknown option %r", key)
            editor.message(f"unknown option: {key}", kind="warn")
            return
        parsed = spec.parse(value)
        if parsed is None:
            editor.message(spec.invalid_message, kind="warn")
            return
        apply = SET_APPLY.get(spec.name)
        if apply is None:
            # The specs/apply invariant is pinned by
            # test_set_option_specs_cover_all_dispatched_options; this
            # runtime guard keeps a forgotten apply entry from crashing
            # the command line with a bare KeyError (PR !61 review M1).
            log.error("set missing apply handler for %r", spec.name)
            editor.message(
                f"internal error: no handler for {spec.name}", kind="warn"
            )
            return
        apply(editor, parsed)

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
                f"available: {format_filetype_candidates()}"
            )
            return
        editor.set_filetype(args)

    reg("set", _set,
        "set an option (keymap, theme, shell, terminal_height, filetype, "
        "readonly)")
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
        editor.overlays.show_help()

    def _manual(args: str) -> None:
        editor.overlays.show_manual(args or "en")

    def _changelog(args: str) -> None:
        editor.overlays.show_changelog(args or "en")

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
        editor.lsp_sync.show_diagnostics()

    def _font(args: str) -> None:
        editor.shell.install_font()

    reg("explorer", _explorer, "toggle the file explorer")
    reg("term", _term, "open/focus the integrated terminal")
    reg("terminal", _term, "alias for :term (Ctrl+` toggles)")
    reg("termclose", _termclose, "hide the integrated terminal")
    reg("diagnostics", _diagnostics,
        "list language server diagnostics for the current file")
    reg("font", _font, "install the bundled Nerd Font")

    # ---- diff ---------------------------------------------------------------

    def _diff(args: str) -> None:
        tokens = _split_paths(args)
        three = False
        names: list[str] = []
        for token in tokens:
            if token in ("-3", "--3way"):
                three = True
            else:
                names.append(token)
        if len(names) == 2 and three:
            editor.message("--3way needs three files", kind="warn")
            return
        if len(names) not in (2, 3):
            editor.message(
                "usage: :diff [--3way] FILE1 FILE2 [FILE3] "
                "(quote paths with spaces)",
                kind="warn",
            )
            return
        editor.overlays.open_diff([
            editor.document_flows.resolve_input_path(Path(p)) for p in names
        ])

    reg("diff", _diff, "compare files in a diff view (:diff [--3way] F1 F2 [F3])")

    log.info("builtin commands registered: %d", len(registry.names()))
