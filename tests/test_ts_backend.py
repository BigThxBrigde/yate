"""Tests for the optional tree-sitter backend (skipped without the deps).

The backend itself degrades gracefully when ``tree_sitter`` is missing
(covered by the engine dispatch tests); the tests here only run when the
optional grammar packs are installed.
"""

# pyright: reportPrivateUsage=false

from __future__ import annotations

import importlib.util
import re
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from unittest import mock

import pytest

from yate.editor_syntax import available_filetypes, engine, regex_backend, ts_backend
from yate.editor_syntax.tokens import SYNTAX_KINDS, Token
from yate.editor_syntax.ts_backend import backend as ts_runtime
from yate.editor_syntax.ts_backend import languages as ts_langs
from yate.services import extensions as ext_services

has_bash = importlib.util.find_spec("tree_sitter_bash") is not None
has_python = importlib.util.find_spec("tree_sitter_python") is not None
has_tree_sitter = ts_langs.ts_available()

_python_skip = pytest.mark.skipif(
    not has_python, reason="tree_sitter_python is not installed"
)
_bash_skip = pytest.mark.skipif(
    not has_bash, reason="tree_sitter_bash is not installed"
)
_ts_skip = pytest.mark.skipif(
    not has_tree_sitter, reason="tree_sitter is not installed"
)


def _kinds(tokens: list[Token], line: str) -> list[tuple[str, str]]:
    """Flatten tokens to ``(kind, text)`` pairs for readable assertions."""
    return [(t.kind, line[t.start:t.end]) for t in tokens]


# --- python grammar ---------------------------------------------------------


@_python_skip
def test_keywords_numbers_strings() -> None:
    lines = ["# note", "def foo():", "    return 42", 'x = "s"']
    toks = ts_backend.tokenize_document(lines, "py")
    assert ("comment", "# note") in _kinds(toks[0], lines[0])
    assert ("keyword", "def") in _kinds(toks[1], lines[1])
    assert ("function", "foo") in _kinds(toks[1], lines[1])
    assert ("keyword", "return") in _kinds(toks[2], lines[2])
    assert ("number", "42") in _kinds(toks[2], lines[2])
    assert ("string", '"s"') in _kinds(toks[3], lines[3])


@_python_skip
def test_class_and_decorator_and_call() -> None:
    lines = ["class Bar:", "    pass", "@dec", "print(foo())"]
    toks = ts_backend.tokenize_document(lines, "py")
    assert ("type", "Bar") in _kinds(toks[0], lines[0])
    assert ("decorator", "@dec") in _kinds(toks[2], lines[2])
    kinds3 = _kinds(toks[3], lines[3])
    assert ("function", "print") in kinds3
    assert ("function", "foo") in kinds3


@_python_skip
def test_multiline_triple_string() -> None:
    lines = ["x = (", '    """', "    doc", '    """', ")"]
    toks = ts_backend.tokenize_document(lines, "py")
    # opening row: only the quotes are inside the string
    assert _kinds(toks[1], lines[1]) == [("string", '"""')]
    # middle and closing rows are entirely string content
    assert _kinds(toks[2], lines[2]) == [("string", "    doc")]
    assert _kinds(toks[3], lines[3]) == [("string", '    """')]
    assert toks[4] == []


@_python_skip
def test_unicode_columns_are_character_based() -> None:
    line = 'x = "é" + 1  # cömment'
    toks = ts_backend.tokenize_document([line], "py")
    pairs = _kinds(toks[0], line)
    assert ("number", "1") in pairs
    assert ("comment", "# cömment") in pairs


@_python_skip
def test_unknown_filetype_is_plain() -> None:
    assert ts_backend.tokenize_document(["x"], "nope") == [[]]


# --- shell grammar ----------------------------------------------------------


