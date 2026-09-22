"""The open documents session: tabs, the active document and search state.

:class:`EditorSession` is the single owner of the *document model* of a
running editor.  It is deliberately UI free -- it knows nothing about panes,
prompts, themes or Textual -- so every layer (widgets, keymaps, actions,
commands, extensions, diagnostics) can share the same concrete object instead
of routing ``doc`` / ``buffer`` / ``docs`` / ``doc_index`` through the
application with one protocol per consumer.

Pane binding and the visual side effects (LSP notifications, repaints) stay
with the callers: the session only reports which documents changed.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Callable, Optional

from yate.config import YateConfig
from yate.editor_core import Document, SearchEngine
from yate.editor_core.buffer import TextBuffer
from yate.services.workspace import Workspace

#: Called with the documents a close operation removed (LSP didClose hook).
ClosedHook = Callable[[list[Document]], None]


class EditorSession:
    """Tabs, the active document and the search state of a running editor."""

    def __init__(
        self,
        config: YateConfig,
        *,
        on_closed: Optional[ClosedHook] = None,
    ) -> None:
        self.config = config
        self.docs: list[Document] = []
        self.index = -1
        self.search = SearchEngine()
        #: The welcome page shows on a pristine startup buffer until a user
        #: requested buffer (:enew) dismisses it; :welcome turns it back on.
        self.welcome_visible = True
        self._on_closed = on_closed

    # ------------------------------------------------------------- documents

    @property
    def doc(self) -> Document:
        """The active document."""
        return self.docs[self.index]

    @property
    def buffer(self) -> TextBuffer:
        """The buffer of the active document."""
        return self.doc.buffer

    def make_buffer(self, text: str = "") -> TextBuffer:
        """Create a buffer honoring the yaterc indentation options."""
        return TextBuffer(
            text,
            tab_width=self.config.tab_width,
            use_spaces=self.config.use_spaces,
        )

    def apply_buffer_options(self, buf: TextBuffer) -> None:
        """Propagate the yaterc indentation options onto an existing buffer."""
        buf.tab_width = self.config.tab_width
        buf.use_spaces = self.config.use_spaces

    def is_open(self, path: Path) -> Optional[Document]:
        """The document already showing *path*, or ``None``."""
        resolved = path.resolve()
        for doc in self.docs:
            if doc.path is not None and doc.path.resolve() == resolved:
                return doc
        return None

    def activate(self, doc: Document) -> None:
        """Make *doc* the active document."""
        self.index = self.docs.index(doc)

    def open(self, path: Path) -> Optional[Document]:
        """Open (or reuse) *path* and make it active.

        Returns ``None`` for a binary file; the caller reports that.
        """
        existing = self.is_open(path)
        if existing is not None:
            self.activate(existing)
            return existing
        if path.exists() and not Workspace.is_text_file(path):
            return None
        if path.exists():
            doc = Document.open(path)
        else:
            doc = Document(path, self.make_buffer())
        self.apply_buffer_options(doc.buffer)
        self.docs.append(doc)
        self.activate(doc)
        return doc

    async def open_async(self, path: Path) -> Optional[Document]:
        """Like :meth:`open`, but the disk read runs off the event loop."""
        existing = self.is_open(path)
        if existing is not None:
            self.activate(existing)
            return existing

        def _inspect() -> tuple[bool, bool]:
            return path.exists(), Workspace.is_text_file(path)

        exists, is_text = await asyncio.to_thread(_inspect)
        if exists and not is_text:
            return None
        if exists:
            doc = await Document.open_async(path)
        else:
            doc = Document(path, self.make_buffer())
        self.apply_buffer_options(doc.buffer)
        self.docs.append(doc)
        self.activate(doc)
        return doc

    def new_buffer(self) -> Document:
        """Append an empty unnamed buffer and make it active."""
        doc = Document(None, self.make_buffer())
        self.docs.append(doc)
        self.activate(doc)
        return doc

    def reset_search(self) -> None:
        """Drop the live search state (tab switches / opens clear matches)."""
        self.search = SearchEngine()

    def cycle(self, delta: int) -> Optional[Document]:
        """Activate the tab *delta* positions away (wrapping)."""
        if len(self.docs) < 2:
            return None
        index = (self.index + delta) % len(self.docs)
        self.activate(self.docs[index])
        return self.doc

    # -------------------------------------------------------------- closing

    def close_active(self) -> tuple[Document, Document]:
        """Remove the active tab; returns ``(closed, fallback)``.

        A fresh scratch buffer is appended when the last tab closes so the
        session always has an active document.
        """
        closed = self.doc
        self.docs.pop(self.index)
        if self.docs:
            fallback = self.docs[min(self.index, len(self.docs) - 1)]
        else:
            fallback = Document(None, self.make_buffer())
            self.docs.append(fallback)
        self.index = self.docs.index(fallback)
        self._notify_closed([closed])
        return closed, fallback

    def close_under(self, path: Path) -> list[Document]:
        """Close every tab whose file lives under *path* (the delete flow)."""
        target = path.resolve()
        closed = [
            doc for doc in self.docs
            if doc.path is not None and doc.path.resolve().is_relative_to(target)
        ]
        if not closed:
            return []
        self.docs = [doc for doc in self.docs if doc not in closed]
        if not self.docs:
            self.docs.append(Document(None, self.make_buffer()))
        self.index = max(0, min(self.index, len(self.docs) - 1))
        self._notify_closed(closed)
        return closed

    def retarget(self, old: Path, new: Path) -> list[Document]:
        """Keep tabs pointing at a document that was renamed on disk."""
        moved: list[Document] = []
        for doc in self.docs:
            if doc.path is not None and doc.path.resolve() == old.resolve():
                doc.path = new
                moved.append(doc)
        return moved

    def _notify_closed(self, closed: list[Document]) -> None:
        if self._on_closed is not None and closed:
            self._on_closed(closed)
