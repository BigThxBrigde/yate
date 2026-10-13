"""Editor event subscription hub for extension scripts.

A single :class:`EventHub` instance is constructed by the editor and
injected into both the extension API (``api.events``) and the flow modules
that emit; it is *not* a module-level global bus (architecture-boundaries
section 4).  Event identities are :class:`EditorEvent` enum members, never
ad-hoc strings, so a typo is a loud ``AttributeError`` instead of a silent
no-op subscription.

Dispatch contract: synchronous, same-thread, in subscription order.  One
failing listener is reported (trace log + message line) and never prevents
the remaining listeners or the editor operation that triggered the emit --
the hub is the single guard point, so every listener is safe regardless of
who subscribed it.

Emissions live at low-frequency points (save / open / close / activate /
diagnostics / keymap / theme), never on the per-keystroke path.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum, auto

from yate.editor_core import Document
from yate.logs import tracing

#: Trace logger ("yate.services.events"); silent unless yate_trace is on.
log = tracing.get_logger(__name__)

#: Extension-supplied listener of open shape (user-code boundary: the hub
#: forwards payloads without inspecting the callable, mirroring the
#: ``AnyCallback`` precedent in :mod:`yate.services.extensions.api`).
type EventCallback = Callable[..., object]

#: Report a listener failure on the message line (single-argument form;
#: the editor injects ``lambda text: ed.message(text)``).
type FailureReporter = Callable[[str], None]


class EditorEvent(Enum):
    """Editor events an extension can subscribe to (``api.events``)."""

    #: A document was written to disk (``:w``, ``:saveas``, ``api.save()``).
    DOCUMENT_SAVED = auto()
    #: A file was opened that was not already open in the session.
    DOCUMENT_OPENED = auto()
    #: One or more documents left the session (``:bd``, last-tab close).
    DOCUMENT_CLOSED = auto()
    #: A document became the active one (open, ``:bn``/``:bp``, tab click).
    DOCUMENT_ACTIVATED = auto()
    #: The language server published diagnostics; the payload carries the
    #: document they belong to (any open document, not just the active one).
    DIAGNOSTICS_UPDATED = auto()
    #: The active keymap changed (``vsc`` / ``vim``).
    KEYMAP_CHANGED = auto()
    #: The color theme changed (``:theme``).
    THEME_CHANGED = auto()


@dataclass(frozen=True)
class DocumentSaved:
    """Payload of :attr:`EditorEvent.DOCUMENT_SAVED`."""

    doc: Document


@dataclass(frozen=True)
class DocumentOpened:
    """Payload of :attr:`EditorEvent.DOCUMENT_OPENED`."""

    doc: Document


@dataclass(frozen=True)
class DocumentClosed:
    """Payload of :attr:`EditorEvent.DOCUMENT_CLOSED`."""

    docs: tuple[Document, ...]


@dataclass(frozen=True)
class DocumentActivated:
    """Payload of :attr:`EditorEvent.DOCUMENT_ACTIVATED`."""

    doc: Document


@dataclass(frozen=True)
class DiagnosticsUpdated:
    """Payload of :attr:`EditorEvent.DIAGNOSTICS_UPDATED`."""

    doc: Document


@dataclass(frozen=True)
class KeymapChanged:
    """Payload of :attr:`EditorEvent.KEYMAP_CHANGED`."""

    name: str


@dataclass(frozen=True)
class ThemeChanged:
    """Payload of :attr:`EditorEvent.THEME_CHANGED`."""

    name: str


class EventHub:
    """Subscription registry and synchronous dispatcher for editor events.

    One hub per running editor.  ``emit`` is called by the editor-owned
    flows at the documented points; listeners added through
    :meth:`subscribe` (directly or via ``api.events``) run in insertion
    order on the calling thread.
    """

    def __init__(self, report_failure: FailureReporter | None = None) -> None:
        self._listeners: dict[EditorEvent, list[EventCallback]] = {}
        self._report_failure = report_failure

    def subscribe(
        self, event: EditorEvent, callback: EventCallback
    ) -> Callable[[], None]:
        """Subscribe *callback* to *event*; returns the unsubscribe thunk.

        Duplicate subscriptions are not de-duplicated: each call registers
        one listener and its own unsubscribe thunk (VS Code disposables
        semantics).  Unsubscribing twice is a safe no-op.
        """
        self._listeners.setdefault(event, []).append(callback)

        def unsubscribe() -> None:
            listeners = self._listeners.get(event)
            if listeners is not None:
                try:
                    listeners.remove(callback)
                except ValueError:
                    pass

        return unsubscribe

    def emit(self, event: EditorEvent, payload: object) -> None:
        """Dispatch *payload* to every listener of *event*, in order.

        Per-listener isolation: a raising listener is logged and reported
        on the message line, then the remaining listeners still run and
        the editor operation that emitted continues.
        """
        for callback in list(self._listeners.get(event, ())):
            try:
                callback(payload)
            except Exception:  # noqa: BLE001 - listener isolation, never crash the emitter
                log.exception("event listener failed: %s", event.name)
                if self._report_failure is not None:
                    self._report_failure(
                        f"extension event {event.name}: listener failed "
                        "(see trace log)"
                    )

    def listener_count(self, event: EditorEvent) -> int:
        """Number of live listeners on *event* (diagnostics and tests)."""
        return len(self._listeners.get(event, ()))