@_bash_skip
def test_comments_keywords_strings_commands() -> None:
    lines = [
        "# run",
        'echo "hello" $HOME',
        "if [ -f x ]; then ls; fi",
    ]
    toks = ts_backend.tokenize_document(lines, "sh")
    assert ("comment", "# run") in _kinds(toks[0], lines[0])
    pairs1 = _kinds(toks[1], lines[1])
    assert ("function", "echo") in pairs1
    assert ("string", '"hello"') in pairs1
    pairs2 = _kinds(toks[2], lines[2])
    assert ("keyword", "if") in pairs2
    assert ("keyword", "then") in pairs2
    assert ("function", "ls") in pairs2
    assert ("keyword", "fi") in pairs2


# --- built-in grammar packs -------------------------------------------------


@dataclass
class _PackCase:
    """One representative highlighting sample for a built-in grammar pack."""

    pack: str  # key in BUILTIN_PACKS
    filetype: str
    lines: list[str]
    expected: tuple[tuple[int, str, str], ...]  # (row, kind, text)


_PACK_CASES: list[_PackCase] = [
    _PackCase(
        "csharp", "cs",
        ["// note", "public class Foo {", '    string s = "x";'],
        (
            (0, "comment", "// note"),
            (1, "keyword", "public"), (1, "keyword", "class"),
            (2, "type", "string"), (2, "string", '"x"'),
        ),
    ),
    _PackCase(
        "rust", "rs",
        ["// note", "fn main() {", '    let s = "x";', "}"],
        (
            (0, "comment", "// note"),
            (1, "keyword", "fn"),
            (2, "keyword", "let"), (2, "string", '"x"'),
        ),
    ),
    _PackCase(
        "javascript", "js",
        ["// note", "function f() {", '    const s = "x";', "}"],
        (
            (0, "comment", "// note"),
            (1, "keyword", "function"),
            (2, "keyword", "const"), (2, "string", '"x"'),
        ),
    ),
    _PackCase(
        "typescript", "ts",
        ["// note", "const n: number = 1;"],
        (
            (0, "comment", "// note"),
            (1, "keyword", "const"), (1, "type", "number"),
            (1, "number", "1"),
        ),
    ),
    _PackCase(
        "c", "c",
        ["// note", "int main(void) {", "    return 0;"],
        (
            (0, "comment", "// note"),
            (1, "type", "int"), (1, "function", "main"), (1, "type", "void"),
            (2, "keyword", "return"), (2, "number", "0"),
        ),
    ),
    _PackCase(
        "cpp", "cpp",
        ["// note", "class Foo {", "};"],
        (
            (0, "comment", "// note"),
            (1, "keyword", "class"), (1, "type", "Foo"),
        ),
    ),
    _PackCase(
        "go", "go",
        ["// note", "func main() {", '    s := "x"'],
        (
            (0, "comment", "// note"),
            (1, "keyword", "func"), (1, "function", "main"),
            (2, "string", '"x"'),
        ),
    ),
    _PackCase(
        "java", "java",
        ["// note", "class Foo {", "    void f() {}"],
        (
            (0, "comment", "// note"),
            (1, "keyword", "class"), (1, "type", "Foo"),
            (2, "type", "void"), (2, "function", "f"),
        ),
    ),
    _PackCase(
        "html", "html",
        ["<!-- note -->", '<div class="x">hi</div>'],
        (
            (0, "comment", "<!-- note -->"),
            (1, "type", "div"), (1, "string", '"x"'),
        ),
    ),
    _PackCase(
        "css", "css",
        ["/* note */", "div {", "    color: red;"],
        (
            (0, "comment", "/* note */"),
            (1, "type", "div"),
            (2, "property", "color"),
        ),
    ),
    _PackCase(
        "json", "json",
        ['{"k": 1, "s": "v"}'],
        (
            (0, "property", '"k"'), (0, "number", "1"),
            (0, "property", '"s"'), (0, "string", '"v"'),
        ),
    ),
    _PackCase(
        "toml", "toml",
        ['name = "yate" # note'],
        (
            (0, "property", "name"), (0, "string", '"yate"'),
            (0, "comment", "# note"),
        ),
    ),
    _PackCase(
        "yaml", "yaml",
        ["# note", "key: value"],
        ((0, "comment", "# note"), (1, "property", "key")),
    ),
    _PackCase(
        "sql", "sql",
        ["-- note", "select * from t where x = 1;"],
        (
            (0, "comment", "-- note"),
            (1, "keyword", "select"), (1, "keyword", "from"),
            (1, "keyword", "where"),
        ),
    ),
    _PackCase(
        "lua", "lua",
        ["-- note", "local function f()", '    print("x")', "end"],
        (
            (0, "comment", "-- note"),
            (1, "keyword", "local"), (1, "keyword", "function"),
            (2, "string", '"x"'),
        ),
    ),
    _PackCase(
        "make", "mak",
        ["# note", "all: build"],
        ((0, "comment", "# note"), (1, "function", "all")),
    ),
    _PackCase(
        "powershell", "ps1",
        ["# note", "if ($true) {", '    Write-Output "x"'],
        (
            (0, "comment", "# note"),
            (1, "keyword", "if"),
            (2, "function", "Write-Output"), (2, "string", '"x"'),
        ),
    ),
    _PackCase(
        "php", "php",
        ["<?php", "// note", "function f() {}"],
        (
            (1, "comment", "// note"),
            (2, "keyword", "function"), (2, "function", "f"),
        ),
    ),
    _PackCase(
        "ruby", "rb",
        ["# note", "def f", "  puts 'x'", "end"],
        (
            (0, "comment", "# note"),
            (1, "keyword", "def"), (1, "function", "f"),
            (2, "string", "'x'"), (3, "keyword", "end"),
        ),
    ),
    _PackCase(
        "markdown", "md",
        ["# Title", "```py", "code = 1"],
        # The heading marker is a ``heading`` capture (SYNTAX_KINDS paints it
        # like a keyword) and the fence's info string is ``builtin`` -- both
        # must be registered in DEFAULT_CAPTURE_MAP or they are dropped.
        ((0, "heading", "#"), (1, "builtin", "py"), (2, "string", "code = 1")),
    ),
    _PackCase(
        "xml", "xml",
        ["<!-- note -->", '<root attr="1">x</root>'],
        (
            (0, "comment", "<!-- note -->"),
            (1, "type", "root"), (1, "string", '"1"'),
        ),
    ),
    _PackCase(
        "xaml", "xaml",
        ["<!-- note -->", "<Grid>x</Grid>"],
        ((0, "comment", "<!-- note -->"), (1, "type", "Grid")),
    ),
    _PackCase(
        "zig", "zig",
        ["// note", "pub fn main() void {", '    const s = "x";', "}"],
        (
            (0, "comment", "// note"),
            (1, "keyword", "pub"), (1, "keyword", "fn"),
            (1, "type", "void"),
        ),
    ),
]

