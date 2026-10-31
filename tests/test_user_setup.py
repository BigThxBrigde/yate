# pyright: reportPrivateUsage=false
"""Tests for one-time user-directory setup/cleanup (yate.services.user_setup).

Every test runs against a ``tmp_path`` base directory -- the service takes an
explicit ``base_dir`` precisely so the real ``Path.home()`` and the crash
handler's ``~/.yate/data`` are never touched. Template sources are the real
shipped package resources.
"""

from __future__ import annotations

import io
from collections.abc import Iterator
from pathlib import Path
from typing import TextIO, cast, override

import pytest

from yate.paths import package_root
from yate.services import user_setup as us

TEMPLATE_RELS: list[str] = [
    "themes/dracula_theme.example",
    "themes/ayu_theme.example",
    "extensions/example_ext.py.example",
    "extensions/yatesh_syntax.py.example",
    "extensions/batch_syntax.py.example",
    "extensions/diff_syntax.py.example",
    "extensions/fsharp_syntax.py.example",
    "extensions/git_syntax.py.example",
    "extensions/ini_syntax.py.example",
    "extensions/lua.example",
]


class _FakeTTY(io.StringIO):
    """StringIO that reports itself as an interactive terminal."""

    @override
    def isatty(self) -> bool:  # noqa: D401 - test double
        """Report an interactive terminal."""
        return True


def _populate(base: Path) -> None:
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


# --- setup_defaults ---------------------------------------------------------


def test_creates_layout_from_scratch_with_real_resources(tmp_path: Path) -> None:
    base = tmp_path / ".yate"
    report = us.setup_defaults(base_dir=base)

    assert report.errors == []
    assert sorted(report.created_dirs) == ["extensions", "themes"]
    assert report.installed_rc
    assert not report.rc_skipped
    assert sorted(report.refreshed_templates) == sorted(TEMPLATE_RELS)
    assert report.skipped_templates == []

    bundled_rc = (package_root() / us.RC_TEMPLATE).read_bytes()
    assert (base / "yaterc").read_bytes() == bundled_rc
    for rel in TEMPLATE_RELS:
        assert (base / rel).is_file(), rel
    # Templates stay *.example: no real built-in extension is copied
    # and no *.py lands in either scanned directory.
    assert not (base / "extensions" / "python_lsp.py").exists()
    assert not (base / "extensions" / "csharp_highlight.py").exists()
    assert list((base / "themes").glob("*.py")) == []
    # data/ is runtime state, never created by setup.
    assert not (base / "data").exists()


def test_is_idempotent_and_refreshes_tampered_templates(tmp_path: Path) -> None:
    base = tmp_path / ".yate"
    first = us.setup_defaults(base_dir=base)
    assert first.errors == []

    tampered = base / "themes" / "dracula_theme.example"
    tampered.write_text("# TAMPERED\n", encoding="utf-8")
    second = us.setup_defaults(base_dir=base)

    assert second.errors == []
    assert second.created_dirs == []
    assert second.rc_skipped
    assert not second.installed_rc
    assert "themes/dracula_theme.example" in second.refreshed_templates
    # Managed templates are restored to the shipped content; the user
    # yaterc is left untouched.
    source = (
        package_root()
        / "resources" / "theme_examples" / "dracula_theme.example"
    )
    assert tampered.read_text(encoding="utf-8") == source.read_text(
        encoding="utf-8")


def test_force_replaces_rc_keeps_earliest_backup(tmp_path: Path) -> None:
    base = tmp_path / ".yate"
    us.setup_defaults(base_dir=base)
    rc = base / "yaterc"
    rc.write_text("# FIRST CUSTOM\n", encoding="utf-8")

    forced = us.setup_defaults(base_dir=base, force=True)
    assert forced.installed_rc
    backup = base / us.RC_BACKUP
    assert forced.rc_backup == backup
    assert backup.read_text(encoding="utf-8") == "# FIRST CUSTOM\n"
    bundled = (package_root() / us.RC_TEMPLATE).read_text(encoding="utf-8")
    assert rc.read_text(encoding="utf-8") == bundled

    # A second force must not overwrite the existing backup: the
    # earliest user version always survives.
    rc.write_text("# SECOND CUSTOM\n", encoding="utf-8")
    us.setup_defaults(base_dir=base, force=True)
    assert backup.read_text(encoding="utf-8") == "# FIRST CUSTOM\n"


