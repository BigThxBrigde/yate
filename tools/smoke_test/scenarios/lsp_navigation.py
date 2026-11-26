"""LSP navigation smoke scenarios (tag: ``lsp-navigation``).

Three scenarios exercise the navigation verbs without a real language
server (the harness never starts one); a fake READY client is injected
through ``register_server`` + ``set_client_factory`` exactly like
``tests/test_hover_integration.py`` does:

* ``lsp_navigation_gd_jumps_across_files_in_both_keymaps`` -- a two-file
  project (``mathutil.py`` defines ``greet``, ``app.py`` imports and calls
  it); ``gd`` on the call site jumps to the other file's definition line,
  first via the vsc ``<alt-g>`` key, then after the keymap switch via the
  vim ``gd`` chord.
* ``lsp_navigation_gr_chooser_lists_both_files_and_enter_navigates`` --
  ``gr`` on the call site opens the chooser whose rendered SVG text
  contains both file names; ``enter`` navigates to the selected row.
* ``lsp_navigation_no_server_warns_and_leaves_buffer_untouched`` -- with
  no server at all the same key emits a warning message and the buffer
  stays byte-identical.
* ``quickfix_panel_next_prev_and_jump_back`` -- ``gr`` dual-publishes the
  two references into the bottom quickfix panel; ``alt+j`` / ``alt+k``
  step and jump between the entries, and ``alt+left`` undoes the last
  quickfix jump through the jump list.

All waiting goes through :func:`wait_until`; no fixed sleeps.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, cast

from yate.app import YateApp
from yate.editor_components.lsp_chooser import LspChooserScreen
from yate.editor_components.hover_popup import HoverPopup
from yate.editor_lsp.client import LspClient, ServerConfig
from yate.editor_lsp.protocol import canonical_uri, path_to_uri

from tools.smoke_test.harness import Check, Scenario, ScenarioResult, new_app, snapshot_svg
from tools.smoke_test.scenarios._base import message_text, run_command, wait_until

__all__ = ["SCENARIOS"]

#: Definition line of ``greet`` in ``mathutil.py`` (0-based) and the column
#: of its name.
_DEF_ROW: int = 0
_DEF_COL: int = 4

#: Row/col of the ``greet(1)`` call site in ``app.py`` (0-based).
_CALL_ROW: int = 2
_CALL_COL: int = 0

#: Text served for ``textDocument/hover``; both ``K`` and ``F7`` must
#: render exactly this.
_HOVER_TEXT: str = "greet(name) -> str"


def _mathutil_source() -> str:
    """The definition file: the function lives on the first line."""
    return "def greet(name):\n    return name\n"


def _app_source() -> str:
    """The call-site file: import on row 0, blank, call on row 2."""
    return "from mathutil import greet\n\ngreet(1)\n"


class _NavFakeClient:
    """Fake READY LSP client serving canned navigation payloads.

    ``server_capabilities`` declares definition / references / hover /
    documentSymbol providers so the capability gate passes; the
    definition and references answers point at the two fixture files,
    whose URIs are frozen by :func:`_install_nav_server`.
    """

    def __init__(self, config: ServerConfig, root: Path) -> None:
        self.config = config
        self.root_path = root
        from yate.editor_lsp import ServerState
        self.state = ServerState.READY
        self.error = ""
        self.trigger_characters: tuple[str, ...] = (".",)
        self.server_capabilities: dict[str, object] = {
            "definitionProvider": True,
            "referencesProvider": True,
            "hoverProvider": True,
            "documentSymbolProvider": True,
        }
        #: Frozen by the factory: URIs of the definition / call-site files.
        self.def_uri: str = ""
        self.call_uri: str = ""
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
        """Serve the canned navigation / hover payload for *method*."""
        future: asyncio.Future[object] = (
            asyncio.get_running_loop().create_future()
        )
        if method == "textDocument/definition":
            future.set_result([_location(self.def_uri, _DEF_ROW, _DEF_COL)])
        elif method == "textDocument/references":
            future.set_result([
                _location(self.def_uri, _DEF_ROW, _DEF_COL),
                _location(self.call_uri, _CALL_ROW, _CALL_COL),
            ])
        elif method == "textDocument/hover":
            future.set_result({"contents": _HOVER_TEXT})
        else:
            future.set_result(None)
        return 1, future

    def settle_request(self, request_id: int) -> None:
        """Fake settle: mirrors the real client's pending cleanup."""
        return None

    async def send_cancel(self, request_id: int) -> None:
        """Fake cancel: discards the request id."""
        return None


