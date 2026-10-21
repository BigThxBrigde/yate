"""Display-width semantics of ``engine_layout`` (the alignment contract).

Every sizing helper must work in display columns -- one per UTF-8 codepoint --
because the games draw multi-byte glyphs (blocks, box drawing, icons) and a
single byte-length mistake shifts a whole border.  These tests pin the
contract at the unit level; ``tests/test_lua_games_visual.py`` re-checks it
against every rendered frame.
"""

from __future__ import annotations

from typing import Any

from lua_game_harness import engine_runtime, lua_to_python, requires_lupa


def run(runtime: Any, chunk: str) -> Any:  # noqa: Any - lupa values are untyped
    """Execute a chunk that returns one value (or a tuple)."""
    return runtime.execute(chunk)


@requires_lupa
def test_width_counts_codepoints_not_bytes() -> None:
    """Blocks and icons are one column each; ASCII stays one per byte."""
    runtime, _api = engine_runtime()

    assert run(runtime, "return engine.glyph and require('engine_layout').width('ab')") == 2
    assert run(runtime, "return require('engine_layout').width('█')") == 1
    assert run(runtime, "return require('engine_layout').width('★')") == 1
    assert run(runtime, "return require('engine_layout').width('██')") == 2
    assert run(runtime, "return require('engine_layout').width('')") == 0


@requires_lupa
def test_truncate_cuts_on_a_glyph_boundary() -> None:
    """A multi-byte glyph is never cut in half."""
    runtime, _api = engine_runtime()

    truncated = run(
        runtime, "return require('engine_layout').truncate('aa██bb', 3)"
    )
    assert truncated == "aa█"
    assert run(
        runtime, "return require('engine_layout').truncate('██', 5)"
    ) == "██"


@requires_lupa
def test_pad_left_aligns_to_the_exact_width() -> None:
    """pad() result is width columns wide, content first."""
    runtime, _api = engine_runtime()
    width = run(runtime, "return require('engine_layout').width")

    value = run(runtime, "return require('engine_layout').pad('█a', 5)")
    assert value == "█a   "
    assert run(runtime, "return require('engine_layout').width('██')") == 2
    assert len(value) == 5  # 2 glyphs (4 bytes) + 3 spaces
    assert width(value) == 5


@requires_lupa
def test_center_pads_both_sides_to_the_exact_width() -> None:
    """center() is a full-width field -- the tetris border regression guard."""
    runtime, _api = engine_runtime()

    value = run(runtime, "return require('engine_layout').center('██', 7)")
    assert value == "  ██   "
    measured = run(
        runtime, "return require('engine_layout').width(require('engine_layout').center('█', 6))"
    )
    assert measured == 6


@requires_lupa
def test_box_top_scales_with_the_title_width() -> None:
    """A wide title keeps the border at inner + 2 columns."""
    runtime, _api = engine_runtime()

    narrow = run(runtime, "return require('engine_layout').box_top('nethack', 72)")
    wide = run(
        runtime,
        "return require('engine_layout').box_top(require('engine_layout').glyph.star, 72)",
    )

    assert len(narrow) == 74
    assert len(wide) == 74
    assert narrow.endswith("╮") and wide.endswith("╮")


@requires_lupa
def test_frame_pads_every_line_to_the_inner_width() -> None:
    """frame() rows are uniform; short lines are padded, long ones truncated."""
    runtime, _api = engine_runtime()

    rows = lua_to_python(
        run(
            runtime,
            "return require('engine_layout').frame('box', 6, {'ab', '████', 'longer line'})",
        )
    )

    assert rows is not None
    assert len(rows) == 5
    for row in rows:
        assert len(row) == 8  # inner + 2 border glyphs
    assert rows[1] == "│ab    │"
    assert rows[2] == "│████  │"
    assert rows[3] == "│longer│"
