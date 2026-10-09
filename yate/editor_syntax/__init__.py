"""editor_syntax -- the UI-agnostic syntax highlighting layer of yate.

Pure logic, no Textual/Rich dependency: backends turn document lines into
per-line :class:`Token` spans whose ``kind`` is one of the keys in
:data:`SYNTAX_KINDS`; the view layer maps kinds to colors through the active
theme.

Backends, resolved per filetype by :mod:`yate.editor_syntax.engine`:

* :mod:`yate.editor_syntax.regex_backend` -- the zero-dependency default
  tokenizer, and the extension point behind ``api.highlight.register``;
* :mod:`yate.editor_syntax.ts_backend` -- optional tree-sitter based
  highlighting (used when the ``tree_sitter`` package and a grammar for
  the language are available).

The declarative language registry (``LangSpec`` and friends) lives in
:mod:`yate.editor_syntax.langdefs`; both backends depend on it in
parallel.

The re-exports below are the public API shared by the core and the
extension bridge (``services/extensions.py``): :func:`tokenize_document`
is the dispatching engine entry point, the rest is the declarative
language registry.  This is the documented public API exception
(architecture-boundaries rule 3.5): pure-leaf packages may re-export their
public surface; UI/service packages may not.
"""

from __future__ import annotations

from yate.editor_syntax.engine import prefer_regex, tokenize_document
from yate.editor_syntax.langdefs import (
    LangSpec,
    available_filetypes,
    format_filetype_candidates,
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
    "format_filetype_candidates",
    "lang_for",
    "language_name",
    "prefer_regex",
    "register_language",
    "resolve_filetype",
    "tokenize_document",
]
