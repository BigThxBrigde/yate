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

from yate.editor_syntax.tokens import Token


# ---------------------------------------------------------------------------
# Language specifications
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LangSpec:
    """Declarative description of a language's lexical rules."""

    name: str
    mode: str = "code"            # "code" | "json" | "markdown" | "config"
    line_comment: str | None = None
    block_comment: tuple[str, str] | None = None
    triple_strings: bool = False  # Python ''' / """ multiline strings
    string_prefixes: str = ""     # letters allowed directly before a quote
    sigils: bool = False          # $variable expansion (shell)
    at_sigil: bool = False        # '@name' is a variable, not a decorator
    paren_vars: bool = False      # '$(VAR)' expansion (make)
    hyphenated_idents: bool = False  # 'font-size' is one identifier (CSS)
    keywords: frozenset[str] = frozenset()
    builtins: frozenset[str] = frozenset()
    constants: frozenset[str] = frozenset()
    types: frozenset[str] = frozenset()
    func_def_words: frozenset[str] = frozenset()   # next identifier = function
    type_def_words: frozenset[str] = frozenset()   # next identifier = type
    macro_call: bool = False      # identifier followed by '!' (Rust macros)


_PY_KEYWORDS: frozenset[str] = frozenset({
    "and", "as", "assert", "async", "await", "break", "class", "continue",
    "def", "del", "elif", "else", "except", "finally", "for", "from",
    "global", "if", "import", "in", "is", "lambda", "nonlocal", "not",
    "or", "pass", "raise", "return", "try", "while", "with", "yield",
    "match", "case",
})
_PY_CONSTANTS: frozenset[str] = frozenset({
    "True", "False", "None", "NotImplemented", "Ellipsis", "__debug__",
})
_PY_BUILTINS: frozenset[str] = frozenset({
    "print", "len", "range", "enumerate", "zip", "map", "filter", "sum",
    "min", "max", "abs", "open", "input", "sorted", "reversed", "any",
    "all", "repr", "format", "dir", "vars", "getattr", "setattr",
    "hasattr", "isinstance", "issubclass", "super", "property",
    "staticmethod", "classmethod", "iter", "next", "hash", "id", "hex",
    "oct", "bin", "chr", "ord", "round", "pow", "divmod", "callable",
    "compile", "eval", "exec", "globals", "locals", "help", "exit", "quit",
})
_PY_TYPES: frozenset[str] = frozenset({
    "int", "str", "float", "bool", "bytes", "bytearray", "complex", "list",
    "dict", "set", "frozenset", "tuple", "object", "type", "Exception",
    "ValueError", "TypeError", "KeyError", "IndexError", "RuntimeError",
    "StopIteration",
})

_C_KEYWORDS: frozenset[str] = frozenset({
    "auto", "break", "case", "const", "continue", "default", "do", "else",
    "enum", "extern", "for", "goto", "if", "inline", "register", "restrict",
    "return", "sizeof", "static", "struct", "switch", "typedef", "union",
    "volatile", "while",
})
_C_BUILTINS: frozenset[str] = frozenset({
    "printf", "fprintf", "sprintf", "snprintf", "puts", "putchar", "getchar",
    "malloc", "calloc", "realloc", "free", "memcpy", "memset", "memmove",
    "strlen", "strcmp", "strncmp", "strcpy", "strncpy", "atoi", "atof",
    "fopen", "fclose", "fread", "fwrite", "fgets", "fputs", "exit", "abort",
})

_C_TYPES: frozenset[str] = frozenset({
    "int", "char", "float", "double", "void", "long", "short", "signed",
    "unsigned", "size_t", "ssize_t", "ptrdiff_t", "FILE", "bool", "uint8_t",
    "uint16_t", "uint32_t", "uint64_t", "int8_t", "int16_t", "int32_t",
    "int64_t", "NULL",
})

_CPP_EXTRA: frozenset[str] = frozenset({
    "class", "public", "private", "protected", "virtual", "new", "delete",
    "namespace", "template", "typename", "this", "nullptr", "throw", "try",
    "catch", "operator", "using", "friend", "constexpr", "decltype",
    "override", "final", "explicit", "mutable", "dynamic_cast",
    "static_cast", "reinterpret_cast", "const_cast", "co_await", "co_return",
    "co_yield", "concept", "requires", "noexcept",
})
_CPP_TYPES: frozenset[str] = frozenset({
    "std", "string", "vector", "map", "unordered_map", "set", "list",
    "shared_ptr", "unique_ptr", "weak_ptr", "optional", "variant",
    "pair", "tuple", "array", "function", "auto",
})

_JAVA_KEYWORDS: frozenset[str] = frozenset({
    "abstract", "assert", "boolean", "break", "byte", "case", "catch",
    "char", "class", "const", "continue", "default", "do", "double", "else",
    "enum", "extends", "final", "finally", "float", "for", "goto", "if",
    "implements", "import", "instanceof", "int", "interface", "long",
    "native", "new", "package", "private", "protected", "public", "return",
    "short", "static", "strictfp", "super", "switch", "synchronized",
    "this", "throw", "throws", "transient", "try", "void", "volatile",
    "while", "var", "record", "sealed", "permits", "yield",
})

