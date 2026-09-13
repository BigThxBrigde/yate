"""editor_syntax -- the UI-agnostic syntax highlighting layer of yate.

Pure logic, no Textual/Rich dependency: backends turn document lines into
per-line :class:`Token` spans whose ``kind`` is one of the keys in
:data:`SYNTAX_KINDS`; the view layer maps kinds to colors through the active
theme.

Backends, resolved per filetype by :mod:`yate.editor_syntax.engine`:

* :mod:`yate.editor_syntax.regex_backend` -- the zero-dependency default:
  a declarative ``LangSpec`` registry covering the built-in languages, and
  the extension point behind ``api.highlight.register``.
* :mod:`yate.editor_syntax.ts_backend` -- optional tree-sitter based
  highlighting (used when the ``tree_sitter`` package and a grammar for
  the language are available).

The re-exports below are the public API shared by the core and the
extension bridge (``services/extensions.py``): :func:`tokenize_document`
is the dispatching engine entry point, the rest is the declarative
language registry.
"""

from __future__ import annotations

from yate.editor_syntax.engine import prefer_regex, tokenize_document
from yate.editor_syntax.regex_backend import (
    LangSpec,
    available_filetypes,
    lang_for,
    language_name,
    register_language,
    resolve_filetype,
)
from yate.editor_syntax.tokens import SYNTAX_KINDS, Token

__all__ = [
    "SYNTAX_KINDS",
    "LangSpec",
    "Token",
    "available_filetypes",
    "lang_for",
    "language_name",
    "prefer_regex",
    "register_language",
    "resolve_filetype",
    "tokenize_document",
]
