"""Tests for the optional tree-sitter backend (skipped without the deps).

The backend itself degrades gracefully when ``tree_sitter`` is missing
(covered by the engine dispatch tests); the tests here only run when the
optional grammar packs are installed.
"""

# pyright: reportPrivateUsage=false

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import cast
from unittest import mock

from yate.editor_syntax import available_filetypes, engine, regex_backend, ts_backend
from yate.editor_syntax.ts_backend import backend as ts_runtime
from yate.editor_syntax.ts_backend import languages as ts_langs
from yate.editor_syntax.tokens import SYNTAX_KINDS, Token
from yate.services import extensions as ext_services

has_bash = importlib.util.find_spec("tree_sitter_bash") is not None
has_python = importlib.util.find_spec("tree_sitter_python") is not None
has_tree_sitter = ts_langs.ts_available()


def _kinds(tokens: list[Token], line: str) -> list[tuple[str, str]]:
    """Flatten tokens to ``(kind, text)`` pairs for readable assertions."""
    return [(t.kind, line[t.start:t.end]) for t in tokens]


@unittest.skipUnless(has_python, "tree_sitter_python is not installed")
class TsPythonTests(unittest.TestCase):
    """Python highlighting through the tree-sitter backend."""

    def test_keywords_numbers_strings(self) -> None:
        lines = ["# note", "def foo():", "    return 42", 'x = "s"']
        toks = ts_backend.tokenize_document(lines, "py")
        self.assertIn(("comment", "# note"), _kinds(toks[0], lines[0]))
        self.assertIn(("keyword", "def"), _kinds(toks[1], lines[1]))
        self.assertIn(("function", "foo"), _kinds(toks[1], lines[1]))
        self.assertIn(("keyword", "return"), _kinds(toks[2], lines[2]))
        self.assertIn(("number", "42"), _kinds(toks[2], lines[2]))
        self.assertIn(("string", '"s"'), _kinds(toks[3], lines[3]))

    def test_class_and_decorator_and_call(self) -> None:
        lines = ["class Bar:", "    pass", "@dec", "print(foo())"]
        toks = ts_backend.tokenize_document(lines, "py")
        self.assertIn(("type", "Bar"), _kinds(toks[0], lines[0]))
        self.assertIn(("decorator", "@dec"), _kinds(toks[2], lines[2]))
        kinds3 = _kinds(toks[3], lines[3])
        self.assertIn(("function", "print"), kinds3)
        self.assertIn(("function", "foo"), kinds3)

    def test_multiline_triple_string(self) -> None:
        lines = ["x = (", '    """', "    doc", '    """', ")"]
        toks = ts_backend.tokenize_document(lines, "py")
        # opening row: only the quotes are inside the string
        self.assertEqual(_kinds(toks[1], lines[1]), [("string", '"""')])
        # middle and closing rows are entirely string content
        self.assertEqual(_kinds(toks[2], lines[2]), [("string", "    doc")])
        self.assertEqual(_kinds(toks[3], lines[3]), [("string", '    """')])
        self.assertEqual(toks[4], [])

    def test_unicode_columns_are_character_based(self) -> None:
        line = 'x = "é" + 1  # cömment'
        toks = ts_backend.tokenize_document([line], "py")
        pairs = _kinds(toks[0], line)
        self.assertIn(("number", "1"), pairs)
        self.assertIn(("comment", "# cömment"), pairs)

    def test_unknown_filetype_is_plain(self) -> None:
        self.assertEqual(ts_backend.tokenize_document(["x"], "nope"), [[]])


