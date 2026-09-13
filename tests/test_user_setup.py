# pyright: reportPrivateUsage=false
"""Tests for one-time user-directory setup/cleanup (yate.services.user_setup).

Every test runs against a ``tmp_path`` base directory -- the service takes an
explicit ``base_dir`` precisely so the real ``Path.home()`` and the crash
handler's ``~/.yate/data`` are never touched. Template sources are the real
shipped package resources.
"""

from __future__ import annotations

import io
import unittest
from pathlib import Path

from yate.paths import package_root
from yate.services import user_setup as us

TEMPLATE_RELS = [
    "themes/dracula_theme.example",
    "themes/ayu_theme.example",
    "extensions/example_ext.py.example",
    "extensions/yatesh_syntax.py.example",
]


class _FakeTTY(io.StringIO):
    """StringIO that reports itself as an interactive terminal."""

    def isatty(self) -> bool:  # noqa: D401 - test double
        return True


class SetupDefaultsTests(unittest.TestCase):
    def test_creates_layout_from_scratch_with_real_resources(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / ".yate"
            report = us.setup_defaults(base_dir=base)

            self.assertEqual(report.errors, [])
            self.assertEqual(sorted(report.created_dirs),
                             ["extensions", "themes"])
            self.assertTrue(report.installed_rc)
            self.assertFalse(report.rc_skipped)
            self.assertEqual(sorted(report.refreshed_templates),
                             sorted(TEMPLATE_RELS))
            self.assertEqual(report.skipped_templates, [])

            bundled_rc = (package_root() / us.RC_TEMPLATE).read_bytes()
            self.assertEqual((base / "yaterc").read_bytes(), bundled_rc)
            for rel in TEMPLATE_RELS:
                self.assertTrue((base / rel).is_file(), rel)
            # Templates stay *.example: no real built-in extension is copied
            # and no *.py lands in either scanned directory.
            self.assertFalse((base / "extensions" / "python_lsp.py").exists())
            self.assertFalse((base / "extensions" / "csharp_highlight.py").exists())
            self.assertEqual(list((base / "themes").glob("*.py")), [])
            # data/ is runtime state, never created by setup.
            self.assertFalse((base / "data").exists())

    def test_is_idempotent_and_refreshes_tampered_templates(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / ".yate"
            first = us.setup_defaults(base_dir=base)
            self.assertEqual(first.errors, [])

            tampered = base / "themes" / "dracula_theme.example"
            tampered.write_text("# TAMPERED\n", encoding="utf-8")
            second = us.setup_defaults(base_dir=base)

            self.assertEqual(second.errors, [])
            self.assertEqual(second.created_dirs, [])
            self.assertTrue(second.rc_skipped)
            self.assertFalse(second.installed_rc)
            self.assertIn("themes/dracula_theme.example",
                          second.refreshed_templates)
            # Managed templates are restored to the shipped content; the user
            # yaterc is left untouched.
            source = (
                package_root()
                / "resources" / "theme_examples" / "dracula_theme.example"
            )
            self.assertEqual(tampered.read_text(encoding="utf-8"),
                             source.read_text(encoding="utf-8"))

    def test_force_replaces_rc_keeps_earliest_backup(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / ".yate"
            us.setup_defaults(base_dir=base)
            rc = base / "yaterc"
            rc.write_text("# FIRST CUSTOM\n", encoding="utf-8")

            forced = us.setup_defaults(base_dir=base, force=True)
            self.assertTrue(forced.installed_rc)
            backup = base / us.RC_BACKUP
            self.assertEqual(forced.rc_backup, backup)
            self.assertEqual(backup.read_text(encoding="utf-8"),
                             "# FIRST CUSTOM\n")
            bundled = (package_root() / us.RC_TEMPLATE).read_text(encoding="utf-8")
            self.assertEqual(rc.read_text(encoding="utf-8"), bundled)

            # A second force must not overwrite the existing backup: the
            # earliest user version always survives.
            rc.write_text("# SECOND CUSTOM\n", encoding="utf-8")
            us.setup_defaults(base_dir=base, force=True)
            self.assertEqual(backup.read_text(encoding="utf-8"),
                             "# FIRST CUSTOM\n")

    def test_missing_template_source_is_skipped_not_fatal(self) -> None:
        import tempfile
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / ".yate"
            fake_pairs = [(package_root() / "no-such-theme.example",
                           "themes/no-such-theme.example")]
            with patch.object(us, "_template_sources", return_value=fake_pairs):
                report = us.setup_defaults(base_dir=base)
            self.assertEqual(report.errors, [])
            self.assertEqual(report.skipped_templates,
                             ["themes/no-such-theme.example"])
            self.assertEqual(report.refreshed_templates, [])
            self.assertTrue((base / "yaterc").is_file())

    def test_oserror_collected_when_theme_dir_blocked_by_file(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / ".yate"
            base.mkdir(parents=True)
            # A regular file occupying the themes/ path makes every theme
            # template copy fail; setup must keep going and report instead.
            (base / "themes").write_text("blocker", encoding="utf-8")

            report = us.setup_defaults(base_dir=base)

            self.assertTrue(report.errors)
            self.assertTrue(any("themes" in e for e in report.errors))
            self.assertTrue((base / "yaterc").is_file())
            self.assertTrue(
                (base / "extensions" / "example_ext.py.example").is_file()
            )


class CleanupDefaultsTests(unittest.TestCase):
    def _populate(self, base: Path) -> None:
        (base / "themes").mkdir(parents=True)
        (base / "extensions").mkdir(parents=True)
        (base / "data").mkdir(parents=True)
        (base / "yaterc").write_text("theme = 'mocha'\n", encoding="utf-8")
        (base / "themes" / "dracula_theme.example").write_text(
            "example", encoding="utf-8")
        (base / "themes" / "dracula.py").write_text(
            "register_theme(Theme())", encoding="utf-8")
        (base / "extensions" / "example_ext.py.example").write_text(
            "example", encoding="utf-8")
        (base / "data" / "crash-x.err").write_text("crash", encoding="utf-8")

    def test_default_removes_config_keeps_data(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / ".yate"
            self._populate(base)
            report = us.cleanup_defaults(force=True, base_dir=base)

            self.assertEqual(report.errors, [])
            self.assertFalse((base / "yaterc").exists())
            self.assertFalse((base / "themes").exists())
            self.assertFalse((base / "extensions").exists())
            self.assertTrue((base / "data" / "crash-x.err").is_file())
            self.assertEqual(report.removed_files, ["yaterc"])
            self.assertEqual(sorted(report.removed_dirs),
                             ["extensions", "themes"])
            self.assertEqual(report.preserved, ["data"])
            self.assertFalse(report.base_removed)

    def test_include_data_empties_and_removes_base_dir(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / ".yate"
            self._populate(base)
            report = us.cleanup_defaults(
                force=True, include_data=True, base_dir=base
            )
            self.assertEqual(report.errors, [])
            self.assertFalse(base.exists())
            self.assertTrue(report.base_removed)
            self.assertEqual(sorted(report.removed_dirs),
                             ["data", "extensions", "themes"])
            self.assertEqual(report.preserved, [])

    def test_unknown_entries_preserved_keep_base_dir(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / ".yate"
            self._populate(base)
            (base / "notes.txt").write_text("mine", encoding="utf-8")

            report = us.cleanup_defaults(force=True, base_dir=base)

            self.assertEqual((base / "notes.txt").read_text(encoding="utf-8"),
                             "mine")
            self.assertIn("notes.txt", report.preserved)
            self.assertFalse(report.base_removed)

    def test_interactive_yes_executes_no_cancels(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / ".yate"
            self._populate(base)
            out = _FakeTTY("")
            agreed = us.cleanup_defaults(
                base_dir=base, stdin=_FakeTTY("y\n"), stdout=out
            )
            self.assertFalse(agreed.cancelled)
            self.assertFalse((base / "yaterc").exists())
            self.assertTrue((base / "data").is_dir())

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / ".yate"
            self._populate(base)
            # Any non-yes answer (including an empty line) cancels and
            # deletes nothing; state is unchanged between attempts.
            for answer in ("n\n", "\n", "q\n"):
                denied = us.cleanup_defaults(
                    base_dir=base, stdin=_FakeTTY(answer),
                    stdout=_FakeTTY(""),
                )
                self.assertTrue(denied.cancelled, answer)
                self.assertTrue((base / "yaterc").is_file())
                self.assertTrue((base / "themes" / "dracula.py").is_file())
                self.assertEqual(denied.removed_files, [])
                self.assertIn("data", denied.preserved)

    def test_non_interactive_stdin_without_force_is_refused(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / ".yate"
            self._populate(base)
            with self.assertRaises(us.ConfirmationRequiredError):
                us.cleanup_defaults(
                    base_dir=base, stdin=io.StringIO("y\n"),
                    stdout=io.StringIO(),
                )
            # Refusal deletes nothing.
            self.assertTrue((base / "yaterc").is_file())
            self.assertTrue((base / "themes" / "dracula.py").is_file())

    def test_missing_base_dir_is_an_empty_success(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / ".yate"
            report = us.cleanup_defaults(force=True, base_dir=base)
            self.assertEqual(report.errors, [])
            self.assertFalse(report.cancelled)
            self.assertFalse(report.base_removed)
            self.assertEqual(report.removed_files, [])
            self.assertEqual(report.removed_dirs, [])
            self.assertFalse(base.exists())

    def test_only_unknown_entries_is_nothing_to_remove(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / ".yate"
            base.mkdir(parents=True)
            (base / "notes.txt").write_text("mine", encoding="utf-8")
            # Must not prompt even without force: nothing destructive planned.
            report = us.cleanup_defaults(
                base_dir=base, stdin=io.StringIO(), stdout=io.StringIO()
            )
            self.assertTrue(report.nothing_to_remove)
            self.assertEqual(report.preserved, ["notes.txt"])
            self.assertTrue((base / "notes.txt").is_file())


if __name__ == "__main__":
    unittest.main()