def test_missing_template_source_is_skipped_not_fatal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    base = tmp_path / ".yate"
    fake_pairs = [(package_root() / "no-such-theme.example",
                   "themes/no-such-theme.example")]
    monkeypatch.setattr(us, "_template_sources", lambda: fake_pairs)
    report = us.setup_defaults(base_dir=base)
    assert report.errors == []
    assert report.skipped_templates == ["themes/no-such-theme.example"]
    assert report.refreshed_templates == []
    assert (base / "yaterc").is_file()


def test_oserror_collected_when_theme_dir_blocked_by_file(tmp_path: Path) -> None:
    base = tmp_path / ".yate"
    base.mkdir(parents=True)
    # A regular file occupying the themes/ path makes every theme
    # template copy fail; setup must keep going and report instead.
    (base / "themes").write_text("blocker", encoding="utf-8")

    report = us.setup_defaults(base_dir=base)

    assert report.errors
    assert any("themes" in e for e in report.errors)
    assert (base / "yaterc").is_file()
    assert (base / "extensions" / "example_ext.py.example").is_file()


# --- cleanup_defaults -------------------------------------------------------


def test_default_removes_config_keeps_data(tmp_path: Path) -> None:
    base = tmp_path / ".yate"
    _populate(base)
    report = us.cleanup_defaults(force=True, base_dir=base)

    assert report.errors == []
    assert not (base / "yaterc").exists()
    assert not (base / "themes").exists()
    assert not (base / "extensions").exists()
    assert (base / "data" / "crash-x.err").is_file()
    assert report.removed_files == ["yaterc"]
    assert sorted(report.removed_dirs) == ["extensions", "themes"]
    assert report.preserved == ["data"]
    assert not report.base_removed


def test_include_data_empties_and_removes_base_dir(tmp_path: Path) -> None:
    base = tmp_path / ".yate"
    _populate(base)
    report = us.cleanup_defaults(force=True, include_data=True, base_dir=base)
    assert report.errors == []
    assert not base.exists()
    assert report.base_removed
    assert sorted(report.removed_dirs) == ["data", "extensions", "themes"]
    assert report.preserved == []


def test_unknown_entries_preserved_keep_base_dir(tmp_path: Path) -> None:
    base = tmp_path / ".yate"
    _populate(base)
    (base / "notes.txt").write_text("mine", encoding="utf-8")

    report = us.cleanup_defaults(force=True, base_dir=base)

    assert (base / "notes.txt").read_text(encoding="utf-8") == "mine"
    assert "notes.txt" in report.preserved
    assert not report.base_removed


def test_interactive_yes_executes_no_cancels(tmp_path: Path) -> None:
    base = tmp_path / ".yate"
    _populate(base)
    agreed = us.cleanup_defaults(
        base_dir=base, stdin=_FakeTTY("y\n"), stdout=_FakeTTY("")
    )
    assert not agreed.cancelled
    assert not (base / "yaterc").exists()
    assert (base / "data").is_dir()


def test_interactive_non_yes_answers_cancel(tmp_path: Path) -> None:
    base = tmp_path / ".yate"
    _populate(base)
    # Any non-yes answer (including an empty line) cancels and
    # deletes nothing; state is unchanged between attempts.
    for answer in ("n\n", "\n", "q\n"):
        denied = us.cleanup_defaults(
            base_dir=base, stdin=_FakeTTY(answer), stdout=_FakeTTY(""),
        )
        assert denied.cancelled, answer
        assert (base / "yaterc").is_file()
        assert (base / "themes" / "dracula.py").is_file()
        assert denied.removed_files == []
        assert "data" in denied.preserved


