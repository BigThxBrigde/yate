"""Regex syntax backend: a single-pass, stateful tokenizer.

This is the zero-dependency default backend of the :mod:`yate.editor_syntax`
layer (the tree-sitter backend, when installed, takes precedence per
language).  The module is pure logic (no terminal/Rich code): it turns
document lines into per-line token ranges, :class:`Token`
``(start, end, kind)`` where *kind* is one of the keys in
:data:`~yate.editor_syntax.tokens.SYNTAX_KINDS`.  The view layer maps kinds
to colors through the active theme.

Design notes (see editor tokenizer lessons):

* A **master regex alternation** is scanned once per line -- rules never
  re-match text that an earlier rule already claimed, which prevents the
  classic "string rule colors content inside an inserted highlight span"
  corruption.
* **Multiline constructs** (Python triple-quoted strings, ``/* ... */`` block
  comments, Markdown code fences) are carried across lines by an explicit
  state machine; they are checked *before* any single-line rule.
* Regexes are module-level constants and word sets are frozensets so the hot
  path is just alternation matching + set lookups.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

from yate.editor_syntax.tokens import Token


# ---------------------------------------------------------------------------
# Language specifications
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LangSpec:
    """Declarative description of a language's lexical rules."""

    name: str
    mode: str = "code"            # "code" | "json" | "markdown" | "config"
    line_comment: Optional[str] = None
    block_comment: Optional[tuple[str, str]] = None
    triple_strings: bool = False  # Python ''' / """ multiline strings
    string_prefixes: str = ""     # letters allowed directly before a quote
    sigils: bool = False          # $variable expansion (shell)
    keywords: frozenset[str] = frozenset()
    builtins: frozenset[str] = frozenset()
    constants: frozenset[str] = frozenset()
    types: frozenset[str] = frozenset()
    func_def_words: frozenset[str] = frozenset()   # next identifier = function
    type_def_words: frozenset[str] = frozenset()   # next identifier = type
    macro_call: bool = False      # identifier followed by '!' (Rust macros)


_PY_KEYWORDS = frozenset({
    "and", "as", "assert", "async", "await", "break", "class", "continue",
    "def", "del", "elif", "else", "except", "finally", "for", "from",
    "global", "if", "import", "in", "is", "lambda", "nonlocal", "not",
    "or", "pass", "raise", "return", "try", "while", "with", "yield",
    "match", "case",
})
_PY_CONSTANTS = frozenset({"True", "False", "None", "NotImplemented", "Ellipsis", "__debug__"})
_PY_BUILTINS = frozenset({
    "print", "len", "range", "enumerate", "zip", "map", "filter", "sum",
    "min", "max", "abs", "open", "input", "sorted", "reversed", "any",
    "all", "repr", "format", "dir", "vars", "getattr", "setattr",
    "hasattr", "isinstance", "issubclass", "super", "property",
    "staticmethod", "classmethod", "iter", "next", "hash", "id", "hex",
    "oct", "bin", "chr", "ord", "round", "pow", "divmod", "callable",
    "compile", "eval", "exec", "globals", "locals", "help", "exit", "quit",
})
_PY_TYPES = frozenset({
    "int", "str", "float", "bool", "bytes", "bytearray", "complex", "list",
    "dict", "set", "frozenset", "tuple", "object", "type", "Exception",
    "ValueError", "TypeError", "KeyError", "IndexError", "RuntimeError",
    "StopIteration",
})

_C_KEYWORDS = frozenset({
    "auto", "break", "case", "const", "continue", "default", "do", "else",
    "enum", "extern", "for", "goto", "if", "inline", "register", "restrict",
    "return", "sizeof", "static", "struct", "switch", "typedef", "union",
    "volatile", "while",
})
_C_BUILTINS = frozenset({
    "printf", "fprintf", "sprintf", "snprintf", "puts", "putchar", "getchar",
    "malloc", "calloc", "realloc", "free", "memcpy", "memset", "memmove",
    "strlen", "strcmp", "strncmp", "strcpy", "strncpy", "atoi", "atof",
    "fopen", "fclose", "fread", "fwrite", "fgets", "fputs", "exit", "abort",
})

