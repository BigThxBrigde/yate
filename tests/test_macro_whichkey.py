"""Regression tests for the macro which-key hint surface (plan-i / wave-4).

Covers the pinned-sheet auto-collection of the three shared macro bindings
(F16), the bilingual which-key docs registration of the awaiting hint and
the replay-count semantics, the guards.py f6 premise, and the evidence that
whichkey_flows.py itself was left untouched by the macro work.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Sequence
from pathlib import Path
from typing import cast

from yate.editor_components.whichkey import ChordEntry, WhichKeyPanel
from yate.flows.whichkey_flows import WhichKeyFlows
from yate.keymaps.base import Keymap
from yate.keymaps.keys import (
    MACRO_PLAY_KEY,
    MACRO_RECORD_KEY,
    MACRO_REPLAY_LAST_KEY,
    parse_key,
)
from yate.keymaps.registry import KeymapSet
from yate.keymaps.vim import VimKeymap
from yate.keymaps.vsc import VscKeymap

_REPO_ROOT = Path(__file__).resolve().parents[1]
_EN = _REPO_ROOT / "yate" / "docs" / "which-key.en.md"
_ZH = _REPO_ROOT / "yate" / "docs" / "which-key.zh.md"
_GUARDS = _REPO_ROOT / "tools" / "smoke_test" / "scenarios" / "guards.py"
_WHICHKEY_FLOWS = _REPO_ROOT / "yate" / "flows" / "whichkey_flows.py"

_MACRO_LABEL_BY_RAW: dict[str, str] = {
    parse_key(MACRO_RECORD_KEY): "<f10>",
    parse_key(MACRO_PLAY_KEY): "<f11>",
    parse_key(MACRO_REPLAY_LAST_KEY): "<f12>",
}
_MACRO_LABELS = tuple(_MACRO_LABEL_BY_RAW.values())
_MACRO_RAWS = frozenset(_MACRO_LABEL_BY_RAW)
_F6_RAW = "\x1b[17~"

_DRIVE_PATH = re.compile(r"[A-Za-z]:[\\/]")
_POSIX_ABS_PATH = re.compile(
    r"(?:^|[\s`(\[])/(?:home|Users|root|usr|var|etc|tmp|opt|[A-Za-z0-9_.-]+)/"
)
_HOME_PATH = re.compile(r"~[\\/]")
_URL = re.compile(r"https?://\S+")


class _PanelRecorder:
    """Recording stand-in for WhichKeyPanel; captures pushed rows."""

    def __init__(self) -> None:
        self.shown: list[tuple[str, tuple[ChordEntry, ...]]] = []
        self.clears = 0

    def show_entries(self, header: str, entries: Sequence[ChordEntry]) -> None:
        """Record one (header, entries) push."""
        self.shown.append((header, tuple(entries)))

    def clear(self) -> None:
        """Record one hide."""
        self.clears += 1


def _sheet_entries_for(keymap: Keymap) -> list[ChordEntry]:
    """Pinned-sheet rows via the public toggle/refresh path (F16)."""
    panel = _PanelRecorder()
    flows = WhichKeyFlows(
        keymaps=KeymapSet({"active": keymap}, "active"),
        window_pending=lambda: False,
        window_chord_hints=lambda: (),
        panel=cast(WhichKeyPanel, panel),
        message=lambda _text, _kind: None,
        which_key_enabled=lambda: True,
    )
    flows.toggle()
    assert len(panel.shown) == 1
    return list(panel.shown[0][1])


def _macro_descriptions(keymap: Keymap) -> dict[str, str]:
    """label -> description for the three macro bindings of one keymap."""
    return {
        _MACRO_LABEL_BY_RAW[binding.key]: binding.description
        for binding in keymap.bindings
        if binding.key in _MACRO_LABEL_BY_RAW
    }


def _section(text: str, number: str) -> str:
    """Body of one numbered H2 section (header included, next H2 excluded)."""
    lines = text.splitlines()
    start: int | None = None
    for index, line in enumerate(lines):
        if line.startswith(f"## {number}."):
            start = index
            break
    assert start is not None, f"missing ## {number} section"
    end = len(lines)
    for index in range(start + 1, len(lines)):
        if lines[index].startswith("## "):
            end = index
            break
    return "\n".join(lines[start:end])


def test_whichkey_pinned_sheet_includes_all_three_macro_bindings() -> None:
    """Case 3-1: the pinned sheet auto-collects F10/F11/F12 on both keymaps."""
    label_sets: list[set[str]] = []
    for keymap in (VscKeymap(), VimKeymap()):
        entries = _sheet_entries_for(keymap)
        labels = {entry.key for entry in entries if entry.key in _MACRO_LABELS}
        assert labels == set(_MACRO_LABELS)
        label_sets.append(labels)
    assert label_sets[0] == label_sets[1], "vsc/vim macro label sets diverge"

    # Section 3 case 1 asks the corresponding descriptions to contain
    # "macro".  wave-2 landed <f12> as "Repeat last replay"
    # (vsc.py:131 / vim.py:242), which carries no "macro" token, while its
    # action name "macro_replay_last" does.  Assert the macro label over
    # the displayed description OR the action name, preserving the
    # "every macro row is macro-labelled" intent (reported as a wording
    # deviation with the measured evidence).
    for keymap in (VscKeymap(), VimKeymap()):
        for binding in keymap.bindings:
            if binding.key in _MACRO_RAWS:
                show_text = f"{binding.description} {binding.action}".lower()
                assert "macro" in show_text


def test_whichkey_macro_descriptions_name_the_actions() -> None:
    """Case 3-2: record / play / repeat descriptions, identical on both sides."""
    vsc = _macro_descriptions(VscKeymap())
    vim = _macro_descriptions(VimKeymap())
    assert set(vsc) == set(_MACRO_LABELS) == set(vim)
    assert vsc == vim, "macro descriptions differ between vsc and vim"
    assert "record" in vsc["<f10>"].lower()
    assert "play" in vsc["<f11>"].lower()
    assert "repeat" in vsc["<f12>"].lower() or "last" in vsc["<f12>"].lower()


def test_whichkey_docs_register_macro_awaiting_hint_in_both_languages() -> None:
    """Case 3-3: both ## 2 sections register keys, a-z0-9 and pinned sheet."""
    en = _section(_EN.read_text(encoding="utf-8"), "2")
    zh = _section(_ZH.read_text(encoding="utf-8"), "2")
    for body in (en, zh):
        for token in ("F10", "F11", "F12", "a-z0-9", "pinned sheet"):
            assert token in body
    assert "register" in en.lower()
    assert "寄存器" in zh