def _location(uri: str, row: int, col: int) -> dict[str, object]:
    """One ``Location`` wire payload against *uri* at (row, col)."""
    return {
        "uri": uri,
        "range": {
            "start": {"line": row, "character": col},
            "end": {"line": row, "character": col + 5},
        },
    }


def _install_nav_server(
    app: YateApp,
    def_path: Path,
    call_path: Path,
    holder: list[_NavFakeClient],
) -> None:
    """Register the fake navigation server for ``.py`` documents."""
    def_uri = canonical_uri(path_to_uri(def_path))
    call_uri = canonical_uri(path_to_uri(call_path))

    def factory(config: ServerConfig, root: Path) -> LspClient:
        client = _NavFakeClient(config, root)
        client.def_uri = def_uri
        client.call_uri = call_uri
        holder.append(client)
        return cast(LspClient, client)

    app.editor.lsp.register_server(ServerConfig(
        name="nav-fake", command="fake", filetypes=["txt"],
    ))
    app.editor.lsp.set_client_factory(factory)


def _two_file_project(tmp: Path) -> tuple[Path, Path]:
    """Write the two fixture files and return (definition, call-site).

    ``.txt`` on purpose: the built-in python_lsp extension claims ``.py``
    for its own (disabled) server, which would shadow the fake client.
    """
    def_path = tmp / "mathutil.txt"
    call_path = tmp / "app.txt"
    def_path.write_text(_mathutil_source(), encoding="utf-8")
    call_path.write_text(_app_source(), encoding="utf-8")
    return def_path, call_path


def _popup_text(popup: HoverPopup) -> str:
    """The popup's rendered text (private attribute read via ``getattr``)."""
    return cast(str, getattr(popup, "_text"))


async def _open_call_site(
    pilot: Any,  # noqa: Any - naming Pilot would import textual here
    app: YateApp,
    call_path: Path,
) -> None:
    """Open the call-site file and park the cursor on ``greet(1)``."""
    app.editor.document_flows.open_path(call_path)
    await pilot.pause()
    app.editor.session.buffer.set_cursor((_CALL_ROW, _CALL_COL))
    await pilot.pause()


async def _gd_jumps_across_files_in_both_keymaps(tmp: Path) -> ScenarioResult:
    """``gd`` on the call site jumps to the definition in both keymaps."""
    def_path, call_path = _two_file_project(tmp)
    app = new_app(target=tmp / "app.txt")
    checks: list[Check] = []
    holder: list[_NavFakeClient] = []
    _install_nav_server(app, def_path, call_path, holder)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        app.editor.refresh_ui()
        ready = await wait_until(
            pilot, lambda: app.editor.lsp.is_open(app.editor.session.doc)
        )
        checks.append(Check("did_open_call_site", True, ready))
        await _open_call_site(pilot, app, call_path)

        # Phase 1: vsc keymap, <alt-g> (the shared GOTO_DEF_VSC_KEY).
        await pilot.press("alt+g")
        jumped = await wait_until(
            pilot,
            lambda: app.editor.session.doc.path == def_path
            and app.editor.session.buffer.cursor == (_DEF_ROW, _DEF_COL),
        )
        checks.append(Check("jump_vsc", True, jumped))
        checks.append(Check(
            "jump_message_vsc", True,
            "jumped to" in message_text(app),
        ))

        # Phase 2: switch to vim, then the gd chord must do the same from
        # the call site again (the keymap-switch hook reopens the file).
        app.editor.execute_action("toggle_keymap")
        await pilot.pause()
        checks.append(Check("keymap", "vim", app.editor.keymaps.name))
        app.editor.document_flows.open_path(call_path)
        await pilot.pause()
        app.editor.session.buffer.set_cursor((_CALL_ROW, _CALL_COL))
        await pilot.pause()
        await pilot.press("g")
        await pilot.press("d")
        jumped_vim = await wait_until(
            pilot,
            lambda: app.editor.session.doc.path == def_path
            and app.editor.session.buffer.cursor == (_DEF_ROW, _DEF_COL),
        )
        checks.append(Check("jump_vim", True, jumped_vim))
        checks.append(Check(
            "jump_message_vim", True,
            "jumped to" in message_text(app),
        ))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult(
        "lsp_navigation_gd_jumps_across_files_in_both_keymaps",
        checks, rows,
    )