_RUST_KEYWORDS: frozenset[str] = frozenset({
    "as", "async", "await", "break", "const", "continue", "crate", "dyn",
    "else", "enum", "extern", "fn", "for", "if", "impl", "in", "let",
    "loop", "match", "mod", "move", "mut", "pub", "ref", "return", "self",
    "Self", "static", "struct", "super", "trait", "type", "unsafe", "use",
    "where", "while",
})
_RUST_CONSTANTS: frozenset[str] = frozenset({"true", "false", "Some", "None", "Ok", "Err"})
_RUST_TYPES: frozenset[str] = frozenset({
    "i8", "i16", "i32", "i64", "i128", "isize", "u8", "u16", "u32", "u64",
    "u128", "usize", "f32", "f64", "bool", "char", "str", "String", "Vec",
    "Box", "Option", "Result", "HashMap", "BTreeMap", "HashSet", "Rc", "Arc",
})

_GO_KEYWORDS: frozenset[str] = frozenset({
    "break", "case", "chan", "const", "continue", "default", "defer", "else",
    "fallthrough", "for", "func", "go", "goto", "if", "import", "interface",
    "map", "package", "range", "return", "select", "struct", "switch",
    "type", "var",
})
_GO_CONSTANTS: frozenset[str] = frozenset({"true", "false", "nil", "iota"})
_GO_BUILTINS: frozenset[str] = frozenset({
    "make", "len", "cap", "new", "append", "copy", "delete", "panic",
    "println", "print", "recover", "complex", "real", "imag", "close",
})
_GO_TYPES: frozenset[str] = frozenset({
    "string", "int", "int8", "int16", "int32", "int64", "uint", "uint8",
    "uint16", "uint32", "uint64", "float32", "float64", "bool", "byte",
    "rune", "error", "any",
})

_JS_KEYWORDS: frozenset[str] = frozenset({
    "break", "case", "catch", "class", "const", "continue", "debugger",
    "default", "delete", "do", "else", "export", "extends", "finally", "for",
    "function", "if", "import", "in", "instanceof", "let", "new", "return",
    "super", "switch", "this", "throw", "try", "typeof", "var", "void",
    "while", "with", "yield", "static", "from", "as", "async", "await", "of",
})
_JS_CONSTANTS: frozenset[str] = frozenset({"true", "false", "null", "undefined", "NaN", "Infinity"})
_JS_BUILTINS: frozenset[str] = frozenset({
    "console", "document", "window", "Math", "JSON", "Object", "Array",
    "String", "Number", "Boolean", "Promise", "Map", "Set", "WeakMap",
    "WeakSet", "Symbol", "BigInt", "setTimeout", "setInterval",
    "clearTimeout", "clearInterval", "fetch", "require", "module",
    "process", "exports", "globalThis", "URL", "Error", "Date", "RegExp",
})
_TS_TYPES: frozenset[str] = frozenset({
    "string", "number", "boolean", "any", "unknown", "never", "void", "null",
    "undefined", "object", "symbol", "bigint", "interface", "type", "enum",
    "namespace", "public", "private", "protected", "readonly", "implements",
    "declare", "abstract", "keyof", "infer", "is",
})

_SHELL_KEYWORDS: frozenset[str] = frozenset({
    "if", "then", "else", "elif", "fi", "for", "while", "do", "done",
    "case", "esac", "function", "in", "select", "until", "time", "local",
    "return", "exit", "export", "source", "alias", "unset", "shift", "set",
})
_SHELL_BUILTINS: frozenset[str] = frozenset({
    "echo", "cd", "ls", "pwd", "cat", "grep", "sed", "awk", "rm", "cp",
    "mv", "mkdir", "touch", "chmod", "chown", "curl", "wget", "git", "python",
    "python3", "pip", "sudo", "apt", "brew", "npm", "node", "make",
})

_JSON_CONSTANTS: frozenset[str] = frozenset({"true", "false", "null"})