_C_TYPES = frozenset({
    "int", "char", "float", "double", "void", "long", "short", "signed",
    "unsigned", "size_t", "ssize_t", "ptrdiff_t", "FILE", "bool", "uint8_t",
    "uint16_t", "uint32_t", "uint64_t", "int8_t", "int16_t", "int32_t",
    "int64_t", "NULL",
})

_CPP_EXTRA = frozenset({
    "class", "public", "private", "protected", "virtual", "new", "delete",
    "namespace", "template", "typename", "this", "nullptr", "throw", "try",
    "catch", "operator", "using", "friend", "constexpr", "decltype",
    "override", "final", "explicit", "mutable", "dynamic_cast",
    "static_cast", "reinterpret_cast", "const_cast", "co_await", "co_return",
    "co_yield", "concept", "requires", "noexcept",
})
_CPP_TYPES = frozenset({
    "std", "string", "vector", "map", "unordered_map", "set", "list",
    "shared_ptr", "unique_ptr", "weak_ptr", "optional", "variant",
    "pair", "tuple", "array", "function", "auto",
})

_JAVA_KEYWORDS = frozenset({
    "abstract", "assert", "boolean", "break", "byte", "case", "catch",
    "char", "class", "const", "continue", "default", "do", "double", "else",
    "enum", "extends", "final", "finally", "float", "for", "goto", "if",
    "implements", "import", "instanceof", "int", "interface", "long",
    "native", "new", "package", "private", "protected", "public", "return",
    "short", "static", "strictfp", "super", "switch", "synchronized",
    "this", "throw", "throws", "transient", "try", "void", "volatile",
    "while", "var", "record", "sealed", "permits", "yield",
})

_RUST_KEYWORDS = frozenset({
    "as", "async", "await", "break", "const", "continue", "crate", "dyn",
    "else", "enum", "extern", "fn", "for", "if", "impl", "in", "let",
    "loop", "match", "mod", "move", "mut", "pub", "ref", "return", "self",
    "Self", "static", "struct", "super", "trait", "type", "unsafe", "use",
    "where", "while",
})
_RUST_CONSTANTS = frozenset({"true", "false", "Some", "None", "Ok", "Err"})
_RUST_TYPES = frozenset({
    "i8", "i16", "i32", "i64", "i128", "isize", "u8", "u16", "u32", "u64",
    "u128", "usize", "f32", "f64", "bool", "char", "str", "String", "Vec",
    "Box", "Option", "Result", "HashMap", "BTreeMap", "HashSet", "Rc", "Arc",
})

_GO_KEYWORDS = frozenset({
    "break", "case", "chan", "const", "continue", "default", "defer", "else",
    "fallthrough", "for", "func", "go", "goto", "if", "import", "interface",
    "map", "package", "range", "return", "select", "struct", "switch",
    "type", "var",
})
_GO_CONSTANTS = frozenset({"true", "false", "nil", "iota"})
_GO_BUILTINS = frozenset({
    "make", "len", "cap", "new", "append", "copy", "delete", "panic",
    "println", "print", "recover", "complex", "real", "imag", "close",
})
_GO_TYPES = frozenset({
    "string", "int", "int8", "int16", "int32", "int64", "uint", "uint8",
    "uint16", "uint32", "uint64", "float32", "float64", "bool", "byte",
    "rune", "error", "any",
})

_JS_KEYWORDS = frozenset({
    "break", "case", "catch", "class", "const", "continue", "debugger",
    "default", "delete", "do", "else", "export", "extends", "finally", "for",
    "function", "if", "import", "in", "instanceof", "let", "new", "return",
    "super", "switch", "this", "throw", "try", "typeof", "var", "void",
    "while", "with", "yield", "static", "from", "as", "async", "await", "of",
})
_JS_CONSTANTS = frozenset({"true", "false", "null", "undefined", "NaN", "Infinity"})
_JS_BUILTINS = frozenset({
    "console", "document", "window", "Math", "JSON", "Object", "Array",
    "String", "Number", "Boolean", "Promise", "Map", "Set", "WeakMap",
    "WeakSet", "Symbol", "BigInt", "setTimeout", "setInterval",
    "clearTimeout", "clearInterval", "fetch", "require", "module",
    "process", "exports", "globalThis", "URL", "Error", "Date", "RegExp",
})
_TS_TYPES = frozenset({
    "string", "number", "boolean", "any", "unknown", "never", "void", "null",
    "undefined", "object", "symbol", "bigint", "interface", "type", "enum",
    "namespace", "public", "private", "protected", "readonly", "implements",
    "declare", "abstract", "keyof", "infer", "is",
})

