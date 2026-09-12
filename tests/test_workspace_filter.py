"""Unit tests for Workspace file filtering.

Covers the explorer filter feature: dotfile visibility (``show_hidden``)
and ``.gitignore`` / ``.yateignore`` pattern handling (root level and
per-directory, negation, directory-only rules).
"""

import tempfile
import unittest
from pathlib import Path

from yate.services.workspace import IGNORED_NAMES, Entry, Workspace


def names(entries: list[Entry]) -> list[str]:
    return [e.name for e in entries]


class EntryTests(unittest.TestCase):
    def test_hidden_flag_is_dot_prefix(self) -> None:
        p = Path("x/.secret")
        self.assertTrue(Entry(p, ".secret", False).hidden)
        self.assertFalse(Entry(Path("x/secret"), "secret", False).hidden)


class ShowHiddenTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        (root / "plain.py").write_text("x\n", encoding="utf-8")
        (root / ".dotfile").write_text("x\n", encoding="utf-8")
        (root / ".config" ).mkdir()
        (root / "sub").mkdir()
        self.ws = Workspace(root)

    def test_dotfiles_hidden_by_default(self) -> None:
        self.assertFalse(self.ws.show_hidden)
        got = names(self.ws.list_dir(self.ws.root))  # type: ignore[arg-type]
        self.assertIn("plain.py", got)
        self.assertIn("sub", got)
        self.assertNotIn(".dotfile", got)
        self.assertNotIn(".config", got)

    def test_show_hidden_reveals_dotfiles(self) -> None:
        self.ws.show_hidden = True
        got = names(self.ws.list_dir(self.ws.root))  # type: ignore[arg-type]
        self.assertIn(".dotfile", got)
        self.assertIn(".config", got)
        self.assertIn("plain.py", got)

    def test_walk_files_respects_show_hidden(self) -> None:
        files = {f.name for f in self.ws.walk_files()}
        self.assertEqual(files, {"plain.py"})
        self.ws.show_hidden = True
        files = {f.name for f in self.ws.walk_files()}
        self.assertIn(".dotfile", files)
        self.assertIn("plain.py", files)

    def test_visible_tree_respects_show_hidden(self) -> None:
        rows = self.ws.visible_tree(set())
        got = {e.name for _, e in rows}
        self.assertNotIn(".dotfile", got)
        self.ws.show_hidden = True
        rows = self.ws.visible_tree(set())
        self.assertIn(".dotfile", {e.name for _, e in rows})


class ParseIgnoreTests(unittest.TestCase):
    def parse(self, text: str) -> list[tuple[str, bool, bool]]:
        pats = Workspace._parse_ignore(text)  # pyright: ignore[reportPrivateUsage]
        return [(p.pattern, p.negated, p.dir_only) for p in pats]

    def test_comments_and_blank_lines_skipped(self) -> None:
        self.assertEqual(self.parse("# comment\n\n   \n*.log\n"), [("*.log", False, False)])

    def test_negation(self) -> None:
        self.assertEqual(self.parse("!keep.txt"), [("keep.txt", True, False)])

    def test_dir_only_marker(self) -> None:
        self.assertEqual(self.parse("build/"), [("build", False, True)])

    def test_patterns_lowercased(self) -> None:
        self.assertEqual(self.parse("*.TMP"), [("*.tmp", False, False)])

    def test_bare_negation_or_slash_ignored(self) -> None:
        self.assertEqual(self.parse("!\n/\n"), [])


class IgnoreRulesTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.ws = Workspace(self.root)

    def names(self, path: Path | None = None) -> list[str]:
        return names(self.ws.list_dir(path if path is not None else self.ws.root))  # type: ignore[arg-type]

    def test_root_gitignore_glob_hides_matching_files(self) -> None:
        (self.root / ".gitignore").write_text("*.log\n", encoding="utf-8")
        (self.root / "a.log").write_text("x\n", encoding="utf-8")
        (self.root / "a.py").write_text("x\n", encoding="utf-8")
        self.ws = Workspace(self.root)  # reload ignores
        got = self.names()
        self.assertNotIn("a.log", got)
        self.assertIn("a.py", got)

    def test_yateignore_is_second_source(self) -> None:
        (self.root / ".yateignore").write_text("secret.txt\n", encoding="utf-8")
        (self.root / "secret.txt").write_text("x\n", encoding="utf-8")
        (self.root / "ok.txt").write_text("x\n", encoding="utf-8")
        self.ws = Workspace(self.root)
        got = self.names()
        self.assertNotIn("secret.txt", got)
        self.assertIn("ok.txt", got)

    def test_negation_reincludes(self) -> None:
        (self.root / ".gitignore").write_text(
            "*.txt\n!keep.txt\n", encoding="utf-8"
        )
        (self.root / "drop.txt").write_text("x\n", encoding="utf-8")
        (self.root / "keep.txt").write_text("x\n", encoding="utf-8")
        self.ws = Workspace(self.root)
        got = self.names()
        self.assertNotIn("drop.txt", got)
        self.assertIn("keep.txt", got)

    def test_last_match_wins(self) -> None:
        (self.root / ".gitignore").write_text(
            "!special.log\n*.log\n", encoding="utf-8"
        )
        (self.root / "special.log").write_text("x\n", encoding="utf-8")
        self.ws = Workspace(self.root)
        self.assertNotIn("special.log", self.names())

    def test_dir_only_rule_spares_files(self) -> None:
        (self.root / ".gitignore").write_text("build/\n", encoding="utf-8")
        (self.root / "build").mkdir()
        (self.root / "build2").write_text("x\n", encoding="utf-8")
        self.ws = Workspace(self.root)
        got = self.names()
        self.assertNotIn("build", got)
        self.assertIn("build2", got)

    def test_matching_is_case_insensitive(self) -> None:
        (self.root / ".gitignore").write_text("*.log\n", encoding="utf-8")
        (self.root / "UPPER.LOG").write_text("x\n", encoding="utf-8")
        self.ws = Workspace(self.root)
        self.assertNotIn("UPPER.LOG", self.names())

    def test_directory_level_rules_apply_only_to_that_dir(self) -> None:
        sub = self.root / "sub"
        sub.mkdir()
        (sub / ".yateignore").write_text("hidden.txt\n", encoding="utf-8")
        (sub / "hidden.txt").write_text("x\n", encoding="utf-8")
        (self.root / "hidden.txt").write_text("x\n", encoding="utf-8")
        self.ws = Workspace(self.root)
        self.assertNotIn("hidden.txt", self.names(sub))
        self.assertIn("hidden.txt", self.names())

    def test_sub_dir_rule_overrides_root_rule(self) -> None:
        sub = self.root / "sub"
        sub.mkdir()
        (self.root / ".gitignore").write_text("*.log\n", encoding="utf-8")
        (sub / ".gitignore").write_text("!special.log\n", encoding="utf-8")
        (sub / "special.log").write_text("x\n", encoding="utf-8")
        (sub / "other.log").write_text("x\n", encoding="utf-8")
        self.ws = Workspace(self.root)
        got = self.names(sub)
        self.assertIn("special.log", got)
        self.assertNotIn("other.log", got)

    def test_ignored_names_always_hidden_even_with_show_hidden(self) -> None:
        (self.root / "__pycache__").mkdir()
        (self.root / "__pycache__" / "x.pyc").write_bytes(b"")
        (self.root / ".git").mkdir()
        self.ws = Workspace(self.root)
        self.ws.show_hidden = True
        got = self.names()
        for banned in IGNORED_NAMES:
            self.assertNotIn(banned, got)

    def test_walk_files_applies_ignore_rules(self) -> None:
        sub = self.root / "sub"
        sub.mkdir()
        (self.root / ".gitignore").write_text("*.tmp\n", encoding="utf-8")
        (self.root / "keep.py").write_text("x\n", encoding="utf-8")
        (sub / "drop.tmp").write_text("x\n", encoding="utf-8")
        (sub / "fine.py").write_text("x\n", encoding="utf-8")
        self.ws = Workspace(self.root)
        got = {p.name for p in self.ws.walk_files()}
        self.assertEqual(got, {"keep.py", "fine.py"})

    def test_set_root_reloads_ignores(self) -> None:
        other = self.root / "other"
        other.mkdir()
        (self.root / ".gitignore").write_text("a.py\n", encoding="utf-8")
        (other / "a.py").write_text("x\n", encoding="utf-8")
        ws = Workspace(self.root)
        self.assertNotIn("a.py", names(ws.list_dir(ws.root)))  # type: ignore[arg-type]
        ws.set_root(other)
        assert ws.root is not None
        self.assertIn("a.py", names(ws.list_dir(ws.root)))

    def test_open_target_loads_ignores(self) -> None:
        (self.root / ".gitignore").write_text("b.log\n", encoding="utf-8")
        (self.root / "b.log").write_text("x\n", encoding="utf-8")
        ws = Workspace()
        self.assertEqual(ws.open_target(self.root / "b.log"), "file")
        assert ws.root is not None
        self.assertNotIn("b.log", names(ws.list_dir(ws.root)))


if __name__ == "__main__":
    unittest.main()