def _spec(
    name: str,
    *,
    mode: str = "code",
    line_comment: str | None = None,
    block_comment: tuple[str, str] | None = None,
    triple_strings: bool = False,
    string_prefixes: str = "",
    sigils: bool = False,
    at_sigil: bool = False,
    paren_vars: bool = False,
    hyphenated_idents: bool = False,
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
        string_prefixes=string_prefixes, sigils=sigils, at_sigil=at_sigil,
        paren_vars=paren_vars, hyphenated_idents=hyphenated_idents,
        keywords=keywords,
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

# --- regex fallbacks for the issue-IKJLTB languages ------------------------
# These languages ship a tree-sitter pack (see ts_backend.languages
# BUILTIN_PACKS); the specs below keep them highlighted in a bare
# ``pip install yate`` (no [ts] extra) and provide the filetype mapping the
# tree-sitter resolver relies on.  Perl has no grammar pack at all: regex
# is its only backend for now.

_CS_KEYWORDS: frozenset[str] = frozenset({
    "abstract", "as", "base", "break", "case", "catch", "checked", "class",
    "const", "continue", "default", "delegate", "do", "else", "enum", "event",
    "explicit", "extern", "finally", "fixed", "for", "foreach", "goto", "if",
    "implicit", "in", "interface", "internal", "is", "lock", "namespace",
    "new", "operator", "out", "override", "params", "private", "protected",
    "public", "readonly", "ref", "return", "sealed", "sizeof", "stackalloc",
    "static", "struct", "switch", "this", "throw", "try", "typeof",
    "unchecked", "unsafe", "using", "virtual", "volatile", "while",
    "add", "alias", "ascending", "async", "await", "by", "descending", "equals",
    "from", "get", "global", "group", "into", "join", "let", "nameof", "on",
    "orderby", "partial", "record", "remove", "select", "set", "value", "var",
    "when", "where", "yield", "init", "required", "with",
})
_CS_CONSTANTS: frozenset[str] = frozenset({"true", "false", "null"})
_CS_TYPES: frozenset[str] = frozenset({
    "bool", "byte", "char", "decimal", "double", "dynamic", "float", "int",
    "long", "nint", "nuint", "object", "sbyte", "short", "string", "uint",
    "ulong", "ushort", "void",
    "String", "Int32", "Int64", "Boolean", "Double", "Single", "Decimal",
    "Char", "Byte", "Object", "Guid", "DateTime", "DateTimeOffset", "TimeSpan",
    "Nullable", "Exception", "Task", "ValueTask", "Action", "Func",
    "List", "IList", "IReadOnlyList", "Dictionary", "IDictionary",
    "HashSet", "IEnumerable", "ICollection", "IDisposable",
    "Span", "ReadOnlySpan", "Memory", "ReadOnlyMemory", "CancellationToken",
})
_CS_BUILTINS: frozenset[str] = frozenset({
    "Console", "Math", "Convert", "Environment", "Debug", "Trace", "GC",
    "File", "Directory", "Path",
})

register_language(
    _spec(
        "csharp", line_comment="//", block_comment=("/*", "*/"),
        string_prefixes="@$",
        keywords=_CS_KEYWORDS, builtins=_CS_BUILTINS,
        constants=_CS_CONSTANTS, types=_CS_TYPES,
        type_def_words=frozenset({"class", "struct", "interface", "enum", "record"}),
    ),
    "cs", "csx",
)

_HTML_TAGS: frozenset[str] = frozenset({
    "a", "abbr", "address", "area", "article", "aside", "audio", "b", "base",
    "bdi", "bdo", "blockquote", "body", "br", "button", "canvas", "caption",
    "cite", "code", "col", "colgroup", "data", "datalist", "dd", "del",
    "details", "dfn", "dialog", "div", "dl", "dt", "em", "embed", "fieldset",
    "figcaption", "figure", "footer", "form", "h1", "h2", "h3", "h4", "h5",
    "h6", "head", "header", "hgroup", "hr", "html", "i", "iframe", "img",
    "input", "ins", "kbd", "label", "legend", "li", "link", "main", "map",
    "mark", "menu", "meta", "meter", "nav", "noscript", "object", "ol",
    "optgroup", "option", "output", "p", "picture", "pre", "progress", "q",
    "rp", "rt", "ruby", "s", "samp", "script", "search", "section", "select",
    "slot", "small", "source", "span", "strong", "style", "sub", "summary",
    "sup", "table", "tbody", "td", "template", "textarea", "tfoot", "th",
    "thead", "time", "title", "tr", "track", "u", "ul", "var", "video", "wbr",
})

register_language(
    _spec("html", block_comment=("<!--", "-->"), types=_HTML_TAGS),
    "html", "htm",
)

_CSS_PROPERTIES: frozenset[str] = frozenset({
    "align-content", "align-items", "align-self", "animation", "background",
    "background-color", "background-image", "background-position",
    "background-repeat", "background-size", "border", "border-color",
    "border-radius", "border-style", "border-width", "bottom", "box-shadow",
    "box-sizing", "color", "content", "cursor", "display", "flex", "flex-basis",
    "flex-direction", "flex-grow", "flex-shrink", "flex-wrap", "float",
    "font", "font-family", "font-size", "font-style", "font-weight", "gap",
    "grid", "grid-template-columns", "grid-template-rows", "height", "inset",
    "justify-content", "justify-items", "justify-self", "left", "letter-spacing",
    "line-height", "list-style", "margin", "margin-bottom", "margin-left",
    "margin-right", "margin-top", "max-height", "max-width", "min-height",
    "min-width", "object-fit", "opacity", "order", "outline", "overflow",
    "overflow-x", "overflow-y", "padding", "padding-bottom", "padding-left",
    "padding-right", "padding-top", "pointer-events", "position", "right",
    "row-gap", "text-align", "text-decoration", "text-overflow",
    "text-transform", "top", "transform", "transition", "user-select",
    "vertical-align", "visibility", "white-space", "width", "word-break",
    "word-spacing", "writing-mode", "z-index",
})
_CSS_COLORS: frozenset[str] = frozenset({
    "black", "white", "red", "green", "blue", "yellow", "orange", "purple",
    "gray", "grey", "silver", "maroon", "olive", "lime", "aqua", "cyan",
    "magenta", "fuchsia", "navy", "teal", "pink", "brown", "beige", "gold",
    "indigo", "violet", "transparent", "currentColor", "inherit", "initial",
    "unset", "revert",
})
_CSS_TAGS: frozenset[str] = frozenset({
    "html", "body", "head", "div", "span", "p", "a", "ul", "ol", "li",
    "table", "tr", "td", "th", "form", "input", "button", "select", "option",
    "textarea", "label", "img", "section", "header", "footer", "nav",
    "article", "aside", "main", "h1", "h2", "h3", "h4", "h5", "h6", "strong",
    "em", "code", "pre", "blockquote", "script", "style", "link", "meta",
    "title",
})

#: ``scss`` / ``less`` get their own specs instead of sharing the ``css`` one:
#: the tree-sitter resolver looks a grammar up by ``LangSpec.name``, so a
#: shared name would route ``.scss`` files into the CSS grammar and produce
#: ERROR nodes for ``$var`` / ``@mixin`` / ``//``.  Separate names keep them on
#: the regex backend (no ``tree-sitter-scss`` / ``-less`` exists on PyPI)
#: without changing any extension key.
def _css_family(name: str) -> LangSpec:
    """The shared CSS word lists under a language name of its own."""
    return _spec(
        name, block_comment=("/*", "*/"),
        builtins=_CSS_PROPERTIES, constants=_CSS_COLORS, types=_CSS_TAGS,
        hyphenated_idents=True,
    )


register_language(_css_family("css"), "css")
register_language(_css_family("scss"), "scss")
register_language(_css_family("less"), "less")

_PS_KEYWORDS: frozenset[str] = frozenset({
    "if", "elseif", "else", "switch", "for", "foreach", "while", "do",
    "until", "break", "continue", "return", "throw", "try", "catch",
    "finally", "trap", "function", "filter", "param", "in", "begin",
    "process", "end", "class", "enum", "exit", "from", "hidden", "static",
    "default", "dynamicparam", "data", "workflow", "parallel", "sequence",
})
#: ``switch`` is absent on purpose: it is a PowerShell keyword.
_PS_TYPES: frozenset[str] = frozenset({
    "string", "int", "bool", "long", "double", "object", "byte", "char",
    "decimal", "single", "float", "array", "hashtable", "psobject", "void",
    "ref", "scriptblock", "xml", "wmi", "wmiclass", "regex",
    "pscustomobject",
})

register_language(
    _spec("powershell", line_comment="#", sigils=True, at_sigil=True,
          keywords=_PS_KEYWORDS, types=_PS_TYPES),
    "ps1", "psm1", "psd1",
)

_LUA_KEYWORDS: frozenset[str] = frozenset({
    "and", "break", "do", "else", "elseif", "end", "for", "function", "goto",
    "if", "in", "local", "not", "or", "repeat", "return", "then", "until",
    "while",
})
_LUA_CONSTANTS: frozenset[str] = frozenset({"true", "false", "nil"})
_LUA_BUILTINS: frozenset[str] = frozenset({
    "print", "type", "tostring", "tonumber", "pairs", "ipairs", "require",
    "error", "pcall", "xpcall", "setmetatable", "getmetatable", "rawget",
    "rawset", "rawequal", "rawlen", "select", "next", "assert", "unpack",
    "load", "loadstring", "dofile", "collectgarbage", "setfenv", "getfenv",
})
#: ``function`` is absent on purpose: it is a Lua keyword, and keywords are
#: matched before types, so listing it here would be dead weight.
_LUA_TYPES: frozenset[str] = frozenset({
    "table", "string", "number", "boolean", "thread", "userdata",
})

register_language(
    _spec(
        "lua", line_comment="--",
        keywords=_LUA_KEYWORDS, builtins=_LUA_BUILTINS,
        constants=_LUA_CONSTANTS, types=_LUA_TYPES,
        func_def_words=frozenset({"function"}),
    ),
    "lua",
)

_MAKE_KEYWORDS: frozenset[str] = frozenset({
    "ifeq", "ifneq", "ifdef", "ifndef", "else", "endif", "include",
    "define", "endef", "export", "unexport", "override",
    "undefine", "private", "vpath", "foreach", "call", "eval", "value",
})

#: ``-include`` is deliberately absent: ``_IDENT_RE`` has no ``-``, so a leading
#: dash could never be classified as a keyword.  Makefile variables are spelled
#: ``$(VAR)`` / ``$@`` / ``$<``, covered by :attr:`LangSpec.paren_vars`.
register_language(
    _spec("make", line_comment="#", sigils=True, paren_vars=True,
          keywords=_MAKE_KEYWORDS),
    "mak", "mk",
)

register_language(
    _spec("xml", block_comment=("<!--", "-->")),
    "xml",
)

#: Common WPF / UWP / Avalonia element and property names.  XML itself has no
#: vocabulary worth listing (tags are open-ended), but XAML is a fixed UI
#: vocabulary, and without it the regex fallback only ever paints comments and
#: attribute values.
_XAML_TYPES: frozenset[str] = frozenset({
    "Application", "Window", "UserControl", "Page", "ContentControl",
    "Grid", "StackPanel", "Canvas", "WrapPanel", "DockPanel", "Panel",
    "Border", "ScrollViewer", "Viewbox", "ItemsControl", "ListBox",
    "ListView", "GridView", "ComboBox", "TabControl", "Menu", "ToolBar",
    "Button", "ToggleButton", "RadioButton", "CheckBox", "TextBox",
    "PasswordBox", "Label", "TextBlock", "RichTextBlock", "Image",
    "ProgressBar", "Slider", "Separator", "ContextMenu", "MenuItem",
    "RowDefinition", "ColumnDefinition", "GridLength", "Thickness",
    "SolidColorBrush", "LinearGradientBrush", "DataTemplate",
    "ControlTemplate", "Style", "Setter", "Trigger", "Storyboard",
    "ResourceDictionary", "TemplateBinding", "Binding", "RelativeSource",
    "DependencyProperty", "DependencyObject", "DispatcherTimer",
})

register_language(
    _spec("xaml", block_comment=("<!--", "-->"), types=_XAML_TYPES),
    "xaml",
)

_PERL_KEYWORDS: frozenset[str] = frozenset({
    "my", "our", "local", "sub", "if", "elsif", "else", "unless", "while",
    "until", "for", "foreach", "do", "last", "next", "redo", "return", "use",
    "no", "require", "package", "state", "format", "given", "when", "default",
})
#: Perl spells its library functions without a receiver (``print STDERR ...``),
#: so they are builtins rather than keywords -- keeping them out of
#: ``_PERL_KEYWORDS`` is what makes ``print`` paint like ``len`` in Python
#: instead of like ``return``.
_PERL_BUILTINS: frozenset[str] = frozenset({
    "new", "bless", "ref", "defined", "exists", "delete", "grep", "map",
    "sort", "join", "split", "print", "printf", "sprintf", "say", "open",
    "close", "opendir", "closedir", "chomp", "chop", "shift", "unshift",
    "push", "pop", "keys", "values", "each", "wantarray", "eval", "try",
    "catch", "finally", "die", "warn", "scalar", "length", "substr", "reverse",
})

register_language(
    _spec(
        "perl", line_comment="#", sigils=True, at_sigil=True,
        keywords=_PERL_KEYWORDS, builtins=_PERL_BUILTINS,
        func_def_words=frozenset({"sub"}),
    ),
    "pl", "pm",
)

_PHP_KEYWORDS: frozenset[str] = frozenset({
    "abstract", "and", "array", "as", "break", "callable", "case", "catch",
    "class", "clone", "const", "continue", "declare", "default", "do", "echo",
    "else", "elseif", "empty", "enddeclare", "endfor", "endforeach", "endif",
    "endswitch", "endwhile", "enum", "extends", "final", "finally", "fn",
    "for", "foreach", "function", "global", "goto", "if", "implements",
    "include", "include_once", "instanceof", "insteadof", "interface",
    "isset", "list", "match", "namespace", "new", "or", "print", "private",
    "protected", "public", "readonly", "require", "require_once", "return",
    "static", "switch", "throw", "trait", "try", "unset", "use", "var",
    "while", "xor", "yield",
})
_PHP_CONSTANTS: frozenset[str] = frozenset({
    "true", "false", "null", "TRUE", "FALSE", "NULL",
})
#: ``callable`` and ``static`` are absent on purpose: both are PHP keywords.
_PHP_TYPES: frozenset[str] = frozenset({
    "int", "float", "bool", "string", "void", "mixed", "object",
    "iterable", "never", "parent", "self",
})

register_language(
    _spec(
        "php", line_comment="//",
        keywords=_PHP_KEYWORDS, constants=_PHP_CONSTANTS, types=_PHP_TYPES,
        func_def_words=frozenset({"function"}),
        type_def_words=frozenset({"class", "interface", "trait", "enum"}),
    ),
    "php",
)

#: Keywords only.  Library methods that read like keywords (``require``,
#: ``include``, ``attr_accessor``, ...) live in :data:`_RUBY_BUILTINS`: keywords
#: are matched first, so listing a word in both tables would make the builtins
#: entry dead data.
_RUBY_KEYWORDS: frozenset[str] = frozenset({
    "alias", "and", "begin", "break", "case", "class", "def", "do",
    "else", "elsif", "end", "ensure", "for", "if", "in", "module", "next",
    "not", "or", "redo", "rescue", "retry", "return", "self", "super", "then",
    "undef", "unless", "until", "when", "while", "yield",
})
#: Kernel / Enumerable methods, not keywords (``each`` is not a keyword at all
#: -- it is an Array method and has no business in the keyword table).
_RUBY_BUILTINS: frozenset[str] = frozenset({
    "new", "raise", "fail", "puts", "print", "loop", "lambda", "proc",
    "catch", "throw", "require", "require_relative", "include", "extend",
    "attr_accessor", "attr_reader", "attr_writer", "each", "map",
})
_RUBY_CONSTANTS: frozenset[str] = frozenset({"true", "false", "nil"})
_RUBY_TYPES: frozenset[str] = frozenset({
    "String", "Integer", "Float", "Array", "Hash", "Symbol", "Proc", "Range",
    "Regexp", "Struct", "Exception", "StandardError", "Object", "Class",
    "Module", "Numeric", "Comparable", "Enumerable", "Kernel", "IO", "File",
    "Dir", "Time", "Date", "Set",
})

register_language(
    _spec(
        "ruby", line_comment="#", at_sigil=True,
        keywords=_RUBY_KEYWORDS, builtins=_RUBY_BUILTINS,
        constants=_RUBY_CONSTANTS, types=_RUBY_TYPES,
        func_def_words=frozenset({"def"}),
        type_def_words=frozenset({"class", "module"}),
    ),
    "rb",
)

_SQL_KEYWORDS: frozenset[str] = frozenset({
    "select", "from", "where", "insert", "into", "values", "update", "delete",
    "set", "create", "table", "drop", "alter", "add", "column", "index",
    "view", "join", "inner", "left", "right", "outer", "full", "cross", "on",
    "group", "by", "order", "having", "limit", "offset", "union", "all",
    "distinct", "as", "and", "or", "not", "in", "between", "like", "ilike",
    "exists", "case", "when", "then", "else", "end", "primary", "key",
    "foreign", "references", "default", "check", "unique", "constraint",
    "begin", "commit", "rollback", "transaction", "truncate", "grant",
    "revoke", "asc", "desc", "is", "with", "using", "natural", "returning",
    "over", "partition", "window", "recursive", "analyze", "explain",
    "vacuum", "if", "temp", "temporary", "cascade", "restrict",
})
_SQL_TYPES: frozenset[str] = frozenset({
    "int", "integer", "bigint", "smallint", "varchar", "char", "text", "date",
    "datetime", "timestamp", "boolean", "bool", "decimal", "numeric", "float",
    "double", "real", "blob", "json", "jsonb", "uuid", "serial", "bigserial",
    "time", "interval", "bytea", "clob",
})
_SQL_BUILTINS: frozenset[str] = frozenset({
    "count", "sum", "avg", "min", "max", "coalesce", "nullif", "cast",
    "concat", "upper", "lower", "substring", "length", "now", "current_date",
    "current_timestamp", "row_number", "rank", "dense_rank", "abs", "round",
    "replace", "trim", "ltrim", "rtrim", "date_trunc", "date_part",
    "string_agg", "group_concat", "extract", "greatest", "least",
})

#: SQL keywords / types / functions are case-insensitive, and the engine
#: matches identifiers case-sensitively -- so both spellings are listed.  Named
#: constants rather than inline comprehensions: the expansion is part of the
#: contract with the word lists above, and its size should be readable.
_SQL_KEYWORDS_ALL: frozenset[str] = _SQL_KEYWORDS | {w.upper() for w in _SQL_KEYWORDS}
_SQL_BUILTINS_ALL: frozenset[str] = _SQL_BUILTINS | {w.upper() for w in _SQL_BUILTINS}
_SQL_TYPES_ALL: frozenset[str] = _SQL_TYPES | {w.upper() for w in _SQL_TYPES}

register_language(
    _spec(
        "sql", line_comment="--", block_comment=("/*", "*/"),
        keywords=_SQL_KEYWORDS_ALL,
        builtins=_SQL_BUILTINS_ALL,
        constants=frozenset({"null", "true", "false", "NULL", "TRUE", "FALSE"}),
        types=_SQL_TYPES_ALL,
    ),
    "sql",
)

_ZIG_KEYWORDS: frozenset[str] = frozenset({
    "align", "allowzero", "and", "anyframe", "anytype", "asm", "async",
    "await", "break", "callconv", "catch", "comptime", "const", "continue",
    "defer", "else", "enum", "errdefer", "error", "export", "extern", "fn",
    "for", "if", "inline", "noasync", "nosuspend", "opaque", "or", "orelse",
    "packed", "pub", "resume", "return", "linksection", "struct", "suspend",
    "switch", "test", "threadlocal", "try", "union", "usingnamespace", "var",
    "volatile", "while",
})
_ZIG_TYPES: frozenset[str] = frozenset({
    "i8", "i16", "i32", "i64", "i128", "isize", "u8", "u16", "u32", "u64",
    "u128", "usize", "f16", "f32", "f64", "f128", "bool", "void", "noreturn",
    "type", "anyerror", "anyopaque", "c_int", "c_uint", "c_long", "c_ulong",
    "c_short", "c_ushort", "c_char", "comptime_int", "comptime_float",
})

register_language(
    _spec(
        "zig", line_comment="//",
        keywords=_ZIG_KEYWORDS, types=_ZIG_TYPES,
        constants=frozenset({"true", "false", "null", "undefined"}),
        func_def_words=frozenset({"fn"}),
        type_def_words=frozenset({"struct", "enum", "union"}),
    ),
    "zig",
)


def lang_for(filetype: str) -> LangSpec | None:
    """Resolve a Document ``filetype`` (file extension without dot) to a spec.

    Returns ``None`` for unknown / plain-text files.
    """
    return _LANGUAGES.get(filetype.lower())


def resolve_filetype(name: str) -> str | None:
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


def language_name(filetype: str) -> str | None:
    """Human-readable language name for an extension key (``py`` -> python)."""
    spec = lang_for(filetype)
    return spec.name if spec is not None else None


def available_filetypes() -> list[str]:
    """Sorted extension keys and language names accepted by :set filetype."""
    return sorted(set(_LANGUAGES) | set(_NAME_TO_KEY))


def format_filetype_candidates(limit: int = 12) -> str:
    """:func:`available_filetypes` as a message-ready, truncated list.

    The registry holds 60+ keys plus every language name, which no status-bar
    width can show in full -- callers used to inline ``", ".join(...)`` and
    silently lose everything past the wrap column.  Shows *limit* entries (at
    least one) and appends ``"... (N total)"`` for the rest.
    """
    filetypes = available_filetypes()
    limit = max(1, limit)
    shown = ", ".join(filetypes[:limit])
    if len(filetypes) > limit:
        shown += f", ... ({len(filetypes)} total)"
    return shown


# ---------------------------------------------------------------------------
# Regex building
# ---------------------------------------------------------------------------

_NUMBER_RE: re.Pattern[str] = re.compile(
    r"(?:"
    r"0[xX][0-9a-fA-F_]+"        # hex
    r"|0[oO][0-7_]+"             # octal
    r"|0[bB][01_]+"              # binary
    r"|\d[\d_]*(?:\.\d[\d_]*)?(?:[eE][+-]?\d[\d_]*)?"  # decimal / float
    r")[uUlLfFjJ]*"
)
_IDENT_RE: re.Pattern[str] = re.compile(r"[A-Za-z_]\w*")
_SIGIL_RE: re.Pattern[str] = re.compile(r"\$\{?[A-Za-z_][A-Za-z0-9_]*\}?")
#: ``$(VAR)``-style make expansion.  The single-char ``$@`` / ``$<`` forms are
#: punctuation to the eye and get no pattern.  One level of nesting is allowed
#: (``$(shell echo $(X))``) so the token does not stop at the first ``)`` and
#: leave a stray one uncolored.  Kept separate from :data:`_SIGIL_RE` because a
#: parenthesized name may contain characters an identifier may not.
_PAREN_VAR_RE: re.Pattern[str] = re.compile(r"\$\((?:[^()\n]|\([^()\n]*\))*\)")
_DECORATOR_RE: re.Pattern[str] = re.compile(r"@[A-Za-z_][\w.]*")
#: Dash-joined identifiers (``font-size``).  Each segment must start with a
#: letter, so ``x-1`` still scans as ``x``, operator ``-``, number ``1``.
_DASHED_IDENT_RE: re.Pattern[str] = re.compile(r"[A-Za-z_]\w*(?:-[A-Za-z_]\w*)*")
_OPERATOR_RE: re.Pattern[str] = re.compile(r"(?:->|=>|\.\.\.|::|[-+*/%=<>!&|^~?:]+)")

_MD_HEADING_RE: re.Pattern[str] = re.compile(r"^(#{1,6})\s+.*$")
_MD_FENCE_RE: re.Pattern[str] = re.compile(r"^\s*(`{3,}|~{3,})")
_MD_RULES: re.Pattern[str] = re.compile(
    r"(`+)(?:[^`\n]|`(?!\1))*?\1"          # code span
    r"|\[[^\]\n]+\]\([^)\n]*\)"            # link [text](url)
    r"|\*\*[^*\n]+\*\*|__[^_\n]+__"        # bold
    r"|(?<!\w)\*[^*\n]+\*(?!\w)|(?<!\w)_[^_\n]+_(?!\w)"  # italic
    r"|^\s*[-*+](?=\s)"                    # list bullet
    r"|`[^`\n]*`?"
)

_CONFIG_SECTION_RE: re.Pattern[str] = re.compile(r"^\s*\[[^\]]+\]")
_CONFIG_KEY_RE: re.Pattern[str] = re.compile(r"^\s*[A-Za-z0-9_.\"-]+(?=\s*[:=])")
_STRING_RE: re.Pattern[str] = re.compile(r'"(?:\\.|[^"\\\n])*"' + r"|'(?:\\.|[^'\\\n])*'")

#: Boolean-ish words painted as ``constant`` in config files, matched only on
#: word boundaries; precompiled once instead of per word per line.
_CONFIG_BOOL_RE: re.Pattern[str] = re.compile(r"(?<!\w)(?:true|false|null|yes|no|on|off)(?!\w)")

#: One-pass value scan for config lines: string | number | bool word.  A
#: single ``finditer`` over this alternation consumes each match before
#: scanning resumes, so tokens never overlap -- a string swallows the
#: digits and bool words inside it instead of double-coloring them.  The
#: branches begin with disjoint characters (quote / digit / bool letter),
#: so the alternation order never decides which one wins.
_CONFIG_TOKEN_RE: re.Pattern[str] = re.compile(
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
    if spec.paren_vars:
        parts.append(_PAREN_VAR_RE.pattern)
    if spec.hyphenated_idents:
        parts.append(_DASHED_IDENT_RE.pattern)
    parts.append(_IDENT_RE.pattern)
    parts.append(_OPERATOR_RE.pattern)
    return re.compile("|".join(f"(?:{p})" for p in parts))


# ---------------------------------------------------------------------------
# Tokenizers
# ---------------------------------------------------------------------------

# Multiline tokenizer states.
_S_CODE: int = 0
_S_BLOCK_COMMENT: int = 1
_S_TRIPLE_DQ: int = 2
_S_TRIPLE_SQ: int = 3
_S_MD_FENCE: int = 4


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
    pending: str | None = None  # forced kind for the next identifier

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
            # '@' is a decorator in Python / C# / Java, but a sigil in perl
            # (@array), ruby (@ivar) and PowerShell (@splat) -- the spec says
            # which one it means.
            _emit(tokens, start, end, "property" if spec.at_sigil else "decorator")
            pending = None
            pos = end
            continue

        if (spec.sigils or spec.paren_vars) and text[0] == "$":
            # Both switches paint a sigil as a property, and either one alone
            # must reach this branch: a $(VAR) matched by _PAREN_VAR_RE would
            # otherwise be consumed with no token emitted at all.
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
    pending: str | None,
    *,
    line: str,
    start: int,
) -> tuple[str | None, str | None]:
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
    if spec.hyphenated_idents and "-" in word:
        # Last resort, after the '.' and '(' rules above: a dashed word that is
        # not itself a known name is looked up segment by segment, so vendor
        # prefixes ('-webkit-transform') and custom properties
        # ('--brand-color') keep the color of their base word -- what the
        # fragment scan produced before the whole word was captured.  Left to
        # right, the first hit wins.
        #
        # Being last is the whole point: '.nav-item' is a class selector, not a
        # property, and must not be painted as the <nav> tag just because one
        # of its segments is a known tag name.  A name whose segments are all
        # unknown ('btn-primary') stays uncolored.
        for part in word.split("-"):
            if part in spec.keywords:
                return "keyword", None
            if part in spec.constants:
                return "constant", None
            if part in spec.types:
                return "type", None
            if part in spec.builtins:
                return "builtin", None
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


def tokenize_document_with_states(
    lines: list[str], filetype: str
) -> tuple[list[list[Token]], tuple[int, ...]]:
    """Tokenize a whole document in one pass: tokens plus multiline state.

    Returns the per-line token lists :func:`tokenize_document` produces
    paired with the regex multiline state entering each next row -- the
    sequence the view layer's row-level resync resumes from.  One pass
    yields both artifacts, so callers that need the states (the highlight
    worker) do not pay a second full-document scan.  Multiline state is
    carried top to bottom so triple strings, block comments and code
    fences highlight correctly across line boundaries.
    """
    spec = lang_for(filetype)
    if spec is None:
        return [[] for _ in lines], (0,) * len(lines)

    result: list[list[Token]] = []
    states: list[int] = []
    state = _S_CODE

    if spec.mode == "markdown":
        for line in lines:
            tokens, state = _tokenize_markdown_line(line, state)
            result.append(tokens)
            states.append(state)
    elif spec.mode == "config":
        for line in lines:
            result.append(_tokenize_config_line(line, spec))
            states.append(state)
    else:
        pattern = _code_line_pattern(spec)
        for line in lines:
            tokens, state = _tokenize_code_line(line, spec, pattern, state)
            result.append(tokens)
            states.append(state)
    return result, tuple(states)


def tokenize_document(lines: list[str], filetype: str) -> list[list[Token]]:
    """Tokenize a whole document, returning tokens per line.

    Multiline state is carried top to bottom so triple strings, block
    comments and code fences highlight correctly across line boundaries.
    """
    return tokenize_document_with_states(lines, filetype)[0]


def tokenize_line(line: str, filetype: str, state: int = 0) -> tuple[list[Token], int]:
    """Tokenize one line synchronously, carrying the multiline state.

    The per-line dispatch mirrors :func:`tokenize_document` exactly
    (markdown, config and code modes), so threading the returned state from
    row to row reproduces the same per-line tokens a whole-document call
    produces.  *state* carries a multiline construct across line boundaries
    (block comment, triple string, Markdown fence); the result pairs the
    row's tokens with the state entering the next row.

    A line tokenizes in microseconds, which makes this function safe to run
    on the UI thread: the view layer calls it to re-tokenize edited rows
    while the debounced whole-document pass is pending, eliminating the
    end-of-line boundary drift of stale tokens for every token kind.
    Unknown filetypes tokenize to no tokens and pass *state* through.
    """
    spec = lang_for(filetype)
    if spec is None:
        return [], state
    if spec.mode == "markdown":
        return _tokenize_markdown_line(line, state)
    if spec.mode == "config":
        return _tokenize_config_line(line, spec), state
    return _tokenize_code_line(line, spec, _code_line_pattern(spec), state)
