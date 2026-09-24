"""Search & replace engine operating on :class:`TextBuffer` lines."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from yate.editor_core.buffer import Pos, TextBuffer


@dataclass
class Match:
    row: int
    start: int
    end: int

    @property
    def pos(self) -> Pos:
        return (self.row, self.start)


class SearchEngine:
    """Holds the current query, options, matches and the active index."""

    def __init__(self) -> None:
        self.query: str = ""
        self.case_sensitive: bool = False
        self.use_regex: bool = False
        self.whole_word: bool = False
        self.matches: list[Match] = []
        self.index: int = -1

    # ---------------------------------------------------------------- query

    def _compile(self, query: str) -> Optional[re.Pattern[str]]:
        if query == "":
            return None
        pattern = query if self.use_regex else re.escape(query)
        if self.whole_word:
            pattern = rf"(?:(?<=\W)|^){pattern}(?=\W|$)"
        flags = 0 if self.case_sensitive else re.IGNORECASE
        try:
            return re.compile(pattern, flags)
        except re.error:
            return None

    def update(self, query: str, buffer: TextBuffer) -> list[Match]:
        self.query = query
        self.matches = []
        self.index = -1
        pattern = self._compile(query)
        if pattern is None:
            return self.matches
        for row, line in enumerate(buffer.lines):
            for found in pattern.finditer(line):
                if found.start() == found.end():
                    continue
                self.matches.append(Match(row, found.start(), found.end()))
        return self.matches

    # ------------------------------------------------------------- navigate

    def _nearest_index(self, pos: Pos, forward: bool) -> int:
        if not self.matches:
            return -1
        row, col = pos
        if forward:
            for i, m in enumerate(self.matches):
                if (m.row, m.start) >= (row, col):
                    return i
            return 0
        for i in range(len(self.matches) - 1, -1, -1):
            m = self.matches[i]
            if (m.row, m.start) < (row, col):
                return i
        return len(self.matches) - 1

    def next(
        self, buffer: TextBuffer, *, forward: bool = True, from_pos: Optional[Pos] = None
    ) -> Optional[Match]:
        if not self.matches:
            return None
        pos = from_pos if from_pos is not None else buffer.cursor
        if self.index < 0:
            self.index = self._nearest_index(pos, forward)
        else:
            step = 1 if forward else -1
            self.index = (self.index + step) % len(self.matches)
        match = self.matches[self.index]
        buffer.anchor = (match.row, match.start)
        buffer.cursor = (match.row, match.end)
        return match

    def current(self) -> Optional[Match]:
        if 0 <= self.index < len(self.matches):
            return self.matches[self.index]
        return None

    # -------------------------------------------------------------- replace

    def replace_current(self, buffer: TextBuffer, replacement: str) -> bool:
        match = self.current()
        if match is None:
            return False
        buffer.anchor = (match.row, match.start)
        buffer.cursor = (match.row, match.end)
        if self.use_regex:
            pattern = self._compile(self.query)
            text = buffer.lines[match.row][match.start : match.end]
            if pattern is not None:
                replacement = pattern.sub(replacement, text)
        buffer.insert_text(replacement, kind="step")
        # Rework matches around the edit: simplest to re-run the search.
        self.update(self.query, buffer)
        return True

    def replace_all(self, buffer: TextBuffer, replacement: str) -> int:
        matches = self.update(self.query, buffer)
        if not matches:
            return 0
        # Bracket the bulk edit as one undoable history entry.
        before = buffer.snapshot()
        pattern = self._compile(self.query) if self.use_regex else None
        by_row: dict[int, list[Match]] = {}
        for match in matches:
            by_row.setdefault(match.row, []).append(match)
        count = 0
        for row, row_matches in by_row.items():
            line = buffer.lines[row]
            out: list[str] = []
            last = 0
            for match in sorted(row_matches, key=lambda m: m.start):
                out.append(line[last : match.start])
                text = line[match.start : match.end]
                repl = pattern.sub(replacement, text) if pattern is not None else replacement
                out.append(repl)
                last = match.end
                count += 1
            out.append(line[last:])
            buffer.lines[row] = "".join(out)
        buffer.anchor = None
        # A replacement can be shorter than the match, which would leave the
        # cursor past the end of its line.  Views, the status bar and the
        # smoke harness' ``cursor_col`` invariant all assume a valid position,
        # so clamp it before the edit is recorded (undo restores the original
        # cursor via ``before``).
        row, col = buffer.cursor
        buffer.cursor = (row, min(col, len(buffer.lines[row])))
        buffer.commit(before, "step")
        self.update(self.query, buffer)
        return count
