"""Unit tests for the LspNavigationFlows orchestration (plan d).

No Textual App: every collaborator is a fake (LSP manager, hover popup,
panes/view, prompt bar) except the session, which uses the real
``EditorSession`` / ``Document`` types over real temp files.  Tests drive
an ``asyncio`` loop through ``asyncio.run`` and poll with ``wait_until``.
"""

# pyright: reportPrivateUsage=false

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable, Coroutine
from pathlib import Path
from typing import Any, cast

from textual.screen import Screen

from yate.config import YateConfig
from yate.editor_components.commandline import PromptBar
from yate.editor_components.hover_popup import HoverPopup
from yate.editor_components.lsp_chooser import LspChooserScreen
from yate.editor_components.panes import PaneManager
from yate.editor_core import Document
from yate.editor_lsp.manager import LspManager
from yate.editor_lsp.navigation import (
    REASON_NO_READY_SERVER,
    REASON_UNSUPPORTED,
    LspCodeAction,
    LspFeatureUnavailable,
    LspLocation,
    LspSignature,
    LspSymbol,
    LspTextEdit,
    WorkspaceEdit,
)
from yate.editor_lsp.protocol import uri_to_path
from yate.flows import SpawnFn
from yate.flows.lsp_navigation_flows import LspNavigationFlows
from yate.session import EditorSession

_TEXT = "abc def\nghi jkl\n"

#: Show arguments recorded by :class:`_FakePopup.show`.
ShowCall = tuple[str, tuple[int, int], tuple[int, int], int, int]


# ------------------------------------------------------------------- fakes


class _FakeLsp:
    """Preset ``LspManager`` double: canned per-feature replies."""

    def __init__(self) -> None:
        self.definition: list[LspLocation] = []
        self.references: list[LspLocation] = []
        self.symbols: list[LspSymbol] = []
        self.rename: WorkspaceEdit | None = None
        self.actions: list[LspCodeAction] = []
        self.signature: LspSignature | None = None
        #: Feature key whose request must raise (``"definition"`` etc.).
        self.raise_on: str | None = None
        #: Reason carried by the raised LspFeatureUnavailable.
        self.raise_reason: str = REASON_UNSUPPORTED
        #: When set, every request waits on it before answering.
        self.gate: asyncio.Event | None = None
        self.calls: list[str] = []
        self.executed: list[tuple[object, str, list[object]]] = []

    async def _wait(self, feature: str) -> None:
        self.calls.append(feature)
        if self.gate is not None:
            await self.gate.wait()
        if self.raise_on == feature:
            raise LspFeatureUnavailable(feature, reason=self.raise_reason)

    async def request_definition(
        self, doc: Document, row: int, col: int
    ) -> list[LspLocation]:
        await self._wait("definition")
        return self.definition

    async def request_references(
        self, doc: Document, row: int, col: int
    ) -> list[LspLocation]:
        await self._wait("references")
        return self.references

    async def request_document_symbols(
        self, doc: Document
    ) -> list[LspSymbol]:
        await self._wait("outline")
        return self.symbols

    async def request_code_actions(
        self, doc: Document, row: int, col: int, diagnostics: list[Any]
    ) -> list[LspCodeAction]:
        await self._wait("code actions")
        return self.actions

    async def request_signature_help(
        self, doc: Document, row: int, col: int
    ) -> LspSignature | None:
        await self._wait("signature help")
        return self.signature

    async def request_rename(
        self, doc: Document, row: int, col: int, new_name: str
    ) -> WorkspaceEdit:
        await self._wait("rename")
        assert self.rename is not None
        return self.rename

    async def ensure_client(self, doc: Document) -> object:
        return object()

    async def execute_command(
        self, client: object, name: str, arguments: list[object]
    ) -> None:
        self.executed.append((client, name, arguments))

    def diagnostics_on_line(self, doc: Document, row: int) -> list[Any]:
        return []


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
    """The slice of ``EditorView`` geometry the workers read."""

    def __init__(self, width: int = 100, height: int = 30) -> None:
        self.size = _FakeSize(width, height)
        self.scroll_col = 0
        self.scroll_offset = _FakeOffset()
        self.reveal_count = 0

    def gutter_width(self) -> int:
        return 3

    def screen_anchor(self, row: int, col: int) -> tuple[int, int]:
        return (col - self.scroll_col, row - self.scroll_offset.y)

    def reveal_cursor(self) -> None:
        self.reveal_count += 1