_PACK_PARAMS: list[object] = [
    pytest.param(
        case.filetype,
        case.lines,
        case.expected,
        id=case.pack,
        marks=[pytest.mark.skipif(
            importlib.util.find_spec(ts_langs.BUILTIN_PACKS[case.pack]) is None,
            reason=f"{ts_langs.BUILTIN_PACKS[case.pack]} is not installed",
        )],
    )
    for case in _PACK_CASES
]


@pytest.mark.parametrize(("filetype", "lines", "expected"), _PACK_PARAMS)
def test_builtin_pack_highlights_representative_tokens(
    filetype: str,
    lines: list[str],
    expected: tuple[tuple[int, str, str], ...],
) -> None:
    """Each built-in grammar pack paints its sample's representative tokens."""
    toks = ts_backend.tokenize_document(lines, filetype)
    for row, kind, text in expected:
        assert (kind, text) in _kinds(toks[row], lines[row])


# --- engine routing ---------------------------------------------------------


@_python_skip
def test_engine_uses_ts_for_python() -> None:
    lines = ["# note", "def foo(): pass"]
    assert engine.tokenize_document(lines, "py") == (
        ts_backend.tokenize_document(lines, "py")
    )


@_python_skip
def test_prefer_regex_still_overrides_ts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lines = ["# note"]
    monkeypatch.setattr(engine, "_REGEX_PINNED", set[str]())
    engine.prefer_regex("py")
    assert engine.tokenize_document(lines, "py") == (
        regex_backend.tokenize_document(lines, "py")
    )