_SHELL_KEYWORDS = frozenset({
    "if", "then", "else", "elif", "fi", "for", "while", "do", "done",
    "case", "esac", "function", "in", "select", "until", "time", "local",
    "return", "exit", "export", "source", "alias", "unset", "shift", "set",
})
_SHELL_BUILTINS = frozenset({
    "echo", "cd", "ls", "pwd", "cat", "grep", "sed", "awk", "rm", "cp",
    "mv", "mkdir", "touch", "chmod", "chown", "curl", "wget", "git", "python",
    "python3", "pip", "sudo", "apt", "brew", "npm", "node", "make",
})

_JSON_CONSTANTS = frozenset({"true", "false", "null"})


def _spec(
    name: str,
    *,
    mode: str = "code",
    line_comment: Optional[str] = None,
    block_comment: Optional[tuple[str, str]] = None,
    triple_strings: bool = False,
    string_prefixes: str = "",
    sigils: bool = False,
    keywords: frozenset[str] = frozenset(),
    builtins: frozenset[str] = frozenset(),
    constants: frozenset[str] = frozenset(),
    types: frozenset[str] = frozenset(),
    func_def_words: frozenset[str] = frozenset(),
    type_def_words: frozenset[str] = frozenset(),
    macro_call: bool = False,
) -> LangSpec:
    """Tiny constructor alias keeping the language table readable."""
    return LangSpec(
        name=name, mode=mode, line_comment=line_comment,
        block_comment=block_comment, triple_strings=triple_strings,
        string_prefixes=string_prefixes, sigils=sigils, keywords=keywords,
        builtins=builtins, constants=constants, types=types,
        func_def_words=func_def_words, type_def_words=type_def_words,
        macro_call=macro_call,
    )


_LANGUAGES: dict[str, LangSpec] = {}

# Canonical language name (LangSpec.name) -> the first extension key that
# registered that spec. Kept in sync inside register_language(), so custom
# languages registered by extensions are resolvable by name immediately.
_NAME_TO_KEY: dict[str, str] = {}


def register_language(spec: LangSpec, *extensions: str) -> None:
    """Register a language spec under one or more extension keys.

    This is the public extension point used by both the built-in language
    table and custom-syntax extensions (``api.highlight.register``):
    registering an existing key again replaces its spec, which lets an
    extension override built-in highlighting. Leading dots are tolerated.
    """
    for ext in extensions:
        key = ext.lower().lstrip(".")
        if not key:
            continue
        _LANGUAGES[key] = spec
        _NAME_TO_KEY.setdefault(spec.name, key)