def test_non_interactive_stdin_without_force_is_refused(tmp_path: Path) -> None:
    base = tmp_path / ".yate"
    _populate(base)
    with pytest.raises(us.ConfirmationRequiredError):
        us.cleanup_defaults(
            base_dir=base, stdin=io.StringIO("y\n"), stdout=io.StringIO(),
        )
    # Refusal deletes nothing.
    assert (base / "yaterc").is_file()
    assert (base / "themes" / "dracula.py").is_file()


def test_missing_base_dir_is_an_empty_success(tmp_path: Path) -> None:
    base = tmp_path / ".yate"
    report = us.cleanup_defaults(force=True, base_dir=base)
    assert report.errors == []
    assert not report.cancelled
    assert not report.base_removed
    assert report.removed_files == []
    assert report.removed_dirs == []
    assert not base.exists()


def test_only_unknown_entries_is_nothing_to_remove(tmp_path: Path) -> None:
    base = tmp_path / ".yate"
    base.mkdir(parents=True)
    (base / "notes.txt").write_text("mine", encoding="utf-8")
    # Must not prompt even without force: nothing destructive planned.
    report = us.cleanup_defaults(
        base_dir=base, stdin=io.StringIO(), stdout=io.StringIO()
    )
    assert report.nothing_to_remove
    assert report.preserved == ["notes.txt"]
    assert (base / "notes.txt").is_file()


# --- base directory removal --------------------------------------------------


def test_cleanup_reports_the_reason_when_the_base_dir_cannot_be_removed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A base directory that survives the cleanup must say why.

    ``except OSError: pass`` left ``base_removed`` False with no reason at all,
    so the report the CLI prints on that path -- which never starts tracing, so
    a log line would never be seen -- could not tell busy from read-only.
    """
    base = tmp_path / ".yate"
    _populate(base)

    def _locked(self: Path) -> None:
        """Stand-in for a base directory Windows refuses to remove."""
        raise OSError("directory not empty")

    # stubbed rather than faked with a real file lock: lock semantics differ
    # per platform and per filesystem driver
    monkeypatch.setattr(Path, "rmdir", _locked)

    report = us.cleanup_defaults(force=True, include_data=True, base_dir=base)

    assert report.base_removed is False
    assert base.is_dir()
    # the isolated error does not swallow the rest of the report surface
    assert report.removed_files == ["yaterc"]
    assert sorted(report.removed_dirs) == ["data", "extensions", "themes"]
    assert report.errors
    assert any(
        ".yate/" in error and "directory not empty" in error
        for error in report.errors
    ), report.errors


def test_cleanup_reports_base_removed_when_rmdir_succeeds(tmp_path: Path) -> None:
    """Reverse path: the untouched success path still removes the base dir.

    "Empty" means empty *after* the managed entries are gone; a directory that
    starts out empty returns early as ``nothing_to_remove`` and never reaches
    the removal branch.
    """
    base = tmp_path / ".yate"
    _populate(base)

    report = us.cleanup_defaults(force=True, include_data=True, base_dir=base)

    assert report.base_removed is True
    assert report.errors == []
    assert not base.exists()


def test_cleanup_reports_an_unreadable_base_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A base directory whose entries cannot be probed is reported, not raised.

    The emptiness probe sits in the error-collecting cleanup function: an
    ``OSError`` there must land in ``report.errors`` instead of escaping and
    crashing the CLI (``base_removed`` simply stays ``False``).
    """
    base = tmp_path / ".yate"
    _populate(base)

    def _raise_oserror(self: Path) -> Iterator[Path]:
        raise OSError("access denied")

    monkeypatch.setattr(Path, "iterdir", _raise_oserror)

    report = us.cleanup_defaults(force=True, include_data=True, base_dir=base)

    assert report.base_removed is False
    assert any("access denied" in e for e in report.errors)


# --- confirmation prompt / report rendering (coverage plan-c) ----------------