@unittest.skipUnless(has_bash, "tree_sitter_bash is not installed")
class TsShellTests(unittest.TestCase):
    """Shell highlighting through the tree-sitter backend."""

    def test_comments_keywords_strings_commands(self) -> None:
        lines = [
            "# run",
            'echo "hello" $HOME',
            "if [ -f x ]; then ls; fi",
        ]
        toks = ts_backend.tokenize_document(lines, "sh")
        self.assertIn(("comment", "# run"), _kinds(toks[0], lines[0]))
        pairs1 = _kinds(toks[1], lines[1])
        self.assertIn(("function", "echo"), pairs1)
        self.assertIn(("string", '"hello"'), pairs1)
        pairs2 = _kinds(toks[2], lines[2])
        self.assertIn(("keyword", "if"), pairs2)
        self.assertIn(("keyword", "then"), pairs2)
        self.assertIn(("function", "ls"), pairs2)
        self.assertIn(("keyword", "fi"), pairs2)


@unittest.skipUnless(has_python, "tree_sitter_python is not installed")
class EngineRoutingTests(unittest.TestCase):
    """The engine routes ts-capable filetypes to the tree-sitter backend."""

    def test_engine_uses_ts_for_python(self) -> None:
        lines = ["# note", "def foo(): pass"]
        self.assertEqual(
            engine.tokenize_document(lines, "py"),
            ts_backend.tokenize_document(lines, "py"),
        )

    def test_prefer_regex_still_overrides_ts(self) -> None:
        lines = ["# note"]
        with mock.patch.object(engine, "_REGEX_PINNED", set[str]()):
            engine.prefer_regex("py")
            self.assertEqual(
                engine.tokenize_document(lines, "py"),
                regex_backend.tokenize_document(lines, "py"),
            )


class BlockedVersionTests(unittest.TestCase):
    """Known heap-corrupting tree-sitter builds force the regex fallback."""

    def test_version_classifier(self) -> None:
        cases = [
            ("win32", "0.26.0", "0.26.0"),
            ("win32", "0.26.99", "0.26.99"),
            ("win32", "0.25.2", None),
            ("win32", "0.27.0", None),
            ("linux", "0.26.0", None),
        ]
        for platform_name, raw, expected in cases:
            with (
                mock.patch.object(ts_langs.sys, "platform", platform_name),
                mock.patch.object(ts_langs, "version", return_value=raw),
            ):
                self.assertEqual(
                    ts_langs._blocked_ts_version(), expected,
                    msg=f"{platform_name} / {raw}",
                )

    def test_blocked_build_disables_ts_and_routes_to_regex(self) -> None:
        lines = ["# note", "def foo(): pass"]
        # Isolate the registry caches: another test module may already have
        # loaded the python grammar into _LANGS in this process, which would
        # make resolve() return early before reaching the block check.
        failed: set[str] = set()
        empty_langs: dict[str, ts_langs.LoadedLanguage] = {}
        with (
            mock.patch.object(ts_langs, "_BLOCKED_TS", "0.26.0"),
            mock.patch.object(ts_langs, "_LANGS", empty_langs),
            mock.patch.object(ts_langs, "_FAILED", failed),
        ):
            self.assertTrue(ts_runtime.tree_sitter_blocked())
            self.assertFalse(ts_runtime.available_for("py"))
            self.assertIsNone(ts_langs.resolve("py"))
            self.assertIn("python", failed)
            self.assertEqual(
                engine.tokenize_document(lines, "py"),
                regex_backend.tokenize_document(lines, "py"),
            )