register_language(
    _spec(
        "python", line_comment="#", triple_strings=True, string_prefixes="rRbBuUfF",
        keywords=_PY_KEYWORDS, builtins=_PY_BUILTINS, constants=_PY_CONSTANTS,
        types=_PY_TYPES, func_def_words=frozenset({"def"}),
        type_def_words=frozenset({"class"}),
    ),
    "py", "pyi", "pyw",
)
register_language(
    _spec(
        "c", line_comment="//", block_comment=("/*", "*/"),
        keywords=_C_KEYWORDS, builtins=_C_BUILTINS,
        constants=frozenset({"EOF"}), types=_C_TYPES,
        func_def_words=frozenset(),
        type_def_words=frozenset({"struct", "union", "typedef", "enum"}),
    ),
    "c", "h",
)
register_language(
    _spec(
        "cpp", line_comment="//", block_comment=("/*", "*/"),
        keywords=_C_KEYWORDS | _CPP_EXTRA, builtins=_C_BUILTINS,
        constants=frozenset({"nullptr", "true", "false", "EOF"}),
        types=_CPP_TYPES | _C_TYPES,
        func_def_words=frozenset(),
        type_def_words=frozenset({"class", "struct", "enum", "namespace", "typename"}),
    ),
    "cpp", "cc", "cxx", "c++", "hpp", "hxx", "h++", "hh", "ino",
)
register_language(
    _spec(
        "java", line_comment="//", block_comment=("/*", "*/"),
        keywords=_JAVA_KEYWORDS,
        constants=frozenset({"true", "false", "null"}),
        type_def_words=frozenset({"class", "interface", "enum", "record"}),
    ),
    "java",
)
register_language(
    _spec(
        "rust", line_comment="//", block_comment=("/*", "*/"),
        keywords=_RUST_KEYWORDS, constants=_RUST_CONSTANTS, types=_RUST_TYPES,
        func_def_words=frozenset({"fn"}),
        type_def_words=frozenset({"struct", "enum", "trait", "type", "impl", "mod"}),
        macro_call=True,
    ),
    "rs",
)
register_language(
    _spec(
        "go", line_comment="//", block_comment=("/*", "*/"),
        keywords=_GO_KEYWORDS, builtins=_GO_BUILTINS, constants=_GO_CONSTANTS,
        types=_GO_TYPES, func_def_words=frozenset({"func"}),
        type_def_words=frozenset({"type", "struct", "interface"}),
    ),
    "go",
)
register_language(
    _spec(
        "javascript", line_comment="//", block_comment=("/*", "*/"),
        keywords=_JS_KEYWORDS, builtins=_JS_BUILTINS, constants=_JS_CONSTANTS,
        func_def_words=frozenset({"function"}),
        type_def_words=frozenset({"class"}),
    ),
    "js", "mjs", "cjs", "jsx",
)
register_language(
    _spec(
        "typescript", line_comment="//", block_comment=("/*", "*/"),
        keywords=_JS_KEYWORDS, builtins=_JS_BUILTINS, constants=_JS_CONSTANTS,
        types=_TS_TYPES, func_def_words=frozenset({"function"}),
        type_def_words=frozenset({"class", "interface", "enum", "namespace", "type"}),
    ),
    "ts", "tsx", "mts", "cts",
)
register_language(
    _spec(
        "shell", line_comment="#", sigils=True,
        keywords=_SHELL_KEYWORDS, builtins=_SHELL_BUILTINS,
        constants=frozenset({"true", "false"}),
    ),
    "sh", "bash", "zsh", "fish",
)
register_language(
    _spec("json", mode="json", line_comment=None, constants=_JSON_CONSTANTS),
    "json",
)
register_language(
    _spec("jsonc", mode="json", line_comment="//", block_comment=("/*", "*/"),
          constants=_JSON_CONSTANTS),
    "jsonc",
)
register_language(_spec("markdown", mode="markdown"), "md", "markdown", "mdx")
register_language(_spec("toml", mode="config", line_comment="#"), "toml")
register_language(_spec("ini", mode="config", line_comment="#"), "ini", "cfg", "conf", "properties")
register_language(_spec("yaml", mode="config", line_comment="#"), "yaml", "yml")


def lang_for(filetype: str) -> Optional[LangSpec]:
    """Resolve a Document ``filetype`` (file extension without dot) to a spec.

    Returns ``None`` for unknown / plain-text files.
    """
    return _LANGUAGES.get(filetype.lower())


def resolve_filetype(name: str) -> Optional[str]:
    """Normalize a user-typed filetype to a registered extension key.

    Accepts either an extension key (``py``, ``ts``, ``c++``) or a language
    name (``python``, ``typescript``). A leading dot is tolerated. Returns
    ``None`` when nothing matches.
    """
    key = name.strip().lower().lstrip(".")
    if not key:
        return None
    if key in _LANGUAGES:
        return key
    return _NAME_TO_KEY.get(key)


def language_name(filetype: str) -> Optional[str]:
    """Human-readable language name for an extension key (``py`` -> python)."""
    spec = lang_for(filetype)
    return spec.name if spec is not None else None


def available_filetypes() -> list[str]:
    """Sorted extension keys and language names accepted by :set filetype."""
    return sorted(set(_LANGUAGES) | set(_NAME_TO_KEY))


# ---------------------------------------------------------------------------
# Regex building
# ---------------------------------------------------------------------------

