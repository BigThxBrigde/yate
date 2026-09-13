"""Headless tests for the syntax highlighting engine and color themes."""

from __future__ import annotations

import unittest
from pathlib import Path
from typing import Any, cast

from yate.editor_syntax import regex_backend as hl
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


class FiletypeResolutionTests(unittest.TestCase):
    """resolve_filetype / language_name / available_filetypes."""

    def test_extension_keys_pass_through(self) -> None:
        self.assertEqual(hl.resolve_filetype("py"), "py")
        self.assertEqual(hl.resolve_filetype(".PY"), "py")
        self.assertEqual(hl.resolve_filetype("c++"), "c++")

    def test_language_names_map_to_extension_keys(self) -> None:
        self.assertEqual(hl.resolve_filetype("python"), "py")
        self.assertEqual(hl.resolve_filetype("Python"), "py")
        self.assertEqual(hl.resolve_filetype("typescript"), "ts")
        self.assertEqual(hl.resolve_filetype("javascript"), "js")
        self.assertEqual(hl.resolve_filetype("shell"), "sh")
        # "markdown" is both a language name and a registered extension key
        # (md/markdown/mdx share one spec); either resolution is valid.
        resolved_md = hl.resolve_filetype("markdown")
        self.assertIn(resolved_md, ("md", "markdown"))
        assert resolved_md is not None
        md_spec = hl.lang_for(resolved_md)
        assert md_spec is not None
        self.assertEqual(md_spec.name, "markdown")

    def test_unknown_and_empty(self) -> None:
        self.assertIsNone(hl.resolve_filetype("nope"))
        self.assertIsNone(hl.resolve_filetype(""))
        self.assertIsNone(hl.resolve_filetype("."))

    def test_language_name(self) -> None:
        self.assertEqual(hl.language_name("py"), "python")
        self.assertEqual(hl.language_name("rs"), "rust")
        self.assertIsNone(hl.language_name("nope"))

    def test_available_includes_keys_and_names(self) -> None:
        available = hl.available_filetypes()
        self.assertIn("py", available)
        self.assertIn("python", available)
        self.assertEqual(available, sorted(available))


class CustomLanguageRegistrationTests(unittest.TestCase):
    """Extensions can register (or override) languages at runtime."""

    KEY = "zzxtoy"  # unique key so the test never clashes with real languages

    def tearDown(self) -> None:
        registry = cast(Any, hl)
        registry._LANGUAGES.pop(self.KEY, None)
        registry._NAME_TO_KEY.pop("xtoy", None)

    def test_register_language_tokenizes_and_resolves_by_name(self) -> None:
        # "thing" is only in type_def_words (not keywords): the identifier
        # after it must still be painted as a type.
        spec = hl.LangSpec(
            name="xtoy", line_comment="#",
            keywords=frozenset({"xto"}),
            type_def_words=frozenset({"thing"}),
        )
        hl.register_language(spec, self.KEY)
        self.assertIs(hl.lang_for(self.KEY), spec)
        self.assertEqual(hl.resolve_filetype("xtoy"), self.KEY)
        self.assertIn("xtoy", hl.available_filetypes())

        line = "xto thing Bar 1  # hi"
        pairs = _kinds(hl.tokenize_document([line], self.KEY)[0], line)
        self.assertIn(("keyword", "xto"), pairs)
        self.assertIn(("type", "Bar"), pairs)
        self.assertIn(("number", "1"), pairs)
        self.assertIn(("comment", "# hi"), pairs)

    def test_register_overrides_existing_key(self) -> None:
        registry = cast(Any, hl)
        original = hl.lang_for("py")
        assert original is not None
        replacement = hl.LangSpec(name="pythonish", line_comment=";")
        try:
            hl.register_language(replacement, "py")
            self.assertIs(hl.lang_for("py"), replacement)
        finally:
            hl.register_language(original, "py")
            registry._NAME_TO_KEY.pop("pythonish", None)
        self.assertIs(hl.lang_for("py"), original)


class CSharpExtensionTests(unittest.TestCase):
    """Load the bundled yate/extensions/csharp_highlight.py via the real loader."""

    EXT_PATH = (
        Path(__file__).resolve().parent.parent
        / "yate" / "extensions" / "csharp_highlight.py"
    )

    def test_extension_registers_csharp_highlighting(self) -> None:
        from yate.services.extensions import ExtensionAPI, ExtensionLoader

        class _FakeApp:
            pass  # the highlight bridge never touches the app

        api = ExtensionAPI(cast(Any, _FakeApp()))
        record = ExtensionLoader(api).load_file(self.EXT_PATH)
        self.assertIsNone(record.error, msg=record.error or "")

        self.assertEqual(hl.resolve_filetype("csharp"), "cs")
        self.assertEqual(hl.resolve_filetype(".csx"), "csx")
        self.assertIn("csharp", hl.available_filetypes())

        line = "public async Task<string> GetName(int id) { return null; }"
        pairs = _kinds(hl.tokenize_document([line], "cs")[0], line)
        self.assertIn(("keyword", "public"), pairs)
        self.assertIn(("keyword", "async"), pairs)
        self.assertIn(("type", "Task"), pairs)
        self.assertIn(("type", "string"), pairs)
        self.assertIn(("type", "int"), pairs)
        self.assertIn(("function", "GetName"), pairs)
        self.assertIn(("constant", "null"), pairs)

        # declaration keyword paints the following identifier as a type
        decl = "sealed class Widget { }"
        pairs = _kinds(hl.tokenize_document([decl], "cs")[0], decl)
        self.assertIn(("keyword", "class"), pairs)
        self.assertIn(("type", "Widget"), pairs)

        # comments and interpolated/verbatim strings
        mix = 'var s = $@"a{b}"; // ok'
        pairs = _kinds(hl.tokenize_document([mix], "cs")[0], mix)
        self.assertIn(("comment", "// ok"), pairs)
        self.assertTrue(any(k == "string" for k, _ in pairs))


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
