"""Tests for the editor_syntax engine: per-filetype backend dispatch."""

# pyright: reportPrivateUsage=false

from __future__ import annotations

import unittest
from unittest import mock

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

    def available_for(self, filetype: str) -> bool:
        self.requested.append(filetype)
        return super().available_for(filetype)

    def tokenize_document(
        self, lines: list[str], filetype: str
    ) -> list[list[Token]]:
        self.requested.append(f"tokenize:{filetype}")
        return super().tokenize_document(lines, filetype)


class EngineDispatchTests(unittest.TestCase):
    """tokenize_document routes to the best backend per filetype."""

    def test_falls_back_to_regex_backend(self) -> None:
        fake = _FakeTS()  # no filetype registered -> unavailable
        with mock.patch.object(engine, "_ts", return_value=fake):
            self.assertEqual(
                engine.tokenize_document(["x = 1"], "py"),
                regex_backend.tokenize_document(["x = 1"], "py"),
            )

    def test_ts_backend_wins_when_available(self) -> None:
        fake = _FakeTS()
        fake.filetypes.add("py")
        with mock.patch.object(engine, "_ts", return_value=fake):
            result = engine.tokenize_document(["x = 1"], "py")
        self.assertEqual(result, [[Token(0, 5, "comment")]])

    def test_unknown_filetype_yields_plain_text(self) -> None:
        fake = _FakeTS()
        with mock.patch.object(engine, "_ts", return_value=fake):
            self.assertEqual(engine.tokenize_document(["hello"], "xyz"), [[]])

    def test_prefer_regex_pins_filetype(self) -> None:
        fake = _FakeTS()
        fake.filetypes.add("py")
        with mock.patch.object(engine, "_REGEX_PINNED", set[str]()), \
                mock.patch.object(engine, "_ts", lambda: fake):
            engine.prefer_regex("py")
            self.assertEqual(
                engine.tokenize_document(["x = 1"], "py"),
                regex_backend.tokenize_document(["x = 1"], "py"),
            )

    def test_prefer_regex_normalizes_keys(self) -> None:
        fake = _FakeTS()
        fake.filetypes.add("py")
        with mock.patch.object(engine, "_REGEX_PINNED", set[str]()), \
                mock.patch.object(engine, "_ts", lambda: fake):
            engine.prefer_regex(".PY", "")
            # ".PY" normalizes to "py" and pins it; the empty key is dropped
            self.assertEqual(
                engine.tokenize_document(["x = 1"], "py"),
                regex_backend.tokenize_document(["x = 1"], "py"),
            )

    def test_ts_import_failure_falls_back(self) -> None:
        # _ts() returning None (dependency missing) must degrade to regex.
        with mock.patch.object(engine, "_ts", return_value=None):
            self.assertEqual(
                engine.tokenize_document(["def f(): pass"], "py"),
                regex_backend.tokenize_document(["def f(): pass"], "py"),
            )

    def test_filetype_is_forwarded_unnormalized_to_the_backend(self) -> None:
        # The engine normalizes only its pin lookup; the backend receives the
        # original string so its own discovery rules stay authoritative.
        rec = _RecordingTS()
        rec.filetypes.add("py")
        with mock.patch.object(engine, "_ts", lambda: rec):
            engine.tokenize_document(["# c"], ".PY")
        self.assertEqual(rec.requested, [".PY", "tokenize:.PY"])

    def test_pin_matches_on_the_request_side_too(self) -> None:
        fake = _FakeTS()
        fake.filetypes.add("py")
        with mock.patch.object(engine, "_REGEX_PINNED", set[str]()), \
                mock.patch.object(engine, "_ts", lambda: fake):
            engine.prefer_regex(".PY")
            self.assertEqual(
                engine.tokenize_document(["x = 1"], "PY"),
                regex_backend.tokenize_document(["x = 1"], "PY"),
            )

    def test_prefer_regex_pins_each_argument(self) -> None:
        with mock.patch.object(engine, "_REGEX_PINNED", set[str]()):
            engine.prefer_regex("py", ".RS", "")
            self.assertEqual(engine._REGEX_PINNED, {"py", "rs"})


if __name__ == "__main__":
    unittest.main()
