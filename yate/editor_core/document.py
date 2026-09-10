"""A file backed :class:`~yate.editor_core.buffer.TextBuffer`."""

from __future__ import annotations

import asyncio
import locale
from pathlib import Path
from typing import Optional

from yate.editor_core.buffer import TextBuffer


class Document:
    """A :class:`TextBuffer` paired with a file path and persistence."""

    def __init__(
        self,
        path: Optional[Path | str] = None,
        buffer: Optional[TextBuffer] = None,
        *,
        encoding: str = "utf-8",
    ) -> None:
        self.path: Optional[Path] = Path(path) if path is not None else None
        self.buffer: TextBuffer = buffer or TextBuffer()
        self.encoding = encoding
        self._saved_text = self.buffer.get_text()

    # ------------------------------------------------------------- factories

    @classmethod
    def open(cls, path: Path | str) -> "Document":
        """Load *path* from disk, sniffing the encoding on failure."""
        p = Path(path)
        raw = p.read_bytes()
        text, encoding = cls._decode(raw)
        # Normalize newlines: the buffer always works with LF.  Saving writes
        # LF too (see save()), so CRLF files from Windows stay consistent.
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        doc = cls(p, TextBuffer(text), encoding=encoding)
        doc.buffer.move_doc_start()
        return doc

    @classmethod
    async def open_async(cls, path: Path | str) -> "Document":
        """Off-loop variant of :meth:`open` (file read runs in a thread)."""
        return await asyncio.to_thread(cls.open, path)

    @staticmethod
    def _decode(raw: bytes) -> tuple[str, str]:
        for enc in ("utf-8", locale.getpreferredencoding(False), "cp1252"):
            if not enc:
                continue
            try:
                return raw.decode(enc), enc
            except (UnicodeDecodeError, LookupError):
                continue
        return raw.decode("utf-8", errors="replace"), "utf-8"

    # ------------------------------------------------------------ properties

    @property
    def modified(self) -> bool:
        return self.buffer.get_text() != self._saved_text

    @property
    def name(self) -> str:
        return self.path.name if self.path is not None else "[no name]"

    @property
    def filetype(self) -> str:
        if self.path is None:
            return "plaintext"
        suffix = self.path.suffix.lower().lstrip(".")
        return suffix or "plaintext"

    @property
    def display_path(self) -> str:
        return str(self.path) if self.path is not None else "[no name]"

    # -------------------------------------------------------------- persist

    def save(self, path: Optional[Path | str] = None) -> Path:
        """Write the buffer to disk and clear the modified flag.

        Returns the path that was written.
        """
        if path is not None:
            self.path = Path(path)
        if self.path is None:
            raise ValueError("cannot save a document without a path")
        text = self.buffer.get_text()
        self.path.write_text(text, encoding=self.encoding, newline="\n")
        self._saved_text = text
        return self.path
