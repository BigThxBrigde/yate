"""LSP hover docs integration tests (plan h, run via pilot, no real server).

The fake LSP client below is injected the way ``tests/test_app_lsp.py``
injects its UI fake: ``register_server`` + ``set_client_factory``.  The
client serves canned ``textDocument/hover`` payloads whose shape is set
per test (docs / ``None`` / ``{}`` / whitespace / ``[]`` / raise / hang).
All waiting goes through :func:`conftest.wait_until` polling -- no fixed
sleeps; the hang case settles a gated future deterministically.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import cast
from unittest.mock import patch

import pytest
from textual.events import MouseMove
from textual.pilot import Pilot

from yate.app import YateApp
from yate.editor_components.hover_popup import HoverPopup
from yate.editor_components.view import EditorView
from yate.editor_core.document import Document
from yate.editor_lsp.client import LspClient, ServerConfig
from yate.editor_lsp.manager import LspManager
from yate.keymaps.keys import parse_key
from conftest import message_text, wait_until

_DOC = "hello world\n"
_HOVER_TEXT = "hover docs text"


def _popup_text(popup: HoverPopup) -> str:
    """The popup's rendered text (private attribute read via ``getattr``)."""
    return cast(str, getattr(popup, "_text"))


class _HoverFakeClient:
    """Fake READY LSP client serving canned hover payloads.

    ``mode`` selects the payload: any object becomes the hover contents
    (``"docs"`` -> real docs text), ``"raise"`` raises, ``"hang"`` leaves
    the future pending until ``gate`` is set.
    """

    def __init__(self, config: ServerConfig, root: Path) -> None:
        self.config = config
        self.root_path = root
        from yate.editor_lsp import ServerState
        self.state = ServerState.READY
        self.error = ""
        self.trigger_characters: tuple[str, ...] = (".",)
        self.mode: object = "docs"
        self.requests: int = 0
        self.gate: asyncio.Event | None = None
        self.settled: bool = False
        self.opened: list[object] = []

    async def start(self) -> None:
        """Fake start: nothing to launch, the client stays READY."""
        return None

    async def stop(self) -> None:
        """Fake stop: flips the state to STOPPED."""
        from yate.editor_lsp import ServerState
        self.state = ServerState.STOPPED

    async def notify(
        self, method: str, params: dict[str, object] | None
    ) -> None:
        """Fake notify: records ``didOpen`` payloads."""
        if method == "textDocument/didOpen":
            self.opened.append(params)

    async def start_request(
        self, method: str, params: dict[str, object] | None
    ) -> tuple[int, asyncio.Future[object]]:
        """Serve the canned hover payload on ``textDocument/hover``."""
        if method != "textDocument/hover":
            return 0, _done_future({})
        self.requests += 1
        future: asyncio.Future[object] = (
            asyncio.get_running_loop().create_future()
        )
        if self.gate is not None:
            await self.gate.wait()
            self.settled = True
        if self.mode == "raise":
            future.set_exception(RuntimeError("boom"))
        elif self.mode == "hang":
            pass  # stays pending: the manager timeout must kick in
        else:
            mode = self.mode
            contents: object = (
                _HOVER_TEXT if mode == "docs" else mode
            )
            future.set_result({"contents": contents})
        return 1, future

    def settle_request(self, request_id: int) -> None:
        """Fake settle: mirrors the real client's pending cleanup."""
        return None

    async def send_cancel(self, request_id: int) -> None:
        """Fake cancel: discards the request id."""
        return None


def _done_future(value: object) -> asyncio.Future[object]:
    """An already-resolved future (non-hover methods of the fake)."""
    future: asyncio.Future[object] = (
        asyncio.get_running_loop().create_future()
    )
    future.set_result(value)
    return future


def _install_hover_server(
    app: YateApp, holder: list[_HoverFakeClient]
) -> None:
    """Register the fake hover server for ``.txt`` documents."""

    def factory(config: ServerConfig, root: Path) -> LspClient:
        client = _HoverFakeClient(config, root)
        holder.append(client)
        return cast(LspClient, client)

    app.editor.lsp.register_server(ServerConfig(
        name="hover-fake", command="fake", filetypes=["txt"],
    ))
    app.editor.lsp.set_client_factory(factory)


