"""Tests for the tools.mdlint core package (engine, rules, CLI)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.mdlint.cli import main
from tools.mdlint.lint import LintEngine, LintViolation
from tools.mdlint.rules import lang_for_path


def test_scan_clean_markdown_returns_empty() -> None:
    """A clean document produces no violations."""
    engine = LintEngine("en")
    assert engine.scan("# Title\n\nBody\n") == []


def test_scan_detects_md013_long_line() -> None:
    """A paragraph line past the configured length triggers MD013."""
    engine = LintEngine("en")
    long_line = " ".join(["word"] * 24)
    assert len(long_line) > 100
    result = engine.scan(f"# Title\n\n{long_line}\n")
    assert len(result) >= 1
    assert result[0].rule_id == "MD013"


def test_scan_detects_md047_missing_trailing_newline() -> None:
    """A document without a trailing newline triggers MD047."""
    engine = LintEngine("en")
    result = engine.scan("# Title\n\nBody")
    assert any(v.rule_id == "MD047" for v in result)


def test_fix_resolves_trailing_newline() -> None:
    """fix() appends the missing trailing newline."""
    engine = LintEngine("en")
    fixed, remaining = engine.fix("# Title\n\nBody")
    assert fixed == "# Title\n\nBody\n"
    assert remaining == []


def test_fix_resolves_multiple_blanks() -> None:
    """fix() collapses runs of blank lines down to one."""
    engine = LintEngine("en")
    fixed, _ = engine.fix("# Title\n\n\n\nBody\n")
    assert "\n\n\n" not in fixed


def test_zh_profile_loads_custom_plugins() -> None:
    """The zh profile loads the custom plugins and reports YM001."""
    engine = LintEngine("zh")
    result = engine.scan("# 标题\n\n你好world\n")
    assert any(v.rule_id == "YM001" for v in result)


def test_zh_profile_skips_md013() -> None:
    """MD013 is disabled for zh: a long CJK line is clean."""
    engine = LintEngine("zh")
    result = engine.scan("# 标题\n\n" + "中" * 120 + "\n")
    assert result == []


def test_scan_file_reads_disk(tmp_path: Path) -> None:
    """scan_file reads the file from disk and returns violations."""
    engine = LintEngine("en")
    path = tmp_path / "sample.md"
    path.write_text("Body", encoding="utf-8")
    violations = engine.scan_file(path)
    assert violations


def test_fix_file_writes_disk(tmp_path: Path) -> None:
    """fix_file rewrites the file in place when it is fixable."""
    engine = LintEngine("en")
    path = tmp_path / "sample.md"
    path.write_text("# Title\n\nBody", encoding="utf-8")
    was_fixed, remaining = engine.fix_file(path)
    assert was_fixed is True
    assert remaining == []
    assert path.read_text(encoding="utf-8") == "# Title\n\nBody\n"


def test_fix_file_keeps_lf_line_endings(tmp_path: Path) -> None:
    """The fixed file is written with LF even on Windows."""
    engine = LintEngine("en")
    path = tmp_path / "sample.md"
    path.write_bytes(b"# Title\n\n\n\nBody")
    assert engine.fix_file(path)[0] is True
    assert b"\r" not in path.read_bytes()


def test_list_rules_returns_sorted(capsys: pytest.CaptureFixture[str]) -> None:
    """--list-rules prints a non-empty, sorted rule list."""
    assert main(["--list-rules"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines
    assert lines == sorted(lines)


def test_invalid_lang_raises() -> None:
    """An unknown language profile raises ValueError."""
    with pytest.raises(ValueError):
        LintEngine("fr")


def test_cli_check_exit_1_on_violation(tmp_path: Path) -> None:
    """--check returns 1 when the file has violations."""
    path = tmp_path / "bad.md"
    path.write_text("Body", encoding="utf-8")
    assert main(["--check", "--lang", "en", str(path)]) == 1


def test_cli_check_exit_0_on_clean(tmp_path: Path) -> None:
    """--check returns 0 for a clean file."""
    path = tmp_path / "good.md"
    path.write_text("# Title\n\nBody\n", encoding="utf-8")
    assert main(["--check", "--lang", "en", str(path)]) == 0


def test_cli_fix_exit_0_when_all_fixable(tmp_path: Path) -> None:
    """--fix returns 0 when every violation is auto-fixable."""
    path = tmp_path / "fixable.md"
    path.write_text("# Title\n\n\n\nBody", encoding="utf-8")
    assert main(["--fix", "--lang", "en", str(path)]) == 0
    assert path.read_text(encoding="utf-8") == "# Title\n\nBody\n"


def test_zh_profile_ignores_rules_outside_the_allowlist() -> None:
    """pymarkdown's default rule set does not leak into the profile.

    The engine disables everything and enables only the profile's rules, so
    a blank line between two block quotes (MD028, not in either profile)
    stays silent instead of reporting a rule the profile never asked for.
    """
    engine = LintEngine("zh")
    assert engine.scan("# 标题\n\n> 引述\n\n> 再引述\n") == []


def test_cli_backend_failure_on_one_file_exits_2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A file the backend chokes on is reported and mapped to exit 2."""
    from tools.mdlint.lint import LintEngine

    def explode(self: LintEngine, path: Path) -> list[object]:
        raise RuntimeError("rehydrate index mismatch")

    monkeypatch.setattr(LintEngine, "scan_file", explode)
    path = tmp_path / "odd.md"
    path.write_text("# Title\n\nBody\n", encoding="utf-8")
    assert main(["--check", "--lang", "en", str(path)]) == 2
    assert "cannot lint" in capsys.readouterr().err