async def _gr_chooser_lists_both_files_and_enter_navigates(
    tmp: Path,
) -> ScenarioResult:
    """``gr`` opens a chooser naming both files; enter navigates."""
    def_path, call_path = _two_file_project(tmp)
    app = new_app(target=tmp / "app.txt")
    checks: list[Check] = []
    holder: list[_NavFakeClient] = []
    _install_nav_server(app, def_path, call_path, holder)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        app.editor.refresh_ui()
        await _open_call_site(pilot, app, call_path)
        # The chooser test runs in the vim keymap: the gr chord.
        app.editor.execute_action("toggle_keymap")
        await pilot.pause()
        await pilot.press("g")
        await pilot.press("r")

        def _chooser() -> LspChooserScreen | None:
            """The top-most chooser screen on the stack, or ``None``."""
            for screen in reversed(app.screen_stack):
                if isinstance(screen, LspChooserScreen):
                    return screen
            return None

        chooser_open = await wait_until(pilot, lambda: _chooser() is not None)
        checks.append(Check("chooser_open", True, chooser_open))
        chooser = _chooser()
        assert chooser is not None
        labels = [row.label for row in chooser.rows]
        checks.append(Check(
            "both_files_listed", True,
            "mathutil.txt" in labels and "app.txt" in labels,
        ))
        rows = snapshot_svg(app, tmp)
        rendered = "".join(rows.values())
        checks.append(Check(
            "svg_shows_both_files", True,
            "mathutil.txt" in rendered and "app.txt" in rendered,
        ))
        # Enter picks the selected row (the definition, listed first).
        await pilot.press("enter")
        navigated = await wait_until(
            pilot,
            lambda: app.editor.session.doc.path == def_path
            and app.editor.session.buffer.cursor == (_DEF_ROW, _DEF_COL),
        )
        checks.append(Check("enter_navigates", True, navigated))
        checks.append(Check(
            "enter_message", True,
            "jumped to" in message_text(app),
        ))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult(
        "lsp_navigation_gr_chooser_lists_both_files_and_enter_navigates",
        checks, rows,
    )


async def _k_and_f7_render_the_same_hover_text(tmp: Path) -> ScenarioResult:
    """``K`` and ``F7`` both render the identical hover card text."""
    def_path, call_path = _two_file_project(tmp)
    app = new_app(target=tmp / "app.txt")
    checks: list[Check] = []
    holder: list[_NavFakeClient] = []
    _install_nav_server(app, def_path, call_path, holder)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        app.editor.refresh_ui()
        await _open_call_site(pilot, app, call_path)
        app.editor.execute_action("toggle_keymap")
        await pilot.pause()
        popup = app.editor.hover_popup
        await wait_until(pilot, lambda: popup.is_mounted)

        await pilot.press("K")
        shown_k = await wait_until(pilot, lambda: popup.is_open)
        checks.append(Check("K_opens", True, shown_k))
        text_k = _popup_text(popup)
        checks.append(Check("K_text", _HOVER_TEXT, text_k))

        # F7 (the retained hover key) must render the same card.
        await pilot.press("escape")
        await wait_until(pilot, lambda: not popup.is_open)
        await pilot.press("f7")
        shown_f7 = await wait_until(pilot, lambda: popup.is_open)
        checks.append(Check("f7_opens", True, shown_f7))
        checks.append(Check(
            "f7_text_same_as_k", text_k, _popup_text(popup),
        ))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult(
        "lsp_navigation_k_and_f7_render_the_same_hover_text",
        checks, rows,
    )


async def _no_server_warns_and_leaves_buffer_untouched(
    tmp: Path,
) -> ScenarioResult:
    """With no server, ``gd`` warns explicitly and edits nothing."""
    call_path = tmp / "app.txt"
    call_path.write_text(_app_source(), encoding="utf-8")
    app = new_app(target=call_path)
    checks: list[Check] = []
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await pilot.pause()
        # No server registered at all: the shared vsc key still reaches
        # the flow, which must answer with an explicit warning.
        message_before = message_text(app)
        lines_before = list(app.editor.session.doc.buffer.lines)
        await pilot.press("alt+g")
        warned = await wait_until(
            pilot, lambda: "unavailable" in message_text(app)
        )
        checks.append(Check("warning_message", True, warned))
        checks.append(Check(
            "buffer_unchanged", lines_before,
            list(app.editor.session.doc.buffer.lines),
        ))
        checks.append(Check(
            "no_popup", False, app.editor.hover_popup.is_open,
        ))
        checks.append(Check(
            "message_changed", False, message_text(app) == message_before,
        ))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult(
        "lsp_navigation_no_server_warns_and_leaves_buffer_untouched",
        checks, rows,
    )