class _FakePanes:
    def __init__(self, view: _FakeView | None) -> None:
        self.active_view = view
        self._view = view

    def views_for(self, doc: Document) -> list[_FakeView]:
        return [self._view] if self._view is not None else []


class _FakePrompt:
    """Records ``activate`` and lets tests drive the submit callback."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []
        self.on_submit: Callable[[str], None] | None = None

    def activate(
        self,
        mode: str,
        *,
        initial: str = "",
        placeholder: str = "",
        on_submit: Callable[[str], None] | None = None,
        on_changed: Callable[[str], None] | None = None,
        on_key: Callable[[str], bool] | None = None,
        refocus: Callable[[], None] | None = None,
    ) -> bool:
        self.calls.append((mode, placeholder))
        self.on_submit = on_submit
        return True

    def submit(self, text: str) -> None:
        callback = self.on_submit
        assert callback is not None
        callback(text)


def _noop(*args: object) -> None:
    """Dismiss stub: keep the chooser screen alive without an App."""


def _spawn_shim(
    fn: Callable[[], Coroutine[object, object, None]], **_kwargs: object
) -> object:
    """Stand-in for ``App.run_worker``: run the coroutine function as a task."""
    return asyncio.get_running_loop().create_task(fn())


async def wait_until(
    predicate: Callable[[], bool], timeout: float = 2.0
) -> bool:
    """Poll *predicate* every loop turn; False on timeout (no fixed sleeps)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        await asyncio.sleep(0)
        if predicate():
            return True
    return predicate()


# ----------------------------------------------------------------- helpers


class _Harness:
    """A real flow wired to the fakes, recording every injected verb."""

    def __init__(self, tmp_path: Path) -> None:
        self.lsp = _FakeLsp()
        self.popup = _FakePopup()
        self.view = _FakeView()
        self.prompt = _FakePrompt()
        self.session = EditorSession(YateConfig())
        self.session.new_buffer()
        source = tmp_path / "mod.py"
        source.write_text(_TEXT, encoding="utf-8")
        self.doc = Document.open(source)
        self.session.docs[self.session.index] = self.doc
        self.opened: list[Path] = []
        self.pushes: list[Screen[None]] = []
        self.messages: list[tuple[str, str]] = []
        self.refreshes = 0
        self.flows = LspNavigationFlows(
            spawn=cast(SpawnFn, _spawn_shim),
            lsp=cast(LspManager, self.lsp),
            session=self.session,
            panes=cast(PaneManager, _FakePanes(self.view)),
            popup=cast(HoverPopup, self.popup),
            open_path=self._open_path,
            push_overlay=self.pushes.append,
            message=lambda text, kind: self.messages.append((text, kind)),
            refresh=self._refresh,
            prompt=cast(PromptBar, self.prompt),
            has_modal_screen=lambda: False,
        )

    def _open_path(self, path: Path) -> None:
        """Fake ``DocumentFlows.open_path``: record and open the document."""
        self.opened.append(path)
        if self.session.is_open(path) is None:
            self.session.docs.append(Document.open(path))

    def _refresh(self) -> None:
        self.refreshes += 1

    def message_texts(self) -> list[str]:
        return [text for text, _kind in self.messages]

    def chooser(self) -> LspChooserScreen:
        """The single pushed chooser screen (asserts exactly one push)."""
        assert len(self.pushes) == 1
        screen = self.pushes[0]
        assert isinstance(screen, LspChooserScreen)
        return screen


def _location(
    tmp_path: Path, name: str, row: int, col: int
) -> LspLocation:
    """A location pointing into *name* under *tmp_path*."""
    return LspLocation(
        uri=str(tmp_path / name), row=row, col=col,
        end_row=row, end_col=col + 3,
    )


# ------------------------------------------------------------------- tests


def test_goto_definition_single_location_jumps_cross_file(
    tmp_path: Path,
) -> None:
    """One definition in another file opens it and lands on the target."""
    target = tmp_path / "other.py"
    target.write_text("target line\nsecond line\n", encoding="utf-8")
    h = _Harness(tmp_path)
    h.lsp.definition = [_location(tmp_path, "other.py", 1, 2)]

    async def scenario() -> None:
        h.flows.goto_definition()
        assert await wait_until(
            lambda: bool(h.opened) and h.session.is_open(target) is not None
        )
        doc = h.session.is_open(target)
        assert doc is not None
        assert doc.buffer.cursor == (1, 2)
        assert any("jumped to" in text for text in h.message_texts())

    asyncio.run(scenario())


