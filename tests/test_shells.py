"""Headless tests for integrated-terminal shell discovery (shells.py).

Only the platform-default resolution paths are exercised: they are gated on
``sys.platform`` at runtime, so the tests pin the platform string and stub
the PATH probes instead of depending on the host machine's installed shells.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from yate.editor_term.shells import resolve_shell


def _which_pwsh(name: str) -> str | None:
    """PATH probe stand-in: pwsh present, everything else missing."""
    return "C:/tools/pwsh/pwsh.exe" if name.startswith("pwsh") else None


def _which_bash(name: str) -> str | None:
    """PATH probe stand-in: bash present, everything else missing."""
    return "/usr/bin/bash" if name == "bash" else None


def _which_nothing(_name: str) -> str | None:
    """PATH probe stand-in: nothing installed."""
    return None


def test_resolve_shell_windows_default_picks_pwsh(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """On Windows an empty config prefers pwsh.exe and adds -NoLogo."""
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr("yate.editor_term.shells.shutil.which", _which_pwsh)
    assert resolve_shell("") == ["C:/tools/pwsh/pwsh.exe", "-NoLogo"]


def test_resolve_shell_posix_default_picks_shell_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """On POSIX an empty config uses $SHELL when the file exists."""
    monkeypatch.setattr(sys, "platform", "linux")
    fake_zsh = tmp_path / "zsh"
    fake_zsh.write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setenv("SHELL", str(fake_zsh))
    assert resolve_shell("") == [str(fake_zsh)]

    # a $SHELL pointing at a missing file falls through to the bash probe
    monkeypatch.setenv("SHELL", str(tmp_path / "missing" / "zsh"))
    monkeypatch.setattr("yate.editor_term.shells.shutil.which", _which_bash)
    assert resolve_shell("") == ["/usr/bin/bash"]


def test_resolve_shell_posix_default_falls_back_to_bash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without $SHELL the POSIX default walks bash, then /bin/sh."""
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.delenv("SHELL", raising=False)

    monkeypatch.setattr("yate.editor_term.shells.shutil.which", _which_bash)
    assert resolve_shell("") == ["/usr/bin/bash"]

    monkeypatch.setattr("yate.editor_term.shells.shutil.which", _which_nothing)
    assert resolve_shell("") == ["/bin/sh"]
