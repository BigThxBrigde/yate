"""Headless tests for the syntax highlighting engine and color themes."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

import pytest

from yate.editor_syntax import regex_backend as hl
from yate.editor_view import theme


def _kinds(tokens: list[hl.Token], line: str) -> list[tuple[str, str]]:
    """Flatten tokens to ``(kind, text)`` pairs for readable assertions."""
    return [(t.kind, line[t.start:t.end]) for t in tokens]


# --- Python highlighting ----------------------------------------------------


def test_keywords_and_builtins() -> None:
    toks = hl.tokenize_document(["print(len(x))"], "py")[0]
    pairs = _kinds(toks, "print(len(x))")
    assert ("builtin", "print") in pairs
    assert ("builtin", "len") in pairs


def test_def_and_class_names() -> None:
    toks = hl.tokenize_document(["def foo():", "    pass", "class Bar:"], "py")
    assert ("function", "foo") in _kinds(toks[0], "def foo():")
    assert ("keyword", "def") in _kinds(toks[0], "def foo():")
    assert ("type", "Bar") in _kinds(toks[2], "class Bar:")
    assert ("keyword", "class") in _kinds(toks[2], "class Bar:")


def test_strings_and_numbers() -> None:
    line = 'x = "hello" + 42'
    pairs = _kinds(hl.tokenize_document([line], "py")[0], line)
    assert ("string", '"hello"') in pairs
    assert ("number", "42") in pairs


def test_comment_does_not_swallow_code() -> None:
    line = "x = 1  # set x"
    pairs = _kinds(hl.tokenize_document([line], "py")[0], line)
    assert ("number", "1") in pairs
    assert ("comment", "# set x") in pairs


def test_triple_quoted_string_spans_lines() -> None:
    lines = ['s = """first', 'second line', 'third"""']
    toks = hl.tokenize_document(lines, "py")
    assert [t.kind for t in toks[0]].count("string") == 1
    assert toks[1]
    assert toks[1][0].kind == "string"
    assert any(t.kind == "string" for t in toks[2])


def test_decorator_and_constants() -> None:
    toks = hl.tokenize_document(["@dataclass", "flag = True"], "py")
    assert toks[0][0].kind == "decorator"
    assert ("constant", "True") in _kinds(toks[1], "flag = True")


# --- C-family highlighting --------------------------------------------------


def test_block_comment_spans_lines() -> None:
    toks = hl.tokenize_document(["/* start", "middle", "end */ int x = 1;"], "c")
    assert all(t.kind == "comment" for t in toks[0])
    assert all(t.kind == "comment" for t in toks[1])
    last = _kinds(toks[2], "end */ int x = 1;")
    assert ("type", "int") in last
    assert ("number", "1") in last


def test_line_comment() -> None:
    toks = hl.tokenize_document(["int x; // note"], "c")
    kinds = [t.kind for t in toks[0]]
    assert "comment" in kinds
    assert kinds[-1] == "comment"


def test_rust_macro_and_keywords() -> None:
    line = 'println!("hi");'
    pairs = _kinds(hl.tokenize_document([line], "rs")[0], line)
    assert ("function", "println") in pairs
    assert ("string", '"hi"') in pairs


# --- other languages --------------------------------------------------------


def test_json_keys_vs_values() -> None:
    line = '{"name": "yate", "version": 1}'
    pairs = _kinds(hl.tokenize_document([line], "json")[0], line)
    assert ("property", '"name"') in pairs
    assert ("string", '"yate"') in pairs
    assert ("number", "1") in pairs


def test_markdown_fence_and_heading() -> None:
    lines = ["# Title", "```py", "code = 1", "```"]
    toks = hl.tokenize_document(lines, "md")
    assert toks[0][0].kind == "heading"
    assert all(t.kind == "string" for t in toks[1])
    assert all(t.kind == "string" for t in toks[2])
    assert all(t.kind == "string" for t in toks[3])


def test_toml_sections_and_keys() -> None:
    lines = ["[tool.yate]", 'name = "yate"  # comment', "count = 3"]
    toks = hl.tokenize_document(lines, "toml")
    assert toks[0][0].kind == "keyword"
    pairs1 = _kinds(toks[1], lines[1])
    assert ("property", "name") in pairs1
    assert ("string", '"yate"') in pairs1
    assert ("comment", "# comment") in pairs1


def test_unknown_language_returns_empty() -> None:
    toks = hl.tokenize_document(["anything here ?? 123"], "plaintext")
    assert toks == [[]]
    assert hl.lang_for("xyz") is None


# --- filetype resolution ----------------------------------------------------


def test_extension_keys_pass_through() -> None:
    assert hl.resolve_filetype("py") == "py"
    assert hl.resolve_filetype(".PY") == "py"
    assert hl.resolve_filetype("c++") == "c++"


def test_language_names_map_to_extension_keys() -> None:
    assert hl.resolve_filetype("python") == "py"
    assert hl.resolve_filetype("Python") == "py"
    assert hl.resolve_filetype("typescript") == "ts"
    assert hl.resolve_filetype("javascript") == "js"
    assert hl.resolve_filetype("shell") == "sh"
    # "markdown" is both a language name and a registered extension key
    # (md/markdown/mdx share one spec); either resolution is valid.
    resolved_md = hl.resolve_filetype("markdown")
    assert resolved_md in ("md", "markdown")
    assert resolved_md is not None
    md_spec = hl.lang_for(resolved_md)
    assert md_spec is not None
    assert md_spec.name == "markdown"


def test_unknown_and_empty() -> None:
    assert hl.resolve_filetype("nope") is None
    assert hl.resolve_filetype("") is None
    assert hl.resolve_filetype(".") is None


def test_language_name() -> None:
    assert hl.language_name("py") == "python"
    assert hl.language_name("rs") == "rust"
    assert hl.language_name("nope") is None


def test_available_includes_keys_and_names() -> None:
    available = hl.available_filetypes()
    assert "py" in available
    assert "python" in available
    assert available == sorted(available)


# --- custom language registration ------------------------------------------


@pytest.fixture
def clean_custom_language() -> Iterator[None]:
    """Remove runtime-registered test languages after the test."""
    yield
    registry = cast(Any, hl)
    registry._LANGUAGES.pop("zzxtoy", None)
    registry._NAME_TO_KEY.pop("xtoy", None)


def test_register_language_tokenizes_and_resolves_by_name(
    clean_custom_language: None,
) -> None:
    # "thing" is only in type_def_words (not keywords): the identifier
    # after it must still be painted as a type.
    spec = hl.LangSpec(
        name="xtoy", line_comment="#",
        keywords=frozenset({"xto"}),
        type_def_words=frozenset({"thing"}),
    )
    key = "zzxtoy"  # unique key so the test never clashes with real languages
    hl.register_language(spec, key)
    assert hl.lang_for(key) is spec
    assert hl.resolve_filetype("xtoy") == key
    assert "xtoy" in hl.available_filetypes()

    line = "xto thing Bar 1  # hi"
    pairs = _kinds(hl.tokenize_document([line], key)[0], line)
    assert ("keyword", "xto") in pairs
    assert ("type", "Bar") in pairs
    assert ("number", "1") in pairs
    assert ("comment", "# hi") in pairs


def test_register_overrides_existing_key() -> None:
    registry = cast(Any, hl)
    original = hl.lang_for("py")
    assert original is not None
    replacement = hl.LangSpec(name="pythonish", line_comment=";")
    try:
        hl.register_language(replacement, "py")
        assert hl.lang_for("py") is replacement
    finally:
        hl.register_language(original, "py")
        registry._NAME_TO_KEY.pop("pythonish", None)
    assert hl.lang_for("py") is original


# --- bundled C# extension ---------------------------------------------------


def test_extension_registers_csharp_highlighting() -> None:
    from yate.services.extensions import ExtensionAPI, ExtensionLoader

    class _FakeApp:
        # wired into api.lsp at construction; the highlight bridge never
        # touches the rest of the app.
        lsp: Any = None

    ext_path = (
        Path(__file__).resolve().parent.parent
        / "yate" / "extensions" / "csharp_highlight.py"
    )
    api = ExtensionAPI(cast(Any, _FakeApp()))
    record = ExtensionLoader(api).load_file(ext_path)
    assert record.error is None, record.error or ""

    assert hl.resolve_filetype("csharp") == "cs"
    assert hl.resolve_filetype(".csx") == "csx"
    assert "csharp" in hl.available_filetypes()

    line = "public async Task<string> GetName(int id) { return null; }"
    pairs = _kinds(hl.tokenize_document([line], "cs")[0], line)
    assert ("keyword", "public") in pairs
    assert ("keyword", "async") in pairs
    assert ("type", "Task") in pairs
    assert ("type", "string") in pairs
    assert ("type", "int") in pairs
    assert ("function", "GetName") in pairs
    assert ("constant", "null") in pairs

    # declaration keyword paints the following identifier as a type
    decl = "sealed class Widget { }"
    pairs = _kinds(hl.tokenize_document([decl], "cs")[0], decl)
    assert ("keyword", "class") in pairs
    assert ("type", "Widget") in pairs

    # comments and interpolated/verbatim strings
    mix = 'var s = $@"a{b}"; // ok'
    pairs = _kinds(hl.tokenize_document([mix], "cs")[0], mix)
    assert ("comment", "// ok") in pairs
    assert any(k == "string" for k, _ in pairs)


# --- themes -----------------------------------------------------------------


def test_four_flavors_registered_with_mocha_default() -> None:
    for name in ("latte", "frappe", "macchiato", "mocha"):
        assert name in theme.available()
    assert theme.active().name == "mocha"


def test_set_theme_switches_and_validates() -> None:
    original = theme.active().name
    try:
        assert theme.set_theme("latte").name == "latte"
        assert theme.active().name == "latte"
        assert not theme.active().dark
        with pytest.raises(KeyError):
            theme.set_theme("nope")
    finally:
        theme.set_theme(original)
    assert theme.active().dark


def test_syntax_color_known_and_unknown() -> None:
    t = theme.active()
    assert t.syntax_color("keyword") == t.syn_keyword
    assert t.syntax_color("nonexistent") is None


def test_comment_style_is_italic() -> None:
    style = theme.active().syntax_style("comment")
    assert style.italic
