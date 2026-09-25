"""Keymap infrastructure: key notation, bindings and dispatch context.

The keymap layer must stay usable from anywhere (actions, extensions, tests):
it never imports widgets or the application.  Everything a keymap may touch
beyond the document itself is passed as a :class:`KeyUi` -- a concrete record
of UI callbacks built by the editor, so no host protocol is involved.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Optional, Union

from yate.editor_core.buffer import TextBuffer
from yate.editor_core.document import Document
from yate.session import EditorSession

# ---------------------------------------------------------------------------
# Key notation
#
# Human readable key specs (used by binding tables and extension scripts):
#   "<ctrl-x>" "<alt-x>" "<shift-x>" "<f1>" "<enter>" "<esc>" "<tab>"
#   "<backspace>" "<up>" "<down>" "<left>" "<right>" "<home>" "<end>"
#   "<pageup>" "<pagedown>" "<delete>" "<space>"
# Plain characters are written literally:  "a", "1", ":", "/".
# ---------------------------------------------------------------------------

SPECIAL_KEYS: dict[str, str] = {
    "enter": "\r",
    "return": "\r",
    "esc": "\x1b",
    "escape": "\x1b",
    "tab": "\t",
    "space": " ",
    "backspace": "\x7f",
    "delete": "\x1b[3~",
    "insert": "\x1b[2~",
    "up": "\x1b[A",
    "down": "\x1b[B",
    "right": "\x1b[C",
    "left": "\x1b[D",
    "home": "\x1b[H",
    "end": "\x1b[F",
    "pageup": "\x1b[5~",
    "pagedown": "\x1b[6~",
    "f1": "\x1bOP",
    "f2": "\x1bOQ",
    "f3": "\x1bOR",
    "f4": "\x1bOS",
    "f5": "\x1b[15~",
    "f6": "\x1b[17~",
    "f7": "\x1b[18~",
    "f8": "\x1b[19~",
    "f9": "\x1b[20~",
    "f10": "\x1b[21~",
    "f11": "\x1b[23~",
    "f12": "\x1b[24~",
}

# Common terminal variants not covered by the canonical names.
KEY_ALIASES: dict[str, str] = {
    "\x1b[1~": "home",
    "\x1b[4~": "end",
    "\x1b[1;5D": "ctrl-left",
    "\x1b[1;5C": "ctrl-right",
    "\x1b[1;2D": "shift-left",
    "\x1b[1;2C": "shift-right",
    "\x1b[1;2A": "shift-up",
    "\x1b[1;2B": "shift-down",
    "\x1b[1;6D": "ctrl-shift-left",
    "\x1b[1;6C": "ctrl-shift-right",
    "\x1b[1;5H": "ctrl-home",
    "\x1b[1;5F": "ctrl-end",
    "\x1b[1;2H": "shift-home",
    "\x1b[1;2F": "shift-end",
    "\x1b[5;5~": "ctrl-pageup",
    "\x1b[6;5~": "ctrl-pagedown",
    "\x1b[1;3A": "alt-up",
    "\x1b[1;3B": "alt-down",
    "\x1b[1;3C": "alt-right",
    "\x1b[1;3D": "alt-left",
    "\x1b[Z": "shift-tab",
}


def parse_key(spec: str) -> str:
    """Parse a human key spec (``"<ctrl-s>"``) into a raw key string."""
    if not (spec.startswith("<") and spec.endswith(">")):
        return spec
    body = spec[1:-1].lower()
    tokens = body.split("-")
    modifiers = set(tokens[:-1])
    name = tokens[-1]

    if name in SPECIAL_KEYS:
        base = SPECIAL_KEYS[name]
    elif len(name) == 1:
        base = name
    else:
        raise ValueError(f"unknown key name in spec: {spec!r}")

    if "shift" in modifiers:
        if len(base) == 1:
            base = base.upper()
    if "alt" in modifiers:
        base = "\x1b" + base
    if "ctrl" in modifiers:
        if len(base) != 1:
            raise ValueError(f"ctrl requires a single character: {spec!r}")
        ch = base.upper()
        if ch == " ":
            base = "\x00"
        elif "@" <= ch <= "_":
            # ctrl-@ .. ctrl-_ map to codes 0x00 .. 0x1f (covers letters,
            # brackets etc. the same way a real terminal encodes them).
            base = chr(ord(ch) - 64)
        elif "0" <= ch <= "9":
            # ctrl+digits have no C0 code; encode as the kitty keyboard
            # protocol CSI-u sequence modern terminals send
            base = f"\x1b[{ord(ch)};5u"
        else:
            raise ValueError(f"unsupported ctrl key: {spec!r}")
    return base


def key_name(key: str) -> str:
    """Inverse of :func:`parse_key`, used by the help overlay."""
    if key in KEY_ALIASES:
        return "<" + KEY_ALIASES[key] + ">"
    for name, raw in SPECIAL_KEYS.items():
        if raw == key and name not in ("return", "escape"):
            return "<" + name + ">"
    if len(key) == 1:
        code = ord(key)
        if code == 0:
            return "<ctrl-space>"
        if 1 <= code <= 26:
            return f"<ctrl-{chr(code + ord('a') - 1)}>"
        if key == " ":
            return "<space>"
        return key
    if key.startswith("\x1b") and len(key) == 2:
        return f"<alt-{key[1]}>"
    m = re.fullmatch(r"\x1b\[(\d+);(\d+)u", key)
    if m:
        code, mod = int(m.group(1)), int(m.group(2))
        mods: list[str] = []
        if mod & 1:
            mods.append("shift")
        if mod & 2:
            mods.append("alt")
        if mod & 4:
            mods.append("ctrl")
        mods.append(chr(code))
        return "<" + "-".join(mods) + ">"
    return repr(key)


ActionFunc = Callable[["ActionContext"], None]


@dataclass
class KeyBinding:
    """One key -> action binding, with metadata for the help system."""

    key: str  # raw key string (use parse_key for specs)
    action: Union[str, ActionFunc]  # action name or direct callable
    description: str = ""
    category: str = "general"

    @property
    def key_label(self) -> str:
        return key_name(self.key)


@dataclass(frozen=True)
class KeyUi:
    """The UI callbacks a keymap may use (built by the editor).

    Callables instead of an interface keep the keymap layer free of widget
    and application types: it only ever sees the document session plus this
    record.
    """

    execute_action: Callable[[str], bool]
    message: Callable[[str], None]
    command_prompt: Callable[[], None]
    find_prompt: Callable[[bool], None]
    goto_prompt: Callable[[], None]
    toggle_keymap: Callable[[], None]


class ActionContext:
    """Passed to every action: the document session plus the UI callbacks."""

    def __init__(self, session: EditorSession, ui: KeyUi) -> None:
        self.session = session
        self.ui = ui

    @property
    def buffer(self) -> TextBuffer:
        return self.session.buffer

    @property
    def doc(self) -> Document:
        return self.session.doc


class Keymap:
    """Base class for key maps.

    Subclasses populate :attr:`bindings` (via :meth:`build_bindings`) and may
    override :meth:`handle_key` for stateful dispatch (vim).
    """

    name: str = "base"
    label: str = "Base"

    def __init__(self) -> None:
        self.bindings: list[KeyBinding] = self.build_bindings()
        self._index: dict[str, KeyBinding] = {b.key: b for b in self.bindings}

    def build_bindings(self) -> list[KeyBinding]:
        return []

    # ------------------------------------------------------------ extension

    def add_binding(
        self,
        key_spec: str,
        action: Union[str, ActionFunc],
        description: str = "extension binding",
        category: str = "extension",
    ) -> None:
        """Register an extra binding (used by the extension system).

        Re-registering a key replaces its previous binding in place: the
        stale entry is dropped from :attr:`bindings`, so consumers walking
        the list (the help overlay) show only the newest one.
        """
        raw = parse_key(key_spec) if key_spec.startswith("<") or len(key_spec) == 1 else key_spec
        binding = KeyBinding(raw, action, description, category)
        if raw in self._index:
            self.bindings = [b for b in self.bindings if b.key != raw]
        self.bindings.append(binding)
        self._index[raw] = binding

    def lookup(self, key: str) -> Optional[KeyBinding]:
        return self._index.get(key)

    # -------------------------------------------------------------- dispatch

    def dispatch(self, binding: KeyBinding, ctx: ActionContext) -> bool:
        action = binding.action
        if callable(action):
            action(ctx)
            return True
        if ctx.ui.execute_action(action):
            return True
        # An unregistered name -- a typo in a user binding, or an action whose
        # extension was unloaded -- used to swallow the key silently.  Name it
        # and report the key as unhandled so the other handlers still see it.
        ctx.ui.message(f"unknown action: {action}")
        return False

    def handle_key(self, ctx: ActionContext, key: str) -> bool:
        binding = self.lookup(key)
        if binding is not None:
            return self.dispatch(binding, ctx)
        return self.handle_unbound(ctx, key)

    def handle_unbound(self, ctx: ActionContext, key: str) -> bool:
        """Default: printable characters insert themselves."""
        if len(key) == 1 and key.isprintable():
            ctx.buffer.insert_text(key)
            return True
        return False