def test_goto_definition_multiple_locations_open_chooser(
    tmp_path: Path,
) -> None:
    """Two definitions push one chooser holding exactly two rows."""
    h = _Harness(tmp_path)
    h.lsp.definition = [
        _location(tmp_path, "a.py", 0, 0),
        _location(tmp_path, "b.py", 3, 1),
    ]

    async def scenario() -> None:
        h.flows.goto_definition()
        assert await wait_until(lambda: len(h.pushes) == 1)
        screen = h.chooser()
        assert len(screen.rows) == 2

    asyncio.run(scenario())


def test_goto_definition_without_provider_reports_unsupported(
    tmp_path: Path,
) -> None:
    """A missing definition provider degrades to a warning, no chooser."""
    h = _Harness(tmp_path)
    h.lsp.raise_on = "definition"

    async def scenario() -> None:
        h.flows.goto_definition()
        assert await wait_until(lambda: len(h.messages) == 1)
        text, kind = h.messages[0]
        assert text == (
            "definition unavailable: server does not support definition"
        )
        assert kind == "warn"
        assert h.pushes == []

    asyncio.run(scenario())


def test_unavailable_without_ready_server_maps_ready_message(
    tmp_path: Path,
) -> None:
    """A no-ready-server reason degrades to the explicit ready message."""
    h = _Harness(tmp_path)
    h.lsp.raise_on = "definition"
    h.lsp.raise_reason = REASON_NO_READY_SERVER

    async def scenario() -> None:
        h.flows.goto_definition()
        assert await wait_until(lambda: len(h.messages) == 1)
        text, kind = h.messages[0]
        assert text == "definition unavailable: language server is not ready"
        assert kind == "warn"
        assert h.pushes == []

    asyncio.run(scenario())


def test_find_references_empty_reports_message(tmp_path: Path) -> None:
    """No references degrade to the explicit info message."""
    h = _Harness(tmp_path)

    async def scenario() -> None:
        h.flows.find_references()
        assert await wait_until(
            lambda: "No references found" in h.message_texts()
        )
        assert h.pushes == []

    asyncio.run(scenario())


def test_find_references_rows_are_navigable(tmp_path: Path) -> None:
    """Picking the second chooser row jumps to its URI path and line."""
    h = _Harness(tmp_path)
    h.lsp.references = [
        _location(tmp_path, "mod.py", 0, 0),
        _location(tmp_path, "mod.py", 1, 4),
    ]

    async def scenario() -> None:
        h.flows.find_references()
        assert await wait_until(lambda: len(h.pushes) == 1)
        screen = h.chooser()
        screen._selected = 1
        cast(Any, screen).dismiss = _noop
        screen.action_pick()
        second = uri_to_path(screen.rows[1].uri)
        assert h.opened[-1] == second
        doc = h.session.is_open(second)
        assert doc is not None
        assert doc.buffer.cursor == (1, 4)

    asyncio.run(scenario())


def test_show_outline_uses_selection_range_and_depth(
    tmp_path: Path,
) -> None:
    """Nested symbols indent labels and jump from the selection range."""
    h = _Harness(tmp_path)
    h.lsp.symbols = [
        LspSymbol(
            name="Class", kind=5, detail="", uri=str(tmp_path / "mod.py"),
            row=0, col=0, end_row=5, end_col=0, depth=0,
        ),
        LspSymbol(
            name="method", kind=6, detail="", uri=str(tmp_path / "mod.py"),
            row=1, col=4, end_row=3, end_col=0, depth=1,
        ),
    ]

    async def scenario() -> None:
        h.flows.show_outline()
        assert await wait_until(lambda: len(h.pushes) == 1)
        screen = h.chooser()
        assert screen.rows[0].label == "Class"
        assert screen.rows[1].label == "  method"
        screen._selected = 1
        cast(Any, screen).dismiss = _noop
        screen.action_pick()
        assert h.doc.buffer.cursor == (1, 4)

    asyncio.run(scenario())