async def _quickfix_panel_next_prev_and_jump_back(tmp: Path) -> ScenarioResult:
    """``gr`` fills the quickfix panel; alt+j/k step and alt+left undoes.

    Entry order mirrors the server answer (definition first, call site
    second), so the fresh panel selects the definition entry at index 0:
    ``alt+j`` lands on the call-site entry, ``alt+k`` steps back to the
    definition row in the other file, and ``alt+left`` pops the one
    jump-list entry pushed by the quickfix jumps.
    """
    def_path, call_path = _two_file_project(tmp)
    app = new_app(target=tmp / "app.txt")
    checks: list[Check] = []
    holder: list[_NavFakeClient] = []
    _install_nav_server(app, def_path, call_path, holder)
    panel = app.editor.quickfix_panel
    flows = app.editor.quickfix_flows
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        app.editor.refresh_ui()
        await _open_call_site(pilot, app, call_path)

        # gr dual-publishes: the chooser opens AND the result set lands
        # in the quickfix list.
        await pilot.press("alt+r")
        filled = await wait_until(pilot, lambda: len(flows.active_entries) == 2)
        checks.append(Check("entries_filled", 2, len(flows.active_entries)))
        checks.append(Check("filled", True, filled))
        # Dismiss the chooser, then open the docked panel explicitly.
        await pilot.press("escape")
        await run_command(pilot, "quickfix")
        shown = await wait_until(pilot, lambda: panel.display)
        checks.append(Check("panel_display", True, shown))
        rows = snapshot_svg(app, tmp)
        rendered = "".join(rows.values())
        checks.append(Check(
            "svg_shows_references", True, "references |" in rendered,
        ))
        checks.append(Check(
            "svg_shows_file_name", True,
            "mathutil.txt" in rendered and "app.txt" in rendered,
        ))

        # alt+j steps forward onto the call-site entry (index 1).
        await pilot.press("alt+j")
        next_entry = await wait_until(pilot, lambda: flows.selected == 1)
        checks.append(Check("next_selected", 1, flows.selected))
        checks.append(Check("next_selected_ok", True, next_entry))
        landed_next = await wait_until(
            pilot,
            lambda: app.editor.session.doc.path == call_path
            and app.editor.session.buffer.cursor == (_CALL_ROW, _CALL_COL),
        )
        checks.append(Check("next_cursor", True, landed_next))

        # alt+k steps back onto the definition entry (index 0, other file).
        await pilot.press("alt+k")
        prev_entry = await wait_until(pilot, lambda: flows.selected == 0)
        checks.append(Check("prev_selected", 0, flows.selected))
        checks.append(Check("prev_selected_ok", True, prev_entry))
        landed_prev = await wait_until(
            pilot,
            lambda: app.editor.session.doc.path == def_path
            and app.editor.session.buffer.cursor == (_DEF_ROW, _DEF_COL),
        )
        checks.append(Check("prev_cursor", True, landed_prev))
        checks.append(Check("panel_still_shown", True, panel.display))

        # alt+left pops the single jump-list entry pushed by the quickfix
        # jumps and returns to the pre-jump position.
        back_before = len(app.editor.session.jumps.stacks()[0])
        await pilot.press("alt+left")
        back_len = await wait_until(
            pilot,
            lambda: len(app.editor.session.jumps.stacks()[0]) == back_before - 1,
        )
        checks.append(Check(
            "back_stack_decreased", back_before - 1,
            len(app.editor.session.jumps.stacks()[0]),
        ))
        checks.append(Check("back_stack_ok", True, back_len))
        landed_back = await wait_until(
            pilot,
            lambda: app.editor.session.doc.path == call_path
            and app.editor.session.buffer.cursor == (_CALL_ROW, _CALL_COL),
        )
        checks.append(Check("jump_back_position", True, landed_back))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult(
        "quickfix_panel_next_prev_and_jump_back",
        checks, rows,
    )


SCENARIOS: list[Scenario] = [
    Scenario(
        "lsp_navigation_gd_jumps_across_files_in_both_keymaps",
        _gd_jumps_across_files_in_both_keymaps,
        ("lsp-navigation",),
    ),
    Scenario(
        "lsp_navigation_gr_chooser_lists_both_files_and_enter_navigates",
        _gr_chooser_lists_both_files_and_enter_navigates,
        ("lsp-navigation",),
    ),
    Scenario(
        "lsp_navigation_k_and_f7_render_the_same_hover_text",
        _k_and_f7_render_the_same_hover_text,
        ("lsp-navigation",),
    ),
    Scenario(
        "lsp_navigation_no_server_warns_and_leaves_buffer_untouched",
        _no_server_warns_and_leaves_buffer_untouched,
        ("lsp-navigation",),
    ),
    Scenario(
        "quickfix_panel_next_prev_and_jump_back",
        _quickfix_panel_next_prev_and_jump_back,
        ("lsp-navigation",),
    ),
]
