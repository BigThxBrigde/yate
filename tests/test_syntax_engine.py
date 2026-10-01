"""Tests for the editor_syntax engine: per-filetype backend dispatch."""

# pyright: reportPrivateUsage=false

from __future__ import annotations

import logging
import sys
import types
from pathlib import Path
from typing import override

import pytest

from yate.editor_syntax import engine, regex_backend
from yate.editor_syntax.tokens import Token
from yate.editor_syntax.ts_backend import languages


class _FakeTS:
    """Stands in for yate.editor_syntax.ts_backend without the dependency."""

    def __init__(self) -> None:
        self.filetypes: set[str] = set()

    def available_for(self, filetype: str) -> bool:
        return filetype.lower().lstrip(".") in self.filetypes

    def tokenize_document(
        self, lines: list[str], filetype: str
    ) -> list[list[Token]]:
        return [[Token(0, len(line), "comment")] for line in lines]


class _RecordingTS(_FakeTS):
    """Remembers the raw filetype strings the engine passes through."""

    def __init__(self) -> None:
        super().__init__()
        self.requested: list[str] = []

    @override
    def available_for(self, filetype: str) -> bool:
        self.requested.append(filetype)
        return super().available_for(filetype)

    @override
    def tokenize_document(
        self, lines: list[str], filetype: str
    ) -> list[list[Token]]:
        self.requested.append(f"tokenize:{filetype}")
        return super().tokenize_document(lines, filetype)


# --- backend dispatch -------------------------------------------------------


def test_falls_back_to_regex_backend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _FakeTS()  # no filetype registered -> unavailable
    monkeypatch.setattr(engine, "_ts", lambda: fake)
    assert engine.tokenize_document(["x = 1"], "py") == \
        regex_backend.tokenize_document(["x = 1"], "py")


def test_ts_backend_wins_when_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _FakeTS()
    fake.filetypes.add("py")
    monkeypatch.setattr(engine, "_ts", lambda: fake)
    result = engine.tokenize_document(["x = 1"], "py")
    assert result == [[Token(0, 5, "comment")]]


def test_unknown_filetype_yields_plain_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _FakeTS()
    monkeypatch.setattr(engine, "_ts", lambda: fake)
    assert engine.tokenize_document(["hello"], "xyz") == [[]]


def test_ts_import_failure_falls_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # _ts() returning None (dependency missing) must degrade to regex.
    monkeypatch.setattr(engine, "_ts", lambda: None)
    assert engine.tokenize_document(["def f(): pass"], "py") == \
        regex_backend.tokenize_document(["def f(): pass"], "py")


def test_filetype_is_forwarded_unnormalized_to_the_backend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The engine normalizes only its pin lookup; the backend receives the
    # original string so its own discovery rules stay authoritative.
    rec = _RecordingTS()
    rec.filetypes.add("py")
    monkeypatch.setattr(engine, "_ts", lambda: rec)
    engine.tokenize_document(["# c"], ".PY")
    assert rec.requested == [".PY", "tokenize:.PY"]


# --- regex pinning ----------------------------------------------------------


