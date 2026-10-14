"""Tests for the extension event subscription system.

Covers the :class:`~yate.services.events.EventHub` dispatch contract
(subscribe / unsubscribe / ordering / listener isolation), the
``api.events`` bridge with its A13 rollback-scope recording, and the
editor-level emission points (keymap, theme, save, open, close) through
the headless pilot harness.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast
from unittest.mock import MagicMock

from conftest import message_text

from yate.app import YateApp
from yate.config import YateConfig
from yate.editor_core import Document
from yate.editor_lsp.manager import LspManager
from yate.flows.lsp_sync import LspSync
from yate.keymaps.base import Keymap
from yate.keymaps.registry import KeymapSet
from yate.registries import ActionRegistry, CommandRegistry
from yate.session import EditorSession
from yate.services.events import (
    DiagnosticsUpdated,
    DocumentSaved,
    EditorEvent,
    EventCallback,
    EventHub,
    KeymapChanged,
)
from yate.services.extensions import ExtensionAPI, ExtensionContext
from yate.services.workspace import Workspace


def _collector(into: list[object]) -> EventCallback:
    """A listener appending every payload to *into* (pyright-typed)."""

    def collect(payload: object) -> None:
        into.append(payload)

    return collect


# --- EventHub unit ------------------------------------------------------------


def test_hub_subscribes_emits_and_unsubscribes() -> None:
    """A listener receives its payload; after unsubscribing it stays quiet."""
    hub = EventHub()
    seen: list[object] = []
    unsubscribe = hub.subscribe(EditorEvent.KEYMAP_CHANGED, _collector(seen))
    payload = KeymapChanged(name="vim")
    hub.emit(EditorEvent.KEYMAP_CHANGED, payload)
    assert seen == [payload]
    unsubscribe()
    hub.emit(EditorEvent.KEYMAP_CHANGED, KeymapChanged(name="vsc"))
    assert len(seen) == 1
    assert hub.listener_count(EditorEvent.KEYMAP_CHANGED) == 0


def test_hub_emits_in_insertion_order() -> None:
    """Listeners run in subscription order (synchronous, same thread)."""
    hub = EventHub()
    order: list[int] = []

    def make_listener(index: int) -> EventCallback:
        def listen(_payload: object) -> None:
            order.append(index)

        return listen

    for index in range(3):
        hub.subscribe(EditorEvent.DOCUMENT_SAVED, make_listener(index))
    hub.emit(EditorEvent.DOCUMENT_SAVED, DocumentSaved(_doc()))
    assert order == [0, 1, 2]


def test_hub_guards_failing_listener() -> None:
    """A raising listener is reported and skipped; the rest still run."""
    failures: list[str] = []
    hub = EventHub(report_failure=failures.append)

    def _boom(_payload: object) -> None:
        raise RuntimeError("listener exploded")

    hub.subscribe(EditorEvent.DOCUMENT_SAVED, _boom)
    after: list[object] = []
    hub.subscribe(EditorEvent.DOCUMENT_SAVED, after.append)
    hub.emit(EditorEvent.DOCUMENT_SAVED, DocumentSaved(_doc()))
    assert len(after) == 1  # the healthy listener still ran
    assert failures and "DOCUMENT_SAVED" in failures[0]


def test_hub_unsubscribe_is_idempotent() -> None:
    """Calling the unsubscribe thunk twice does not raise."""
    hub = EventHub()
    unsubscribe = hub.subscribe(EditorEvent.THEME_CHANGED, _collector([]))
    unsubscribe()
    unsubscribe()  # must be a no-op
    assert hub.listener_count(EditorEvent.THEME_CHANGED) == 0


# --- api.events bridge + A13 rollback -----------------------------------------


def _doc() -> Document:
    """A throwaway document for payload construction."""
    session = EditorSession(YateConfig())
    session.new_buffer()
    return session.doc


def _extension_api(hub: EventHub | None = None) -> ExtensionAPI:
    """An ExtensionAPI over real registries (the test_extension_api shape).

    *hub*, when given, is the editor-side hub the API wraps; tests use it
    to emit exactly what the editor would.
    """
    session = EditorSession(YateConfig())
    session.new_buffer()
    ctx = ExtensionContext(
        session=session,
        workspace=Workspace(),
        lsp=LspManager(),
        keymaps=KeymapSet({"vsc": Keymap(), "vim": Keymap()}, "vsc"),
        actions=ActionRegistry(),
        commands=CommandRegistry(),
        message=lambda _text: None,
        run_shell=lambda _command, _show: None,
        open_path=lambda _path: None,
        save=lambda: None,
        run_action=lambda _name: False,
        set_theme=lambda _name: None,
        active_theme_name=lambda: "mocha",
    )
    return ExtensionAPI(ctx, hub)


def test_hub_unsubscribe_twice_is_safe_noop() -> None:
    """Unsubscribing the same thunk twice does not raise (docstring promise)."""
    hub = EventHub()
    seen: list[object] = []
    unsubscribe = hub.subscribe(EditorEvent.KEYMAP_CHANGED, _collector(seen))
    unsubscribe()
    unsubscribe()
    assert seen == []
    assert hub.listener_count(EditorEvent.KEYMAP_CHANGED) == 0


def test_bridge_subscription_rolls_back_on_setup_failure() -> None:
    """A subscription made inside a failing setup scope is undone (A13)."""
    hub = EventHub()
    api = _extension_api(hub)
    seen: list[object] = []
    api.start_scope()
    api.events.subscribe(EditorEvent.KEYMAP_CHANGED, _collector(seen))
    api.rollback_scope()
    hub.emit(EditorEvent.KEYMAP_CHANGED, KeymapChanged(name="vim"))
    assert seen == []
    assert hub.listener_count(EditorEvent.KEYMAP_CHANGED) == 0


def test_bridge_subscription_outside_scope_is_permanent() -> None:
    """Subscriptions made without an active scope survive (``:trust`` path)."""
    hub = EventHub()
    api = _extension_api(hub)
    seen: list[object] = []
    api.events.subscribe(EditorEvent.KEYMAP_CHANGED, _collector(seen))
    api.rollback_scope()  # no active scope: a no-op, must not unsubscribe
    payload = KeymapChanged(name="vim")
    hub.emit(EditorEvent.KEYMAP_CHANGED, payload)
    assert seen == [payload]


# --- editor emission points (headless pilot) ----------------------------------


def test_keymap_and_theme_events_fire() -> None:
    """``toggle_keymap`` and ``set_theme`` emit their events, in order."""

    async def scenario() -> None:
        app = YateApp(keymap="vsc")
        async with app.run_test(size=(100, 30)):
            keymap_events: list[KeymapChanged] = []
            theme_events: list[object] = []
            api = app.editor.extension_api
            api.events.subscribe(
                EditorEvent.KEYMAP_CHANGED, keymap_events.append
            )
            api.events.subscribe(EditorEvent.THEME_CHANGED, theme_events.append)
            app.editor.toggle_keymap()
            app.editor.set_theme("latte")
            assert [event.name for event in keymap_events] == ["vim"]
            assert len(theme_events) == 1

    asyncio.run(scenario())


def test_reselect_active_theme_no_event_but_message() -> None:
    """Re-selecting the active theme emits no THEME_CHANGED (the Textual
    reactive skips the same-value repaint, so listeners must not see a
    change nothing re-rendered) but still confirms on the message line."""

    async def scenario() -> None:
        app = YateApp(keymap="vsc")
        async with app.run_test(size=(100, 30)):
            theme_events: list[object] = []
            api = app.editor.extension_api
            api.events.subscribe(EditorEvent.THEME_CHANGED, theme_events.append)
            app.editor.set_theme("mocha")  # already active: guarded
            assert theme_events == []
            assert "theme: Catppuccin Mocha" in message_text(app)

    asyncio.run(scenario())


def test_document_saved_event_fires(tmp_path: Path) -> None:
    """``save_document`` emits DOCUMENT_SAVED with the persisted document."""

    async def scenario() -> None:
        target = tmp_path / "event_saved.txt"
        target.write_text("hello", encoding="utf-8")
        app = YateApp()
        async with app.run_test(size=(100, 30)):
            saved: list[DocumentSaved] = []
            api = app.editor.extension_api
            api.events.subscribe(EditorEvent.DOCUMENT_SAVED, saved.append)
            app.editor.document_flows.open_path(target)
            app.editor.document_flows.save_document()
            assert [event.doc.path for event in saved] == [target]
            assert target.read_text(encoding="utf-8") == "hello"

    asyncio.run(scenario())


def test_document_opened_and_closed_events_fire(tmp_path: Path) -> None:
    """Opening a fresh file emits OPENED (not on reuse); ``:bd`` emits CLOSED."""

    async def scenario() -> None:
        first = tmp_path / "event_open_a.txt"
        first.write_text("a", encoding="utf-8")
        second = tmp_path / "event_open_b.txt"
        second.write_text("b", encoding="utf-8")
        app = YateApp()
        async with app.run_test(size=(100, 30)):
            opened: list[object] = []
            closed: list[object] = []
            api = app.editor.extension_api
            api.events.subscribe(EditorEvent.DOCUMENT_OPENED, opened.append)
            api.events.subscribe(EditorEvent.DOCUMENT_CLOSED, closed.append)
            app.editor.document_flows.open_path(first)
            app.editor.document_flows.open_path(first)  # reuse: no event
            assert len(opened) == 1
            app.editor.document_flows.open_path(second)
            assert len(opened) == 2
            app.editor.document_flows.close_tab()
            assert len(closed) == 1
            assert message_text(app) is not None

    asyncio.run(scenario())


def test_unsubscribe_thunk_removes_editor_listener() -> None:
    """The thunk returned by ``api.events.subscribe`` really unsubscribes."""

    async def scenario() -> None:
        app = YateApp(keymap="vsc")
        async with app.run_test(size=(100, 30)):
            seen: list[object] = []
            unsubscribe: Callable[[], None] = (
                app.editor.extension_api.events.subscribe(
                    EditorEvent.KEYMAP_CHANGED, seen.append
                )
            )
            app.editor.toggle_keymap()
            assert len(seen) == 1
            unsubscribe()
            app.editor.toggle_keymap()
            assert len(seen) == 1

    asyncio.run(scenario())


# --- lsp_sync emission contract: diagnostics carry their own document --------


def _lsp_sync(events: EventHub) -> LspSync:
    """A LspSync wired to mocks except the real event hub."""
    lsp = MagicMock()
    lsp.diagnostic_at.return_value = None
    panes = MagicMock()
    panes.all_views.return_value = []
    prompt = MagicMock()
    prompt.active_mode = None
    return LspSync(
        spawn=MagicMock(),
        lsp=cast(Any, lsp),
        session=cast(Any, MagicMock()),
        panes=cast(Any, panes),
        status_bar=cast(Any, MagicMock()),
        prompt=cast(Any, prompt),
        events=events,
        message=MagicMock(),
        mounted=lambda: True,
        push_overlay=MagicMock(),
    )


def test_lsp_sync_emits_diagnostics_for_the_attributed_document(
    tmp_path: Path,
) -> None:
    """A publish about any open document reaches listeners with its own doc."""
    events = EventHub()
    seen: list[object] = []
    events.subscribe(EditorEvent.DIAGNOSTICS_UPDATED, _collector(seen))
    sync = _lsp_sync(events)
    doc = Document(tmp_path / "bg.py")

    sync.on_event("diagnostics", doc)

    assert len(seen) == 1
    assert isinstance(seen[0], DiagnosticsUpdated)
    assert seen[0].doc is doc


def test_lsp_sync_unknown_uri_and_state_events_emit_nothing(
    tmp_path: Path,
) -> None:
    """A publish about an unknown uri (doc None) and state events stay silent."""
    events = EventHub()
    seen: list[object] = []
    events.subscribe(EditorEvent.DIAGNOSTICS_UPDATED, _collector(seen))
    sync = _lsp_sync(events)

    sync.on_event("diagnostics", None)
    sync.on_event("state")

    assert seen == []
