"""VS Code style key map for yate (modeless)."""

from __future__ import annotations

from yate.keymaps.base import KeyBinding, Keymap, parse_key

# help categories (module level: uppercase constants)
EDIT = "Editing"
NAV = "Navigation"
SEL = "Selection"
HIST = "History"
FILE = "File"
SRCH = "Search"
VIEW = "View"
TAB = "Tabs"
HELP = "Help"


def _k(spec: str, action: str, description: str, category: str) -> KeyBinding:
    return KeyBinding(parse_key(spec), action, description, category)


def _raw(raw: str, action: str, description: str, category: str) -> KeyBinding:
    return KeyBinding(raw, action, description, category)


class VscKeymap(Keymap):
    """Modeless key map mirroring common VS Code shortcuts."""

    name = "vsc"
    label = "VS Code"

    def build_bindings(self) -> list[KeyBinding]:
        return [
            # ---- editing
            _k("<enter>", "newline", "Insert newline (auto-indent)", EDIT),
            _k("<tab>", "insert_tab", "Indent / insert tab", EDIT),
            _k("<backspace>", "delete_backward", "Delete character before cursor", EDIT),
            _k("<delete>", "delete_forward", "Delete character after cursor", EDIT),
            _k("<alt-backspace>", "delete_word_back", "Delete word before cursor", EDIT),
            _k("<alt-d>", "delete_word_fwd", "Delete word after cursor", EDIT),
            _k("<ctrl-d>", "duplicate_line", "Duplicate current line / selection", EDIT),
            _k("<ctrl-shift-k>", "delete_line", "Delete current line", EDIT),
            _raw("\x1b[1;3A", "move_line_up", "Move line up", EDIT),
            _raw("\x1b[1;3B", "move_line_down", "Move line down", EDIT),
            _k("<ctrl-]>", "indent", "Indent line / selection", EDIT),
            _raw("\x1b[Z", "outdent", "Outdent line / selection", EDIT),
            _k("<ctrl-j>", "join_lines", "Join lines", EDIT),
            # ---- navigation
            _k("<left>", "move_left", "Move cursor left", NAV),
            _k("<right>", "move_right", "Move cursor right", NAV),
            _k("<up>", "move_up", "Move cursor up", NAV),
            _k("<down>", "move_down", "Move cursor down", NAV),
            _raw("\x1b[1;5D", "move_word_left", "Move one word left", NAV),
            _raw("\x1b[1;5C", "move_word_right", "Move one word right", NAV),
            _k("<home>", "line_start", "Go to line start", NAV),
            _k("<end>", "line_end", "Go to line end", NAV),
            _raw("\x1b[1~", "line_start", "Go to line start", NAV),
            _raw("\x1b[4~", "line_end", "Go to line end", NAV),
            _raw("\x1b[1;5H", "doc_start", "Go to document start", NAV),
            _raw("\x1b[1;5F", "doc_end", "Go to document end", NAV),
            _k("<pageup>", "page_up", "Page up", NAV),
            _k("<pagedown>", "page_down", "Page down", NAV),
            # ---- selection
            _raw("\x1b[1;2D", "select_left", "Select left", SEL),
            _raw("\x1b[1;2C", "select_right", "Select right", SEL),
            _raw("\x1b[1;2A", "select_up", "Select up", SEL),
            _raw("\x1b[1;2B", "select_down", "Select down", SEL),
            _raw("\x1b[1;6D", "select_word_left", "Select word left", SEL),
            _raw("\x1b[1;6C", "select_word_right", "Select word right", SEL),
            _raw("\x1b[1;2H", "select_line_start", "Select to line start", SEL),
            _raw("\x1b[1;2F", "select_line_end", "Select to line end", SEL),
            _k("<ctrl-a>", "select_all", "Select all", SEL),
            _k("<esc>", "clear_selection", "Clear selection", SEL),
            # ---- history / clipboard
            _k("<ctrl-z>", "undo", "Undo", HIST),
            _k("<ctrl-y>", "redo", "Redo", HIST),
            _k("<ctrl-x>", "cut", "Cut selection / line", HIST),
            _k("<ctrl-c>", "copy", "Copy selection / line", HIST),
            _k("<ctrl-v>", "paste", "Paste", HIST),
            # ---- file
            _k("<ctrl-s>", "save", "Save file", FILE),
            _k("<ctrl-o>", "open_prompt", "Open file by path", FILE),
            _k("<ctrl-n>", "new_buffer", "New empty buffer", FILE),
            _k("<ctrl-w>", "close_tab", "Close current tab", FILE),
            _k("<ctrl-q>", "quit", "Quit yate", FILE),
            _k(":", "command_prompt", "Ex command prompt (:w :q :e ...)", FILE),
            # ---- search
            _k("<ctrl-f>", "find", "Find", SRCH),
            _k("<f3>", "find_next", "Next match", SRCH),
            _k("<f4>", "replace", "Find & replace", SRCH),
            # ---- view / tools
            _k("<ctrl-p>", "quick_open", "Quick file open (ctrl+p)", VIEW),
            _k("<alt-shift-p>", "command_palette", "Command palette (alt+shift+p)", VIEW),
            _raw("\x1f", "toggle_keymap", "Toggle vsc/vim keymap (ctrl+/)", VIEW),
            _k("<ctrl-e>", "focus_explorer", "Focus file explorer", VIEW),
            _k("<ctrl-b>", "toggle_explorer", "Toggle file explorer", VIEW),
            _k("<f2>", "shell_prompt", "Run shell command", VIEW),
            _raw("\x1b[5;5~", "prev_tab", "Previous tab", TAB),
            _raw("\x1b[6;5~", "next_tab", "Next tab", TAB),
            _k("<f1>", "help", "Keyboard shortcuts help", HELP),
            _k("<f8>", "manual", "Open user manual (read-only)", HELP),
        ]
