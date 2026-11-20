"""The data/event-domain ``api.*`` bridges (events / clipboard / docs /
actions / data).

Grouping note: these five bridges share one module because they are all
stateless wrappers over session-or-service owned state (the event hub,
the system clipboard, the session's open documents, the action registry,
the ``~/.yate/data`` store) -- none of them references the syntax or UI
domain, and none logs anything beyond :class:`DataExtensionBridge`.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from yate.editor_core import Document
from yate.logs import tracing
from yate.registries import ActionRegistry
from yate.session import EditorSession
from yate.services import clipboard, data_store
from yate.services.events import EditorEvent, EventHub, EventCallback

#: Trace logger ("yate.services.extensions.bridges.data_event"); silent
#: unless yate_trace is on.
log = tracing.get_logger(__name__)


class EventExtensionBridge:
    """``api.events`` -- subscribe to editor events from an extension.

    Wraps the editor-owned :class:`~yate.services.events.EventHub`; every
    subscription made while a rollback scope is active is recorded, so a
    failing ``setup`` also drops its listeners (A13).
    """

    #: Re-exported so extensions subscribe without importing yate internals.
    EditorEvent = EditorEvent

    def __init__(
        self,
        hub: EventHub,
        record_undo: Callable[[Callable[[], None]], None],
    ) -> None:
        self._hub = hub
        self._record_undo = record_undo

    def subscribe(
        self, event: EditorEvent, callback: EventCallback
    ) -> Callable[[], None]:
        """Subscribe to *event*; returns the unsubscribe thunk.

        *callback* is guarded by the hub itself (a raising listener is
        reported and skipped, never crashing the editor operation that
        emitted).  Payloads are the frozen dataclasses defined in
        :mod:`yate.services.events`.
        """
        unsubscribe = self._hub.subscribe(event, callback)
        self._record_undo(unsubscribe)
        return unsubscribe


class ClipboardExtensionBridge:
    """``api.clipboard`` -- read/write the system clipboard from an extension.

    Thin wrapper over :mod:`yate.services.clipboard` (resolved through the
    module so tests can monkeypatch it): both calls degrade gracefully
    (``False`` / ``None``) when no system clipboard backend is available,
    so extension code never sees a platform exception.
    """

    def set(self, text: str) -> bool:
        """Copy *text* to the system clipboard; ``False`` when unavailable."""
        return clipboard.copy_text(text)

    def get(self) -> str | None:
        """The clipboard text (``None`` when unavailable, ``""`` when empty)."""
        return clipboard.paste_text()


class DocsExtensionBridge:
    """``api.docs`` -- a read-only view of the session's open documents.

    Deliberately narrow: no open / activate / close -- the document
    lifecycle goes through the editor's UI flows (``api.open_path`` /
    ``api.save``), never through a back door around them.
    """

    def __init__(self, session: EditorSession) -> None:
        self._session = session

    def all(self) -> list[Document]:
        """Every open document (a fresh list; safe for the caller to hold)."""
        return list(self._session.docs)

    def is_open(self, path: str | Path) -> bool:
        """True when a document showing *path* is already open."""
        return self._session.is_open(Path(path)) is not None


class ActionExtensionBridge:
    """``api.actions`` -- run registered editor actions by name.

    ``run`` goes through the editor's key UI dispatch (the same path the
    keymaps use), so an extension-invoked action behaves exactly like a
    key-triggered one; ``names`` / ``has`` read the shared
    :class:`~yate.registries.ActionRegistry`.
    """

    def __init__(
        self,
        registry: ActionRegistry,
        run_action: Callable[[str], bool],
    ) -> None:
        self._registry = registry
        self._run_action = run_action

    def run(self, name: str) -> bool:
        """Run action *name*; ``False`` when it is unknown."""
        return self._run_action(name)

    def names(self) -> list[str]:
        """Every registered action name."""
        return self._registry.names()

    def has(self, name: str) -> bool:
        """True when action *name* is registered."""
        return self._registry.get(name) is not None


class DataExtensionBridge:
    """``api.data`` -- small text documents under ``~/.yate/data``.

    The only file channel an extension gets.  Names are relative to
    ``~/.yate/data``; absolute paths and ``..`` are rejected by
    :mod:`yate.services.data_store`, and every write is atomic (temporary
    sibling file, then replace).  Real-path validation lives in the same
    module too: symlinks (including intermediate directories) that resolve
    outside the data root are refused.  Failures are reported as
    ``None`` / ``False`` / ``[]`` instead of exceptions: a script must
    never take the editor down over a failed save, and a missing file is
    the normal "nothing saved yet" case.
    """

    def read(self, name: str) -> str | None:
        """Return the document *name*, or ``None`` when unreadable."""
        try:
            return data_store.read_text(name)
        except (ValueError, OSError) as exc:
            log.warning("api.data.read(%r) failed: %s", name, exc)
            return None

    def write(self, name: str, text: str) -> bool:
        """Write *text* to document *name* (atomically); ``False`` on failure."""
        try:
            data_store.write_text(name, text)
        except (ValueError, OSError, TypeError) as exc:
            log.warning("api.data.write(%r) failed: %s", name, exc)
            return False
        return True

    def remove(self, name: str) -> bool:
        """Delete document *name*; ``False`` when it did not exist."""
        try:
            return data_store.remove(name)
        except (ValueError, OSError) as exc:
            log.warning("api.data.remove(%r) failed: %s", name, exc)
            return False

    def list(self, prefix: str) -> list[str]:
        """Return the document names inside *prefix* (sorted, empty on miss)."""
        try:
            return data_store.names(prefix)
        except (ValueError, OSError) as exc:
            log.warning("api.data.list(%r) failed: %s", prefix, exc)
            return []