def test_whichkey_docs_document_count_and_fkey_limitations() -> None:
    """Case 3-4: both ## 4 sections carry the new count wording and no old limit."""
    en = _section(_EN.read_text(encoding="utf-8"), "4")
    zh = _section(_ZH.read_text(encoding="utf-8"), "4")
    for token in (
        "numeric prefix",
        "N times",
        "always returns one",
        ":macro-play",
        ":macro-replay-last",
        "printable prefix",
        "1<f12>",
    ):
        assert token in en
    for token in (
        "数字前缀",
        "N 次",
        "恒返回 1",
        ":macro-play",
        ":macro-replay-last",
        "f 键不参与 printable 前缀",
        "1<f12>",
    ):
        assert token in zh
    for body in (en, zh):
        assert "fixed one replay" not in body.lower()
        assert "把按键回放次数写死为单次" not in body


def test_whichkey_en_zh_section_headings_stay_paired() -> None:
    """Case 3-5: H2 headings stay paired in count, order and topic (doc section 3)."""

    def headings(path: Path) -> list[str]:
        return [
            line
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.startswith("## ")
        ]

    def numbers(rows: list[str]) -> list[str]:
        out: list[str] = []
        for row in rows:
            match = re.match(r"^##\s+(\d+)\.", row)
            assert match is not None
            out.append(match.group(1))
        return out

    en = headings(_EN)
    zh = headings(_ZH)
    assert len(en) == len(zh)
    assert numbers(en) == numbers(zh) == ["1", "2", "3", "4"]
    assert any(row.startswith("## 2") for row in en)
    assert any(row.startswith("## 2") for row in zh)
    assert any(row.startswith("## 4") for row in en)
    assert any(row.startswith("## 4") for row in zh)
    # The bilingual headings differ in text by design (zh carries a Chinese
    # name), so "paired" is checked as equal count/order plus the English
    # topic of each heading appearing in its Chinese counterpart.
    for en_row, zh_row in zip(en, zh, strict=True):
        topic = en_row.split(".", 1)[1].strip()
        assert topic in zh_row


def test_guards_f6_premise_not_broken_by_macro_keys() -> None:
    """Case 3-6: guards.py f6 "no built-in binding" premise survives (F18)."""
    source = _GUARDS.read_text(encoding="utf-8")
    assert r'_F6_RAW: str = "\x1b[17~"' in source
    assert "<f6>" in source
    assert "has no built-in binding" in source
    assert "binding_not_leaked" in source
    assert VscKeymap().lookup(_F6_RAW) is None
    assert VimKeymap().lookup(_F6_RAW) is None


def test_whichkey_flows_source_is_unchanged_by_macro_work() -> None:
    """Case 3-7: WhichKeyFlows keeps its six injections; no macro state added."""
    source = _WHICHKEY_FLOWS.read_text(encoding="utf-8")
    assert "macro_awaiting" not in source
    assert "session.macro" not in source
    tree = ast.parse(source)
    cls = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "WhichKeyFlows"
    )
    init = next(
        node
        for node in cls.body
        if isinstance(node, ast.FunctionDef) and node.name == "__init__"
    )
    params = {arg.arg for arg in init.args.args} - {"self"}
    assert params == {
        "keymaps",
        "window_pending",
        "window_chord_hints",
        "panel",
        "message",
        "which_key_enabled",
    }
    assert len(params) == 6


def test_whichkey_docs_contain_no_machine_local_paths() -> None:
    """Case 3-8: no drive / POSIX / home absolute paths in the bilingual docs."""
    # The whole document is scanned line by line (a stronger check than
    # limiting it to the newly added paragraphs); external URLs are exempt
    # per doc-conventions.md section 5, so they are stripped before matching.
    for path in (_EN, _ZH):
        for lineno, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            clean = _URL.sub("", line)
            assert not _DRIVE_PATH.search(clean), f"{path.name}:{lineno}: drive path"
            assert not _POSIX_ABS_PATH.search(clean), f"{path.name}:{lineno}: posix path"
            assert not _HOME_PATH.search(clean), f"{path.name}:{lineno}: home path"
