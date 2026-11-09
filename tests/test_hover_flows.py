"""Unit tests for the HoverFlows orchestration (plan g).

No Textual App: every collaborator is a fake (LSP manager, hover popup,
panes/view) except the session, which uses the real ``EditorSession`` /
``Document`` types.  Tests drive an ``asyncio`` loop through ``asyncio.run``
and poll with a ``wait_until`` helper; the debounce constant is monkeypatched
to ``0`` so no test depends on a sleep duration.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable, Coroutine
from typing import cast

import pytest

from yate.config import YateConfig
from yate.editor_components.hover_popup import HoverPopup
from yate.editor_components.panes import PaneManager
from yate.editor_core import Document
from yate.editor_lsp.manager import LspManager
from yate.flows import SpawnFn
from yate.flows import hover_flows
from yate.flows.hover_flows import HoverFlows
from yate.session import EditorSession

_DOCS = "**f()** docs"

#: Show arguments recorded by :class:`_FakePopup.show`.
ShowCall = tuple[str, tuple[int, int], tuple[int, int], int, int]


# ------------------------------------------------------------------- fakes


class _FakeLsp:
    """Preset ``LspManager`` double: canned reply, optional gate/raise."""

    def __init__(
        self, reply: str = "", *, supports: bool = True, raises: bool = False
    ) -> None:
        self.reply = reply
        self._supports = supports
        self._raises = raises
        self.calls = 0
        #: When set, ``request_hover`` waits on it before answering
        #: (lets a test resolve a request after mutating editor state).
        self.gate: asyncio.Event | None = None

    def supports(self, doc: Document) -> bool:
        return self._supports

    def set_supports(self, value: bool) -> None:
        """Toggle the ``supports`` gate from tests (guard scenarios)."""
        self._supports = value

    async def request_hover(self, doc: Document, row: int, col: int) -> str:
        self.calls += 1
        if self.gate is not None:
            await self.gate.wait()
        if self._raises:
            raise TimeoutError("lsp hover timed out")
        return self.reply


class _FakePopup:
    """Records ``show`` / ``close``; always reports mounted."""

    def __init__(self) -> None:
        self.shows: list[ShowCall] = []
        self.closes = 0
        self._open = False

    @property
    def is_open(self) -> bool:
        return self._open

    @property
    def is_mounted(self) -> bool:
        return True

    def show(
        self,
        text: str,
        anchor: tuple[int, int],
        inner_size: tuple[int, int],
        gutter: int,
        origin_y: int = 0,
    ) -> None:
        self.shows.append((text, anchor, inner_size, gutter, origin_y))
        self._open = True

    def close(self) -> None:
        self.closes += 1
        self._open = False


class _FakeSize:
    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height


class _FakeOffset:
    def __init__(self) -> None:
        self.y = 0


class _FakeView:
    """The slice of ``EditorView`` geometry the worker reads."""

    def __init__(self, width: int = 100, height: int = 30) -> None:
        self.size = _FakeSize(width, height)
        self.scroll_col = 0
        self.scroll_offset = _FakeOffset()

    def gutter_width(self) -> int:
        return 3


class _FakePanes:
    def __init__(self, view: _FakeView | None) -> None:
        self.active_view = view


def _spawn_shim(
    fn: Callable[[], Coroutine[object, object, None]], **_kwargs: object
) -> object:
    """Stand-in for ``App.run_worker``: run the coroutine function as a task."""
    return asyncio.get_running_loop().create_task(fn())


# ----------------------------------------------------------------- helpers


def _session(text: str = "abcdef\nghij\n") -> EditorSession:
    session = EditorSession(YateConfig())
    session.new_buffer()
    session.docs[session.index] = Document(None, session.make_buffer(text))
    return session


def _make_flows(
    lsp: _FakeLsp,
    session: EditorSession,
    popup: _FakePopup,
    view: _FakeView | None = None,
    modal: bool = False,
) -> HoverFlows:
    """Build a real ``HoverFlows`` wired to the fakes (casts only here)."""
    return HoverFlows(
        spawn=cast(SpawnFn, _spawn_shim),
        lsp=cast(LspManager, lsp),
        session=session,
        panes=cast(
            PaneManager, _FakePanes(_FakeView() if view is None else view)
        ),
        popup=cast(HoverPopup, popup),
        has_modal_screen=lambda: modal,
    )


async def wait_until(predicate: Callable[[], bool], timeout: float = 2.0) -> bool:
    """Poll *predicate* every loop turn; False on timeout (no fixed sleeps)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        await asyncio.sleep(0)
        if predicate():
            return True
    return predicate()


