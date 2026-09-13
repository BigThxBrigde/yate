# pyright: reportPrivateUsage=false
"""Tests for best-effort crash diagnostics (yate.crash)."""

from __future__ import annotations

import faulthandler
import io
import sys
import unittest
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

import yate
from yate import crash


class CrashDataDirTests(unittest.TestCase):
    def test_crash_data_dir_creates_home_yate_data(self) -> None:
        with TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            with mock.patch.object(Path, "home", return_value=home):
                directory = crash.crash_data_dir()
            self.assertEqual(directory, home / ".yate" / "data")
            self.assertTrue(directory.is_dir())


class ErrFilePathTests(unittest.TestCase):
    def test_name_is_timestamped_err_under_dir(self) -> None:
        with TemporaryDirectory() as tmp:
            directory = Path(tmp)
            path = crash._err_file_path(
                directory, datetime(2026, 9, 13, 10, 15, 30)
            )
            self.assertEqual(path.parent, directory)
        self.assertEqual(path.name, "crash-20260913-101530.err")

    def test_defaults_to_current_time(self) -> None:
        with TemporaryDirectory() as tmp:
            path = crash._err_file_path(Path(tmp))
        self.assertRegex(path.name, r"^crash-\d{8}-\d{6}\.err$")


class InstallTests(unittest.TestCase):
    """Each test gets an isolated HOME and a full global-state restore."""

    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.home = Path(self._tmp.name) / "home"
        self.home.mkdir()
        self._home_patch = mock.patch.object(Path, "home", return_value=self.home)
        self._home_patch.start()
        self.addCleanup(self._home_patch.stop)

        self._saved_hook = sys.excepthook
        self._saved_original = crash._original_excepthook
        self._faulthandler_was_enabled = faulthandler.is_enabled()
        self._reset_module()
        self.addCleanup(self._restore)

    @staticmethod
    def _reset_module() -> None:
        crash._err_file = None
        crash._err_path = None
        crash._crashed = False

    def _restore(self) -> None:
        handle = crash._err_file
        if handle is not None:
            try:
                handle.close()
            except OSError:
                pass
        self._reset_module()
        crash._original_excepthook = self._saved_original
        sys.excepthook = self._saved_hook
        # Re-point faulthandler away from any (possibly closed) temp fd.
        faulthandler.disable()
        if self._faulthandler_was_enabled:
            faulthandler.enable()

    def _data_dir(self) -> Path:
        return self.home / ".yate" / "data"

    def _report_files(self) -> list[Path]:
        return sorted(self._data_dir().glob("crash-*.err"))

    def test_install_creates_report_with_header_and_enables_faulthandler(
        self,
    ) -> None:
        crash.install()
        self.assertTrue(faulthandler.is_enabled())
        files = self._report_files()
        self.assertEqual(len(files), 1)
        content = files[0].read_text(encoding="utf-8")
        self.assertIn(f"yate {yate.__version__} crash report", content)
        self.assertIn("cwd:", content)
        self.assertIn("argv:", content)
        self.assertIn(f"python: {sys.version.split()[0]} on {sys.platform}", content)

    def test_install_is_idempotent(self) -> None:
        crash.install()
        first_hook = sys.excepthook
        crash.install()
        crash.install()
        self.assertEqual(len(self._report_files()), 1)
        self.assertIs(sys.excepthook, first_hook)

    def test_uninstall_releases_handle_and_deletes_healthy_report(self) -> None:
        crash.install()
        report = crash.current_crash_file()
        self.assertIsNotNone(report)
        assert report is not None  # narrow for pyright
        self.assertTrue(report.is_file())

        crash.uninstall()
        # The Windows --include-data cleanup relies on the handle being
        # released and the healthy report disappearing from data/.
        self.assertFalse(report.exists())
        self.assertIsNone(crash.current_crash_file())
        self.assertFalse(faulthandler.is_enabled())
        # Idempotent: atexit calls it again on interpreter shutdown.
        crash.uninstall()

    def test_excepthook_appends_traceback_and_delegates_to_original(self) -> None:
        sentinel = mock.Mock()
        crash._original_excepthook = sentinel
        crash.install()

        err = RuntimeError("boom")
        sys.excepthook(RuntimeError, err, None)

        sentinel.assert_called_once_with(RuntimeError, err, None)
        content = self._report_files()[0].read_text(encoding="utf-8")
        self.assertIn("=== uncaught Python exception ===", content)
        self.assertIn("RuntimeError: boom", content)

    def test_clean_exit_removes_header_only_report(self) -> None:
        crash.install()
        self.assertEqual(len(self._report_files()), 1)
        crash._cleanup_on_exit()
        self.assertEqual(self._report_files(), [])
        self.assertIsNone(crash._err_file)

    def test_report_is_kept_after_uncaught_exception(self) -> None:
        crash._original_excepthook = mock.Mock()
        crash.install()
        sys.excepthook(ValueError, ValueError("kept"), None)
        crash._cleanup_on_exit()
        files = self._report_files()
        self.assertEqual(len(files), 1)
        self.assertIn("ValueError: kept", files[0].read_text(encoding="utf-8"))

    def test_unwritable_data_dir_falls_back_to_stderr_without_raising(
        self,
    ) -> None:
        stderr_path = Path(self._tmp.name) / "stderr.txt"
        fake_stderr = open(stderr_path, "w", encoding="utf-8")
        self.addCleanup(fake_stderr.close)
        with (
            mock.patch.object(
                crash, "crash_data_dir", side_effect=OSError("denied")
            ),
            mock.patch.object(sys, "stderr", fake_stderr),
        ):
            crash.install()  # must not raise
        try:
            self.assertTrue(faulthandler.is_enabled())
            self.assertEqual(self._report_files(), [])
            self.assertIs(sys.excepthook, self._saved_hook)
            self.assertIsNone(crash._err_file)
        finally:
            faulthandler.disable()
            if self._faulthandler_was_enabled:
                faulthandler.enable()

    def test_install_keeps_working_when_stderr_lacks_a_fileno(self) -> None:
        # faulthandler.enable() raises ValueError on a non-fd stream; even
        # then install() must swallow it and leave the editor launchable.
        with (
            mock.patch.object(
                crash, "crash_data_dir", side_effect=OSError("denied")
            ),
            mock.patch.object(sys, "stderr", io.StringIO()),
        ):
            crash.install()  # must not raise
        self.assertIsNone(crash._err_file)


if __name__ == "__main__":
    unittest.main()