# --- blocked-version guard --------------------------------------------------


def test_version_classifier(monkeypatch: pytest.MonkeyPatch) -> None:
    cases = [
        ("win32", "0.26.0", "0.26.0"),
        ("win32", "0.26.99", "0.26.99"),
        ("win32", "0.25.2", None),
        ("win32", "0.27.0", None),
        ("linux", "0.26.0", None),
    ]
    for platform_name, raw, expected in cases:
        monkeypatch.setattr(sys, "platform", platform_name)

        def fake_version(_name: str, raw: str = raw) -> str:
            return raw

        monkeypatch.setattr(ts_langs, "version", fake_version)
        assert ts_langs._blocked_ts_version() == expected, f"{platform_name} / {raw}"


def test_blocked_build_disables_ts_and_routes_to_regex(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lines = ["# note", "def foo(): pass"]
    # Isolate the registry caches: another test module may already have
    # loaded the python grammar into _LANGS in this process, which would
    # make resolve() return early before reaching the block check.
    monkeypatch.setattr(ts_langs, "_BLOCKED_TS", "0.26.0")
    monkeypatch.setattr(ts_langs, "_LANGS", {})
    monkeypatch.setattr(ts_langs, "_FAILED", set[str]())
    assert ts_runtime.tree_sitter_blocked()
    assert not ts_runtime.available_for("py")
    assert ts_langs.resolve("py") is None
    assert "python" in ts_langs._FAILED
    assert engine.tokenize_document(lines, "py") == (
        regex_backend.tokenize_document(lines, "py")
    )


# --- syntax extension bridge ------------------------------------------------


@_python_skip
def test_unknown_pack_raises_value_error() -> None:
    from yate.services.extensions import SyntaxExtensionBridge

    bridge = SyntaxExtensionBridge()
    with pytest.raises(ValueError):
        bridge.register_tree_sitter(
            "nope_lang",
            grammar="tree_sitter_definitely_missing_xyz",
            extensions=["npx"],
            query="(comment) @comment",
        )


@_python_skip
def test_pack_registration_and_query_file(tmp_path: Path) -> None:
    query_path = tmp_path / "highlights.scm"
    query_path.write_text(
        "(comment) @comment\n(string) @string\n", encoding="utf-8"
    )
    bridge = ext_services.SyntaxExtensionBridge()
    with (
        mock.patch.dict(ts_langs._LANGS),
        mock.patch.dict(ts_langs._EXT_TO_LANG),
        mock.patch.object(ts_langs, "_FAILED", set[str]()),
        mock.patch.dict(regex_backend._LANGUAGES),
        mock.patch.dict(regex_backend._NAME_TO_KEY),
    ):
        bridge.register_tree_sitter(
            "pytestlang",
            grammar="tree_sitter_python",
            extensions=["ptl"],
            query=str(query_path),  # file path variant
        )
        lines = ["# hi", 'x = "s"']
        assert ts_backend.available_for("ptl")
        toks = ts_backend.tokenize_document(lines, "ptl")
        assert ("comment", "# hi") in _kinds(toks[0], lines[0])
        assert ("string", '"s"') in _kinds(toks[1], lines[1])
        # routed through the engine, and visible in :set filetype
        assert engine.tokenize_document(lines, "ptl") == (
            ts_backend.tokenize_document(lines, "ptl")
        )
        assert "ptl" in available_filetypes()


# --- byte column conversion -------------------------------------------------


def test_ascii_passes_through() -> None:
    assert ts_runtime._to_char(b"hello", 0) == 0
    assert ts_runtime._to_char(b"hello", 3) == 3


def test_values_are_clamped_to_the_line() -> None:
    assert ts_runtime._to_char(b"abc", 99) == 3
    assert ts_runtime._to_char(b"abc", -5) == 0


def test_multibyte_utf8() -> None:
    line = "xé".encode("utf-8")  # b"x\xc3\xa9"
    assert ts_runtime._to_char(line, 1) == 1
    assert ts_runtime._to_char(line, 3) == 2


def test_column_inside_a_multibyte_sequence_drops_the_lone_lead() -> None:
    assert ts_runtime._to_char("xé".encode("utf-8"), 2) == 1


# --- capture clipping -------------------------------------------------------


@dataclass
class _Point:
    row: int
    column: int


@dataclass
class _Node:
    """Minimal stand-in for a tree-sitter node's point geometry."""

    start_point: _Point
    end_point: _Point


def _clip(node: _Node, lines: list[str]) -> list[tuple[int, int, int]]:
    return list(
        ts_runtime._clip_to_rows(
            cast(ts_runtime._TsNode, node),
            lines,
            [line.encode("utf-8") for line in lines],
        )
    )


def test_single_line_node() -> None:
    assert _clip(_Node(_Point(0, 0), _Point(0, 3)), ["abc"]) == [(0, 0, 3)]


def test_multiline_node_fills_inner_rows() -> None:
    node = _Node(_Point(0, 1), _Point(2, 1))
    assert _clip(node, ["ab", "cd", "ef"]) == (
        [(0, 1, 2), (1, 0, 2), (2, 0, 1)]
    )


def test_node_starting_past_document_end_is_dropped() -> None:
    node = _Node(_Point(3, 0), _Point(4, 0))
    assert _clip(node, ["a", "b"]) == []


def test_node_ending_past_document_end_is_clamped() -> None:
    # Tree built before the document shrank: the tail clips to the last row.
    node = _Node(_Point(0, 0), _Point(5, 10))
    assert _clip(node, ["ab", "cd"]) == [(0, 0, 2), (1, 0, 2)]


# --- per-row token layout ---------------------------------------------------


def test_empty_intervals_produce_no_tokens() -> None:
    assert ts_runtime._tokens_for_row([], 5) == []


def test_single_span() -> None:
    assert ts_runtime._tokens_for_row([(0, 3, "keyword")], 5) == (
        [Token(0, 3, "keyword")]
    )


def test_nested_span_inner_wins_and_gaps_keep_outer_kind() -> None:
    tokens = ts_runtime._tokens_for_row(
        [(0, 6, "string"), (2, 4, "keyword")], 6
    )
    assert tokens == [
        Token(0, 2, "string"),
        Token(2, 4, "keyword"),
        Token(4, 6, "string"),
    ]


def test_adjacent_same_kind_runs_are_merged() -> None:
    assert ts_runtime._tokens_for_row([(0, 2, "x"), (2, 4, "x")], 4) == (
        [Token(0, 4, "x")]
    )


def test_adjacent_different_kinds_stay_separate() -> None:
    assert ts_runtime._tokens_for_row([(0, 2, "a"), (2, 4, "b")], 4) == (
        [Token(0, 2, "a"), Token(2, 4, "b")]
    )


def test_spans_are_clipped_to_line_bounds() -> None:
    assert ts_runtime._tokens_for_row([(-3, 2, "a"), (4, 99, "b")], 5) == (
        [Token(0, 2, "a"), Token(4, 5, "b")]
    )


def test_zero_length_span_is_dropped() -> None:
    assert ts_runtime._tokens_for_row([(2, 2, "a"), (0, 1, "b")], 5) == (
        [Token(0, 1, "b")]
    )


def test_unsorted_input_comes_out_position_sorted() -> None:
    tokens = ts_runtime._tokens_for_row(
        [(4, 5, "a"), (0, 2, "b")], 5
    )
    assert [token.start for token in tokens] == [0, 4]


# --- degrade paths ----------------------------------------------------------


def test_empty_document_returns_no_rows() -> None:
    # Even a resolvable language on zero lines returns an empty result.
    assert ts_backend.tokenize_document([], "py") == []


def test_unknown_filetype_is_plain_text_per_line() -> None:
    assert ts_backend.tokenize_document(["a", "bb"], "not_a_language_xyz") == (
        [[], []]
    )


# --- cross-module invariants ------------------------------------------------


def test_capture_map_targets_are_valid_token_kinds() -> None:
    invalid = set(ts_langs.DEFAULT_CAPTURE_MAP.values()) - set(SYNTAX_KINDS)
    assert invalid == set()


def test_builtin_packs_ship_a_query_file() -> None:
    for name in ts_langs.BUILTIN_PACKS:
        query = ts_langs.QUERIES_DIR / f"{name}.scm"
        assert query.is_file(), f"missing bundled query {query}"


#: ``@name`` in a query source; the trailing boundary keeps ``@name.foo``
#: (dotted capture names) intact.
_CAPTURE_RE = re.compile(r"@([A-Za-z_][\w.]*)")


def _query_capture_names() -> dict[str, set[str]]:
    """Capture names per bundled query file, ignoring ``;`` comment lines.

    Deliberately dependency-free: a grammar-pack install is not required, so
    the invariant still holds in a regex-only checkout.
    """
    found: dict[str, set[str]] = {}
    for scm in sorted(ts_langs.QUERIES_DIR.glob("*.scm")):
        names: set[str] = set()
        for line in scm.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith(";"):
                continue
            names.update(_CAPTURE_RE.findall(stripped))
        found[scm.stem] = names
    return found


def test_bundled_queries_only_use_registered_captures() -> None:
    # An unregistered capture name is dropped by the backend (``kind is None``),
    # so the span renders with the default foreground -- a silent failure that
    # no per-language sample test can catch when its grammar pack is absent.
    for stem, names in _query_capture_names().items():
        unregistered = names - set(ts_langs.DEFAULT_CAPTURE_MAP)
        assert unregistered == set(), f"{stem}.scm uses unregistered {unregistered}"


def test_markdown_heading_and_fence_language_are_registered() -> None:
    # The two markdown captures that regressed once: the heading markers and
    # the fence info string (the ```py language tag).
    names = _query_capture_names()["markdown"]
    assert "heading" in names
    assert "builtin" in names


def test_builtin_packs_match_packaging_manifests() -> None:
    # BUILTIN_PACKS, the [ts] extra and PyInstaller's _TS_PACKAGES are three
    # copies of one list, previously kept in sync by a prose comment.  They
    # must agree: a grammar missing from the extra is uninstallable, and one
    # missing from _TS_PACKAGES is invisible in a frozen build.
    root = Path(__file__).resolve().parents[1]
    pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    extras = pyproject["project"]["optional-dependencies"]
    ts_extra = cast(list[str], extras["ts"])
    dev_extra = cast(list[str], extras["dev"])

    def modules(requirements: list[str]) -> set[str]:
        names: set[str] = set()
        for requirement in requirements:
            base = re.split(r"[<>=!~\[; ]", requirement.strip(), maxsplit=1)[0]
            names.add(base.replace("-", "_"))
        return names

    common_src = (root / "pack" / "_common.py").read_text(encoding="utf-8")
    tuple_body = re.search(
        r"_TS_PACKAGES[^=]*=\s*\(([^)]*)\)", common_src, re.DOTALL
    )
    assert tuple_body is not None, "pack/_common.py lost its _TS_PACKAGES tuple"
    pack_modules = set(re.findall(r'"([\w.]+)"', tuple_body.group(1)))

    assert modules(ts_extra) == pack_modules
    # ``dev`` is a superset: it adds the test/type tooling on top of [ts].
    assert pack_modules <= modules(dev_extra)
    # Every pack a language needs, and nothing else (xml/xaml share one module,
    # hence the set comparison rather than equal counts).
    assert set(ts_langs.BUILTIN_PACKS.values()) == pack_modules - {"tree_sitter"}


def test_same_span_captures_resolve_by_kind_precedence() -> None:
    # Bundled queries keep a wide catch-all next to a narrow capture (a query
    # cannot express "not a call"); the winner must not depend on the dict
    # order of QueryCursor.captures(), which py-tree-sitter does not document.
    both = [(0, 3, "function.method"), (0, 3, "property")]
    assert [t.kind for t in ts_runtime._tokens_for_row(both, 3)] == ["function.method"]
    # ... and the same answer whichever way the candidates arrive.
    assert [t.kind for t in ts_runtime._tokens_for_row(both[::-1], 3)] == [
        "function.method"
    ]
    assert ts_runtime._KIND_RANK["function.method"] < ts_runtime._KIND_RANK["property"]
    assert ts_runtime._KIND_RANK["property"] < len(ts_runtime._KIND_PRECEDENCE)


def test_scss_and_less_do_not_borrow_the_css_grammar() -> None:
    # They share the CSS word lists but must keep their own language name: the
    # tree-sitter resolver looks a grammar up by LangSpec.name, and a shared
    # "css" name would parse $var / @mixin / // with the CSS grammar.
    for name in ("css", "scss", "less"):
        spec = regex_backend.lang_for(name)
        assert spec is not None
        assert spec.name == name
    if has_tree_sitter:
        assert ts_backend.available_for("css")
        assert not ts_backend.available_for("scss")
        assert not ts_backend.available_for("less")


def test_symbol_name_replaces_non_identifier_characters() -> None:
    assert ts_langs._symbol_name("yate shell") == "yate_shell"
    assert ts_langs._symbol_name("MyLang-2!") == "mylang_2_"


# --- registry without tree-sitter -------------------------------------------


def test_availability_follows_the_probe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ts_langs, "tree_sitter", lambda: None)
    assert not ts_langs.ts_available()
    monkeypatch.setattr(ts_langs, "tree_sitter", lambda: object())
    assert ts_langs.ts_available()


