"""Tests for the editor_syntax engine: per-filetype backend dispatch."""

# pyright: reportPrivateUsage=false

from __future__ import annotations

from typing import override

import pytest

from yate.editor_syntax import engine, regex_backend
from yate.editor_syntax.tokens import Token


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
