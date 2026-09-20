# pyright: reportPrivateUsage=false
"""Tests for the runtime trace log (yate.tracing)."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from pathlib import Path

import pytest

from yate import tracing
from yate.config import YateConfig


@pytest.fixture(autouse=True)
def tracing_state(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """No env vars and no attached handler before/after each test."""
    monkeypatch.delenv("YATE_TRACE", raising=False)
    monkeypatch.delenv("YATE_TRACE_LEVEL", raising=False)
    tracing.uninstall()
    yield
    tracing.uninstall()


def _logs_dir() -> Path:
    return Path.home() / ".yate" / "data" / "logs"


def _log_files() -> list[Path]:
    directory = _logs_dir()
    if not directory.is_dir():
        return []
    return sorted(directory.glob("yate-*.log"))


def _log_text() -> str:
    files = _log_files()
    return files[0].read_text(encoding="utf-8") if files else ""


# --- levels ------------------------------------------------------------------


def test_resolve_level_maps_builtin_names() -> None:
    assert tracing.resolve_level("DEBUG") == logging.DEBUG
    assert tracing.resolve_level("info") == logging.INFO
    assert tracing.resolve_level(" Warning ") == logging.WARNING
    assert tracing.resolve_level("error") == logging.ERROR
    assert tracing.resolve_level("CRITICAL") == logging.CRITICAL


def _zero_level(name: str) -> int:
    """Stand-in for ``resolve_level``: resolves everything to NOTSET (0)."""
    return 0


def test_requested_level_keeps_a_falsy_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    """A resolved level of 0 (logging.NOTSET) must not become DEBUG."""
    monkeypatch.setattr(tracing, "resolve_level", _zero_level)
    assert tracing._requested_level(YateConfig(yate_trace=True)) == 0


def test_resolve_level_rejects_unknown_names() -> None:
    assert tracing.resolve_level("VERBOSE") is None
    assert tracing.resolve_level("") is None
    assert tracing.resolve_level("10") is None


def test_get_logger_names_children_without_doubling_prefix() -> None:
    assert tracing.get_logger() is tracing._logger
    assert tracing.get_logger("yate").name == "yate"
    assert tracing.get_logger("editor_lsp").name == "yate.editor_lsp"
    assert (
        tracing.get_logger("yate.editor_lsp.manager").name
        == "yate.editor_lsp.manager"
    )


# --- off by default ----------------------------------------------------------


def test_off_by_default_writes_nothing(isolated_home: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert tracing.install() is False
    assert tracing.is_enabled() is False
    tracing.get_logger("demo").warning("must not appear anywhere")
    out, err = capsys.readouterr()
    assert out == ""
    assert err == ""
    assert not _logs_dir().exists()
    assert tracing.current_log_path() is None


# --- environment switches ----------------------------------------------------


@pytest.mark.parametrize("value", ["1", "true", "YES", "on"])
def test_env_trace_on_values(value: str, isolated_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("YATE_TRACE", value)
    assert tracing.install() is True
    # Nothing is written until the first record: an early-exit command
    # (yate --version) must not leave an empty shell file behind.
    assert _log_files() == []
    tracing.get_logger("demo").info("first record")
    files = _log_files()
    assert len(files) == 1
    assert files[0].parent == _logs_dir()
    content = files[0].read_text(encoding="utf-8")
    assert "trace session ===" in content
    assert "trace level: DEBUG" in content
    assert "pid:" in content
    assert "first record" in content


@pytest.mark.parametrize("value", ["0", "false", "No", "OFF"])
def test_env_trace_off_values(value: str, isolated_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("YATE_TRACE", value)
    assert tracing.install(YateConfig(yate_trace=True)) is False
    assert not tracing.is_enabled()
    assert _log_files() == []


def test_level_filters_records(isolated_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("YATE_TRACE", "1")
    monkeypatch.setenv("YATE_TRACE_LEVEL", "info")
    assert tracing.install() is True
    log = tracing.get_logger("demo")
    log.debug("hidden-detail")
    log.info("visible-detail")
    log.error("kept-anyway")
    content = _log_text()
    assert "visible-detail" in content
    assert "kept-anyway" in content
    assert "hidden-detail" not in content


def test_invalid_env_values_warn_and_fall_back(
    isolated_home: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("YATE_TRACE", "maybe")
    monkeypatch.setenv("YATE_TRACE_LEVEL", "chatty")
    assert tracing.env_trace() is None
    assert tracing.env_level() is None
    # yaterc decides then; with it off nothing is written, but both bad
    # values were reported once on stderr.
    assert tracing.install(YateConfig(yate_trace=False)) is False
    err = capsys.readouterr().err
    assert "YATE_TRACE" in err
    assert "YATE_TRACE_LEVEL" in err


# --- yaterc options and priority ---------------------------------------------


def test_yaterc_enables_tracing(isolated_home: Path) -> None:
    assert tracing.install(YateConfig(yate_trace=True)) is True
    assert _log_files() == []
    tracing.get_logger("demo").warning("something happened")
    assert len(_log_files()) == 1
    assert "trace level: DEBUG" in _log_text()
    assert "something happened" in _log_text()


def test_enabled_but_silent_session_leaves_no_file(isolated_home: Path) -> None:
    """YATE_TRACE=1 on a command that logs nothing writes no log file."""
    assert tracing.install(YateConfig(yate_trace=True)) is True
    assert tracing.is_enabled() is True
    # The directory is reserved eagerly (like crash.py's data/), the file is
    # not: an early-exit command must not accumulate empty shell logs.
    assert _logs_dir().is_dir()
    assert _log_files() == []


def test_yaterc_level_is_used(isolated_home: Path) -> None:
    config = YateConfig(yate_trace=True, yate_trace_level="ERROR")
    assert tracing.install(config) is True
    log = tracing.get_logger("demo")
    log.warning("dropped")
    log.error("kept")
    content = _log_text()
    assert "kept" in content
    assert "dropped" not in content


def test_env_trace_beats_yaterc(isolated_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("YATE_TRACE", "1")
    assert tracing.install(YateConfig(yate_trace=False)) is True


def test_env_level_beats_yaterc(isolated_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("YATE_TRACE_LEVEL", "error")
    tracing.install(YateConfig(yate_trace=True, yate_trace_level="DEBUG"))
    log = tracing.get_logger("demo")
    log.warning("dropped")
    log.error("kept")
    content = _log_text()
    assert "kept" in content
    assert "dropped" not in content


# --- two-phase install (cli startup) -----------------------------------------


def test_second_install_keeps_file_and_adjusts_level(
    isolated_home: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("YATE_TRACE", "1")
    tracing.install()                    # pass 1: env only, DEBUG
    path = tracing.current_log_path()
    assert path is not None
    tracing.install(YateConfig(yate_trace=True, yate_trace_level="WARNING"))
    assert tracing.current_log_path() == path
    assert len(tracing._file_handlers()) == 1
    log = tracing.get_logger("demo")
    log.info("dropped")
    log.warning("kept")
    content = path.read_text(encoding="utf-8")
    assert "kept" in content
    assert "dropped" not in content


def test_install_is_idempotent(isolated_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("YATE_TRACE", "on")
    assert tracing.install() is True
    first = tracing.current_log_path()
    assert tracing.install() is True
    assert tracing.install() is True
    assert tracing.current_log_path() == first
    assert len(tracing._file_handlers()) == 1
    tracing.get_logger("demo").info("once")
    assert len(_log_files()) == 1
    assert _log_text().count("trace session ===") == 1


def test_install_off_detaches_handlers(isolated_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("YATE_TRACE", "1")
    tracing.install()
    monkeypatch.setenv("YATE_TRACE", "0")
    assert tracing.install() is False
    assert tracing.is_enabled() is False


# --- degraded environment ----------------------------------------------------


def test_unwritable_logs_dir_only_warns(
    isolated_home: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def denied() -> Path:
        raise OSError("denied")

    monkeypatch.setattr(tracing, "logs_dir", denied)
    monkeypatch.setenv("YATE_TRACE", "1")
    assert tracing.install() is False
    assert not tracing.is_enabled()
    assert "trace log unavailable" in capsys.readouterr().err


# --- uninstall (Windows data/ cleanup) ---------------------------------------


def test_uninstall_releases_the_file(isolated_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("YATE_TRACE", "1")
    tracing.install()
    tracing.get_logger("demo").info("written")
    path = tracing.current_log_path()
    assert path is not None and path.is_file()
    tracing.uninstall()
    assert tracing.is_enabled() is False
    assert tracing.current_log_path() is None
    # Only possible on Windows when the handle was really released.
    path.unlink()
    assert not path.exists()
    tracing.uninstall()  # idempotent