def test_interactive_returns_false_when_stdin_lacks_isatty() -> None:
    """A stdin object without isatty() is treated as non-interactive."""

    class _NoIsatty:
        """Minimal stream stand-in that has no isatty at all."""

    assert (
        us._interactive(cast(TextIO, _NoIsatty()), cast(TextIO, io.StringIO()))
        is False
    )


def test_interactive_returns_false_when_isatty_raises_os_error() -> None:
    """A stream whose isatty() raises OSError is treated as non-interactive."""

    class _BrokenTTY(io.StringIO):
        @override
        def isatty(self) -> bool:
            raise OSError("closed stream")

    assert us._interactive(_BrokenTTY(), _FakeTTY()) is False


def test_confirmation_prompt_renders_non_directory_managed_entry(
    tmp_path: Path,
) -> None:
    """A managed name occupied by a file prints bare, without a file count."""
    blocker = tmp_path / "themes"
    blocker.write_text("blocker", encoding="utf-8")
    out = io.StringIO()

    us._print_confirmation_prompt(
        cast(TextIO, out), tmp_path, [], [blocker], ["data", "notes.txt"],
        include_data=False,
    )

    text = out.getvalue()
    assert "  themes\n" in text
    assert "themes/  (" not in text
    assert "data/  (crash logs; --include-data to remove)" in text
    assert "notes.txt  (unknown, not created by yate)" in text
    assert text.endswith("proceed? [y/N]: ")

    # With no preserved entry and --include-data off, the data hint prints.
    hint = io.StringIO()
    us._print_confirmation_prompt(
        cast(TextIO, hint), tmp_path, [], [], [], include_data=False
    )
    assert "(data/ kept unless --include-data)" in hint.getvalue()


def test_format_setup_report_renders_every_field(tmp_path: Path) -> None:
    """Every SetupReport field reaches the rendered summary."""
    report = us.SetupReport(
        base_dir=tmp_path,
        created_dirs=["themes", "extensions"],
        installed_rc=True,
        rc_skipped=True,
        rc_backup=tmp_path / us.RC_BACKUP,
        refreshed_templates=["themes/dracula_theme.example"],
        skipped_templates=["themes/missing.example"],
        errors=["themes/: disk full"],
    )
    text = us.format_setup_report(report)

    assert "created     themes/" in text
    assert "replaced" in text
    assert "(from yaterc.example)" in text
    assert f"backed up   {us.RC_BACKUP}" in text
    assert "skipped     yaterc already exists" in text
    assert "refreshed   themes/dracula_theme.example" in text
    assert "skipped     themes/missing.example" in text
    assert "error       themes/: disk full" in text
    # An error report carries no customize hint.
    assert "edit yaterc" not in text


def test_format_cleanup_report_renders_nothing_to_remove(tmp_path: Path) -> None:
    """nothing_to_remove reports the bare finding, without the data hint."""
    text = us.format_cleanup_report(
        us.CleanupReport(base_dir=tmp_path, nothing_to_remove=True)
    )

    assert f"no yate-managed configuration found under {tmp_path}" in text
    assert "data/ is recreated" not in text


def test_format_cleanup_report_renders_removed_and_preserved(
    tmp_path: Path,
) -> None:
    """removed / preserved / base-removed / error lines all render."""
    text = us.format_cleanup_report(
        us.CleanupReport(
            base_dir=tmp_path,
            removed_files=["yaterc"],
            removed_dirs=["themes"],
            preserved=["data", "notes.txt"],
            base_removed=True,
            errors=["yaterc: locked"],
        )
    )

    assert "removed:" in text
    assert "  yaterc\n" in text
    assert "  themes/\n" in text
    assert "data/ preserved (crash diagnostics)." in text
    assert "notes.txt preserved (not created by yate)." in text
    assert f"the now-empty {tmp_path} directory was removed." in text
    assert "data/ is recreated automatically on the next launch." in text
    assert "error: yaterc: locked" in text