_NUMBER_RE = re.compile(
    r"(?:"
    r"0[xX][0-9a-fA-F_]+"        # hex
    r"|0[oO][0-7_]+"             # octal
    r"|0[bB][01_]+"              # binary
    r"|\d[\d_]*(?:\.\d[\d_]*)?(?:[eE][+-]?\d[\d_]*)?"  # decimal / float
    r")[uUlLfFjJ]*"
)
_IDENT_RE = re.compile(r"[A-Za-z_]\w*")
_SIGIL_RE = re.compile(r"\$\{?[A-Za-z_][A-Za-z0-9_]*\}?")
_DECORATOR_RE = re.compile(r"@[A-Za-z_][\w.]*")
_OPERATOR_RE = re.compile(r"(?:->|=>|\.\.\.|::|[-+*/%=<>!&|^~?:]+)")

_MD_HEADING_RE = re.compile(r"^(#{1,6})\s+.*$")
_MD_FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")
_MD_RULES = re.compile(
    r"(`+)(?:[^`\n]|`(?!\1))*?\1"          # code span
    r"|\[[^\]\n]+\]\([^)\n]*\)"            # link [text](url)
    r"|\*\*[^*\n]+\*\*|__[^_\n]+__"        # bold
    r"|(?<!\w)\*[^*\n]+\*(?!\w)|(?<!\w)_[^_\n]+_(?!\w)"  # italic
    r"|^\s*[-*+](?=\s)"                    # list bullet
    r"|`[^`\n]*`?"
)

_CONFIG_SECTION_RE = re.compile(r"^\s*\[[^\]]+\]")
_CONFIG_KEY_RE = re.compile(r"^\s*[A-Za-z0-9_.\"-]+(?=\s*[:=])")
_STRING_RE = re.compile(r'"(?:\\.|[^"\\\n])*"' + r"|'(?:\\.|[^'\\\n])*'")

#: Boolean-ish words painted as ``constant`` in config files, matched only on
#: word boundaries; precompiled once instead of per word per line.
_CONFIG_BOOL_RE = re.compile(r"(?<!\w)(?:true|false|null|yes|no|on|off)(?!\w)")

#: One-pass value scan for config lines: string | number | bool word.  A
#: single ``finditer`` over this alternation consumes each match before
#: scanning resumes, so tokens never overlap -- a string swallows the
#: digits and bool words inside it instead of double-coloring them.  The
#: branches begin with disjoint characters (quote / digit / bool letter),
#: so the alternation order never decides which one wins.
_CONFIG_TOKEN_RE = re.compile(
    f"(?:{_STRING_RE.pattern})|(?:{_NUMBER_RE.pattern})"
    f"|(?:{_CONFIG_BOOL_RE.pattern})"
)


@lru_cache(maxsize=None)
def _code_line_pattern(spec: LangSpec) -> re.Pattern[str]:
    """Build the master alternation regex for one code-like language.

    :class:`LangSpec` is a frozen, hashable dataclass and the built pattern
    depends only on it, so results are cached per spec: repeated
    :func:`tokenize_document` calls for the same language skip the rebuild.
    """
    parts: list[str] = []
    if spec.block_comment is not None:
        open_, _close = spec.block_comment
        parts.append(re.escape(open_))
    if spec.triple_strings:
        parts.append(r'"""|\'\'\'')
    if spec.line_comment is not None:
        parts.append(re.escape(spec.line_comment) + r"[^\n]*")
    prefix = f"(?:[{spec.string_prefixes}]{{1,2}})?" if spec.string_prefixes else ""
    parts.append(prefix + r'"(?:\\.|[^"\\\n])*"')
    parts.append(prefix + r"'(?:\\.|[^'\\\n])*'")
    parts.append(_NUMBER_RE.pattern)
    parts.append(_DECORATOR_RE.pattern)
    if spec.sigils:
        parts.append(_SIGIL_RE.pattern)
    parts.append(_IDENT_RE.pattern)
    parts.append(_OPERATOR_RE.pattern)
    return re.compile("|".join(f"(?:{p})" for p in parts))


# ---------------------------------------------------------------------------
# Tokenizers
# ---------------------------------------------------------------------------

# Multiline tokenizer states.
_S_CODE = 0
_S_BLOCK_COMMENT = 1
_S_TRIPLE_DQ = 2
_S_TRIPLE_SQ = 3
_S_MD_FENCE = 4