def test_cli_fix_backend_failure_exits_2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A file the backend chokes on during ``--fix`` also maps to exit 2."""
    from tools.mdlint.lint import LintEngine

    def explode(self: LintEngine, path: Path) -> tuple[bool, list[LintViolation]]:
        raise RuntimeError("rehydrate index mismatch")

    monkeypatch.setattr(LintEngine, "fix_file", explode)
    path = tmp_path / "odd.md"
    path.write_text("# Title\n\nBody\n", encoding="utf-8")
    assert main(["--fix", "--lang", "en", str(path)]) == 2
    assert "cannot lint" in capsys.readouterr().err


def test_cli_violations_win_over_a_failed_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A backend failure on one file must not mask another file's violations."""
    from tools.mdlint.lint import LintEngine

    original = LintEngine.scan_file

    def flaky(self: LintEngine, path: Path) -> list[LintViolation]:
        if path.name == "odd.md":
            raise RuntimeError("rehydrate index mismatch")
        return original(self, path)

    monkeypatch.setattr(LintEngine, "scan_file", flaky)
    bad = tmp_path / "bad.md"
    bad.write_text("Body", encoding="utf-8")
    odd = tmp_path / "odd.md"
    odd.write_text("# Title\n\nBody\n", encoding="utf-8")
    assert main(["--check", "--lang", "en", str(bad), str(odd)]) == 1


def test_cli_missing_path_is_usage_error(tmp_path: Path) -> None:
    """A PATH that is not an existing file exits with 2."""
    assert main(["--check", "--lang", "en", str(tmp_path / "nope.md")]) == 2


def test_cli_fix_missing_file_is_usage_error(tmp_path: Path) -> None:
    """--fix on a missing file exits with 2."""
    missing = tmp_path / "docs_zelf.md"
    assert main(["--fix", "--auto-lang", str(missing)]) == 2


def test_lang_for_path_zh_suffix() -> None:
    """Files ending in .zh.md map to the zh profile."""
    assert lang_for_path("docs/guide.zh.md") == "zh"
    assert lang_for_path("docs\\guide.zh.md") == "zh"


def test_lang_for_path_trae_dir() -> None:
    """Anything below a .trae directory maps to the zh profile."""
    assert lang_for_path(".trae/rules/architecture-boundaries.md") == "zh"
    assert lang_for_path("sub/dir/.trae/notes.md") == "zh"


def test_lang_for_path_en_suffix_wins_inside_trae() -> None:
    """An English twin under ``.trae`` stays English."""
    assert lang_for_path(".trae/documents/plan.en.md") == "en"


def test_lang_for_path_readme_defaults_en() -> None:
    """README/CHANGELOG map to the en profile."""
    assert lang_for_path("README.md") == "en"
    assert lang_for_path("CHANGELOG.md") == "en"


def test_lang_for_path_en_suffix_and_default_en() -> None:
    """Everything else (including *.en.md) maps to the en profile."""
    assert lang_for_path("docs/api.en.md") == "en"
    assert lang_for_path("notes.md") == "en"
    assert lang_for_path("a/b/c.md") == "en"


def test_cli_auto_lang_conflicts_with_lang(tmp_path: Path) -> None:
    """--lang together with --auto-lang is a usage error (exit 2)."""
    path = tmp_path / "a.md"
    path.write_text("# Title\n\nBody\n", encoding="utf-8")
    with pytest.raises(SystemExit) as excinfo:
        main(["--check", "--lang", "en", "--auto-lang", str(path)])
    assert excinfo.value.code == 2


def test_cli_auto_lang_picks_zh_profile(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """--auto-lang applies the zh profile to *.zh.md files."""
    path = tmp_path / "guide.zh.md"
    path.write_text("# 标题\n\n你好world\n", encoding="utf-8")
    assert main(["--check", "--auto-lang", str(path)]) == 1
    assert "YM001" in capsys.readouterr().out
