"""Tests for the on-disk resource-location authority (yate.paths)."""

from __future__ import annotations

import unittest
from pathlib import Path

from yate import paths


class ResourcePathTests(unittest.TestCase):
    def test_package_root_is_the_yate_package(self) -> None:
        root = paths.package_root()
        self.assertTrue(root.is_dir(), root)
        self.assertEqual((root / "paths.py").resolve(), Path(paths.__file__).resolve())

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

    def test_bundled_docs_are_bilingual(self) -> None:
        directory = paths.bundled_docs_dir()
        stems = {p.name for p in directory.glob("*.md")}
        for guide in ("extensions", "lsp", "themes", "yaterc"):
            self.assertIn(f"{guide}.zh.md", stems)
            self.assertIn(f"{guide}.en.md", stems)

    def test_example_rc_ships_inside_package(self) -> None:
        example = paths.example_rc_path()
        self.assertTrue(example.is_file(), example)
        self.assertEqual(example.name, "yaterc.example")

    def test_bundled_doc_helper(self) -> None:
        self.assertEqual(
            paths.bundled_doc("lsp.en.md"),
            paths.bundled_docs_dir() / "lsp.en.md",
        )


if __name__ == "__main__":
    unittest.main()
