"""Key and mouse dispatch routing for the editor.

Module-level functions parameterized by ``ed: Editor``; the
:class:`yate.editor.Editor` class keeps thin delegates for its public
dispatch surface and forwards here.  No ``self.app`` attribute chains
(architecture guard ``test_flow_modules_hold_no_app_handle`` scans
top-level ``yate/*.py``): the app handle is reached via ``ed.app``
(Editor is the L3 sole App holder).  The functions are editor-private
(consumed only by :mod:`yate.editor`); they are listed in ``__all__`` so
importing them from editor.py reads as deliberate to pyright
(editor_compose ``__all__`` precedent), and ``import yate.editor`` sits
at the end of this file so either import order stays safe.
"""

from __future__ import annotations

from textual.events import Key, MouseEvent

from yate.editor_components.editor import EditorView
from yate.editor_components.terminal import TOGGLE_KEYS
from yate.editor_core import BufferReadOnlyError
from yate.keymaps.base import ActionContext
from yate.keyproto.key_codec import event_to_raw
from yate.logs import tracing

#: Trace logger ("yate.editor_dispatch"); silent unless yate_trace is on.
log = tracing.get_logger(__name__)

__all__ = [
    "_cancel_mouse_state",
    "_execute_action",
    "_handle_key",
    "_handle_raw_key",
    "_insert_char",
    "_on_view_mouse",
    "_readonly_notice",
]


def _handle_key(ed: yate.editor.Editor, event: Key) -> bool:
    """Dispatch one key event; returns ``True`` when it was consumed.

    Called both by the editor view (keys typed in a pane) and by the
    application shell (keys that bubble up from other widgets).  The
    dispatch is not side-effect free: the window flows arm and clear
    the ``ctrl+w`` pending chord (``window_flows.try_window_prefix``)
    and the completion-popup branch commits the highlighted candidate
    (``completion.accept``).  A ``True`` return means the caller must
    stop the event (R10) instead of letting it bubble into a second
    dispatch.
    """
    if ed.has_modal_screen():
        return False  # a modal screen owns input
    # Entry-level evidence: YATE_TRACE turns this into the ground truth of
    # what event.key names a real terminal actually delivers (field reports
    # and pilot synthesis can disagree; the log settles which side erred).
    log.debug(
        "key event: key=%s character=%r focused=%s",
        event.key,
        event.character,
        type(ed.app.focused).__name__ if ed.app.focused else None,
    )
    editor_focused = isinstance(ed.app.focused, EditorView)
    # Ctrl+Space = manual completion. Checked BEFORE the terminal toggle.
    # The NUL byte splits by driver: the legacy conhost path collapses
    # Ctrl+Space / Ctrl+` / Ctrl+2 into one NUL byte that Textual names
    # "ctrl+@" -- ambiguous, so with the editor focused it favors
    # completion (Ctrl+` still closes the panel while the terminal is
    # focused).  The chord driver keeps the chords distinct -- it names
    # Ctrl+Space "ctrl+space" and the Ctrl+@ key (what the grave chord
    # looks like on layouts where the physical ` sits on Shift+2)
    # "ctrl+2"/"ctrl+shift+2"; those toggle the terminal via TOGGLE_KEYS
    # below.
    nul_keys = ("ctrl+space", "ctrl+@")
    # The command line owns its Input: ctrl+space must not open the
    # completion popup over it and must keep flowing to the prompt bar
    # (the active_mode branch below hands the event back to the Input).
    if event.key in nul_keys and not ed.prompt_bar.active_mode:
        if editor_focused or event.key == "ctrl+space":
            ed.completion.request(manual=True)
            return True
    if event.key in TOGGLE_KEYS and event.key not in nul_keys:
        ed.terminal_panel.toggle()
        return True
    # The completion popup owns a handful of keys while it is open; it
    # never takes focus itself, so the keys arrive here.  Every other key
    # falls through to the normal dispatch below: typing keeps filtering
    # the candidates (``handle_raw_key`` ends in
    # ``completion.after_editor_key``, which re-queries) and the global
    # chords stay usable while the popup is up.
    popup = ed.completion_popup
    if popup.is_open:
        if event.key in ("tab", "enter"):
            ed.completion.accept()
            return True
        if event.key == "up":
            popup.select_prev()
            return True
        if event.key == "down":
            popup.select_next()
            return True
        if event.key == "escape":
            popup.close()
            return True
    # vim ctrl+w window chord (armed or pending); before the other
    # chords so the prefix is consumed wherever focus currently is.
    # The panel follows via window_flows.on_chord_change -- no manual
    # refresh here, the chord state owner notifies on every flip.
    if ed.window_flows.try_window_prefix(event):
        return True
    # Global chords that raw byte dispatch cannot represent reliably.
    # alt+shift+p is the default: Windows Terminal reserves ctrl+shift+p
    # for its own command palette, and ctrl+shift+a clashes with other
    # terminal emulators; alt+shift+p is unbound in both.
    if event.key == "alt+shift+p":
        ed.overlays.open_command_palette()
        return True
    if ed.prompt_bar.active_mode:
        # command line is editing; enter must bubble so the Input's own
        # enter->submit binding can fire
        return False
    # alt+shift+s toggles the screensaver: alt+shift combos have no raw
    # byte form (keyproto.key_codec maps only single-modifier alt chords),
    # so like alt+shift+p this must be intercepted by key name.  Kept
    # below the prompt check: typing a :command must never toggle it.
    if event.key == "alt+shift+s":
        ed.execute_action("toggle_screensaver")
        return True
    # alt+shift+f opens the file manager overlay: same alt+shift shape
    # as the two chords above (no raw byte form, keymap row is
    # help-only), so the real dispatch is by key name here.  The call
    # itself goes through the action registry, so rebinding/wrapping
    # the "file_manager" action takes effect.
    if event.key == "alt+shift+f":
        ed.execute_action("file_manager")
        return True
    # vscode-style pane focus chords (CSI-u encodings, not in the raw
    # byte table)
    if event.key == "ctrl+shift+e":
        ed.focus_explorer()
        return True
    if event.key == "ctrl+1":
        ed.focus_editor()
        return True
    if event.key == "ctrl+p":
        ed.overlays.open_file_palette()
        return True
    if ed.explorer_focused():
        return False  # explorer consumes its own keys
    raw = event_to_raw(event.key, event.character)
    if raw is None:
        # Unmapped names are normal (exotic terminals, widgets without a
        # raw form), so this stays a debug log: YATE_TRACE turns it into
        # evidence when chasing missing-key reports.
        log.debug("unmapped key event: %s (character=%r)", event.key, event.character)
        return False
    return ed.handle_raw_key(raw)


