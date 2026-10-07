"""editor_core -- the UI independent heart of yate.

Contains the plain text model (:mod:`yate.editor_core.buffer`), file backed
documents (:mod:`yate.editor_core.document`) and the search/replace engine
(:mod:`yate.editor_core.search`).  None of these modules depend on a UI
framework, so the core can be used (and tested) headlessly and reused by
extensions.

The re-exports below are the documented public API exception
(architecture-boundaries rule 3.5): pure-leaf packages may re-export their
public surface; UI/service packages may not.
"""

from __future__ import annotations

from yate.editor_core.buffer import (
    BufferReadOnlyError,
    Pos,
    TextBuffer,
)
from yate.editor_core.document import Document
from yate.editor_core.search import Match, SearchEngine

__all__ = [
    "BufferReadOnlyError",
    "Pos",
    "TextBuffer",
    "Document",
    "Match",
    "SearchEngine",
]
