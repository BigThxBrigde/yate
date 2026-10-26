"""Headless tests for the project-wide search primitives (plan-a).

Run with:  python -m pytest tests/test_project_search.py -v
"""

from __future__ import annotations

from pathlib import Path

import pytest

from yate.editor_core.buffer import TextBuffer
from yate.editor_core.project_search import (
    compile_query,
    replace_lines,
    search_files,
    search_lines,
)
from yate.editor_core.search import SearchEngine
from yate.editor_core.words import next_word_start, prev_word_start, word_end, word_span


# --- compile_query -----------------------------------------------------------


def test_compile_query_empty_returns_none() -> None:
    """An empty query compiles to nothing, as in SearchEngine._compile."""
    assert compile_query("", case_sensitive=False, use_regex=False, whole_word=False) is None


def test_compile_query_invalid_regex_returns_none() -> None:
    """An uncompilable pattern yields None instead of raising."""
    assert compile_query("(", use_regex=True) is None


def test_compile_query_whole_word_groups_a_regex_alternation() -> None:
    """The whole-word wrapper must group the pattern, or an alternation
    leaks into the anchors: ``foo|bar`` with ``(?:(?<=\\W)|^)foo|bar(?=\\W|$)``
    would match a bare ``bar`` inside any word (only ``foo`` keeps the
    boundaries).  The non-capturing group changes neither the ``re.escape``
    result nor the ``\\1`` backreference semantics."""
    pattern = compile_query(r"foo|bar", use_regex=True, whole_word=True)
    assert pattern is not None
    assert search_lines(["xbar"], pattern) == []
    assert search_lines(["foobar"], pattern) == []
    matches = search_lines(["foo bar"], pattern)
    assert [(m.row, m.start, m.end) for m in matches] == [(0, 0, 3), (0, 4, 7)]


# --- search_lines ------------------------------------------------------------


def test_search_lines_finds_all_occurrences() -> None:
    """Every non-overlapping occurrence becomes a LineMatch on its row."""
    pattern = compile_query("foo")
    assert pattern is not None
    matches = search_lines(["foo bar foo"], pattern)
    assert [(m.row, m.start, m.end) for m in matches] == [(0, 0, 3), (0, 8, 11)]


def test_search_lines_whole_word_skips_substring() -> None:
    """With whole_word on, a match inside a longer word is not reported."""
    pattern = compile_query("cat", whole_word=True)
    assert pattern is not None
    matches = search_lines(["category cat"], pattern)
    assert [(m.row, m.start, m.end) for m in matches] == [(0, 9, 12)]


def test_search_lines_case_flag() -> None:
    """Case-insensitive by default; case_sensitive narrows to exact case."""
    insensitive = compile_query("FOO")
    sensitive = compile_query("FOO", case_sensitive=True)
    assert insensitive is not None
    assert sensitive is not None
    assert len(search_lines(["FOO foo"], insensitive)) == 2
    assert len(search_lines(["FOO foo"], sensitive)) == 1


def test_search_lines_skips_empty_matches() -> None:
    """Zero-length matches are skipped; only real hits survive."""
    pattern = compile_query("a*", use_regex=True)
    assert pattern is not None
    matches = search_lines(["bab"], pattern)
    assert [(m.row, m.start, m.end) for m in matches] == [(0, 1, 2)]


# --- search_files ------------------------------------------------------------


def test_search_files_skips_binary_and_oversize(tmp_path: Path) -> None:
    """Undecodable and oversized files contribute no results."""
    a = tmp_path / "a.txt"
    a.write_text("has needle here", encoding="utf-8")
    b = tmp_path / "b.bin"
    b.write_bytes(b"\xff\x00needle")
    c = tmp_path / "c.txt"
    c.write_bytes(b"0" * (4 * 1024 * 1024))
    results = search_files([a, b, c], "needle")
    assert [r.path for r in results] == [a]


def test_search_files_unreadable_is_skipped(tmp_path: Path) -> None:
    """A missing file is skipped without raising."""
    good = tmp_path / "good.txt"
    good.write_text("needle", encoding="utf-8")
    missing = tmp_path / "missing.txt"
    results = search_files([missing, good], "needle")
    assert [r.path for r in results] == [good]
    assert [(m.row, m.start, m.end) for m in results[0].matches] == [(0, 0, 6)]


