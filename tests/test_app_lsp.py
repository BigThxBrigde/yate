"""LSP / extensions headless Textual UI tests (run via pilot, no real terminal)."""

# tests legitimately poke at internals:
# pyright: reportPrivateUsage=false

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, cast
import pytest
from yate.app import YateApp
from conftest import plain_text, wait_until

# ----------------------------------------------------- rc-declared extensions


def test_rc_declared_file_and_directory_extensions_load(tmp_path: Path) -> None:
    from yate.yaterc import load_config

    async def scenario() -> None:
        root = tmp_path
        # a single-file extension registering a :command
        (root / "myext.py").write_text(
            "def setup(api):\n"
            '    @api.command("rcping", "rc test command")\n'
            "    def rcping(args):\n"
            '        api.message("pong")\n',
            encoding="utf-8",
        )
        # a directory extension
        bundle = root / "bundle"
        bundle.mkdir()
        (bundle / "dir_ext.py").write_text(
            "def setup(api):\n"
            '    api.register_action("rc-action", lambda: None)\n',
            encoding="utf-8",
        )
        rc = root / "yaterc"
        rc.write_text('extensions = ["myext.py", "bundle"]\n', encoding="utf-8")

        config = load_config([rc])
        assert config.errors == []
        app = YateApp(config=config)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            assert "rcping" in app.editor.commands.names()
            loaded = {rec.name for rec in app.editor.extension_loader.loaded}
            assert "myext" in loaded
            assert "dir_ext" in loaded
            assert all(rec.error is None for rec in app.editor.extension_loader.loaded)

    asyncio.run(scenario())


# ---------------------------------------------------------- bundled extensions


