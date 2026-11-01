"""Shared file preview pipeline (worker-loaded lines, tokens, cache).

Extracted from the command palette (file-manager plan-b) so the palette
screen and the file manager screen consume one read+tokenize+cache
pipeline instead of duplicating it.  The worker side (:func:`load_preview`
/ :func:`load_preview_worker`) never touches widgets; the pure Rich Text
assembly (:func:`preview_text`) is shared too, while the pane write and
the cache store stay with the owning screen.  The import direction is
one-way: consumer screens import this module, never the reverse.
"""

from __future__ import annotations

import asyncio
from collections.abc import ItemsView
from dataclasses import dataclass
from itertools import islice
from pathlib import Path
from typing import override

from rich.text import Text
from textual.widgets import RichLog

from yate.config import FilePreviewConfig
from yate.editor_syntax.engine import tokenize_document
from yate.editor_syntax.tokens import Token
from yate.logs import tracing
from yate.services.workspace import Workspace

from yate.editor_view import theme
from yate.editor_view.scrollbars import apply_scrollbar_theme, apply_slim_scrollbars

#: preview cache entry cap (FIFO eviction)
PREVIEW_CACHE_SIZE: int = 16

log = tracing.get_logger(__name__)


@dataclass(frozen=True)
class PreviewData:
    """Worker-produced preview payload (raw lines + tokens, no widgets)."""

    path: Path
    lines: list[str]
    tokens: list[list[Token]]
    mtime_ns: int
    size: int
    truncated: bool
    note: str | None  # binary / oversize / unreadable explanation


class PreviewLog(RichLog):
    """Read-only preview pane (source lines, syntax highlighted).

    ``can_focus = False`` keeps a mouse click on the pane from stealing
    focus away from the query input (one dispatch per keypress).
    """

    can_focus = False

    @override
    def on_mount(self) -> None:
        """Own the slim-scrollbar wiring and the theme painting."""
        # RichLog inherits ScrollView.on_mount (scrollbar visibility refresh).
        super().on_mount()
        # Same self-painting pattern as the explorer (issue IKJUU2): the
        # renderer sliver alone still shows Textual's opaque default track.
        apply_slim_scrollbars(self)
        self._apply_theme()
        theme.attach(self, self._apply_theme)

    def on_unmount(self) -> None:
        """Detach from the theme broadcast."""
        theme.detach(self)

    def _apply_theme(self) -> None:
        """Paint the scrollbar palette from the active theme (IKJUU2, IKINF3 pattern)."""
        apply_scrollbar_theme(self)


def load_preview(path: Path, cfg: FilePreviewConfig) -> PreviewData:
    """Read and tokenize *path* (worker thread; never touches widgets).

    Oversize and binary files degrade to a note payload with empty
    lines; successful reads keep the real ``stat`` fields so the cache
    can serve repeat cursor visits without re-reading.  Decoding is
    declared ``errors="replace"`` so odd bytes never raise.
    """
    try:
        st = path.stat()
    except OSError as exc:
        return PreviewData(
            path=path, lines=[], tokens=[], mtime_ns=0, size=0,
            truncated=False, note=f"cannot read: {exc}",
        )
    if st.st_size > cfg.max_size:
        return PreviewData(
            path=path, lines=[], tokens=[],
            mtime_ns=st.st_mtime_ns, size=st.st_size, truncated=False,
            note=f"file too large (> {cfg.max_size} bytes)",
        )
    if not Workspace.is_text_file(path):
        return PreviewData(
            path=path, lines=[], tokens=[],
            mtime_ns=st.st_mtime_ns, size=st.st_size, truncated=False,
            note="(binary file)",
        )
    lines: list[str] = []
    truncated = False
    try:
        with path.open(encoding="utf-8", errors="replace") as fh:
            lines = [
                line.rstrip("\n") for line in islice(fh, cfg.max_lines)
            ]
            truncated = next(fh, None) is not None
    except OSError as exc:
        return PreviewData(
            path=path, lines=[], tokens=[],
            mtime_ns=st.st_mtime_ns, size=st.st_size, truncated=False,
            note=f"cannot read: {exc}",
        )
    # suffix-derived filetype, same rule as Document.filetype
    filetype = path.suffix.lower().lstrip(".") or "plaintext"
    tokens: list[list[Token]] = []
    try:
        tokens = tokenize_document(lines, filetype) if lines else []
    except Exception as exc:  # noqa: BLE001 - degrade to unhighlighted text
        # A tokenizer crash must never leave the pane stuck on
        # "loading…"; align one empty token row per line so preview_text's
        # zip still walks every line and renders it plain via t.fg.
        log.warning("palette preview tokenize failed for %s: %s", path, exc)
        tokens = [[] for _ in lines]
    return PreviewData(
        path=path, lines=lines, tokens=tokens,
        mtime_ns=st.st_mtime_ns, size=st.st_size,
        truncated=truncated, note=None,
    )