def test_load_entry_points_raise_runtime_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ts_langs, "tree_sitter", lambda: None)
    with pytest.raises(RuntimeError):
        ts_langs.load_language("x", object(), "")
    with pytest.raises(RuntimeError):
        ts_langs.load_language_from_grammar("x", "tree_sitter_x", "")
    with pytest.raises(RuntimeError):
        ts_langs.language_from_shared_library("x.so", "tree_sitter_x")


def test_missing_symbol_error_includes_library_path_and_symbol(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakeDll:
        """Loaded shared-library stand-in that exposes no symbols."""

    def fake_cdll(_path: str) -> _FakeDll:
        return _FakeDll()

    monkeypatch.setattr(ts_langs, "tree_sitter", lambda: object())
    monkeypatch.setattr(ts_langs, "ctypes", SimpleNamespace(CDLL=fake_cdll))
    with pytest.raises(RuntimeError) as excinfo:
        ts_langs.language_from_shared_library(
            "fake_grammar.dll", "tree_sitter_missing"
        )
    message = str(excinfo.value)
    assert "fake_grammar.dll" in message
    assert "tree_sitter_missing" in message


def test_unknown_filetype_resolves_to_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ts_langs, "tree_sitter", lambda: None)
    assert ts_langs.resolve("not_registered_language_xyz") is None