def test_bundled_extensions_load_regardless_of_cwd(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    async def scenario() -> None:
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            records = {
                r.name: r for r in app.editor.extension_loader.loaded
            }
            assert "python_lsp" in records
            # csharp highlighting is built-in now: the bundled script is gone
            assert "csharp_highlight" not in records
            # the .example template is never auto-loaded
            assert "example_ext" not in records
            assert records["python_lsp"].error is None

    monkeypatch.chdir(tmp_path)
    asyncio.run(scenario())


def test_disabled_extensions_skip_bundled_not_project_dir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from yate.config import YateConfig
    from yate.services import trust

    root = tmp_path
    project_ext = root / "extensions"
    project_ext.mkdir()
    (project_ext / "myext.py").write_text(
        "def setup(api):\n    pass\n", encoding="utf-8"
    )
    config = YateConfig(disabled_extensions=["python_lsp"])
    monkeypatch.setattr(trust, "TRUST_FILE", root / "trusted_workspaces")

    async def scenario() -> None:
        app = YateApp(config=config)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            names = {r.name for r in app.editor.extension_loader.loaded}
            assert "python_lsp" not in names
            # an untrusted workspace must not run its project scripts
            assert "myext" not in names
            assert any(
                "skipped untrusted" in message
                for message in app.editor._ext_messages
            )
            # and no Python server got registered while LSP was off
            assert app.editor.lsp.config_for("py") is None
            # :trust is the explicit confirmation that loads them now
            app.editor.extension_flows.trust_cwd_extensions()
            await pilot.pause()
            names = {r.name for r in app.editor.extension_loader.loaded}
            assert "myext" in names
        assert (root / "trusted_workspaces").exists()

    monkeypatch.chdir(root)
    asyncio.run(scenario())


def test_rc_same_stem_extension_is_named_as_shadowed(tmp_path: Path) -> None:
    # An rc-declared script with a bundled default's stem loads first, but
    # the last-write-wins registrars would let the bundled default take
    # over: the conflict must surface as a startup warning.
    from yate.config import YateConfig

    root = tmp_path
    rc_dir = root / "rc_extensions"
    rc_dir.mkdir()
    (rc_dir / "python_lsp.py").write_text(
        "def setup(api):\n    pass\n", encoding="utf-8"
    )
    config = YateConfig(extension_paths=[rc_dir])

    async def scenario() -> None:
        app = YateApp(config=config)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            messages = app.editor._ext_messages
            assert any(
                "python_lsp" in m
                and "shadowed by the bundled default" in m
                for m in messages
            ), messages

    asyncio.run(scenario())


def test_disabled_bundled_extension_does_not_warn_shadow(
    tmp_path: Path,
) -> None:
    # Disabling the bundled default removes the collision entirely.
    from yate.config import YateConfig

    root = tmp_path
    rc_dir = root / "rc_extensions"
    rc_dir.mkdir()
    (rc_dir / "python_lsp.py").write_text(
        "def setup(api):\n    pass\n", encoding="utf-8"
    )
    config = YateConfig(
        extension_paths=[rc_dir],
        disabled_extensions=["python_lsp"],
    )

    async def scenario() -> None:
        app = YateApp(config=config)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            messages = app.editor._ext_messages
            assert not any(
                "shadowed by the bundled default" in m for m in messages
            ), messages

    asyncio.run(scenario())


def test_rc_declaring_the_bundled_dir_does_not_warn_shadow(
    tmp_path: Path,
) -> None:
    # An rc extension_paths entry that *is* the bundled directory loads the
    # same scripts; de-duplication hands back the identical record, which
    # must not be reported as shadowing itself.
    from yate.config import YateConfig
    from yate.paths import bundled_extensions_dir

    config = YateConfig(extension_paths=[bundled_extensions_dir()])

    async def scenario() -> None:
        app = YateApp(config=config)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            messages = app.editor._ext_messages
            assert not any(
                "shadowed by the bundled default" in m for m in messages
            ), messages

    asyncio.run(scenario())


# ----------------------------------------------------------------- LSP UI fake


def _install_fake_server(  # noqa: Any - fake LSP server boundary; no stubs
    app: YateApp, completions: list[dict[str, Any]] | None = None
) -> list[Any]:
    from yate.editor_lsp.client import ServerConfig

    created: list[Any] = []
    completions = completions if completions is not None else [
        {"label": "barbell", "insertText": "barbell", "kind": 3,
         "detail": "(object)"},
        {"label": "baritone", "insertText": "baritone", "kind": 3},
        {"label": "baz", "insertText": "baz", "kind": 5},
    ]

    class UiFakeClient:
        """Fake LSP double recording ``didOpen`` and serving canned completions."""

        def __init__(self, config: Any, root: Any) -> None:
            self.config = config
            self.root_path = root
            from yate.editor_lsp import ServerState
            self.state = ServerState.READY
            self.error = ""
            self.trigger_characters: tuple[str, ...] = (".",)
            self.opened: list[Any] = []
            created.append(self)

        async def start(self) -> None:
            """Fake start: nothing to launch, the client stays READY."""
            return None

        async def stop(self) -> None:
            """Fake stop: flips the state to STOPPED."""
            from yate.editor_lsp import ServerState
            self.state = ServerState.STOPPED

        async def notify(self, method: str, params: Any) -> None:
            """Fake notify: records ``didOpen`` payloads."""
            if method == "textDocument/didOpen":
                self.opened.append(params)

        async def request(self, method: str, params: Any) -> Any:
            """Fake request: serves the canned completion list."""
            return {"isIncomplete": False, "items": completions}

        async def start_request(self, method: str, params: Any) -> Any:
            """Fake start_request: returns an already-done future."""
            import asyncio
            future: asyncio.Future[Any] = asyncio.get_running_loop().create_future()
            future.set_result({"isIncomplete": False, "items": completions})
            return 1, future

        async def send_cancel(self, request_id: int) -> None:
            """Fake cancel: discards the request id."""
            return None

        def publish_diagnostics(  # noqa: Any - fake LSP server boundary; no stubs
            self, manager: Any, uri: str, entries: list[dict[str, Any]]
        ) -> None:
            """Fake diagnostics pump: forwards entries to the manager."""
            manager.handle_notification(
                "textDocument/publishDiagnostics",
                {"uri": uri, "diagnostics": entries},
            )

    def factory(config: Any, root: Any) -> Any:
        return UiFakeClient(config, root)

    app.editor.lsp.register_server(ServerConfig(
        name="python", command="fake", filetypes=["py"],
    ))
    # factory must be installed on the manager after registration; the
    # manager keeps it independent of config replacement
    app.editor.lsp.set_client_factory(factory)
    return created


def test_completion_popup_navigate_accept_and_ctrl_space(tmp_path: Path) -> None:
    async def scenario() -> None:
        py = tmp_path / "m.py"
        py.write_text("ba\n", encoding="utf-8")
        app = YateApp(target=py)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            _install_fake_server(app)
            app.editor.refresh_ui()  # schedules didOpen on the freshly registered server
            await pilot.pause()

            def is_ready() -> bool:
                state = app.editor.lsp.state_for_doc(app.editor.session.doc)
                return state is not None and state.value == "ready"

            ready = await wait_until(pilot, is_ready)
            assert ready
            popup = app.editor.completion_popup
            assert popup is not None
            # cursor sits at doc start after open; move to end of "ba"
            app.editor.session.buffer.cursor = (0, 2)
            app.editor.refresh_ui()
            # manual trigger via ctrl+space at the end of "ba"
            await pilot.press("ctrl+space")
            shown = await wait_until(pilot, lambda: popup.is_open)
            assert shown
            assert popup.item_count == 3
            first = popup.selected()
            assert first is not None
            assert first.label == "barbell"
            # down wraps through the list, esc closes
            await pilot.press("down")
            second = popup.selected()
            assert second is not None
            assert second.label == "baritone"
            await pilot.press("escape")
            assert not popup.is_open
            # reopen and accept the second entry with tab
            await pilot.press("ctrl+space")
            await wait_until(pilot, lambda: popup.is_open)
            await pilot.press("down", "tab")
            await pilot.pause()
            assert not popup.is_open
            assert app.editor.session.buffer.lines[0] == "baritone"
            assert app.editor.session.doc.modified

    asyncio.run(scenario())


def test_diagnostic_render_status_echo_and_command(tmp_path: Path) -> None:
    from yate.editor_lsp import protocol
    from yate.editor_view.modals import OutputScreen

    async def scenario() -> None:
        py = tmp_path / "diag.py"
        py.write_text("x = 1\n", encoding="utf-8")
        app = YateApp(target=py)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            created = _install_fake_server(app)
            app.editor.refresh_ui()
            await pilot.pause()
            await wait_until(pilot, lambda: bool(created and created[0].opened))
            fake = created[0]
            uri = protocol.path_to_uri(py.resolve())
            fake.publish_diagnostics(app.editor.lsp, uri, [
                {"range": {"start": {"line": 0, "character": 0},
                           "end": {"line": 0, "character": 5}},
                 "severity": 1, "message": "undefined name 'x'",
                 "source": "pyright"},
            ])
            await pilot.pause()
            editor = app.editor.panes.active_view
            assert editor is not None
            line0 = "".join(seg.text for seg in editor.render_line(0))
            assert "✖" in line0  # gutter mark
            underlined = [
                seg for seg in editor.render_line(0)
                if seg.style is not None and seg.style.underline
            ]
            assert underlined
            # status bar carries the error count
            status_bar = app.editor.status_bar
            assert status_bar is not None
            assert "✖ 1" in plain_text(status_bar.content)
            # message line echoes the diagnostic under the cursor
            prompt_bar = app.editor.prompt_bar
            assert prompt_bar is not None
            app.editor.refresh_ui()
            assert "undefined name" in plain_text(prompt_bar.message.content)
            # :diagnostics opens the listing screen
            app.editor.run_command("diagnostics")
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, OutputScreen)
            assert "undefined name" in cast(OutputScreen, screen).output_text

    asyncio.run(scenario())


