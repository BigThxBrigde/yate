"""Fenced-code and inline-code masking for the custom rule plugins.

``pymarkdown`` hands ``next_line`` the raw source line, so a plugin that
wants to report prose-level issues has to skip the parts of a document that
are code.  This module owns that logic once:

- :class:`FenceTracker` follows fenced code blocks across lines, accepting
  any indentation (a fence nested in a list item sits at four or more
  spaces) and closing only on the same character with a run at least as long
  as the opening one, which is what CommonMark requires;
- :func:`mask_code_spans` blanks inline code spans, matching backtick runs
  of equal length so ``` ``code`` ``` is treated like `` `code` ``.

Masking preserves column positions (masked characters become spaces), so
plugins can report offsets straight from the masked line.
"""

from __future__ import annotations

import re

_FENCE_LINE = re.compile(r"^[ \t]*(`{3,}|~{3,})(.*)$")


def mask_code_spans(line: str) -> str:
    """Blank every inline code span in *line*, keeping the column count."""
    chars = list(line)
    index = 0
    length = len(line)
    while index < length:
        if line[index] != "`":
            index += 1
            continue
        run_end = index
        while run_end < length and line[run_end] == "`":
            run_end += 1
        run = run_end - index
        close_start = run_end
        closed = False
        while close_start < length:
            if line[close_start] != "`":
                close_start += 1
                continue
            close_end = close_start
            while close_end < length and line[close_end] == "`":
                close_end += 1
            if close_end - close_start == run:
                for position in range(index, close_end):
                    chars[position] = " "
                index = close_end
                closed = True
                break
            close_start = close_end
        if not closed:
            # An unmatched backtick run is literal text, not a code span.
            index = run_end
    return "".join(chars)


class FenceTracker:
    """Track fenced code blocks across the lines of one document."""

    def __init__(self) -> None:
        """Start outside any fenced block."""
        self._open: str = ""

    def reset(self) -> None:
        """Forget the current block (called at the start of every file)."""
        self._open = ""

    def mask(self, line: str) -> str | None:
        """Return the maskable prose of *line*, or ``None`` for code lines.

        Fence lines themselves, and every line inside a fenced block, return
        ``None``: there is nothing for a prose rule to inspect there.
        """
        fence = _FENCE_LINE.match(line)
        if self._open:
            if fence is not None and self._closes(fence):
                self._open = ""
            return None
        if fence is not None:
            self._open = fence.group(1)
            return None
        return mask_code_spans(line)

    def _closes(self, fence: re.Match[str]) -> bool:
        """Whether *fence* is the closing line for the block in progress."""
        marker = fence.group(1)
        if marker[0] != self._open[0] or len(marker) < len(self._open):
            return False
        # A closing fence may carry trailing spaces/tabs only.
        return not fence.group(2).strip()