def test_failed_load_is_recorded_and_never_retried() -> None:
    with (
        mock.patch.dict(ts_langs._LANGS, {}, clear=True),
        mock.patch.dict(ts_langs._EXT_TO_LANG, {"fl": "fakelang"}, clear=True),
        mock.patch.object(ts_langs, "_FAILED", set[str]()),
        mock.patch.object(
            ts_langs, "_load_builtin", return_value=None
        ) as load,
    ):
        assert ts_langs.resolve("fl") is None
        assert ts_langs.resolve("fl") is None
        load.assert_called_once_with("fakelang")
        assert "fakelang" in ts_langs._FAILED


# --- grammar discovery ------------------------------------------------------


@_ts_skip
def test_missing_pack_raises_value_error() -> None:
    with pytest.raises(ValueError):
        ts_langs.load_language_from_grammar(
            "zzz", "tree_sitter_definitely_missing_xyz", ""
        )


@_ts_skip
def test_missing_shared_library_raises_os_error() -> None:
    library = str(Path("no_such_grammar_dir_xyz") / "zzz.so")
    with pytest.raises(OSError):
        ts_langs.load_language_from_grammar("zzz", library, "")


# --- load_language registration ---------------------------------------------


@_python_skip
def test_extensions_capture_map_and_failure_clearing() -> None:
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
        assert ts_langs._FAILED == set()
        # names/extensions are normalized to lowercase, dot-stripped keys
        assert "pytest" in ts_langs._LANGS
        assert ts_langs._EXT_TO_LANG["ptl"] == "pytest"
        loaded = ts_langs.resolve(".PTL")
        assert loaded is not None
        assert loaded is ts_langs._LANGS["pytest"]
        # custom mapping overrides the default, defaults otherwise survive
        assert loaded.capture_map["comment"] == "operator"
        assert loaded.capture_map["keyword"] == "keyword"
        # tree-sitter serves the extension, while :set filetype sees it
        assert ts_backend.available_for("ptl")
        assert "ptl" in available_filetypes()
        fallback = regex_backend.lang_for("ptl")
        assert fallback is not None
        assert fallback.name == "pytest"