def test_prefer_regex_pins_filetype(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeTS()
    fake.filetypes.add("py")
    monkeypatch.setattr(engine, "_REGEX_PINNED", set[str]())
    monkeypatch.setattr(engine, "_ts", lambda: fake)
    engine.prefer_regex("py")
    assert engine.tokenize_document(["x = 1"], "py") == \
        regex_backend.tokenize_document(["x = 1"], "py")


def test_prefer_regex_normalizes_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeTS()
    fake.filetypes.add("py")
    monkeypatch.setattr(engine, "_REGEX_PINNED", set[str]())
    monkeypatch.setattr(engine, "_ts", lambda: fake)
    engine.prefer_regex(".PY", "")
    # ".PY" normalizes to "py" and pins it; the empty key is dropped
    assert engine.tokenize_document(["x = 1"], "py") == \
        regex_backend.tokenize_document(["x = 1"], "py")


def test_pin_matches_on_the_request_side_too(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _FakeTS()
    fake.filetypes.add("py")
    monkeypatch.setattr(engine, "_REGEX_PINNED", set[str]())
    monkeypatch.setattr(engine, "_ts", lambda: fake)
    engine.prefer_regex(".PY")
    assert engine.tokenize_document(["x = 1"], "PY") == \
        regex_backend.tokenize_document(["x = 1"], "PY")


def test_prefer_regex_pins_each_argument(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(engine, "_REGEX_PINNED", set[str]())
    engine.prefer_regex("py", ".RS", "")
    assert engine._REGEX_PINNED == {"py", "rs"}


# --- ts_backend.languages degradation warnings ------------------------------


class _LogCapture(logging.Handler):
    """Collect messages from one logger.

    The ``yate`` root logger never propagates (``propagate = False``), so
    pytest's caplog cannot see child-logger records; attach this instead.
    """

    def __init__(self) -> None:
        super().__init__()
        self.messages: list[str] = []

    @override
    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())


class _FakeTSModule:
    """Minimal ``tree_sitter`` stand-in with working Language/Query."""

    @staticmethod
    def Language(_pointer: object) -> str:
        return "<language>"

    @staticmethod
    def Query(_language: object, _source: str) -> str:
        return "<query>"


class _BrokenTSModule:
    """``tree_sitter`` stand-in whose Language constructor fails."""

    @staticmethod
    def Language(_pointer: object) -> str:
        raise RuntimeError("broken grammar")


def test_load_builtin_warns_once_per_language_until_success(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """First degradation warns once; success re-arms the warning."""
    monkeypatch.setattr(languages, "_DEGRADED_WARNED", set[str]())
    monkeypatch.setattr(languages, "_LANGS", {})
    monkeypatch.setattr(languages, "QUERIES_DIR", tmp_path)
    (tmp_path / "fakelang.scm").write_text("(comment) @comment", encoding="utf-8")
    monkeypatch.setattr(languages, "BUILTIN_PACKS", {"fakelang": "tree_sitter_fakelang"})
    pack = types.ModuleType("tree_sitter_fakelang")
    setattr(pack, "language", lambda: 0)
    monkeypatch.setitem(sys.modules, "tree_sitter_fakelang", pack)

    capture = _LogCapture()
    logger = logging.getLogger("yate.editor_syntax.ts_backend.languages")
    logger.addHandler(capture)
    try:
        # First failure (dependency missing): warn once ...
        monkeypatch.setattr(languages, "tree_sitter", lambda: None)
        assert languages._load_builtin("fakelang") is None
        assert capture.messages == [
            "tree-sitter unavailable for 'fakelang' (falls back to regex)"
        ]

        # ... a second failure of the same language stays silent ...
        assert languages._load_builtin("fakelang") is None
        assert capture.messages == [
            "tree-sitter unavailable for 'fakelang' (falls back to regex)"
        ]

        # ... and the other failure path (broken grammar) is deduplicated too.
        monkeypatch.setattr(languages, "tree_sitter", _BrokenTSModule)
        assert languages._load_builtin("fakelang") is None
        assert capture.messages == [
            "tree-sitter unavailable for 'fakelang' (falls back to regex)"
        ]

        # A successful load clears the dedup entry ...
        monkeypatch.setattr(languages, "tree_sitter", _FakeTSModule)
        assert languages._load_builtin("fakelang") is not None
        assert capture.messages == [
            "tree-sitter unavailable for 'fakelang' (falls back to regex)"
        ]

        # ... so a later failure warns again.
        monkeypatch.setattr(languages, "tree_sitter", lambda: None)
        assert languages._load_builtin("fakelang") is None
        assert capture.messages == [
            "tree-sitter unavailable for 'fakelang' (falls back to regex)",
            "tree-sitter unavailable for 'fakelang' (falls back to regex)",
        ]
    finally:
        logger.removeHandler(capture)


def test_resolve_blocked_build_warns_once_per_language(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The blocked tree-sitter branch degrades loudly once, then silently."""
    monkeypatch.setattr(languages, "_BLOCKED_TS", "0.26.0")
    monkeypatch.setattr(languages, "_DEGRADED_WARNED", set[str]())
    monkeypatch.setattr(languages, "_FAILED", set[str]())
    monkeypatch.setattr(languages, "_LANGS", {})
    monkeypatch.setattr(languages, "_EXT_TO_LANG", {})
    capture = _LogCapture()
    logger = logging.getLogger("yate.editor_syntax.ts_backend.languages")
    logger.addHandler(capture)
    try:
        # First resolution of a language under a blocked build warns once ...
        assert languages.resolve("py") is None
        assert capture.messages == [
            "tree-sitter python is a blocked build (falls back to regex)"
        ]

        # ... a repeat is short-circuited by _FAILED and stays silent ...
        assert languages.resolve("py") is None
        assert len(capture.messages) == 1

        # ... and so is a third attempt with _FAILED cleared: the per-language
        # dedup set kept by the warning helper absorbs it.
        monkeypatch.setattr(languages, "_FAILED", set[str]())
        assert languages.resolve("py") is None
        assert len(capture.messages) == 1
    finally:
        logger.removeHandler(capture)