@unittest.skipUnless(has_python, "tree_sitter_python is not installed")
class SyntaxBridgeTests(unittest.TestCase):
    """``api.syntax.register_tree_sitter`` end to end (bridge class)."""

    def test_unknown_pack_raises_value_error(self) -> None:
        from yate.services.extensions import SyntaxExtensionBridge

        bridge = SyntaxExtensionBridge()
        with self.assertRaises(ValueError):
            bridge.register_tree_sitter(
                "nope_lang",
                grammar="tree_sitter_definitely_missing_xyz",
                extensions=["npx"],
                query="(comment) @comment",
            )

    def test_pack_registration_and_query_file(self) -> None:
        from yate.editor_syntax.ts_backend import languages as ts_langs
        from yate.services.extensions import SyntaxExtensionBridge

        with tempfile.NamedTemporaryFile(
            "w", suffix=".scm", delete=False, encoding="utf-8"
        ) as fh:
            fh.write("(comment) @comment\n(string) @string\n")
            query_path = fh.name
        try:
            bridge = SyntaxExtensionBridge()
            with mock.patch.dict(ts_langs._LANGS), \
                    mock.patch.dict(ts_langs._EXT_TO_LANG), \
                    mock.patch.object(ts_langs, "_FAILED", set[str]()), \
                    mock.patch.dict(regex_backend._LANGUAGES), \
                    mock.patch.dict(regex_backend._NAME_TO_KEY):
                bridge.register_tree_sitter(
                    "pytestlang",
                    grammar="tree_sitter_python",
                    extensions=["ptl"],
                    query=query_path,  # file path variant
                )
                lines = ["# hi", 'x = "s"']
                self.assertTrue(ts_backend.available_for("ptl"))
                toks = ts_backend.tokenize_document(lines, "ptl")
                self.assertIn(("comment", "# hi"), _kinds(toks[0], lines[0]))
                self.assertIn(("string", '"s"'), _kinds(toks[1], lines[1]))
                # routed through the engine, and visible in :set filetype
                self.assertEqual(
                    engine.tokenize_document(lines, "ptl"),
                    ts_backend.tokenize_document(lines, "ptl"),
                )
                self.assertIn("ptl", available_filetypes())
        finally:
            Path(query_path).unlink(missing_ok=True)


class ByteColumnTests(unittest.TestCase):
    """tree-sitter reports byte columns; the backend speaks character cols."""

    def test_ascii_passes_through(self) -> None:
        self.assertEqual(ts_runtime._to_char(b"hello", 0), 0)
        self.assertEqual(ts_runtime._to_char(b"hello", 3), 3)

    def test_values_are_clamped_to_the_line(self) -> None:
        self.assertEqual(ts_runtime._to_char(b"abc", 99), 3)
        self.assertEqual(ts_runtime._to_char(b"abc", -5), 0)

    def test_multibyte_utf8(self) -> None:
        line = "xé".encode("utf-8")  # b"x\xc3\xa9"
        self.assertEqual(ts_runtime._to_char(line, 1), 1)
        self.assertEqual(ts_runtime._to_char(line, 3), 2)

    def test_column_inside_a_multibyte_sequence_drops_the_lone_lead(self) -> None:
        self.assertEqual(ts_runtime._to_char("xé".encode("utf-8"), 2), 1)


@dataclass
class _Point:
    row: int
    column: int


@dataclass
class _Node:
    """Minimal stand-in for a tree-sitter node's point geometry."""

    start_point: _Point
    end_point: _Point


class CaptureClipTests(unittest.TestCase):
    """Multi-line capture nodes are split into per-row character spans."""

    def _clip(self, node: _Node, lines: list[str]) -> list[tuple[int, int, int]]:
        return list(
            ts_runtime._clip_to_rows(
                cast(ts_runtime._TsNode, node),
                lines,
                [line.encode("utf-8") for line in lines],
            )
        )

    def test_single_line_node(self) -> None:
        self.assertEqual(
            self._clip(_Node(_Point(0, 0), _Point(0, 3)), ["abc"]),
            [(0, 0, 3)],
        )

    def test_multiline_node_fills_inner_rows(self) -> None:
        node = _Node(_Point(0, 1), _Point(2, 1))
        self.assertEqual(
            self._clip(node, ["ab", "cd", "ef"]),
            [(0, 1, 2), (1, 0, 2), (2, 0, 1)],
        )

    def test_node_starting_past_document_end_is_dropped(self) -> None:
        node = _Node(_Point(3, 0), _Point(4, 0))
        self.assertEqual(self._clip(node, ["a", "b"]), [])

    def test_node_ending_past_document_end_is_clamped(self) -> None:
        # Tree built before the document shrank: the tail clips to the last row.
        node = _Node(_Point(0, 0), _Point(5, 10))
        self.assertEqual(
            self._clip(node, ["ab", "cd"]), [(0, 0, 2), (1, 0, 2)]
        )


