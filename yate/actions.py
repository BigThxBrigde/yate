"""The built-in action table.

Actions are named operations (``"save"``, ``"move_left"`` ...) decoupled from
keys: key maps bind keys to action names, the command line calls them by
name, and extensions can register new ones.

The registry itself lives in :mod:`yate.registries` (a leaf module); this
module wires the built-in table against a concrete :class:`~yate.editor.Editor`:
editing actions work on :attr:`ActionContext.buffer`, session-level actions
call the editor's operations.
"""

from __future__ import annotations

from yate.editor import Editor
from yate.keymaps.base import ActionContext
from yate.logs import tracing
from yate.registries import Action, ActionRegistry
from yate.services import clipboard

__all__ = ["Action", "ActionRegistry", "populate"]

log = tracing.get_logger(__name__)


def populate(registry: ActionRegistry, editor: Editor) -> None:
    """Register all built-in actions on *registry*.

    Editing actions work on :attr:`ActionContext.buffer`; session-level
    actions call *editor* (the running editor).
    """
    reg = registry.register

    # ------------------------------------------------------------- editing

    reg("newline", lambda ctx: ctx.buffer.insert_newline(), "Insert newline (auto-indent)")
    reg("insert_tab", lambda ctx: ctx.buffer.insert_tab(), "Indent / insert tab")
    reg("delete_backward", lambda ctx: ctx.buffer.delete_backward(), "Delete char before cursor")
    reg("delete_forward", lambda ctx: ctx.buffer.delete_forward(), "Delete char after cursor")
    reg("delete_word_back", lambda ctx: ctx.buffer.delete_backward(word=True), "Delete word back")
    reg("delete_word_fwd", lambda ctx: ctx.buffer.delete_forward(word=True), "Delete word forward")
    reg(
        "delete_to_line_start",
        lambda ctx: ctx.buffer.delete_to_line_start(),
        "Delete to line start",
    )
    reg("duplicate_line", lambda ctx: ctx.buffer.duplicate_line(), "Duplicate line / selection")
    reg("delete_line", lambda ctx: ctx.buffer.delete_lines(), "Delete line")
    reg("move_line_up", lambda ctx: ctx.buffer.move_line(-1), "Move line up")
    reg("move_line_down", lambda ctx: ctx.buffer.move_line(1), "Move line down")
    reg("indent", lambda ctx: ctx.buffer.indent_selection(), "Indent")
    reg("outdent", lambda ctx: ctx.buffer.outdent_selection(), "Outdent")
    reg("join_lines", lambda ctx: ctx.buffer.join_lines(), "Join lines")

    # ---------------------------------------------------------- navigation

    reg("move_left", lambda ctx: ctx.buffer.move_left(), "Move left")
    reg("move_right", lambda ctx: ctx.buffer.move_right(), "Move right")
    reg("move_up", lambda ctx: ctx.buffer.move_up(), "Move up")
    reg("move_down", lambda ctx: ctx.buffer.move_down(), "Move down")
    reg("move_word_left", lambda ctx: ctx.buffer.move_left(word=True), "Move word left")
    reg("move_word_right", lambda ctx: ctx.buffer.move_right(word=True), "Move word right")
    reg("line_start", lambda ctx: ctx.buffer.move_line_start(), "Go to line start")
    reg("line_end", lambda ctx: ctx.buffer.move_line_end(), "Go to line end")
    reg("doc_start", lambda ctx: ctx.buffer.move_doc_start(), "Go to document start")
    reg("doc_end", lambda ctx: ctx.buffer.move_doc_end(), "Go to document end")
    reg("page_up", lambda ctx: editor.page(-1), "Page up")
    reg("page_down", lambda ctx: editor.page(1), "Page down")
    reg("page_half_up", lambda ctx: editor.page(-1, half=True), "Half page up")
    reg("page_half_down", lambda ctx: editor.page(1, half=True), "Half page down")

    # ----------------------------------------------------------- selection

    reg("select_left", lambda ctx: ctx.buffer.move_left(select=True), "Select left")
    reg("select_right", lambda ctx: ctx.buffer.move_right(select=True), "Select right")
    reg("select_up", lambda ctx: ctx.buffer.move_up(select=True), "Select up")
    reg("select_down", lambda ctx: ctx.buffer.move_down(select=True), "Select down")
    reg(
        "select_word_left",
        lambda ctx: ctx.buffer.move_left(select=True, word=True),
        "Select word left",
    )
    reg(
        "select_word_right",
        lambda ctx: ctx.buffer.move_right(select=True, word=True),
        "Select word right",
    )
    reg(
        "select_line_start",
        lambda ctx: ctx.buffer.move_line_start(select=True, toggle=False),
        "Select to line start",
    )
    reg("select_line_end", lambda ctx: ctx.buffer.move_line_end(select=True), "Select to line end")
    reg("select_all", lambda ctx: ctx.buffer.select_all(), "Select all")
    reg("clear_selection", lambda ctx: ctx.buffer.clear_selection(), "Clear selection")

    # ------------------------------------------------------- history/clip

    reg("undo", lambda ctx: ctx.buffer.undo(), "Undo")
    reg("redo", lambda ctx: ctx.buffer.redo(), "Redo")

    def cut(ctx: ActionContext) -> None:
        """Cut the selection (or the whole line) into the system clipboard.

        The internal register is kept in sync too, so a clipboard-unavailable
        fallback still behaves like before.  An empty text never reaches the
        system clipboard, so a doomed cut cannot wipe the user's copy.
        """
        buf = ctx.buffer
        if buf.has_selection():
            buf.register = buf.selected_text() or ""
            buf.delete_selection()
            if buf.register:
                clipboard.copy_text(buf.register)
        else:
            text = buf.delete_lines()
            if text:
                clipboard.copy_text(text)

    def copy(ctx: ActionContext) -> None:
        """Yank the selection (or the whole line) into the system clipboard.

        An empty yank updates the register but skips the system clipboard.
        """
        buf = ctx.buffer
        if buf.has_selection():
            text = buf.yank_selection()
        else:
            text = buf.yank_lines()
        if text:
            clipboard.copy_text(text)

    def paste(ctx: ActionContext) -> None:
        """Paste from the system clipboard, falling back to the register.

        When the system clipboard is unavailable (or empty), the internal
        unnamed register is pasted as before.  A read-only buffer skips the
        clipboard read and the register priming entirely -- a doomed paste
        mirrors the vim-side ``_prime_paste`` guard and pays no system call.
        """
        buf = ctx.buffer
        if not buf.read_only:
            text = clipboard.paste_text()
            if text:
                buf.register = text
        buf.paste()

    reg("cut", cut, "Cut")
    reg("copy", copy, "Copy")
    reg("paste", paste, "Paste")

    # --------------------------------------------------------------- files

    reg("save", lambda ctx: editor.document_flows.save_document(), "Save file")
    reg("open_prompt", lambda ctx: editor.document_flows.prompt_open(),
        "Open file by path")
    reg("new_buffer", lambda ctx: editor.document_flows.new_buffer(),
        "New empty buffer")
    reg("close_tab", lambda ctx: editor.document_flows.close_tab(),
        "Close current tab")
    reg("quit", lambda ctx: editor.quit(), "Quit yate")

    # -------------------------------------------------------------- search

    reg("find", lambda ctx: editor.prompt_flows.find_prompt(True), "Find")
    reg("find_next", lambda ctx: editor.prompt_flows.find_next(True),
        "Next match")
    reg("find_prev", lambda ctx: editor.prompt_flows.find_next(False),
        "Previous match")
    reg("replace", lambda ctx: editor.prompt_flows.replace_prompt(),
        "Find & replace")

    # ---------------------------------------------------------------- view

    reg("command_prompt", lambda ctx: editor.command_prompt(), "Ex command prompt")
    reg("goto_prompt", lambda ctx: editor.prompt_flows.goto_prompt(),
        "Go to line (enter a line number)")
    reg("quick_open", lambda ctx: editor.overlays.open_file_palette(),
        "Quick file open")
    reg("command_palette", lambda ctx: editor.overlays.open_command_palette(),
        "Command palette")
    reg("focus_explorer", lambda ctx: editor.focus_explorer(), "Focus explorer")
    reg("focus_editor", lambda ctx: editor.focus_editor(), "Focus editor")
    reg("toggle_explorer", lambda ctx: editor.toggle_explorer(), "Toggle explorer")
    reg("manual", lambda ctx: editor.overlays.show_manual(), "Open the user manual")
    reg("shell_prompt", lambda ctx: editor.shell.open_prompt(), "Run shell command")
    reg("prev_tab", lambda ctx: editor.document_flows.cycle_tab(-1),
        "Previous tab")
    reg("next_tab", lambda ctx: editor.document_flows.cycle_tab(1), "Next tab")
    reg("help", lambda ctx: editor.overlays.show_help(), "Keyboard shortcuts help")
    reg("toggle_keymap", lambda ctx: editor.toggle_keymap(), "Toggle vsc/vim keymap")
    reg(
        "toggle_screensaver",
        lambda ctx: editor.overlays.toggle_screensaver(),
        "Toggle the idle screensaver",
    )

    log.info("builtin actions populated: %d", len(registry.names()))
