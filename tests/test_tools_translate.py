"""Tests for the Markdown translator (:mod:`tools.translate`).

Every test monkeypatches the subprocess call inside
:mod:`tools.translate.runner`, so no network access or local CLI is needed.
"""

from __future__ import annotations

import io
import subprocess
import sys
import types
from pathlib import Path
from typing import cast

import pytest
from tools.translate import cli, runner


def _patch_run(
    monkeypatch: pytest.MonkeyPatch,
    returncode: int = 0,
    stdout: str = "",
    stderr: str = "",
) -> list[dict[str, object]]:
    """Replace ``subprocess.run`` in :mod:`tools.translate.runner`.

    Returns the list of captured call records (the argv under key
    ``"argv"``, the keyword arguments spread alongside) so tests can assert
    on the assembled command.
    """
    calls: list[dict[str, object]] = []

    def _fake_run(argv: object, **kwargs: object) -> object:
        calls.append({"argv": argv, **kwargs})
        return types.SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)

    monkeypatch.setattr(runner.subprocess, "run", _fake_run)
    # Keep the executable resolution hermetic: "codebuddy-code" resolves to
    # itself so argv assertions stay stable across machines.
    monkeypatch.setattr(runner.shutil, "which", _identity_which)
    return calls


def _patch_run_raising(
    monkeypatch: pytest.MonkeyPatch,
    error: BaseException,
) -> list[dict[str, object]]:
    """Replace ``subprocess.run`` with a stub that raises *error*."""
    calls: list[dict[str, object]] = []

    def _fake_run(argv: object, **kwargs: object) -> object:
        calls.append({"argv": argv, **kwargs})
        raise error

    monkeypatch.setattr(runner.subprocess, "run", _fake_run)
    monkeypatch.setattr(runner.shutil, "which", _identity_which)
    return calls


def _identity_which(cmd: str) -> str:
    """Hermetic ``shutil.which`` stub: every command resolves to itself."""
    return cmd


def _missing_which(cmd: str) -> str | None:
    """``shutil.which`` stub that reports the command as absent."""
    return None


def _argv(calls: list[dict[str, object]]) -> list[str]:
    """Return the argv list of the first captured subprocess call."""
    argv = calls[0]["argv"]
    assert isinstance(argv, list)
    return cast(list[str], argv)


def _argv_value(argv: list[str], flag: str) -> str:
    """Return the value that immediately follows *flag* in *argv*."""
    return argv[argv.index(flag) + 1]


@pytest.fixture()
def source(tmp_path: Path) -> Path:
    """A small Chinese Markdown source file."""
    path = tmp_path / "in.md"
    path.write_text("# 标题\n\n正文\n", encoding="utf-8")
    return path


