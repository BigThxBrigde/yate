"""A file backed :class:`~yate.editor_core.buffer.TextBuffer`."""

from __future__ import annotations

import asyncio
import contextlib
import locale
import os
import shutil
import tempfile
from pathlib import Path

from yate.editor_core.buffer import TextBuffer


def _current_umask() -> int:
    """The process umask, read without leaving it changed."""
    value = os.umask(0)
    os.umask(value)
    return value


class Document:
    """A :class:`TextBuffer` paired with a file path and persistence."""

    _uid_counter: int = 0

    def __init__(
        self,
        path: Path | str | None = None,
        buffer: TextBuffer | None = None,
        *,
        encoding: str = "utf-8",
    ) -> None:
        Document._uid_counter += 1
        self.uid: int = Document._uid_counter
        self.path: Path | None = Path(path) if path is not None else None
        self.buffer: TextBuffer = buffer or TextBuffer()
        self.encoding = encoding
        # Dominant line ending of the file as opened (``\r\n`` / ``\n`` /
        # ``\r``); ``save()`` converts the buffer's LF newlines back to it.
        # New buffers keep LF.  See :meth:`open` and :meth:`_dominant_eol`.
        self.eol: str = "\n"
        # Manual syntax/filetype override (`:set filetype=...`); ``None``
        # means the type is detected from the path suffix.
        self.filetype_override: str | None = None
        # Buffer edit count and line snapshot at the last save.  ``modified``
        # compares the O(1) counter first; when it differs (e.g. the save
        # landed in the middle of a coalesced typing step, or the undo stack
        # dropped old steps) it falls back to an exact line comparison, so
        # the flag stays correct across undo/redo without a full-text join.
        self._saved_edits = self.buffer.content_edits
        self._saved_lines = tuple(self.buffer.lines)
        # Memoized ``modified`` verdict, keyed on the buffer's edit counter:
        # ``(edits at query time, verdict)``.  ``save()`` clears it (the
        # baseline moves); undo/redo rewinds the counter, which simply misses
        # the cache and recomputes, so a stale verdict can never be served.
        self._modified_cache: tuple[int, bool] | None = None

    # ------------------------------------------------------------- factories

    @classmethod
    def open(cls, path: Path | str) -> Document:
        """Load *path* from disk, sniffing the encoding on failure."""
        p = Path(path)
        raw = p.read_bytes()
        text, encoding = cls._decode(raw)
        # Remember the file's dominant line ending, then normalize: the
        # buffer always works with LF, and saving converts back to the
        # recorded EOL (see save()), so a CRLF file from Windows stays CRLF.
        eol = cls._dominant_eol(text)
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        doc = cls(p, TextBuffer(text), encoding=encoding)
        doc.eol = eol
        doc.buffer.move_doc_start()
        return doc

    @classmethod
    async def open_async(cls, path: Path | str) -> Document:
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

    @staticmethod
    def _dominant_eol(text: str) -> str:
        """Return the dominant line ending of *text* as read from disk.

        Counts CRLF, lone LF and lone CR occurrences and returns the most
        frequent one; ties go to CRLF over the others and to LF over CR.  A
        text without any line ending counts as LF -- the default new files
        are saved with too.
        """
        crlf = text.count("\r\n")
        lf = text.count("\n") - crlf
        cr = text.count("\r") - crlf
        if crlf > 0 and crlf >= lf and crlf >= cr:
            return "\r\n"
        if cr > lf:
            return "\r"
        return "\n"

    # ------------------------------------------------------------ properties

    @property
    def modified(self) -> bool:
        """Whether the buffer differs from the last saved state.

        The verdict is memoized on the buffer's edit counter: an unchanged
        counter (the status bar queries this once per keystroke) returns the
        cached verdict in O(1).  A counter that moved -- forward on edits,
        backward on undo -- recomputes: first from the saved edit counter,
        falling back to an exact ``tuple(lines)`` comparison when the counter
        cannot decide (see ``__init__``), which is **O(N) in the line count**
        and therefore the expensive path on large buffers.
        """
        edits = self.buffer.content_edits
        cached = self._modified_cache
        if cached is not None and cached[0] == edits:
            return cached[1]
        if edits == self._saved_edits:
            verdict = False
        else:
            verdict = tuple(self.buffer.lines) != self._saved_lines
        self._modified_cache = (edits, verdict)
        return verdict

    @property
    def name(self) -> str:
        return self.path.name if self.path is not None else "[no name]"

    @property
    def filetype(self) -> str:
        """Effective type (extension-key form, e.g. ``py``).

        A manual override set via ``:set filetype=`` wins; otherwise the type
        is detected from the path suffix.
        """
        if self.filetype_override is not None:
            return self.filetype_override
        if self.path is None:
            return "plaintext"
        suffix = self.path.suffix.lower().lstrip(".")
        return suffix or "plaintext"

    @property
    def display_path(self) -> str:
        return str(self.path) if self.path is not None else "[no name]"

    # -------------------------------------------------------------- persist

    def save(self, path: Path | str | None = None) -> Path:
        """Write the buffer to disk and clear the modified flag.

        The write is atomic: the encoded text lands in a sibling temporary
        file first and then replaces the target in one ``os.replace`` call,
        so a crash (or a full disk) mid-write can never destroy the previous
        on-disk contents.  Encoding also happens before anything is written,
        so an unencodable character still leaves the file untouched.

        Line endings follow the file's original dominant EOL, recorded when
        :meth:`open` loaded it (CRLF / LF / CR; brand-new buffers keep LF):
        the buffer works in LF internally and ``save`` converts on the way
        out, so a Windows CRLF file round-trips as CRLF.  The recorded EOL
        is the one detected at open time -- re-rolling the file to different
        line endings externally between open and save does not change what
        the next save writes.

        ``os.replace`` swaps the inode, so the target's permission bits (and,
        where the platform exposes them, its extended attributes -- which is
        how POSIX ACLs are carried) are copied onto the temporary file first;
        without that a restricted mode such as ``0600`` would come back as the
        process umask.  A brand-new file instead lands with the umask default
        (usually ``0644``), like any other tool writes it.  The timestamps are
        deliberately *not* inherited: the saved file must look freshly written
        to build tools and file watchers.

        The replacement targets the *path*: a symbolic link is swapped for a
        regular file (no write-through), and other hard links to the previous
        inode keep the old contents.  On Windows the swap needs the target to
        be share-deletable by whoever holds it open, so a scanner or preview
        holding a non-shared handle makes the save fail with
        ``PermissionError`` -- the previous contents survive.

        Returns the path that was written.
        """
        if path is not None:
            self.path = Path(path)
        if self.path is None:
            raise ValueError("cannot save a document without a path")
        text = self.buffer.get_text()
        # Write back with the EOL recorded at open time (new buffers default
        # to LF): the buffer works in LF, so CRLF/CR files convert on the
        # way out.  See the ``eol`` attribute for the detection boundary.
        if self.eol != "\n":
            text = text.replace("\n", self.eol)
        data = text.encode(self.encoding)
        target = self.path
        # A unique sibling temp file avoids collisions between concurrent
        # saves; mkstemp creates it owner-only, which is fixed up below.
        fd, tmp_name = tempfile.mkstemp(
            dir=target.parent, prefix=target.name + ".yate-tmp-"
        )
        tmp = Path(tmp_name)
        try:
            # ``fdopen`` takes ownership of ``fd``: the sentinel keeps the
            # error path from closing a descriptor the handle already owns.
            with os.fdopen(fd, "wb") as fh:
                fd = -1
                fh.write(data)
            if target.exists():
                # Inherit the permission bits and, on POSIX, the xattrs that
                # carry ACLs -- but not the timestamps: a saved file must look
                # freshly written to build tools and file watchers, so put
                # them back to now (copystat copies atime/mtime as well).
                shutil.copystat(target, tmp)
                os.utime(tmp)
            elif os.name == "posix":
                # A new file gets the umask default, not mkstemp's 0600.
                os.chmod(tmp, 0o666 & ~_current_umask())
            os.replace(tmp, target)
        except BaseException:
            # Wide on purpose: this path only re-raises after a best-effort
            # cleanup, so no failure is ever swallowed.  Cleanup must not
            # replace the original exception either.
            if fd >= 0:
                with contextlib.suppress(OSError):
                    os.close(fd)
            with contextlib.suppress(OSError):
                tmp.unlink(missing_ok=True)
            raise
        self._saved_edits = self.buffer.content_edits
        self._saved_lines = tuple(self.buffer.lines)
        self._modified_cache = None
        return self.path
