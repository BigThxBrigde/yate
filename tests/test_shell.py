"""Shell execution (``services.shell``) and shell discovery (``editor_term.shells``).

``run_shell`` goes through the platform shell, so the command strings used here
are valid for both ``cmd.exe`` and ``/bin/sh``.  The discovery tests cover the
platform-exclusive branches behind ``sys.platform`` guards: a single CI run can
only reach its own platform's half, which is why both halves are written out.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

from yate.editor_term.shells import resolve_shell, shell_label
from yate.services.shell import ShellResult, run_shell, shell_name

_WINDOWS = sys.platform.startswith("win")


def _which(mapping: dict[str, str | None]) -> Any:
    """A ``shutil.which`` replacement driven by *mapping*."""

    def fake_which(command: str) -> str | None:
        return mapping.get(command)

    return fake_which


# --- run_shell --------------------------------------------------------------


def test_run_shell_captures_stdout_and_success(tmp_path: Path) -> None:
    """A successful command reports its output, cwd and ok flag."""
    result = run_shell("echo hello", cwd=tmp_path)
    assert result.ok is True
    assert result.returncode == 0
    assert "hello" in result.output
    assert result.cwd == tmp_path
    assert result.command == "echo hello"


def test_run_shell_appends_stderr_on_its_own_line() -> None:
    """stderr is folded into the captured output."""
    result = run_shell("echo oops 1>&2")
    assert result.returncode == 0
    assert "oops" in result.output


def test_run_shell_reports_a_non_zero_exit_code() -> None:
    """A failing command keeps its exit code instead of raising."""
    result = run_shell("exit 3")
    assert result.returncode == 3
    assert result.ok is False


def test_run_shell_times_out_with_a_message() -> None:
    """A command that outlives the timeout returns the synthetic 124 code."""
    command = f'"{sys.executable}" -c "import time; time.sleep(5)"'
    result = run_shell(command, timeout=0.2)
    assert result.returncode == 124
    assert "timed out after 0.2s" in result.output


def test_run_shell_defaults_to_the_process_cwd() -> None:
    """Without an explicit cwd the current directory is used."""
    assert run_shell("echo hi").cwd == Path.cwd()


def test_shell_result_ok_tracks_the_return_code() -> None:
    """ok is exactly "return code zero"."""
    assert ShellResult("x", 0, "", Path.cwd()).ok is True
    assert ShellResult("x", 1, "", Path.cwd()).ok is False


def test_shell_name_matches_the_platform() -> None:
    """The reported shell name is the one run_shell actually uses."""
    assert shell_name() == ("cmd.exe" if _WINDOWS else "/bin/sh")


# --- resolve_shell ----------------------------------------------------------


def test_configured_shell_with_arguments_is_split() -> None:
    """A configured command line is split into executable plus arguments."""
    assert resolve_shell("/usr/bin/zsh -l") == ["/usr/bin/zsh", "-l"]


def test_configured_shell_without_a_path_stays_one_word() -> None:
    """A bare name is not mistaken for an existing file."""
    assert resolve_shell("pwsh") == ["pwsh"]


@pytest.mark.skipif(
    not _WINDOWS, reason="only Windows keeps an existing path verbatim"
)
def test_configured_existing_path_keeps_spaces(tmp_path: Path) -> None:
    """A real Windows path may contain spaces and is used unsplit."""
    exe = tmp_path / "my shell.exe"
    exe.write_text("", encoding="utf-8")
    assert resolve_shell(str(exe)) == [str(exe)]


def test_shell_label_uses_the_executable_name() -> None:
    """The panel header shows the executable's file name."""
    assert shell_label(["/usr/bin/bash", "-l"]) == "bash"
    assert shell_label([]) == "shell"


# --- platform default: Windows ---------------------------------------------


@pytest.mark.skipif(not _WINDOWS, reason="Windows default shell discovery")
def test_windows_default_prefers_pwsh(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PowerShell 7 on PATH wins and is started without a logo banner."""
    monkeypatch.setattr(
        "yate.editor_term.shells.shutil.which",
        _which({"pwsh": r"C:\tools\pwsh.exe"}),
    )
    assert resolve_shell("") == [r"C:\tools\pwsh.exe", "-NoLogo"]


@pytest.mark.skipif(not _WINDOWS, reason="Windows default shell discovery")
def test_windows_default_falls_back_to_bundled_powershell(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Without pwsh the bundled Windows PowerShell is used."""
    monkeypatch.setattr("yate.editor_term.shells.shutil.which", _which({}))
    system_root = tmp_path / "Windows"
    powershell = (
        system_root / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    )
    powershell.parent.mkdir(parents=True)
    powershell.write_text("", encoding="utf-8")
    monkeypatch.setenv("SystemRoot", str(system_root))
    assert resolve_shell("") == [str(powershell), "-NoLogo"]


@pytest.mark.skipif(not _WINDOWS, reason="Windows default shell discovery")
def test_windows_default_uses_comspec_then_cmd(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """COMSPEC wins over a PATH lookup, which is the final fallback."""
    monkeypatch.setattr("yate.editor_term.shells.shutil.which", _which({}))
    monkeypatch.setenv("SystemRoot", str(tmp_path))  # no bundled PowerShell
    comspec = tmp_path / "cmd.exe"
    comspec.write_text("", encoding="utf-8")
    monkeypatch.setenv("COMSPEC", str(comspec))
    assert resolve_shell("") == [str(comspec)]

    monkeypatch.setenv("COMSPEC", str(tmp_path / "missing.exe"))
    monkeypatch.setattr(
        "yate.editor_term.shells.shutil.which", _which({"cmd.exe": r"C:\cmd.exe"})
    )
    assert resolve_shell("") == [r"C:\cmd.exe"]

    monkeypatch.setattr("yate.editor_term.shells.shutil.which", _which({}))
    assert resolve_shell("") == ["cmd.exe"]


# --- platform default: POSIX ------------------------------------------------


@pytest.mark.skipif(_WINDOWS, reason="POSIX default shell discovery")
def test_posix_default_prefers_the_shell_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """$SHELL wins when it points at an existing file."""
    shell = tmp_path / "zsh"
    shell.write_text("", encoding="utf-8")
    monkeypatch.setenv("SHELL", str(shell))
    assert resolve_shell("") == [str(shell)]


@pytest.mark.skipif(_WINDOWS, reason="POSIX default shell discovery")
def test_posix_default_falls_back_to_bash_then_sh(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A missing $SHELL falls back to bash on PATH, then /bin/sh."""
    monkeypatch.setenv("SHELL", "/nonexistent/shell")
    monkeypatch.setattr(
        "yate.editor_term.shells.shutil.which", _which({"bash": "/bin/bash"})
    )
    assert resolve_shell("") == ["/bin/bash"]

    monkeypatch.setattr("yate.editor_term.shells.shutil.which", _which({}))
    assert resolve_shell("") == ["/bin/sh"]