def _emit(tokens: list[Token], start: int, end: int, kind: str) -> None:
    if end > start:
        tokens.append(Token(start, end, kind))


def _tokenize_code_line(
    line: str, spec: LangSpec, pattern: re.Pattern[str], state: int
) -> tuple[list[Token], int]:
    """Tokenize one code/markdown line; returns (tokens, new_state)."""
    tokens: list[Token] = []
    n = len(line)
    pos = 0
    pending: Optional[str] = None  # forced kind for the next identifier

    # --- continuation of a multiline construct -----------------------------
    if state == _S_BLOCK_COMMENT:
        assert spec.block_comment is not None
        close = spec.block_comment[1]
        idx = line.find(close)
        if idx == -1:
            _emit(tokens, 0, n, "comment")
            return tokens, _S_BLOCK_COMMENT
        end = idx + len(close)
        _emit(tokens, 0, end, "comment")
        pos = end
        state = _S_CODE
    elif state in (_S_TRIPLE_DQ, _S_TRIPLE_SQ):
        quote = '"""' if state == _S_TRIPLE_DQ else "'''"
        idx = line.find(quote)
        if idx == -1:
            _emit(tokens, 0, n, "string")
            return tokens, state
        end = idx + 3
        _emit(tokens, 0, end, "string")
        pos = end
        state = _S_CODE

    # --- single-pass master scan -------------------------------------------
    while pos < n:
        m = pattern.match(line, pos)
        if m is None:
            # Unmatched punctuation (brackets, parens, commas) breaks the
            # "def <name>" expectation (e.g. Go's `func (r *T) Method()`).
            if not line[pos].isspace():
                pending = None
            pos += 1
            continue
        start, end = m.start(), m.end()
        text = m.group(0)

        if spec.block_comment is not None and text == spec.block_comment[0]:
            close = spec.block_comment[1]
            close_idx = line.find(close, end)
            if close_idx == -1:
                _emit(tokens, start, n, "comment")
                return tokens, _S_BLOCK_COMMENT
            _emit(tokens, start, close_idx + len(close), "comment")
            pos = close_idx + len(close)
            pending = None
            continue

        if spec.triple_strings and text in ('"""', "'''"):
            quote = text
            close_idx = line.find(quote, end)
            if close_idx == -1:
                _emit(tokens, start, n, "string")
                state = _S_TRIPLE_DQ if quote == '"""' else _S_TRIPLE_SQ
                return tokens, state
            _emit(tokens, start, close_idx + 3, "string")
            pos = close_idx + 3
            pending = None
            continue

        if spec.line_comment is not None and text.startswith(spec.line_comment):
            _emit(tokens, start, n, "comment")
            break

        if text[0] in ('"', "'") or (
            spec.string_prefixes and text[:1] in spec.string_prefixes
            and text[-1:] in ('"', "'")
        ):
            kind = "string"
            if spec.mode == "json":
                # JSON property key: string immediately followed by ':'
                tail = line[end:end + 5].lstrip()
                if tail.startswith(":"):
                    kind = "property"
            _emit(tokens, start, end, kind)
            pending = None
            pos = end
            continue

        if _NUMBER_RE.match(text) and (text[0].isdigit() or text[:2].lower() in ("0x", "0o", "0b")):
            _emit(tokens, start, end, "number")
            pending = None
            pos = end
            continue

        if text[0] == "@":
            _emit(tokens, start, end, "decorator")
            pending = None
            pos = end
            continue

        if spec.sigils and text[0] == "$":
            _emit(tokens, start, end, "property")
            pos = end
            continue

        if _IDENT_RE.match(text):
            kind, pending = _classify_ident(
                spec, text, pending, line=line, start=start
            )
            if kind is not None:
                _emit(tokens, start, end, kind)
            pos = end
            continue

        if text and text[0] in "=+-*/%<>!&|^~?:":
            _emit(tokens, start, end, "operator")
            pending = None
            pos = end
            continue

        pos = end if end > pos else pos + 1

    return tokens, state