def test_rename_applies_workspace_edit_bottom_up(tmp_path: Path) -> None:
    """Two edits in one buffer both apply, one refresh, success message."""
    h = _Harness(tmp_path)
    uri = str(tmp_path / "mod.py")
    h.lsp.rename = WorkspaceEdit(
        changes={
            uri: (
                LspTextEdit(
                    start_row=0, start_col=0, end_row=0, end_col=3,
                    text="ABC",
                ),
                LspTextEdit(
                    start_row=1, start_col=0, end_row=1, end_col=3,
                    text="DEF",
                ),
            )
        },
        unsupported=False,
    )

    async def scenario() -> None:
        h.flows.rename_symbol()
        assert h.prompt.calls == [("lsp_rename", "New symbol name")]
        h.prompt.submit("newname")
        assert await wait_until(lambda: h.refreshes >= 1)
        assert h.doc.buffer.get_text() == "ABC def\nDEF jkl\n"
        assert any(
            "Renamed 2 occurrence(s)" in t for t in h.message_texts()
        )

    asyncio.run(scenario())


def test_rename_rolls_back_all_buffers_on_failure(tmp_path: Path) -> None:
    """A failing edit restores every buffer and warns, no partial result."""
    h = _Harness(tmp_path)
    uri = str(tmp_path / "mod.py")
    h.lsp.rename = WorkspaceEdit(
        changes={
            uri: (
                LspTextEdit(
                    start_row=0, start_col=0, end_row=0, end_col=3,
                    text="X",
                ),
                LspTextEdit(
                    start_row=9, start_col=0, end_row=9, end_col=1,
                    text="boom",
                ),
            )
        },
        unsupported=False,
    )

    async def scenario() -> None:
        h.flows.rename_symbol()
        h.prompt.submit("newname")
        assert await wait_until(
            lambda: any("rename failed" in t for t in h.message_texts())
        )
        assert h.doc.buffer.get_text() == "abc def\nghi jkl\n"

    asyncio.run(scenario())


def test_rename_locked_buffer_reports_failure_without_false_success(
    tmp_path: Path,
) -> None:
    """A locked (chunked) buffer must not report a rename that changed nothing."""
    h = _Harness(tmp_path)
    uri = str(tmp_path / "mod.py")
    h.lsp.rename = WorkspaceEdit(
        changes={uri: (
            LspTextEdit(start_row=0, start_col=0, end_row=0, end_col=3, text="X"),
        )},
        unsupported=False,
    )
    h.doc.buffer.locked = True

    async def scenario() -> None:
        h.flows.rename_symbol()
        h.prompt.submit("newname")
        assert await wait_until(
            lambda: any("rename failed" in t for t in h.message_texts())
        )
        assert not any("Renamed " in t for t in h.message_texts())
        assert h.doc.buffer.get_text() == _TEXT

    asyncio.run(scenario())


def test_rename_read_only_buffer_reports_failure(tmp_path: Path) -> None:
    """A read-only buffer is rejected up front, before any mutation."""
    h = _Harness(tmp_path)
    uri = str(tmp_path / "mod.py")
    h.lsp.rename = WorkspaceEdit(
        changes={uri: (
            LspTextEdit(start_row=0, start_col=0, end_row=0, end_col=3, text="X"),
        )},
        unsupported=False,
    )
    h.doc.buffer.read_only = True

    async def scenario() -> None:
        h.flows.rename_symbol()
        h.prompt.submit("newname")
        assert await wait_until(
            lambda: any("read-only" in t for t in h.message_texts())
        )
        assert h.doc.buffer.get_text() == _TEXT

    asyncio.run(scenario())


def test_rename_unsupported_edit_reports_message(tmp_path: Path) -> None:
    """``unsupported=True`` warns and never mutates a buffer."""
    h = _Harness(tmp_path)
    h.lsp.rename = WorkspaceEdit(changes={}, unsupported=True)

    async def scenario() -> None:
        h.flows.rename_symbol()
        h.prompt.submit("newname")
        assert await wait_until(
            lambda: any("unsupported" in t for t in h.message_texts())
        )
        assert h.doc.buffer.get_text() == "abc def\nghi jkl\n"
        assert h.refreshes == 0

    asyncio.run(scenario())


