# pyright: reportPrivateUsage=false
"""Headless tests for the extension startup flow (ExtensionFlows).

Drives :meth:`yate.flows.extension_flows.ExtensionFlows.trust_cwd_extensions`
with a loader stub and a recording message line.  ``Path.cwd`` and the trust
store are pointed at ``tmp_path`` so no real workspace or user file is ever
touched; the symlink probe is stubbed because creating real symlinks needs
platform privileges.  Covered: the symlinked-cwd refusal, the "no extensions
directory" info, and per-extension failure reporting after a partial load.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import cast

import pytest

from yate.config import YateConfig
from yate.flows.extension_flows import ExtensionFlows
from yate.services.extensions import ExtensionAPI, ExtensionLoader
from yate.services.extensions.loader import LoadedExtension
from yate.services import trust as trust_mod


def _symlinked(_path: Path) -> bool:
    """Symlink-probe stand-in: every path reports a symlink component."""
    return True


def _link_free(_path: Path) -> bool:
    """Symlink-probe stand-in: every path reports no symlink component."""
    return False


class _LoaderStub:
    """ExtensionLoader stand-in: records directories, replays records."""

    def __init__(self, records: list[LoadedExtension]) -> None:
        self.records = records
        self.dirs: list[Path] = []

    def load_directory(
        self, directory: Path, *, exclude: Sequence[str] | None = None
    ) -> list[LoadedExtension]:
        self.dirs.append(directory)
        return self.records


class _ApiStub:
    """ExtensionAPI stand-in (never touched by the trust flow)."""


def _make_flows(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    records: list[LoadedExtension],
) -> tuple[ExtensionFlows, _LoaderStub, list[tuple[str, str]]]:
    """Point cwd and the trust store at tmp_path; build the flow."""
    def _fake_cwd(cls: type[Path]) -> Path:
        return tmp_path

    monkeypatch.setattr(Path, "cwd", classmethod(_fake_cwd))
    monkeypatch.setattr(
        trust_mod, "TRUST_FILE", tmp_path / "trusted_workspaces"
    )
    loader = _LoaderStub(records)
    messages: list[tuple[str, str]] = []
    flows = ExtensionFlows(
        extension_loader=cast(ExtensionLoader, loader),
        extension_api=cast(ExtensionAPI, _ApiStub()),
        config=YateConfig(),
        ext_dirs=[],
        ext_files=[],
        message=lambda text, kind: messages.append((text, kind)),
    )
    return flows, loader, messages


def test_trust_cwd_refuses_symlinked_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A symlinked cwd is refused before any extension directory is loaded."""
    monkeypatch.setattr(trust_mod, "_has_symlink_component", _symlinked)
    flows, loader, messages = _make_flows(tmp_path, monkeypatch, [])

    flows.trust_cwd_extensions()

    assert len(messages) == 1
    text, kind = messages[0]
    assert f"refused to trust {tmp_path}" in text
    assert "symlink component" in text
    assert kind == "error"
    assert loader.dirs == []


def test_trust_cwd_reports_missing_extensions_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A trusted cwd without extensions/ gets an info line; nothing loads."""
    monkeypatch.setattr(trust_mod, "_has_symlink_component", _link_free)
    flows, loader, messages = _make_flows(tmp_path, monkeypatch, [])

    flows.trust_cwd_extensions()

    assert len(messages) == 1
    text, kind = messages[0]
    assert text == f"trusted {tmp_path}; no extensions directory to load"
    assert kind == "info"
    assert loader.dirs == []


def test_trust_cwd_reports_each_failed_extension(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The loaded-count info is followed by one error line per failure."""
    monkeypatch.setattr(trust_mod, "_has_symlink_component", _link_free)
    ext_dir = tmp_path / "extensions"
    ext_dir.mkdir()
    records = [
        LoadedExtension(name="good", path=ext_dir / "good.py"),
        LoadedExtension(name="bad", path=ext_dir / "bad.py", error="boom"),
    ]
    flows, loader, messages = _make_flows(tmp_path, monkeypatch, records)

    flows.trust_cwd_extensions()

    assert loader.dirs == [ext_dir]
    assert len(messages) == 2
    info_text, info_kind = messages[0]
    assert info_text == f"trusted {tmp_path}; loaded 1 extension(s) from {ext_dir}"
    assert info_kind == "info"
    assert messages[1] == ("extension bad: boom", "error")