# --- broken built-in packs --------------------------------------------------


@_ts_skip
def test_missing_pack_returns_none_then_caches_the_failure() -> None:
    with (
        mock.patch.dict(ts_langs._LANGS, {}, clear=True),
        mock.patch.object(ts_langs, "_FAILED", set[str]()),
        mock.patch.dict(
            ts_langs.BUILTIN_PACKS,
            {"python": "tree_sitter_pack_missing_xyz"},
        ),
    ):
        assert ts_langs._load_builtin("python") is None
        # resolve() records the failure on first miss ...
        assert ts_langs.resolve("py") is None
        assert "python" in ts_langs._FAILED
        # ... and does not retry the broken grammar on later calls
        with mock.patch.object(ts_langs, "_load_builtin") as load:
            assert ts_langs.resolve("py") is None
            load.assert_not_called()


def test_missing_query_file_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        ts_langs, "QUERIES_DIR", Path("/nonexistent_query_dir_xyz")
    )
    assert ts_langs._load_builtin("python") is None


# --- bridge argument handling -----------------------------------------------


@pytest.fixture
def bridge() -> ext_services.SyntaxExtensionBridge:
    """Provide a fresh syntax extension bridge."""
    return ext_services.SyntaxExtensionBridge()


def test_query_source_string_is_passed_through(
    bridge: ext_services.SyntaxExtensionBridge,
) -> None:
    with mock.patch.object(
        ext_services, "load_language_from_grammar"
    ) as loader:
        bridge.register_tree_sitter(
            "lg",
            grammar="tree_sitter_lg",
            extensions=["lg"],
            query="(comment) @comment",
            capture_map={"weird.capture": "comment"},
        )
    loader.assert_called_once()
    args, kwargs = loader.call_args
    assert args[0] == "lg"
    assert args[1] == "tree_sitter_lg"
    assert args[2] == "(comment) @comment"
    assert kwargs["extensions"] == ("lg",)
    assert kwargs["capture_map"] == {"weird.capture": "comment"}


