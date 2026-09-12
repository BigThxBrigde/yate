"""Action registry and the built-in action table.

Actions are named operations (``"save"``, ``"move_left"`` ...) decoupled from
keys: key maps bind keys to action names, the command line calls them by
name, and extensions can register new ones.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List

from yate.keymaps.base import ActionContext


@dataclass
class Action:
    """A named operation registered in :class:`ActionRegistry`."""

    name: str
    func: Callable[[ActionContext], object]
    description: str


class ActionRegistry:
    """Maps action names to zero-argument-in-spirit context callables."""

    def __init__(self) -> None:
        self._actions: Dict[str, Action] = {}

    def register(
        self, name: str, func: Callable[[ActionContext], object], description: str = ""
    ) -> None:
        """Add (or replace) the action *name*."""
        self._actions[name] = Action(name, func, description)

    def get(self, name: str) -> Action | None:
        """Return the :class:`Action` for *name*, or ``None``."""
        return self._actions.get(name)

    def execute(self, name: str, ctx: ActionContext) -> bool:
        """Run *name* with *ctx*; returns ``False`` for unknown names."""
        action = self._actions.get(name)
        if action is None:
            return False
        action.func(ctx)
        return True

    def names(self) -> List[str]:
        """Sorted list of registered action names."""
        return sorted(self._actions)

    def describe(self) -> list[tuple[str, str]]:
        """Sorted ``(name, description)`` pairs for the help system."""
        return sorted((a.name, a.description) for a in self._actions.values())


def populate(registry: ActionRegistry) -> None:
    """Register all built-in actions."""
    reg = registry.register

    # ------------------------------------------------------------- editing

    reg("newline", lambda ctx: ctx.buffer.insert_newline(), "Insert newline (auto-indent)")
    reg("insert_tab", lambda ctx: ctx.buffer.insert_tab(), "Indent / insert tab")
    reg("delete_backward", lambda ctx: ctx.buffer.delete_backward(), "Delete char before cursor")
    reg("delete_forward", lambda ctx: ctx.buffer.delete_forward(), "Delete char after cursor")
    reg("delete_word_back", lambda ctx: ctx.buffer.delete_backward(word=True), "Delete word back")
    reg("delete_word_fwd", lambda ctx: ctx.buffer.delete_forward(word=True), "Delete word forward")
    reg("delete_to_line_start", lambda ctx: ctx.buffer.delete_to_line_start(), "Delete to line start")
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
    reg("page_up", lambda ctx: ctx.app.page(-1), "Page up")
    reg("page_down", lambda ctx: ctx.app.page(1), "Page down")
    reg("page_half_up", lambda ctx: ctx.app.page(-1, half=True), "Half page up")
    reg("page_half_down", lambda ctx: ctx.app.page(1, half=True), "Half page down")

    # ----------------------------------------------------------- selection

    reg("select_left", lambda ctx: ctx.buffer.move_left(select=True), "Select left")
    reg("select_right", lambda ctx: ctx.buffer.move_right(select=True), "Select right")
    reg("select_up", lambda ctx: ctx.buffer.move_up(select=True), "Select up")
    reg("select_down", lambda ctx: ctx.buffer.move_down(select=True), "Select down")
    reg("select_word_left", lambda ctx: ctx.buffer.move_left(select=True, word=True), "Select word left")
    reg("select_word_right", lambda ctx: ctx.buffer.move_right(select=True, word=True), "Select word right")
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
        """Cut the selection (or the whole line) into the register."""
        buf = ctx.buffer
        if buf.has_selection():
            buf.register = buf.selected_text() or ""
            buf.delete_selection()
        else:
            buf.delete_lines()

    def copy(ctx: ActionContext) -> None:
        """Yank the selection (or the whole line) into the register."""
        buf = ctx.buffer
        if buf.has_selection():
            buf.yank_selection()
        else:
            buf.yank_lines()

    reg("cut", cut, "Cut")
    reg("copy", copy, "Copy")
    reg("paste", lambda ctx: ctx.buffer.paste(), "Paste")

    # --------------------------------------------------------------- files

    reg("save", lambda ctx: ctx.app.save_document(), "Save file")
    reg("open_prompt", lambda ctx: ctx.app.prompt_open(), "Open file by path")
    reg("new_buffer", lambda ctx: ctx.app.new_buffer(), "New empty buffer")
    reg("close_tab", lambda ctx: ctx.app.close_tab(), "Close current tab")
    reg("quit", lambda ctx: ctx.app.quit(), "Quit yate")

    # -------------------------------------------------------------- search

    reg("find", lambda ctx: ctx.app.find_prompt(True), "Find")
    reg("find_next", lambda ctx: ctx.app.find_next(True), "Next match")
    reg("find_prev", lambda ctx: ctx.app.find_next(False), "Previous match")
    reg("replace", lambda ctx: ctx.app.replace_prompt(), "Find & replace")

    # ---------------------------------------------------------------- view

    reg("command_prompt", lambda ctx: ctx.app.command_prompt(), "Ex command prompt")
    reg("goto_prompt", lambda ctx: ctx.app.goto_prompt(), "Go to line (enter a line number)")
    reg("quick_open", lambda ctx: ctx.app.open_file_palette(), "Quick file open")
    reg("command_palette", lambda ctx: ctx.app.open_command_palette(), "Command palette")
    reg("focus_explorer", lambda ctx: ctx.app.focus_explorer(), "Focus explorer")
    reg("focus_editor", lambda ctx: ctx.app.focus_editor(), "Focus editor")
    reg("toggle_explorer", lambda ctx: ctx.app.toggle_explorer(), "Toggle explorer")
    reg("manual", lambda ctx: ctx.app.show_manual(), "Open the user manual")
    reg("shell_prompt", lambda ctx: ctx.app.shell_prompt(), "Run shell command")
    reg("prev_tab", lambda ctx: ctx.app.cycle_tab(-1), "Previous tab")
    reg("next_tab", lambda ctx: ctx.app.cycle_tab(1), "Next tab")
    reg("help", lambda ctx: ctx.app.show_help(), "Keyboard shortcuts help")
    reg("toggle_keymap", lambda ctx: ctx.app.toggle_keymap(), "Toggle vsc/vim keymap")
