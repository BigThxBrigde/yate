"""Paired bilingual checks for the bundled marks / jump-list documentation.

The English and Chinese manuals must list the three navigation keys as
table rows in both section 5 keymap tables and document the four marks /
jumps commands in section 8.  En/zh row counts stay paired and the fresh
rows stay free of machine-local paths.  Manuals resolve through
``importlib.resources`` (the same channel the in-app manual reader uses),
so this module carries no absolute path.
"""

from __future__ import annotations

import re
from importlib.resources import files

_KEYS: tuple[str, ...] = ("<alt-left>", "<alt-right>", "<alt-m>")
_COMMANDS: tuple[str, ...] = (":marks", ":delmark", ":jumps")
_ACTION_PAIRS: tuple[tuple[str, str], ...] = (
    ("<alt-left>", "jump_back"),
    ("<alt-right>", "jump_forward"),
    ("<alt-m>", "marks_overlay"),
)
_KEYMAP_SECTIONS: tuple[tuple[str, str], ...] = (
    (r"^### 5\.1", r"^### 5\.2"),
    (r"^### 5\.2", r"^## 6\b"),
)
_MARK_COMMAND_RE: re.Pattern[str] = re.compile(r"`:mark(?!s)\b")
_URL_RE: re.Pattern[str] = re.compile(r"https?://\S+")
_DRIVE_RE: re.Pattern[str] = re.compile(r"[A-Za-z]:[\\/]")


def _manual_texts() -> tuple[str, str]:
    """Read the bundled manuals (en, zh) through ``yate.resources``."""
    texts = [
        files("yate.resources").joinpath(name).read_text(encoding="utf-8")
        for name in ("manual.en.md", "manual.zh.md")
    ]
    return texts[0], texts[1]


def _section(text: str, start: str, end: str) -> str:
    """Return the block from the *start* heading up to the *end* heading.

    Both arguments are regular expressions anchored at a heading line; the
    start heading is part of the block, the end heading is not.
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


def _table_rows(block: str, token: str) -> list[str]:
    """Table lines (``|``-prefixed) in *block* that mention ``token``."""
    return [
        line for line in block.splitlines()
        if line.lstrip().startswith("|") and f"`{token}`" in line
    ]


def test_manual_both_languages_list_all_three_keys() -> None:
    """Both manuals list the three keys as rows in the 5.1 and 5.2 tables."""
    en, zh = _manual_texts()
    for text in (en, zh):
        for start, end in _KEYMAP_SECTIONS:
            block = _section(text, start, end)
            for key in _KEYS:
                rows = _table_rows(block, key)
                assert len(rows) == 1, (key, start, rows)


def test_manual_both_languages_document_marks_commands() -> None:
    """Section 8 of both manuals documents the four marks / jump commands."""
    en, zh = _manual_texts()
    for text in (en, zh):
        block = _section(text, r"^## 8\b", r"^## 9\b")
        for command in _COMMANDS:
            assert command in block, command
        assert _MARK_COMMAND_RE.search(block) is not None


def test_manual_en_zh_table_rows_stay_paired() -> None:
    """Each key row appears the same number of times in en and zh per section."""
    en, zh = _manual_texts()
    for start, end in _KEYMAP_SECTIONS:
        en_block = _section(en, start, end)
        zh_block = _section(zh, start, end)
        for key in _KEYS:
            en_rows = _table_rows(en_block, key)
            zh_rows = _table_rows(zh_block, key)
            assert len(en_rows) == len(zh_rows) >= 1, key


def test_manual_new_lines_have_no_machine_local_paths() -> None:
    """Lines carrying the new keys / commands never embed a drive-letter path."""
    en, zh = _manual_texts()
    markers = (
        *_KEYS,
        *_COMMANDS,
        ":mark ",
        *(action for _, action in _ACTION_PAIRS),
    )
    for text in (en, zh):
        fresh = [
            line for line in text.splitlines()
            if any(marker in line for marker in markers)
        ]
        assert fresh
        for line in fresh:
            cleaned = _URL_RE.sub("", line)
            assert _DRIVE_RE.search(cleaned) is None, cleaned


def test_manual_keys_match_action_names() -> None:
    """Manual key rows share terminology with the keymap action names."""
    from yate.keymaps.keys import (
        JUMPLIST_BACK_KEY,
        JUMPLIST_FORWARD_KEY,
        MARKS_OVERLAY_KEY,
    )
    from yate.keymaps.vim import VimKeymap
    from yate.keymaps.vsc import VscKeymap

    expected = (
        (JUMPLIST_BACK_KEY, "jump_back", "Jump back in jump history"),
        (JUMPLIST_FORWARD_KEY, "jump_forward", "Jump forward in jump history"),
        (MARKS_OVERLAY_KEY, "marks_overlay", "Open the marks overview"),
    )
    for keymap in (VscKeymap(), VimKeymap()):
        for raw, action, description in expected:
            binding = keymap.lookup(raw)
            assert binding is not None, action
            assert binding.action == action
            assert binding.description == description
    en, zh = _manual_texts()
    for text in (en, zh):
        for start, end in _KEYMAP_SECTIONS:
            block = _section(text, start, end)
            for key, action in _ACTION_PAIRS:
                rows = _table_rows(block, key)
                assert len(rows) == 1, (key, start)
                assert f"`{action}`" in rows[0], (key, action)