# ------------------------------------------------------------------- tests


def test_request_at_cursor_shows_normalized_docs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A keyboard request shows the LSP reply at the cursor cell."""
    monkeypatch.setattr(hover_flows, "HOVER_DEBOUNCE_S", 0.0)

    async def scenario() -> None:
        lsp = _FakeLsp(reply=_DOCS)
        popup = _FakePopup()
        view = _FakeView(width=100, height=30)
        flows = _make_flows(lsp, _session(), popup, view)
        flows.request_at_cursor()
        assert await wait_until(lambda: len(popup.shows) == 1)
        text, anchor, inner, gutter, origin_y = popup.shows[0]
        assert text == _DOCS
        assert anchor == (0, 0)
        assert inner == (100, 30)
        assert gutter == 3
        assert origin_y == 2

    asyncio.run(scenario())


def test_empty_result_produces_zero_ui_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An empty hover result with no card open is fully silent."""
    monkeypatch.setattr(hover_flows, "HOVER_DEBOUNCE_S", 0.0)

    async def scenario() -> None:
        lsp = _FakeLsp(reply="")
        popup = _FakePopup()
        flows = _make_flows(lsp, _session(), popup)
        flows.request_at_cursor()
        assert await wait_until(lambda: lsp.calls == 1)
        assert popup.closes == 0
        assert popup.shows == []

    asyncio.run(scenario())


