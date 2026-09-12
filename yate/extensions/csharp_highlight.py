"""C# syntax highlighting for yate, shipped as a bundled extension.

Lives at ``yate/extensions/csharp_highlight.py`` and is auto-loaded at
startup (every installation, not only the source checkout). To turn it off,
set ``disabled_extensions = ["csharp_highlight"]`` in yaterc. A modified copy
can also be dropped into ``~/.yate/extensions/`` or loaded explicitly::

    yate --ext csharp_highlight.py

After loading, ``.cs`` / ``.csx`` files highlight automatically and the type
is selectable manually with ``:set filetype=cs`` (or ``filetype=csharp``).

The highlighter is a declarative :class:`~yate.editor_view.highlight.LangSpec`:
the built-in tokenizer already handles ``//`` and ``/* ... */`` comments,
single/double quoted strings (with up to two prefix characters, so C#
``$"..."`` / ``@"..."`` / ``$@"..."`` interpolated/verbatim strings work),
numbers and the coloring of identifiers following ``class`` / ``struct`` /
``interface`` / ``enum`` / ``record``. Only the word lists are language
specific.

Known limitation: verbatim strings that actually span several source lines
(``@"line1\nline2"`` with a real newline) are not carried across lines.
"""

from __future__ import annotations

from yate.editor_view.highlight import LangSpec
from yate.services.extensions import ExtensionAPI

# Reserved keywords (true/false/null live in constants below so they get the
# constant color, as in most C# themes; primitive types live in _CS_TYPES).
_CS_KEYWORDS = frozenset({
    "abstract", "as", "base", "break", "case", "catch", "checked", "class",
    "const", "continue", "default", "delegate", "do", "else", "enum", "event",
    "explicit", "extern", "finally", "fixed", "for", "foreach", "goto", "if",
    "implicit", "in", "interface", "internal", "is", "lock", "namespace",
    "new", "operator", "out", "override", "params", "private", "protected",
    "public", "readonly", "ref", "return", "sealed", "sizeof", "stackalloc",
    "static", "struct", "switch", "this", "throw", "try", "typeof",
    "unchecked", "unsafe", "using", "virtual", "volatile", "while",
    # common contextual keywords
    "add", "alias", "ascending", "async", "await", "by", "descending", "equals",
    "from", "get", "global", "group", "into", "join", "let", "nameof", "on",
    "orderby", "partial", "record", "remove", "select", "set", "value", "var",
    "when", "where", "yield", "init", "required", "with",
})

_CS_CONSTANTS = frozenset({"true", "false", "null"})

_CS_TYPES = frozenset({
    # built-in value/reference type keywords
    "bool", "byte", "char", "decimal", "double", "dynamic", "float", "int",
    "long", "nint", "nuint", "object", "sbyte", "short", "string", "uint",
    "ulong", "ushort", "void",
    # common BCL types
    "String", "Int32", "Int64", "Boolean", "Double", "Single", "Decimal",
    "Char", "Byte", "Object", "Guid", "DateTime", "DateTimeOffset", "TimeSpan",
    "Nullable", "Exception", "ArgumentException", "ArgumentNullException",
    "InvalidOperationException", "NotImplementedException",
    "Task", "ValueTask", "Action", "Func",
    "List", "IList", "IReadOnlyList", "Dictionary", "IDictionary",
    "IReadOnlyDictionary", "HashSet", "ISet", "Queue", "Stack",
    "IEnumerable", "IEnumerator", "IAsyncEnumerable", "ICollection",
    "IDisposable", "IAsyncDisposable", "Tuple", "ValueTuple",
    "Span", "ReadOnlySpan", "Memory", "ReadOnlyMemory", "CancellationToken",
})

_CS_BUILTINS = frozenset({
    "Console", "Math", "Convert", "Environment", "Debug", "Trace", "GC",
    "StringComparer", "File", "Directory", "Path",
})

CSHARP_SPEC = LangSpec(
    name="csharp",
    mode="code",
    line_comment="//",
    block_comment=("/*", "*/"),
    # $ interpolated, @ verbatim, and $@ / @$ combinations (up to 2 prefixes).
    string_prefixes="@$",
    keywords=_CS_KEYWORDS,
    builtins=_CS_BUILTINS,
    constants=_CS_CONSTANTS,
    types=_CS_TYPES,
    type_def_words=frozenset({"class", "struct", "interface", "enum", "record"}),
)


def setup(api: ExtensionAPI) -> None:
    api.highlight.register(CSHARP_SPEC, "cs", "csx")
