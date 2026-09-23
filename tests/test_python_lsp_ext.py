"""The bundled Python LSP extension: server discovery and registration.

Loads the shipped ``yate/extensions/python_lsp.py`` through the real
``ExtensionLoader`` and asserts what it registers on a recording LSP stand-in,
so discovery order, the environment override and the settings hand-off are all
exercised without spawning a server.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, cast

import pytest

from yate.editor_lsp.client import ServerConfig
from yate.extensions import python_lsp
from yate.services.extensions import ExtensionAPI, ExtensionContext, ExtensionLoader

_EXT_PATH = (
    Path(__file__).resolve().parent.parent / "yate" / "extensions" / "python_lsp.py"
)


class _LspRecorder:
    """Minimal ``LspManager`` stand-in that records the registrations."""

    def __init__(self) -> None:
        self.configs: list[ServerConfig] = []

    def register_server(self, config: ServerConfig) -> None:
        self.configs.append(config)


def _load_extension(recorder: _LspRecorder) -> ServerConfig:
    """Load the bundled extension and return the server config it registered."""
    ctx = ExtensionContext(
        session=cast(Any, None),
        workspace=cast(Any, None),
        lsp=cast(Any, recorder),
        keymaps=cast(Any, None),
        actions=cast(Any, None),
        commands=cast(Any, None),
        message=lambda _text: None,
        run_shell=lambda _command, _show: None,
        open_path=lambda _path: None,
        save=lambda: None,
    )
    record = ExtensionLoader(ExtensionAPI(ctx)).load_file(_EXT_PATH)
    assert record.error is None, record.error or ""
    assert len(recorder.configs) == 1
    return recorder.configs[0]


def _which(mapping: dict[str, str | None]) -> Any:
    """A ``shutil.which`` replacement driven by *mapping*."""

    def fake_which(command: str, *_args: Any) -> str | None:
        return mapping.get(command)

    return fake_which


# --- registration -----------------------------------------------------------


def test_bundled_extension_registers_the_python_server(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The shipped extension registers one python server with py/pyi filetypes."""
    monkeypatch.setenv("YATE_PYTHON_LSP", "pyright-langserver --stdio")
    recorder = _LspRecorder()
    config = _load_extension(recorder)

    assert config.name == "python"
    assert config.command == "pyright-langserver"
    assert config.args == ["--stdio"]
    assert config.filetypes == ["py", "pyi"]
    assert config.language_ids == {"py": "python", "pyi": "python"}
    assert "pyproject.toml" in config.root_markers
    assert ".git" in config.root_markers


def test_pyright_registration_points_at_the_running_interpreter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A pyright-derived command gets the ``python.pythonPath`` setting."""
    monkeypatch.setenv("YATE_PYTHON_LSP", "pyright-langserver --stdio")
    config = _load_extension(_LspRecorder())
    assert config.settings == {"python": {"pythonPath": sys.executable}}


def test_pylsp_registration_carries_no_python_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Servers that are not pyright do not get pyright-specific settings."""
    monkeypatch.setenv("YATE_PYTHON_LSP", "pylsp")
    config = _load_extension(_LspRecorder())
    assert config.args == []
    assert config.settings is None


def test_frozen_builds_register_without_python_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A frozen executable has no interpreter to point pyright at."""
    monkeypatch.setenv("YATE_PYTHON_LSP", "pyright-langserver --stdio")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert _load_extension(_LspRecorder()).settings is None


def test_missing_server_still_registers_an_empty_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With no server available the registration stays visible but empty."""
    monkeypatch.setenv("YATE_PYTHON_LSP", "off")
    assert python_lsp.discover_command() == ("", [])
    assert _load_extension(_LspRecorder()).command == ""


# --- discovery --------------------------------------------------------------


@pytest.mark.parametrize("value", ["0", "off", "false", "none", "no", "OFF"])
def test_override_opt_out_disables_discovery(
    value: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every opt-out spelling of the override registers no server."""
    monkeypatch.setenv("YATE_PYTHON_LSP", value)
    assert python_lsp.discover_command() == ("", [])


def test_override_is_split_with_shell_quoting(monkeypatch: pytest.MonkeyPatch) -> None:
    """The override is a full command line, quoted arguments included."""
    monkeypatch.setenv("YATE_PYTHON_LSP", 'mypy-langserver --verbose "two words"')
    assert python_lsp.discover_command() == (
        "mypy-langserver",
        ["--verbose", "two words"],
    )


def test_blank_override_falls_through_to_the_path_lookup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An empty override is ignored and PATH is searched instead."""
    monkeypatch.setenv("YATE_PYTHON_LSP", "   ")
    monkeypatch.setattr(
        "yate.extensions.python_lsp.shutil.which",
        _which({"pyright-langserver": "/usr/bin/pyright-langserver"}),
    )
    assert python_lsp.discover_command() == ("/usr/bin/pyright-langserver", ["--stdio"])


def test_venv_launcher_is_used_when_path_lacks_the_server(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A launcher beside the interpreter wins over pylsp on PATH."""
    monkeypatch.delenv("YATE_PYTHON_LSP", raising=False)
    launcher = tmp_path / "pyright-langserver.cmd"
    launcher.write_text("@echo off\n", encoding="utf-8")
    fake_python = tmp_path / "python.exe"
    fake_python.write_text("", encoding="utf-8")
    monkeypatch.setattr("yate.extensions.python_lsp.sys.executable", str(fake_python))
    monkeypatch.setattr(
        "yate.extensions.python_lsp.shutil.which",
        _which({"pylsp": "/usr/bin/pylsp"}),
    )
    assert python_lsp.discover_command() == (str(launcher), ["--stdio"])


def test_no_server_at_all_yields_an_empty_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Nothing on PATH and no venv launcher leaves the command empty."""
    monkeypatch.delenv("YATE_PYTHON_LSP", raising=False)
    monkeypatch.setattr(
        "yate.extensions.python_lsp.sys.executable", str(tmp_path / "python.exe")
    )
    monkeypatch.setattr(
        "yate.extensions.python_lsp.shutil.which", _which({})
    )
    assert python_lsp.discover_command() == ("", [])


def test_pylsp_is_the_last_resort(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without pyright anywhere, pylsp on PATH is used as-is."""
    monkeypatch.delenv("YATE_PYTHON_LSP", raising=False)
    # the venv launcher lookup must also come up empty, otherwise it wins
    monkeypatch.setattr(
        "yate.extensions.python_lsp.sys.executable", str(tmp_path / "python.exe")
    )
    monkeypatch.setattr(
        "yate.extensions.python_lsp.shutil.which",
        _which({"pylsp": "/usr/bin/pylsp"}),
    )
    assert python_lsp.discover_command() == ("/usr/bin/pylsp", [])
