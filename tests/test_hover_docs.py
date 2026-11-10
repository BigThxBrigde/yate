"""Consistency tests for the LSP hover documentation (wave-2, plan f).

Verifies that the six bilingual doc files (lsp docs, manual, FEATURES) state
the same facts: a single ``F7`` hover key shared by both keymaps, mouse hover
gated by ``support_mouse``, a fully silent UI when the server returns no
documentation, and no stale ``Ctrl+K`` mapping or machine-local paths.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

LSP_EN = ROOT / "yate" / "docs" / "lsp.en.md"
LSP_ZH = ROOT / "yate" / "docs" / "lsp.zh.md"
MANUAL_EN = ROOT / "yate" / "resources" / "manual.en.md"
MANUAL_ZH = ROOT / "yate" / "resources" / "manual.zh.md"
FEATURES_EN = ROOT / "FEATURES.md"
FEATURES_ZH = ROOT / "FEATURES.zh.md"

SIX_FILES: tuple[Path, ...] = (
    LSP_EN,
    LSP_ZH,
    MANUAL_EN,
    MANUAL_ZH,
    FEATURES_EN,
    FEATURES_ZH,
)


def _read(path: Path) -> str:
    """Read a doc file as UTF-8 text."""
    return path.read_text(encoding="utf-8")


def _section(text: str, start: str, end: str) -> str:
    """Slice the text between two top-level headings (inclusive of start)."""
    start_match = re.search(rf"^{re.escape(start)}.*$", text, flags=re.MULTILINE)
    assert start_match is not None, f"heading not found: {start}"
    end_match = re.search(
        rf"^{re.escape(end)}.*$", text[start_match.end():], flags=re.MULTILINE
    )
    if end_match is None:
        return text[start_match.start():]
    return text[start_match.start(): start_match.end() + end_match.start()]


def test_lsp_docs_both_languages_describe_hover_and_f7() -> None:
    """Both lsp docs mention the hover capability bound to F7."""
    en: str = _read(LSP_EN)
    zh: str = _read(LSP_ZH)
    assert "F7" in en
    assert "hover" in en.lower()
    assert "F7" in zh
    assert ("悬停" in zh) or ("hover" in zh.lower())


def test_lsp_docs_both_languages_describe_silent_empty_behavior() -> None:
    """Both lsp docs state that no documentation means nothing is shown."""
    en: str = _read(LSP_EN)
    zh: str = _read(LSP_ZH)
    assert ("no documentation" in en.lower()) or ("nothing is shown" in en.lower())
    assert ("无文档" in zh) or ("不显示" in zh)


def test_manual_both_languages_put_the_same_key_in_vsc_and_vim_sections() -> None:
    """Section 5 of both manuals mentions F7 twice (vsc table + vim table)."""
    en: str = _section(_read(MANUAL_EN), "## 5.", "## 6.")
    zh: str = _section(_read(MANUAL_ZH), "## 5.", "## 6.")
    assert en.count("F7") >= 2
    assert zh.count("F7") >= 2
    # No table row may present Ctrl+K / ctrl-k as the hover key.
    for line in en.splitlines() + zh.splitlines():
        lowered: str = line.lower()
        if ("hover" in lowered) or ("悬停" in line) or ("documentation" in lowered):
            assert "ctrl+k" not in lowered.replace("ctrl+shift+k", "")
            assert "ctrl-k" not in lowered


def test_manual_cheat_sheet_uses_identical_f7_in_both_key_columns() -> None:
    """The Section 18 hover row writes F7 in both key columns."""
    for path in (MANUAL_EN, MANUAL_ZH):
        cheat: str = _section(_read(path), "## 18.", "## 19.")
        rows: list[str] = [
            line
            for line in cheat.splitlines()
            if line.startswith("|") and "F7" in line
        ]
        assert rows, f"no F7 row in {path.name} cheat sheet"
        hover_row: str = rows[0]
        assert hover_row.count("`F7`") == 2


def test_manual_lsp_sections_describe_mouse_hover_and_silence() -> None:
    """Section 16 of both manuals covers mouse hover and the silent-empty rule."""
    en: str = _section(_read(MANUAL_EN), "## 16.", "## 17.")
    zh: str = _section(_read(MANUAL_ZH), "## 16.", "## 17.")
    assert ("support_mouse" in en) and ("nothing is shown" in en.lower())
    assert ("support_mouse" in zh) or ("鼠标" in zh)
    assert ("无文档" in zh) or ("不显示" in zh)


def test_features_both_languages_mention_hover_and_f7() -> None:
    """Both feature lists mention F7 inside the LSP section (Section 11)."""
    for path in (FEATURES_EN, FEATURES_ZH):
        text: str = _read(path)
        lsp_section: str = _section(text, "## 11.", "## 12.")
        assert "F7" in lsp_section


def test_docs_never_present_ctrl_k_as_the_hover_key() -> None:
    """No doc line presents Ctrl+K / ctrl-k as the hover key."""
    for path in SIX_FILES:
        for line in _read(path).splitlines():
            lowered: str = line.lower()
            hoverish: bool = (
                ("hover" in lowered) or ("悬停" in line) or ("documentation" in lowered)
            )
            if hoverish:
                assert "ctrl+k" not in lowered.replace("ctrl+shift+k", "")
                assert "ctrl-k" not in lowered


def test_docs_contain_no_machine_local_absolute_paths() -> None:
    """No doc contains machine-local user paths (architecture guard pattern)."""
    pattern: re.Pattern[str] = re.compile(
        "|".join(("[A-Za-z]:" + r"\\Users\\", "/" + "home/", "/" + "Users/")),
    )
    for path in SIX_FILES:
        assert pattern.search(_read(path)) is None, f"machine-local path in {path.name}"
