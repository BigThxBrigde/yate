"""Headless tests for the vim ``gc{motion}`` / ``gcc`` comment operator."""

from __future__ import annotations

from typing import Any, cast

from yate.actions import populate
from yate.keymaps.vim import VimKeymap, VimMode
from yate.registries import ActionRegistry

from conftest import make_action_context, make_key_ui


def _keymap_context(text: str) -> tuple[VimKeymap, Any]:
    """A vim keymap wired to the real action table over a real buffer."""
    ctx = make_action_context(text)
    ctx.doc.filetype_override = "py"
    registry = ActionRegistry()
    populate(registry, cast(Any, object()))
    ctx.ui = make_key_ui(execute=lambda name: registry.execute(name, ctx))
    return VimKeymap(), ctx


def _press(keymap: VimKeymap, ctx: Any, keys: str) -> None:
    for key in keys:
        assert keymap.handle_key(ctx, key) is True


def test_gcc_toggles_current_line_and_restores() -> None:
    keymap, ctx = _keymap_context("one\ntwo\nthree\n")
    ctx.buffer.set_cursor((1, 2))

    _press(keymap, ctx, "gcc")
    assert ctx.buffer.lines == ["one", "# two", "three", ""]

    _press(keymap, ctx, "gcc")
    assert ctx.buffer.lines == ["one", "two", "three", ""]


def test_counted_gcc_toggles_multiple_rows() -> None:
    keymap, ctx = _keymap_context("one\ntwo\nthree\nfour\n")

    _press(keymap, ctx, "2gcc")
    assert ctx.buffer.lines == ["# one", "# two", "three", "four", ""]


def test_gcj_toggles_current_and_next_row() -> None:
    keymap, ctx = _keymap_context("one\ntwo\nthree\n")

    _press(keymap, ctx, "gcj")
    assert ctx.buffer.lines == ["# one", "# two", "three", ""]


def test_gck_toggles_current_and_previous_row() -> None:
    keymap, ctx = _keymap_context("one\ntwo\nthree\n")
    ctx.buffer.set_cursor((2, 0))

    _press(keymap, ctx, "gck")
    assert ctx.buffer.lines == ["one", "# two", "# three", ""]


def test_gcw_touches_the_rows_the_word_motion_crosses() -> None:
    keymap, ctx = _keymap_context("alpha beta\ngamma\n")

    _press(keymap, ctx, "gcw")
    assert ctx.buffer.lines[0].startswith("# ")


def test_visual_gc_toggles_the_selection_and_returns_to_normal() -> None:
    keymap, ctx = _keymap_context("one\ntwo\nthree\n")
    _press(keymap, ctx, "v")
    ctx.buffer.set_cursor((1, 0))
    ctx.buffer.set_cursor((1, 3), select=True)

    _press(keymap, ctx, "gc")
    assert ctx.buffer.lines == ["one", "# two", "three", ""]
    assert keymap.mode is VimMode.NORMAL


def test_gc_unknown_follower_does_not_arm_other_state() -> None:
    keymap, ctx = _keymap_context("hello\n")

    _press(keymap, ctx, "gcq")

    assert keymap.comment_pending is False
    assert keymap.prefix is None
    assert keymap.op is None
    assert ctx.buffer.lines == ["hello", ""]


def test_gc_prefix_shows_comment_hint() -> None:
    keymap, _ctx = _keymap_context("hello\n")

    keymap.handle_key(_ctx, "g")
    labels = [label for label, _description in keymap.chord_hints()]

    assert "c" in labels


def test_gc_pending_chord_is_visible() -> None:
    keymap, ctx = _keymap_context("hello\n")

    _press(keymap, ctx, "gc")
    assert keymap.pending_prefix() == "c"
    assert keymap.comment_pending is True


def test_existing_g_motions_are_unchanged() -> None:
    keymap, ctx = _keymap_context("one\ntwo\nthree\n")

    _press(keymap, ctx, "gg")
    assert ctx.buffer.row == 0
    _press(keymap, ctx, "j")
    assert ctx.buffer.row == 1
    _press(keymap, ctx, "2gg")
    assert ctx.buffer.row == 1
    assert ctx.buffer.lines == ["one", "two", "three", ""]