async def load_preview_worker(path: Path, cfg: FilePreviewConfig) -> PreviewData:
    """Read+tokenize *path* in a thread (worker entry, never touches widgets).

    The thread part does IO + tokenize only; the Rich Text assembly and
    the widget write stay on the UI thread (same split as the editor's
    highlight worker).
    """
    return await asyncio.to_thread(load_preview, path, cfg)


def preview_text(data: PreviewData, t: theme.Theme, max_lines: int) -> Text:
    """Assemble the syntax-highlighted preview text (pure, UI-thread side).

    Token columns are clamped to the line length (backends may lag the
    source after the truncation cut); token-free spans render with the
    plain foreground.
    """
    text = Text()
    for line, row_tokens in zip(data.lines, data.tokens):
        pos = 0
        for tok in row_tokens:
            start, end = min(tok.start, len(line)), min(tok.end, len(line))
            if start > pos:
                text.append(line[pos:start], style=t.fg)
            text.append(line[start:end], style=t.syntax_style(tok.kind))
            pos = max(pos, end)
        if pos < len(line):
            text.append(line[pos:], style=t.fg)
        text.append("\n")
    if data.truncated:
        text.append(f"… truncated at {max_lines} lines", style=t.fg_dim)
    return text


class PreviewCache:
    """FIFO preview cache with mtime+size staleness revalidation."""

    def __init__(self, capacity: int = PREVIEW_CACHE_SIZE) -> None:
        """Start an empty cache holding at most *capacity* entries."""
        self._entries: dict[Path, PreviewData] = {}
        self._capacity = capacity

    def __contains__(self, path: object) -> bool:
        """Whether an entry for *path* exists (fresh or stale)."""
        return path in self._entries

    def __len__(self) -> int:
        """Number of entries currently held."""
        return len(self._entries)

    def items(self) -> ItemsView[Path, PreviewData]:
        """Iterate the held entries (probe-independent read access)."""
        return self._entries.items()

    def get(self, path: Path, mtime_ns: int, size: int) -> PreviewData | None:
        """Return the entry for *path* if it is still fresh, else ``None``.

        The *mtime_ns* / *size* arguments are the caller's current
        ``stat`` probe of the file; an entry whose stored pair no longer
        matches reads as stale and is dropped at once, so the cache only
        ever holds payloads valid at their last probe.
        """
        data = self._entries.get(path)
        if data is None:
            return None
        if data.mtime_ns != mtime_ns or data.size != size:
            del self._entries[path]
            return None
        return data

    def store(self, data: PreviewData) -> None:
        """Add *data* to the cache, evicting the oldest over capacity.

        Insertion order is the eviction order (dicts keep it), so the entry
        furthest in the past is dropped first; the just-stored payload is
        never the eviction candidate.
        """
        self._entries[data.path] = data
        while len(self._entries) > self._capacity:
            self._entries.pop(next(iter(self._entries)))

    def clear(self) -> None:
        """Drop every entry."""
        self._entries.clear()