def _hover_app(
    tmp_path: Path, *, keymap: str | None = None
) -> YateApp:
    """A yate app over a one-line document the fake server serves."""
    target = tmp_path / "hover.txt"
    target.write_text(_DOC, encoding="utf-8")
    return YateApp(target=target, keymap=keymap)


async def _make_ready(
    pilot: Pilot[None], app: YateApp, holder: list[_HoverFakeClient]
) -> _HoverFakeClient:
    """Install the fake server and wait until the doc is didOpen'd."""
    _install_hover_server(app, holder)
    app.editor.refresh_ui()
    ready = await wait_until(
        pilot, lambda: app.editor.lsp.is_open(app.editor.session.doc)
    )
    assert ready
    return holder[0]


def _status_text(app: YateApp) -> str:
    """The rendered status bar text (left + right blocks)."""
    return "".join(
        seg.text for seg in app.editor.status_bar.render_line(0)
    )


def _assert_zero_ui_output(
    app: YateApp, status_before: str, message_before: str
) -> None:
    """The silence contract: no card, no message, no status drift."""
    popup = app.editor.hover_popup
    assert popup.is_open is False
    assert _popup_text(popup) == ""
    # the idle hint line is pre-existing content: only drift is a failure
    assert message_text(app) == message_before
    assert _status_text(app) == status_before


def test_f7_shows_hover_docs_in_vsc_keymap(tmp_path: Path) -> None:
    async def scenario() -> None:
        app = _hover_app(tmp_path)
        holder: list[_HoverFakeClient] = []
        async with app.run_test(size=(100, 30)) as pilot:
            client = await _make_ready(pilot, app, holder)
            await pilot.press("f7")
            shown = await wait_until(
                pilot, lambda: app.editor.hover_popup.is_open
            )
            assert shown
            assert client.requests == 1
            assert _popup_text(app.editor.hover_popup) == _HOVER_TEXT

    asyncio.run(scenario())