def test_empty_result_clears_a_previously_visible_card(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A later empty result clears a card an earlier request had shown."""
    monkeypatch.setattr(hover_flows, "HOVER_DEBOUNCE_S", 0.0)

    async def scenario() -> None:
        lsp = _FakeLsp(reply=_DOCS)
        popup = _FakePopup()
        flows = _make_flows(lsp, _session(), popup)
        flows.request_at_cursor()
        assert await wait_until(lambda: len(popup.shows) == 1)
        lsp.reply = ""
        flows.request_at_cursor()
        assert await wait_until(lambda: popup.closes == 1)
        assert len(popup.shows) == 1

    asyncio.run(scenario())


def test_whitespace_only_result_is_silent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A whitespace-only reply counts as empty: silent, no close, no show."""
    monkeypatch.setattr(hover_flows, "HOVER_DEBOUNCE_S", 0.0)

    async def scenario() -> None:
        lsp = _FakeLsp(reply="  \n ")
        popup = _FakePopup()
        flows = _make_flows(lsp, _session(), popup)
        flows.request_at_cursor()
        assert await wait_until(lambda: lsp.calls == 1)
        assert popup.closes == 0
        assert popup.shows == []

    asyncio.run(scenario())


def test_request_failure_is_silent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A raised ``TimeoutError`` degrades to empty: fully silent, no show."""
    monkeypatch.setattr(hover_flows, "HOVER_DEBOUNCE_S", 0.0)

    async def scenario() -> None:
        lsp = _FakeLsp(raises=True)
        popup = _FakePopup()
        flows = _make_flows(lsp, _session(), popup)
        flows.request_at_cursor()
        assert await wait_until(lambda: lsp.calls == 1)
        assert popup.closes == 0
        assert popup.shows == []

    asyncio.run(scenario())


def test_empty_result_with_hidden_card_does_not_repaint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An empty reply with a never-shown card triggers no close at all."""
    monkeypatch.setattr(hover_flows, "HOVER_DEBOUNCE_S", 0.0)

    async def scenario() -> None:
        lsp = _FakeLsp(reply="")
        popup = _FakePopup()
        flows = _make_flows(lsp, _session(), popup)
        flows.request_at_cursor()
        assert await wait_until(lambda: lsp.calls == 1)
        await wait_until(lambda: False, timeout=0.05)
        assert popup.closes == 0
        assert popup.shows == []

    asyncio.run(scenario())


def test_no_server_guard_does_not_show_card(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without a server the guard returns silently: no worker, no popup."""
    monkeypatch.setattr(hover_flows, "HOVER_DEBOUNCE_S", 0.0)

    async def scenario() -> None:
        lsp = _FakeLsp(reply=_DOCS, supports=False)
        popup = _FakePopup()
        flows = _make_flows(lsp, _session(), popup)
        flows.request_at_cursor()
        await wait_until(lambda: False, timeout=0.05)
        assert lsp.calls == 0
        assert popup.shows == []
        assert popup.closes == 0

    asyncio.run(scenario())


def test_modal_screen_blocks_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A modal screen on top blocks the request outright."""
    monkeypatch.setattr(hover_flows, "HOVER_DEBOUNCE_S", 0.0)

    async def scenario() -> None:
        lsp = _FakeLsp(reply=_DOCS)
        popup = _FakePopup()
        flows = _make_flows(lsp, _session(), popup, modal=True)
        flows.request_at_cursor()
        await wait_until(lambda: False, timeout=0.05)
        assert lsp.calls == 0
        assert popup.shows == []
        assert popup.closes == 0

    asyncio.run(scenario())


def test_stale_result_after_tab_switch_is_dropped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A result resolving after the active tab changed never reaches UI."""
    monkeypatch.setattr(hover_flows, "HOVER_DEBOUNCE_S", 0.0)

    async def scenario() -> None:
        lsp = _FakeLsp(reply=_DOCS)
        lsp.gate = asyncio.Event()
        popup = _FakePopup()
        session = _session()
        flows = _make_flows(lsp, session, popup)
        flows.request_at_cursor()
        assert await wait_until(lambda: lsp.calls == 1)
        other = Document(None, session.make_buffer("other\n"))
        session.docs.append(other)
        session.activate(other)
        lsp.gate.set()
        await wait_until(lambda: False, timeout=0.05)
        assert popup.shows == []
        assert popup.closes == 0

    asyncio.run(scenario())


def test_stale_result_after_cursor_move_is_dropped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A key-path result resolving after the cursor moved never shows."""
    monkeypatch.setattr(hover_flows, "HOVER_DEBOUNCE_S", 0.0)

    async def scenario() -> None:
        lsp = _FakeLsp(reply=_DOCS)
        lsp.gate = asyncio.Event()
        popup = _FakePopup()
        session = _session()
        flows = _make_flows(lsp, session, popup)
        flows.request_at_cursor()
        assert await wait_until(lambda: lsp.calls == 1)
        session.doc.buffer.set_cursor((0, 3))
        lsp.gate.set()
        await wait_until(lambda: False, timeout=0.05)
        assert popup.shows == []

    asyncio.run(scenario())


def test_newer_request_supersedes_older_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only the newest token may drive the popup when two requests overlap."""
    monkeypatch.setattr(hover_flows, "HOVER_DEBOUNCE_S", 0.0)

    async def scenario() -> None:
        lsp = _FakeLsp(reply=_DOCS)
        lsp.gate = asyncio.Event()
        popup = _FakePopup()
        flows = _make_flows(lsp, _session(), popup)
        flows.request_at_cursor()
        flows.request_at_cursor()
        assert await wait_until(lambda: lsp.calls == 2)
        lsp.gate.set()
        assert await wait_until(lambda: len(popup.shows) == 1)
        assert popup.closes == 0

    asyncio.run(scenario())


def test_mouse_move_debounces_to_one_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Five rapid moves to the same position collapse into one request."""
    monkeypatch.setattr(hover_flows, "HOVER_DEBOUNCE_S", 0.0)

    async def scenario() -> None:
        lsp = _FakeLsp(reply=_DOCS)
        popup = _FakePopup()
        flows = _make_flows(lsp, _session(), popup)
        for _ in range(5):
            flows.on_mouse_move((0, 2))
        assert await wait_until(lambda: lsp.calls == 1)
        await wait_until(lambda: False, timeout=0.05)
        assert lsp.calls == 1
        assert len(popup.shows) == 1

    asyncio.run(scenario())


def test_mouse_move_to_different_position_closes_old_card(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Moving the pointer closes the visible card right away and re-requests."""
    monkeypatch.setattr(hover_flows, "HOVER_DEBOUNCE_S", 0.0)

    async def scenario() -> None:
        lsp = _FakeLsp(reply=_DOCS)
        popup = _FakePopup()
        flows = _make_flows(lsp, _session(), popup)
        flows.on_mouse_move((0, 2))
        assert await wait_until(lambda: len(popup.shows) == 1)
        flows.on_mouse_move((1, 0))
        assert popup.closes == 1
        assert await wait_until(lambda: lsp.calls == 2)

    asyncio.run(scenario())


def test_mouse_move_to_none_dismisses_and_cancels_timer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``None`` dismisses: close, token advanced, no later request fires."""
    monkeypatch.setattr(hover_flows, "HOVER_DEBOUNCE_S", 0.0)

    async def scenario() -> None:
        lsp = _FakeLsp(reply=_DOCS)
        popup = _FakePopup()
        flows = _make_flows(lsp, _session(), popup)
        flows.on_mouse_move((0, 2))
        assert await wait_until(lambda: len(popup.shows) == 1)
        token_before = cast(int, getattr(flows, "_token"))
        flows.on_mouse_move(None)
        assert popup.closes == 1
        assert cast(int, getattr(flows, "_token")) == token_before + 1
        await wait_until(lambda: False, timeout=0.05)
        assert lsp.calls == 1
        assert len(popup.shows) == 1

    asyncio.run(scenario())


def test_stale_mouse_result_after_pointer_move_is_dropped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A mouse result resolving after the pointer moved never shows."""
    monkeypatch.setattr(hover_flows, "HOVER_DEBOUNCE_S", 0.0)

    async def scenario() -> None:
        lsp = _FakeLsp(reply=_DOCS)
        lsp.gate = asyncio.Event()
        popup = _FakePopup()
        flows = _make_flows(lsp, _session(), popup)
        flows.on_mouse_move((0, 2))
        assert await wait_until(lambda: lsp.calls == 1)
        flows.on_mouse_move((1, 0))
        assert await wait_until(lambda: lsp.calls == 2)
        lsp.reply = ""
        lsp.gate.set()
        await wait_until(lambda: False, timeout=0.05)
        assert popup.shows == []

    asyncio.run(scenario())


def test_card_geometry_falls_back_when_view_size_is_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A zero-sized view falls back to the (80, 20) inner size."""
    monkeypatch.setattr(hover_flows, "HOVER_DEBOUNCE_S", 0.0)

    async def scenario() -> None:
        lsp = _FakeLsp(reply=_DOCS)
        popup = _FakePopup()
        view = _FakeView(width=0, height=0)
        flows = _make_flows(lsp, _session(), popup, view)
        flows.request_at_cursor()
        assert await wait_until(lambda: len(popup.shows) == 1)
        assert popup.shows[0][2] == (80, 20)

    asyncio.run(scenario())


def test_mouse_move_to_new_position_drops_inflight_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A reply settling after the pointer moved never shows.

    The default debounce stays in place (not patched to 0): the first
    request is in flight inside the debounce window when the pointer
    moves, so the fix must invalidate it immediately, not only when the
    debounce timer fires and spawns the next worker.
    """
    monkeypatch.setattr(hover_flows, "HOVER_DEBOUNCE_S", 0.35)

    async def scenario() -> None:
        lsp = _FakeLsp(reply=_DOCS)
        lsp.gate = asyncio.Event()
        popup = _FakePopup()
        flows = _make_flows(lsp, _session(), popup)
        flows.on_mouse_move((0, 2))
        assert await wait_until(lambda: lsp.calls == 1)
        flows.on_mouse_move((1, 0))
        lsp.gate.set()
        await wait_until(lambda: False, timeout=0.05)
        assert popup.shows == []

    asyncio.run(scenario())


def test_guard_triggered_mid_request_drops_inflight_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A guard firing while a request is in flight invalidates it."""
    monkeypatch.setattr(hover_flows, "HOVER_DEBOUNCE_S", 0.0)

    async def scenario() -> None:
        lsp = _FakeLsp(reply=_DOCS)
        lsp.gate = asyncio.Event()
        popup = _FakePopup()
        flows = _make_flows(lsp, _session(), popup)
        flows.request_at_cursor()
        assert await wait_until(lambda: lsp.calls == 1)
        lsp.set_supports(False)
        flows.request_at_cursor()
        lsp.gate.set()
        await wait_until(lambda: False, timeout=0.05)
        assert popup.shows == []

    asyncio.run(scenario())