class RowLayoutTests(unittest.TestCase):
    """Overlapping captures resolve into flat, non-overlapping per-row tokens."""

    def test_empty_intervals_produce_no_tokens(self) -> None:
        self.assertEqual(ts_runtime._tokens_for_row([], 5), [])

    def test_single_span(self) -> None:
        self.assertEqual(
            ts_runtime._tokens_for_row([(0, 3, "keyword")], 5),
            [Token(0, 3, "keyword")],
        )

    def test_nested_span_inner_wins_and_gaps_keep_outer_kind(self) -> None:
        tokens = ts_runtime._tokens_for_row(
            [(0, 6, "string"), (2, 4, "keyword")], 6
        )
        self.assertEqual(
            tokens,
            [
                Token(0, 2, "string"),
                Token(2, 4, "keyword"),
                Token(4, 6, "string"),
            ],
        )

    def test_adjacent_same_kind_runs_are_merged(self) -> None:
        self.assertEqual(
            ts_runtime._tokens_for_row([(0, 2, "x"), (2, 4, "x")], 4),
            [Token(0, 4, "x")],
        )

    def test_adjacent_different_kinds_stay_separate(self) -> None:
        self.assertEqual(
            ts_runtime._tokens_for_row([(0, 2, "a"), (2, 4, "b")], 4),
            [Token(0, 2, "a"), Token(2, 4, "b")],
        )

    def test_spans_are_clipped_to_line_bounds(self) -> None:
        self.assertEqual(
            ts_runtime._tokens_for_row([(-3, 2, "a"), (4, 99, "b")], 5),
            [Token(0, 2, "a"), Token(4, 5, "b")],
        )

    def test_zero_length_span_is_dropped(self) -> None:
        self.assertEqual(
            ts_runtime._tokens_for_row([(2, 2, "a"), (0, 1, "b")], 5),
            [Token(0, 1, "b")],
        )

    def test_unsorted_input_comes_out_position_sorted(self) -> None:
        tokens = ts_runtime._tokens_for_row(
            [(4, 5, "a"), (0, 2, "b")], 5
        )
        self.assertEqual([token.start for token in tokens], [0, 4])


class TokenizeDegradeTests(unittest.TestCase):
    """The module stays usable with no content or no registered grammar."""

    def test_empty_document_returns_no_rows(self) -> None:
        # Even a resolvable language on zero lines returns an empty result.
        self.assertEqual(ts_backend.tokenize_document([], "py"), [])

    def test_unknown_filetype_is_plain_text_per_line(self) -> None:
        self.assertEqual(
            ts_backend.tokenize_document(["a", "bb"], "not_a_language_xyz"),
            [[], []],
        )


class SyntaxContractTests(unittest.TestCase):
    """Cross-module invariants every registered language must honor."""

    def test_capture_map_targets_are_valid_token_kinds(self) -> None:
        invalid = set(ts_langs.DEFAULT_CAPTURE_MAP.values()) - set(SYNTAX_KINDS)
        self.assertEqual(invalid, set())

    def test_builtin_packs_ship_a_query_file(self) -> None:
        for name in ts_langs.BUILTIN_PACKS:
            query = ts_langs.QUERIES_DIR / f"{name}.scm"
            self.assertTrue(query.is_file(), f"missing bundled query {query}")

    def test_symbol_name_replaces_non_identifier_characters(self) -> None:
        self.assertEqual(ts_langs._symbol_name("yate shell"), "yate_shell")
        self.assertEqual(ts_langs._symbol_name("MyLang-2!"), "mylang_2_")