def test_builtin_python_extension_loads_cleanly() -> None:
    # The auto-loaded extension registers a (disabled) python server and
    # setup must neither print nor spawn nor record an error.
    async def scenario() -> None:
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            assert "python" in app.editor.lsp.config_names()
            rec = next(r for r in app.editor.extension_loader.loaded
                       if r.name == "python_lsp")
            assert rec.error is None

    asyncio.run(scenario())


def test_rc_configured_server_auto_activates_on_matching_file(
    tmp_path: Path,
) -> None:
    from yate.config import LanguageServerSpec, YateConfig

    rs = tmp_path / "main.rs"
    rs.write_text("fn main() {}\n", encoding="utf-8")
    config = YateConfig(language_servers=[LanguageServerSpec(
        name="rc-rust",
        command="fake-rust-analyzer",
        filetypes=["rs"],
        language_ids={"rs": "rust"},
        root_markers=["Cargo.toml", ".git"],
    )])
    created: list[Any] = []

    def factory(config: Any, root: Any) -> Any:
        return _RcClientShim(created, config, root)

    async def scenario() -> None:
        app = YateApp(target=rs, config=config)
        # factory must be in place before on_mount registers/opens docs
        app.editor.lsp.set_client_factory(factory)
        async with app.run_test(size=(100, 30)) as pilot:
            opened = await wait_until(pilot, lambda: app.editor.lsp.is_open(app.editor.session.doc))
            assert opened
            registered = app.editor.lsp.config_for("rs")
            assert registered is not None
            assert registered.name == "rc-rust"
            state = app.editor.lsp.state_for_doc(app.editor.session.doc)
            assert state is not None
            assert state.value == "ready"
            assert len(created) == 1
            params = created[0].opened[0]
            assert params["textDocument"]["languageId"] == "rust"

    asyncio.run(scenario())


