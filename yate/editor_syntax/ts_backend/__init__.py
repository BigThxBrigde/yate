"""Tree-sitter backend of the syntax layer (optional dependency).

This package must stay importable even when ``tree_sitter`` is not
installed: no module here imports the optional dependency at module level,
and every entry point degrades gracefully (``available_for`` returns
``False``), so :mod:`yate.editor_syntax.engine` can probe the backend
unconditionally and fall back to the regex backend.

Languages are discovered from two sources:

* built-in grammar packs (``tree_sitter_python`` / ``tree_sitter_bash``)
  paired with the bundled ``queries/*.scm`` files;
* extension-registered grammars (:func:`load_language`, typically a shared
  library loaded via :func:`language_from_shared_library`).
"""

from __future__ import annotations

from yate.editor_syntax.ts_backend.backend import available_for, tokenize_document
from yate.editor_syntax.ts_backend.languages import (
    language_from_shared_library,
    load_language,
    load_language_from_grammar,
    resolve,
    ts_available,
)

__all__ = [
    "available_for",
    "language_from_shared_library",
    "load_language",
    "load_language_from_grammar",
    "resolve",
    "ts_available",
    "tokenize_document",
]