def test_f7_shows_hover_docs_in_vim_keymap_after_ctrl_slash_toggle(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        app = _hover_app(tmp_path)
        holder: list[_HoverFakeClient] = []
        async with app.run_test(size=(100, 30)) as pilot:
            client = await _make_ready(pilot, app, holder)
            await pilot.press("ctrl+/")
            assert app.editor.keymaps.active.name == "vim"
            await pilot.press("f7")
            shown = await wait_until(
                pilot, lambda: app.editor.hover_popup.is_open
            )
            assert shown
            assert client.requests == 1
            assert _popup_text(app.editor.hover_popup) == _HOVER_TEXT

    asyncio.run(scenario())


@pytest.mark.parametrize("mode", [None, {}, "  ", []])
def test_empty_results_have_zero_ui_output(
    tmp_path: Path, mode: object
) -> None:
    async def scenario() -> None:
        app = _hover_app(tmp_path)
        holder: list[_HoverFakeClient] = []
        async with app.run_test(size=(100, 30)) as pilot:
            client = await _make_ready(pilot, app, holder)
            client.mode = mode
            status_before = _status_text(app)
            message_before = message_text(app)
            await pilot.press("f7")
            done = await wait_until(pilot, lambda: client.requests == 1)
            assert done
            await pilot.pause()
            _assert_zero_ui_output(app, status_before, message_before)

    asyncio.run(scenario())


def test_null_hover_result_has_zero_ui_output(tmp_path: Path) -> None:
    async def scenario() -> None:
        app = _hover_app(tmp_path)
        holder: list[_HoverFakeClient] = []
        async with app.run_test(size=(100, 30)) as pilot:
            client = await _make_ready(pilot, app, holder)
            client.mode = None
            status_before = _status_text(app)
            message_before = message_text(app)
            await pilot.press("f7")
            done = await wait_until(pilot, lambda: client.requests == 1)
            assert done
            await pilot.pause()
            _assert_zero_ui_output(app, status_before, message_before)

    asyncio.run(scenario())


def test_failed_and_timed_out_requests_are_silent(tmp_path: Path) -> None:
    async def scenario() -> None:
        import yate.editor_lsp.manager as manager

        app = _hover_app(tmp_path)
        holder: list[_HoverFakeClient] = []
        async with app.run_test(size=(100, 30)) as pilot:
            client = await _make_ready(pilot, app, holder)
            status_before = _status_text(app)
            message_before = message_text(app)
            saved_timeout = manager.HOVER_TIMEOUT_S
            for mode in ("raise", "hang"):
                client.mode = mode
                manager.HOVER_TIMEOUT_S = 0.05
                try:
                    await pilot.press("f7")
                    done = await wait_until(
                        pilot, lambda: client.requests >= 1
                    )
                    assert done
                    await pilot.pause()
                    _assert_zero_ui_output(app, status_before, message_before)
                finally:
                    manager.HOVER_TIMEOUT_S = saved_timeout
                    client.requests = 0

    asyncio.run(scenario())


def test_card_is_cleared_when_a_later_result_is_empty(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        app = _hover_app(tmp_path)
        holder: list[_HoverFakeClient] = []
        async with app.run_test(size=(100, 30)) as pilot:
            client = await _make_ready(pilot, app, holder)
            status_before = _status_text(app)
            message_before = message_text(app)
            await pilot.press("f7")
            shown = await wait_until(
                pilot, lambda: app.editor.hover_popup.is_open
            )
            assert shown
            client.mode = None
            await pilot.press("f7")
            cleared = await wait_until(
                pilot, lambda: client.requests == 2
                and not app.editor.hover_popup.is_open
            )
            assert cleared
            _assert_zero_ui_output(app, status_before, message_before)

    asyncio.run(scenario())


def test_typing_dismisses_card_without_swallowing_key(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        app = _hover_app(tmp_path)
        holder: list[_HoverFakeClient] = []
        async with app.run_test(size=(100, 30)) as pilot:
            await _make_ready(pilot, app, holder)
            await pilot.press("f7")
            shown = await wait_until(
                pilot, lambda: app.editor.hover_popup.is_open
            )
            assert shown
            await pilot.press("x")
            closed = await wait_until(
                pilot, lambda: not app.editor.hover_popup.is_open
            )
            assert closed
            # the key reached the buffer: "x" was inserted at the cursor
            assert app.editor.session.buffer.lines[0].startswith("x")
            assert app.editor.session.buffer.cursor == (0, 1)

    asyncio.run(scenario())


def test_escape_dismisses_card_and_keeps_existing_behavior(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        app = _hover_app(tmp_path)
        holder: list[_HoverFakeClient] = []
        async with app.run_test(size=(100, 30)) as pilot:
            await _make_ready(pilot, app, holder)
            await pilot.press("f7")
            shown = await wait_until(
                pilot, lambda: app.editor.hover_popup.is_open
            )
            assert shown
            cursor_before = app.editor.session.buffer.cursor
            await pilot.press("escape")
            closed = await wait_until(
                pilot, lambda: not app.editor.hover_popup.is_open
            )
            assert closed
            # existing escape behavior: cursor untouched, keymap unchanged
            assert app.editor.session.buffer.cursor == cursor_before
            assert app.editor.keymaps.active.name == "vsc"

    asyncio.run(scenario())


def test_hover_does_not_start_server_or_open_document(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def scenario() -> None:
        app = _hover_app(tmp_path)
        calls: list[str] = []

        async def _no_ensure(doc: Document) -> None:
            calls.append("ensure_client")
            return None

        async def _no_open(doc: Document) -> None:
            calls.append("on_document_shown")
            return None

        monkeypatch.setattr(LspManager, "ensure_client", _no_ensure)
        monkeypatch.setattr(LspManager, "on_document_shown", _no_open)
        # no server is registered at all: hover must stay passive
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            status_before = _status_text(app)
            message_before = message_text(app)
            await pilot.press("f7")
            await pilot.pause()
            _assert_zero_ui_output(app, status_before, message_before)
            assert calls == []

    asyncio.run(scenario())


def test_switching_buffer_drops_stale_hover_response(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        app = _hover_app(tmp_path)
        holder: list[_HoverFakeClient] = []
        async with app.run_test(size=(100, 30)) as pilot:
            client = await _make_ready(pilot, app, holder)
            # gate the response: it must not settle while we switch buffers
            client.gate = asyncio.Event()
            await pilot.press("f7")
            sent = await wait_until(pilot, lambda: client.requests == 1)
            assert sent
            other = tmp_path / "other.txt"
            other.write_text("second doc\n", encoding="utf-8")
            app.editor.document_flows.open_path(other)
            await pilot.pause()
            client.gate.set()
            settled = await wait_until(pilot, lambda: client.settled)
            assert settled
            await pilot.pause()
            assert app.editor.hover_popup.is_open is False
            assert _popup_text(app.editor.hover_popup) == ""

    asyncio.run(scenario())


def test_cursor_move_drops_stale_keyboard_response(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        app = _hover_app(tmp_path)
        holder: list[_HoverFakeClient] = []
        async with app.run_test(size=(100, 30)) as pilot:
            client = await _make_ready(pilot, app, holder)
            client.gate = asyncio.Event()
            await pilot.press("f7")
            sent = await wait_until(pilot, lambda: client.requests == 1)
            assert sent
            # the cursor move dismisses: dismiss bumps the staleness token
            await pilot.press("right")
            client.gate.set()
            settled = await wait_until(pilot, lambda: client.settled)
            assert settled
            await pilot.pause()
            assert app.editor.hover_popup.is_open is False
            assert _popup_text(app.editor.hover_popup) == ""

    asyncio.run(scenario())


def test_support_mouse_off_disables_hover_and_keeps_mouse_behavior(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        app = _hover_app(tmp_path)
        holder: list[_HoverFakeClient] = []
        async with app.run_test(size=(100, 30)) as pilot:
            client = await _make_ready(pilot, app, holder)
            app.editor.config.support_mouse = False
            view = app.editor.panes.active_view
            assert view is not None
            event = _mouse_move(view, x=8)
            cursor_before = app.editor.session.buffer.cursor
            consumed = app.editor.mouse_flows.handle_view_mouse(view, event)
            assert consumed is False
            await pilot.pause()
            assert client.requests == 0
            assert app.editor.session.buffer.cursor == cursor_before
            assert app.editor.hover_popup.is_open is False

    asyncio.run(scenario())


def test_support_mouse_on_non_drag_move_triggers_debounced_hover(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def scenario() -> None:
        monkeypatch.setattr(
            "yate.flows.hover_flows.HOVER_DEBOUNCE_S", 0.0
        )
        app = _hover_app(tmp_path)
        holder: list[_HoverFakeClient] = []
        async with app.run_test(size=(100, 30)) as pilot:
            client = await _make_ready(pilot, app, holder)
            view = app.editor.panes.active_view
            assert view is not None
            event = _mouse_move(view, x=8)
            consumed = app.editor.mouse_flows.handle_view_mouse(view, event)
            assert consumed is False
            shown = await wait_until(
                pilot, lambda: app.editor.hover_popup.is_open
            )
            assert shown
            assert client.requests == 1
            assert _popup_text(app.editor.hover_popup) == _HOVER_TEXT

    asyncio.run(scenario())


def test_non_drag_mouse_move_is_not_consumed(tmp_path: Path) -> None:
    async def scenario() -> None:
        app = _hover_app(tmp_path)
        holder: list[_HoverFakeClient] = []
        async with app.run_test(size=(100, 30)) as pilot:
            await _make_ready(pilot, app, holder)
            view = app.editor.panes.active_view
            assert view is not None
            event = _mouse_move(view, x=8)
            with patch.object(event, "stop") as spy:
                consumed = app.editor.mouse_flows.handle_view_mouse(
                    view, event
                )
            assert consumed is False
            spy.assert_not_called()

    asyncio.run(scenario())


def test_bind_key_both_retargets_hover_action_in_both_keymaps(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        app = _hover_app(tmp_path)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            app.editor.extension_api.bind_action(
                "<f6>", "show_hover_docs", keymap="both"
            )
            for name in ("vsc", "vim"):
                keymap = app.editor.keymaps.get(name)
                assert keymap is not None
                binding = keymap.lookup(parse_key("<f6>"))
                assert binding is not None
                assert binding.action == "show_hover_docs"
            # ``add_binding`` only adds: the old <f7> binding stays in both
            # keymaps (bind_action never unbinds the previous key, verified
            # in services/extensions/api.py -- reported as a plan deviation).

    asyncio.run(scenario())


def _mouse_move(view: EditorView, x: int) -> MouseMove:
    """A synthetic non-drag MouseMove over *view* at cell *x*."""
    return MouseMove(
        view, x=x, y=0, delta_x=0, delta_y=0, button=0,
        shift=False, meta=False, ctrl=False,
    )