def test_rename_unopened_target_with_invalid_edit_restores_and_discloses(
    tmp_path: Path,
) -> None:
    """An invalid edit after opening an unopened target restores buffers
    and discloses that the newly opened file was left unsaved (M5)."""
    target = tmp_path / "other.py"
    target.write_text("target\n", encoding="utf-8")
    h = _Harness(tmp_path)
    h.lsp.rename = WorkspaceEdit(
        changes={
            str(tmp_path / "other.py"): (
                LspTextEdit(
                    start_row=0, start_col=0, end_row=0, end_col=3,
                    text="NEW",
                ),
            ),
            str(tmp_path / "mod.py"): (
                LspTextEdit(
                    start_row=9, start_col=0, end_row=9, end_col=1,
                    text="boom",
                ),
            ),
        },
        unsupported=False,
    )

    async def scenario() -> None:
        h.flows.rename_symbol()
        h.prompt.submit("newname")
        assert await wait_until(
            lambda: any("rename failed" in t for t in h.message_texts())
        )
        # The unopened target got opened by the pre-open pass...
        target_doc = h.session.is_open(target)
        assert target_doc is not None
        # ...and both buffers are restored byte-for-byte.
        assert h.doc.buffer.get_text() == "abc def\nghi jkl\n"
        assert target_doc.buffer.get_text() == "target\n"
        assert target_doc.buffer.cursor == (0, 0)
        # The message discloses the unsaved newly opened file.
        text = next(t for t in h.message_texts() if "rename failed" in t)
        assert "unsaved" in text and "other.py" in text

    asyncio.run(scenario())


def test_rename_success_message_discloses_unsaved_files(
    tmp_path: Path,
) -> None:
    """A successful rename reports occurrences, files and the unsaved note."""
    h = _Harness(tmp_path)
    uri = str(tmp_path / "mod.py")
    h.lsp.rename = WorkspaceEdit(
        changes={
            uri: (
                LspTextEdit(
                    start_row=0, start_col=0, end_row=0, end_col=3,
                    text="ABC",
                ),
            )
        },
        unsupported=False,
    )

    async def scenario() -> None:
        h.flows.rename_symbol()
        h.prompt.submit("newname")
        assert await wait_until(lambda: h.refreshes >= 1)
        assert any(
            "Renamed 1 occurrence(s) in 1 file(s) (unsaved; save to apply)"
            in t
            for t in h.message_texts()
        )

    asyncio.run(scenario())


def test_show_code_actions_executes_command_without_edit(
    tmp_path: Path,
) -> None:
    """A command-only action runs executeCommand with name and arguments."""
    h = _Harness(tmp_path)
    h.lsp.actions = [
        LspCodeAction(
            title="Fix", kind="quickfix", edit=None,
            command="server.fix", arguments=("a", 1),
        )
    ]

    async def scenario() -> None:
        h.flows.show_code_actions()
        assert await wait_until(lambda: len(h.pushes) == 1)
        screen = h.chooser()
        cast(Any, screen).dismiss = _noop
        screen.action_pick()
        assert await wait_until(lambda: len(h.lsp.executed) == 1)
        _client, name, arguments = h.lsp.executed[0]
        assert name == "server.fix"
        assert arguments == ["a", 1]

    asyncio.run(scenario())


def test_show_signature_help_uses_hover_popup(tmp_path: Path) -> None:
    """A signature reply shows the hover popup with the cursor anchor."""
    h = _Harness(tmp_path)
    h.lsp.signature = LspSignature(text="def f(x)", active_parameter=0)

    async def scenario() -> None:
        h.flows.show_signature_help()
        assert await wait_until(lambda: len(h.popup.shows) == 1)
        text, anchor, inner, gutter, origin_y = h.popup.shows[0]
        assert text == "def f(x)"
        assert anchor == (0, 0)
        assert inner == (100, 30)
        assert gutter == 3
        assert origin_y == 2

    asyncio.run(scenario())


def test_stale_result_is_discarded(tmp_path: Path) -> None:
    """A reply settling after the active tab switched drives no UI at all."""
    h = _Harness(tmp_path)
    h.lsp.gate = asyncio.Event()
    other = tmp_path / "other.py"
    other.write_text("other\n", encoding="utf-8")

    async def scenario() -> None:
        h.flows.goto_definition()
        assert await wait_until(lambda: len(h.lsp.calls) == 1)
        h.session.docs.append(Document.open(other))
        h.session.activate(h.session.docs[1])
        gate = h.lsp.gate
        assert gate is not None
        gate.set()
        await wait_until(lambda: False, timeout=0.05)
        assert h.pushes == []
        assert h.messages == []
        assert h.popup.shows == []

    asyncio.run(scenario())
