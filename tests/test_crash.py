# pyright: reportPrivateUsage=false
"""Tests for best-effort crash diagnostics (yate.logs.crash).

State lives on the ``CrashService`` singleton and its public properties are
read-only, so a fixture resets the backing attributes directly (hence the
private-usage pragma above) -- the same way it restores ``sys.excepthook``.
"""

from __future__ import annotations

import atexit
import faulthandler
import io
import os
import re
import sys
from collections.abc import Callable, Iterator
from datetime import datetime
from pathlib import Path
from unittest import mock

import pytest

import yate
from yate import logs
from yate.logs import crash


# --- data dir ---------------------------------------------------------------


def test_crash_data_dir_creates_home_yate_data(isolated_home: Path) -> None:
    directory = logs.crash_data_dir()
    assert directory == isolated_home / ".yate" / "data"
    assert directory.is_dir()


# --- err file naming --------------------------------------------------------


def test_name_is_timestamped_err_under_dir(tmp_path: Path) -> None:
    path = crash.build_err_path(tmp_path, datetime(2026, 9, 13, 10, 15, 30))
    assert path.parent == tmp_path
    assert path.name == f"crash-20260913-101530-{os.getpid()}.err"


def test_defaults_to_current_time(tmp_path: Path) -> None:
    path = crash.build_err_path(tmp_path)
    assert re.match(r"^crash-\d{8}-\d{6}-\d+\.err$", path.name)


def test_same_second_processes_get_distinct_report_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """S36: two processes crashing in the same second must not share a name.

    Both reports are opened in ``"w"`` mode, so a shared name would let the
    later header truncate the earlier process's report.  The second process
    is simulated by patching the pid.
    """
    fixed = datetime(2026, 9, 13, 10, 15, 30)
    monkeypatch.setattr(os, "getpid", lambda: 111)
    first = crash.build_err_path(tmp_path, fixed)
    monkeypatch.setattr(os, "getpid", lambda: 222)
    second = crash.build_err_path(tmp_path, fixed)
    assert first != second
    assert first.name == "crash-20260913-101530-111.err"
    assert second.name == "crash-20260913-101530-222.err"


# --- install / uninstall lifecycle -----------------------------------------


def _reset_crash_state() -> None:
    # Fresh state per test: the properties read these backing attributes, and
    # the hook to chain to is saved/restored separately.
    crash._err_file = None
    crash._err_path = None
    crash._crashed = False
    crash._installed_excepthook = None


@pytest.fixture
def crash_state(isolated_home: Path) -> Iterator[Path]:
    """Fresh crash service state per test; full global-state restore.

    Home is already redirected by the autouse ``isolated_home`` fixture;
    the yielded path is the isolated home.
    """
    saved_hook = sys.excepthook
    saved_original = crash.original_excepthook
    faulthandler_was_enabled = faulthandler.is_enabled()
    _reset_crash_state()
    yield isolated_home
    handle = crash.err_file
    if handle is not None:
        try:
            handle.close()
        except OSError:
            pass
    _reset_crash_state()
    crash._original_excepthook = saved_original
    sys.excepthook = saved_hook
    # Re-point faulthandler away from any (possibly closed) temp fd.
    faulthandler.disable()
    if faulthandler_was_enabled:
        faulthandler.enable()


def _report_files(home: Path) -> list[Path]:
    return sorted((home / ".yate" / "data").glob("crash-*.err"))


def test_install_creates_report_with_header_and_enables_faulthandler(
    crash_state: Path,
) -> None:
    crash.install()
    assert faulthandler.is_enabled()
    files = _report_files(crash_state)
    assert len(files) == 1
    content = files[0].read_text(encoding="utf-8")
    assert f"yate {yate.__version__} crash report" in content
    assert "cwd:" in content
    assert "argv:" in content
    assert f"python: {sys.version.split()[0]} on {sys.platform}" in content


def test_install_is_idempotent(crash_state: Path) -> None:
    crash.install()
    first_hook = sys.excepthook
    crash.install()
    crash.install()
    assert len(_report_files(crash_state)) == 1
    assert sys.excepthook is first_hook


