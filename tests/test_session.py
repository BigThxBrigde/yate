"""The document session: tab reuse, closing and the closed-document hook.

``EditorSession`` owns the open documents and the search state for a running
editor without touching any UI, so everything here is exercised headlessly
with real files under ``tmp_path``.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from yate.config import YateConfig
from yate.editor_core import Document
from yate.editor_core.buffer import TextBuffer
from yate.session import EditorSession


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def _binary(path: Path) -> Path:
    path.write_bytes(b"\x00\x01\x02binary")
    return path


# --- documents --------------------------------------------------------------


def test_new_buffer_becomes_the_active_document() -> None:
    """A fresh session starts empty and every new buffer becomes active."""
    session = EditorSession(YateConfig())
    assert session.docs == []

    first = session.new_buffer()
    second = session.new_buffer()

    assert session.docs == [first, second]
    assert session.doc is second
    assert session.buffer is second.buffer
    assert session.index == 1


def test_open_reads_a_file_and_reuses_it_on_a_second_open(tmp_path: Path) -> None:
    """Re-opening a path activates the existing tab instead of duplicating it."""
    session = EditorSession(YateConfig())
    target = _write(tmp_path / "notes.txt", "hello\n")

    first = session.open(target)
    assert first is not None
    assert first.buffer.get_text() == "hello\n"
    assert session.is_open(target) is first

    scratch = session.new_buffer()
    again = session.open(target)

    assert again is first
    assert session.docs == [first, scratch]
    assert session.doc is first


def test_open_returns_none_for_a_binary_file(tmp_path: Path) -> None:
    """A file the workspace does not consider text is refused."""
    session = EditorSession(YateConfig())

    assert session.open(_binary(tmp_path / "blob")) is None
    assert session.docs == []


def test_open_async_reuses_an_open_document(tmp_path: Path) -> None:
    """The off-loop open shares the same reuse rule as the sync one."""
    session = EditorSession(YateConfig())
    target = _write(tmp_path / "async.txt", "one\n")

    async def scenario() -> tuple[Document | None, Document | None]:
        first = await session.open_async(target)
        session.new_buffer()
        return first, await session.open_async(target)

    first, again = asyncio.run(scenario())
    assert first is not None
    assert again is first
    assert session.doc is first


def test_open_async_returns_none_for_a_binary_file(tmp_path: Path) -> None:
    """The binary check also runs for the asynchronous open."""
    session = EditorSession(YateConfig())

    assert asyncio.run(session.open_async(_binary(tmp_path / "blob"))) is None
    assert session.docs == []


def test_open_accepts_a_path_that_does_not_exist_yet(tmp_path: Path) -> None:
    """Opening a not-yet-created file yields an empty buffer for it."""
    session = EditorSession(YateConfig())
    target = tmp_path / "brand-new.txt"

    doc = session.open(target)

    assert doc is not None
    assert doc.path == target
    assert doc.buffer.get_text() == ""
    assert not target.exists()


def test_open_async_accepts_a_path_that_does_not_exist_yet(
    tmp_path: Path,
) -> None:
    """The off-loop open also handles a missing file."""
    session = EditorSession(YateConfig())
    target = tmp_path / "brand-new.txt"

    doc = asyncio.run(session.open_async(target))

    assert doc is not None
    assert doc.path == target
    assert doc.buffer.get_text() == ""


def test_activate_moves_the_index() -> None:
    """Activating a document makes it the active one."""
    session = EditorSession(YateConfig())
    first = session.new_buffer()
    session.new_buffer()

    session.activate(first)

    assert session.index == 0
    assert session.doc is first


def test_make_buffer_uses_the_configured_indentation() -> None:
    """New buffers inherit the yaterc indentation options."""
    session = EditorSession(YateConfig())
    buf = session.make_buffer("a\nb")

    assert buf.lines == ["a", "b"]
    assert buf.tab_width == session.config.tab_width
    assert buf.use_spaces == session.config.use_spaces


def test_apply_buffer_options_updates_an_existing_buffer() -> None:
    """Buffers created before a config change pick the options up."""
    session = EditorSession(YateConfig())
    buf = TextBuffer("x", tab_width=1, use_spaces=False)

    session.apply_buffer_options(buf)

    assert buf.tab_width == session.config.tab_width
    assert buf.use_spaces == session.config.use_spaces


def test_reset_search_drops_the_query() -> None:
    """Tab switches discard the live search state."""
    session = EditorSession(YateConfig())
    session.new_buffer()
    session.search.update("a", session.buffer)
    assert session.search.query == "a"

    session.reset_search()

    assert session.search.query == ""
    assert session.search.matches == []


# --- tabs -------------------------------------------------------------------


def test_cycle_wraps_around_and_needs_two_tabs() -> None:
    """Cycling is a no-op with a single tab and wraps with several."""
    session = EditorSession(YateConfig())
    only = session.new_buffer()
    assert session.cycle(1) is None
    assert session.doc is only

    second = session.new_buffer()

    assert session.cycle(1) is only
    assert session.cycle(1) is second
    assert session.cycle(-1) is only


def test_close_active_keeps_a_neighbour_active() -> None:
    """Closing a tab leaves the previous one active."""
    session = EditorSession(YateConfig())
    first = session.new_buffer()
    second = session.new_buffer()

    closed, fallback = session.close_active()

    assert closed is second
    assert fallback is first
    assert session.docs == [first]
    assert session.doc is first


def test_closing_the_last_tab_seeds_a_scratch_buffer() -> None:
    """Closing the only tab leaves an empty unnamed buffer behind."""
    session = EditorSession(YateConfig())
    only = session.new_buffer()

    closed, fallback = session.close_active()

    assert closed is only
    assert fallback is not only
    assert fallback.path is None
    assert session.docs == [fallback]
    assert session.doc is fallback


def test_close_under_removes_only_matching_tabs(tmp_path: Path) -> None:
    """Every tab under the folder goes, tabs outside it stay."""
    session = EditorSession(YateConfig())
    folder = tmp_path / "pkg"
    folder.mkdir()
    doc_inside = session.open(_write(folder / "a.py", "x = 1\n"))
    doc_keep = session.open(_write(tmp_path / "outside.py", "y = 2\n"))
    assert doc_inside is not None
    assert doc_keep is not None

    closed = session.close_under(folder)

    assert closed == [doc_inside]
    assert session.docs == [doc_keep]


def test_close_under_a_path_without_tabs_changes_nothing(tmp_path: Path) -> None:
    """A folder with no open tabs reports an empty close list."""
    session = EditorSession(YateConfig())
    session.new_buffer()

    assert session.close_under(tmp_path / "empty") == []
    assert len(session.docs) == 1


def test_retarget_follows_a_renamed_file(tmp_path: Path) -> None:
    """Renaming a document on disk keeps the tab pointing at the new path."""
    session = EditorSession(YateConfig())
    old = _write(tmp_path / "old.txt", "text\n")
    new = tmp_path / "new.txt"
    doc = session.open(old)
    assert doc is not None

    moved = session.retarget(old, new)

    assert moved == [doc]
    assert doc.path == new
    assert session.retarget(tmp_path / "unrelated.txt", new) == []


# --- closed-document hook ---------------------------------------------------


def test_closed_hook_receives_the_closed_document() -> None:
    """Closing a tab reports exactly what it removed."""
    seen: list[list[Document]] = []
    session = EditorSession(YateConfig(), on_closed=seen.append)
    session.new_buffer()
    second = session.new_buffer()

    session.close_active()

    assert seen == [[second]]


def test_closed_hook_receives_every_document_of_a_folder_close(
    tmp_path: Path,
) -> None:
    """Closing a folder notifies the hook once with all matching documents."""
    seen: list[list[Document]] = []
    session = EditorSession(YateConfig(), on_closed=seen.append)
    folder = tmp_path / "pkg"
    folder.mkdir()
    first = session.open(_write(folder / "a.py", "x = 1\n"))
    second = session.open(_write(folder / "b.py", "y = 2\n"))
    assert first is not None and second is not None

    closed = session.close_under(folder)

    assert closed == [first, second]
    assert seen == [[first, second]]


def test_closed_hook_is_not_called_for_an_empty_close(tmp_path: Path) -> None:
    """Closing nothing must not notify the hook."""
    seen: list[list[Document]] = []
    session = EditorSession(YateConfig(), on_closed=seen.append)
    session.new_buffer()

    session.close_under(tmp_path / "nothing")

    assert seen == []
