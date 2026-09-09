"""Headless tests for the syntax highlighting engine and color themes."""

from __future__ import annotations

import unittest

from yate.editor_view import highlight as hl
from yate.editor_view import theme


def _kinds(tokens: list[hl.Token], line: str) -> list[tuple[str, str]]:
    """Flatten tokens to ``(kind, text)`` pairs for readable assertions."""
    return [(t.kind, line[t.start:t.end]) for t in tokens]


class PythonHighlightTests(unittest.TestCase):
    """Python keyword / string / comment / definition coloring."""

    def test_keywords_and_builtins(self) -> None:
        toks = hl.tokenize_document(["print(len(x))"], "py")[0]
        pairs = _kinds(toks, "print(len(x))")
        self.assertIn(("builtin", "print"), pairs)
        self.assertIn(("builtin", "len"), pairs)

    def test_def_and_class_names(self) -> None:
        toks = hl.tokenize_document(["def foo():", "    pass", "class Bar:"], "py")
        self.assertIn(("function", "foo"), _kinds(toks[0], "def foo():"))
        self.assertIn(("keyword", "def"), _kinds(toks[0], "def foo():"))
        self.assertIn(("type", "Bar"), _kinds(toks[2], "class Bar:"))
        self.assertIn(("keyword", "class"), _kinds(toks[2], "class Bar:"))

    def test_strings_and_numbers(self) -> None:
        line = 'x = "hello" + 42'
        pairs = _kinds(hl.tokenize_document([line], "py")[0], line)
        self.assertIn(("string", '"hello"'), pairs)
        self.assertIn(("number", "42"), pairs)

    def test_comment_does_not_swallow_code(self) -> None:
        line = "x = 1  # set x"
        pairs = _kinds(hl.tokenize_document([line], "py")[0], line)
        self.assertIn(("number", "1"), pairs)
        self.assertIn(("comment", "# set x"), pairs)

    def test_triple_quoted_string_spans_lines(self) -> None:
        lines = ['s = """first', 'second line', 'third"""']
        toks = hl.tokenize_document(lines, "py")
        self.assertEqual([t.kind for t in toks[0]].count("string"), 1)
        self.assertTrue(toks[1])
        self.assertEqual(toks[1][0].kind, "string")
        self.assertTrue(any(t.kind == "string" for t in toks[2]))

    def test_decorator_and_constants(self) -> None:
        toks = hl.tokenize_document(["@dataclass", "flag = True"], "py")
        self.assertEqual(toks[0][0].kind, "decorator")
        self.assertIn(("constant", "True"), _kinds(toks[1], "flag = True"))


class CLikeHighlightTests(unittest.TestCase):
    """Block comments and C-family keywords."""

    def test_block_comment_spans_lines(self) -> None:
        toks = hl.tokenize_document(["/* start", "middle", "end */ int x = 1;"], "c")
        self.assertTrue(all(t.kind == "comment" for t in toks[0]))
        self.assertTrue(all(t.kind == "comment" for t in toks[1]))
        last = _kinds(toks[2], "end */ int x = 1;")
        self.assertIn(("type", "int"), last)
        self.assertIn(("number", "1"), last)

    def test_line_comment(self) -> None:
        toks = hl.tokenize_document(["int x; // note"], "c")
        kinds = [t.kind for t in toks[0]]
        self.assertIn("comment", kinds)
        self.assertEqual(kinds[-1], "comment")

    def test_rust_macro_and_keywords(self) -> None:
        line = 'println!("hi");'
        pairs = _kinds(hl.tokenize_document([line], "rs")[0], line)
        self.assertIn(("function", "println"), pairs)
        self.assertIn(("string", '"hi"'), pairs)


class OtherLanguagesTests(unittest.TestCase):
    """JSON / Markdown / config file highlighting."""

    def test_json_keys_vs_values(self) -> None:
        line = '{"name": "yate", "version": 1}'
        pairs = _kinds(hl.tokenize_document([line], "json")[0], line)
        self.assertIn(("property", '"name"'), pairs)
        self.assertIn(("string", '"yate"'), pairs)
        self.assertIn(("number", "1"), pairs)

    def test_markdown_fence_and_heading(self) -> None:
        lines = ["# Title", "```py", "code = 1", "```"]
        toks = hl.tokenize_document(lines, "md")
        self.assertEqual(toks[0][0].kind, "heading")
        self.assertTrue(all(t.kind == "string" for t in toks[1]))
        self.assertTrue(all(t.kind == "string" for t in toks[2]))
        self.assertTrue(all(t.kind == "string" for t in toks[3]))

    def test_toml_sections_and_keys(self) -> None:
        lines = ["[tool.yate]", 'name = "yate"  # comment', "count = 3"]
        toks = hl.tokenize_document(lines, "toml")
        self.assertEqual(toks[0][0].kind, "keyword")
        pairs1 = _kinds(toks[1], lines[1])
        self.assertIn(("property", "name"), pairs1)
        self.assertIn(("string", '"yate"'), pairs1)
        self.assertIn(("comment", "# comment"), pairs1)

    def test_unknown_language_returns_empty(self) -> None:
        toks = hl.tokenize_document(["anything here ?? 123"], "plaintext")
        self.assertEqual(toks, [[]])
        self.assertIsNone(hl.lang_for("xyz"))


class ThemeTests(unittest.TestCase):
    """Catppuccin theme registry and syntax color mapping."""

    def test_four_flavors_registered_with_mocha_default(self) -> None:
        for name in ("latte", "frappe", "macchiato", "mocha"):
            self.assertIn(name, theme.available())
        self.assertEqual(theme.active().name, "mocha")

    def test_set_theme_switches_and_validates(self) -> None:
        original = theme.active().name
        try:
            self.assertEqual(theme.set_theme("latte").name, "latte")
            self.assertEqual(theme.active().name, "latte")
            self.assertFalse(theme.active().dark)
            with self.assertRaises(KeyError):
                theme.set_theme("nope")
        finally:
            theme.set_theme(original)
        self.assertTrue(theme.active().dark)

    def test_syntax_color_known_and_unknown(self) -> None:
        t = theme.active()
        self.assertEqual(t.syntax_color("keyword"), t.syn_keyword)
        self.assertIsNone(t.syntax_color("nonexistent"))

    def test_comment_style_is_italic(self) -> None:
        style = theme.active().syntax_style("comment")
        self.assertTrue(style.italic)


if __name__ == "__main__":
    unittest.main()