def test_uninstall_releases_handle_and_deletes_healthy_report(
    crash_state: Path,
) -> None:
    crash.install()
    report = crash.current_crash_file()
    assert report is not None
    assert report.is_file()

    crash.uninstall()
    # The Windows --include-data cleanup relies on the handle being
    # released and the healthy report disappearing from data/.
    assert not report.exists()
    assert crash.current_crash_file() is None
    assert not faulthandler.is_enabled()
    # The interpreter gets its own hook back: an uninstalled service must
    # not stay reachable from sys.excepthook, where it would keep flipping
    # _crashed with no report open.
    assert sys.excepthook is crash.original_excepthook
    # Idempotent: atexit calls it again on interpreter shutdown.
    crash.uninstall()
    assert sys.excepthook is crash.original_excepthook


def test_install_chains_to_and_restores_a_hook_installed_after_import(
    crash_state: Path,
) -> None:
    """S5: the chained hook is captured at install() time, not import time.

    A hook the host installed between ``import yate`` and ``install()`` is
    the one delegated to on uncaught exceptions -- and the one
    ``uninstall()`` puts back, instead of some import-time snapshot.
    """
    fake = mock.Mock()
    sys.excepthook = fake
    crash.install()
    assert crash.original_excepthook is fake

    err = RuntimeError("boom")
    sys.excepthook(RuntimeError, err, None)
    fake.assert_called_once_with(RuntimeError, err, None)

    crash.uninstall()
    assert sys.excepthook is fake


def test_install_uninstall_cycles_keep_one_atexit_callback(
    crash_state: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # atexit runs *every* registered entry, so install() must drop a stale
    # registration and uninstall() its live one; the stand-in unregister
    # mirrors the stdlib semantics ("drop all entries equal to func").
    registered: list[Callable[[], None]] = []

    def _unregister(func: Callable[[], None]) -> None:
        registered[:] = [item for item in registered if item != func]

    monkeypatch.setattr(atexit, "register", registered.append)
    monkeypatch.setattr(atexit, "unregister", _unregister)

    for _ in range(3):
        crash.install()
        assert registered == [crash.cleanup_on_exit]
        crash.uninstall()
        assert registered == []


def test_excepthook_appends_traceback_and_delegates_to_original(
    crash_state: Path,
) -> None:
    sentinel = mock.Mock()
    crash._original_excepthook = sentinel
    crash.install()

    err = RuntimeError("boom")
    sys.excepthook(RuntimeError, err, None)

    sentinel.assert_called_once_with(RuntimeError, err, None)
    content = _report_files(crash_state)[0].read_text(encoding="utf-8")
    assert "=== uncaught Python exception ===" in content
    assert "RuntimeError: boom" in content


def test_clean_exit_removes_header_only_report(crash_state: Path) -> None:
    crash.install()
    assert len(_report_files(crash_state)) == 1
    crash.cleanup_on_exit()
    assert _report_files(crash_state) == []
    assert crash.err_file is None


def test_report_is_kept_after_uncaught_exception(crash_state: Path) -> None:
    crash._original_excepthook = mock.Mock()
    crash.install()
    sys.excepthook(ValueError, ValueError("kept"), None)
    crash.cleanup_on_exit()
    files = _report_files(crash_state)
    assert len(files) == 1
    assert "ValueError: kept" in files[0].read_text(encoding="utf-8")


# --- degraded environments --------------------------------------------------


def _denied_data_dir() -> Path:
    raise OSError("denied")


def test_unwritable_data_dir_falls_back_to_stderr_without_raising(
    crash_state: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    stderr_path = tmp_path / "stderr.txt"
    with open(stderr_path, "w", encoding="utf-8") as fake_stderr:
        # install() resolves the helper from the module globals of yate.logs,
        # so the module function is patched here, not the service object.
        monkeypatch.setattr(logs, "crash_data_dir", _denied_data_dir)
        monkeypatch.setattr(sys, "stderr", fake_stderr)
        hook_before = sys.excepthook
        crash.install()  # must not raise
    assert faulthandler.is_enabled()
    assert _report_files(crash_state) == []
    assert sys.excepthook is hook_before  # original hook kept
    assert crash.err_file is None


def test_install_keeps_working_when_stderr_lacks_a_fileno(
    crash_state: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # faulthandler.enable() raises ValueError on a non-fd stream; even
    # then install() must swallow it and leave the editor launchable.
    monkeypatch.setattr(logs, "crash_data_dir", _denied_data_dir)
    monkeypatch.setattr(sys, "stderr", io.StringIO())
    crash.install()  # must not raise
    assert crash.err_file is None
