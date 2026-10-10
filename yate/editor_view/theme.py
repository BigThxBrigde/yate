"""Theme broadcast hub and facade for editor_view (Rich / Textual).

This module owns the *active theme* singleton and the 1:N broadcast
mechanism: :func:`set_theme` switches the process-global theme (like vim's
``colorscheme``) and fans the change out to every subscriber registered via
:func:`subscribe` / :func:`attach`.  Widgets own their theme painting: they
subscribe on mount and unsubscribe on unmount.

The theme data itself lives in :mod:`yate.editor_view.themes` (the
:class:`Theme` class, the built-in palettes, the registry and the Textual
bridge), the character geometry helpers in
:mod:`yate.editor_view.cells` and the custom theme file loader in
:mod:`yate.editor_view.theme_files`.  All public symbols of those modules are
re-exported here (big-module-split wave d facade), so the historical import
surface -- ``from yate.editor_view import theme`` and
``from yate.editor_view.theme import THEMES`` in the docs -- keeps working
unchanged.

Import direction (acyclic): ``cells`` depends on nothing; ``themes`` on
:mod:`yate.editor_syntax.tokens`; ``theme_files`` on ``themes``; this module
on all three; everybody else imports this module.
"""

from __future__ import annotations

from collections.abc import Callable

from textual.widget import Widget

from yate.logs import tracing

from yate.editor_view.cells import (
    cell_len,
    cell_to_char,
    cell_width,
    char_to_cell,
    expand_char,
    truncate_to_cells,
)
from yate.editor_view.theme_files import (
    _theme_namespace,
    load_theme_file,
    load_theme_paths,
)
from yate.editor_view.themes import (
    DEFAULT_THEME,
    TEXTUAL_THEME_PREFIX,
    THEMES,
    Theme,
    available,
    register_theme,
    textual_theme_name,
    to_textual_theme,
    validate_theme,
)

__all__ = [
    "DEFAULT_THEME",
    "TEXTUAL_THEME_PREFIX",
    "THEMES",
    "Theme",
    "ThemeListener",
    "Unsubscribe",
    # private by naming convention; see theme_files.__all__ (wave-a precedent)
    "_theme_namespace",
    "active",
    "attach",
    "available",
    "cell_len",
    "cell_to_char",
    "cell_width",
    "char_to_cell",
    "detach",
    "expand_char",
    "load_theme_file",
    "load_theme_paths",
    "register_theme",
    "set_theme",
    "subscribe",
    "textual_theme_name",
    "to_textual_theme",
    "truncate_to_cells",
    "validate_theme",
]

log = tracing.get_logger(__name__)

_active: Theme = THEMES[DEFAULT_THEME]


def active() -> Theme:
    """Return the currently active :class:`Theme`."""
    return _active


def set_theme(name: str) -> Theme:
    """Switch the active theme by name and notify subscribers.

    :raises KeyError: if no theme called *name* is registered.
    """
    # The active theme is intentionally process-global state (like vim's
    # colorscheme): every widget reads it through :func:`active`.
    global _active
    if name not in THEMES:
        raise KeyError(f"unknown theme: {name!r} (have: {', '.join(sorted(THEMES))})")
    _active = THEMES[name]
    _notify()
    return _active


#: A theme-change subscriber: widgets hand their repaint callable to
#: :func:`attach` and keep the returned :data:`Unsubscribe` for ``on_unmount``.
type ThemeListener = Callable[[], None]

#: What :func:`subscribe` gives back -- call it once to detach that listener
#: again.  Same shape as :data:`ThemeListener` but the opposite intent: it
#: *removes* a subscription instead of receiving a broadcast.
type Unsubscribe = Callable[[], None]

#: Subscribers notified (synchronously) after a successful :func:`set_theme`.
#: Widgets own their theme painting: they subscribe on mount and unsubscribe
#: on unmount (rule "1:N low-frequency broadcast -> callback list").
_listeners: list[ThemeListener] = []


def subscribe(listener: ThemeListener) -> Unsubscribe:
    """Register *listener* for theme changes; return its unsubscribe function.

    An equal listener (e.g. the same widget's bound method, should its
    ``on_mount`` ever fire twice) is collapsed into one entry, so a single
    ``unsubscribe`` call fully detaches it.  The returned callable removes
    the listener again (idempotent: removing an unknown listener is a
    no-op), so widgets can unsubscribe in their ``on_unmount`` without
    coordination.
    """
    if listener not in _listeners:
        _listeners.append(listener)

    def _unsubscribe() -> None:
        try:
            _listeners.remove(listener)
        except ValueError:
            pass

    return _unsubscribe


def _notify() -> None:
    """Fan the theme change out to every subscriber, isolating failures.

    One misbehaving listener must not block the broadcast, so each call is
    guarded and logged; the exception is never re-raised.
    """
    for listener in list(_listeners):
        try:
            listener()
        except Exception as exc:  # noqa: BLE001 - isolate one bad subscriber
            log.warning(
                "theme listener failed: %s: %s", type(exc).__name__, exc
            )


def attach(widget: Widget, repaint: ThemeListener) -> None:
    """Subscribe *widget* to theme broadcasts (call from ``on_mount``).

    Stores the unsubscribe hook on *widget* as ``_theme_unsubscribe`` --
    the attribute every self-painting component declares.  The assignment
    goes through ``setattr`` (same explicit-intent pattern as
    :func:`yate.editor_view.scrollbars.apply_slim_scrollbars`) because the
    hook lives on concrete widget classes, not on :class:`Widget` itself,
    and a lookup protocol would violate the R2 architecture rule.
    :func:`detach` undoes it from the unmount path.
    """
    setattr(widget, "_theme_unsubscribe", subscribe(repaint))


def detach(widget: Widget) -> None:
    """Unsubscribe *widget* from theme broadcasts (idempotent unmount)."""
    hook = getattr(widget, "_theme_unsubscribe", None)
    if callable(hook):
        hook()
    setattr(widget, "_theme_unsubscribe", None)
