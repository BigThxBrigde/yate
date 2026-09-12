"""Unit tests for the extension loader (discovery, exclude, de-duplication)."""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, cast

from yate.services.extensions import ExtensionAPI, ExtensionLoader

_SETUP_OK = "def setup(api):\n    pass\n"
_SETUP_BAD = "def setup(api):\n    raise RuntimeError('boom')\n"


class _FakeApp:
    pass


class ExtensionLoaderTests(unittest.TestCase):
    def _loader(self) -> ExtensionLoader:
        return ExtensionLoader(cast(Any, ExtensionAPI(cast(Any, _FakeApp()))))

    def test_load_directory_loads_sorted_py_files(self) -> None:
        with TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / "b.py").write_text(_SETUP_OK, encoding="utf-8")
            (directory / "a.py").write_text(_SETUP_OK, encoding="utf-8")
            (directory / "_hidden.py").write_text(_SETUP_OK, encoding="utf-8")
            (directory / "note.txt").write_text(_SETUP_OK, encoding="utf-8")
            records = self._loader().load_directory(directory)
            self.assertEqual([r.name for r in records], ["a", "b"])
            self.assertTrue(all(r.error is None for r in records))

    def test_load_directory_exclude_skips_stems(self) -> None:
        with TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / "keep.py").write_text(_SETUP_OK, encoding="utf-8")
            (directory / "skip.py").write_text(_SETUP_BAD, encoding="utf-8")
            records = self._loader().load_directory(
                directory, exclude=["skip"]
            )
            self.assertEqual([r.name for r in records], ["keep"])

    def test_missing_directory_is_empty(self) -> None:
        self.assertEqual(self._loader().load_directory(Path("/no/such/dir")), [])

    def test_same_file_loaded_once_across_sources(self) -> None:
        with TemporaryDirectory() as tmp:
            directory = Path(tmp)
            script = directory / "one.py"
            script.write_text(_SETUP_OK, encoding="utf-8")
            loader = self._loader()
            first = loader.load_file(script)
            second = loader.load_file(script.resolve())
            self.assertIs(first, second)
            self.assertEqual(len(loader.loaded), 1)

    def test_setup_error_is_recorded_not_raised(self) -> None:
        with TemporaryDirectory() as tmp:
            script = Path(tmp) / "broken.py"
            script.write_text(_SETUP_BAD, encoding="utf-8")
            record = self._loader().load_file(script)
            self.assertIsNotNone(record.error)
            self.assertIn("RuntimeError", record.error or "")

    def test_missing_setup_function_is_an_error(self) -> None:
        with TemporaryDirectory() as tmp:
            script = Path(tmp) / "nosetup.py"
            script.write_text("x = 1\n", encoding="utf-8")
            record = self._loader().load_file(script)
            self.assertIn("no setup(api)", record.error or "")

    def test_teardown_hook_is_captured_and_called(self) -> None:
        with TemporaryDirectory() as tmp:
            script = Path(tmp) / "res.py"
            script.write_text(
                "calls = []\n"
                "def setup(api):\n"
                "    calls.append('setup')\n"
                "def teardown(api):\n"
                "    calls.append('teardown')\n",
                encoding="utf-8",
            )
            loader = self._loader()
            record = loader.load_file(script)
            self.assertIsNone(record.error)
            self.assertIsNotNone(record.teardown)
            assert record.module is not None
            self.assertEqual(record.module.calls, ["setup"])
            loader.teardown_all()
            self.assertEqual(record.module.calls, ["setup", "teardown"])

    def test_teardown_error_does_not_block_other_extensions(self) -> None:
        with TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / "a_bad.py").write_text(
                "def setup(api):\n"
                "    pass\n"
                "def teardown(api):\n"
                "    raise RuntimeError('cleanup boom')\n",
                encoding="utf-8",
            )
            (directory / "b_good.py").write_text(
                "calls = []\n"
                "def setup(api):\n"
                "    pass\n"
                "def teardown(api):\n"
                "    calls.append('done')\n",
                encoding="utf-8",
            )
            loader = self._loader()
            loader.load_directory(directory)
            loader.teardown_all()  # must not raise
            good = next(r for r in loader.loaded if r.name == "b_good")
            assert good.module is not None
            self.assertEqual(good.module.calls, ["done"])

    def test_teardown_skipped_when_setup_failed(self) -> None:
        with TemporaryDirectory() as tmp:
            script = Path(tmp) / "broken.py"
            script.write_text(
                "def setup(api):\n"
                "    raise RuntimeError('boom')\n"
                "def teardown(api):\n"
                "    raise AssertionError('must not run')\n",
                encoding="utf-8",
            )
            loader = self._loader()
            record = loader.load_file(script)
            self.assertIsNotNone(record.error)
            self.assertIsNone(record.teardown)
            loader.teardown_all()  # must not invoke the skipped hook


if __name__ == "__main__":
    unittest.main()
