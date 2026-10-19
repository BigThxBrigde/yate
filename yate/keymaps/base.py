"""Keymap infrastructure: bindings and dispatch context (L1).

The keymap layer must stay usable from anywhere (actions, extensions, tests):
it never imports widgets or the application.  Everything a keymap may touch
beyond the document itself is passed as a :class:`KeyUi` -- a concrete record
of UI callbacks built by the editor, so no host protocol is involved.

Key *notation* moved to the L0 leaf :mod:`yate.keymaps.keys` in the
2026-10-17 layer split; the four notation names are re-exported below so
the historical import surface keeps working.  L0 code (``keyproto/*``)
must import them from :mod:`yate.keymaps.keys` directly.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from yate.editor_core.buffer import TextBuffer
from yate.editor_core.document import Document
from yate.keymaps.keys import (
    KEY_ALIASES as KEY_ALIASES,
    SPECIAL_KEYS as SPECIAL_KEYS,
    key_name,
    parse_key,
)
from yate.session import EditorSession

#: What a direct (name-less) binding calls: the action body itself, handed the
#: :class:`ActionContext`.  A PEP 695 alias is lazily evaluated, so it may
#: precede the class it names.
type ActionFunc = Callable[[ActionContext], None]

#: ``execute_action(name)`` -- run an action by name; the result says whether
#: the editor knew it, so a key handler can fall through when it did not.
type ActionRunner = Callable[[str], bool]


@dataclass
class KeyBinding:
    """One key -> action binding, with metadata for the help system."""

    key: str  # raw key string (use parse_key for specs)
    action: str | ActionFunc  # action name or direct callable
    description: str = ""
    category: str = "general"

    @property
    def key_label(self) -> str:
        """Human readable form of the raw key (for the help overlay)."""
        return key_name(self.key)


@dataclass(frozen=True)
class KeyUi:
    """The UI callbacks a keymap may use (built by the editor).

    Callables instead of an interface keep the keymap layer free of widget
    and application types: it only ever sees the document session plus this
    record.
    """

    execute_action: ActionRunner
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
        """The document's text buffer."""
        return self.session.buffer

    @property
    def doc(self) -> Document:
        """The document being edited."""
        return self.session.doc


class Keymap:
    """Base class for key maps.

    Subclasses populate :attr:`bindings` (via :meth:`build_bindings`) and may
    override :meth:`handle_key` for stateful dispatch (vim).
    """

    name: str = "base"
    label: str = "Base"

    #: Raw keys this keymap consumes in hardcoded dispatch branches before
    #: the binding table is consulted, so a table entry on any of them can
    #: never dispatch.  Table-driven keymaps stay empty; stateful keymaps
    #: with hardcoded branches override (vim).  Consumed by
    #: :func:`yate.keymaps.conflicts.find_key_conflicts` via the caller.
    reserved_keys: frozenset[str] = frozenset()

    def chord_hints(self) -> tuple[tuple[str, str], ...]:
        """Next-key rows for the hardcoded chord in flight, if any.

        Stateful keymaps with hardcoded dispatch branches (vim) override
        this to describe what can follow the currently pending state --
        an armed operator lists its motions, a find prefix its ``{char}``
        follower, and so on -- so the which-key panel can list them
        key by key.  Each row is ``(label, description)`` where *label*
        is one next key, a ``{char}`` argument placeholder or a compact
        range like ``a-z``.  Table-driven keymaps hold no hardcoded state
        and return ``()``.
        """
        return ()

    def __init__(self) -> None:
        self.bindings: list[KeyBinding] = self.build_bindings()
        self._index: dict[str, KeyBinding] = {b.key: b for b in self.bindings}

    def build_bindings(self) -> list[KeyBinding]:
        """The keymap's binding table (empty in the base class)."""
        return []

    # ------------------------------------------------------------ extension

    @staticmethod
    def normalize_key(key_spec: str) -> str:
        """The raw key for *key_spec* (shared by add/remove/rollback paths)."""
        return parse_key(key_spec) if key_spec.startswith("<") or len(key_spec) == 1 else key_spec

    def add_binding(
        self,
        key_spec: str,
        action: str | ActionFunc,
        description: str = "extension binding",
        category: str = "extension",
    ) -> None:
        """Register an extra binding (used by the extension system).

        Re-registering a key replaces its previous binding in place: the
        stale entry is dropped from :attr:`bindings`, so consumers walking
        the list (the help overlay) show only the newest one.
        """
        raw = self.normalize_key(key_spec)
        binding = KeyBinding(raw, action, description, category)
        if raw in self._index:
            self.bindings = [b for b in self.bindings if b.key != raw]
        self.bindings.append(binding)
        self._index[raw] = binding

    def remove_binding(self, key_spec: str) -> bool:
        """Drop the binding for *key_spec*; ``False`` when it was unbound.

        The key is normalized exactly like :meth:`add_binding`, so a
        ``<named>`` or single-character spec removes the same entry the
        addition created.  Used by the extension loader to roll back a
        failed ``setup`` (architecture-boundaries rule 4, audit A13).
        """
        raw = self.normalize_key(key_spec)
        if raw not in self._index:
            return False
        del self._index[raw]
        self.bindings = [b for b in self.bindings if b.key != raw]
        return True

    def lookup(self, key: str) -> KeyBinding | None:
        """The binding for a raw key, or ``None`` when unbound."""
        return self._index.get(key)

    # -------------------------------------------------------------- dispatch

    def dispatch(self, binding: KeyBinding, ctx: ActionContext) -> bool:
        """Run *binding*'s action; ``False`` when the action is unknown.

        Direct callables run as-is; named actions go through
        :attr:`KeyUi.execute_action`, and a miss is reported to the user so
        the key counts as unhandled.
        """
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
        """Dispatch one key: a bound binding wins, else the unbound fallback."""
        binding = self.lookup(key)
        if binding is not None:
            return self.dispatch(binding, ctx)
        return self.handle_unbound(ctx, key)

    def handle_unbound(self, ctx: ActionContext, key: str) -> bool:
        """Default: printable characters insert themselves.

        The fallback goes through
        :meth:`~yate.editor_core.buffer.TextBuffer.type_char` rather than
        :meth:`~yate.editor_core.buffer.TextBuffer.insert_text`, so every
        modeless keymap inherits bracket auto-completion, closing-symbol
        skipping and selection wrapping; the active document's *filetype*
        travels with the call so the language rules stay in one place.

        While multi-cursor mode is active (the buffer has extra cursor
        points) printable characters insert at *every* point through
        :meth:`~yate.editor_core.buffer.TextBuffer.insert_at_points`
        instead: bracket auto-completion is a single-cursor
        :meth:`~yate.editor_core.buffer.TextBuffer.type_char` affordance
        and does not apply per point.
        """
        if ctx.buffer.has_extra_cursors() and len(key) == 1 and key.isprintable():
            ctx.buffer.insert_at_points(key)
            return True
        if len(key) == 1 and key.isprintable():
            ctx.buffer.type_char(key, language=ctx.doc.filetype)
            return True
        return False

    def pending_prefix(self) -> str:
        """The chord typed so far in human form (empty when nothing pends).

        Which-key surfaces read this after every dispatch to decide whether
        the pending-chord panel is visible.  The modeless base keymap never
        holds chord state, so it answers empty; stateful subclasses override.
        """
        return ""