def test_nonexistent_query_path_is_treated_as_source(
    bridge: ext_services.SyntaxExtensionBridge,
) -> None:
    query = "no/such/dir_xyz/highlights.scm"
    with mock.patch.object(
        ext_services, "load_language_from_grammar"
    ) as loader:
        bridge.register_tree_sitter(
            "lg", grammar="tree_sitter_lg", extensions=["lg"], query=query
        )
    assert loader.call_args.args[2] == query


def test_query_file_path_is_read_before_registration(
    bridge: ext_services.SyntaxExtensionBridge, tmp_path: Path
) -> None:
    query_path = tmp_path / "highlights.scm"
    query_path.write_text("(comment) @comment\n", encoding="utf-8")
    with mock.patch.object(
        ext_services, "load_language_from_grammar"
    ) as loader:
        bridge.register_tree_sitter(
            "lg",
            grammar="tree_sitter_lg",
            extensions=["lg"],
            query=str(query_path),
        )
    assert loader.call_args.args[2] == "(comment) @comment\n"


def test_runtime_error_propagates_without_tree_sitter(
    bridge: ext_services.SyntaxExtensionBridge,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ts_langs, "tree_sitter", lambda: None)
    with pytest.raises(RuntimeError):
        bridge.register_tree_sitter(
            "lg",
            grammar="tree_sitter_lg",
            extensions=["lg"],
            query="(comment) @comment",
        )
