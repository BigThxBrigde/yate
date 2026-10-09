"""Headless tests for the syntax highlighting engine and color themes."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any, cast

import pytest

from yate.editor_syntax import (
    LangSpec,
    available_filetypes,
    format_filetype_candidates,
    lang_for,
    langdefs as reg,
    language_name,
    register_language,
    regex_backend as hl,
    resolve_filetype,
)
from yate.editor_syntax.tokens import Token
from yate.editor_view import theme


def _kinds(tokens: list[Token], line: str) -> list[tuple[str, str]]:
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
    assert reg.lang_for("xyz") is None


# --- filetype resolution ----------------------------------------------------


def test_extension_keys_pass_through() -> None:
    assert reg.resolve_filetype("py") == "py"
    assert reg.resolve_filetype(".PY") == "py"
    assert reg.resolve_filetype("c++") == "c++"


def test_language_names_map_to_extension_keys() -> None:
    assert reg.resolve_filetype("python") == "py"
    assert reg.resolve_filetype("Python") == "py"
    assert reg.resolve_filetype("typescript") == "ts"
    assert reg.resolve_filetype("javascript") == "js"
    assert reg.resolve_filetype("shell") == "sh"
    # "markdown" is both a language name and a registered extension key
    # (md/markdown/mdx share one spec); either resolution is valid.
    resolved_md = reg.resolve_filetype("markdown")
    assert resolved_md in ("md", "markdown")
    assert resolved_md is not None
    md_spec = reg.lang_for(resolved_md)
    assert md_spec is not None
    assert md_spec.name == "markdown"


def test_unknown_and_empty() -> None:
    assert reg.resolve_filetype("nope") is None
    assert reg.resolve_filetype("") is None
    assert reg.resolve_filetype(".") is None


def test_language_name() -> None:
    assert reg.language_name("py") == "python"
    assert reg.language_name("rs") == "rust"
    assert reg.language_name("nope") is None


def test_available_includes_keys_and_names() -> None:
    available = reg.available_filetypes()
    assert "py" in available
    assert "python" in available
    assert available == sorted(available)


# --- custom language registration ------------------------------------------


@pytest.fixture
def clean_custom_language() -> Iterator[None]:
    """Remove runtime-registered test languages after the test."""
    yield
    registry = cast(Any, reg)
    registry._LANGUAGES.pop("zzxtoy", None)
    registry._NAME_TO_KEY.pop("xtoy", None)


def test_register_language_tokenizes_and_resolves_by_name(
    clean_custom_language: None,
) -> None:
    # "thing" is only in type_def_words (not keywords): the identifier
    # after it must still be painted as a type.
    spec = reg.LangSpec(
        name="xtoy", line_comment="#",
        keywords=frozenset({"xto"}),
        type_def_words=frozenset({"thing"}),
    )
    key = "zzxtoy"  # unique key so the test never clashes with real languages
    reg.register_language(spec, key)
    assert reg.lang_for(key) is spec
    assert reg.resolve_filetype("xtoy") == key
    assert "xtoy" in reg.available_filetypes()

    line = "xto thing Bar 1  # hi"
    pairs = _kinds(hl.tokenize_document([line], key)[0], line)
    assert ("keyword", "xto") in pairs
    assert ("type", "Bar") in pairs
    assert ("number", "1") in pairs
    assert ("comment", "# hi") in pairs


def test_register_overrides_existing_key() -> None:
    registry = cast(Any, reg)
    original = reg.lang_for("py")
    assert original is not None
    replacement = reg.LangSpec(name="pythonish", line_comment=";")
    try:
        reg.register_language(replacement, "py")
        assert reg.lang_for("py") is replacement
    finally:
        reg.register_language(original, "py")
        registry._NAME_TO_KEY.pop("pythonish", None)
    assert reg.lang_for("py") is original


# --- built-in C# (regex fallback of the tree-sitter pack) -------------------


def test_csharp_is_a_builtin_language() -> None:
    # csharp_highlight.py was removed: the language is registered by the
    # built-in regex table (and served by tree-sitter when installed).
    assert reg.resolve_filetype("csharp") == "cs"
    assert reg.resolve_filetype(".csx") == "csx"
    assert "csharp" in reg.available_filetypes()


def test_csharp_regex_highlighting() -> None:
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


# --- regex fallbacks for the issue-IKJLTB languages -------------------------


def test_html_tags_and_comment() -> None:
    lines = ["<!-- note -->", '<div class="x">hi</div>']
    toks = hl.tokenize_document(lines, "html")
    assert toks[0]
    assert all(t.kind == "comment" for t in toks[0])
    pairs = _kinds(toks[1], lines[1])
    assert ("type", "div") in pairs
    assert ("string", '"x"') in pairs


def test_css_properties_and_colors() -> None:
    lines = ["/* note */", "div {", "    color: red;"]
    toks = hl.tokenize_document(lines, "css")
    assert toks[0]
    assert all(t.kind == "comment" for t in toks[0])
    assert ("type", "div") in _kinds(toks[1], lines[1])
    pairs = _kinds(toks[2], lines[2])
    assert ("builtin", "color") in pairs
    assert ("constant", "red") in pairs


def test_powershell_keywords_and_sigils() -> None:
    lines = ["# note", "if ($env:Path) {", "    $name = 'x'"]
    toks = hl.tokenize_document(lines, "ps1")
    assert ("comment", "# note") in _kinds(toks[0], lines[0])
    assert ("keyword", "if") in _kinds(toks[1], lines[1])
    pairs = _kinds(toks[2], lines[2])
    assert ("property", "$name") in pairs
    assert ("string", "'x'") in pairs


def test_lua_keywords_and_comment() -> None:
    lines = ["-- note", "local function f()", '    print("x")']
    toks = hl.tokenize_document(lines, "lua")
    assert ("comment", "-- note") in _kinds(toks[0], lines[0])
    assert ("keyword", "local") in _kinds(toks[1], lines[1])
    assert ("function", "f") in _kinds(toks[1], lines[1])
    pairs = _kinds(toks[2], lines[2])
    assert ("builtin", "print") in pairs
    assert ("string", '"x"') in pairs


def test_make_keywords_and_comment() -> None:
    lines = ["# note", "ifeq ($(OS), Windows_NT)"]
    toks = hl.tokenize_document(lines, "mak")
    assert ("comment", "# note") in _kinds(toks[0], lines[0])
    assert ("keyword", "ifeq") in _kinds(toks[1], lines[1])


def test_xml_comment_and_string() -> None:
    lines = ["<!-- note -->", '<root attr="1">x</root>']
    toks = hl.tokenize_document(lines, "xml")
    assert toks[0]
    assert all(t.kind == "comment" for t in toks[0])
    assert ("string", '"1"') in _kinds(toks[1], lines[1])


def test_xaml_comment_and_string() -> None:
    lines = ["<!-- note -->", '<Grid Text="hi">x</Grid>']
    toks = hl.tokenize_document(lines, "xaml")
    assert toks[0]
    assert all(t.kind == "comment" for t in toks[0])
    assert ("string", '"hi"') in _kinds(toks[1], lines[1])
    # The XAML vocabulary: without it the fallback only ever paints comments
    # and attribute values.
    assert ("type", "Grid") in _kinds(toks[1], lines[1])


def test_perl_sub_names_the_function() -> None:
    # `sub foo {` -- 'foo' is followed by a space, not '(', so only
    # func_def_words can color it.
    line = "sub foo {"
    assert ("keyword", "sub") in _kinds(hl.tokenize_document([line], "pl")[0], line)
    assert ("function", "foo") in _kinds(hl.tokenize_document([line], "pl")[0], line)


def test_perl_library_functions_are_builtins_not_keywords() -> None:
    # Same classification convention as _PY_BUILTINS / _GO_BUILTINS.
    line = "print 'x';"
    assert ("builtin", "print") in _kinds(hl.tokenize_document([line], "pl")[0], line)


def test_at_sigil_is_a_variable_where_the_language_says_so() -> None:
    for filetype, line, text in (
        ("pl", "push @items;", "@items"),
        ("rb", "@ivar = 1", "@ivar"),
        ("ps1", "Write-Output @rest", "@rest"),
    ):
        assert ("property", text) in _kinds(
            hl.tokenize_document([line], filetype)[0], line
        ), filetype
    # ... while python keeps @ as a decorator.
    line = "@dataclass"
    assert ("decorator", "@dataclass") in _kinds(
        hl.tokenize_document([line], "py")[0], line
    )


def test_make_expands_parenthesised_variables() -> None:
    # Makefile variables are $(VAR) / $@ / $<, not $VAR.
    line = "all: $(OS)"
    assert ("property", "$(OS)") in _kinds(hl.tokenize_document([line], "mak")[0], line)
    # '-include' was unreachable: _IDENT_RE has no '-', so it could never match.
    spec = reg.lang_for("mak")
    assert spec is not None
    assert "include" in spec.keywords
    assert "-include" not in spec.keywords


def test_css_scans_hyphenated_properties_as_one_identifier() -> None:
    line = "font-size: 12px;"
    pairs = _kinds(hl.tokenize_document([line], "css")[0], line)
    assert ("builtin", "font-size") in pairs
    # The value still scans: the dashed pattern only joins letter-led segments.
    assert ("number", "12") in pairs
    assert ("operator", ":") in pairs


def test_css_dashed_lookup_falls_back_to_its_base_word() -> None:
    # Capturing the whole word must not lose what the fragment scan colored:
    # a vendor prefix or a custom property still shows its base name.
    for line, base in (
        ("-webkit-transform: none;", "transform"),
        ("-ms-grid-row: 1;", "grid"),
        ("--brand-color: red;", "color"),
        ("color: var(--brand-color);", "color"),
    ):
        pairs = _kinds(hl.tokenize_document([line], "css")[0], line)
        # The base word is colored, whether the token spans the whole dashed
        # name or just the part of it that carries the meaning.
        assert any(
            kind == "builtin" and base in text for kind, text in pairs
        ), line
    # A dashed word whose segments are all unknown stays uncolored, and one
    # that merely contains a tag or property name ('.nav-item', '.border-x')
    # must not be painted as that tag either: a class selector is not a
    # property name.  Substring semantics, so a token claiming the whole class
    # name as a word-list hit is caught however it is split.
    for name in (
        "btn-primary", "text-muted", "nav-item", "main-content",
        "form-control", "section-header", "code-block", "link-button",
        "a-b", "my-custom-prop", "border-x", "flex-center", "no-div-here",
        "my-a-thing",
    ):
        line = f".{name} {{ color: red; }}"
        pairs = _kinds(hl.tokenize_document([line], "css")[0], line)
        for kind in ("type", "builtin", "constant", "keyword"):
            assert not any(
                k == kind and name in text for k, text in pairs
            ), f"{name} painted as {kind}"
        # Whatever it is, 'red' after the colon still gets its own color.
        assert ("constant", "red") in pairs, name
    # A member access keeps the pre-existing property coloring -- the same one
    # a plain '.foo' has always had, not something this fallback introduced.
    assert ("property", "nav-item") in _kinds(
        hl.tokenize_document([".nav-item { color: red; }"], "css")[0],
        ".nav-item { color: red; }",
    )
    # '.border' (and '.border-', whose trailing dash leaves a bare 'border'
    # token) keeps the color the built-in CSS word lists always gave it: the
    # plain whole-word lookup runs before the selector rules, and that predates
    # hyphenated_idents.
    assert ("builtin", "border") in _kinds(
        hl.tokenize_document([".border { color: red; }"], "css")[0],
        ".border { color: red; }",
    )


def test_paren_vars_works_without_the_sigils_switch() -> None:
    # The two switches are independent: paren_vars alone must not silently
    # drop every $(...) it matched.
    spec = reg.LangSpec(name="parenonly", mode="code", paren_vars=True)
    registry = cast(Any, reg)
    try:
        reg.register_language(spec, "zzparenonly")
        line = "x = $(VAR) y"
        assert ("property", "$(VAR)") in _kinds(
            hl.tokenize_document([line], "zzparenonly")[0], line
        )
    finally:
        registry._LANGUAGES.pop("zzparenonly", None)
        registry._NAME_TO_KEY.pop("parenonly", None)


def test_paren_vars_tolerates_one_level_of_nesting() -> None:
    line = "a = $(shell echo $(X))"
    pairs = _kinds(hl.tokenize_document([line], "mak")[0], line)
    assert ("property", "$(shell echo $(X))") in pairs


def test_ruby_library_methods_are_builtins_not_keywords() -> None:
    # keywords win over builtins, so a word in both tables is dead data.
    for word in ("require", "include", "attr_accessor"):
        line = f"{word} 'x'"
        assert ("builtin", word) in _kinds(
            hl.tokenize_document([line], "rb")[0], line
        ), word
    # 'each' is not a ruby keyword at all -- it must not end up colorless.
    assert ("builtin", "each") in _kinds(
        hl.tokenize_document(["[1, 2].each { }"], "rb")[0], "[1, 2].each { }"
    )


def test_langspec_word_tables_have_no_unreachable_entries() -> None:
    # keywords win over types, and types over builtins, so a word in both
    # tables makes the weaker entry dead weight.
    for spec in (
        reg.lang_for("lua"), reg.lang_for("ps1"), reg.lang_for("php"),
        reg.lang_for("pl"), reg.lang_for("rb"),
    ):
        assert spec is not None
        assert not spec.types & spec.keywords
        assert not spec.types & spec.builtins
        assert not spec.builtins & spec.keywords


def test_scss_and_less_reuse_the_css_word_lists() -> None:
    for filetype in ("scss", "less"):
        spec = reg.lang_for(filetype)
        assert spec is not None
        assert spec.name == filetype          # own name -> no ts grammar lookup
        assert spec.hyphenated_idents
    line = "a { color: red; }"
    for filetype in ("scss", "less"):
        pairs = _kinds(hl.tokenize_document([line], filetype)[0], line)
        assert ("type", "a") in pairs or ("builtin", "color") in pairs


def test_filetype_candidate_list_is_truncated_with_a_total() -> None:
    # The registry outgrew the message width; an untruncated join silently lost
    # everything past the wrap column.
    shown = reg.format_filetype_candidates()
    total = len(reg.available_filetypes())
    head = shown.split(", ...")[0]
    assert shown.endswith(f"... ({total} total)")
    assert head == ", ".join(reg.available_filetypes()[:12])
    assert reg.format_filetype_candidates(limit=4).startswith(
        ", ".join(reg.available_filetypes()[:4])
    )
    # A zero limit would render ", ... (72 total)" with an empty head.
    assert reg.format_filetype_candidates(limit=0).startswith(
        reg.available_filetypes()[0]
    )


def test_perl_keywords_and_sigils() -> None:
    line = "my $name = 'x';"
    pairs = _kinds(hl.tokenize_document([line], "pl")[0], line)
    assert ("keyword", "my") in pairs
    assert ("property", "$name") in pairs
    assert ("string", "'x'") in pairs


def test_perl_line_comment() -> None:
    assert ("comment", "# note") in _kinds(
        hl.tokenize_document(["# note"], "pl")[0], "# note"
    )


def test_php_keywords_and_function() -> None:
    lines = ["// note", "function f() {", "    return true;"]
    toks = hl.tokenize_document(lines, "php")
    assert ("comment", "// note") in _kinds(toks[0], lines[0])
    assert ("keyword", "function") in _kinds(toks[1], lines[1])
    assert ("function", "f") in _kinds(toks[1], lines[1])
    assert ("constant", "true") in _kinds(toks[2], lines[2])


def test_ruby_keywords_and_comment() -> None:
    lines = ["# note", "def f", "  puts 'x'", "end"]
    toks = hl.tokenize_document(lines, "rb")
    assert ("comment", "# note") in _kinds(toks[0], lines[0])
    assert ("keyword", "def") in _kinds(toks[1], lines[1])
    assert ("function", "f") in _kinds(toks[1], lines[1])
    assert ("string", "'x'") in _kinds(toks[2], lines[2])
    assert ("keyword", "end") in _kinds(toks[3], lines[3])


def test_sql_keywords_are_case_insensitive() -> None:
    lines = ["-- note", "select * from t where x = 1;", "SELECT COUNT(*) FROM t"]
    toks = hl.tokenize_document(lines, "sql")
    assert ("comment", "-- note") in _kinds(toks[0], lines[0])
    pairs = _kinds(toks[1], lines[1])
    assert ("keyword", "select") in pairs
    assert ("keyword", "from") in pairs
    assert ("keyword", "where") in pairs
    # The upper half only passes because the registry expands every word list
    # with its upper-case spelling -- drop that expansion and this goes red.
    upper = _kinds(toks[2], lines[2])
    assert ("keyword", "SELECT") in upper
    assert ("keyword", "FROM") in upper
    assert ("builtin", "COUNT") in upper


def test_zig_keywords_and_types() -> None:
    line = "pub fn main() void {"
    pairs = _kinds(hl.tokenize_document([line], "zig")[0], line)
    assert ("keyword", "pub") in pairs
    assert ("keyword", "fn") in pairs
    assert ("function", "main") in pairs
    assert ("type", "void") in pairs


# --- pattern caching & config boolean constants -----------------------------


def test_code_line_pattern_is_cached_per_spec() -> None:
    spec = reg.lang_for("py")
    assert spec is not None
    registry = cast(Any, hl)
    assert registry._code_line_pattern(spec) is registry._code_line_pattern(spec)


def test_config_bool_words_match_on_word_boundaries_only() -> None:
    line = "a = on b = off c = yes d = no e = only"
    toks = hl.tokenize_document([line], "toml")[0]
    pairs = _kinds(toks, line)
    assert ("constant", "on") in pairs
    assert ("constant", "off") in pairs
    assert ("constant", "yes") in pairs
    assert ("constant", "no") in pairs
    # "only" must not contribute a partial-word constant (its "on" prefix)
    only_start = line.index("only")
    only_end = only_start + len("only")
    for t in toks:
        if t.kind == "constant":
            assert t.end <= only_start or t.start >= only_end


def test_config_bool_word_does_not_match_inside_true1() -> None:
    line = "flag1 = true1"
    toks = hl.tokenize_document([line], "toml")[0]
    assert all(kind != "constant" for kind, _ in _kinds(toks, line))
    # no double coloring: token spans stay sorted and disjoint
    spans = [(t.start, t.end) for t in toks]
    assert spans == sorted(spans)
    assert all(a[1] <= b[0] for a, b in zip(spans, spans[1:]))


def test_config_number_inside_string_is_not_double_colored() -> None:
    line = 'port = "8080"'
    toks = hl.tokenize_document([line], "toml")[0]
    assert ("string", '"8080"') in _kinds(toks, line)
    assert [t.kind for t in toks] == ["property", "string"]


def test_config_bool_word_inside_string_is_not_double_colored() -> None:
    line = 'mode = "on"'
    toks = hl.tokenize_document([line], "toml")[0]
    assert ("string", '"on"') in _kinds(toks, line)
    assert [t.kind for t in toks] == ["property", "string"]


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


# --- package-root re-export identity -----------------------------------------


def test_package_root_reexports_bind_langdefs_objects() -> None:
    # The leaf-package exception re-exports the registry at the package root;
    # each symbol must stay bound to the very object langdefs owns, not a
    # copy or a symbol re-pointed at some intermediate layer.
    assert LangSpec is reg.LangSpec
    assert lang_for is reg.lang_for
    assert register_language is reg.register_language
    assert resolve_filetype is reg.resolve_filetype
    assert language_name is reg.language_name
    assert available_filetypes is reg.available_filetypes
    assert format_filetype_candidates is reg.format_filetype_candidates
