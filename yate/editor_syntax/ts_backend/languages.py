"""Grammar / query registry and discovery for the tree-sitter backend.

Nothing in this module imports ``tree_sitter`` at module level: the
optional dependency is probed lazily so a regex-only install can import
the package safely (``resolve`` simply reports "not available").

Discovery order for a filetype:

1. extension keys explicitly registered via :func:`load_language`;
2. the canonical language name from the regex registry
   (``LangSpec.name``), mapped onto a built-in grammar pack
   (:data:`BUILTIN_PACKS`) plus a bundled ``queries/<name>.scm`` file.

Load failures (dependency missing, broken pack, bad query) are remembered
in ``_FAILED`` and never retried: the backend degrades to regex silently
instead of paying for repeated failures on every keystroke.
"""

from __future__ import annotations

import ctypes
import importlib
import re
import sys
from dataclasses import dataclass, field
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

from yate.editor_syntax.regex_backend import LangSpec, lang_for, register_language
from yate.logs import tracing

log = tracing.get_logger(__name__)


def _blocked_ts_version() -> str | None:
    """A known-broken installed tree-sitter version, or ``None``.

    py-tree-sitter 0.26.0 ships a Windows wheel that corrupts the heap while
    walking parse-tree nodes: accessing ``Node.start_point`` /
    ``Node.children`` raises a deterministic 0xC0000005 in python313.dll
    (reproducible on a single-threaded parse+walk), which kills the whole
    editor process. The dependency pin in pyproject keeps fresh installs on
    0.25.x, but environments created under the old pin can still carry 0.26;
    detect that here and degrade to the regex backend instead of crashing.
    """
    if sys.platform != "win32":
        return None
    try:
        raw = version("tree-sitter")
    except PackageNotFoundError:
        return None
    parts = raw.split(".")
    try:
        major, minor = int(parts[0]), int(parts[1])
    except (ValueError, IndexError):
        return None
    if (major, minor) == (0, 26):
        return raw
    return None


#: ``None`` when the installed tree-sitter is fine; otherwise the blocked
#: version string, under which every grammar degrades to the regex backend.
#: Computed once at import.
_BLOCKED_TS = _blocked_ts_version()


def tree_sitter_blocked() -> bool:
    """Whether the installed tree-sitter is a known heap-corrupting build."""
    return _BLOCKED_TS is not None


# canonical language name -> importable grammar pack (optional dependency).
# Names follow the regex registry's canonical LangSpec.name (``shell``, not
# the grammar's own ``bash``).  Only languages with a bundled
# queries/<name>.scm are listed; a grammar without a query cannot highlight
# anything.
BUILTIN_PACKS: dict[str, str] = {
    "python": "tree_sitter_python",
    "shell": "tree_sitter_bash",
}

QUERIES_DIR = Path(__file__).parent / "queries"

# tree-sitter capture name -> SYNTAX_KINDS key.  Captures not listed here
# (variables, punctuation, ...) intentionally inherit the default
# foreground color, matching the regex backend's visual density.
DEFAULT_CAPTURE_MAP: dict[str, str] = {
    "comment": "comment",
    "string": "string",
    "escape_sequence": "string",
    "number": "number",
    "constant": "constant",
    "constant.builtin": "constant",
    "decorator": "decorator",
    "attribute": "decorator",
    "attribute.builtin": "decorator",
    "keyword": "keyword",
    "keyword.function": "keyword",
    "keyword.modifier": "keyword",
    "keyword.operator": "operator",
    "operator": "operator",
    "function": "function",
    "function.call": "function",
    "function.method": "function",
    "function.builtin": "builtin",
    "variable.builtin": "builtin",
    "type": "type",
    "type.builtin": "type",
    "type.definition": "type",
    "property": "property",
}


@dataclass
class LoadedLanguage:
    """Everything needed to highlight one language."""

    name: str
    language: Any                 # tree_sitter.Language (untyped C binding)
    query: Any                    # tree_sitter.Query over ``highlights``
    capture_map: dict[str, str] = field(default_factory=dict[str, str])


_LANGS: dict[str, LoadedLanguage] = {}
_EXT_TO_LANG: dict[str, str] = {}
_FAILED: set[str] = set()


def tree_sitter() -> Any:
    """The ``tree_sitter`` module, or ``None`` when not installed."""
    try:
        import tree_sitter
    except ImportError:
        return None
    return tree_sitter


def ts_available() -> bool:
    """Whether the optional ``tree_sitter`` dependency is importable."""
    return tree_sitter() is not None


def _load_builtin(name: str) -> LoadedLanguage | None:
    """Load a built-in grammar pack + bundled query, or ``None``."""
    ts = tree_sitter()
    module_name = BUILTIN_PACKS.get(name)
    query_file = QUERIES_DIR / f"{name}.scm"
    if ts is None or module_name is None or not query_file.is_file():
        log.debug("tree-sitter unavailable for %r (falls back to regex)", name)
        return None
    try:
        module = importlib.import_module(module_name)
        language = ts.Language(module.language())
        query_src = query_file.read_text(encoding="utf-8")
        query = ts.Query(language, query_src)
    except Exception:
        # optional native code / third-party grammar: any failure must
        # degrade to the regex backend, never break the editor
        log.debug("tree-sitter load failed for %r (falls back to regex)", name)
        return None
    loaded = LoadedLanguage(name, language, query, dict(DEFAULT_CAPTURE_MAP))
    _LANGS[name] = loaded
    log.debug("tree-sitter language loaded: %s", name)
    return loaded