class RegistryWithoutTreeSitterTests(unittest.TestCase):
    """With the optional dependency missing, each entry point degrades cleanly."""

    def test_availability_follows_the_probe(self) -> None:
        with mock.patch.object(ts_langs, "tree_sitter", lambda: None):
            self.assertFalse(ts_langs.ts_available())
        with mock.patch.object(ts_langs, "tree_sitter", lambda: object()):
            self.assertTrue(ts_langs.ts_available())

    def test_load_entry_points_raise_runtime_error(self) -> None:
        with mock.patch.object(ts_langs, "tree_sitter", lambda: None):
            with self.assertRaises(RuntimeError):
                ts_langs.load_language("x", object(), "")
            with self.assertRaises(RuntimeError):
                ts_langs.load_language_from_grammar("x", "tree_sitter_x", "")
            with self.assertRaises(RuntimeError):
                ts_langs.language_from_shared_library("x.so", "tree_sitter_x")

    def test_unknown_filetype_resolves_to_none(self) -> None:
        with mock.patch.object(ts_langs, "tree_sitter", lambda: None):
            self.assertIsNone(ts_langs.resolve("not_registered_language_xyz"))

    def test_failed_load_is_recorded_and_never_retried(self) -> None:
        with (
            mock.patch.dict(ts_langs._LANGS, {}, clear=True),
            mock.patch.dict(ts_langs._EXT_TO_LANG, {"fl": "fakelang"}, clear=True),
            mock.patch.object(ts_langs, "_FAILED", set[str]()),
            mock.patch.object(
                ts_langs, "_load_builtin", return_value=None
            ) as load,
        ):
            self.assertIsNone(ts_langs.resolve("fl"))
            self.assertIsNone(ts_langs.resolve("fl"))
            load.assert_called_once_with("fakelang")
            self.assertIn("fakelang", ts_langs._FAILED)


@unittest.skipUnless(has_tree_sitter, "tree_sitter is not installed")
class GrammarDiscoveryTests(unittest.TestCase):
    """Grammar argument handling when tree-sitter itself is importable."""

    def test_missing_pack_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            ts_langs.load_language_from_grammar(
                "zzz", "tree_sitter_definitely_missing_xyz", ""
            )

    def test_missing_shared_library_raises_os_error(self) -> None:
        library = str(Path("no_such_grammar_dir_xyz") / "zzz.so")
        with self.assertRaises(OSError):
            ts_langs.load_language_from_grammar("zzz", library, "")


@unittest.skipUnless(has_python, "tree_sitter_python is not installed")
class LoadLanguageRegistrationTests(unittest.TestCase):
    """``load_language`` wires the grammar into both backends."""

    def test_extensions_capture_map_and_failure_clearing(self) -> None:
        import tree_sitter as ts
        import tree_sitter_python

        language = ts.Language(tree_sitter_python.language())
        with (
            mock.patch.dict(ts_langs._LANGS, {}, clear=True),
            mock.patch.dict(ts_langs._EXT_TO_LANG, {}, clear=True),
            mock.patch.object(ts_langs, "_FAILED", {"pytest"}),
            mock.patch.dict(regex_backend._LANGUAGES, {}, clear=True),
            mock.patch.dict(regex_backend._NAME_TO_KEY, {}, clear=True),
        ):
            ts_langs.load_language(
                "PyTest",
                language,
                "(comment) @comment\n(string) @string\n",
                capture_map={"comment": "operator"},
                extensions=(".PTL",),
            )

            # the failed-load marker is cleared on success
            self.assertEqual(ts_langs._FAILED, set())
            # names/extensions are normalized to lowercase, dot-stripped keys
            self.assertIn("pytest", ts_langs._LANGS)
            self.assertEqual(ts_langs._EXT_TO_LANG["ptl"], "pytest")
            loaded = ts_langs.resolve(".PTL")
            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertIs(loaded, ts_langs._LANGS["pytest"])
            # custom mapping overrides the default, defaults otherwise survive
            self.assertEqual(loaded.capture_map["comment"], "operator")
            self.assertEqual(loaded.capture_map["keyword"], "keyword")
            # tree-sitter serves the extension, while :set filetype sees it
            self.assertTrue(ts_backend.available_for("ptl"))
            self.assertIn("ptl", available_filetypes())
            fallback = regex_backend.lang_for("ptl")
            self.assertIsNotNone(fallback)
            assert fallback is not None
            self.assertEqual(fallback.name, "pytest")