def test_rc_configured_server_activates_on_later_open(tmp_path: Path) -> None:
    from yate.config import LanguageServerSpec, YateConfig

    rs = tmp_path / "later.rs"
    rs.write_text("let x = 1;\n", encoding="utf-8")
    config = YateConfig(language_servers=[LanguageServerSpec(
        name="rc-rust-late", command="fake-rust", filetypes=["rs"],
    )])

    async def scenario() -> None:
        app = YateApp(config=config)
        created: list[Any] = []

        def factory(config: Any, root: Any) -> Any:
            return _RcClientShim(created, config, root)

        app.editor.lsp.set_client_factory(factory)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            # unnamed scratch buffer: registered but nothing spawned
            assert created == []
            assert not app.editor.lsp.is_open(app.editor.session.doc)
            registered = app.editor.lsp.config_for("rs")
            assert registered is not None
            assert registered.name == "rc-rust-late"
            # omitted root_markers fall back to the built-in defaults
            from yate.editor_lsp.client import DEFAULT_ROOT_MARKERS
            assert registered.root_markers == list(DEFAULT_ROOT_MARKERS)
            # opening the matching file activates the server
            app.editor.document_flows.open_path(rs)
            await pilot.pause()
            activated = await wait_until(
                pilot, lambda: bool(created) and created[0].opened
            )
            assert activated
            assert app.editor.lsp.is_open(app.editor.session.doc)

    asyncio.run(scenario())


def test_rc_python_entry_overrides_builtin_extension(tmp_path: Path) -> None:
    # The bundled python_lsp extension registers a "python" server with
    # an empty command (YATE_PYTHON_LSP=off for the suite). A same-named
    # rc entry registered after extensions must replace it: opening a
    # .py file then talks to the rc server, not the disabled builtin one.
    from yate.config import LanguageServerSpec, YateConfig

    py = tmp_path / "app.py"
    py.write_text("print('hi')\n", encoding="utf-8")
    config = YateConfig(language_servers=[LanguageServerSpec(
        name="python",
        command="fake-pyright",
        args=["--stdio"],
        filetypes=["py", "pyi"],
        language_ids={"py": "python", "pyi": "python"},
        initialization_options={"diagnostics": True},
        settings={"python": {"version": "3"}},
        env={"FAKE_ENV": "1"},
        root_markers=["pyproject.toml", ".git"],
    )])

    async def scenario() -> None:
        app = YateApp(target=py, config=config)
        created: list[Any] = []

        def factory(config: Any, root: Any) -> Any:
            return _RcClientShim(created, config, root)

        app.editor.lsp.set_client_factory(factory)
        async with app.run_test(size=(100, 30)) as pilot:
            registered = await wait_until(
                pilot, lambda: app.editor.lsp.is_open(app.editor.session.doc)
            )
            assert registered
            cfg = app.editor.lsp.config_for("py")
            assert cfg is not None
            assert cfg.command == "fake-pyright"
            assert cfg.args == ["--stdio"]
            assert cfg.env == {"FAKE_ENV": "1"}
            assert cfg.root_markers == ["pyproject.toml", ".git"]
            assert cfg.initialization_options == {"diagnostics": True}
            assert cfg.settings == {"python": {"version": "3"}}
            assert cfg.language_id("pyi") == "python"
            assert len(created) == 1
            params = created[0].opened[0]
            assert params["textDocument"]["languageId"] == "python"
            # the disabled builtin registration left no failed client
            state = app.editor.lsp.state_for_doc(app.editor.session.doc)
            assert state is not None
            assert state.value == "ready"

    asyncio.run(scenario())


# ------------------------------------------------------------- fake LSP client


class _RcClientShim:
    """Module-level fake client built by the rc-server tests' factory."""

    def __init__(self, created: list[Any], config: Any, root: Any) -> None:
        from yate.editor_lsp import ServerState
        self.config = config
        self.root_path = root
        self.state = ServerState.READY
        self.error = ""
        self.trigger_characters: tuple[str, ...] = ()
        self.opened: list[Any] = []
        created.append(self)

    async def start(self) -> None:
        """Fake start: nothing to launch, the client stays READY."""
        return None

    async def stop(self) -> None:
        """Fake stop: flips the state to STOPPED."""
        from yate.editor_lsp import ServerState
        self.state = ServerState.STOPPED

    async def notify(self, method: str, params: Any) -> None:
        """Fake notify: records ``didOpen`` payloads."""
        if method == "textDocument/didOpen":
            self.opened.append(params)

    async def request(self, method: str, params: Any) -> Any:
        """Fake request: no scripted result, always ``None``."""
        return None

    async def start_request(self, method: str, params: Any) -> Any:
        """Fake start_request: future resolved with ``None``."""
        future: asyncio.Future[Any] = asyncio.get_running_loop().create_future()
        future.set_result(None)
        return 1, future

    async def send_cancel(self, request_id: int) -> None:
        """Fake cancel: discards the request id."""
        return None