def test_search_files_stats_before_reading_an_oversized_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The size gate runs on ``stat`` before the bytes are read, so an
    oversized file costs no read at all (the post-read guard stays for
    files that grow between stat and read)."""
    big = tmp_path / "big.txt"
    big.write_bytes(b"x" * 10)

    def _boom(self: Path) -> bytes:
        raise AssertionError("read_bytes must not be called for oversized files")

    monkeypatch.setattr(Path, "read_bytes", _boom)
    assert search_files([big], "x", max_file_bytes=1) == []


def test_search_files_stops_at_max_matches(tmp_path: Path) -> None:
    """Collection stops at the accumulated max_matches budget."""
    paths: list[Path] = []
    for i in range(3):
        p = tmp_path / f"f{i}.txt"
        p.write_text("needle\n" * 100, encoding="utf-8")
        paths.append(p)
    results = search_files(paths, "needle", max_matches=150)
    total = sum(len(r.matches) for r in results)
    assert total == 150
    assert total <= 150


def test_search_files_reports_progress(tmp_path: Path) -> None:
    """progress is called once per scanned file with the running count."""
    seen: list[int] = []
    paths: list[Path] = []
    for i in range(2):
        p = tmp_path / f"p{i}.txt"
        p.write_text("needle", encoding="utf-8")
        paths.append(p)
    search_files(paths, "needle", progress=seen.append)
    assert seen == [1, 2]


# --- replace_lines -----------------------------------------------------------


def test_replace_lines_replaces_and_counts() -> None:
    """Matches are replaced and counted across lines."""
    pattern = compile_query("foo")
    assert pattern is not None
    new_lines, count = replace_lines(["foo bar", "x foo"], pattern, "qux")
    assert new_lines == ["qux bar", "x qux"]
    assert count == 2


def test_replace_lines_regex_backreference_per_match() -> None:
    """Backreferences expand against each matched text, not the whole line."""
    pattern = compile_query(r"(\w+)@x", use_regex=True)
    assert pattern is not None
    new_lines, count = replace_lines(["a@x b@x"], pattern, r"\1")
    assert new_lines == ["a b"]
    assert count == 2


def test_replace_lines_no_change_returns_same_object() -> None:
    """With no matches the input list is returned as-is (skip-write signal)."""
    pattern = compile_query("zzz")
    assert pattern is not None
    lines = ["abc", "def"]
    new_lines, count = replace_lines(lines, pattern, "qux")
    assert count == 0
    assert new_lines is lines


def test_replace_lines_matches_engine_replace_all() -> None:
    """replace_lines reproduces SearchEngine.replace_all line for line."""
    # Plain mode (case-insensitive default), including an untouched row.
    source: str = "foo bar foo\nnope\nFOO foo"
    buffer = TextBuffer(source)
    engine = SearchEngine()
    engine.update("foo", buffer)
    assert engine.replace_all(buffer, "qux") == 4
    pattern = compile_query("foo")
    assert pattern is not None
    # [*...] widens: this pyright build types literal.split as list[LiteralString].
    lines: list[str] = [*source.split("\n")]
    new_lines, count = replace_lines(lines, pattern, "qux")
    assert new_lines == buffer.lines
    assert count == 4

    # Regex mode with backreferences relative to each single match.
    source: str = "a@x b@x\nc@x d@x"
    buffer = TextBuffer(source)
    engine = SearchEngine()
    engine.use_regex = True
    engine.update(r"(\w+)@x", buffer)
    assert engine.replace_all(buffer, r"\1") == 4
    pattern = compile_query(r"(\w+)@x", use_regex=True)
    assert pattern is not None
    lines: list[str] = [*source.split("\n")]
    new_lines, count = replace_lines(lines, pattern, r"\1")
    assert new_lines == buffer.lines
    assert count == 4


def test_replace_lines_empty_replacement_deletes() -> None:
    """An empty replacement deletes the matches, keeping surrounding text."""
    pattern = compile_query("foo")
    assert pattern is not None
    new_lines, count = replace_lines(["foo bar", "x foo"], pattern, "")
    assert new_lines == [" bar", "x "]
    assert count == 2


# --- search_files line view --------------------------------------------------


def test_search_files_uses_newline_only_line_view(tmp_path: Path) -> None:
    """Rows follow the newline-only view: U+2028 is an ordinary character."""
    doc = tmp_path / "sep.txt"
    doc.write_text("alpha\u2028beta needle\n", encoding="utf-8")
    hits = search_files([doc], "needle")
    assert len(hits) == 1
    assert [(m.row, m.start, m.end) for m in hits[0].matches] == [(0, 11, 17)]


def test_search_files_dollar_anchor_sees_crlf_like_the_buffer(
    tmp_path: Path,
) -> None:
    """A ``$`` anchor matches the buffer view: the CRLF tail keeps it quiet."""
    doc = tmp_path / "crlf.txt"
    doc.write_bytes(b"foo\r\nbar\r\n")
    assert search_files([doc], "foo$", use_regex=True) == []
    hits = search_files([doc], "foo")
    assert [(m.row, m.start, m.end) for m in hits[0].matches] == [(0, 0, 3)]


def test_search_files_carries_hit_line_texts(tmp_path: Path) -> None:
    """Each hit file carries the raw text of its hit rows (no second read)."""
    doc = tmp_path / "crlf.txt"
    doc.write_bytes(b"first\r\nneedle x\r\nneedle y\r\n")
    hits = search_files([doc], "needle")
    assert len(hits) == 1
    fm = hits[0]
    assert [(m.row, m.start, m.end) for m in fm.matches] == [
        (1, 0, 6),
        (2, 0, 6),
    ]
    assert fm.hit_lines == {1: "needle x\r", 2: "needle y\r"}


# --- SearchEngine.next cursor positioning ------------------------------------


def test_search_jump_clears_the_vertical_goal_column() -> None:
    """Jumping to a match goes through set_cursor, so the stale vertical
    goal column is cleared and the next move_down lands relative to the
    match instead of the pre-jump target column."""
    buffer = TextBuffer("top row data ok\nne here\nmid")
    buffer.cursor = (0, 10)
    buffer.move_down()  # establishes goal column 10
    engine = SearchEngine()
    engine.update("ne", buffer)
    match = engine.next(buffer)
    assert match is not None
    assert (match.row, match.start, match.end) == (1, 0, 2)
    assert buffer.cursor == (1, 2)
    assert buffer.anchor == (1, 0)
    buffer.move_down()
    # goal col 10 would clamp onto (2, 3); the match's end column lands 2.
    assert buffer.cursor == (2, 2)


# --- SearchEngine.replace_current incremental rework --------------------------


def test_replace_current_sequence_matches_full_update() -> None:
    """Consecutive replace_current steps agree with a fresh full rescan."""
    buffer = TextBuffer("foo bar foo baz foo\nno foo\nfoo")
    engine = SearchEngine()
    engine.update("foo", buffer)
    for _ in range(5):
        assert engine.next(buffer) is not None
        assert engine.replace_current(buffer, "qux") is True
        if engine.matches:
            # the incremental list must equal a from-scratch rescan
            fresh = SearchEngine()
            fresh.update("foo", buffer)
            assert [(m.row, m.start, m.end) for m in engine.matches] == [
                (m.row, m.start, m.end) for m in fresh.matches
            ]
        # index resets, so next() re-anchors from the cursor forward
        match = engine.next(buffer)
        if match is None:
            break


def test_replace_current_growing_replacement_keeps_row_matches() -> None:
    """A longer replacement shifts later same-row matches by the delta."""
    buffer = TextBuffer("ab ab ab")
    engine = SearchEngine()
    engine.update("ab", buffer)
    assert engine.next(buffer, from_pos=(0, 0)) is not None
    assert engine.replace_current(buffer, "cd") is True
    assert buffer.lines[0] == "cd ab ab"
    assert [(m.row, m.start, m.end) for m in engine.matches] == [(0, 3, 5), (0, 6, 8)]
    assert engine.index == -1


def test_replace_current_empty_replacement_and_other_rows() -> None:
    """An empty replacement deletes the match; other rows stay untouched."""
    buffer = TextBuffer("go\ngone go\ngo")
    engine = SearchEngine()
    engine.update("go", buffer)
    assert engine.next(buffer, from_pos=(1, 0)) is not None
    assert engine.current() is not None
    assert engine.replace_current(buffer, "") is True
    assert buffer.lines == ["go", "ne go", "go"]
    assert [(m.row, m.start, m.end) for m in engine.matches] == [
        (0, 0, 2),
        (1, 3, 5),
        (2, 0, 2),
    ]


def test_replace_current_regex_backreference() -> None:
    """Regex mode expands backreferences before splicing the row matches."""
    buffer = TextBuffer("a@x b@x")
    engine = SearchEngine()
    engine.use_regex = True
    engine.update(r"(\w+)@x", buffer)
    assert engine.next(buffer, from_pos=(0, 0)) is not None
    assert engine.replace_current(buffer, r"\1") is True
    assert buffer.lines[0] == "a b@x"
    assert [(m.row, m.start, m.end) for m in engine.matches] == [(0, 2, 5)]


def test_replace_current_without_active_match_returns_false() -> None:
    """With no matches there is nothing to replace."""
    buffer = TextBuffer("abc")
    engine = SearchEngine()
    engine.update("zzz", buffer)
    assert engine.replace_current(buffer, "x") is False


# --- word motion parity (words.py run scanners vs per-character reference) ----


def _reference_next_word_start(line: str, col: int) -> int:
    """Per-character reference for next_word_start (pre-run-scanner form)."""
    import re as _re

    def is_word(ch: str) -> bool:
        return bool(_re.compile(r"\w").match(ch))

    n = len(line)
    i = min(col, n)
    if i < n and is_word(line[i]):
        while i < n and is_word(line[i]):
            i += 1
    else:
        while i < n and not is_word(line[i]) and not line[i].isspace():
            i += 1
    while i < n and line[i].isspace():
        i += 1
    return i


def _reference_prev_word_start(line: str, col: int) -> int:
    """Per-character reference for prev_word_start (pre-run-scanner form)."""
    import re as _re

    def is_word(ch: str) -> bool:
        return bool(_re.compile(r"\w").match(ch))

    i = min(col, len(line))
    while i > 0 and line[i - 1].isspace():
        i -= 1
    if i > 0 and not is_word(line[i - 1]):
        while i > 0 and not is_word(line[i - 1]) and not line[i - 1].isspace():
            i -= 1
    else:
        while i > 0 and is_word(line[i - 1]):
            i -= 1
    return i


def _reference_word_end(line: str, col: int) -> int:
    """Per-character reference for word_end (pre-run-scanner form)."""
    import re as _re

    def is_word(ch: str) -> bool:
        return bool(_re.compile(r"\w").match(ch))

    n = len(line)
    i = min(col, n)
    if i < n and line[i].isspace():
        while i < n and line[i].isspace():
            i += 1
    if i < n and is_word(line[i]):
        while i < n and is_word(line[i]):
            i += 1
    else:
        while i < n and not is_word(line[i]) and not line[i].isspace():
            i += 1
    return i


def test_word_motions_match_per_character_reference() -> None:
    """Run-based scanners agree with the per-character loops everywhere."""
    lines = [
        "foo bar-baz qux",
        "  leading and trailing  ",
        "word",
        "!!!???...,,",
        "mix_1 and _under_score2",
        "",
        "tabs\tand spaces",
    ]
    for line in lines:
        for col in range(len(line) + 1):
            assert next_word_start(line, col) == _reference_next_word_start(line, col)
            assert prev_word_start(line, col) == _reference_prev_word_start(line, col)
            assert word_end(line, col) == _reference_word_end(line, col)


def test_word_span_still_spans_the_whole_word() -> None:
    """word_span walks back to the run start, not just to the click point."""
    assert word_span("foo bar", 1) == (0, 3)
    assert word_span("foo bar", 4) == (4, 7)
    assert word_span("foo bar", 3) == (3, 3)
