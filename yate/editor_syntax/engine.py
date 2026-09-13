"""Per-filetype backend selection for the syntax layer.

The engine is the single entry point the view layer calls
(:func:`tokenize_document`); it routes each filetype to the best available
backend:

1. the tree-sitter backend (:mod:`yate.editor_syntax.ts_backend`), when the
   optional dependency is installed and a grammar is registered for the
   language;
2. the declarative regex backend (:mod:`yate.editor_syntax.regex_backend`,
   built-in languages plus anything registered through
   ``api.highlight.register``);
3. unknown filetypes render as plain text (the regex backend returns no
   tokens for them).

Filetypes registered through ``api.highlight.register`` are pinned to the
regex backend via :func:`prefer_regex`, so a custom declarative
highlighter always beats the built-in tree-sitter registration for the
same extension key.
"""

from __future__ import annotations

from typing import Protocol

from yate.editor_syntax import regex_backend
from yate.editor_syntax.tokens import Token


class SyntaxBackend(Protocol):
    """What a syntax backend must provide (whole-document call shape).

    Both entry points are ``staticmethod``-compatible module-level
    functions; the protocol exists so the engine stays type-checkable
    without importing the optional tree-sitter dependency.
    """

    def available_for(self, filetype: str) -> bool:
        """Whether this backend can highlight *filetype*."""
        ...

    def tokenize_document(
        self, lines: list[str], filetype: str
    ) -> list[list[Token]]:
        """Tokenize a whole document: one token list per input line."""
        ...


# Extension keys explicitly overridden by a custom LangSpec registration;
# tree-sitter never handles these.
_REGEX_PINNED: set[str] = set()


def prefer_regex(*filetypes: str) -> None:
    """Pin *filetypes* to the regex backend.

    Called by the extension bridge when a custom ``LangSpec`` is registered:
    a deliberately registered declarative highlighter wins over the
    built-in tree-sitter registration for the same key.  Leading dots are
    tolerated (same normalization as :func:`register_language`).
    """
    for ft in filetypes:
        key = ft.lower().lstrip(".")
        if key:
            _REGEX_PINNED.add(key)


def _ts() -> SyntaxBackend | None:
    """Import the tree-sitter backend lazily; ``None`` when unavailable.

    The import (and the ``tree_sitter`` dependency check inside it) must
    stay lazy: the regex-only install must not pay for the optional
    dependency, and a missing/broken install degrades to the regex backend.
    """
    try:
        from yate.editor_syntax import ts_backend
    except ImportError:
        return None
    return ts_backend  # type: ignore[no-any-return]


def tokenize_document(lines: list[str], filetype: str) -> list[list[Token]]:
    """Tokenize a whole document with the best backend for *filetype*.

    Same contract as the regex backend's function of the same name: one
    :class:`~yate.editor_syntax.tokens.Token` list per input line.
    """
    key = filetype.lower().lstrip(".")
    if key not in _REGEX_PINNED:
        ts = _ts()
        if ts is not None and ts.available_for(filetype):
            return ts.tokenize_document(lines, filetype)
    return regex_backend.tokenize_document(lines, filetype)