def test_cli_builds_expected_command(
    source: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The argv must match the plan's exact shape, and stdin text flows out."""
    calls = _patch_run(monkeypatch, stdout="# Title\n\nBody\n")
    code = cli.main([str(source), "--model", "hy3", "--max-turns", "12", "--timeout", "60"])
    assert code == 0
    argv = _argv(calls)
    assert argv[0] == "codebuddy-code"
    assert argv[1] == "-p"
    prompt = _argv_value(argv, "-p")
    assert str(source) in prompt
    assert "English" in prompt
    assert _argv_value(argv, "--model") == "hy3"
    assert _argv_value(argv, "--output-format") == "text"
    assert _argv_value(argv, "--tools") == "Read"
    assert _argv_value(argv, "--permission-mode") == "bypassPermissions"
    assert _argv_value(argv, "--max-turns") == "12"
    assert "--no-session-persistence" in argv
    assert _argv_value(argv, "--fallback-model") == "glm-5.3-flash"
    assert calls[0]["shell"] is False
    assert calls[0]["encoding"] == "utf-8"
    assert calls[0]["errors"] == "replace"
    assert calls[0]["timeout"] == 60
    assert capsys.readouterr().out == "# Title\n\nBody\n"


def test_cli_fallback_model_default_and_override(
    source: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``--fallback-model`` defaults to the runner constant, override wins."""
    calls = _patch_run(monkeypatch, stdout="# Title\n\nBody\n")
    assert cli.main([str(source)]) == 0
    assert _argv_value(_argv(calls), "--fallback-model") == "glm-5.3-flash"
    calls = _patch_run(monkeypatch, stdout="# Title\n\nBody\n")
    assert cli.main([str(source), "--fallback-model", "hy3-x"]) == 0
    assert _argv_value(_argv(calls), "--fallback-model") == "hy3-x"


def test_cli_strips_outer_code_fence(
    source: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A translation wrapped in one ``` fence pair is unwrapped on stdout."""
    _patch_run(monkeypatch, stdout="```\n# Title\n\nBody\n```\n")
    assert cli.main([str(source)]) == 0
    assert capsys.readouterr().out == "# Title\n\nBody\n"


def test_cli_file_mode_writes_out_and_stdout(
    source: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """File mode prints the translation and writes the same text to OUT."""
    out_path = tmp_path / "out.md"
    _patch_run(monkeypatch, stdout="# Title\n\nBody\n")
    assert cli.main([str(source), str(out_path)]) == 0
    assert out_path.read_text(encoding="utf-8") == "# Title\n\nBody\n"
    assert capsys.readouterr().out == "# Title\n\nBody\n"


def test_cli_stdin_mode_reads_stdin_and_uses_temp_file(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Stdin mode feeds a temp file to the prompt and prints only the result."""
    calls = _patch_run(monkeypatch, stdout="# Title\n")
    monkeypatch.setattr(sys, "stdin", io.StringIO("# 标题\n\n正文\n"))
    assert cli.main([]) == 0
    prompt = _argv_value(_argv(calls), "-p")
    assert "stdin.md" in prompt
    assert capsys.readouterr().out == "# Title\n"


def test_cli_empty_output_fails_and_writes_nothing(
    source: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Whitespace-only output is a failure: exit 1, stderr note, no OUT."""
    out_path = tmp_path / "out.md"
    _patch_run(monkeypatch, stdout="   \n")
    assert cli.main([str(source), str(out_path)]) == 1
    assert not out_path.exists()
    assert "wiki-translate" in capsys.readouterr().err


def test_cli_timeout_fails_without_writing_out(
    source: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``subprocess.TimeoutExpired`` maps to exit 1 and never writes OUT."""
    out_path = tmp_path / "out.md"
    _patch_run_raising(monkeypatch, subprocess.TimeoutExpired(cmd="codebuddy-code", timeout=900))
    assert cli.main([str(source), str(out_path)]) == 1
    err = capsys.readouterr().err
    assert "wiki-translate" in err
    assert "timed out" in err
    assert not out_path.exists()


def test_cli_nonzero_exit_fails(
    source: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A non-zero CLI exit surfaces the code and stderr detail via exit 1."""
    _patch_run(monkeypatch, returncode=2, stderr="model overloaded")
    assert cli.main([str(source)]) == 1
    err = capsys.readouterr().err
    assert "wiki-translate" in err
    assert "exit code 2" in err
    assert "model overloaded" in err


def test_cli_identical_translation_fails(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An output equal to the source is treated as a failure, not success."""
    src = tmp_path / "in.md"
    src.write_text("# Title\n\nBody\n", encoding="utf-8")
    out_path = tmp_path / "out.md"
    _patch_run(monkeypatch, stdout="# Title\n\nBody\n")
    assert cli.main([str(src), str(out_path)]) == 1
    assert not out_path.exists()
    assert "wiki-translate" in capsys.readouterr().err


def test_cli_dry_run_skips_subprocess(
    source: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``--dry-run`` prints the command and prompt without any subprocess."""
    out_path = tmp_path / "out.md"

    def _fail(*args: object, **kwargs: object) -> object:
        raise AssertionError("subprocess.run must not be called in dry-run mode")

    monkeypatch.setattr(runner.subprocess, "run", _fail)
    assert cli.main([str(source), str(out_path), "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert str(source) in out
    assert "--tools" in out
    assert "bypassPermissions" in out
    assert "--no-session-persistence" in out
    assert not out_path.exists()


def test_cli_missing_executable_fails_cleanly(
    source: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unresolvable translator binary maps to exit 1, not a traceback."""
    monkeypatch.setattr(runner.shutil, "which", _missing_which)
    assert cli.main([str(source)]) == 1
    err = capsys.readouterr().err
    assert "wiki-translate" in err
    assert "not found on PATH" in err


def test_clean_output_leaves_plain_text_untouched() -> None:
    """Non-fenced output only loses its surrounding whitespace."""
    assert runner.clean_output("  # Title\n\nBody  ") == "# Title\n\nBody"


def test_clean_output_keeps_leading_code_block() -> None:
    """A translation that legitimately starts with a fence is not unwrapped."""
    text = "```python\nprint('hi')\n```\n\nBody\n"
    assert runner.clean_output(text) == text.strip()


def test_cli_rejects_non_positive_numeric_options(source: Path) -> None:
    """``--max-turns`` / ``--timeout`` must be positive integers."""
    with pytest.raises(SystemExit):
        cli.main([str(source), "--max-turns", "0"])
    with pytest.raises(SystemExit):
        cli.main([str(source), "--timeout", "-5"])


def test_stdin_stdout_pipe_survives_ansi_codepage(tmp_path: Path) -> None:
    """Real pipe round-trip: UTF-8 in, UTF-8 out (review finding B1).

    Spawns the module as an actual child process so the Windows ANSI
    code-page pipe encoding (GBK on this machine) is exercised -- the
    mocked unit tests cannot see that layer.  The stub translator is a
    ``.cmd`` file on Windows, which also pins the ``shutil.which``
    resolution fix; POSIX needs a real executable script instead
    (``shutil.which`` demands the exec bit, and batch files cannot run).
    """
    if sys.platform == "win32":
        stub = tmp_path / "stub.cmd"
        stub.write_text("@echo # Title\r\n", encoding="utf-8")
    else:
        stub = tmp_path / "stub.sh"
        stub.write_text("#!/bin/sh\necho '# Title'\n", encoding="utf-8")
        stub.chmod(0o755)
    proc = subprocess.run(
        [sys.executable, "-m", "tools.translate", "--cmd", str(stub)],
        input="# 中文标题\n\n正文\n".encode("utf-8"),
        capture_output=True,
        cwd=Path(__file__).resolve().parents[1],
        timeout=120,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")
    # Windows text mode emits CRLF; the wiki side reads with universal
    # newlines, so normalise before comparing.
    assert proc.stdout.decode("utf-8").replace("\r\n", "\n") == "# Title\n"
