"""Paired bilingual checks for the bundled macro documentation.

The English and Chinese manuals must register the three macro keys, the
``:macro-*`` commands, the ``rec @a`` indicator and the replay-count rule
in the same sections and in the same order.  Paths follow
``doc-conventions.md``: the manuals live under ``yate/resources/`` and
references stay relative and free of machine-local absolute paths.
"""

from __future__ import annotations

import re
from pathlib import Path

_ROOT: Path = Path(__file__).resolve().parent.parent
_EN_PATH: Path = _ROOT / "yate/resources/manual.en.md"
_ZH_PATH: Path = _ROOT / "yate/resources/manual.zh.md"
_EN_TEXT: str = _EN_PATH.read_text(encoding="utf-8")
_ZH_TEXT: str = _ZH_PATH.read_text(encoding="utf-8")

_HEADING_RE: re.Pattern[str] = re.compile(r"^(#{2,3})\s+(\d+(?:\.\d+)*)?")
_URL_RE: re.Pattern[str] = re.compile(r"https?://\S+")


def _section(text: str, start: str, end: str) -> str:
    """Return the block from the first *start* heading up to the first *end* heading.

    Both arguments are regular expressions anchored at a heading line.  The
    start heading itself is part of the returned block; the end heading is not.
    """
    lines = text.splitlines()
    start_re = re.compile(start)
    end_re = re.compile(end)
    begin = next(i for i, line in enumerate(lines) if start_re.match(line))
    stop = next(
        (i for i in range(begin + 1, len(lines)) if end_re.match(lines[i])),
        len(lines),
    )
    return "\n".join(lines[begin:stop])


def _heading_keys(text: str) -> list[str]:
    """Reduce headings to their level plus numeric label for cross-language pairing."""
    keys: list[str] = []
    for line in text.splitlines():
        match = _HEADING_RE.match(line)
        if match is None:
            continue
        level = str(match.group(1))
        label = str(match.group(2) or "")
        keys.append(f"{level} {label}".rstrip())
    return keys


def _machine_local_path_patterns() -> list[re.Pattern[str]]:
    """Build the four doc-conventions section 5 local-path shapes at runtime.

    Fragments are assembled instead of written out so this module never
    carries a home-directory literal that the source guard would flag.
    """
    slash = "/"
    drive = r"[A-Za-z]:[\\/]"
    return [
        re.compile(drive),
        re.compile(drive + r"+Users" + r"[\\/]"),
        re.compile(slash + "home" + slash + r"[^/\s\"']+"),
        re.compile(slash + "Users" + slash + r"[^/\s\"']+"),
    ]


def test_manual_both_languages_list_all_three_macro_keys() -> None:
    """Sections 5.1 and 5.2 of both manuals list the three shared macro keys."""
    keys = ("F10", "F11", "F12")
    blocks: list[tuple[str, str]] = [
        (_section(_EN_TEXT, r"^### 5\.1", r"^### 5\.2"), "macro"),
        (_section(_EN_TEXT, r"^### 5\.2", r"^## 6\b"), "macro"),
        (_section(_ZH_TEXT, r"^### 5\.1", r"^### 5\.2"), "宏"),
        (_section(_ZH_TEXT, r"^### 5\.2", r"^## 6\b"), "宏"),
    ]
    for block, marker in blocks:
        for key in keys:
            rows = [line for line in block.splitlines() if f"`{key}`" in line]
            assert len(rows) == 1
            assert marker in rows[0]


def test_manual_both_languages_document_macro_commands() -> None:
    """Section 8 of both manuals documents all four macro commands and registers."""
    commands = (":macro-record", ":macro-stop", ":macro-play", ":macro-replay-last")
    for text in (_EN_TEXT, _ZH_TEXT):
        block = _section(text, r"^## 8\b", r"^## 9\b")
        for command in commands:
            assert command in block
        assert "a-z0-9" in block


def test_manual_both_languages_document_recording_indicator() -> None:
    """Section 3.6 of both manuals documents the recording status-bar indicator."""
    en = _section(_EN_TEXT, r"^### 3\.6", r"^### 3\.7")
    zh = _section(_ZH_TEXT, r"^### 3\.6", r"^### 3\.7")
    assert "rec @" in en
    assert "rec @" in zh
    assert "status bar" in en
    assert "状态栏" in zh


def test_manual_both_languages_document_count_limitation() -> None:
    """Section 5 states the new count rule and drops the fixed-one-replay limit."""
    en = _section(_EN_TEXT, r"^## 5\b", r"^## 6\b")
    zh = _section(_ZH_TEXT, r"^## 5\b", r"^## 6\b")
    for block in (en, zh):
        for token in (":macro-play", ":macro-replay-last", "1<f12>"):
            assert token in block
        for stale in ("fixed one replay", "single replay only", "写死为单次", "回放次数写死"):
            assert stale not in block
    assert "count" in en
    assert "prefix" in en
    assert "N times" in en
    assert "always one" in en
    assert "double entry point" in en
    assert "次数" in zh
    assert "前缀" in zh
    assert "N 次" in zh
    assert "恒 1" in zh
    assert "双入口" in zh


def test_manual_en_zh_section_headings_stay_paired() -> None:
    """Both manuals keep identical heading levels and numeric labels in order."""
    en_keys = _heading_keys(_EN_TEXT)
    zh_keys = _heading_keys(_ZH_TEXT)
    assert en_keys == zh_keys
    for key in ("## 5", "### 5.1", "### 5.2", "## 8", "### 3.6"):
        assert key in en_keys
        assert key in zh_keys


def test_manual_paths_use_actual_resources_location() -> None:
    """The manuals live under yate/resources; the issue's yate/docs path is absent."""
    assert (_ROOT / "yate/resources/manual.en.md").is_file()
    assert (_ROOT / "yate/resources/manual.zh.md").is_file()
    assert not (_ROOT / "yate/docs/manual.en.md").exists()


def test_manual_existing_f7_hover_rows_unchanged() -> None:
    """The pre-existing F7 hover rows survive the new macro key rows."""
    for text in (_EN_TEXT, _ZH_TEXT):
        for start, end in (
            (r"^### 5\.1", r"^### 5\.2"),
            (r"^### 5\.2", r"^## 6\b"),
        ):
            block = _section(text, start, end)
            rows = [line for line in block.splitlines() if "`F7`" in line]
            assert rows
            assert any("hover" in row.lower() for row in rows)


def test_manual_new_sections_contain_no_machine_local_paths() -> None:
    """Freshly added macro documentation rows carry no machine-local path."""
    patterns = _machine_local_path_patterns()
    markers = (
        "`F10`", "`F11`", "`F12`", ":macro-", "rec @", "1<f12>", "3<f11>",
        "count", "prefix", "macro", "N times", "always one", "double entry",
        "次数", "前缀", "N 次", "恒 1", "双入口", "数字前缀",
    )
    for text in (_EN_TEXT, _ZH_TEXT):
        fresh = [
            line for line in text.splitlines()
            if any(marker in line for marker in markers)
        ]
        assert fresh
        for line in fresh:
            cleaned = _URL_RE.sub("", line)
            for pattern in patterns:
                assert pattern.search(cleaned) is None, cleaned