def _classify_ident(
    spec: LangSpec,
    word: str,
    pending: Optional[str],
    *,
    line: str,
    start: int,
) -> tuple[Optional[str], Optional[str]]:
    """Decide the token kind of an identifier, plus the pending kind for the
    next identifier (set by ``def`` / ``class`` / ``fn`` style keywords)."""
    end = start + len(word)
    if pending is not None:
        return pending, None
    # func_def_words / type_def_words are keyword-like on their own (a custom
    # LangSpec may omit them from ``keywords``): they color as keywords and
    # force the kind of the identifier that follows.
    if (
        word in spec.keywords
        or word in spec.func_def_words
        or word in spec.type_def_words
    ):
        if word in spec.func_def_words:
            return "keyword", "function"
        if word in spec.type_def_words:
            return "keyword", "type"
        return "keyword", None
    if word in spec.constants:
        return "constant", None
    if word in spec.types:
        return "type", None
    if word in spec.builtins:
        return "builtin", None
    after = line[end:end + 2]
    if spec.macro_call and after.startswith("!"):
        return "function", None
    if after.startswith("("):
        return "function", None
    if start > 0 and line[start - 1] == ".":
        return "property", None
    return None, None


def _tokenize_markdown_line(line: str, state: int) -> tuple[list[Token], int]:
    """Tokenize one Markdown line (headings, fences, spans)."""
    tokens: list[Token] = []
    if state == _S_MD_FENCE:
        if _MD_FENCE_RE.match(line):
            _emit(tokens, 0, len(line), "string")
            return tokens, _S_CODE
        _emit(tokens, 0, len(line), "string")
        return tokens, _S_MD_FENCE

    fence = _MD_FENCE_RE.match(line)
    if fence is not None:
        _emit(tokens, fence.start(), len(line), "string")
        return tokens, _S_MD_FENCE

    heading = _MD_HEADING_RE.match(line)
    if heading is not None:
        _emit(tokens, 0, len(line), "heading")
        return tokens, _S_CODE

    for m in _MD_RULES.finditer(line):
        text = m.group(0)
        if text[0] == "`":
            kind = "string"
        elif text[0] == "[":
            kind = "link"
        elif text[0] in "*-+" and len(text.strip()) <= 2:
            kind = "operator"          # list bullet
        else:
            kind = "emphasis"          # bold / italic
        _emit(tokens, m.start(), m.end(), kind)
    return tokens, _S_CODE


def _tokenize_config_line(line: str, spec: LangSpec) -> list[Token]:
    """Tokenize one TOML / INI / YAML style line."""
    tokens: list[Token] = []
    if spec.line_comment is not None:
        idx = line.find(spec.line_comment)
        if idx != -1:
            _emit(tokens, idx, len(line), "comment")
            line = line[:idx]

    section = _CONFIG_SECTION_RE.match(line)
    if section is not None:
        _emit(tokens, section.start(), section.end(), "keyword")
        return tokens

    key = _CONFIG_KEY_RE.match(line)
    scan_from = 0
    if key is not None:
        _emit(tokens, key.start(), key.end(), "property")
        # digits / bool words inside the key belong to the property token
        scan_from = key.end()

    for m in _CONFIG_TOKEN_RE.finditer(line, scan_from):
        text = m.group(0)
        if text[0] in ('"', "'"):
            _emit(tokens, m.start(), m.end(), "string")
        elif text[0].isdigit():
            _emit(tokens, m.start(), m.end(), "number")
        else:
            _emit(tokens, m.start(), m.end(), "constant")
    return tokens


def tokenize_document(lines: list[str], filetype: str) -> list[list[Token]]:
    """Tokenize a whole document, returning tokens per line.

    Multiline state is carried top to bottom so triple strings, block
    comments and code fences highlight correctly across line boundaries.
    """
    spec = lang_for(filetype)
    if spec is None:
        return [[] for _ in lines]

    result: list[list[Token]] = []
    state = _S_CODE

    if spec.mode == "markdown":
        for line in lines:
            tokens, state = _tokenize_markdown_line(line, state)
            result.append(tokens)
        return result

    if spec.mode == "config":
        for line in lines:
            result.append(_tokenize_config_line(line, spec))
        return result

    pattern = _code_line_pattern(spec)
    for line in lines:
        tokens, state = _tokenize_code_line(line, spec, pattern, state)
        result.append(tokens)
    return result
