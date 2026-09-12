"""Tests for the on-disk resource-location authority (yate.paths)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from yate import paths


class ResourcePathTests(unittest.TestCase):
    def test_package_root_is_the_yate_package(self) -> None:
        root = paths.package_root()
        self.assertTrue(root.is_dir(), root)
        self.assertEqual((root / "paths.py").resolve(), Path(paths.__file__).resolve())

    def test_frozen_package_root_uses_meipass(self) -> None:
        # A PyInstaller process sets sys.frozen and sys._MEIPASS; the bundled
        # data is collected under <_MEIPASS>/yate.
        with TemporaryDirectory() as tmp:
            bundle_root = Path(tmp)
            with mock.patch.object(sys, "frozen", True, create=True), \
                    mock.patch.object(sys, "_MEIPASS", str(bundle_root), create=True):
                self.assertEqual(paths.package_root(), bundle_root / "yate")
            # extensions dir is derived from the frozen root too
            with mock.patch.object(sys, "frozen", True, create=True), \
                    mock.patch.object(sys, "_MEIPASS", str(bundle_root), create=True):
                self.assertEqual(
                    paths.bundled_extensions_dir(),
                    bundle_root / "yate" / "extensions",
                )

    def test_frozen_without_usable_meipass_falls_back(self) -> None:
        normal_root = Path(paths.__file__).resolve().parent
        with mock.patch.object(sys, "frozen", True, create=True), \
                mock.patch.object(sys, "_MEIPASS", 123, create=True):
            self.assertEqual(paths.package_root(), normal_root)

    def test_bundled_extensions_ship_inside_package(self) -> None:
        directory = paths.bundled_extensions_dir()
        self.assertTrue(directory.is_dir(), directory)
        names = {p.name for p in directory.glob("*.py")}
        self.assertIn("__init__.py", names)
        self.assertIn("python_lsp.py", names)
        self.assertIn("csharp_highlight.py", names)
        # the example template must not be auto-loaded as a script
        self.assertTrue((directory / "example_ext.py.example").is_file())
        self.assertNotIn("example_ext.py", names)

    def test_shipped_data_presence_contract(self) -> None:
        # Bilingual guides and the rc template are plain shipped data (no code
        # helper needed); pin their presence so a packaging change cannot
        # silently drop them.
        root = paths.package_root()
        for guide in ("extensions", "lsp", "themes", "yaterc"):
            self.assertTrue((root / "docs" / f"{guide}.zh.md").is_file())
            self.assertTrue((root / "docs" / f"{guide}.en.md").is_file())
        self.assertTrue((root / "yaterc.example").is_file())


if __name__ == "__main__":
    unittest.main()