@unittest.skipUnless(has_tree_sitter, "tree_sitter is not installed")
class BuiltinLoadFailureTests(unittest.TestCase):
    """Broken built-in packs degrade to regex instead of raising."""

    def test_missing_pack_returns_none_then_caches_the_failure(self) -> None:
        with (
            mock.patch.dict(ts_langs._LANGS, {}, clear=True),
            mock.patch.object(ts_langs, "_FAILED", set[str]()),
            mock.patch.dict(
                ts_langs.BUILTIN_PACKS,
                {"python": "tree_sitter_pack_missing_xyz"},
            ),
        ):
            self.assertIsNone(ts_langs._load_builtin("python"))
            # resolve() records the failure on first miss ...
            self.assertIsNone(ts_langs.resolve("py"))
            self.assertIn("python", ts_langs._FAILED)
            # ... and does not retry the broken grammar on later calls
            with mock.patch.object(ts_langs, "_load_builtin") as load:
                self.assertIsNone(ts_langs.resolve("py"))
                load.assert_not_called()

    def test_missing_query_file_returns_none(self) -> None:
        with mock.patch.object(
            ts_langs, "QUERIES_DIR", Path("/nonexistent_query_dir_xyz")
        ):
            self.assertIsNone(ts_langs._load_builtin("python"))


class SyntaxBridgeContractTests(unittest.TestCase):
    """``api.syntax.register_tree_sitter`` argument handling.

    The loader itself is mocked so these run without the native dependency;
    the no-dependency error path is covered separately.
    """

    def setUp(self) -> None:
        self.bridge = ext_services.SyntaxExtensionBridge()

    def test_query_source_string_is_passed_through(self) -> None:
        with mock.patch.object(
            ext_services, "load_language_from_grammar"
        ) as loader:
            self.bridge.register_tree_sitter(
                "lg",
                grammar="tree_sitter_lg",
                extensions=["lg"],
                query="(comment) @comment",
                capture_map={"weird.capture": "comment"},
            )
        loader.assert_called_once()
        args, kwargs = loader.call_args
        self.assertEqual(args[0], "lg")
        self.assertEqual(args[1], "tree_sitter_lg")
        self.assertEqual(args[2], "(comment) @comment")
        self.assertEqual(kwargs["extensions"], ("lg",))
        self.assertEqual(kwargs["capture_map"], {"weird.capture": "comment"})

    def test_nonexistent_query_path_is_treated_as_source(self) -> None:
        query = "no/such/dir_xyz/highlights.scm"
        with mock.patch.object(
            ext_services, "load_language_from_grammar"
        ) as loader:
            self.bridge.register_tree_sitter(
                "lg", grammar="tree_sitter_lg", extensions=["lg"], query=query
            )
        self.assertEqual(loader.call_args.args[2], query)

    def test_query_file_path_is_read_before_registration(self) -> None:
        with tempfile.NamedTemporaryFile(
            "w", suffix=".scm", delete=False, encoding="utf-8"
        ) as fh:
            fh.write("(comment) @comment\n")
            query_path = fh.name
        try:
            with mock.patch.object(
                ext_services, "load_language_from_grammar"
            ) as loader:
                self.bridge.register_tree_sitter(
                    "lg",
                    grammar="tree_sitter_lg",
                    extensions=["lg"],
                    query=query_path,
                )
            self.assertEqual(loader.call_args.args[2], "(comment) @comment\n")
        finally:
            Path(query_path).unlink(missing_ok=True)

    def test_runtime_error_propagates_without_tree_sitter(self) -> None:
        with mock.patch.object(ts_langs, "tree_sitter", lambda: None):
            with self.assertRaises(RuntimeError):
                self.bridge.register_tree_sitter(
                    "lg",
                    grammar="tree_sitter_lg",
                    extensions=["lg"],
                    query="(comment) @comment",
                )


if __name__ == "__main__":
    unittest.main()
