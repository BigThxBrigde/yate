"""Tree-sitter highlighting: query captures to per-line tokens.

Call shape matches the regex backend (whole document in, one token list
per line out), so the view layer needs no special casing.  Strategy v1 is
a whole-document reparse per change: the view already debounces via
content-version invalidation and tokenizes off the UI thread, and
py-tree-sitter releases the GIL during parse.  Incremental
``Tree.edit()`` reparsing can be layered on later without changing this
call shape.

Capture resolution:

* capture names are mapped to SYNTAX_KINDS keys via the language's
  ``capture_map`` (unmapped captures inherit the default foreground);
* overlapping captures are resolved shortest-span-wins (a narrow capture
  inside a wide one repaints over it), matching the master-regex
  backend's flat, non-overlapping token output.

Tree-sitter points carry *byte* columns; every offset is converted to a
character column against the UTF-8 encoding of its line.
"""

from __future__ import annotations

from typing import Any, Iterator, Optional, Protocol

from yate.editor_syntax.ts_backend.languages import (
    LoadedLanguage,
    resolve,
    tree_sitter,
    tree_sitter_blocked,
)
from yate.editor_syntax.tokens import Token

__all__ = ["available_for", "tokenize_document"]


def available_for(filetype: str) -> bool:
    """Whether *filetype* can be highlighted with tree-sitter right now."""
    if tree_sitter_blocked():
        # Known heap-corrupting tree-sitter build: force the regex backend
        # even for grammars registered through the extension API.
        return False
    return resolve(filetype) is not None


def tokenize_document(lines: list[str], filetype: str) -> list[list[Token]]:
    """Highlight a whole document: one token list per input line."""
    loaded = resolve(filetype)
    if loaded is None or not lines:
        return [[] for _ in lines]
    return _highlight(lines, loaded)


def _highlight(lines: list[str], loaded: LoadedLanguage) -> list[list[Token]]:
    ts = tree_sitter()
    if ts is None:  # pragma: no cover - resolve() implies a working import
        return [[] for _ in lines]
    parser = ts.Parser(loaded.language)
    text = "\n".join(lines)
    tree = parser.parse(text.encode("utf-8"))
    captures = _query_captures(ts, loaded.query, tree.root_node)

    line_bytes = [line.encode("utf-8") for line in lines]
    # (char_start, char_end, kind) candidates per row, unsorted
    intervals: list[list[tuple[int, int, str]]] = [[] for _ in lines]
    for capture_name, nodes in captures.items():
        kind = loaded.capture_map.get(capture_name)
        if kind is None:
            continue
        for node in nodes:
            for row, start, end in _clip_to_rows(node, lines, line_bytes):
                intervals[row].append((start, end, kind))
    return [_tokens_for_row(ivs, len(line)) for line, ivs in zip(lines, intervals)]


def _query_captures(ts: Any, query: Any, node: Any) -> dict[str, list[Any]]:
    """Version-tolerant ``query.captures`` returning name -> nodes.

    py-tree-sitter >= 0.25 runs queries through ``QueryCursor``; 0.23/0.24
    expose ``Query.captures`` directly.  Both return a ``dict`` keyed by
    capture name.
    """
    cursor_cls = getattr(ts, "QueryCursor", None)
    if cursor_cls is not None:
        return dict(cursor_cls(query).captures(node))
    return dict(query.captures(node))


class _TsPoint(Protocol):
    row: int
    column: int


class _TsNode(Protocol):
    """The slice of the tree-sitter Node API the backend relies on."""

    start_point: _TsPoint
    end_point: _TsPoint


def _clip_to_rows(
    node: _TsNode, lines: list[str], line_bytes: list[bytes]
) -> Iterator[tuple[int, int, int]]:
    """Split one capture node into per-row ``(row, char_start, char_end)``.

    Multi-line nodes (block comments, triple-quoted strings, heredocs)
    produce whole-line spans on the rows they cover, mirroring how the
    regex backend emits multiline constructs.
    """
    r1, c1 = node.start_point.row, node.start_point.column
    r2, c2 = node.end_point.row, node.end_point.column
    last = len(lines) - 1
    if r1 > last:
        return
    if r2 > last:  # tree built from text that has since shrunk
        r2, c2 = last, len(line_bytes[last])
    if r1 == r2:
        yield r1, _to_char(line_bytes[r1], c1), _to_char(line_bytes[r1], c2)
        return
    yield r1, _to_char(line_bytes[r1], c1), len(lines[r1])
    for row in range(r1 + 1, r2):
        yield row, 0, len(lines[row])
    yield r2, 0, _to_char(line_bytes[r2], c2)


def _to_char(line_bytes: bytes, byte_col: int) -> int:
    """Convert a tree-sitter byte column to a character column.

    A byte column can land inside a multi-byte UTF-8 sequence (e.g. a
    stale offset after an edit): ``errors="ignore"`` then discards the
    incomplete trailing character -- its lone lead byte cannot decode on
    its own -- so such an offset maps to the first column of the character
    it cuts into.  Columns past the line end clamp to the line length.
    """
    if byte_col <= 0:
        return 0
    if byte_col >= len(line_bytes):
        byte_col = len(line_bytes)
    return len(line_bytes[:byte_col].decode("utf-8", errors="ignore"))


def _tokens_for_row(
    intervals: list[tuple[int, int, str]], line_len: int
) -> list[Token]:
    """Resolve overlapping capture spans into flat, non-overlapping tokens.

    Shorter spans claim their range first (nested captures win over the
    enclosing one), then gaps are filled by wider spans; adjacent runs of
    the same kind are merged.
    """
    if not intervals:
        return []
    claimed = bytearray(line_len)
    flat: list[tuple[int, int, str]] = []
    for start, end, kind in sorted(
        intervals, key=lambda iv: (iv[1] - iv[0], iv[0])
    ):
        start = max(0, start)
        end = min(end, line_len)
        if end <= start:
            continue
        seg_start: Optional[int] = None
        for i in range(start, end):
            if claimed[i]:
                if seg_start is not None:
                    flat.append((seg_start, i, kind))
                    seg_start = None
            elif seg_start is None:
                seg_start = i
        if seg_start is not None:
            flat.append((seg_start, end, kind))
            seg_start = None
        for i in range(start, end):
            claimed[i] = 1
    flat.sort()
    tokens: list[Token] = []
    for start, end, kind in flat:
        if tokens and tokens[-1].end == start and tokens[-1].kind == kind:
            tokens[-1] = Token(tokens[-1].start, end, kind)
        else:
            tokens.append(Token(start, end, kind))
    return tokens
