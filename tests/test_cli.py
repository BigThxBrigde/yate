"""Headless tests for the command line entry point (yate.cli).

These cover argument parsing only — launching the TUI needs a real terminal.
The dest names asserted here are the exact attributes ``main()`` reads, so a
rename that desynchronizes argparse from ``main`` (which previously crashed
every launch with ``AttributeError: 'Namespace' ... ext_dirs``) fails here.
"""

from __future__ import annotations

import unittest

from yate.cli import build_parser


class CliParserTests(unittest.TestCase):
    def test_extension_dests_default_to_empty_lists(self) -> None:
        args = build_parser().parse_args([])
        self.assertEqual(args.ext_files, [])
        self.assertEqual(args.ext_dirs, [])

    def test_ext_flags_are_repeatable_into_expected_dests(self) -> None:
        args = build_parser().parse_args(
            ["--ext", "a.py", "--ext", "b.py", "--ext-dir", "exts", "--ext-dir", "more"]
        )
        self.assertEqual(args.ext_files, ["a.py", "b.py"])
        self.assertEqual(args.ext_dirs, ["exts", "more"])

    def test_keymap_flag_and_alias(self) -> None:
        self.assertEqual(build_parser().parse_args(["--keymap", "vim"]).keymap, "vim")
        # "normal" is the documented vsc alias and must parse without error.
        self.assertEqual(build_parser().parse_args(["--keymap", "normal"]).keymap, "normal")

    def test_yaterc_none_and_path(self) -> None:
        self.assertEqual(build_parser().parse_args(["-u", "NONE"]).yaterc, "NONE")
        self.assertEqual(build_parser().parse_args(["-u", "rc.py"]).yaterc, "rc.py")

    def test_positional_path(self) -> None:
        self.assertEqual(build_parser().parse_args(["some/file.txt"]).path, "some/file.txt")
        self.assertIsNone(build_parser().parse_args([]).path)


if __name__ == "__main__":
    unittest.main()