def _handle_raw_key(ed: yate.editor.Editor, raw: str) -> bool:
    """Dispatch one raw key to the active keymap, then refresh the UI."""
    try:
        handled = ed.keymaps.active.handle_key(
            ActionContext(ed.session, ed.key_ui), raw
        )
    except BufferReadOnlyError:
        # Typing / vim operators / edit actions on a read-only buffer:
        # the key is consumed (R10) with a notice instead of an edit.
        ed.readonly_notice()
        return True
    # Unconsumed keys pay nothing: only a handled key changed editor
    # state worth repainting (plan-f P3).  The completion feed stays
    # unconditional -- the popup needs every raw key even when the
    # keymap ignored it.
    if handled:
        ed.refresh_ui()
    ed.completion.after_editor_key(raw)
    return handled


def _on_view_mouse(ed: yate.editor.Editor, leaf_id: int, event: MouseEvent) -> bool:
    """Dispatch one mouse event for the view of *leaf_id*."""
    view = ed.panes.views.get(leaf_id)
    if view is None:
        return False
    return ed.mouse_flows.handle_view_mouse(view, event)


def _cancel_mouse_state(ed: yate.editor.Editor) -> None:
    """Drop every in-flight mouse interaction (``:set support_mouse
    off`` mid-drag): the app gate now drops all mouse events, so no
    MouseUp path can release captures or clear drag flags."""
    ed.app.capture_mouse(None)  # view or PaneHost capture, whoever holds it
    ed.mouse_flows.cancel_drag()
    host = ed.panes.host
    if host is not None:
        host.cancel_drag()


def _execute_action(ed: yate.editor.Editor, name: str) -> bool:
    """Run a registered action by name; ``False`` when it is unknown.

    Called by keymaps (which report an unknown name and let the key fall
    through), the palette and the extension bridge.  A refused edit on a
    read-only buffer also reports ``True`` (the request was consumed,
    with a user notice) instead of propagating the error.
    """
    try:
        handled = ed.actions.execute(
            name, ActionContext(ed.session, ed.key_ui)
        )
        if not handled:
            log.debug("action not found: %s", name)
        return handled
    except BufferReadOnlyError:
        ed.readonly_notice()
        # the refused action may have moved the cursor / changed anchors
        # before raising; repaint so the view never goes stale
        ed.refresh_ui()
        return True


def _readonly_notice(ed: yate.editor.Editor) -> None:
    """User feedback for an edit refused on a read-only buffer."""
    ed.message(
        "buffer is read-only (:set readonly=false to unlock)", kind="warn"
    )


def _insert_char(ed: yate.editor.Editor, ch: str) -> None:
    """Insert one character at the cursor (keymap ``insert_char``)."""
    ed.session.buffer.insert_text(ch)


# Placed after the functions on purpose: editor.py imports these names at
# its top, so a direct `import yate.editor_dispatch` must not re-enter
# editor.py before they exist (import-cycle order safety).  The
# annotation references are lazy strings, so no earlier runtime binding
# is needed.
import yate.editor
