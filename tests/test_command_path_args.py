"""Quoted / space-containing path parsing on the ex command line (IKJK0B).

Unit tests cover the two helpers behind the fix -- ``_split_paths``
(quote-aware tokenizing for ``:diff``) and ``_strip_quotes`` (pair
stripping for the single-path commands) -- and pilot tests prove
``:diff "..." "..."`` and ``:e "..."`` open real files whose paths
contain spaces, including the unquoted double-space case that
``run_command``'s ``split(maxsplit=1)`` keeps.
"""

# tests legitimately poke at command-table privates:
# pyright: reportPrivateUsage=false

from __future__ import annotations

import asyncio
import os
import time
from collections.abc import Callable
from pathlib import Path

# The bundled yate/extensions/ directory is auto-loaded with every YateApp;
# make sure the Python LSP extension never probes PATH or spawns a real server
# while the UI test suite runs.
os.environ["YATE_PYTHON_LSP"] = "off"

from textual.pilot import Pilot

from yate.app import YateApp
from yate.commands import _split_paths, _strip_quotes
from yate.editor_view.diffview import DiffPane, DiffScreen


async def wait_until(
    pilot: Pilot[None],
    predicate: Callable[[], bool],
    timeout: float = 5.0,
    step: float = 0.05,
) -> bool:
    """Pause until *predicate* holds; False on timeout (for worker tests)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        # pilot.pause lets background workers/to_thread callbacks progress
        await pilot.pause(step)
        if predicate():
            return True
    return predicate()


# ---- _split_paths ---------------------------------------------------------


def test_split_paths_paired_double_quotes_form_single_tokens() -> None:
    """Each double-quoted section becomes one token, quotes stripped."""
    assert _split_paths('"a b.txt" "c d.txt"') == ["a b.txt", "c d.txt"]


def test_split_paths_paired_single_quotes_form_single_tokens() -> None:
    """Single-quoted sections tokenize the same way."""
    assert _split_paths("'my file.txt'") == ["my file.txt"]


def test_split_paths_mixed_quote_kinds_are_literal_inside_sections() -> None:
    """A foreign quote char inside a section is literal; kinds can mix."""
    assert _split_paths('"it\'s here" \'say "hi"\'') == ["it's here", 'say "hi"']


def test_split_paths_unclosed_quote_keeps_rest_of_line_best_effort() -> None:
    """A forgotten closing quote keeps the remainder as one token."""
    assert _split_paths('"open dir') == ["open dir"]
    assert _split_paths('a "b c') == ["a", "b c"]


def test_split_paths_empty_quote_pairs_are_discarded() -> None:
    """Adjacent quotes never produce an empty token."""
    assert _split_paths('"" x') == ["x"]
    assert _split_paths('""') == []


def test_split_paths_plain_tokens_split_on_whitespace_unquoted() -> None:
    """Without quotes this is ordinary whitespace splitting."""
    assert _split_paths("a  b") == ["a", "b"]
    assert _split_paths("x y z") == ["x", "y", "z"]


# ---- _strip_quotes --------------------------------------------------------


def test_strip_quotes_paired_quotes_removed() -> None:
    """A wrapping quote pair is removed."""
    assert _strip_quotes('"my file.txt"') == "my file.txt"
    assert _strip_quotes("'x y'") == "x y"


def test_strip_quotes_unpaired_kept_as_is() -> None:
    """Mismatched leading/trailing quotes are kept verbatim."""
    assert _strip_quotes('"a b') == '"a b'
    assert _strip_quotes("'a b\"") == "'a b\""


def test_strip_quotes_single_char_kept_as_is() -> None:
    """A one-character string can never carry a pair (len < 2 guard)."""
    assert _strip_quotes('"') == '"'


def test_strip_quotes_empty_string_kept_as_is() -> None:
    """The empty string round-trips (len < 2 guard)."""
    assert _strip_quotes("") == ""


# ---- pilot: the real command line -----------------------------------------


def test_command_diff_quoted_paths_in_spaced_dir_opens_screen(
    tmp_path: Path,
) -> None:
    """``:diff "a b.txt" "c d.txt"`` in a spaced dir opens the 2-pane screen."""

    async def scenario() -> None:
        spaced = tmp_path / "my dir"
        spaced.mkdir()
        f1 = spaced / "a b.txt"
        f1.write_text("one\ntwo", encoding="utf-8")
        f2 = spaced / "c d.txt"
        f2.write_text("one\nTWO", encoding="utf-8")
        app = YateApp(target=tmp_path)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            app.editor.run_command(f'diff "{f1}" "{f2}"')
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, DiffScreen)
            assert len(screen.query(DiffPane)) == 2

    asyncio.run(scenario())


def test_command_edit_quoted_path_with_spaces_opens_document(
    tmp_path: Path,
) -> None:
    """``:e "my file.txt"`` opens the document whose path has a space."""

    async def scenario() -> None:
        path = tmp_path / "my file.txt"
        path.write_text("hello", encoding="utf-8")
        app = YateApp(target=tmp_path)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            app.editor.run_command(f'e "{path}"')
            assert await wait_until(
                pilot, lambda: app.editor.session.doc.path == path,
            )

    asyncio.run(scenario())


def test_command_edit_unquoted_double_spaces_preserved_in_path(
    tmp_path: Path,
) -> None:
    """``:e my  file.txt`` (unquoted) keeps the inner double space."""

    async def scenario() -> None:
        path = tmp_path / "my  file.txt"
        path.write_text("hello", encoding="utf-8")
        app = YateApp(target=tmp_path)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            # run_command must not re-join args (" ".join would collapse the
            # double space into one) -- split(maxsplit=1) keeps it intact
            app.editor.run_command(f"e {path}")
            assert await wait_until(
                pilot, lambda: app.editor.session.doc.path == path,
            )
            opened = app.editor.session.doc.path
            assert opened is not None
            assert "  " in opened.name

    asyncio.run(scenario())