def load_language(
    name: str,
    language: Any,
    query_src: str,
    *,
    capture_map: dict[str, str] | None = None,
    extensions: tuple[str, ...] = (),
) -> None:
    """Register a grammar + query under a canonical language *name*.

    The extension API entry point (``api.syntax.register_tree_sitter``):
    *language* is a ``tree_sitter.Language`` (from a pip grammar pack or
    :func:`language_from_shared_library`), *query_src* is a
    ``highlights.scm`` query source.  *capture_map* overrides/extends
    :data:`DEFAULT_CAPTURE_MAP` for this language.
    """
    ts = tree_sitter()
    if ts is None:
        raise RuntimeError("tree_sitter is not installed")
    key = name.lower()
    merged = dict(DEFAULT_CAPTURE_MAP)
    if capture_map:
        merged.update(capture_map)
    _LANGS[key] = LoadedLanguage(key, language, ts.Query(language, query_src), merged)
    _FAILED.discard(key)
    if extensions:
        # register a bare LangSpec under the extension keys so they show up
        # in ``:set filetype=`` completion and keep a minimal regex fallback
        # (strings / numbers / operators) should the grammar fail to load;
        # tree-sitter still handles them (they are not regex-pinned)
        register_language(LangSpec(name=key), *extensions)
        for ext in extensions:
            ext_key = ext.lower().lstrip(".")
            if ext_key:
                _EXT_TO_LANG[ext_key] = key


def load_language_from_grammar(
    name: str,
    grammar: str,
    query_src: str,
    *,
    capture_map: dict[str, str] | None = None,
    extensions: tuple[str, ...] = (),
) -> None:
    """:func:`load_language` with grammar discovery for extension authors.

    *grammar* is either an importable grammar pack name
    (``"tree_sitter_yatesh"``) or a path to a compiled shared library
    (``.dll`` / ``.so`` / ``.dylib``; its C entry point must be named
    ``tree_sitter_<name>``).  Raises ``RuntimeError`` when the optional
    dependency is missing and ``ValueError`` for unresolvable grammars.
    """
    ts = tree_sitter()
    if ts is None:
        raise RuntimeError(
            "tree_sitter is not installed -- install it with "
            "'pip install yate[ts]' to use tree-sitter highlighters"
        )
    path_like = bool(Path(grammar).suffix) or "/" in grammar or "\\" in grammar
    if path_like:
        symbol = f"tree_sitter_{_symbol_name(name)}"
        language = language_from_shared_library(grammar, symbol)
    else:
        try:
            module = importlib.import_module(grammar)
        except ImportError as exc:
            raise ValueError(f"grammar pack {grammar!r} is not installed") from exc
        language = ts.Language(module.language())
    load_language(
        name, language, query_src, capture_map=capture_map, extensions=extensions
    )


def _symbol_name(name: str) -> str:
    """The C entry point suffix for a grammar (``yate shell`` -> ``yate_shell``)."""
    return re.sub(r"[^0-9A-Za-z_]", "_", name).lower()


def language_from_shared_library(library_path: str, symbol: str) -> Any:
    """Load a compiled grammar (``.dll`` / ``.so`` / ``.dylib``) via ctypes.

    *symbol* is the C entry point generated by tree-sitter's CLI
    (``tree_sitter_<language>``).  Raises on missing library or symbol;
    callers decide how to surface the error.
    """
    ts = tree_sitter()
    if ts is None:
        raise RuntimeError("tree_sitter is not installed")
    dll = ctypes.CDLL(library_path)
    try:
        fn = getattr(dll, symbol)
    except AttributeError as exc:
        raise RuntimeError(
            f"{library_path} lacks entry point {symbol!r} -- the shared "
            "library is not a tree-sitter grammar for this language"
        ) from exc
    fn.restype = ctypes.c_void_p
    return ts.Language(fn())


def resolve(filetype: str) -> LoadedLanguage | None:
    """The loaded language for *filetype*, loading it on first use.

    Returns ``None`` when the dependency is missing, the language is
    unknown, or its grammar/query failed to load before.
    """
    key = filetype.lower().lstrip(".")
    name = _EXT_TO_LANG.get(key)
    if name is None:
        spec = lang_for(key)
        if spec is not None:
            name = spec.name.lower()
    if name is None:
        return None
    loaded = _LANGS.get(name)
    if loaded is not None:
        return loaded
    if name in _FAILED:
        return None
    if _BLOCKED_TS is not None:
        # Installed tree-sitter is a known heap-corrupting release; never
        # load any grammar so the regex backend stays in charge.
        _FAILED.add(name)
        return None
    loaded = _load_builtin(name)
    if loaded is None:
        _FAILED.add(name)
        return None
    return loaded
